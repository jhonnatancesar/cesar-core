from cesar_core.ai.contracts import AIRequest, AIRequestPayload, AIResponse
from cesar_core.applications.context import ApplicationContext
from cesar_core.applications.identity import ApplicationId
from cesar_core.policy.cost_policy import CostPolicy
from cesar_core.policy.purpose import Purpose
from cesar_core.policy.requirements import Requirements
from cesar_core.policy.service_class import ServiceClass
from cesar_core.search.contracts import (
    SearchRequest,
    SearchRequestPayload,
    SearchResponse,
    SearchResult,
)


def _context() -> ApplicationContext:
    return ApplicationContext(
        application_id=ApplicationId.GG_OFERTA,
        service="collection_worker",
        purpose=Purpose(value="market_research"),
        request_id="req-1",
        correlation_id="corr-1",
    )


def _requirements() -> Requirements:
    return Requirements(
        service_class=ServiceClass.ECONOMY, cost_policy=CostPolicy.FREE_ONLY
    )


def test_ai_request_payload_has_no_identity_fields() -> None:
    assert "context" not in AIRequestPayload.model_fields
    assert "application_id" not in AIRequestPayload.model_fields


def test_search_request_payload_has_no_identity_fields() -> None:
    assert "context" not in SearchRequestPayload.model_fields
    assert "application_id" not in SearchRequestPayload.model_fields


def test_ai_request_extends_payload_with_trusted_context() -> None:
    payload = AIRequestPayload(
        requirements=_requirements(), prompt="qual o menor preço?"
    )
    request = AIRequest(context=_context(), **payload.model_dump())
    response = AIResponse(
        request_id="req-1",
        correlation_id="corr-1",
        content="resposta",
        provider_gateway="omniroute",
        model="model-a",
        latency_ms=1.5,
    )

    assert request.context.application_id is ApplicationId.GG_OFERTA
    assert request.context.service == "collection_worker"
    assert request.context.purpose.value == "market_research"
    assert request.prompt == "qual o menor preço?"
    assert response.content == "resposta"
    assert response.usage is None


def test_search_request_extends_payload_with_trusted_context() -> None:
    payload = SearchRequestPayload(
        requirements=_requirements(), query="placa de vídeo RTX"
    )
    request = SearchRequest(context=_context(), **payload.model_dump())
    response = SearchResponse(
        correlation_id="corr-2",
        results=[SearchResult(title="Oferta X", url="https://example.test/x")],
    )

    assert request.query == "placa de vídeo RTX"
    assert request.context.request_id == "req-1"
    assert response.results[0].title == "Oferta X"


def test_search_response_defaults_to_no_results() -> None:
    response = SearchResponse(correlation_id="corr-3")
    assert response.results == []
