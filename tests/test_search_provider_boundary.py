import inspect

import pytest

from cesar_core.search.provider import SearchProvider


def test_search_provider_declares_only_search() -> None:
    assert hasattr(SearchProvider, "search")
    assert not hasattr(SearchProvider, "complete")


def test_search_provider_cannot_be_instantiated() -> None:
    with pytest.raises(TypeError):
        SearchProvider()


def test_search_provider_has_no_real_implementation() -> None:
    source = inspect.getsource(SearchProvider)
    assert "..." in source
    assert "http" not in source.lower()
    assert "requests" not in source.lower()
