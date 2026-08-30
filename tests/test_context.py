import pytest
from pydantic import ValidationError

from cesar_core.applications.context import ApplicationContext
from cesar_core.applications.identity import ApplicationId


def test_application_context_holds_application_and_correlation_id() -> None:
    context = ApplicationContext(
        application_id=ApplicationId.GG_OFERTA,
        correlation_id="11111111-1111-1111-1111-111111111111",
    )
    assert context.application_id is ApplicationId.GG_OFERTA
    assert context.correlation_id == "11111111-1111-1111-1111-111111111111"


def test_application_context_rejects_empty_correlation_id() -> None:
    with pytest.raises(ValidationError):
        ApplicationContext(application_id=ApplicationId.GG_OFERTA, correlation_id="")
