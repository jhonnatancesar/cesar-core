from fastapi.testclient import TestClient

from cesar_core.ai.contracts import AIResponse
from cesar_core.api.app import app
from cesar_core.api.deps import get_ai_manager
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
