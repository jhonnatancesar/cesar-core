"""Policy de seleção e autorização do Central Web Fetch/Enrichment Gateway."""

from collections.abc import Mapping
from dataclasses import dataclass

from cesar_core.applications.identity import ApplicationId
from cesar_core.applications.registry import is_active
from cesar_core.fetch.contracts import FetchRequest
from cesar_core.fetch.errors import (
    FetchApplicationDeniedError,
    FetchCostPolicyDeniedError,
    FetchNotConfiguredError,
)
from cesar_core.policy.cost_policy import CostPolicy
from cesar_core.policy.service_class import ServiceClass

WILDCARD_PURPOSE = "*"
PolicyKey = tuple[ApplicationId, str, ServiceClass]


@dataclass(frozen=True, slots=True)
class FetchProviderTarget:
    """Provider interno escolhido pela policy, nunca recebido no DTO público."""

    provider: str
    paid: bool = False

    def __post_init__(self) -> None:
        if not self.provider.strip() or self.provider != self.provider.strip():
            raise ValueError("Fetch provider target must be a normalized value")


class FetchPolicy:
    """Resolve application/purpose/service class e aplica a política de custo."""

    def __init__(self, rules: Mapping[PolicyKey, FetchProviderTarget]) -> None:
        self._rules = dict(rules)

    def resolve(self, request: FetchRequest) -> FetchProviderTarget:
        if not is_active(request.context.application_id):
            raise FetchApplicationDeniedError(
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
            raise FetchNotConfiguredError(
                "No Fetch target configured for application, purpose and service class"
            )
        if request.requirements.cost_policy is CostPolicy.FREE_ONLY and target.paid:
            raise FetchCostPolicyDeniedError(
                "Configured Fetch target is paid but request is free_only"
            )
        return target
