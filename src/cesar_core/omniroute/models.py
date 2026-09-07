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
    selected_provider: str | None = None
    """``X-OmniRoute-Provider``: alias real do provider/connection que
    efetivamente atendeu a chamada (``getProviderAlias()`` no OmniRoute),
    inclusive quando o request usou um combo -- não é o mesmo dado que o
    ``model`` pedido pelo Core. Emitido pelo OmniRoute em todo retorno de
    sucesso não-streaming (``domain/omnirouteResponseMeta.ts``,
    ``attachOmniRouteMetaHeaders``); ``None`` quando o OmniRoute não o
    emitiu (nunca inferido a partir do nome do modelo)."""
