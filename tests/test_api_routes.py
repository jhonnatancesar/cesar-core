from fastapi.testclient import TestClient

from cesar_core.ai.contracts import AIResponse
from cesar_core.api.app import app
from cesar_core.api.deps import get_ai_manager, get_search_manager
from cesar_core.search.contracts import SearchResponse, SearchUsage
from cesar_core.search.errors import (
    SearchCostPolicyDeniedError,
    SearchUpstreamAuthError,
    SearchUpstreamUnavailableError,
)
from cesar_core.telemetry.correlation import CORRELATION_HEADER

client = TestClient(app)


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
        "ai": "not_configured",
        "search": "not_configured",
        "search_general_web": "not_configured",
        "search_technical_documentation": "not_configured",
        "omniroute": "not_configured",
    }


def test_response_carries_correlation_id_header_even_when_not_sent() -> None:
    response = client.get("/health")
    assert response.headers.get(CORRELATION_HEADER)


def test_response_reuses_incoming_correlation_id_header() -> None:
    response = client.get("/health", headers={CORRELATION_HEADER: "fixed-id"})
    assert response.headers.get(CORRELATION_HEADER) == "fixed-id"


class StubAIManager:
    async def generate(self, request):
        return AIResponse(
            request_id=request.context.request_id,
            correlation_id=request.context.correlation_id,
            content="pong",
            provider_gateway="omniroute",
            model="model-a",
            latency_ms=1,
        )


def test_ai_generate_builds_trusted_context_outside_the_body() -> None:
    app.dependency_overrides[get_ai_manager] = lambda: StubAIManager()
    try:
        response = client.post(
            "/v1/ai/generate",
            headers={
                "X-Application-Id": "gg_oferta",
                "X-Service": "backend",
                "X-Purpose": "chat",
                CORRELATION_HEADER: "corr-fixed",
            },
            json={
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


def test_ai_generate_requires_identity_headers() -> None:
    app.dependency_overrides[get_ai_manager] = lambda: StubAIManager()
    try:
        response = client.post(
            "/v1/ai/generate",
            json={
                "requirements": {
                    "service_class": "standard",
                    "cost_policy": "free_preferred",
                },
                "prompt": "ping",
            },
        )
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 422


def test_ai_generate_returns_normalized_error_when_gateway_is_disabled(
    monkeypatch,
) -> None:
    monkeypatch.setenv("CESAR_CORE_AI_ENABLED", "false")
    response = client.post(
        "/v1/ai/generate",
        headers={
            "X-Application-Id": "gg_oferta",
            "X-Service": "backend",
            "X-Purpose": "chat",
            CORRELATION_HEADER: "corr-disabled",
        },
        json={
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
            headers={
                "X-Application-Id": "gg_oferta",
                "X-Service": "backend",
                "X-Purpose": "market_research",
                CORRELATION_HEADER: "corr-search",
            },
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


def test_search_requires_identity_headers() -> None:
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
    assert response.status_code == 422


def test_search_returns_normalized_error_when_disabled(monkeypatch) -> None:
    monkeypatch.setenv("CESAR_CORE_SEARCH_ENABLED", "false")
    result = client.post(
        "/v1/search",
        headers={
            "X-Application-Id": "gg_oferta",
            "X-Service": "backend",
            "X-Purpose": "market_research",
            CORRELATION_HEADER: "corr-disabled-search",
        },
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
    monkeypatch.setenv("CESAR_CORE_OMNIROUTE_API_KEY_FILE", str(key_file))

    response = client.post(
        "/v1/search",
        headers={
            "X-Application-Id": "gg_oferta",
            "X-Service": "backend",
            "X-Purpose": "market_research",
        },
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
