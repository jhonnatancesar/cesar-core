import inspect

import pytest

from cesar_core.ai.provider import AIProvider


def test_ai_provider_declares_only_complete() -> None:
    assert hasattr(AIProvider, "complete")
    assert not hasattr(AIProvider, "search")


def test_ai_provider_cannot_be_instantiated() -> None:
    with pytest.raises(TypeError):
        AIProvider()


def test_ai_provider_has_no_real_implementation() -> None:
    source = inspect.getsource(AIProvider)
    assert "..." in source
    assert "http" not in source.lower()
    assert "requests" not in source.lower()
