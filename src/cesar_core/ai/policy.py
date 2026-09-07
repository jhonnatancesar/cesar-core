"""Policy de seleção e autorização do Central AI Gateway."""

from collections.abc import Mapping
from dataclasses import dataclass

from cesar_core.ai.contracts import AIRequest
from cesar_core.ai.errors import (
    AIApplicationDeniedError,
    AICostPolicyDeniedError,
    AIMaxTokensUnsupportedError,
    AINotConfiguredError,
    AIRequestLimitExceededError,
)
from cesar_core.applications.identity import ApplicationId
from cesar_core.applications.registry import is_active
from cesar_core.policy.ai_profile import AIProfile
from cesar_core.policy.cost_policy import CostPolicy
from cesar_core.policy.service_class import ServiceClass

WILDCARD_PURPOSE = "*"
PolicyKey = tuple[ApplicationId, str, ServiceClass, AIProfile]


@dataclass(frozen=True, slots=True)
class AIModelTarget:
    """Alvo interno escolhido pela policy, nunca recebido no DTO público."""

    model: str
    provider: str | None = None
    paid: bool = False
    max_tokens_limit: int | None = None
    enforces_max_tokens: bool = False

    def __post_init__(self) -> None:
        if not self.model.strip():
            raise ValueError("AI model target cannot be empty")
        if self.max_tokens_limit is not None and self.max_tokens_limit < 1:
            raise ValueError("AI max_tokens_limit must be positive")


class AIPolicy:
    """Resolve application/purpose/service class e aplica restrição de custo."""

    def __init__(self, rules: Mapping[PolicyKey, AIModelTarget]) -> None:
        self._rules = dict(rules)

    def resolve(self, request: AIRequest) -> AIModelTarget:
        if not is_active(request.context.application_id):
            raise AIApplicationDeniedError(
                f"Application {request.context.application_id} is not active"
            )

        exact_key = (
            request.context.application_id,
            request.context.purpose.value,
            request.requirements.service_class,
            request.ai_profile,
        )
        wildcard_key = (
            request.context.application_id,
            WILDCARD_PURPOSE,
            request.requirements.service_class,
            request.ai_profile,
        )
        target = self._rules.get(exact_key) or self._rules.get(wildcard_key)
        if target is None:
            raise AINotConfiguredError(
                "No AI target configured for application, purpose and service class"
            )

        if request.requirements.cost_policy is CostPolicy.FREE_ONLY and target.paid:
            raise AICostPolicyDeniedError(
                "Configured AI target is paid but request is free_only"
            )
        if (
            request.max_tokens is not None
            and target.max_tokens_limit is not None
            and request.max_tokens > target.max_tokens_limit
        ):
            raise AIRequestLimitExceededError(
                "Requested max_tokens exceeds the policy limit"
            )
        if request.max_tokens is not None and not target.enforces_max_tokens:
            raise AIMaxTokensUnsupportedError(
                "Configured AI target does not enforce max_tokens upstream"
            )
        return target
