import json
from datetime import UTC, datetime, timedelta

import pytest
from argon2 import PasswordHasher
from fastapi.testclient import TestClient

from cesar_core.admin import cli
from cesar_core.admin.auth import rate_limit_login
from cesar_core.admin.config import AdminConfig
from cesar_core.admin.crypto import (
    credential_hmac,
    digest,
    issue_credential,
    parse_credential,
    read_required,
)
from cesar_core.admin.storage import ControlPlaneStore, get_store
from cesar_core.api.app import create_app
from cesar_core.security.authentication import ApplicationAuthenticator
from cesar_core.security.config import SecurityConfig
from cesar_core.security.errors import InvalidCredentialError


@pytest.fixture
def admin_client(monkeypatch, tmp_path):
    password = "correct horse battery staple"
    password_file = tmp_path / "admin-password"
    password_file.write_text(PasswordHasher().hash(password), encoding="utf-8")
    pepper_file = tmp_path / "credential-pepper"
    pepper_file.write_bytes(b"p" * 48)
    monkeypatch.setenv("CESAR_CORE_ADMIN_PASSWORD_HASH_FILE", str(password_file))
    monkeypatch.setenv("CESAR_CORE_ADMIN_CREDENTIAL_PEPPER_FILE", str(pepper_file))
    monkeypatch.setenv("CESAR_CORE_ADMIN_ALLOWED_ORIGIN", "http://127.0.0.1")
    monkeypatch.setenv("CESAR_CORE_ADMIN_COOKIE_SECURE", "false")
    monkeypatch.setattr("cesar_core.admin.routes.rate_limit_login", lambda *_: None)
    with TestClient(create_app(), base_url="http://127.0.0.1") as client:
        yield client, password


def login(client: TestClient, password: str) -> str:
    response = client.post(
        "/admin/api/login",
        json={"password": password},
        headers={"Origin": "http://127.0.0.1"},
    )
    assert response.status_code == 200
    return response.json()["csrf_token"]


def test_admin_requires_configuration(monkeypatch):
    monkeypatch.delenv("CESAR_CORE_ADMIN_PASSWORD_HASH_FILE", raising=False)
    client = TestClient(create_app())
    assert client.get("/admin").status_code == 503
    assert client.get("/admin/api/applications").status_code == 503


def test_login_rejects_origin_and_bad_password(admin_client):
    client, password = admin_client
    assert (
        client.post("/admin/api/login", json={"password": password}).status_code == 403
    )
    response = client.post(
        "/admin/api/login",
        json={"password": "wrong"},
        headers={"Origin": "http://127.0.0.1"},
    )
    assert response.status_code == 401
    assert get_store().list_audit()[0]["outcome"] == "denied"


def test_session_csrf_logout_and_ui(admin_client):
    client, password = admin_client
    csrf = login(client, password)
    assert client.get("/admin/api/session").json() == {"authenticated": True}
    assert client.get("/admin").status_code == 200
    assert client.post("/admin/api/logout").status_code == 403
    assert (
        client.post(
            "/admin/api/logout",
            headers={"Origin": "http://127.0.0.1", "X-CSRF-Token": csrf},
        ).status_code
        == 204
    )
    assert client.get("/admin/api/session").status_code == 401


def test_application_and_credential_lifecycle(admin_client):
    client, password = admin_client
    csrf = login(client, password)
    write = {"Origin": "http://127.0.0.1", "X-CSRF-Token": csrf}
    created = client.post(
        "/admin/api/applications",
        json={
            "id": "sample_app",
            "display_name": "Sample",
            "client_id": "sample-client",
        },
        headers=write,
    )
    assert created.status_code == 201
    assert created.json()["state"] == "disabled"
    assert (
        client.put(
            "/admin/api/applications/sample_app",
            json={
                "display_name": "Sample",
                "state": "active",
                "capabilities": ["ai"],
                "quotas": {"ai": 4},
            },
            headers=write,
        ).status_code
        == 409
    )
    issued = client.post(
        "/admin/api/credentials",
        json={"application_id": "sample_app", "name": "dev"},
        headers=write,
    )
    assert issued.status_code == 201
    token = issued.json()["credential"]
    assert token.startswith("cc_")
    updated = client.put(
        "/admin/api/applications/sample_app",
        json={
            "display_name": "Sample App",
            "state": "active",
            "capabilities": ["ai"],
            "quotas": {"ai": 4},
        },
        headers=write,
    )
    assert updated.status_code == 200
    assert (
        ApplicationAuthenticator(SecurityConfig()).authenticate(f"Bearer {token}")
        == "sample_app"
    )
    credentials = client.get("/admin/api/credentials?application_id=sample_app").json()
    assert token not in json.dumps(credentials)
    credential_id = issued.json()["id"]
    assert client.post(
        f"/admin/api/credentials/{credential_id}/revoke", headers=write
    ).json() == {"revoked": True}
    with pytest.raises(InvalidCredentialError):
        ApplicationAuthenticator(SecurityConfig()).authenticate(f"Bearer {token}")


def test_reserved_application_is_immutable(admin_client):
    client, password = admin_client
    csrf = login(client, password)
    response = client.put(
        "/admin/api/applications/claudiao",
        json={
            "display_name": "Claudião",
            "state": "active",
            "capabilities": ["ai"],
            "quotas": {"ai": 1},
        },
        headers={"Origin": "http://127.0.0.1", "X-CSRF-Token": csrf},
    )
    assert response.status_code in {409, 403}
    assert get_store().get_application("claudiao")["state"] == "reserved"
    credential = client.post(
        "/admin/api/credentials",
        json={"application_id": "claudiao", "name": "forbidden"},
        headers={"Origin": "http://127.0.0.1", "X-CSRF-Token": csrf},
    )
    assert credential.status_code == 409
    assert get_store().active_credential_count("claudiao") == 0


def test_read_only_admin_views(admin_client, monkeypatch):
    client, password = admin_client
    login(client, password)

    async def healthy():
        return [
            {"name": "redis", "status": "healthy", "checked_at": "now", "latency_ms": 1}
        ]

    monkeypatch.setattr("cesar_core.admin.routes.detailed_health", healthy)
    assert client.get("/admin/api/overview").status_code == 200
    assert client.get("/admin/api/routes").status_code == 200
    assert client.get("/admin/api/usage?days=7").status_code == 200
    health = client.get("/admin/api/health")
    assert health.status_code == 200
    assert health.json()["status"] == "ok"
    assert health.json()["components"][1]["name"] == "redis"
    assert client.get("/admin/api/audit").status_code == 200


def test_storage_persists_sessions_audit_and_rollups(tmp_path):
    store = ControlPlaneStore(tmp_path / "state.sqlite3")
    store.migrate()
    store.bootstrap(10, 20)
    store.create_session("id", digest("token"), digest("csrf"), 300)
    assert store.validate_session(digest("token"), digest("csrf"), 60)
    assert store.validate_session(digest("token"), digest("bad"), 60) is None
    store.audit("test", "success", metadata={"safe": True})
    store.record_usage("gg_oferta", "ai", "success", tokens=3)
    assert store.list_audit()[0]["metadata"] == {"safe": True}
    assert store.usage(1)[0]["tokens"] == 3
    store.migrate()


def test_usage_retention_prunes_only_expired_rollups(tmp_path):
    store = ControlPlaneStore(tmp_path / "state.sqlite3")
    store.migrate()
    store.bootstrap(10, 20)
    store.record_usage("gg_oferta", "ai", "success", tokens=3)
    old = (datetime.now(UTC) - timedelta(days=40)).isoformat()
    with store.connect() as db:
        db.execute("UPDATE usage_rollups SET bucket_hour=?", (old,))
    assert store.prune_usage(30) == 1
    assert store.usage(365) == []


def test_bootstrap_is_idempotent_and_preserves_admin_changes(tmp_path):
    store = ControlPlaneStore(tmp_path / "state.sqlite3")
    store.migrate()
    store.bootstrap(10, 20)
    store.update_application(
        "gg_oferta",
        display_name="GG Oferta editado",
        state="disabled",
        capabilities={"ai"},
        quotas={"ai": 7},
    )
    store.bootstrap(99, 99)
    rows = store.list_applications()
    assert len(rows) == 2
    assert store.get_application("gg_oferta")["display_name"] == "GG Oferta editado"
    assert store.get_quota("gg_oferta", "ai") == 7
    assert store.get_application("claudiao")["state"] == "reserved"


def test_dynamic_credentials_are_multiple_and_never_persist_plaintext(
    admin_client, tmp_path
):
    client, password = admin_client
    csrf = login(client, password)
    headers = {"Origin": "http://127.0.0.1", "X-CSRF-Token": csrf}
    tokens = []
    for name in ("blue", "green"):
        response = client.post(
            "/admin/api/credentials",
            json={"application_id": "gg_oferta", "name": name},
            headers=headers,
        )
        assert response.headers["cache-control"] == "no-store"
        tokens.append(response.json()["credential"])
    for token in tokens:
        assert (
            ApplicationAuthenticator(SecurityConfig()).authenticate(f"Bearer {token}")
            == "gg_oferta"
        )
        assert token.encode() not in AdminConfig().database_path.read_bytes()


def test_quota_policy_edit_does_not_reset_redis_window(monkeypatch):
    from cesar_core.security.quota import build_store

    config = SecurityConfig()
    store = build_store(config)
    key = f"{config.quota_namespace}:gg_oferta:ai"
    assert store.consume(key, 10, 60_000)[0] == 1
    current = get_store().get_application("gg_oferta")
    get_store().update_application(
        "gg_oferta",
        display_name=current["display_name"],
        state="active",
        capabilities={"ai", "search"},
        quotas={"ai": 1, "search": 60},
    )
    assert store.consume(key, get_store().get_quota("gg_oferta", "ai"), 60_000)[0] == 0


def test_admin_config_only_allows_insecure_cookie_on_loopback():
    config = AdminConfig(allowed_origin="http://127.0.0.1:8100/", cookie_secure=False)
    assert config.allowed_origin == "http://127.0.0.1:8100"
    with pytest.raises(ValueError):
        AdminConfig(allowed_origin="http://example.com", cookie_secure=False)
    with pytest.raises(ValueError):
        AdminConfig(allowed_origin="http://127.0.0.1:8100", cookie_secure=True)


def test_login_rate_limit_uses_redis_and_fails_closed(monkeypatch):
    class Client:
        count = 0

        def __enter__(self):
            return self

        def __exit__(self, *_):
            return None

        def incr(self, _key):
            self.count += 1
            return self.count

        def expire(self, _key, _seconds):
            return True

    class Store:
        client = Client()

        def _client(self):
            return self.client

    monkeypatch.setattr("cesar_core.admin.auth.build_store", lambda _: Store())
    request = type(
        "Request", (), {"client": type("ClientInfo", (), {"host": "127.0.0.1"})()}
    )()
    config = AdminConfig(login_attempts_per_minute=1)
    rate_limit_login(request, config)
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as exc:
        rate_limit_login(request, config)
    assert exc.value.status_code == 429


def test_session_absolute_and_idle_expiration(tmp_path):
    store = ControlPlaneStore(tmp_path / "sessions.sqlite3")
    store.migrate()
    store.bootstrap(1, 1)
    store.create_session("expired", digest("old"), digest("csrf"), 300)
    old = (datetime.now(UTC) - timedelta(hours=2)).isoformat()
    with store.connect() as db:
        db.execute(
            "UPDATE admin_sessions SET last_seen_at=?,expires_at=? WHERE id='expired'",
            (old, old),
        )
    assert store.validate_session(digest("old"), None, 60) is None


def test_different_pepper_invalidates_dynamic_credential(
    admin_client, monkeypatch, tmp_path
):
    client, password = admin_client
    csrf = login(client, password)
    issued = client.post(
        "/admin/api/credentials",
        json={"application_id": "gg_oferta", "name": "pepper-test"},
        headers={"Origin": "http://127.0.0.1", "X-CSRF-Token": csrf},
    ).json()
    other = tmp_path / "other-pepper"
    other.write_bytes(b"z" * 48)
    monkeypatch.setenv("CESAR_CORE_ADMIN_CREDENTIAL_PEPPER_FILE", str(other))
    with pytest.raises(InvalidCredentialError):
        ApplicationAuthenticator(SecurityConfig()).authenticate(
            f"Bearer {issued['credential']}"
        )


def test_legacy_shaped_token_is_rejected_when_only_dynamic_auth_is_configured(
    admin_client,
):
    with pytest.raises(InvalidCredentialError):
        ApplicationAuthenticator(SecurityConfig()).authenticate(
            "Bearer definitely-not-a-dynamic-credential"
        )


def test_crypto_boundaries(tmp_path):
    pepper = b"x" * 32
    credential_id, token, _, stored = issue_credential(pepper)
    parsed = parse_credential(token)
    assert parsed and credential_hmac(pepper, *parsed) == stored
    assert parse_credential("bad") is None
    assert digest("a") != digest("b")
    weak = tmp_path / "weak"
    weak.write_text("weak", encoding="utf-8")
    with pytest.raises(RuntimeError):
        read_required(weak)


def test_password_hash_cli(monkeypatch, capsys):
    answers = iter(["a secure local password", "a secure local password"])
    monkeypatch.setattr(cli, "getpass", lambda _: next(answers))
    cli.main()
    encoded = capsys.readouterr().out.strip()
    assert PasswordHasher().verify(encoded, "a secure local password")
