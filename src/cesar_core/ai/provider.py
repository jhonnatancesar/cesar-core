"""Boundary do provider de AI consumido pelo César Core.

Contrato próprio do domínio AI -- não compartilhado com Search (ver ADR
0006). ``ai/providers/omniroute.py`` é a implementação concreta atual, sem
alterar esta interface de domínio.
"""

from typing import Protocol

from cesar_core.ai.contracts import AIRequest, AIResponse
from cesar_core.ai.policy import AIModelTarget


class AIProvider(Protocol):
    """Contrato que uma implementação de provider de AI deve seguir."""

    async def complete(
        self, request: AIRequest, *, target: AIModelTarget
    ) -> AIResponse: ...
