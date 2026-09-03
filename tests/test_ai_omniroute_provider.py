import pytest

from cesar_core.ai.contracts import AIRequest
from cesar_core.ai.errors import (
    AIUpstreamAuthError,
    AIUpstreamRequestError,
    AIUpstreamResponseError,
    AIUpstreamUnavailableError,
)
from cesar_core.ai.policy import AIModelTarget
from cesar_core.ai.providers.omniroute import OmniRouteAIProvider
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


class StubClient:
    def __init__(self, body: dict) -> None:
        self.body = body
        self.payload: dict | None = None
        self.correlation_id: str | None = None

    async def chat_completions(
        self, payload: dict, *, correlation_id: str
    ) -> OmniRouteResponse:
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

    async def chat_completions(
        self, payload: dict, *, correlation_id: str
    ) -> OmniRouteResponse:
        raise self.error


def _request() -> AIRequest:
    return AIRequest(
        context=ApplicationContext(
            application_id=ApplicationId.GG_OFERTA,
            service="worker",
            purpose=Purpose(value="normalize_offer_title"),
            request_id="req-1",
            correlation_id="corr-1",
        ),
        requirements=Requirements(
            service_class=ServiceClass.ECONOMY,
            cost_policy=CostPolicy.FREE_ONLY,
        ),
        messages=({"role": "user", "content": "normalize"},),
        max_tokens=50,
    )


async def test_omniroute_ai_provider_translates_request_and_response() -> None:
    client = StubClient(
        {
            "model": "resolved-model",
            "provider": "provider-a",
            "choices": [{"message": {"content": "normalized"}}],
            "usage": {"prompt_tokens": 3, "completion_tokens": 2, "total_tokens": 5},
            "fallback_used": True,
        }
    )
    provider = OmniRouteAIProvider(client)  # type: ignore[arg-type]
    response = await provider.complete(
        _request(), target=AIModelTarget("model-a", provider="preferred-provider")
    )

    assert client.payload == {
        "model": "model-a",
        "provider": "preferred-provider",
        "messages": [{"role": "user", "content": "normalize"}],
        "max_tokens": 50,
    }
    assert client.correlation_id == "corr-1"
    assert response.request_id == "req-1"
    assert response.content == "normalized"
    assert response.model == "resolved-model"
    assert response.provider == "provider-a"
    assert response.usage is not None and response.usage.total_tokens == 5
    assert response.fallback_used is True
    assert response.upstream_request_id == "upstream-1"


async def test_omniroute_ai_provider_rejects_invalid_envelope() -> None:
    provider = OmniRouteAIProvider(StubClient({"choices": []}))  # type: ignore[arg-type]
    with pytest.raises(AIUpstreamResponseError):
        await provider.complete(_request(), target=AIModelTarget("model-a"))


async def test_omniroute_ai_provider_rejects_non_text_content() -> None:
    body = {"choices": [{"message": {"content": {"not": "text"}}}]}
    provider = OmniRouteAIProvider(StubClient(body))  # type: ignore[arg-type]
    with pytest.raises(AIUpstreamResponseError):
        await provider.complete(_request(), target=AIModelTarget("model-a"))


@pytest.mark.parametrize(
    "usage",
    [
        None,
        {"prompt_tokens": 3, "completion_tokens": None, "total_tokens": 3},
        {"prompt_tokens": 3, "completion_tokens": 51, "total_tokens": 54},
    ],
)
async def test_omniroute_ai_provider_fails_closed_when_max_tokens_is_not_proven(
    usage: dict | None,
) -> None:
    body = {
        "choices": [{"message": {"content": "too much or unverifiable"}}],
        "usage": usage,
    }
    provider = OmniRouteAIProvider(StubClient(body))  # type: ignore[arg-type]
    with pytest.raises(AIUpstreamResponseError):
        await provider.complete(_request(), target=AIModelTarget("model-a"))


@pytest.mark.parametrize(
    ("transport_error", "domain_error"),
    [
        (OmniRouteAuthError(401, "bad", "up-1"), AIUpstreamAuthError),
        (OmniRouteClientError(400, "bad", "up-2"), AIUpstreamRequestError),
        (OmniRouteServerError(500, "bad", "up-3"), AIUpstreamUnavailableError),
        (OmniRouteConnectionError("down"), AIUpstreamUnavailableError),
        (OmniRouteTimeoutError("slow"), AIUpstreamUnavailableError),
        (OSError("missing secret"), AIUpstreamUnavailableError),
    ],
)
async def test_omniroute_ai_provider_normalizes_transport_errors(
    transport_error: Exception,
    domain_error: type[Exception],
) -> None:
    provider = OmniRouteAIProvider(FailingClient(transport_error))  # type: ignore[arg-type]
    with pytest.raises(domain_error):
        await provider.complete(_request(), target=AIModelTarget("model-a"))
