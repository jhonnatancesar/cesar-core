"""Lógica de saúde/prontidão/capacidades, independente de HTTP.

Ver ADR 0008 para a semântica exata de /health, /ready e /v1/capabilities.
"""

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


def get_health() -> HealthStatus:
    """O processo César Core está vivo."""
    return HealthStatus()


def get_readiness(
    *,
    dependencies_ready: bool | None = None,
    ai_config: AIConfig | None = None,
    search_config: SearchConfig | None = None,
) -> ReadinessStatus:
    """César Core apto a atender as capacidades atualmente habilitadas.

    Readiness é derivado de ``get_capabilities()``, não de um valor hardcoded.
    Sem capacidade configurada, não há dependência obrigatória e o Core está
    pronto. Quando AI ou Search está habilitado, ``dependencies_ready`` deve
    representar os probes reais exigidos pela capacidade.
    """
    capabilities = get_capabilities(ai_config=ai_config, search_config=search_config)
    enabled = [
        status
        for status in (capabilities.ai, capabilities.search, capabilities.omniroute)
        if status is ServiceStatus.AVAILABLE
    ]
    is_ready = len(enabled) == 0 or dependencies_ready is True
    return ReadinessStatus(
        status="ok" if is_ready else "degraded", core=ServiceStatus.AVAILABLE
    )


def get_capabilities(
    *,
    ai_config: AIConfig | None = None,
    search_config: SearchConfig | None = None,
) -> CapabilitiesResponse:
    """Capacidades habilitadas pela configuração atual."""
    ai = ai_config or AIConfig()
    search = search_config or SearchConfig()
    return CapabilitiesResponse(
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

    try:
        client = OmniRouteClient(OmniRouteConfig())
    except ValueError:
        return get_readiness(
            ai_config=ai_config,
            search_config=search_config,
            dependencies_ready=False,
        )

    try:
        await client.health()
        authentication_enforced = True
        if ai_config.is_configured:
            authentication_enforced = (
                authentication_enforced and await client.chat_authentication_enforced()
            )
        if search_config.is_configured:
            authentication_enforced = (
                authentication_enforced
                and await client.search_authentication_enforced()
            )
    except (OmniRouteError, OSError):
        return get_readiness(
            ai_config=ai_config,
            search_config=search_config,
            dependencies_ready=False,
        )
    finally:
        await client.aclose()
    return get_readiness(
        ai_config=ai_config,
        search_config=search_config,
        dependencies_ready=authentication_enforced,
    )
