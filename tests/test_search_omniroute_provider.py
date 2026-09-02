import pytest

from cesar_core.applications.context import ApplicationContext
from cesar_core.applications.identity import ApplicationId
from cesar_core.omniroute.errors import (
    OmniRouteAuthError,
    OmniRouteClientError,
    OmniRouteConnectionError,
    OmniRouteServerError,
    OmniRouteTimeoutError,
)
from cesar_core.omniroute.models import OmniRouteResponse
from cesar_core.policy.cost_policy import CostPolicy
from cesar_core.policy.purpose import Purpose
from cesar_core.policy.requirements import Requirements
from cesar_core.policy.service_class import ServiceClass
from cesar_core.search.contracts import SearchRequest
from cesar_core.search.errors import (
    SearchUpstreamAuthError,
    SearchUpstreamRequestError,
    SearchUpstreamResponseError,
    SearchUpstreamUnavailableError,
)
from cesar_core.search.policy import SearchProviderTarget
from cesar_core.search.providers.omniroute import OmniRouteSearchProvider


class StubClient:
    def __init__(self, body: dict) -> None:
        self.body = body
        self.payload = None
        self.correlation_id = None

    async def search(self, payload: dict, *, correlation_id: str):
        self.payload = payload
        self.correlation_id = correlation_id
        return OmniRouteResponse(
            status_code=200,
            body=self.body,
            upstream_request_id="upstream-1",
        )


class FailingClient:
    def __init__(self, error: Exception) -> None:
        self.error = error

    async def search(self, payload: dict, *, correlation_id: str):
        raise self.error


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
            service_class=ServiceClass.ECONOMY,
            cost_policy=CostPolicy.FREE_ONLY,
        ),
        query="placa de video",
        max_results=2,
    )


def _body(provider: str = "duckduckgo-free", results=None) -> dict:
    return {
        "provider": provider,
        "query": "placa de video",
        "results": [] if results is None else results,
        "usage": {"queries_used": 1, "search_cost_usd": 0},
        "metrics": {"total_results_available": 9},
        "errors": [],
        "cached": False,
    }


async def test_adapter_translates_and_normalizes_the_real_contract_shape() -> None:
    client = StubClient(
        _body(
            results=[
                {
                    "title": "Oferta",
                    "url": "https://example.test",
                    "snippet": "Preço",
                    "position": 1,
                    "score": 0.8,
                    "published_at": "2026-09-01",
                }
            ]
        )
    )
    response = await OmniRouteSearchProvider(client).search(
        _request(), target=SearchProviderTarget("duckduckgo-free")
    )
    assert client.payload == {
        "query": "placa de video",
        "provider": "duckduckgo-free",
        "search_type": "web",
        "max_results": 2,
    }
    assert client.correlation_id == "corr-1"
    assert response.request_id == "req-1"
    assert response.results[0].snippet == "Preço"
    assert response.usage.queries_used == 1
    assert response.total_results_available == 9
    assert response.upstream_request_id == "upstream-1"


async def test_adapter_accepts_empty_results_without_fallback() -> None:
    response = await OmniRouteSearchProvider(StubClient(_body())).search(
        _request(), target=SearchProviderTarget("duckduckgo-free")
    )
    assert response.results == []
    assert response.fallback_used is False


async def test_adapter_marks_a_provider_change_as_upstream_fallback() -> None:
    response = await OmniRouteSearchProvider(
        StubClient(_body(provider="alternate-free"))
    ).search(_request(), target=SearchProviderTarget("primary-free"))
    assert response.provider == "alternate-free"
    assert response.fallback_used is True


@pytest.mark.parametrize(
    "body",
    [
        {},
        {**_body(), "query": "different"},
        {**_body(), "results": {}},
        {**_body(), "results": [None]},
        {**_body(), "usage": None},
        {**_body(), "usage": {"queries_used": -1, "search_cost_usd": 0}},
        {**_body(), "errors": {}},
    ],
)
async def test_adapter_fails_closed_for_invalid_envelopes(body: dict) -> None:
    with pytest.raises(SearchUpstreamResponseError):
        await OmniRouteSearchProvider(StubClient(body)).search(
            _request(), target=SearchProviderTarget("duckduckgo-free")
        )


@pytest.mark.parametrize(
    ("transport_error", "domain_error"),
    [
        (OmniRouteAuthError(401, "bad", "up-1"), SearchUpstreamAuthError),
        (OmniRouteClientError(400, "bad", "up-2"), SearchUpstreamRequestError),
        (OmniRouteServerError(500, "bad", "up-3"), SearchUpstreamUnavailableError),
        (OmniRouteConnectionError("down"), SearchUpstreamUnavailableError),
        (OmniRouteTimeoutError("slow"), SearchUpstreamUnavailableError),
        (OSError("missing secret"), SearchUpstreamUnavailableError),
    ],
)
async def test_adapter_normalizes_transport_errors(
    transport_error, domain_error
) -> None:
    with pytest.raises(domain_error):
        await OmniRouteSearchProvider(FailingClient(transport_error)).search(
            _request(), target=SearchProviderTarget("duckduckgo-free")
        )
