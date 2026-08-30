from fastapi.testclient import TestClient

from cesar_core.api.app import app
from cesar_core.telemetry.correlation import CORRELATION_HEADER

client = TestClient(app)


def test_health_endpoint_reports_process_alive() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_ready_endpoint_reports_core_available() -> None:
    response = client.get("/ready")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "core": "available"}


def test_capabilities_endpoint_is_honest_about_unconfigured_services() -> None:
    response = client.get("/v1/capabilities")
    assert response.status_code == 200
    assert response.json() == {
        "core": "available",
        "ai": "not_configured",
        "search": "not_configured",
        "omniroute": "not_configured",
    }


def test_response_carries_correlation_id_header_even_when_not_sent() -> None:
    response = client.get("/health")
    assert response.headers.get(CORRELATION_HEADER)


def test_response_reuses_incoming_correlation_id_header() -> None:
    response = client.get("/health", headers={CORRELATION_HEADER: "fixed-id"})
    assert response.headers.get(CORRELATION_HEADER) == "fixed-id"
