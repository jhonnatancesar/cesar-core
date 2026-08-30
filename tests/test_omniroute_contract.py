"""Testes de contrato reais contra uma instância do OmniRoute rodando de
verdade -- nenhum mock aqui (ver tests/test_omniroute_client.py para os
testes unitários com transporte mockado).

Pulados automaticamente quando não há uma credencial local configurada,
para que o restante da suíte (ruff/pytest/cobertura) continue verde sem
depender de infraestrutura viva. Rodam de verdade só quando o OmniRoute
pinado (release/v3.8.51 @ 1f4dc830) está de pé em http://127.0.0.1:20128
e a chave mínima de inferência existe em .secrets/omniroute_api_key.
"""

from pathlib import Path

import pytest

from cesar_core.omniroute.client import OmniRouteClient
from cesar_core.omniroute.config import OmniRouteConfig

DEFAULT_KEY_FILE = Path(r"C:\cesar-core\.secrets\omniroute_api_key")

pytestmark = pytest.mark.contract

if not DEFAULT_KEY_FILE.exists():
    pytest.skip(
        "OmniRoute contract tests need a live instance + .secrets/omniroute_api_key "
        "(see docs/adr/0011-omniroute-low-level-client.md)",
        allow_module_level=True,
    )


def _client() -> OmniRouteClient:
    config = OmniRouteConfig(api_key_file=DEFAULT_KEY_FILE)
    return OmniRouteClient(config)


async def test_health_against_real_omniroute_without_any_paid_provider() -> None:
    client = _client()
    health = await client.health()
    assert health.status == "ok"
    assert health.timestamp
    await client.aclose()


async def test_authenticated_request_against_real_omniroute() -> None:
    client = _client()
    response = await client.request("GET", "/v1/models", correlation_id="cesar-core-contract-test")
    assert response.status_code == 200
    assert isinstance(response.body, dict)
    await client.aclose()


async def test_invalid_credential_is_a_distinct_auth_error() -> None:
    from cesar_core.omniroute.errors import OmniRouteAuthError

    bad_key_file = DEFAULT_KEY_FILE.parent / "omniroute_api_key_invalid_for_test"
    bad_key_file.write_text("sk-definitely-not-a-real-key", encoding="utf-8")
    try:
        client = OmniRouteClient(OmniRouteConfig(api_key_file=bad_key_file))
        with pytest.raises(OmniRouteAuthError):
            await client.request("GET", "/v1/models", correlation_id="cesar-core-contract-test")
        await client.aclose()
    finally:
        bad_key_file.unlink(missing_ok=True)
