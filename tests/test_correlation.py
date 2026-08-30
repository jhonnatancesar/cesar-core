from cesar_core.telemetry.correlation import new_correlation_id, resolve_correlation_id


def test_new_correlation_id_is_not_empty() -> None:
    assert new_correlation_id()


def test_resolve_correlation_id_reuses_incoming_value() -> None:
    assert resolve_correlation_id("incoming-id") == "incoming-id"


def test_resolve_correlation_id_generates_when_missing() -> None:
    generated = resolve_correlation_id(None)
    assert generated
    assert generated != resolve_correlation_id(None)
