import pytest

from cesar_core.omniroute.errors import (
    OmniRouteAuthError,
    OmniRouteClientError,
    OmniRouteConnectionError,
    OmniRouteError,
    OmniRouteServerError,
    OmniRouteTimeoutError,
)


@pytest.mark.parametrize(
    "error_cls",
    [OmniRouteConnectionError, OmniRouteTimeoutError],
)
def test_transport_errors_are_omniroute_errors(error_cls: type[OmniRouteError]) -> None:
    assert issubclass(error_cls, OmniRouteError)
    assert isinstance(error_cls("boom"), OmniRouteError)


@pytest.mark.parametrize(
    "error_cls",
    [OmniRouteAuthError, OmniRouteClientError, OmniRouteServerError],
)
def test_http_status_errors_carry_status_and_body(error_cls: type[OmniRouteError]) -> None:
    error = error_cls(403, "forbidden body")
    assert isinstance(error, OmniRouteError)
    assert error.status_code == 403
    assert error.body == "forbidden body"


def test_401_and_403_are_distinct_from_generic_client_error() -> None:
    """Guardrail do plano-mestre: 401/403 não podem virar um 4xx genérico."""
    assert not issubclass(OmniRouteAuthError, OmniRouteClientError)
    assert not issubclass(OmniRouteClientError, OmniRouteAuthError)
