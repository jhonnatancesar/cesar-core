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
    }
