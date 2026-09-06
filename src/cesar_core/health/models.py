"""Modelos de saúde/prontidão/capacidades do César Core."""

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field


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
    reason: Literal["quota_store_misconfigured", "quota_store_unavailable"] | None = (
        Field(
            default=None,
            description="Safe quota dependency failure reason; omitted when absent.",
        )
    )


class CapabilitiesResponse(BaseModel):
    """Resposta de GET /v1/capabilities.

    Semântica exata (ver ADR 0008): informa quais capacidades existem e
    seu estado -- é um inventário, não um gate de prontidão. O transporte
    OmniRoute fica ``available`` quando ao menos um gateway de domínio está
    configurado. AI e Search são reportados independentemente; Search também
    explicita a cobertura semântica geral e de documentação técnica.
    """

    core: ServiceStatus = ServiceStatus.AVAILABLE
    application_registry: ServiceStatus = ServiceStatus.AVAILABLE
    application_authentication: ServiceStatus = ServiceStatus.NOT_CONFIGURED
    metrics: ServiceStatus = ServiceStatus.AVAILABLE
    ai: ServiceStatus = ServiceStatus.NOT_CONFIGURED
    search: ServiceStatus = Field(
        default=ServiceStatus.NOT_CONFIGURED,
        description="Aggregated Search availability for at least one purpose.",
    )
    search_general_web: ServiceStatus = Field(
        default=ServiceStatus.NOT_CONFIGURED,
        description="General Web Search target availability.",
    )
    search_technical_documentation: ServiceStatus = Field(
        default=ServiceStatus.NOT_CONFIGURED,
        description="Technical-documentation Search target availability.",
    )
    fetch: ServiceStatus = Field(
        default=ServiceStatus.NOT_CONFIGURED,
        description="Web Fetch/Enrichment Gateway availability.",
    )
    omniroute: ServiceStatus = ServiceStatus.NOT_CONFIGURED
