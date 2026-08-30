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

    ``upstream_request_id`` é o ``x-request-id`` que o próprio OmniRoute
    devolveu na resposta -- NÃO é o mesmo valor enviado (o OmniRoute
    3.8.50 não ecoa o ``x-request-id`` do chamador, gera o seu próprio;
    ver ADR 0013). Guardado separado, nunca sobrescreve
    ``ApplicationContext.correlation_id``/``request_id`` do César Core.
    """

    status_code: int
    body: dict[str, Any]
    upstream_request_id: str | None = None
