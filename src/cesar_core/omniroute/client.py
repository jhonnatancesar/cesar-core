"""Client HTTP de baixo nível do César Core para o OmniRoute.

Escopo estrito da TASK-118B: transporte (config, autenticação, timeout,
serialização/desserialização, correlation, normalização de erros). Não
sabe nada de AI/Search/regras de negócio -- adapters de domínio
(``ai/providers/omniroute.py``, ``search/providers/omniroute.py`` em
118C/118D) usam este client, nunca o inverso (ver ADR 0006/0011).
"""

from typing import Any

import httpx

from cesar_core.omniroute.auth import bearer_header
from cesar_core.omniroute.config import OmniRouteConfig
from cesar_core.omniroute.errors import (
    OmniRouteAuthError,
    OmniRouteClientError,
    OmniRouteConnectionError,
    OmniRouteServerError,
    OmniRouteTimeoutError,
)
from cesar_core.omniroute.models import OmniRouteHealth, OmniRouteResponse

REQUEST_ID_HEADER = "x-request-id"


class OmniRouteClient:
    """Client HTTP de baixo nível para o OmniRoute (sem regras de negócio)."""

    def __init__(
        self, config: OmniRouteConfig, transport: httpx.AsyncBaseTransport | None = None
    ) -> None:
        self._config = config
        self._http = httpx.AsyncClient(
            base_url=config.base_url,
            timeout=config.timeout_seconds,
            transport=transport,
        )

    async def aclose(self) -> None:
        await self._http.aclose()

    async def __aenter__(self) -> "OmniRouteClient":
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        await self.aclose()

    async def health(self) -> OmniRouteHealth:
        """``GET /api/health`` -- sem autenticação, sem depender de provider pago."""
        try:
            response = await self._http.get("/api/health")
        except httpx.TimeoutException as exc:
            raise OmniRouteTimeoutError("OmniRoute health check timed out") from exc
        except httpx.ConnectError as exc:
            raise OmniRouteConnectionError("OmniRoute unreachable") from exc
        self._raise_for_status(response)
        return OmniRouteHealth.model_validate(response.json())

    async def request(
        self,
        method: str,
        path: str,
        *,
        correlation_id: str,
        json: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
    ) -> OmniRouteResponse:
        """Chamada autenticada de baixo nível a uma rota do OmniRoute.

        Propaga ``correlation_id`` como ``x-request-id`` -- convenção que
        o próprio OmniRoute lê para seu tracing/auditoria interno -- para
        correlação ponta a ponta (GG Oferta -> César Core -> OmniRoute).
        """
        headers = {
            **bearer_header(self._config.read_api_key()),
            REQUEST_ID_HEADER: correlation_id,
        }
        try:
            response = await self._http.request(
                method, path, json=json, params=params, headers=headers
            )
        except httpx.TimeoutException as exc:
            raise OmniRouteTimeoutError(f"OmniRoute request to {path} timed out") from exc
        except httpx.ConnectError as exc:
            raise OmniRouteConnectionError(f"OmniRoute unreachable calling {path}") from exc
        self._raise_for_status(response)
        return OmniRouteResponse(status_code=response.status_code, body=response.json())

    @staticmethod
    def _raise_for_status(response: httpx.Response) -> None:
        if response.status_code in (401, 403):
            raise OmniRouteAuthError(response.status_code, response.text)
        if 400 <= response.status_code < 500:
            raise OmniRouteClientError(response.status_code, response.text)
        if response.status_code >= 500:
            raise OmniRouteServerError(response.status_code, response.text)
