"""Falhas do armazenamento são normalizadas, nunca autorização implícita."""

from unittest.mock import MagicMock

import pytest
from pydantic import ValidationError
from redis import ConnectionError, TimeoutError

from cesar_core.applications.identity import ApplicationId
from cesar_core.health.service import get_health, probe_readiness
from cesar_core.security.config import SecurityConfig
from cesar_core.security.errors import (
    QuotaExceededError,
    QuotaStoreMisconfiguredError,
    QuotaStoreUnavailableError,
)
from cesar_core.security.quota import QuotaLimiter, RedisQuotaStore, probe_quota_storage


@pytest.mark.parametrize("url", ["https://localhost", "redis://user:secret@localhost",
                                "redis://localhost/0?password=value", "redis://localhost/bad"])
def test_url_never_accepts_inline_credentials_or_client_overrides(url):
    with pytest.raises(ValidationError):
        SecurityConfig(_env_file=None, quota_redis_url=url)


def test_password_file_and_no_retries(monkeypatch, tmp_path):
    path = tmp_path / "password"
    path.write_text("unit-only-secret")
    factory = MagicMock()
    monkeypatch.setattr("cesar_core.security.quota.Redis.from_url", factory)
    RedisQuotaStore(SecurityConfig(_env_file=None, quota_redis_password_file=path))._client()
    assert factory.call_args.kwargs["password"] == "unit-only-secret"
    assert factory.call_args.kwargs["retry"].get_retries() == 0
    assert factory.call_args.kwargs["retry_on_timeout"] is False


@pytest.mark.parametrize("error", [ConnectionError("private"), TimeoutError("private"), OSError("private")])
def test_fail_closed_without_retry_or_exception_detail(monkeypatch, error):
    store = MagicMock()
    store.consume.side_effect = error
    store.probe.side_effect = error
    monkeypatch.setattr("cesar_core.security.quota.build_store", lambda config: store)
    with pytest.raises(QuotaStoreUnavailableError) as failure:
        QuotaLimiter().check(ApplicationId.GG_OFERTA, "ai", 1)
    assert "private" not in str(failure.value)
    assert store.consume.call_count == 1
    with pytest.raises(QuotaStoreUnavailableError):
        probe_quota_storage()


@pytest.mark.parametrize("bad", ["appendonly", "appendfsync", "maxmemory-policy", "no-appendfsync-on-rewrite", "aof"])
def test_durability_is_required(bad):
    client = MagicMock()
    config = {"appendonly": "yes", "appendfsync": "always", "maxmemory-policy": "noeviction",
              "no-appendfsync-on-rewrite": "no"}
    if bad != "aof":
        config[bad] = "unsafe"
    client.config_get.return_value = config
    client.info.return_value = {"aof_last_write_status": "err" if bad == "aof" else "ok"}
    with pytest.raises(QuotaStoreUnavailableError) as failure:
        RedisQuotaStore._durable(client)
    assert failure.value.code == ("quota_store_unavailable" if bad == "aof" else "quota_store_misconfigured")
    client.config_set.assert_not_called()
    client.eval.assert_not_called()


def test_probe_consume_and_reset_test_namespace(monkeypatch):
    store = RedisQuotaStore(SecurityConfig(_env_file=None, quota_namespace="cesar-core:test:unit"))
    client = MagicMock()
    client.__enter__.return_value = client
    client.config_get.return_value = {"appendonly": "yes", "appendfsync": "always",
                                    "maxmemory-policy": "noeviction", "no-appendfsync-on-rewrite": "no"}
    client.info.return_value = {"aof_last_write_status": "ok"}
    client.eval.return_value = [0, 301]
    client.scan_iter.return_value = ["cesar-core:test:unit:gg_oferta:ai"]
    monkeypatch.setattr(store, "_client", lambda: client)
    store.probe()
    assert store.consume("key", 1, 60000) == (0, 301)
    store.reset()
    client.delete.assert_called_once_with("cesar-core:test:unit:gg_oferta:ai")


def test_runtime_reset_forbidden_and_invalid_policy(monkeypatch):
    monkeypatch.delenv("CESAR_CORE_SECURITY_QUOTA_NAMESPACE")
    with pytest.raises(ValueError, match="restricted"):
        RedisQuotaStore(SecurityConfig(_env_file=None)).reset()
    with pytest.raises(ValueError):
        QuotaLimiter(window_seconds=0)
    with pytest.raises(ValueError):
        QuotaLimiter().check(ApplicationId.GG_OFERTA, "other", 1)


def test_store_shared_by_limiter_objects_and_capabilities_independent():
    QuotaLimiter().check(ApplicationId.GG_OFERTA, "ai", 1)
    with pytest.raises(QuotaExceededError):
        QuotaLimiter().check(ApplicationId.GG_OFERTA, "ai", 1)
    QuotaLimiter().check(ApplicationId.GG_OFERTA, "search", 1)


@pytest.mark.parametrize("error,reason", [
    (ConnectionError("secret"), "quota_store_unavailable"),
    (QuotaStoreMisconfiguredError(), "quota_store_misconfigured"),
])
async def test_quota_storage_down_degrades_ready_but_not_liveness(monkeypatch, tmp_path, error, reason):
    key = tmp_path / "key"
    key.write_text("unit")
    monkeypatch.setenv("CESAR_CORE_AI_ENABLED", "true")
    monkeypatch.setenv("CESAR_CORE_AI_DEFAULT_MODEL", "model")
    monkeypatch.setenv("CESAR_CORE_SECURITY_GG_OFERTA_API_KEY_FILE", str(key))
    store = MagicMock()
    store.probe.side_effect = error
    store.consume.side_effect = error
    monkeypatch.setattr("cesar_core.security.quota.build_store", lambda config: store)
    readiness = await probe_readiness()
    assert readiness.status == "degraded" and readiness.reason == reason
    with pytest.raises(QuotaStoreUnavailableError) as failure:
        QuotaLimiter().check(ApplicationId.GG_OFERTA, "ai", 1)
    assert failure.value.code == reason
    assert get_health().status == "ok"
    monkeypatch.setenv("CESAR_CORE_AI_ENABLED", "false")
    monkeypatch.setenv("CESAR_CORE_SEARCH_ENABLED", "false")
    assert (await probe_readiness()).status == "ok"
    assert (await probe_readiness()).reason is None
