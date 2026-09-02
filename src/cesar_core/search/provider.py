"""Boundary do provider de Web Search consumido pelo César Core.

Contrato próprio do domínio Search -- não compartilhado com AI (ver ADR
0006). A implementação OmniRoute vive em ``search/providers/omniroute.py``.
"""

from typing import Protocol

from cesar_core.search.contracts import SearchRequest, SearchResponse
from cesar_core.search.policy import SearchProviderTarget


class SearchProvider(Protocol):
    """Contrato que uma implementação de provider de Search deve seguir."""

    async def search(
        self, request: SearchRequest, *, target: SearchProviderTarget
    ) -> SearchResponse: ...
