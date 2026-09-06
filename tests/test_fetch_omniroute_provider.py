import pytest

from cesar_core.applications.context import ApplicationContext
from cesar_core.applications.identity import ApplicationId
from cesar_core.fetch.contracts import FetchRequest
from cesar_core.fetch.errors import (
    FetchUpstreamAuthError,
    FetchUpstreamRequestError,
    FetchUpstreamResponseError,
    FetchUpstreamUnavailableError,
)
from cesar_core.fetch.policy import FetchProviderTarget
from cesar_core.fetch.providers.omniroute import OmniRouteFetchProvider
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


class StubClient:
    def __init__(self, body: dict) -> None:
        self.body = body
        self.payload = None
        self.correlation_id = None

    async def fetch(self, payload: dict, *, correlation_id: str):
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

    async def fetch(self, payload: dict, *, correlation_id: str):
        raise self.error


def _request(url: str = "https://example.test/product") -> FetchRequest:
    return FetchRequest(
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
        url=url,
    )


def _body(**overrides) -> dict:
    body = {
        "provider": "firecrawl",
        "url": "https://example.test/product",
        "content": "# Produto\nPreço R$ 100",
        "links": [],
        "metadata": {"title": "Produto", "description": "desc"},
        "screenshot_url": None,
    }
    body.update(overrides)
    return body


async def test_adapter_translates_the_real_contract_shape() -> None:
    client = StubClient(_body())
    response = await OmniRouteFetchProvider(client).fetch(
        _request(), target=FetchProviderTarget("firecrawl")
    )
    assert client.payload == {
        "url": "https://example.test/product",
        "provider": "firecrawl",
        "format": "markdown",
        "depth": 0,
        "include_metadata": True,
    }
    assert client.correlation_id == "corr-1"
    assert response.request_id == "req-1"
    assert response.fetched is True
    assert response.title == "Produto"
    assert response.content == "# Produto\nPreço R$ 100"
    assert response.upstream_request_id == "upstream-1"


async def test_blank_content_is_normalized_as_no_evidence_not_an_error() -> None:
    """OmniRoute (via Firecrawl) pode devolver `success` HTTP com conteúdo
    vazio quando a origem específica bloqueia/paginação falha -- mesma
    semântica que o cliente Firecrawl direto já tinha (nunca uma exceção)."""
    response = await OmniRouteFetchProvider(StubClient(_body(content="   "))).fetch(
        _request(), target=FetchProviderTarget("firecrawl")
    )
    assert response.fetched is False
    assert response.content is None
    assert response.title is None


async def test_content_longer_than_configured_limit_is_truncated() -> None:
    long_content = "x" * 100
    provider = OmniRouteFetchProvider(
        StubClient(_body(content=long_content)), max_content_length=10
    )
    response = await provider.fetch(_request(), target=FetchProviderTarget("firecrawl"))
    assert response.truncated is True
    assert response.content == "x" * 10


@pytest.mark.parametrize(
    "body",
    [
        {},
        {**_body(), "provider": ""},
        {**_body(), "url": None},
        {**_body(), "content": None},
        {**_body(), "metadata": "not-an-object"},
    ],
)
async def test_adapter_fails_closed_for_invalid_envelopes(body: dict) -> None:
    with pytest.raises(FetchUpstreamResponseError):
        await OmniRouteFetchProvider(StubClient(body)).fetch(
            _request(), target=FetchProviderTarget("firecrawl")
        )


@pytest.mark.parametrize(
    ("transport_error", "domain_error"),
    [
        (OmniRouteAuthError(401, "bad", "up-1"), FetchUpstreamAuthError),
        (OmniRouteClientError(400, "bad", "up-2"), FetchUpstreamRequestError),
        (OmniRouteServerError(500, "bad", "up-3"), FetchUpstreamUnavailableError),
        (OmniRouteConnectionError("down"), FetchUpstreamUnavailableError),
        (OmniRouteTimeoutError("slow"), FetchUpstreamUnavailableError),
        (OSError("missing secret"), FetchUpstreamUnavailableError),
    ],
)
async def test_adapter_normalizes_transport_errors(
    transport_error, domain_error
) -> None:
    with pytest.raises(domain_error):
        await OmniRouteFetchProvider(FailingClient(transport_error)).fetch(
            _request(), target=FetchProviderTarget("firecrawl")
        )
