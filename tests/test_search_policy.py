import pytest

from cesar_core.applications.context import ApplicationContext
from cesar_core.applications.identity import ApplicationId
from cesar_core.policy.cost_policy import CostPolicy
from cesar_core.policy.purpose import Purpose
from cesar_core.policy.requirements import Requirements
from cesar_core.policy.service_class import ServiceClass
from cesar_core.search.contracts import SearchRequest
from cesar_core.search.errors import (
    SearchApplicationDeniedError,
    SearchCostPolicyDeniedError,
    SearchNotConfiguredError,
    SearchRequestLimitExceededError,
)
from cesar_core.search.policy import (
    WILDCARD_PURPOSE,
    SearchPolicy,
    SearchProviderTarget,
)


def _request(
    *,
    application: ApplicationId = ApplicationId.GG_OFERTA,
    purpose: str = "market_research",
    cost: CostPolicy = CostPolicy.FREE_ONLY,
    max_results: int = 5,
) -> SearchRequest:
    return SearchRequest(
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
        query="placa de video",
        max_results=max_results,
    )


def _key(purpose: str = WILDCARD_PURPOSE):
    return (ApplicationId.GG_OFERTA, purpose, ServiceClass.ECONOMY)


def test_policy_prefers_exact_purpose_and_supports_wildcard() -> None:
    exact = SearchProviderTarget("exact-free")
    policy = SearchPolicy(
        {
            _key(): SearchProviderTarget("fallback-free"),
            _key("market_research"): exact,
        }
    )
    assert policy.resolve(_request()) is exact
    assert policy.resolve(_request(purpose="catalog")).provider == "fallback-free"


def test_policy_rejects_reserved_application() -> None:
    with pytest.raises(SearchApplicationDeniedError):
        SearchPolicy({}).resolve(_request(application=ApplicationId.CLAUDIAO))


def test_policy_rejects_missing_target() -> None:
    with pytest.raises(SearchNotConfiguredError):
        SearchPolicy({}).resolve(_request())


def test_policy_rejects_paid_target_for_free_only() -> None:
    policy = SearchPolicy({_key(): SearchProviderTarget("paid", paid=True)})
    with pytest.raises(SearchCostPolicyDeniedError):
        policy.resolve(_request())
    assert policy.resolve(_request(cost=CostPolicy.PAID_ALLOWED)).provider == "paid"


def test_policy_enforces_max_results_before_upstream() -> None:
    policy = SearchPolicy({_key(): SearchProviderTarget("free", max_results_limit=3)})
    with pytest.raises(SearchRequestLimitExceededError):
        policy.resolve(_request(max_results=4))


@pytest.mark.parametrize(
    "kwargs",
    [
        {"provider": " "},
        {"provider": " free "},
        {"provider": "free", "max_results_limit": 0},
    ],
)
def test_target_rejects_invalid_values(kwargs) -> None:
    with pytest.raises(ValueError):
        SearchProviderTarget(**kwargs)
