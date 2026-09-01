"""Boundary do provider de AI consumido pelo César Core.

Contrato próprio do domínio AI -- não compartilhado com Search (ver ADR
0006). Nenhuma implementação concreta existe no estado atual: o adapter que
falará com o transporte OmniRoute deve entrar em
``ai/providers/omniroute.py``.
"""

from typing import Protocol

from cesar_core.ai.contracts import AIRequest, AIResponse


class AIProvider(Protocol):
    """Contrato que uma implementação de provider de AI deve seguir."""

    async def complete(self, request: AIRequest) -> AIResponse: ...
