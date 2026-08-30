from cesar_core.policy.cost_policy import CostPolicy


def test_cost_policy_has_exactly_the_three_options() -> None:
    assert {member.value for member in CostPolicy} == {
        "free_only",
        "free_preferred",
        "paid_allowed",
    }
