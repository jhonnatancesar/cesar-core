import pytest

from cesar_core.applications.context import ApplicationContext
from cesar_core.applications.identity import ApplicationId
from cesar_core.fetch.contracts import FetchRequest
from cesar_core.fetch.errors import (
    FetchApplicationDeniedError,
    FetchCostPolicyDeniedError,
    FetchNotConfiguredError,
)
from cesar_core.fetch.policy import (
    WILDCARD_PURPOSE,
    FetchPolicy,
    FetchProviderTarget,
)
from cesar_core.policy.cost_policy import CostPolicy
from cesar_core.policy.purpose import Purpose
from cesar_core.policy.requirements import Requirements
from cesar_core.policy.service_class import ServiceClass


def _request(
    *,
    application: ApplicationId = ApplicationId.GG_OFERTA,
    purpose: str = "market_research",
    cost: CostPolicy = CostPolicy.FREE_ONLY,
) -> FetchRequest:
    return FetchRequest(
        context=ApplicationContext(
            application_id=application,
            service="worker",
            purpose=Purpose(value=purpose),
            request_id="req-1",
            correlation_id="corr-1",
        ),
        requirements=Requirements(
            service_class=ServiceClass.ECONOMY,
            cost_policy=cost,
        ),
        url="https://example.test/product",
    )


def _key(purpose: str = WILDCARD_PURPOSE):
    return (ApplicationId.GG_OFERTA, purpose, ServiceClass.ECONOMY)


def test_policy_prefers_exact_purpose_and_supports_wildcard() -> None:
    exact = FetchProviderTarget("exact-free")
    policy = FetchPolicy(
        {
            _key(): FetchProviderTarget("fallback-free"),
            _key("market_research"): exact,
        }
    )
    assert policy.resolve(_request()) is exact
    assert policy.resolve(_request(purpose="catalog")).provider == "fallback-free"


def test_policy_rejects_reserved_application() -> None:
    with pytest.raises(FetchApplicationDeniedError):
        FetchPolicy({}).resolve(_request(application=ApplicationId.CLAUDIAO))


def test_policy_rejects_missing_target() -> None:
    with pytest.raises(FetchNotConfiguredError):
        FetchPolicy({}).resolve(_request())


def test_policy_rejects_paid_target_for_free_only() -> None:
    policy = FetchPolicy({_key(): FetchProviderTarget("paid", paid=True)})
    with pytest.raises(FetchCostPolicyDeniedError):
        policy.resolve(_request())
    assert policy.resolve(_request(cost=CostPolicy.PAID_ALLOWED)).provider == "paid"


@pytest.mark.parametrize("kwargs", [{"provider": " "}, {"provider": " free "}])
def test_target_rejects_invalid_values(kwargs) -> None:
    with pytest.raises(ValueError):
        FetchProviderTarget(**kwargs)
