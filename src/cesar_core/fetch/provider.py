"""Boundary do provider de Fetch/Enrichment consumido pelo César Core.

Contrato próprio do domínio Fetch -- não compartilhado com AI/Search (ver
ADR 0006). A implementação OmniRoute vive em
``fetch/providers/omniroute.py``.
"""

from typing import Protocol

from cesar_core.fetch.contracts import FetchRequest, FetchResponse
from cesar_core.fetch.policy import FetchProviderTarget


class FetchProvider(Protocol):
    """Contrato que uma implementação de provider de Fetch deve seguir."""

    async def fetch(
        self, request: FetchRequest, *, target: FetchProviderTarget
    ) -> FetchResponse: ...
