"""Policy de seleção e autorização do Central Web Search Gateway."""

from collections.abc import Mapping
from dataclasses import dataclass

from cesar_core.applications.identity import ApplicationId
from cesar_core.applications.registry import is_active
from cesar_core.policy.cost_policy import CostPolicy
from cesar_core.policy.service_class import ServiceClass
from cesar_core.search.contracts import SearchRequest
from cesar_core.search.errors import (
    SearchApplicationDeniedError,
    SearchCostPolicyDeniedError,
    SearchNotConfiguredError,
    SearchRequestLimitExceededError,
)

WILDCARD_PURPOSE = "*"
PolicyKey = tuple[ApplicationId, str, ServiceClass]


@dataclass(frozen=True, slots=True)
class SearchProviderTarget:
    """Provider interno escolhido pela policy, nunca recebido no DTO público."""

    provider: str
    paid: bool = False
    max_results_limit: int = 20

    def __post_init__(self) -> None:
        if not self.provider.strip() or self.provider != self.provider.strip():
            raise ValueError("Search provider target must be a normalized value")
        if not 1 <= self.max_results_limit <= 100:
            raise ValueError("Search max_results_limit must be between 1 and 100")


class SearchPolicy:
    """Resolve application/purpose/service class e aplica custo/limites."""

    def __init__(self, rules: Mapping[PolicyKey, SearchProviderTarget]) -> None:
        self._rules = dict(rules)

    def resolve(self, request: SearchRequest) -> SearchProviderTarget:
        if not is_active(request.context.application_id):
            raise SearchApplicationDeniedError(
                f"Application {request.context.application_id} is not active"
            )

        exact_key = (
            request.context.application_id,
            request.context.purpose.value,
            request.requirements.service_class,
        )
        wildcard_key = (
            request.context.application_id,
            WILDCARD_PURPOSE,
            request.requirements.service_class,
        )
        target = self._rules.get(exact_key) or self._rules.get(wildcard_key)
        if target is None:
            raise SearchNotConfiguredError(
                "No Search target configured for application, purpose and service class"
            )
        if request.requirements.cost_policy is CostPolicy.FREE_ONLY and target.paid:
            raise SearchCostPolicyDeniedError(
                "Configured Search target is paid but request is free_only"
            )
        if request.max_results > target.max_results_limit:
            raise SearchRequestLimitExceededError(
                "Requested max_results exceeds the policy limit"
            )
        return target
