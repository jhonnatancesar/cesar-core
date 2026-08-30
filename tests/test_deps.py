from cesar_core.api.deps import get_application_context, get_correlation_id
from cesar_core.applications.identity import ApplicationId


def test_get_correlation_id_reuses_header_value() -> None:
    assert get_correlation_id("incoming") == "incoming"


def test_get_correlation_id_generates_when_missing() -> None:
    assert get_correlation_id(None)


def test_get_application_context_builds_context_from_headers() -> None:
    context = get_application_context(
        ApplicationId.GG_OFERTA, "collection_worker", "market_research", "corr-1"
    )
    assert context.application_id is ApplicationId.GG_OFERTA
    assert context.service == "collection_worker"
    assert context.purpose.value == "market_research"
    assert context.correlation_id == "corr-1"
    assert context.request_id


def test_get_application_context_generates_correlation_id_when_missing() -> None:
    context = get_application_context(ApplicationId.CLAUDIAO, "bot", "chat", None)
    assert context.application_id is ApplicationId.CLAUDIAO
    assert context.correlation_id


def test_get_application_context_generates_a_fresh_request_id_every_call() -> None:
    first = get_application_context(ApplicationId.GG_OFERTA, "bot", "chat", "corr-x")
    second = get_application_context(ApplicationId.GG_OFERTA, "bot", "chat", "corr-x")
    assert first.request_id != second.request_id
