"""Probes detalhados e seguros do Control Plane."""

import asyncio
from datetime import UTC, datetime
from time import perf_counter

import httpx
from starlette.concurrency import run_in_threadpool

from cesar_core.admin.storage import get_store
from cesar_core.ai.config import AIConfig
from cesar_core.omniroute.client import OmniRouteClient
from cesar_core.omniroute.config import OmniRouteConfig
from cesar_core.search.config import SearchConfig
from cesar_core.security.errors import (
    QuotaStoreMisconfiguredError,
    QuotaStoreUnavailableError,
)
from cesar_core.security.quota import probe_quota_storage


def _component(name: str, status: str, started: float, **extra) -> dict:
    return {
        "name": name,
        "status": status,
        "checked_at": datetime.now(UTC).isoformat(),
        "latency_ms": round((perf_counter() - started) * 1000, 2),
        **extra,
    }


async def _sqlite() -> dict:
    started = perf_counter()
    try:
        await run_in_threadpool(get_store().list_applications)
        return _component("control_plane_sqlite", "healthy", started)
    except Exception:
        return _component(
            "control_plane_sqlite",
            "unavailable",
            started,
            reason="database_unavailable",
        )


async def _redis() -> dict:
    started = perf_counter()
    try:
        await run_in_threadpool(probe_quota_storage)
        return _component("redis", "healthy", started)
    except QuotaStoreMisconfiguredError as exc:
        return _component("redis", "degraded", started, reason=exc.code)
    except QuotaStoreUnavailableError as exc:
        return _component("redis", "unavailable", started, reason=exc.code)
    except Exception:
        return _component(
            "redis", "unavailable", started, reason="quota_store_unavailable"
        )


async def _omniroute() -> dict:
    started = perf_counter()
    enabled = []
    if AIConfig().is_configured:
        enabled.append("ai")
    if SearchConfig().is_configured:
        enabled.append("search")
    if not enabled:
        return _component("omniroute", "not_configured", started)
    clients: list[tuple[str, OmniRouteClient]] = []
    try:
        config = OmniRouteConfig()
        clients = [
            (capability, OmniRouteClient(config.for_capability(capability)))
            for capability in enabled
        ]
        for capability, client in clients:
            await client.health()
            accepted = (
                await client.chat_credential_accepted()
                if capability == "ai"
                else await client.search_credential_accepted()
            )
            if not accepted:
                return _component(
                    "omniroute",
                    "degraded",
                    started,
                    reason=f"{capability}_credential_rejected",
                )
        return _component("omniroute", "healthy", started)
    except Exception:
        return _component(
            "omniroute", "unavailable", started, reason="omniroute_unavailable"
        )
    finally:
        for _, client in clients:
            await client.aclose()


async def _searxng() -> dict:
    started = perf_counter()
    config = SearchConfig()
    if not config.enabled or not config.has_general_web_provider:
        return _component("searxng", "not_configured", started)
    if not config.provider_health_url:
        return _component(
            "searxng", "degraded", started, reason="health_url_not_configured"
        )
    try:
        async with httpx.AsyncClient(
            timeout=3, trust_env=False, follow_redirects=False
        ) as client:
            response = await client.get(config.provider_health_url)
            response.raise_for_status()
        return _component("searxng", "healthy", started)
    except (httpx.HTTPError, OSError, ValueError):
        return _component(
            "searxng", "unavailable", started, reason="searxng_unavailable"
        )


async def detailed_health() -> list[dict]:
    """Executa os quatro probes independentes em paralelo."""
    return list(await asyncio.gather(_sqlite(), _redis(), _omniroute(), _searxng()))
