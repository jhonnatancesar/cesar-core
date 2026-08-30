"""Boundary do provider de AI consumido pelo César Core.

Contrato próprio do domínio AI -- não compartilhado com Search (ver ADR
0006, revisado nesta mesma TASK-118A). Nenhuma implementação concreta
existe aqui: um adapter real (ex.: falando com o OmniRoute) chega em
``ai/providers/omniroute.py`` numa TASK futura.
"""

from typing import Protocol

from cesar_core.ai.contracts import AIRequest, AIResponse


class AIProvider(Protocol):
    """Contrato que uma implementação futura de provider de AI deve seguir."""

    async def complete(self, request: AIRequest) -> AIResponse: ...
