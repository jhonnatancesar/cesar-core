"""Boundary/contrato do OmniRoute — TASK-118A não integra funcionalmente.

Este módulo define apenas a forma (Protocol) de um futuro gateway para o
OmniRoute. Nenhuma implementação concreta existe aqui: nenhuma chamada
HTTP real é feita por este repositório nesta fase. A implementação
concreta chega em uma TASK-118 posterior.
"""

from typing import Protocol

from cesar_core.ai.contracts import AIRequest, AIResponse
from cesar_core.search.contracts import SearchRequest, SearchResponse


class OmniRouteGateway(Protocol):
    """Contrato que uma implementação futura do cliente OmniRoute deve seguir."""

    async def complete(self, request: AIRequest) -> AIResponse: ...

    async def search(self, request: SearchRequest) -> SearchResponse: ...
