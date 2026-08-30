import pytest
from pydantic import ValidationError

from cesar_core.applications.context import ApplicationContext
from cesar_core.applications.identity import ApplicationId
from cesar_core.policy.purpose import Purpose


def _context(**overrides) -> ApplicationContext:
    defaults = dict(
        application_id=ApplicationId.GG_OFERTA,
        service="collection_worker",
        purpose=Purpose(value="market_research"),
        request_id="11111111-1111-1111-1111-111111111111",
        correlation_id="22222222-2222-2222-2222-222222222222",
    )
    defaults.update(overrides)
    return ApplicationContext(**defaults)


def test_application_context_carries_identity_end_to_end() -> None:
    context = _context()
    assert context.application_id is ApplicationId.GG_OFERTA
    assert context.service == "collection_worker"
    assert context.purpose.value == "market_research"
    assert context.request_id == "11111111-1111-1111-1111-111111111111"
    assert context.correlation_id == "22222222-2222-2222-2222-222222222222"


def test_application_context_rejects_empty_correlation_id() -> None:
    with pytest.raises(ValidationError):
        _context(correlation_id="")


def test_application_context_rejects_empty_request_id() -> None:
    with pytest.raises(ValidationError):
        _context(request_id="")


def test_application_context_rejects_empty_service() -> None:
    with pytest.raises(ValidationError):
        _context(service="")


def test_application_context_has_no_separate_trace_id_field() -> None:
    assert "trace_id" not in ApplicationContext.model_fields
