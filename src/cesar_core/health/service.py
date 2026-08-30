"""Lógica de saúde/prontidão/capacidades, independente de HTTP.

Ver ADR 0008 para a semântica exata de /health, /ready e /v1/capabilities.
"""

from cesar_core.health.models import (
    CapabilitiesResponse,
    HealthStatus,
    ReadinessStatus,
    ServiceStatus,
)


def get_health() -> HealthStatus:
    """O processo César Core está vivo."""
    return HealthStatus()


def get_readiness() -> ReadinessStatus:
    """César Core apto a atender as capacidades atualmente habilitadas.

    Readiness é derivado de ``get_capabilities()``, não de um valor
    hardcoded independente: nesta fase (TASK-118A) nenhuma capacidade
    está habilitada, então não há dependência obrigatória a checar e o
    core está sempre pronto. Uma TASK futura que habilitar uma
    capacidade DEVE substituir a lista vazia abaixo por uma checagem
    real da dependência obrigatória dela -- nunca reportar "ok" para uma
    capacidade habilitada com dependência quebrada.
    """
    capabilities = get_capabilities()
    enabled = [
        status
        for status in (capabilities.ai, capabilities.search, capabilities.omniroute)
        if status is ServiceStatus.AVAILABLE
    ]
    is_ready = len(enabled) == 0
    return ReadinessStatus(status="ok" if is_ready else "degraded", core=ServiceStatus.AVAILABLE)


def get_capabilities() -> CapabilitiesResponse:
    """Capacidades reais disponíveis: apenas o core, honestamente."""
    return CapabilitiesResponse()
