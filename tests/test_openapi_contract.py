import json
from pathlib import Path

from cesar_core.api.app import app

CONTRACT_PATH = Path(__file__).resolve().parent.parent / "contracts" / "openapi.json"


def test_committed_openapi_contract_matches_the_app_schema() -> None:
    committed = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    assert committed == app.openapi()


def test_openapi_contract_documents_the_current_endpoints() -> None:
    committed = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    assert set(committed["paths"].keys()) == {
        "/health",
        "/ready",
        "/v1/capabilities",
        "/v1/ai/generate",
        "/v1/search",
        "/v1/fetch",
    }


def test_gateway_contract_uses_bearer_auth_without_application_id_header() -> None:
    committed = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    scheme = committed["components"]["securitySchemes"]["ApplicationBearer"]
    assert scheme == {"type": "http", "scheme": "bearer"}
    for path in ("/v1/ai/generate", "/v1/search", "/v1/fetch"):
        operation = committed["paths"][path]["post"]
        assert operation["security"] == [{"ApplicationBearer": []}]
        parameter_names = {item["name"] for item in operation["parameters"]}
        assert "X-Application-Id" not in parameter_names
