from cesar_core.ai.contracts import AIRequest, AIResponse
from cesar_core.applications.context import ApplicationContext
from cesar_core.applications.identity import ApplicationId
from cesar_core.policy.cost_policy import CostPolicy
from cesar_core.policy.purpose import Purpose
from cesar_core.policy.requirements import Requirements
from cesar_core.policy.service_class import ServiceClass
from cesar_core.policy.service_kind import ServiceKind
from cesar_core.search.contracts import SearchRequest, SearchResponse, SearchResult


def _context() -> ApplicationContext:
    return ApplicationContext(
        application_id=ApplicationId.GG_OFERTA,
        service="collection_worker",
        purpose=Purpose(value="market_research"),
        request_id="req-1",
        correlation_id="corr-1",
    )


def _requirements(service: ServiceKind) -> Requirements:
    return Requirements(
        service=service,
        service_class=ServiceClass.ECONOMY,
        cost_policy=CostPolicy.FREE_ONLY,
    )


def test_ai_request_carries_full_application_context() -> None:
    request = AIRequest(
        context=_context(),
        requirements=_requirements(ServiceKind.AI),
        prompt="qual o menor preço?",
    )
    response = AIResponse(correlation_id="corr-1", content="resposta")
    assert request.context.application_id is ApplicationId.GG_OFERTA
    assert request.context.service == "collection_worker"
    assert request.context.purpose.value == "market_research"
    assert response.content == "resposta"


def test_search_request_carries_full_application_context() -> None:
    request = SearchRequest(
        context=_context(),
        requirements=_requirements(ServiceKind.SEARCH),
        query="placa de vídeo RTX",
    )
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
