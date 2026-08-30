import pytest
from pydantic import ValidationError

from cesar_core.policy.cost_policy import CostPolicy
from cesar_core.policy.purpose import Purpose
from cesar_core.policy.requirements import Requirements
from cesar_core.policy.service_class import ServiceClass
from cesar_core.policy.service_kind import ServiceKind


def test_requirements_assembles_the_full_policy_shape() -> None:
    requirements = Requirements(
        service=ServiceKind.AI,
        service_class=ServiceClass.STANDARD,
        cost_policy=CostPolicy.FREE_PREFERRED,
        purpose=Purpose(value="classificação de categoria de produto"),
    )
    assert requirements.service is ServiceKind.AI
    assert requirements.service_class is ServiceClass.STANDARD
    assert requirements.cost_policy is CostPolicy.FREE_PREFERRED
    assert requirements.purpose.value == "classificação de categoria de produto"


def test_purpose_rejects_empty_value() -> None:
    with pytest.raises(ValidationError):
        Purpose(value="")


def test_requirements_rejects_unknown_service_kind() -> None:
    with pytest.raises(ValidationError):
        Requirements(
            service="unknown",
            service_class=ServiceClass.STANDARD,
            cost_policy=CostPolicy.FREE_ONLY,
            purpose=Purpose(value="x"),
        )
