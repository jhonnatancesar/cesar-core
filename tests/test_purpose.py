import pytest
from pydantic import ValidationError

from cesar_core.policy.purpose import Purpose


def test_purpose_holds_free_text_value() -> None:
    assert Purpose(value="market_research").value == "market_research"


def test_purpose_rejects_empty_value() -> None:
    with pytest.raises(ValidationError):
        Purpose(value="")
