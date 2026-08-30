from cesar_core.policy.cost_policy import CostPolicy
from cesar_core.policy.requirements import Requirements
from cesar_core.policy.service_class import ServiceClass


def test_requirements_assembles_quality_and_cost() -> None:
    requirements = Requirements(
        service_class=ServiceClass.STANDARD,
        cost_policy=CostPolicy.FREE_PREFERRED,
    )
    assert requirements.service_class is ServiceClass.STANDARD
    assert requirements.cost_policy is CostPolicy.FREE_PREFERRED


def test_requirements_has_no_duplicate_purpose_field() -> None:
    """purpose já viaja em ApplicationContext (ADR 0009) -- não duplicar aqui."""
    assert "purpose" not in Requirements.model_fields


def test_requirements_has_no_duplicate_service_field() -> None:
    """service (ServiceKind) foi removido: duplicava ApplicationContext.service
    com significado diferente, e o gateway já é dado pelo tipo do request
    (AIRequest vs SearchRequest, ADR 0009)."""
    assert "service" not in Requirements.model_fields
    assert set(Requirements.model_fields) == {"service_class", "cost_policy"}
