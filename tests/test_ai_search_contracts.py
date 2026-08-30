from cesar_core.ai.contracts import AIRequest, AIResponse
from cesar_core.applications.identity import ApplicationId
from cesar_core.policy.cost_policy import CostPolicy
from cesar_core.policy.purpose import Purpose
from cesar_core.policy.requirements import Requirements
from cesar_core.policy.service_class import ServiceClass
from cesar_core.policy.service_kind import ServiceKind
from cesar_core.search.contracts import SearchRequest, SearchResponse, SearchResult


def _requirements(service: ServiceKind) -> Requirements:
    return Requirements(
        service=service,
        service_class=ServiceClass.ECONOMY,
        cost_policy=CostPolicy.FREE_ONLY,
        purpose=Purpose(value="teste"),
    )


def test_ai_request_and_response_are_neutral_shapes() -> None:
    request = AIRequest(
        application_id=ApplicationId.GG_OFERTA,
        correlation_id="corr-1",
        requirements=_requirements(ServiceKind.AI),
        prompt="qual o menor preço?",
    )
    response = AIResponse(correlation_id="corr-1", content="resposta")
    assert request.application_id is ApplicationId.GG_OFERTA
    assert response.content == "resposta"


def test_search_request_and_response_are_neutral_shapes() -> None:
    request = SearchRequest(
        application_id=ApplicationId.GG_OFERTA,
        correlation_id="corr-2",
        requirements=_requirements(ServiceKind.SEARCH),
        query="placa de vídeo RTX",
    )
    response = SearchResponse(
        correlation_id="corr-2",
        results=[SearchResult(title="Oferta X", url="https://example.test/x")],
    )
    assert request.query == "placa de vídeo RTX"
    assert response.results[0].title == "Oferta X"


def test_search_response_defaults_to_no_results() -> None:
    response = SearchResponse(correlation_id="corr-3")
    assert response.results == []
