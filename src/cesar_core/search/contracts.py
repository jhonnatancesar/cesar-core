"""Contrato neutro de Web Search Gateway do César Core.

Sem provider específico: nenhuma chamada real é feita nesta fase. A
implementação concreta chega via ``search/providers/`` em TASKs futuras.
"""

from pydantic import BaseModel, Field

from cesar_core.applications.context import ApplicationContext
from cesar_core.policy.requirements import Requirements


class SearchRequest(BaseModel):
    """Forma neutra de uma requisição de busca feita ao César Core."""

    context: ApplicationContext
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
