"""Client HTTP de baixo nível do César Core para o OmniRoute.

Escopo estrito da TASK-118B: transporte para health, chat completions e
search (config, autenticação, timeout, serialização/desserialização,
correlation, normalização de erros). Não sabe nada de policy de
aplicação, service_class, cost policy, GG Oferta, Market Research ou
qual modelo/provider o negócio escolheu -- isso é responsabilidade dos
adapters de domínio (``ai/providers/omniroute.py``,
``search/providers/omniroute.py`` em 118C/118D), que usam este client,
nunca o inverso (ver ADR 0006/0011).

Correlation (ver ADR 0013): ``correlation_id`` do César Core é enviado
como ``x-request-id`` -- uma ADAPTAÇÃO ao contrato do OmniRoute 3.8.50
(que lê esse header para seu próprio tracing/auditoria interno), não
uma equivalência semântica. O OmniRoute 3.8.50 NÃO ecoa esse valor de
volta: cada resposta carrega o SEU PRÓPRIO ``x-request-id``, diferente
do que foi enviado. Esse valor upstream é capturado separadamente em
``OmniRouteResponse.upstream_request_id`` -- nunca substitui
``correlation_id``/``request_id`` do ``ApplicationContext``.
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

CHAT_COMPLETIONS_PATH = "/v1/chat/completions"
SEARCH_PATH = "/v1/search"
AUTH_PROBE_MODEL = "does-not-exist-cesar-core-auth-enforcement-probe"
AUTH_PROBE_SEARCH_PROVIDER = "does-not-exist-cesar-core-auth-enforcement-probe"
AUTH_PROBE_TOKEN = "sk-cesar-core-intentionally-invalid-auth-probe"


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

    async def chat_completions(
        self, payload: dict[str, Any], *, correlation_id: str
    ) -> OmniRouteResponse:
        """``POST /v1/chat/completions`` de baixo nível.

        ``payload`` é o corpo no formato nativo do OmniRoute (ex.:
        ``{"model": ..., "messages": [...]}"``) -- montado pelo adapter
        de domínio (118C), não por este client. Este método só conhece
        endpoint/auth/timeout/serialização/erro, nunca qual modelo ou
        provider o negócio escolheu.
        """
        return await self.request(
            "POST", CHAT_COMPLETIONS_PATH, correlation_id=correlation_id, json=payload
        )

    async def chat_authentication_enforced(self) -> bool:
        """Prova que o endpoint de chat rejeita uma credencial inválida.

        O health é público e ``/v1/models`` pode exigir autenticação mesmo
        quando chat ainda permite fallback anônimo. Por isso readiness usa
        uma requisição deliberadamente inválida a um modelo inexistente: um
        runtime seguro responde 401/403 antes de qualquer resolução de
        provider; qualquer outra resposta significa que a fronteira de chat
        não está protegida.
        """
        headers = {
            "Authorization": f"Bearer {AUTH_PROBE_TOKEN}",
            REQUEST_ID_HEADER: "cesar-core-readiness-auth-probe",
        }
        payload = {
            "model": AUTH_PROBE_MODEL,
            "messages": [{"role": "user", "content": "auth probe"}],
        }
        try:
            response = await self._http.post(
                CHAT_COMPLETIONS_PATH,
                json=payload,
                headers=headers,
            )
        except httpx.TimeoutException as exc:
            raise OmniRouteTimeoutError("OmniRoute auth probe timed out") from exc
        except httpx.ConnectError as exc:
            raise OmniRouteConnectionError(
                "OmniRoute unreachable during auth probe"
            ) from exc
        if response.status_code in (401, 403):
            return True
        if response.status_code >= 500:
            self._raise_for_status(response)
        return False

    async def chat_credential_accepted(self) -> bool:
        """Valida a credencial AI sem executar um modelo real."""
        payload = {
            "model": AUTH_PROBE_MODEL,
            "messages": [{"role": "user", "content": "credential probe"}],
        }
        return await self._credential_reaches_target_validation(
            CHAT_COMPLETIONS_PATH,
            payload,
            request_id="cesar-core-readiness-ai-credential-probe",
        )

    async def search(
        self, payload: dict[str, Any], *, correlation_id: str
    ) -> OmniRouteResponse:
        """``POST /v1/search`` de baixo nível.

        ``payload`` é o corpo no formato nativo do OmniRoute (ex.:
        ``{"query": ...}"``, opcionalmente ``provider``) -- montado pelo
        adapter de domínio (118D), não por este client.
        """
        return await self.request(
            "POST", SEARCH_PATH, correlation_id=correlation_id, json=payload
        )

    async def search_authentication_enforced(self) -> bool:
        """Prova que a rota Search rejeita uma credencial inválida.

        O provider deliberadamente inexistente impede uma busca externa caso
        autenticação esteja desabilitada: nesse cenário inseguro o OmniRoute
        devolve 400 após o auth gate, em vez de consumir um provider real.
        """
        headers = {
            "Authorization": f"Bearer {AUTH_PROBE_TOKEN}",
            REQUEST_ID_HEADER: "cesar-core-readiness-search-auth-probe",
        }
        payload = {
            "query": "auth probe",
            "provider": AUTH_PROBE_SEARCH_PROVIDER,
            "max_results": 1,
        }
        try:
            response = await self._http.post(
                SEARCH_PATH,
                json=payload,
                headers=headers,
            )
        except httpx.TimeoutException as exc:
            raise OmniRouteTimeoutError(
                "OmniRoute search auth probe timed out"
            ) from exc
        except httpx.ConnectError as exc:
            raise OmniRouteConnectionError(
                "OmniRoute unreachable during search auth probe"
            ) from exc
        if response.status_code in (401, 403):
            return True
        if response.status_code >= 500:
            self._raise_for_status(response)
        return False

    async def search_credential_accepted(self) -> bool:
        """Valida a credencial Search sem executar um provider real."""
        payload = {
            "query": "credential probe",
            "provider": AUTH_PROBE_SEARCH_PROVIDER,
            "max_results": 1,
        }
        return await self._credential_reaches_target_validation(
            SEARCH_PATH,
            payload,
            request_id="cesar-core-readiness-search-credential-probe",
        )

    async def _credential_reaches_target_validation(
        self, path: str, payload: dict[str, Any], *, request_id: str
    ) -> bool:
        """400 prova auth aceita e alvo inexistente rejeitado antes de consumo."""
        headers = {
            **bearer_header(self._config.read_api_key()),
            REQUEST_ID_HEADER: request_id,
        }
        try:
            response = await self._http.post(path, json=payload, headers=headers)
        except httpx.TimeoutException as exc:
            raise OmniRouteTimeoutError("OmniRoute credential probe timed out") from exc
        except httpx.ConnectError as exc:
            raise OmniRouteConnectionError(
                "OmniRoute unreachable during credential probe"
            ) from exc
        if response.status_code in (401, 403):
            return False
        if response.status_code >= 500:
            self._raise_for_status(response)
        return response.status_code == 400

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

        Envia ``correlation_id`` como ``x-request-id`` (adaptação ao
        contrato do OmniRoute 3.8.50, ver ADR 0013) -- não espera nem
        exige que o OmniRoute o devolva igual; o ``x-request-id`` da
        resposta (se houver) vem em
        ``OmniRouteResponse.upstream_request_id``, capturado à parte.
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
            raise OmniRouteTimeoutError(
                f"OmniRoute request to {path} timed out"
            ) from exc
        except httpx.ConnectError as exc:
            raise OmniRouteConnectionError(
                f"OmniRoute unreachable calling {path}"
            ) from exc
        self._raise_for_status(response)
        return OmniRouteResponse(
            status_code=response.status_code,
            body=response.json(),
            upstream_request_id=response.headers.get(REQUEST_ID_HEADER),
        )

    @staticmethod
    def _raise_for_status(response: httpx.Response) -> None:
        upstream_request_id = response.headers.get(REQUEST_ID_HEADER)
        if response.status_code in (401, 403):
            raise OmniRouteAuthError(
                response.status_code, response.text, upstream_request_id
            )
        if 400 <= response.status_code < 500:
            raise OmniRouteClientError(
                response.status_code, response.text, upstream_request_id
            )
        if response.status_code >= 500:
            raise OmniRouteServerError(
                response.status_code, response.text, upstream_request_id
            )
