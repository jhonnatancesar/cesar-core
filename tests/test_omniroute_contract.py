"""Testes de contrato reais contra uma instância do OmniRoute rodando de
verdade -- nenhum mock aqui (ver tests/test_omniroute_client.py para os
testes unitários com transporte mockado).

Autoridade: diegosouzapw/omniroute:3.8.50, digest
sha256:085c57adf499a8aaa9f35ccde95c0df9c11bd9ecd18d6c9edbf3b68b8079ba9d
(ver docs/adr/0012-omniroute-runtime-baseline-3-8-50.md) -- não o
commit 1f4dc830, que está fora do baseline executável.

Pulados automaticamente quando não há uma credencial local configurada,
para que o restante da suíte (ruff/pytest/cobertura) continue verde sem
depender de infraestrutura viva.

Três superfícies reais:
  A. health  -- GET /api/health, sem autenticação, sem provider pago.
  B. search  -- POST /v1/search, sem provider especificado; o OmniRoute
     promove "duckduckgo-free" (fallback zero-config, sem credencial)
     automaticamente. Prova auth + request + envelope + parsing reais.
  C. chat    -- POST /v1/chat/completions, sem upstream pago configurado:
     teste controlado com um model inexistente. Prova endpoint correto +
     Bearer auth aceita + request enviado + erro real (400) classificado
     como OmniRouteClientError -- suficiente para a camada de transporte,
     sem precisar de um provider de chat configurado.
"""

from pathlib import Path

import pytest

from cesar_core.omniroute.client import OmniRouteClient
from cesar_core.omniroute.config import OmniRouteConfig
from cesar_core.omniroute.errors import OmniRouteAuthError, OmniRouteClientError

DEFAULT_KEY_FILE = Path(r"C:\cesar-core\.secrets\omniroute_api_key")

pytestmark = pytest.mark.contract

if not DEFAULT_KEY_FILE.exists():
    pytest.skip(
        "OmniRoute contract tests need a live instance + .secrets/omniroute_api_key "
        "(see docs/adr/0012-omniroute-runtime-baseline-3-8-50.md)",
        allow_module_level=True,
    )


def _client() -> OmniRouteClient:
    config = OmniRouteConfig(api_key_file=DEFAULT_KEY_FILE)
    return OmniRouteClient(config)


async def test_a_health_against_real_omniroute_without_any_paid_provider() -> None:
    client = _client()
    health = await client.health()
    assert health.status == "ok"
    assert health.timestamp
    await client.aclose()


async def test_b_search_against_real_omniroute_using_the_free_fallback_provider() -> None:
    """POST /v1/search real, sem provider especificado -- o OmniRoute
    promove duckduckgo-free (zero credencial) automaticamente."""
    client = _client()
    response = await client.search(
        {"query": "OmniRoute cesar core contract test"}, correlation_id="cesar-core-contract-search"
    )
    assert response.status_code == 200
    assert response.body["provider"] == "duckduckgo-free"
    assert isinstance(response.body["results"], list)
    assert response.upstream_request_id
    await client.aclose()


async def test_c_chat_completions_against_real_omniroute_unresolvable_model_is_a_client_error() -> None:
    """POST /v1/chat/completions real, sem upstream pago configurado: prova
    endpoint + auth + request + erro real classificado -- suficiente pra
    camada de transporte (não exige provider de chat configurado)."""
    client = _client()
    with pytest.raises(OmniRouteClientError) as exc_info:
        await client.chat_completions(
            {
                "model": "does-not-exist-cesar-core-contract-test",
                "messages": [{"role": "user", "content": "ping"}],
            },
            correlation_id="cesar-core-contract-chat",
        )
    assert exc_info.value.status_code == 400
    await client.aclose()


async def test_authenticated_request_against_real_omniroute() -> None:
    client = _client()
    response = await client.request("GET", "/v1/models", correlation_id="cesar-core-contract-test")
    assert response.status_code == 200
    assert isinstance(response.body, dict)
    await client.aclose()


async def test_invalid_credential_is_a_distinct_auth_error() -> None:
    bad_key_file = DEFAULT_KEY_FILE.parent / "omniroute_api_key_invalid_for_test"
    bad_key_file.write_text("sk-definitely-not-a-real-key", encoding="utf-8")
    try:
        client = OmniRouteClient(OmniRouteConfig(api_key_file=bad_key_file))
        with pytest.raises(OmniRouteAuthError):
            await client.request("GET", "/v1/models", correlation_id="cesar-core-contract-test")
        await client.aclose()
    finally:
        bad_key_file.unlink(missing_ok=True)
