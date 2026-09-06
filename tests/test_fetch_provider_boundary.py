import inspect

import pytest

from cesar_core.fetch.provider import FetchProvider


def test_fetch_provider_declares_only_fetch() -> None:
    assert hasattr(FetchProvider, "fetch")
    assert not hasattr(FetchProvider, "search")
    assert not hasattr(FetchProvider, "complete")


def test_fetch_provider_cannot_be_instantiated() -> None:
    with pytest.raises(TypeError):
        FetchProvider()


def test_fetch_provider_remains_a_transport_agnostic_protocol() -> None:
    source = inspect.getsource(FetchProvider)
    assert "..." in source
    assert "http" not in source.lower()
    assert "requests" not in source.lower()
    assert "firecrawl" not in source.lower()
