import pytest

from cesar_core.ai.contracts import AIRequest, AIResponse
from cesar_core.ai.errors import AIUpstreamUnavailableError
from cesar_core.ai.manager import AIManager
from cesar_core.ai.policy import WILDCARD_PURPOSE, AIModelTarget, AIPolicy
from cesar_core.applications.context import ApplicationContext
from cesar_core.applications.identity import ApplicationId
from cesar_core.policy.ai_profile import AIProfile
from cesar_core.policy.cost_policy import CostPolicy
from cesar_core.policy.purpose import Purpose
from cesar_core.policy.requirements import Requirements
from cesar_core.policy.service_class import ServiceClass


class StubProvider:
    def __init__(self, result: AIResponse | Exception) -> None:
        self.result = result
        self.target: AIModelTarget | None = None

    async def complete(
        self, request: AIRequest, *, target: AIModelTarget
    ) -> AIResponse:
        self.target = target
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


def _request() -> AIRequest:
    return AIRequest(
        context=ApplicationContext(
            application_id=ApplicationId.GG_OFERTA,
            service="worker",
            purpose=Purpose(value="chat"),
            request_id="req-1",
            correlation_id="corr-1",
        ),
        ai_profile=AIProfile.ADMIN_DEV,
        requirements=Requirements(
            service_class=ServiceClass.STANDARD,
            cost_policy=CostPolicy.FREE_PREFERRED,
        ),
        messages=({"role": "user", "content": "ping"},),
    )


def _policy() -> AIPolicy:
    return AIPolicy(
        {
            (
                ApplicationId.GG_OFERTA,
                WILDCARD_PURPOSE,
                ServiceClass.STANDARD,
                AIProfile.ADMIN_DEV,
            ): AIModelTarget("model-a")
        }
    )


def _response() -> AIResponse:
    return AIResponse(
        request_id="req-1",
        correlation_id="corr-1",
        content="pong",
        provider_gateway="omniroute",
        model="model-a",
        latency_ms=0,
    )


async def test_manager_applies_policy_and_records_latency() -> None:
    provider = StubProvider(_response())
    response = await AIManager(provider, _policy()).generate(_request())  # type: ignore[arg-type]
    assert provider.target is not None and provider.target.model == "model-a"
    assert response.content == "pong"
    assert response.latency_ms >= 0


async def test_manager_propagates_normalized_provider_error() -> None:
    error = AIUpstreamUnavailableError("down")
    manager = AIManager(StubProvider(error), _policy())  # type: ignore[arg-type]
    with pytest.raises(AIUpstreamUnavailableError) as exc_info:
        await manager.generate(_request())
    assert exc_info.value is error
