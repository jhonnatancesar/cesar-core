import json

import httpx
import pytest
from fastapi.testclient import TestClient

from cesar_core.admin.storage import get_store
from cesar_core.ai.contracts import AIRequest, AIRequestPayload
from cesar_core.ai.manager import AIManager
from cesar_core.ai.policy import AIModelTarget, AIPolicy
from cesar_core.ai.providers.omniroute import OmniRouteAIProvider
from cesar_core.api.app import create_app
from cesar_core.api.deps import QUOTA_LIMITER, get_ai_manager
from cesar_core.applications.identity import ApplicationId
from cesar_core.applications.registry import REGISTRY
from cesar_core.omniroute.client import OmniRouteClient
from cesar_core.omniroute.config import OmniRouteConfig
from cesar_core.policy.service_class import ServiceClass


@pytest.fixture
def typed_client(monkeypatch, tmp_path):
    key = tmp_path / "fixture-key"
    key.write_text("synthetic-message-test-key", encoding="utf-8")
    monkeypatch.setenv("CESAR_CORE_SECURITY_GG_OFERTA_API_KEY_FILE", str(key))
    QUOTA_LIMITER.reset()
    wire = []

    def upstream(request):
        wire.append(json.loads(request.content))
        return httpx.Response(
            200,
            json={
                "model": "fixture-model",
                "choices": [{"message": {"content": "ok"}}],
                "usage": {
                    "prompt_tokens": 10,
                    "completion_tokens": 2,
                    "total_tokens": 12,
                },
            },
        )

    policy = AIPolicy(
        {
            (
                ApplicationId.GG_OFERTA,
                "messages_test",
                ServiceClass.ECONOMY,
            ): AIModelTarget(
                "fixture-model", enforces_max_tokens=True, max_tokens_limit=8
            )
        }
    )

    async def manager():
        async with OmniRouteClient(
            OmniRouteConfig(_env_file=None, api_key_file=key),
            transport=httpx.MockTransport(upstream),
        ) as gateway:
            yield AIManager(OmniRouteAIProvider(gateway), policy)

    app = create_app()
    app.dependency_overrides[get_ai_manager] = manager
    with TestClient(app) as client:
        client.headers.update(
            {
                "Authorization": "Bearer synthetic-message-test-key",
                "X-Service": "contract_test",
                "X-Purpose": "messages_test",
            }
        )
        yield client, wire


def send(client, **payload):
    return client.post(
        "/v1/ai/generate",
        json={
            "requirements": {"service_class": "economy", "cost_policy": "free_only"},
            "max_tokens": 8,
            **payload,
        },
    )


@pytest.mark.parametrize(
    "roles",
    [
        ["user"],
        ["system", "user"],
        ["system", "user", "assistant", "user"],
    ],
)
def test_roles_order_and_cap_reach_provider(typed_client, roles):
    client, wire = typed_client
    messages = [
        {"role": role, "content": f"private-message-{i}"}
        for i, role in enumerate(roles)
    ]
    response = send(client, messages=messages)
    assert response.status_code == 200
    assert wire == [{"model": "fixture-model", "messages": messages, "max_tokens": 8}]


def test_legacy_prompt_normalizes_without_changing_text(typed_client):
    client, wire = typed_client
    assert send(client, prompt="  legacy text  ").status_code == 200
    assert wire[0]["messages"] == [{"role": "user", "content": "  legacy text  "}]
    assert not issubclass(AIRequest, AIRequestPayload)
    assert "prompt" not in AIRequest.model_fields


def test_grounding_flag_is_provider_agnostic_and_defaults_off():
    payload = AIRequestPayload(
        requirements={"service_class": "economy", "cost_policy": "free_only"},
        messages=[{"role": "user", "content": "question"}],
        require_search_grounding=True,
    )
    assert payload.require_search_grounding is True
    assert AIRequestPayload(
        requirements={"service_class": "economy", "cost_policy": "free_only"},
        prompt="question",
    ).require_search_grounding is False


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"prompt": "private", "messages": [{"role": "user", "content": "private"}]},
        {"messages": []},
        {"messages": None},
        {"prompt": None},
        {"prompt": "private", "messages": None},
        {"messages": [{"role": "developer", "content": "private"}]},
        {"messages": [{"role": "user", "content": 123}]},
        {"messages": [{"role": "user", "content": "   "}]},
        {"messages": [{"role": "system", "content": ""}]},
        {"messages": [{"role": "user", "content": ["private"]}]},
    ],
)
def test_invalid_messages_are_normalized_400_without_upstream(
    typed_client, payload, caplog
):
    client, wire = typed_client
    response = send(client, **payload)
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "ai_invalid_request"
    assert response.json()["error"]["request_id"]
    assert "private" not in response.text + caplog.text
    assert not wire


def test_messages_do_not_bypass_auth_capability_quota_or_policy(
    typed_client, monkeypatch
):
    client, wire = typed_client
    payload = {"messages": [{"role": "user", "content": "private"}]}
    token = client.headers.pop("Authorization")
    assert send(client, **payload).status_code == 401
    client.headers["Authorization"] = token
    entry = REGISTRY[ApplicationId.GG_OFERTA]
    monkeypatch.setitem(
        REGISTRY,
        ApplicationId.GG_OFERTA,
        entry.model_copy(update={"allowed_capabilities": frozenset()}),
    )
    assert send(client, **payload).status_code == 403
    assert not wire
    monkeypatch.setitem(REGISTRY, ApplicationId.GG_OFERTA, entry)
    assert send(client, **payload, max_tokens=9).status_code == 403
    assert not wire
    QUOTA_LIMITER.reset()
    get_store().update_application(
        "gg_oferta",
        display_name=entry.display_name,
        state="active",
        capabilities={"ai", "search"},
        quotas={"ai": 1, "search": 60},
    )
    assert send(client, **payload).status_code == 200
    assert send(client, **payload).status_code == 429
    assert len(wire) == 1
