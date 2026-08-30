"""Contrato neutro de Web Search Gateway do César Core.

Sem provider específico: nenhuma chamada real é feita nesta fase. A
implementação concreta pertence ao OmniRoute e a TASKs futuras.
"""

from pydantic import BaseModel, Field

from cesar_core.applications.identity import ApplicationId
from cesar_core.policy.requirements import Requirements


class SearchRequest(BaseModel):
    """Forma neutra de uma requisição de busca feita ao César Core."""

    application_id: ApplicationId
    correlation_id: str = Field(min_length=1)
    requirements: Requirements
    query: str = Field(min_length=1)


class SearchResult(BaseModel):
    """Um resultado individual de busca."""

    title: str
    url: str


class SearchResponse(BaseModel):
    """Forma neutra de uma resposta de busca devolvida pelo César Core."""

    correlation_id: str = Field(min_length=1)
    results: list[SearchResult] = Field(default_factory=list)
