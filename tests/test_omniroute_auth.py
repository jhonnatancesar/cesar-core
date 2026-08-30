from cesar_core.omniroute.auth import bearer_header


def test_bearer_header_format() -> None:
    assert bearer_header("sk-abc123") == {"Authorization": "Bearer sk-abc123"}
