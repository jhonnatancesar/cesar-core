import pytest

from cesar_core.applications.context import ApplicationContext
from cesar_core.applications.identity import ApplicationId
from cesar_core.fetch.contracts import FetchRequest, FetchResponse, FetchUsage
from cesar_core.fetch.errors import FetchUpstreamUnavailableError
from cesar_core.fetch.manager import FetchManager
from cesar_core.fetch.policy import FetchPolicy, FetchProviderTarget
from cesar_core.policy.cost_policy import CostPolicy
from cesar_core.policy.purpose import Purpose
from cesar_core.policy.requirements import Requirements
from cesar_core.policy.service_class import ServiceClass


class StubProvider:
    def __init__(self, result: FetchResponse | Exception) -> None:
        self.result = result
        self.target = None

    async def fetch(self, request, *, target):
        self.target = target
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


def _request() -> FetchRequest:
    return FetchRequest(
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
        url="https://example.test/product",
    )


def _manager(result: FetchResponse | Exception):
    target = FetchProviderTarget("firecrawl")
    policy = FetchPolicy(
        {(ApplicationId.GG_OFERTA, "market_research", ServiceClass.STANDARD): target}
    )
    return FetchManager(StubProvider(result), policy)


def _response(*, fetched: bool = True) -> FetchResponse:
    return FetchResponse(
        request_id="req-1",
        correlation_id="corr-1",
        provider_gateway="omniroute",
        provider="firecrawl",
        url="https://example.test/product",
        fetched=fetched,
        content="conteudo" if fetched else None,
        usage=FetchUsage(),
        latency_ms=0,
    )


async def test_manager_applies_policy_and_records_latency() -> None:
    manager = _manager(_response())
    response = await manager.fetch(_request())
    assert manager._provider.target.provider == "firecrawl"
    assert response.fetched is True
    assert response.latency_ms >= 0


async def test_no_content_from_source_is_success_not_error() -> None:
    manager = _manager(_response(fetched=False))
    response = await manager.fetch(_request())
    assert response.fetched is False
    assert response.content is None


async def test_manager_propagates_normalized_provider_error() -> None:
    error = FetchUpstreamUnavailableError("down")
    with pytest.raises(FetchUpstreamUnavailableError) as exc_info:
        await _manager(error).fetch(_request())
    assert exc_info.value is error
