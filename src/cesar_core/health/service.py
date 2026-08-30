"""Lógica de saúde/prontidão/capacidades, independente de HTTP."""

from cesar_core.health.models import CapabilitiesResponse, HealthStatus, ReadinessStatus


def get_health() -> HealthStatus:
    """O processo César Core está vivo."""
    return HealthStatus()


def get_readiness() -> ReadinessStatus:
    """Estado estrutural do Core nesta fase de fundação."""
    return ReadinessStatus()


def get_capabilities() -> CapabilitiesResponse:
    """Capacidades reais disponíveis: apenas o core, honestamente."""
    return CapabilitiesResponse()
