import pytest
from fastapi.testclient import TestClient

from cesar_core.ai.contracts import AIResponse
from cesar_core.api.app import app
from cesar_core.api.deps import QUOTA_LIMITER, get_ai_manager, get_search_manager
from cesar_core.search.contracts import SearchResponse, SearchUsage
from cesar_core.search.errors import (
    SearchCostPolicyDeniedError,
    SearchUpstreamAuthError,
    SearchUpstreamUnavailableError,
)
from cesar_core.telemetry.correlation import CORRELATION_HEADER
from cesar_core.telemetry.metrics import METRICS

client = TestClient(app)
TEST_CREDENTIAL = "gg-oferta-test-credential"


@pytest.fixture(autouse=True)
def configure_application_authentication(monkeypatch, tmp_path) -> None:
    credential_file = tmp_path / "ggoferta-core-client"
    credential_file.write_text(TEST_CREDENTIAL, encoding="utf-8")
    monkeypatch.setenv(
        "CESAR_CORE_SECURITY_GG_OFERTA_API_KEY_FILE", str(credential_file)
    )
    QUOTA_LIMITER.reset()
    METRICS.reset()


def _identity_headers(*, purpose: str, correlation_id: str | None = None) -> dict:
    headers = {
        "Authorization": f"Bearer {TEST_CREDENTIAL}",
        "X-Service": "backend",
        "X-Purpose": purpose,
    }
    if correlation_id is not None:
        headers[CORRELATION_HEADER] = correlation_id
    return headers


def test_health_endpoint_reports_process_alive() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_ready_endpoint_reports_core_available() -> None:
    response = client.get("/ready")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "core": "available"}


def test_capabilities_endpoint_is_honest_about_unconfigured_services() -> None:
    response = client.get("/v1/capabilities")
    assert response.status_code == 200
    assert response.json() == {
        "core": "available",
        "application_registry": "available",
        "application_authentication": "available",
        "metrics": "available",
        "ai": "not_configured",
        "search": "not_configured",
        "search_general_web": "not_configured",
        "search_technical_documentation": "not_configured",
        "fetch": "not_configured",
        "omniroute": "not_configured",
    }


def test_response_carries_correlation_id_header_even_when_not_sent() -> None:
    response = client.get("/health")
    assert response.headers.get(CORRELATION_HEADER)


def test_response_reuses_incoming_correlation_id_header() -> None:
    response = client.get("/health", headers={CORRELATION_HEADER: "fixed-id"})
    assert response.headers.get(CORRELATION_HEADER) == "fixed-id"


class StubAIManager:
    def __init__(self) -> None:
        self.last_request = None

    async def generate(self, request):
        self.last_request = request
        return AIResponse(
            request_id=request.context.request_id,
            correlation_id=request.context.correlation_id,
            content="pong",
            provider_gateway="omniroute",
            model="model-a",
            latency_ms=1,
        )


def test_ai_generate_builds_trusted_context_outside_the_body() -> None:
    manager = StubAIManager()
    app.dependency_overrides[get_ai_manager] = lambda: manager
    try:
        response = client.post(
            "/v1/ai/generate",
            headers=_identity_headers(purpose="chat", correlation_id="corr-fixed"),
            json={
                "ai_profile": "admin_dev",
                "requirements": {
                    "service_class": "standard",
                    "cost_policy": "free_preferred",
                },
                "prompt": "ping",
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["content"] == "pong"
    assert response.json()["correlation_id"] == "corr-fixed"
    assert response.headers[CORRELATION_HEADER] == "corr-fixed"
    assert manager.last_request.context.application_id.value == "gg_oferta"


def test_spoofed_application_header_does_not_change_authenticated_identity() -> None:
    manager = StubAIManager()
    app.dependency_overrides[get_ai_manager] = lambda: manager
    headers = _identity_headers(purpose="chat")
    headers["X-Application-Id"] = "claudiao"
    try:
        response = client.post(
            "/v1/ai/generate",
            headers=headers,
            json={
                "ai_profile": "admin_dev",
                "requirements": {
                    "service_class": "standard",
                    "cost_policy": "free_preferred",
                },
                "prompt": "ping",
            },
        )
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 200
    assert manager.last_request.context.application_id.value == "gg_oferta"


def test_ai_generate_requires_a_bearer_credential() -> None:
    app.dependency_overrides[get_ai_manager] = lambda: StubAIManager()
    try:
        response = client.post(
            "/v1/ai/generate",
            json={
                "ai_profile": "admin_dev",
                "requirements": {
                    "service_class": "standard",
                    "cost_policy": "free_preferred",
                },
                "prompt": "ping",
            },
        )
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "invalid_credential"
    assert response.headers["WWW-Authenticate"] == "Bearer"


def test_invalid_application_credential_is_rejected() -> None:
    response = client.post(
        "/v1/ai/generate",
        headers={
            "Authorization": "Bearer wrong",
            "X-Service": "backend",
            "X-Purpose": "chat",
        },
        json={
            "ai_profile": "admin_dev",
            "requirements": {
                "service_class": "standard",
                "cost_policy": "free_preferred",
            },
            "prompt": "ping",
        },
    )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "invalid_credential"


def test_authentication_not_configured_is_fail_closed(monkeypatch) -> None:
    monkeypatch.delenv("CESAR_CORE_SECURITY_GG_OFERTA_API_KEY_FILE")
    response = client.post(
        "/v1/ai/generate",
        headers=_identity_headers(purpose="chat"),
        json={
            "ai_profile": "admin_dev",
            "requirements": {
                "service_class": "standard",
                "cost_policy": "free_preferred",
            },
            "prompt": "ping",
        },
    )
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "authentication_not_configured"


def test_ai_generate_returns_normalized_error_when_gateway_is_disabled(
    monkeypatch,
) -> None:
    monkeypatch.setenv("CESAR_CORE_AI_ENABLED", "false")
    response = client.post(
        "/v1/ai/generate",
        headers=_identity_headers(purpose="chat", correlation_id="corr-disabled"),
        json={
            "ai_profile": "admin_dev",
            "requirements": {
                "service_class": "standard",
                "cost_policy": "free_preferred",
            },
            "prompt": "ping",
        },
    )
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "ai_not_configured"
    assert response.json()["error"]["correlation_id"] == "corr-disabled"


class StubSearchManager:
    def __init__(self, result=None) -> None:
        self.result = result

    async def search(self, request):
        if isinstance(self.result, Exception):
            raise self.result
        return SearchResponse(
            request_id=request.context.request_id,
            correlation_id=request.context.correlation_id,
            provider_gateway="omniroute",
            provider="duckduckgo-free",
            usage=SearchUsage(queries_used=1, search_cost_usd=0),
            latency_ms=1,
        )


def _search_request(manager) -> object:
    app.dependency_overrides[get_search_manager] = lambda: manager
    try:
        return client.post(
            "/v1/search",
            headers=_identity_headers(
                purpose="market_research", correlation_id="corr-search"
            ),
            json={
                "requirements": {
                    "service_class": "economy",
                    "cost_policy": "free_only",
                },
                "query": "placa de video",
                "max_results": 3,
            },
        )
    finally:
        app.dependency_overrides.clear()


def test_search_builds_context_and_returns_normalized_response() -> None:
    response = _search_request(StubSearchManager())
    assert response.status_code == 200
    assert response.json()["provider"] == "duckduckgo-free"
    assert response.json()["correlation_id"] == "corr-search"
    assert response.headers[CORRELATION_HEADER] == "corr-search"


def test_search_requires_a_bearer_credential() -> None:
    response = client.post(
        "/v1/search",
        json={
            "requirements": {
                "service_class": "economy",
                "cost_policy": "free_only",
            },
            "query": "x",
        },
    )
    assert response.status_code == 401


def test_search_returns_normalized_error_when_disabled(monkeypatch) -> None:
    monkeypatch.setenv("CESAR_CORE_SEARCH_ENABLED", "false")
    result = client.post(
        "/v1/search",
        headers=_identity_headers(
            purpose="market_research", correlation_id="corr-disabled-search"
        ),
        json={
            "requirements": {
                "service_class": "economy",
                "cost_policy": "free_only",
            },
            "query": "x",
        },
    )
    assert result.status_code == 503
    assert result.json()["error"]["code"] == "search_not_configured"


def test_documentation_target_does_not_serve_a_general_search_purpose(
    monkeypatch, tmp_path
) -> None:
    key_file = tmp_path / "omniroute-key"
    key_file.write_text("not-used-before-policy", encoding="utf-8")
    monkeypatch.setenv("CESAR_CORE_SEARCH_ENABLED", "true")
    monkeypatch.delenv("CESAR_CORE_SEARCH_DEFAULT_PROVIDER", raising=False)
    monkeypatch.setenv("CESAR_CORE_SEARCH_TECHNICAL_DOCUMENTATION_PROVIDER", "context7")
    monkeypatch.setenv("CESAR_CORE_OMNIROUTE_SEARCH_API_KEY_FILE", str(key_file))

    response = client.post(
        "/v1/search",
        headers=_identity_headers(purpose="market_research"),
        json={
            "requirements": {
                "service_class": "economy",
                "cost_policy": "free_only",
            },
            "query": "general web search",
        },
    )
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "search_not_configured"


def test_search_maps_policy_upstream_and_unavailable_errors() -> None:
    cases = [
        (SearchCostPolicyDeniedError("denied"), 403, "search_policy_denied"),
        (
            SearchUpstreamAuthError("bad", upstream_request_id="up-1"),
            502,
            "search_upstream_error",
        ),
        (SearchUpstreamUnavailableError("down"), 503, "search_upstream_unavailable"),
    ]
    for error, status, code in cases:
        response = _search_request(StubSearchManager(error))
        assert response.status_code == status
        assert response.json()["error"]["code"] == code


def test_quota_is_enforced_before_the_ai_manager(monkeypatch) -> None:
    monkeypatch.setenv("CESAR_CORE_SECURITY_AI_REQUESTS_PER_MINUTE", "1")
    manager = StubAIManager()
    app.dependency_overrides[get_ai_manager] = lambda: manager
    payload = {
        "ai_profile": "admin_dev",
        "requirements": {
            "service_class": "standard",
            "cost_policy": "free_preferred",
        },
        "prompt": "ping",
    }
    try:
        first = client.post(
            "/v1/ai/generate", headers=_identity_headers(purpose="chat"), json=payload
        )
        second = client.post(
            "/v1/ai/generate", headers=_identity_headers(purpose="chat"), json=payload
        )
    finally:
        app.dependency_overrides.clear()
    assert first.status_code == 200
    assert second.status_code == 429
    assert second.json()["error"]["code"] == "quota_exceeded"
    assert int(second.headers["Retry-After"]) >= 1


def test_metrics_aggregate_authenticated_usage_without_credentials() -> None:
    app.dependency_overrides[get_ai_manager] = lambda: StubAIManager()
    try:
        response = client.post(
            "/v1/ai/generate",
            headers=_identity_headers(purpose="chat"),
            json={
                "ai_profile": "admin_dev",
                "requirements": {
                    "service_class": "standard",
                    "cost_policy": "free_preferred",
                },
                "prompt": "ping",
            },
        )
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 200
    metrics = client.get("/metrics")
    assert metrics.status_code == 200
    assert 'cesar_core_ai_requests_total{application="gg_oferta"} 1' in metrics.text
    assert TEST_CREDENTIAL not in metrics.text


def test_fetch_rejects_an_internal_target_before_reaching_the_manager() -> None:
    """Regressão de segurança (SSRF): a rota `/v1/fetch` real barra um alvo
    interno com 400, sem nunca acionar o `FetchManager`/upstream."""
    response = client.post(
        "/v1/fetch",
        headers=_identity_headers(purpose="market_research"),
        json={
            "requirements": {
                "service_class": "economy",
                "cost_policy": "free_only",
            },
            "url": "http://169.254.169.254/latest/meta-data/",
        },
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "fetch_target_rejected"


def test_fetch_rejects_a_sensitive_query_parameter_before_reaching_the_manager() -> (
    None
):
    """Regressão de segurança (vazamento de dados, FASE E.3): a rota
    `/v1/fetch` real barra uma URL com parâmetro de alta confiança na query
    (aqui, um valor sintético claramente falso) já na validação do corpo da
    requisição -- 422, antes de qualquer autenticação/manager/upstream."""
    response = client.post(
        "/v1/fetch",
        headers=_identity_headers(purpose="market_research"),
        json={
            "requirements": {
                "service_class": "economy",
                "cost_policy": "free_only",
            },
            "url": "https://shop.example.test/product?session_id=FAKE_AUDIT_TOKEN_123",
        },
    )
    assert response.status_code == 422


def test_fetch_rejects_an_unknown_payload_field() -> None:
    """Regressão de segurança (FASE E.3): `FetchRequestPayload` usa
    `extra="forbid"` -- um campo desconhecido no corpo é rejeitado com 422
    antes de qualquer chamada ao manager/upstream."""
    response = client.post(
        "/v1/fetch",
        headers=_identity_headers(purpose="market_research"),
        json={
            "requirements": {
                "service_class": "economy",
                "cost_policy": "free_only",
            },
            "url": "https://shop.example.test/product",
            "provider": "firecrawl",
        },
    )
    assert response.status_code == 422
