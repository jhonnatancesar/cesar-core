import pytest

from cesar_core.applications.context import ApplicationContext
from cesar_core.applications.identity import ApplicationId
from cesar_core.policy.cost_policy import CostPolicy
from cesar_core.policy.purpose import Purpose
from cesar_core.policy.requirements import Requirements
from cesar_core.policy.service_class import ServiceClass
from cesar_core.search.contracts import SearchRequest, SearchResponse, SearchUsage
from cesar_core.search.errors import SearchUpstreamUnavailableError
from cesar_core.search.manager import SearchManager
from cesar_core.search.policy import SearchPolicy, SearchProviderTarget


class StubProvider:
    def __init__(self, result: SearchResponse | Exception) -> None:
        self.result = result
        self.target = None

    async def search(self, request, *, target):
        self.target = target
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


def _request() -> SearchRequest:
    return SearchRequest(
        context=ApplicationContext(
            application_id=ApplicationId.GG_OFERTA,
            service="worker",
            purpose=Purpose(value="market_research"),
            request_id="req-1",
            correlation_id="corr-1",
        ),
        requirements=Requirements(
            service_class=ServiceClass.STANDARD,
            cost_policy=CostPolicy.FREE_ONLY,
        ),
        query="x",
    )


def _manager(result: SearchResponse | Exception):
    target = SearchProviderTarget("duckduckgo-free")
    policy = SearchPolicy(
        {(ApplicationId.GG_OFERTA, "market_research", ServiceClass.STANDARD): target}
    )
    return SearchManager(StubProvider(result), policy)


def _response() -> SearchResponse:
    return SearchResponse(
        request_id="req-1",
        correlation_id="corr-1",
        provider_gateway="omniroute",
        provider="duckduckgo-free",
        usage=SearchUsage(queries_used=1, search_cost_usd=0),
        latency_ms=0,
    )


async def test_manager_applies_policy_and_records_latency() -> None:
    manager = _manager(_response())
    response = await manager.search(_request())
    assert manager._provider.target.provider == "duckduckgo-free"
    assert response.results == []
    assert response.latency_ms >= 0


async def test_empty_result_is_success_and_does_not_trigger_a_retry() -> None:
    manager = _manager(_response())
    response = await manager.search(_request())
    assert response.results == []
    assert response.fallback_used is False


async def test_manager_propagates_normalized_provider_error() -> None:
    error = SearchUpstreamUnavailableError("down")
    with pytest.raises(SearchUpstreamUnavailableError) as exc_info:
        await _manager(error).search(_request())
    assert exc_info.value is error
