"""Boundary do provider de Web Search consumido pelo César Core.

Contrato próprio do domínio Search -- não compartilhado com AI (ver ADR
0006). Nenhuma implementação concreta existe no estado atual: o adapter que
falará com o transporte OmniRoute deve entrar em
``search/providers/omniroute.py``.
"""

from typing import Protocol

from cesar_core.search.contracts import SearchRequest, SearchResponse


class SearchProvider(Protocol):
    """Contrato que uma implementação de provider de Search deve seguir."""

    async def search(self, request: SearchRequest) -> SearchResponse: ...
