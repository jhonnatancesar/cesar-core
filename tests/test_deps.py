from cesar_core.api.deps import get_application_context, get_correlation_id
from cesar_core.applications.identity import ApplicationId


def test_get_correlation_id_reuses_header_value() -> None:
    assert get_correlation_id("incoming") == "incoming"


def test_get_correlation_id_generates_when_missing() -> None:
    assert get_correlation_id(None)


def test_get_application_context_builds_context_from_headers() -> None:
    context = get_application_context(ApplicationId.GG_OFERTA, "corr-1")
    assert context.application_id is ApplicationId.GG_OFERTA
    assert context.correlation_id == "corr-1"


def test_get_application_context_generates_correlation_id_when_missing() -> None:
    context = get_application_context(ApplicationId.CLAUDIAO, None)
    assert context.application_id is ApplicationId.CLAUDIAO
    assert context.correlation_id
