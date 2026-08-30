from cesar_core.policy.service_class import ServiceClass


def test_service_class_has_exactly_the_three_tiers() -> None:
    assert {member.value for member in ServiceClass} == {"economy", "standard", "quality"}
