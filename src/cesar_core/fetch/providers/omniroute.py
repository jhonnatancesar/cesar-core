"""Adapter do contrato Fetch do César Core para o transporte OmniRoute.

Traduz para o contrato REAL de ``POST /v1/web/fetch`` do OmniRoute (extraído
do código-fonte oficial, não inventado -- ver DEC-107/DEC-109 no repositório
GG Oferta e ``open-sse/handlers/webFetch.ts`` no OmniRoute): ``format``
fixo em ``"markdown"`` e ``depth=0`` porque o único consumidor (enriquecimento
de Market Research do GG Oferta) só precisa de texto da própria página, nunca
HTML/links/screenshot nem navegação em profundidade -- os demais campos do
contrato OmniRoute (``wait_for_selector``) não têm uso de negócio hoje e não
são expostos neste adapter.
"""

from typing import Any

from cesar_core.fetch.config import FetchConfig
from cesar_core.fetch.contracts import FetchRequest, FetchResponse, FetchUsage
from cesar_core.fetch.errors import (
    FetchUpstreamAuthError,
    FetchUpstreamRequestError,
    FetchUpstreamResponseError,
    FetchUpstreamUnavailableError,
)
from cesar_core.fetch.policy import FetchProviderTarget
from cesar_core.omniroute.client import OmniRouteClient
from cesar_core.omniroute.errors import (
    OmniRouteAuthError,
    OmniRouteClientError,
    OmniRouteConnectionError,
    OmniRouteServerError,
    OmniRouteTimeoutError,
)


class OmniRouteFetchProvider:
    """Traduz requests/responses de Fetch sem vazar o payload upstream."""

    def __init__(
        self, client: OmniRouteClient, *, max_content_length: int = 20_000
    ) -> None:
        self._client = client
        self._max_content_length = max_content_length

    async def fetch(
        self, request: FetchRequest, *, target: FetchProviderTarget
    ) -> FetchResponse:
        payload: dict[str, Any] = {
            "url": request.url,
            "provider": target.provider,
            "format": "markdown",
            "depth": 0,
            "include_metadata": True,
        }
        try:
            upstream = await self._client.fetch(
                payload, correlation_id=request.context.correlation_id
            )
        except OmniRouteAuthError as exc:
            raise FetchUpstreamAuthError(
                "Fetch gateway authentication failed",
                status_code=exc.status_code,
                upstream_request_id=exc.upstream_request_id,
            ) from exc
        except OmniRouteClientError as exc:
            raise FetchUpstreamRequestError(
                "Fetch gateway rejected the normalized request",
                status_code=exc.status_code,
                upstream_request_id=exc.upstream_request_id,
            ) from exc
        except (
            OmniRouteConnectionError,
            OmniRouteTimeoutError,
            OmniRouteServerError,
            OSError,
        ) as exc:
            raise FetchUpstreamUnavailableError(
                "Fetch gateway is unavailable",
                status_code=getattr(exc, "status_code", None),
                upstream_request_id=getattr(exc, "upstream_request_id", None),
            ) from exc

        body = upstream.body
        try:
            provider = _required_string(body.get("provider"))
            url = _required_string(body.get("url"))
            content = body.get("content")
            if not isinstance(content, str):
                raise TypeError("content must be a string")
            metadata = body.get("metadata")
            title = None
            if metadata is not None:
                if not isinstance(metadata, dict):
                    raise TypeError("metadata must be an object or null")
                raw_title = metadata.get("title")
                title = (
                    raw_title
                    if isinstance(raw_title, str) and raw_title.strip()
                    else None
                )
        except (KeyError, TypeError, ValueError) as exc:
            raise FetchUpstreamResponseError(
                "OmniRoute returned an invalid web-fetch envelope",
                status_code=upstream.status_code,
                upstream_request_id=upstream.upstream_request_id,
            ) from exc

        # A origem específica pode recusar/bloquear a leitura mesmo com HTTP
        # 200 do provider (paywall, 404 da página, robots) -- o OmniRoute não
        # distingue esse caso de "sem evidência" no envelope, então o Core
        # trata conteúdo vazio como "não obtido", nunca como erro (mesma
        # semântica que o cliente Firecrawl direto do GG Oferta já tinha).
        stripped = content.strip()
        fetched = bool(stripped)
        truncated = False
        if fetched and len(stripped) > self._max_content_length:
            stripped = stripped[: self._max_content_length]
            truncated = True

        return FetchResponse(
            request_id=request.context.request_id,
            correlation_id=request.context.correlation_id,
            provider_gateway="omniroute",
            provider=provider,
            url=url,
            fetched=fetched,
            title=title if fetched else None,
            content=stripped if fetched else None,
            truncated=truncated,
            usage=FetchUsage(),
            latency_ms=0,
            upstream_request_id=upstream.upstream_request_id,
        )


def build_fetch_provider(
    client: OmniRouteClient, config: FetchConfig
) -> OmniRouteFetchProvider:
    return OmniRouteFetchProvider(client, max_content_length=config.max_content_length)


def _required_string(value: object) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError("required string is missing")
    return value
