"""Quota compartilhada pré-upstream; sem fallback em memória ou retry de consumo."""

from math import ceil

from redis import Redis, RedisError
from redis.backoff import NoBackoff
from redis.retry import Retry

from cesar_core.applications.identity import ApplicationId
from cesar_core.security.config import SecurityConfig
from cesar_core.security.credentials import read_secret
from cesar_core.security.errors import (
    QuotaExceededError,
    QuotaStoreMisconfiguredError,
    QuotaStoreUnavailableError,
)

# Uma janela começa na primeira admissão; rejeição não incrementa nem renova TTL.
# Lua serializa inclusive entre processos/instâncias, usando o relógio do Redis.
CONSUME = """
local raw = redis.call('GET', KEYS[1])
if not raw then
    redis.call('SET', KEYS[1], 1, 'PX', ARGV[2])
    return {1, tonumber(ARGV[2])}
end
local count = tonumber(raw)
local ttl = redis.call('PTTL', KEYS[1])
if not count or count < 1 or count ~= math.floor(count) or ttl < 0 then
    return redis.error_reply('Invalid quota state')
end
if count >= tonumber(ARGV[1]) then return {0, ttl} end
redis.call('INCR', KEYS[1])
return {1, ttl}
"""


class RedisQuotaStore:
    """Conexão curta por operação; nenhuma credencial/exception Redis é exposta."""

    def __init__(self, config: SecurityConfig) -> None:
        self.config = config

    def _client(self) -> Redis:
        password = (
            read_secret(self.config.quota_redis_password_file)
            if self.config.quota_redis_password_file
            else None
        )
        return Redis.from_url(
            self.config.quota_redis_url,
            username=self.config.quota_redis_username,
            password=password,
            socket_timeout=self.config.quota_redis_timeout_seconds,
            socket_connect_timeout=self.config.quota_redis_timeout_seconds,
            decode_responses=True,
            retry=Retry(NoBackoff(), 0),
            retry_on_timeout=False,
        )

    @staticmethod
    def _durable(client: Redis) -> None:
        required = {
            "appendonly": "yes",
            "appendfsync": "always",
            "maxmemory-policy": "noeviction",
            "no-appendfsync-on-rewrite": "no",
        }
        actual = client.config_get(*required)
        if any(actual.get(key) != value for key, value in required.items()):
            raise QuotaStoreMisconfiguredError()
        if client.info("persistence").get("aof_last_write_status") != "ok":
            raise QuotaStoreUnavailableError()

    def probe(self) -> None:
        with self._client() as client:
            self._durable(client)

    def consume(self, key: str, limit: int, window_ms: int) -> tuple[int, int]:
        with self._client() as client:
            self._durable(client)
            allowed, ttl = client.eval(CONSUME, 1, key, limit, window_ms)
            return int(allowed), int(ttl)

    def snapshot(self, key: str) -> tuple[int, int]:
        with self._client() as client:
            self._durable(client)
            raw = client.get(key)
            ttl = client.pttl(key)
            return (int(raw) if raw else 0, max(0, int(ttl)))

    def reset(self) -> None:
        # Seam estritamente de testes; nenhum startup chama isto.
        namespace = self.config.quota_namespace
        if not namespace.startswith("cesar-core:test:"):
            raise ValueError("Quota reset is restricted to isolated test namespaces")
        with self._client() as client:
            for key in client.scan_iter(match=f"{namespace}:*"):
                client.delete(key)


def build_store(config: SecurityConfig) -> RedisQuotaStore:
    return RedisQuotaStore(config)


def probe_quota_storage() -> None:
    try:
        build_store(SecurityConfig()).probe()
    except (RedisError, OSError, ValueError):
        raise QuotaStoreUnavailableError() from None


class QuotaLimiter:
    """Fixed window durável compartilhada; o objeto não contém contadores."""

    def __init__(self, *, window_seconds: int = 60) -> None:
        if window_seconds < 1:
            raise ValueError("Quota window must be positive")
        self._window_seconds = window_seconds

    def check(self, application_id: ApplicationId, capability: str, limit: int) -> None:
        if limit < 1 or capability not in {"ai", "search", "fetch"}:
            raise ValueError("Invalid quota policy")
        try:
            config = SecurityConfig()
            key = f"{config.quota_namespace}:{application_id.value}:{capability}"
            allowed, ttl = build_store(config).consume(
                key, limit, self._window_seconds * 1000
            )
        except (RedisError, OSError, ValueError):
            raise QuotaStoreUnavailableError() from None
        if not allowed:
            raise QuotaExceededError(max(1, ceil(ttl / 1000)))

    def reset(self) -> None:
        build_store(SecurityConfig()).reset()
