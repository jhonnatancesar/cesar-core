"""118E over real loopback HTTP and the official local OmniRoute.

The transport observer delegates every request to real sockets. No manager,
provider, authentication dependency or response is mocked. Registry restriction
is temporary policy configuration inside this isolated Core test process.
"""

import asyncio
import json
import logging
import secrets
import socket
import threading
import time
from pathlib import Path

import httpx
import pytest
import uvicorn

from cesar_core.api import deps
from cesar_core.api.app import create_app
from cesar_core.applications.identity import ApplicationId, ApplicationState
from cesar_core.applications.registry import REGISTRY
from cesar_core.omniroute.client import OmniRouteClient
from cesar_core.omniroute.config import OmniRouteConfig
from cesar_core.telemetry.metrics import METRICS

pytestmark = pytest.mark.contract
KEY = Path(__file__).resolve().parents[1] / ".secrets" / "omniroute_api_key"


@pytest.fixture
def live_core(monkeypatch, tmp_path, caplog):
    if not KEY.is_file():
        pytest.skip("Requires the official local OmniRoute credential")
    upstream_secret = KEY.read_text(encoding="utf-8").strip()
    core_secret = secrets.token_urlsafe(32)
    sensitive = [upstream_secret, core_secret]
    paths = {}
    for name, value in (
        ("ai", upstream_secret),
        ("search", upstream_secret),
        ("core", core_secret),
        ("invalid", secrets.token_urlsafe(32)),
    ):
        path = tmp_path / name
        path.write_text(value, encoding="utf-8")
        paths[name] = path
        sensitive.append(value)
    # Copies exercise independent configuration paths, NOT independently issued
    # OmniRoute credentials. Invalid-key tests expose anonymous fallback honestly.
    config = {
        "AI_ENABLED": "true",
        "AI_DEFAULT_MODEL": "auto/best-free",
        "AI_MODEL_IS_PAID": "false",
        "SEARCH_ENABLED": "true",
        "SEARCH_TECHNICAL_DOCUMENTATION_PROVIDER": "context7",
        "SEARCH_PROVIDER_IS_PAID": "false",
        "OMNIROUTE_BASE_URL": "http://127.0.0.1:20128",
        "OMNIROUTE_TIMEOUT_SECONDS": "90",
        "OMNIROUTE_AI_API_KEY_FILE": str(paths["ai"]),
        "OMNIROUTE_SEARCH_API_KEY_FILE": str(paths["search"]),
        "SECURITY_GG_OFERTA_API_KEY_FILE": str(paths["core"]),
        "SECURITY_AI_REQUESTS_PER_MINUTE": "60",
        "SECURITY_SEARCH_REQUESTS_PER_MINUTE": "60",
    }
    for name, value in config.items():
        monkeypatch.setenv("CESAR_CORE_" + name, value)
    for domain in ("AI", "SEARCH"):
        for level in ("ECONOMY", "STANDARD", "QUALITY"):
            suffix = "MODEL" if domain == "AI" else "PROVIDER"
            monkeypatch.setenv(f"CESAR_CORE_{domain}_{level}_{suffix}", "")
    monkeypatch.setenv("CESAR_CORE_SEARCH_DEFAULT_PROVIDER", "")
    wire = []
    outputs = []

    class ObservedTransport(httpx.AsyncHTTPTransport):
        def __init__(self, config):
            super().__init__()
            self.config = config

        async def handle_async_request(self, request):
            row = {
                "path": request.url.path,
                "configuration": self.config.api_key_file.name,
                "credential_matches_configuration": request.headers.get("Authorization")
                == "Bearer " + self.config.read_api_key(),
                "correlation": request.headers.get("x-request-id"),
            }
            wire.append(row)
            response = await super().handle_async_request(request)
            row["status"] = response.status_code
            row["upstream_request_id"] = response.headers.get("x-request-id")
            return response

    class ObservedClient(OmniRouteClient):
        def __init__(self, config):
            super().__init__(config, transport=ObservedTransport(config))

    monkeypatch.setattr(deps, "OmniRouteClient", ObservedClient)
    deps.QUOTA_LIMITER.reset()
    METRICS.reset()
    caplog.set_level(logging.INFO)
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    server = uvicorn.Server(
        uvicorn.Config(create_app(), log_config=None, access_log=False)
    )
    thread = threading.Thread(target=server.run, kwargs={"sockets": [sock]})
    thread.start()
    deadline = time.monotonic() + 10
    while not server.started and thread.is_alive() and time.monotonic() < deadline:
        time.sleep(0.01)
    assert server.started, "Core HTTP server did not start"
    client = httpx.Client(base_url=f"http://127.0.0.1:{port}", timeout=120)

    def call(capability, token=core_secret):
        correlation = "118e-" + secrets.token_hex(8)
        headers = {
            "X-Service": "contract_test",
            "X-Purpose": "technical_documentation",
            "X-Correlation-Id": correlation,
            "X-Application-Id": "claudiao",  # cannot override credential identity
        }
        if token is not None:
            headers["Authorization"] = "Bearer " + token
        payload = {
            "requirements": {"service_class": "economy", "cost_policy": "free_only"}
        }
        if capability == "ai":
            payload["prompt"] = "Reply with exactly: CESAR_CORE_118E_OK"
            endpoint = "/v1/ai/generate"
        else:
            payload.update(
                query="Python programming language official documentation",
                max_results=3,
            )
            endpoint = "/v1/search"
        response = client.post(endpoint, headers=headers, json=payload)
        outputs.append(response.text)
        body = response.json()
        envelope = body if response.status_code == 200 else body["error"]
        assert envelope["request_id"]
        assert envelope["correlation_id"] == correlation
        assert response.headers["X-Correlation-Id"] == correlation
        return response

    try:
        yield call, client, paths, wire, outputs
    finally:
        client.close()
        server.should_exit = True
        thread.join(timeout=15)
        sock.close()
        assert not thread.is_alive()
        actual_output = (
            json.dumps(outputs + wire, default=str)
            + json.dumps([record.__dict__ for record in caplog.records], default=str)
            + METRICS.render()
        )
        leaked = any(value and value in actual_output for value in sensitive)
        assert not leaked, "Credential detected in actual output; values suppressed"
        print("118E actual HTTP/trace/metric secret scan: PASS")


@pytest.mark.parametrize("capability", ["ai", "search"])
def test_real_core_auth_authorization_and_pre_upstream_quota(
    live_core, monkeypatch, caplog, capability
):
    call, client, _, wire, outputs = live_core
    for token in (None, "invalid-unregistered-credential"):
        before = len(wire)
        assert call(capability, token).status_code == 401
        assert len(wire) == before
    assert REGISTRY[ApplicationId.CLAUDIAO].state is ApplicationState.RESERVED
    assert not REGISTRY[ApplicationId.CLAUDIAO].allowed_capabilities
    success = call(capability)
    assert success.status_code == 200, "Real configured capability failed"
    assert success.json()["upstream_request_id"]
    if capability == "ai":
        assert "CESAR_CORE_118E_OK" in success.json()["content"]
    else:
        assert 1 <= len(success.json()["results"]) <= 3
    assert any(
        getattr(record, "application", None) == "gg_oferta"
        and getattr(record, "request_id", None) == success.json()["request_id"]
        for record in caplog.records
    )
    entry = REGISTRY[ApplicationId.GG_OFERTA]
    monkeypatch.setitem(
        REGISTRY,
        ApplicationId.GG_OFERTA,
        entry.model_copy(update={"allowed_capabilities": frozenset()}),
    )
    before = len(wire)
    denied = call(capability)
    assert denied.status_code == 403
    assert denied.json()["error"]["code"] == "application_access_denied"
    assert len(wire) == before
    monkeypatch.setitem(REGISTRY, ApplicationId.GG_OFERTA, entry)
    deps.QUOTA_LIMITER.reset()
    monkeypatch.setenv(
        f"CESAR_CORE_SECURITY_{capability.upper()}_REQUESTS_PER_MINUTE", "1"
    )
    assert call(capability).status_code == 200
    before = len(wire)
    rejected = call(capability)
    assert rejected.status_code == 429
    assert rejected.json()["error"]["code"] == "quota_exceeded"
    assert int(rejected.headers["Retry-After"]) >= 1
    assert len(wire) == before
    metrics = client.get("/metrics").text
    outputs.append(metrics)
    assert 'status="429"} 1' in metrics
    assert 'application="gg_oferta"' in metrics
    assert all(row["credential_matches_configuration"] for row in wire)
    print(
        json.dumps(
            {
                "capability": capability,
                "auth": [401, 401, 200],
                "scope_denied": 403,
                "quota": [200, 429],
                "denied_upstream_requests": 0,
                "wire": wire,
            }
        )
    )


@pytest.mark.parametrize("invalid_capability", ["ai", "search"])
def test_real_upstream_credentials_do_not_silently_fallback(
    live_core, monkeypatch, invalid_capability
):
    call, _, paths, wire, _ = live_core
    monkeypatch.setenv(
        f"CESAR_CORE_OMNIROUTE_{invalid_capability.upper()}_API_KEY_FILE",
        str(paths["invalid"]),
    )
    responses = {name: call(name) for name in ("ai", "search")}
    print(
        json.dumps(
            {
                "invalid_configuration": invalid_capability,
                "statuses": {k: v.status_code for k, v in responses.items()},
                "wire": wire,
            }
        )
    )
    assert all(row["credential_matches_configuration"] for row in wire)
    valid_capability = "search" if invalid_capability == "ai" else "ai"
    assert responses[valid_capability].status_code == 200
    assert responses[invalid_capability].status_code == 502, (
        "OmniRoute did not reject the invalid configured capability credential"
    )
    invalid_path = (
        "/v1/chat/completions" if invalid_capability == "ai" else "/v1/search"
    )
    invalid_wire = [row for row in wire if row["path"] == invalid_path]
    assert len(invalid_wire) == 1
    assert invalid_wire[0]["configuration"] == "invalid"
    assert invalid_wire[0]["status"] == 401
    assert all(
        row["configuration"] == valid_capability and row["status"] == 200
        for row in wire
        if row["path"] != invalid_path
    )


def test_real_readiness_credential_and_disabled_matrix(live_core, monkeypatch):
    _, client, paths, _, outputs = live_core

    async def auth_gates():
        async with OmniRouteClient(OmniRouteConfig(api_key_file=KEY)) as upstream:
            return (
                await upstream.chat_authentication_enforced(),
                await upstream.search_authentication_enforced(),
            )

    gates = asyncio.run(auth_gates())
    matrix = {}

    def probe(name):
        response = client.get("/ready")
        outputs.append(response.text)
        matrix[name] = response.json()["status"]
        return matrix[name]

    assert all(gates), "Requires temporary REQUIRE_API_KEY=true on OmniRoute"
    assert probe("valid_configuration") == "ok"
    for capability in ("ai", "search"):
        variable = f"CESAR_CORE_OMNIROUTE_{capability.upper()}_API_KEY_FILE"
        for variant in ("invalid", "missing"):
            path = (
                paths["invalid"]
                if variant == "invalid"
                else paths[capability].with_suffix(".missing")
            )
            monkeypatch.setenv(variable, str(path))
            assert probe(f"{capability}_{variant}") == "degraded"
        monkeypatch.setenv(variable, str(paths[capability]))
    for capability in ("ai", "search"):
        monkeypatch.setenv(f"CESAR_CORE_{capability.upper()}_ENABLED", "false")
    assert probe("both_disabled") == "ok"
    print(json.dumps({"auth_gates_enforced": gates, "readiness": matrix}))
