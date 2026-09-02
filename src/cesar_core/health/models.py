"""Modelos de saúde/prontidão/capacidades do César Core."""

from enum import StrEnum

from pydantic import BaseModel


class ServiceStatus(StrEnum):
    """Status honesto de uma capacidade do César Core.

    NOT_CONFIGURED nunca deve virar AVAILABLE por conveniência: o valor deve
    refletir exatamente o que está configurado no runtime.
    """

    AVAILABLE = "available"
    NOT_CONFIGURED = "not_configured"


class HealthStatus(BaseModel):
    """Resposta de GET /health: só confirma que o processo está vivo.

    Não checa nenhuma dependência, capacidade ou dado -- isso é papel de
    /ready. Ver ADR 0008 para a semântica exata dos três endpoints.
    """

    status: str = "ok"


class ReadinessStatus(BaseModel):
    """Resposta de GET /ready.

    Semântica exata (ver ADR 0008): /ready responde se o César Core está
    apto a atender as capacidades ATUALMENTE configuradas/habilitadas --
    não todas as capacidades que um dia poderão existir. Uma capacidade
    NOT_CONFIGURED nunca bloqueia readiness, porque ela ainda não foi
    habilitada e portanto não impõe dependência obrigatória nenhuma.
    Quando uma capacidade for habilitada, readiness
    passa a refletir só as dependências obrigatórias dela -- nunca "ok"
    fingido para uma dependência habilitada e quebrada.
    """

    status: str = "ok"
    core: ServiceStatus = ServiceStatus.AVAILABLE


class CapabilitiesResponse(BaseModel):
    """Resposta de GET /v1/capabilities.

    Semântica exata (ver ADR 0008): informa quais capacidades existem e
    seu estado -- é um inventário, não um gate de prontidão. O transporte
    OmniRoute e AI são ``available`` somente quando o Central AI Gateway está
    habilitado e possui um modelo configurado. Search permanece independente.
    """

    core: ServiceStatus = ServiceStatus.AVAILABLE
    ai: ServiceStatus = ServiceStatus.NOT_CONFIGURED
    search: ServiceStatus = ServiceStatus.NOT_CONFIGURED
    omniroute: ServiceStatus = ServiceStatus.NOT_CONFIGURED
