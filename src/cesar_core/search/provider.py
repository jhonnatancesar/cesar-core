"""Boundary do provider de Web Search consumido pelo César Core.

Contrato próprio do domínio Search -- não compartilhado com AI (ver ADR
0006, revisado nesta mesma TASK-118A). Nenhuma implementação concreta
existe aqui: um adapter real (ex.: falando com o OmniRoute) chega em
``search/providers/omniroute.py`` numa TASK futura.
"""

from typing import Protocol

from cesar_core.search.contracts import SearchRequest, SearchResponse


class SearchProvider(Protocol):
    """Contrato que uma implementação futura de provider de Search deve seguir."""

    async def search(self, request: SearchRequest) -> SearchResponse: ...
