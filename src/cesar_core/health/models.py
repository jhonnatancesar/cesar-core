"""Modelos de saúde/prontidão/capacidades do César Core."""

from enum import StrEnum

from pydantic import BaseModel


class ServiceStatus(StrEnum):
    """Status honesto de uma capacidade do César Core.

    NOT_CONFIGURED nunca deve virar AVAILABLE por conveniência: refletir
    exatamente o que está configurado é a exigência desta TASK.
    """

    AVAILABLE = "available"
    NOT_CONFIGURED = "not_configured"


class HealthStatus(BaseModel):
    """Resposta de GET /health: só confirma que o processo está vivo."""

    status: str = "ok"


class ReadinessStatus(BaseModel):
    """Resposta de GET /ready: estado estrutural do Core."""

    status: str = "ok"
    core: ServiceStatus = ServiceStatus.AVAILABLE


class CapabilitiesResponse(BaseModel):
    """Resposta de GET /v1/capabilities.

    OmniRoute ainda não está integrado nesta TASK: ai/search/omniroute
    são reportados como not_configured, nunca fingidos como disponíveis.
    """

    core: ServiceStatus = ServiceStatus.AVAILABLE
    ai: ServiceStatus = ServiceStatus.NOT_CONFIGURED
    search: ServiceStatus = ServiceStatus.NOT_CONFIGURED
    omniroute: ServiceStatus = ServiceStatus.NOT_CONFIGURED
