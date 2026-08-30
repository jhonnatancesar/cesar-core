import pytest
from pydantic import ValidationError

from cesar_core.policy.cost_policy import CostPolicy
from cesar_core.policy.requirements import Requirements
from cesar_core.policy.service_class import ServiceClass
from cesar_core.policy.service_kind import ServiceKind


def test_requirements_assembles_the_full_policy_shape() -> None:
    requirements = Requirements(
        service=ServiceKind.AI,
        service_class=ServiceClass.STANDARD,
        cost_policy=CostPolicy.FREE_PREFERRED,
    )
    assert requirements.service is ServiceKind.AI
    assert requirements.service_class is ServiceClass.STANDARD
    assert requirements.cost_policy is CostPolicy.FREE_PREFERRED


def test_requirements_rejects_unknown_service_kind() -> None:
    with pytest.raises(ValidationError):
        Requirements(
            service="unknown",
            service_class=ServiceClass.STANDARD,
            cost_policy=CostPolicy.FREE_ONLY,
        )


def test_requirements_has_no_duplicate_purpose_field() -> None:
    """purpose já viaja em ApplicationContext (ADR 0007) -- não duplicar aqui."""
    assert "purpose" not in Requirements.model_fields
