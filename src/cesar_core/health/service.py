"""Lógica de saúde/prontidão/capacidades, independente de HTTP.

Ver ADR 0008 para a semântica exata de /health, /ready e /v1/capabilities.
"""

import httpx
from starlette.concurrency import run_in_threadpool

from cesar_core.admin.config import AdminConfig
from cesar_core.admin.storage import get_store
from cesar_core.ai.config import AIConfig
from cesar_core.health.models import (
    CapabilitiesResponse,
    HealthStatus,
    ReadinessStatus,
    ServiceStatus,
)
from cesar_core.omniroute.client import OmniRouteClient
from cesar_core.omniroute.config import OmniRouteConfig
from cesar_core.omniroute.errors import OmniRouteError
from cesar_core.search.config import SearchConfig
from cesar_core.security.config import SecurityConfig
from cesar_core.security.credentials import read_secret
from cesar_core.security.errors import QuotaStoreUnavailableError
from cesar_core.security.quota import probe_quota_storage


def get_health() -> HealthStatus:
    """O processo César Core está vivo."""
    return HealthStatus()


def get_readiness(
    *,
    dependencies_ready: bool | None = None,
    ai_config: AIConfig | None = None,
    search_config: SearchConfig | None = None,
    security_config: SecurityConfig | None = None,
) -> ReadinessStatus:
    """César Core apto a atender as capacidades atualmente habilitadas.

    Readiness é derivado de ``get_capabilities()``, não de um valor hardcoded.
    Sem capacidade configurada, não há dependência obrigatória e o Core está
    pronto. Quando AI ou Search está habilitado, ``dependencies_ready`` deve
    representar os probes reais exigidos pela capacidade.
    """
    capabilities = get_capabilities(
        ai_config=ai_config,
        search_config=search_config,
        security_config=security_config,
    )
    domain_enabled = any(
        status is ServiceStatus.AVAILABLE
        for status in (capabilities.ai, capabilities.search)
    )
    is_ready = not domain_enabled or (
        capabilities.application_authentication is ServiceStatus.AVAILABLE
        and dependencies_ready is True
    )
    return ReadinessStatus(
        status="ok" if is_ready else "degraded", core=ServiceStatus.AVAILABLE
    )


def get_capabilities(
    *,
    ai_config: AIConfig | None = None,
    search_config: SearchConfig | None = None,
    security_config: SecurityConfig | None = None,
) -> CapabilitiesResponse:
    """Capacidades habilitadas pela configuração atual."""
    ai = ai_config or AIConfig()
    search = search_config or SearchConfig()
    security = security_config or SecurityConfig()
    authentication_configured = security.is_configured
    if not authentication_configured:
        pepper = AdminConfig().credential_pepper_file
        authentication_configured = bool(
            pepper
            and pepper.is_file()
            and any(row["revoked_at"] is None for row in get_store().list_credentials())
        )
    return CapabilitiesResponse(
        application_authentication=(
            ServiceStatus.AVAILABLE
            if authentication_configured
            else ServiceStatus.NOT_CONFIGURED
        ),
        ai=(
            ServiceStatus.AVAILABLE
            if ai.is_configured
            else ServiceStatus.NOT_CONFIGURED
        ),
        search=(
            ServiceStatus.AVAILABLE
            if search.is_configured
            else ServiceStatus.NOT_CONFIGURED
        ),
        search_general_web=(
            ServiceStatus.AVAILABLE
            if search.enabled and search.has_general_web_provider
            else ServiceStatus.NOT_CONFIGURED
        ),
        search_technical_documentation=(
            ServiceStatus.AVAILABLE
            if search.enabled
            and search.normalized_technical_documentation_provider is not None
            else ServiceStatus.NOT_CONFIGURED
        ),
        omniroute=(
            ServiceStatus.AVAILABLE
            if ai.is_configured or search.is_configured
            else ServiceStatus.NOT_CONFIGURED
        ),
    )


async def probe_readiness() -> ReadinessStatus:
    """Confirma OmniRoute e auth das capacidades habilitadas."""
    ai_config = AIConfig()
    search_config = SearchConfig()
    if not ai_config.is_configured and not search_config.is_configured:
        return get_readiness(ai_config=ai_config, search_config=search_config)

    security_config = SecurityConfig()
    try:
        credential_path = security_config.gg_oferta_api_key_file
        if credential_path is not None:
            read_secret(credential_path)
        else:
            pepper = AdminConfig().credential_pepper_file
            if (
                not pepper
                or not pepper.is_file()
                or not any(
                    row["revoked_at"] is None for row in get_store().list_credentials()
                )
            ):
                raise OSError("Application credential is not configured")
        await run_in_threadpool(probe_quota_storage)
        omniroute_config = OmniRouteConfig()
        capability_configs: list[tuple[str, OmniRouteConfig]] = []
        if ai_config.is_configured:
            capability_configs.append(("ai", omniroute_config.for_capability("ai")))
        if search_config.is_configured:
            capability_configs.append(
                ("search", omniroute_config.for_capability("search"))
            )
        clients = [
            (capability, OmniRouteClient(config))
            for capability, config in capability_configs
        ]
    except QuotaStoreUnavailableError as exc:
        return ReadinessStatus(status="degraded", reason=exc.code)
    except (OSError, ValueError):
        return get_readiness(
            ai_config=ai_config,
            search_config=search_config,
            security_config=security_config,
            dependencies_ready=False,
        )

    try:
        authentication_enforced = True
        if search_config.has_general_web_provider and search_config.provider_health_url:
            async with httpx.AsyncClient(
                timeout=3, trust_env=False, follow_redirects=False
            ) as probe:
                response = await probe.get(search_config.provider_health_url)
                response.raise_for_status()
        for capability, client in clients:
            await client.health()
            if capability == "ai":
                authentication_enforced = (
                    authentication_enforced
                    and await client.chat_authentication_enforced()
                    and await client.chat_credential_accepted()
                )
            else:
                authentication_enforced = (
                    authentication_enforced
                    and await client.search_authentication_enforced()
                    and await client.search_credential_accepted()
                )
    except (OmniRouteError, OSError, httpx.HTTPError, ValueError):
        return get_readiness(
            ai_config=ai_config,
            search_config=search_config,
            security_config=security_config,
            dependencies_ready=False,
        )
    finally:
        for _, client in clients:
            await client.aclose()
    return get_readiness(
        ai_config=ai_config,
        search_config=search_config,
        security_config=security_config,
        dependencies_ready=authentication_enforced,
    )
