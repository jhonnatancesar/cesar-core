"""Testes de contrato reais contra uma instância do OmniRoute rodando de
verdade -- nenhum mock aqui (ver tests/test_omniroute_client.py para os
testes unitários com transporte mockado).

Autoridade: diegosouzapw/omniroute:3.8.50, digest
sha256:085c57adf499a8aaa9f35ccde95c0df9c11bd9ecd18d6c9edbf3b68b8079ba9d
(ver docs/adr/0012-omniroute-runtime-baseline-3-8-50.md) -- não o
commit 1f4dc830, que está fora do baseline executável.

Pulados automaticamente quando não há uma credencial local configurada,
para que o restante da suíte (ruff/pytest/cobertura) continue verde sem
depender de infraestrutura viva.

Superfícies reais:
  A. health  -- GET /api/health, sem autenticação, sem provider pago.
  B. search  -- POST /v1/search, sem provider especificado; o OmniRoute
     promove "duckduckgo-free" (fallback zero-config, sem credencial)
     automaticamente. Prova auth + request + envelope + parsing reais.
  C. chat    -- POST /v1/chat/completions, sem upstream pago configurado:
     teste controlado com um model inexistente. Prova endpoint correto +
     Bearer auth aceita + request enviado + erro real (400) classificado
     como OmniRouteClientError -- suficiente para a camada de transporte,
     sem precisar de um provider de chat configurado.
  D. adapter -- o mesmo erro real atravessa `OmniRouteAIProvider` e vira
     `AIUpstreamRequestError`, sem vazar a exceção de transporte.
  E. endpoint -- `POST /v1/ai/generate` executa policy exata, manager e
     adapter sobre `auto/best-free`, validando conteúdo e usage reais.
  F. auth AI -- credencial inválida vira `AIUpstreamAuthError` no adapter.
  G. readiness -- AI habilitada verifica health e auth real do chat.
  H. timeout -- timeout de socket real vira `AIUpstreamUnavailableError`.
  I. indisponibilidade -- conexão recusada real recebe a mesma normalização.
  J. max tokens -- caps reais no target certificado; conteúdo inválido é rejeitado.
  K. Search adapter -- captura payload/auth reais e normaliza resultado + usage.
  L. Search endpoint -- rota, policy, manager e adapter contra OmniRoute real.
  M. Search error -- provider inválido vira erro de domínio normalizado.
"""

import json
import socket
from pathlib import Path
from uuid import uuid4

import httpx
import pytest
from fastapi.testclient import TestClient

from cesar_core.ai.contracts import AIRequest
from cesar_core.ai.errors import (
    AIUpstreamAuthError,
    AIUpstreamRequestError,
    AIUpstreamResponseError,
    AIUpstreamUnavailableError,
)
from cesar_core.ai.manager import AIManager
from cesar_core.ai.policy import AIModelTarget, AIPolicy
from cesar_core.ai.providers.omniroute import OmniRouteAIProvider
from cesar_core.api.app import app
from cesar_core.api.deps import get_ai_manager
from cesar_core.applications.context import ApplicationContext
from cesar_core.applications.identity import ApplicationId
from cesar_core.omniroute.client import OmniRouteClient
from cesar_core.omniroute.config import OmniRouteConfig
from cesar_core.omniroute.errors import OmniRouteAuthError, OmniRouteClientError
from cesar_core.policy.cost_policy import CostPolicy
from cesar_core.policy.purpose import Purpose
from cesar_core.policy.requirements import Requirements
from cesar_core.policy.service_class import ServiceClass
from cesar_core.search.contracts import SearchRequest
from cesar_core.search.errors import SearchUpstreamRequestError
from cesar_core.search.policy import SearchProviderTarget
from cesar_core.search.providers.omniroute import OmniRouteSearchProvider

DEFAULT_KEY_FILE = Path(r"C:\cesar-core\.secrets\omniroute_api_key")
CORE_TEST_CREDENTIAL = "gg-oferta-contract-credential"
REAL_FREE_MODEL = "auto/best-free"
REAL_MAX_TOKENS_MODEL = "oc/mimo-v2.5-free"

pytestmark = pytest.mark.contract

if not DEFAULT_KEY_FILE.exists():
    pytest.skip(
        "OmniRoute contract tests need a live instance + .secrets/omniroute_api_key "
        "(see docs/adr/0012-omniroute-runtime-baseline-3-8-50.md)",
        allow_module_level=True,
    )


def _client() -> OmniRouteClient:
    config = OmniRouteConfig(api_key_file=DEFAULT_KEY_FILE)
    return OmniRouteClient(config)


class CapturingTransport(httpx.AsyncBaseTransport):
    """Captura os bytes reais e delega a chamada ao transporte de rede."""

    def __init__(self) -> None:
        self.inner = httpx.AsyncHTTPTransport()
        self.chat_payloads: list[dict] = []
        self.chat_responses: list[dict] = []
        self.search_payloads: list[dict] = []
        self.search_authenticated: list[bool] = []

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        if request.url.path == "/v1/chat/completions":
            self.chat_payloads.append(json.loads(request.content))
        if request.url.path == "/v1/search":
            self.search_payloads.append(json.loads(request.content))
            self.search_authenticated.append(
                request.headers.get("Authorization", "").startswith("Bearer ")
            )
        response = await self.inner.handle_async_request(request)
        if request.url.path == "/v1/chat/completions":
            await response.aread()
            self.chat_responses.append(response.json())
        return response

    async def aclose(self) -> None:
        await self.inner.aclose()


async def test_a_health_against_real_omniroute_without_any_paid_provider() -> None:
    client = _client()
    health = await client.health()
    assert health.status == "ok"
    assert health.timestamp
    await client.aclose()


async def test_b_search_against_real_omniroute_using_the_free_fallback_provider() -> (
    None
):
    """POST /v1/search real, sem provider especificado -- o OmniRoute
    promove duckduckgo-free (zero credencial) automaticamente."""
    client = _client()
    response = await client.search(
        {"query": "OmniRoute cesar core contract test"},
        correlation_id="cesar-core-contract-search",
    )
    assert response.status_code == 200
    assert response.body["provider"] == "duckduckgo-free"
    assert isinstance(response.body["results"], list)
    assert response.upstream_request_id
    await client.aclose()


async def test_search_adapter_normalizes_real_omniroute_response_and_usage() -> None:
    """Prova payload, resultados, max_results e cache reais da 118D."""
    query = f"Python programming language official documentation {uuid4()}"
    transport = CapturingTransport()
    client = OmniRouteClient(
        OmniRouteConfig(api_key_file=DEFAULT_KEY_FILE), transport=transport
    )
    provider = OmniRouteSearchProvider(client)
    request = SearchRequest(
        context=ApplicationContext(
            application_id=ApplicationId.GG_OFERTA,
            service="contract_test",
            purpose=Purpose(value="search_contract_validation"),
            request_id="contract-search-request",
            correlation_id="contract-search-correlation",
        ),
        requirements=Requirements(
            service_class=ServiceClass.ECONOMY,
            cost_policy=CostPolicy.FREE_ONLY,
        ),
        query=query,
        max_results=3,
    )
    try:
        first = await provider.search(
            request, target=SearchProviderTarget("context7", paid=False)
        )
        second = await provider.search(
            request, target=SearchProviderTarget("context7", paid=False)
        )
    finally:
        await client.aclose()

    expected_payload = {
        "query": query,
        "provider": "context7",
        "search_type": "web",
        "max_results": 3,
    }
    assert transport.search_payloads == [expected_payload, expected_payload]
    assert transport.search_authenticated == [True, True]
    assert first.request_id == "contract-search-request"
    assert first.correlation_id == "contract-search-correlation"
    assert first.provider_gateway == "omniroute"
    assert first.provider == "context7"
    assert first.usage.queries_used == 1
    assert first.usage.search_cost_usd == 0
    assert first.cached is False
    assert first.fallback_used is False
    assert first.upstream_request_id
    assert 1 <= len(first.results) <= 3
    result = first.results[0]
    assert result.title
    assert result.url.startswith("https://")
    assert result.snippet
    assert result.position == 1
    assert second.cached is True
    assert second.usage.queries_used == 0
    assert second.usage.search_cost_usd == 0
    assert second.results == first.results


async def test_search_endpoint_runs_real_policy_manager_adapter_and_gateway(
    monkeypatch,
    tmp_path,
) -> None:
    """Prova config -> rota -> policy -> manager -> adapter -> OmniRoute."""
    monkeypatch.setenv("CESAR_CORE_SEARCH_ENABLED", "true")
    monkeypatch.delenv("CESAR_CORE_SEARCH_DEFAULT_PROVIDER", raising=False)
    monkeypatch.setenv("CESAR_CORE_SEARCH_TECHNICAL_DOCUMENTATION_PROVIDER", "context7")
    monkeypatch.setenv("CESAR_CORE_SEARCH_PROVIDER_IS_PAID", "false")
    monkeypatch.setenv("CESAR_CORE_SEARCH_MAX_RESULTS_LIMIT", "3")
    monkeypatch.setenv(
        "CESAR_CORE_OMNIROUTE_SEARCH_API_KEY_FILE", str(DEFAULT_KEY_FILE)
    )
    core_key = tmp_path / "ggoferta-core-client"
    core_key.write_text(CORE_TEST_CREDENTIAL, encoding="utf-8")
    monkeypatch.setenv("CESAR_CORE_SECURITY_GG_OFERTA_API_KEY_FILE", str(core_key))

    response = TestClient(app).post(
        "/v1/search",
        headers={
            "Authorization": f"Bearer {CORE_TEST_CREDENTIAL}",
            "X-Service": "contract_test",
            "X-Purpose": "technical_documentation",
            "X-Correlation-Id": "contract-search-endpoint-correlation",
        },
        json={
            "requirements": {
                "service_class": "economy",
                "cost_policy": "free_only",
            },
            "query": (f"Python programming language official documentation {uuid4()}"),
            "max_results": 3,
        },
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["provider_gateway"] == "omniroute"
    assert body["provider"] == "context7"
    assert body["usage"] == {
        "queries_used": 1,
        "search_cost_usd": 0.0,
        "llm_tokens": None,
    }
    assert body["correlation_id"] == "contract-search-endpoint-correlation"
    assert body["request_id"]
    assert body["upstream_request_id"]
    assert 1 <= len(body["results"]) <= 3
    assert body["results"][0]["title"]
    assert body["results"][0]["url"].startswith("https://")
    assert body["results"][0]["snippet"]
    assert body["results"][0]["position"] == 1


async def test_search_adapter_normalizes_real_provider_request_error() -> None:
    client = _client()
    request = SearchRequest(
        context=ApplicationContext(
            application_id=ApplicationId.GG_OFERTA,
            service="contract_test",
            purpose=Purpose(value="search_error_validation"),
            request_id="contract-search-error-request",
            correlation_id="contract-search-error-correlation",
        ),
        requirements=Requirements(
            service_class=ServiceClass.ECONOMY,
            cost_policy=CostPolicy.FREE_ONLY,
        ),
        query="must not reach an external provider",
        max_results=1,
    )
    try:
        with pytest.raises(SearchUpstreamRequestError) as exc_info:
            await OmniRouteSearchProvider(client).search(
                request,
                target=SearchProviderTarget(
                    "does-not-exist-cesar-core-search-contract"
                ),
            )
        assert exc_info.value.status_code == 400
        assert exc_info.value.upstream_request_id
    finally:
        await client.aclose()


async def test_c_chat_completions_against_real_omniroute_unresolvable_model_is_a_client_error() -> (
    None
):
    """POST /v1/chat/completions real, sem upstream pago configurado: prova
    endpoint + auth + request + erro real classificado -- suficiente pra
    camada de transporte (não exige provider de chat configurado)."""
    client = _client()
    with pytest.raises(OmniRouteClientError) as exc_info:
        await client.chat_completions(
            {
                "model": "does-not-exist-cesar-core-contract-test",
                "messages": [{"role": "user", "content": "ping"}],
            },
            correlation_id="cesar-core-contract-chat",
        )
    assert exc_info.value.status_code == 400
    await client.aclose()


async def test_authenticated_request_against_real_omniroute() -> None:
    client = _client()
    response = await client.request(
        "GET", "/v1/models", correlation_id="cesar-core-contract-test"
    )
    assert response.status_code == 200
    assert isinstance(response.body, dict)
    await client.aclose()


async def test_invalid_credential_is_a_distinct_auth_error() -> None:
    bad_key_file = DEFAULT_KEY_FILE.parent / "omniroute_api_key_invalid_for_test"
    bad_key_file.write_text("sk-definitely-not-a-real-key", encoding="utf-8")
    try:
        client = OmniRouteClient(OmniRouteConfig(api_key_file=bad_key_file))
        with pytest.raises(OmniRouteAuthError):
            await client.request(
                "GET", "/v1/models", correlation_id="cesar-core-contract-test"
            )
        await client.aclose()
    finally:
        bad_key_file.unlink(missing_ok=True)


async def test_ai_adapter_normalizes_real_omniroute_client_error() -> None:
    """Exercita a fronteira 118C sobre o transporte real da 118B."""
    client = _client()
    provider = OmniRouteAIProvider(client)
    request = AIRequest(
        context=ApplicationContext(
            application_id=ApplicationId.GG_OFERTA,
            service="contract_test",
            purpose=Purpose(value="transport_validation"),
            request_id="contract-ai-request",
            correlation_id="contract-ai-correlation",
        ),
        requirements=Requirements(
            service_class=ServiceClass.ECONOMY,
            cost_policy=CostPolicy.FREE_ONLY,
        ),
        prompt="ping",
    )
    with pytest.raises(AIUpstreamRequestError) as exc_info:
        await provider.complete(
            request,
            target=AIModelTarget("does-not-exist-cesar-core-ai-adapter-test"),
        )
    assert exc_info.value.status_code == 400
    await client.aclose()


async def test_ai_generate_endpoint_normalizes_real_omniroute_completion(
    monkeypatch, tmp_path
) -> None:
    """Prova rota -> contexto -> policy -> manager -> adapter -> OmniRoute."""
    target = AIModelTarget(
        REAL_FREE_MODEL,
        paid=False,
        max_tokens_limit=32,
    )
    policy = AIPolicy(
        {
            (
                ApplicationId.GG_OFERTA,
                "contract_ai_validation",
                ServiceClass.ECONOMY,
            ): target
        }
    )

    async def real_manager():
        async with _client() as omniroute_client:
            yield AIManager(OmniRouteAIProvider(omniroute_client), policy)

    app.dependency_overrides[get_ai_manager] = real_manager
    core_key = tmp_path / "ggoferta-core-client"
    core_key.write_text(CORE_TEST_CREDENTIAL, encoding="utf-8")
    monkeypatch.setenv("CESAR_CORE_SECURITY_GG_OFERTA_API_KEY_FILE", str(core_key))
    monkeypatch.setenv("CESAR_CORE_OMNIROUTE_AI_API_KEY_FILE", str(DEFAULT_KEY_FILE))
    try:
        response = TestClient(app).post(
            "/v1/ai/generate",
            headers={
                "Authorization": f"Bearer {CORE_TEST_CREDENTIAL}",
                "X-Service": "contract_test",
                "X-Purpose": "contract_ai_validation",
                "X-Correlation-Id": "contract-ai-success-correlation",
            },
            json={
                "requirements": {
                    "service_class": "economy",
                    "cost_policy": "free_only",
                },
                "prompt": "Reply with exactly: CESAR_CORE_118C_OK",
            },
        )
        limit_response = TestClient(app).post(
            "/v1/ai/generate",
            headers={
                "Authorization": f"Bearer {CORE_TEST_CREDENTIAL}",
                "X-Service": "contract_test",
                "X-Purpose": "contract_ai_validation",
                "X-Correlation-Id": "contract-ai-limit-correlation",
            },
            json={
                "requirements": {
                    "service_class": "economy",
                    "cost_policy": "free_only",
                },
                "prompt": "this request must be rejected before the upstream",
                "max_tokens": 33,
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200, response.text
    body = response.json()
    assert "CESAR_CORE_118C_OK" in body["content"]
    assert body["provider_gateway"] == "omniroute"
    assert body["model"]
    assert body["request_id"]
    assert body["correlation_id"] == "contract-ai-success-correlation"
    assert body["upstream_request_id"]
    assert body["usage"]["prompt_tokens"] > 0
    assert body["usage"]["completion_tokens"] > 0
    assert body["usage"]["total_tokens"] >= body["usage"]["completion_tokens"]
    assert limit_response.status_code == 403
    assert limit_response.json()["error"]["code"] == "ai_policy_denied"


async def test_ai_adapter_real_small_cap_and_response_validation() -> None:
    """Caps pequenos certificam limite, não conclusão textual probabilística."""
    for cap in (8, 128):
        await _assert_real_cap_and_response_validation(cap)


async def _assert_real_cap_and_response_validation(cap: int) -> None:
    """Cap certificado, sem presumir que um alias dinâmico viola o limite.

    Reasoning pode esgotar o cap sem conteúdo textual: isso não vira sucesso.
    Violação deliberada de usage é coberta nos testes unitários do adapter,
    não fabricada nem pressuposta neste transporte real.
    """
    transport = CapturingTransport()
    client = OmniRouteClient(
        OmniRouteConfig(
            api_key_file=DEFAULT_KEY_FILE,
            timeout_seconds=90,
        ),
        transport=transport,
    )
    provider = OmniRouteAIProvider(client)
    request = AIRequest(
        context=ApplicationContext(
            application_id=ApplicationId.GG_OFERTA,
            service="contract_test",
            purpose=Purpose(value="max_tokens_validation"),
            request_id="contract-ai-max-tokens-request",
            correlation_id="contract-ai-max-tokens-correlation",
        ),
        requirements=Requirements(
            service_class=ServiceClass.ECONOMY,
            cost_policy=CostPolicy.FREE_ONLY,
        ),
        prompt="Reply with exactly: CESAR_CORE_MAX_TOKENS_PROBE",
        max_tokens=cap,
    )
    response = None
    error = None
    try:
        try:
            response = await provider.complete(
                request,
                target=AIModelTarget(
                    REAL_MAX_TOKENS_MODEL, paid=False, enforces_max_tokens=True
                ),
            )
        except AIUpstreamResponseError as exc:
            error = exc
    finally:
        await client.aclose()

    assert transport.chat_payloads == [
        {
            "model": REAL_MAX_TOKENS_MODEL,
            "messages": [{"role": "user", "content": request.prompt}],
            "max_tokens": cap,
        }
    ]
    assert len(transport.chat_responses) == 1
    raw = transport.chat_responses[0]
    assert raw["model"] == "mimo-v2.5-free"
    assert 0 < raw["usage"]["completion_tokens"] <= cap
    content = raw["choices"][0]["message"]["content"]
    if isinstance(content, str):
        assert error is None
        assert response is not None
        assert response.content == content
        assert response.usage.completion_tokens == raw["usage"]["completion_tokens"]
    else:
        assert response is None
        assert error is not None
        assert "non-text chat content" in str(error)
        assert error.upstream_request_id
    print(
        json.dumps(
            {
                "payload": transport.chat_payloads[0],
                "model": raw["model"],
                "usage": raw["usage"],
                "finish_reason": raw["choices"][0]["finish_reason"],
                "text_content": isinstance(content, str),
                "adapter_rejected": error is not None,
            }
        )
    )


async def test_ai_real_text_completion_with_comfortable_cap(
    monkeypatch, tmp_path
) -> None:
    """Positivo textual separado: 512 dá margem sobre o cap 128 esgotado.

    Mantém limite explícito e baixo, sem retries ou alteração do target.
    """
    transport = CapturingTransport()
    client = OmniRouteClient(
        OmniRouteConfig(api_key_file=DEFAULT_KEY_FILE, timeout_seconds=90),
        transport=transport,
    )
    target = AIModelTarget(
        REAL_MAX_TOKENS_MODEL,
        paid=False,
        enforces_max_tokens=True,
        max_tokens_limit=512,
    )
    policy = AIPolicy(
        {(ApplicationId.GG_OFERTA, "max_tokens_text", ServiceClass.ECONOMY): target}
    )

    async def real_manager():
        async with client:
            yield AIManager(OmniRouteAIProvider(client), policy)

    core_key = tmp_path / "ggoferta-core-client"
    core_key.write_text(CORE_TEST_CREDENTIAL, encoding="utf-8")
    monkeypatch.setenv("CESAR_CORE_SECURITY_GG_OFERTA_API_KEY_FILE", str(core_key))
    monkeypatch.setenv("CESAR_CORE_OMNIROUTE_AI_API_KEY_FILE", str(DEFAULT_KEY_FILE))
    app.dependency_overrides[get_ai_manager] = real_manager
    try:
        response = TestClient(app).post(
            "/v1/ai/generate",
            headers={
                "Authorization": f"Bearer {CORE_TEST_CREDENTIAL}",
                "X-Service": "contract_test",
                "X-Purpose": "max_tokens_text",
                "X-Correlation-Id": "contract-ai-text-correlation",
            },
            json={
                "requirements": {
                    "service_class": "economy",
                    "cost_policy": "free_only",
                },
                "prompt": "Reply with exactly: CAPPED",
                "max_tokens": 512,
            },
        )
    finally:
        app.dependency_overrides.pop(get_ai_manager, None)
        for raw in transport.chat_responses:
            print(
                json.dumps(
                    {
                        "payload": transport.chat_payloads[0],
                        "model": raw.get("model"),
                        "usage": raw.get("usage"),
                        "finish_reason": raw["choices"][0].get("finish_reason"),
                        "text_content": isinstance(
                            raw["choices"][0]["message"].get("content"), str
                        ),
                    }
                )
            )

    assert transport.chat_payloads == [
        {
            "model": REAL_MAX_TOKENS_MODEL,
            "messages": [{"role": "user", "content": "Reply with exactly: CAPPED"}],
            "max_tokens": 512,
        }
    ]
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["model"] == "mimo-v2.5-free"
    assert isinstance(body["content"], str) and body["content"].strip()
    assert (
        body["content"]
        == transport.chat_responses[0]["choices"][0]["message"]["content"]
    )
    assert body["provider_gateway"] == "omniroute"
    assert body["request_id"] and body["upstream_request_id"]
    assert body["correlation_id"] == "contract-ai-text-correlation"
    assert body["usage"]["prompt_tokens"] > 0
    assert 0 < body["usage"]["completion_tokens"] <= 512
    assert (
        body["usage"]["completion_tokens"]
        == transport.chat_responses[0]["usage"]["completion_tokens"]
    )
    assert body["usage"]["total_tokens"] >= body["usage"]["completion_tokens"]
    print(
        json.dumps(
            {
                "payload": transport.chat_payloads[0],
                "model": body["model"],
                "content": body["content"],
                "completion_tokens": body["usage"]["completion_tokens"],
            }
        )
    )


async def test_ai_adapter_normalizes_real_authentication_error() -> None:
    bad_key_file = (
        DEFAULT_KEY_FILE.parent / "omniroute_api_key_invalid_for_ai_adapter_test"
    )
    bad_key_file.write_text("sk-definitely-not-a-real-ai-key", encoding="utf-8")
    try:
        client = OmniRouteClient(OmniRouteConfig(api_key_file=bad_key_file))
        provider = OmniRouteAIProvider(client)
        request = AIRequest(
            context=ApplicationContext(
                application_id=ApplicationId.GG_OFERTA,
                service="contract_test",
                purpose=Purpose(value="auth_validation"),
                request_id="contract-ai-auth-request",
                correlation_id="contract-ai-auth-correlation",
            ),
            requirements=Requirements(
                service_class=ServiceClass.ECONOMY,
                cost_policy=CostPolicy.FREE_ONLY,
            ),
            prompt="ping",
        )
        with pytest.raises(AIUpstreamAuthError) as exc_info:
            await provider.complete(request, target=AIModelTarget(REAL_FREE_MODEL))
        assert exc_info.value.status_code == 401
        await client.aclose()
    finally:
        bad_key_file.unlink(missing_ok=True)


def test_readiness_and_capabilities_with_real_enabled_ai(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("CESAR_CORE_AI_ENABLED", "true")
    monkeypatch.setenv("CESAR_CORE_AI_DEFAULT_MODEL", REAL_FREE_MODEL)
    monkeypatch.setenv("CESAR_CORE_OMNIROUTE_AI_API_KEY_FILE", str(DEFAULT_KEY_FILE))
    core_key = tmp_path / "ggoferta-core-client"
    core_key.write_text(CORE_TEST_CREDENTIAL, encoding="utf-8")
    monkeypatch.setenv("CESAR_CORE_SECURITY_GG_OFERTA_API_KEY_FILE", str(core_key))

    client = TestClient(app)
    readiness = client.get("/ready")
    capabilities = client.get("/v1/capabilities")
    assert readiness.status_code == 200
    assert readiness.json() == {"status": "ok", "core": "available"}
    assert capabilities.status_code == 200
    assert capabilities.json()["ai"] == "available"
    assert capabilities.json()["omniroute"] == "available"
    assert capabilities.json()["search"] == "not_configured"


async def test_ai_adapter_normalizes_real_timeout() -> None:
    client = OmniRouteClient(
        OmniRouteConfig(api_key_file=DEFAULT_KEY_FILE, timeout_seconds=0.001)
    )
    provider = OmniRouteAIProvider(client)
    request = AIRequest(
        context=ApplicationContext(
            application_id=ApplicationId.GG_OFERTA,
            service="contract_test",
            purpose=Purpose(value="timeout_validation"),
            request_id="contract-ai-timeout-request",
            correlation_id="contract-ai-timeout-correlation",
        ),
        requirements=Requirements(
            service_class=ServiceClass.ECONOMY,
            cost_policy=CostPolicy.FREE_ONLY,
        ),
        prompt="Reply with exactly: TIMEOUT_SHOULD_WIN",
    )
    try:
        with pytest.raises(AIUpstreamUnavailableError):
            await provider.complete(request, target=AIModelTarget(REAL_FREE_MODEL))
    finally:
        await client.aclose()


async def test_ai_adapter_normalizes_real_connection_refusal() -> None:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        unused_port = probe.getsockname()[1]

    client = OmniRouteClient(
        OmniRouteConfig(
            base_url=f"http://127.0.0.1:{unused_port}",
            api_key_file=DEFAULT_KEY_FILE,
            timeout_seconds=0.2,
        )
    )
    provider = OmniRouteAIProvider(client)
    request = AIRequest(
        context=ApplicationContext(
            application_id=ApplicationId.GG_OFERTA,
            service="contract_test",
            purpose=Purpose(value="unavailable_validation"),
            request_id="contract-ai-unavailable-request",
            correlation_id="contract-ai-unavailable-correlation",
        ),
        requirements=Requirements(
            service_class=ServiceClass.ECONOMY,
            cost_policy=CostPolicy.FREE_ONLY,
        ),
        prompt="ping",
    )
    try:
        with pytest.raises(AIUpstreamUnavailableError):
            await provider.complete(request, target=AIModelTarget(REAL_FREE_MODEL))
    finally:
        await client.aclose()
