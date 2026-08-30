import inspect

import pytest

from cesar_core.omniroute.gateway import OmniRouteGateway


def test_omniroute_gateway_declares_the_expected_methods() -> None:
    assert hasattr(OmniRouteGateway, "complete")
    assert hasattr(OmniRouteGateway, "search")


def test_omniroute_gateway_cannot_be_instantiated() -> None:
    with pytest.raises(TypeError):
        OmniRouteGateway()


def test_omniroute_gateway_has_no_real_implementation() -> None:
    source = inspect.getsource(OmniRouteGateway)
    assert "..." in source
    assert "http" not in source.lower()
    assert "requests" not in source.lower()
