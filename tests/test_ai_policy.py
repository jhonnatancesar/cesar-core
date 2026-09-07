import pytest

from cesar_core.ai.contracts import AIRequest
from cesar_core.ai.errors import (
    AIApplicationDeniedError,
    AICostPolicyDeniedError,
    AIMaxTokensUnsupportedError,
    AINotConfiguredError,
    AIRequestLimitExceededError,
)
from cesar_core.ai.policy import WILDCARD_PURPOSE, AIModelTarget, AIPolicy
from cesar_core.applications.context import ApplicationContext
from cesar_core.applications.identity import ApplicationId
from cesar_core.policy.ai_profile import AIProfile
from cesar_core.policy.cost_policy import CostPolicy
from cesar_core.policy.purpose import Purpose
from cesar_core.policy.requirements import Requirements
from cesar_core.policy.service_class import ServiceClass


def _request(
    *,
    application: ApplicationId = ApplicationId.GG_OFERTA,
    purpose: str = "market_research",
    cost: CostPolicy = CostPolicy.FREE_ONLY,
    max_tokens: int | None = None,
    ai_profile: AIProfile = AIProfile.ADMIN_DEV,
) -> AIRequest:
    return AIRequest(
        context=ApplicationContext(
            application_id=application,
            service="worker",
            purpose=Purpose(value=purpose),
            request_id="req-1",
            correlation_id="corr-1",
        ),
        ai_profile=ai_profile,
        requirements=Requirements(
            service_class=ServiceClass.ECONOMY,
            cost_policy=cost,
        ),
        messages=({"role": "user", "content": "ping"},),
        max_tokens=max_tokens,
    )


def test_policy_prefers_exact_purpose_over_wildcard() -> None:
    exact = AIModelTarget("exact-model")
    policy = AIPolicy(
        {
            (
                ApplicationId.GG_OFERTA,
                WILDCARD_PURPOSE,
                ServiceClass.ECONOMY,
                AIProfile.ADMIN_DEV,
            ): AIModelTarget("fallback-model"),
            (
                ApplicationId.GG_OFERTA,
                "market_research",
                ServiceClass.ECONOMY,
                AIProfile.ADMIN_DEV,
            ): exact,
        }
    )
    assert policy.resolve(_request()) is exact


def test_policy_uses_wildcard_purpose() -> None:
    target = AIModelTarget("model-a")
    policy = AIPolicy(
        {
            (
                ApplicationId.GG_OFERTA,
                WILDCARD_PURPOSE,
                ServiceClass.ECONOMY,
                AIProfile.ADMIN_DEV,
            ): target
        }
    )
    assert policy.resolve(_request(purpose="another")) is target


def test_policy_rejects_reserved_application() -> None:
    with pytest.raises(AIApplicationDeniedError):
        AIPolicy({}).resolve(_request(application=ApplicationId.CLAUDIAO))


def test_policy_rejects_missing_target() -> None:
    with pytest.raises(AINotConfiguredError):
        AIPolicy({}).resolve(_request())


def test_policy_rejects_paid_target_for_free_only() -> None:
    policy = AIPolicy(
        {
            (
                ApplicationId.GG_OFERTA,
                WILDCARD_PURPOSE,
                ServiceClass.ECONOMY,
                AIProfile.ADMIN_DEV,
            ): AIModelTarget("paid-model", paid=True)
        }
    )
    with pytest.raises(AICostPolicyDeniedError):
        policy.resolve(_request())
    assert policy.resolve(_request(cost=CostPolicy.PAID_ALLOWED)).model == "paid-model"


def test_policy_enforces_max_tokens_limit() -> None:
    policy = AIPolicy(
        {
            (
                ApplicationId.GG_OFERTA,
                WILDCARD_PURPOSE,
                ServiceClass.ECONOMY,
                AIProfile.ADMIN_DEV,
            ): AIModelTarget("model-a", max_tokens_limit=100, enforces_max_tokens=True)
        }
    )
    with pytest.raises(AIRequestLimitExceededError):
        policy.resolve(_request(max_tokens=101))


def test_policy_rejects_max_tokens_before_upstream_when_target_is_not_certified() -> (
    None
):
    policy = AIPolicy(
        {
            (
                ApplicationId.GG_OFERTA,
                WILDCARD_PURPOSE,
                ServiceClass.ECONOMY,
                AIProfile.ADMIN_DEV,
            ): AIModelTarget("auto/best-free")
        }
    )

    with pytest.raises(AIMaxTokensUnsupportedError):
        policy.resolve(_request(max_tokens=8))


def test_model_target_rejects_invalid_values() -> None:
    with pytest.raises(ValueError):
        AIModelTarget(" ")
    with pytest.raises(ValueError):
        AIModelTarget("model", max_tokens_limit=0)
