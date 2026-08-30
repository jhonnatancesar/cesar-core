"""Modelos de baixo nível de serialização/desserialização do transporte OmniRoute."""

from typing import Any

from pydantic import BaseModel


class OmniRouteHealth(BaseModel):
    """Forma real de ``GET /api/health`` no OmniRoute (sem autenticação)."""

    status: str
    timestamp: str


class OmniRouteResponse(BaseModel):
    """Envelope genérico de uma resposta autenticada do OmniRoute.

    ``body`` fica como ``dict`` neutro: o transporte não conhece o
    formato de negócio de cada rota (isso é responsabilidade dos
    adapters de domínio em 118C/118D).
    """

    status_code: int
    body: dict[str, Any]
