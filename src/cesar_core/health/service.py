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


def get_health() -> HealthStatus:
    """O processo César Core está vivo."""
    return HealthStatus()


def get_readiness(
    *,
    dependencies_ready: bool | None = None,
    ai_config: AIConfig | None = None,
) -> ReadinessStatus:
    """César Core apto a atender as capacidades atualmente habilitadas.

    Readiness é derivado de ``get_capabilities()``, não de um valor
    hardcoded independente: no estado atual nenhuma capacidade de domínio
    está habilitada, então não há dependência obrigatória a checar e o
    core está pronto. Uma mudança que habilitar uma
    capacidade DEVE substituir a lista vazia abaixo por uma checagem
    real da dependência obrigatória dela -- nunca reportar "ok" para uma
    capacidade habilitada com dependência quebrada.
    """
    capabilities = get_capabilities(ai_config=ai_config)
    enabled = [
        status
        for status in (capabilities.ai, capabilities.search, capabilities.omniroute)
        if status is ServiceStatus.AVAILABLE
    ]
    is_ready = len(enabled) == 0 or dependencies_ready is True
    return ReadinessStatus(
        status="ok" if is_ready else "degraded", core=ServiceStatus.AVAILABLE
    )


def get_capabilities(*, ai_config: AIConfig | None = None) -> CapabilitiesResponse:
    """Capacidades habilitadas pela configuração atual."""
    config = ai_config or AIConfig()
    if not config.is_configured:
        return CapabilitiesResponse()
    return CapabilitiesResponse(
        ai=ServiceStatus.AVAILABLE,
        omniroute=ServiceStatus.AVAILABLE,
    )


async def probe_readiness() -> ReadinessStatus:
    """Confirma a dependência OmniRoute quando AI estiver habilitada."""
    ai_config = AIConfig()
    if not ai_config.is_configured:
        return get_readiness(ai_config=ai_config)

    try:
        client = OmniRouteClient(OmniRouteConfig())
    except ValueError:
        return get_readiness(ai_config=ai_config, dependencies_ready=False)

    try:
        await client.health()
        authentication_enforced = await client.chat_authentication_enforced()
    except (OmniRouteError, OSError):
        return get_readiness(ai_config=ai_config, dependencies_ready=False)
    finally:
        await client.aclose()
    return get_readiness(
        ai_config=ai_config,
        dependencies_ready=authentication_enforced,
    )
