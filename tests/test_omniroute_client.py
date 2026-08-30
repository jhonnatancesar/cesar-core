import json
from pathlib import Path

import httpx
import pytest

from cesar_core.omniroute.client import (
    CHAT_COMPLETIONS_PATH,
    REQUEST_ID_HEADER,
    SEARCH_PATH,
    OmniRouteClient,
)
from cesar_core.omniroute.config import OmniRouteConfig
from cesar_core.omniroute.errors import (
    OmniRouteAuthError,
    OmniRouteClientError,
    OmniRouteConnectionError,
    OmniRouteServerError,
    OmniRouteTimeoutError,
)


def _config(tmp_path: Path, api_key: str = "sk-test-key") -> OmniRouteConfig:
    key_file = tmp_path / "omniroute_api_key"
    key_file.write_text(api_key, encoding="utf-8")
    return OmniRouteConfig(_env_file=None, api_key_file=key_file, timeout_seconds=5.0)


def _client(tmp_path: Path, handler) -> OmniRouteClient:
    transport = httpx.MockTransport(handler)
    return OmniRouteClient(_config(tmp_path), transport=transport)


async def test_health_success(tmp_path: Path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/health"
        return httpx.Response(200, json={"status": "ok", "timestamp": "2026-08-30T00:00:00Z"})

    client = _client(tmp_path, handler)
    health = await client.health()
    assert health.status == "ok"
    await client.aclose()


async def test_health_timeout_maps_to_omniroute_timeout_error(tmp_path: Path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.TimeoutException("timed out", request=request)

    client = _client(tmp_path, handler)
    with pytest.raises(OmniRouteTimeoutError):
        await client.health()
    await client.aclose()


async def test_health_connection_error_maps_to_omniroute_connection_error(tmp_path: Path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused", request=request)

    client = _client(tmp_path, handler)
    with pytest.raises(OmniRouteConnectionError):
        await client.health()
    await client.aclose()


async def test_request_sends_bearer_auth_and_correlation_header(tmp_path: Path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["Authorization"] == "Bearer sk-test-key"
        assert request.headers[REQUEST_ID_HEADER] == "corr-123"
        return httpx.Response(200, json={"data": ["model-a"]})

    client = _client(tmp_path, handler)
    response = await client.request("GET", "/v1/models", correlation_id="corr-123")
    assert response.status_code == 200
    assert response.body == {"data": ["model-a"]}
    await client.aclose()


async def test_request_401_maps_to_auth_error(tmp_path: Path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, text="invalid key")

    client = _client(tmp_path, handler)
    with pytest.raises(OmniRouteAuthError) as exc_info:
        await client.request("GET", "/v1/models", correlation_id="corr-1")
    assert exc_info.value.status_code == 401
    await client.aclose()


async def test_request_403_maps_to_auth_error(tmp_path: Path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(403, text="forbidden")

    client = _client(tmp_path, handler)
    with pytest.raises(OmniRouteAuthError):
        await client.request("GET", "/v1/models", correlation_id="corr-1")
    await client.aclose()


async def test_request_404_maps_to_client_error(tmp_path: Path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, text="not found")

    client = _client(tmp_path, handler)
    with pytest.raises(OmniRouteClientError) as exc_info:
        await client.request("GET", "/v1/does-not-exist", correlation_id="corr-1")
    assert exc_info.value.status_code == 404
    await client.aclose()


async def test_request_500_maps_to_server_error(tmp_path: Path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="boom")

    client = _client(tmp_path, handler)
    with pytest.raises(OmniRouteServerError) as exc_info:
        await client.request("GET", "/v1/models", correlation_id="corr-1")
    assert exc_info.value.status_code == 500
    await client.aclose()


async def test_request_timeout_maps_to_omniroute_timeout_error(tmp_path: Path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.TimeoutException("timed out", request=request)

    client = _client(tmp_path, handler)
    with pytest.raises(OmniRouteTimeoutError):
        await client.request("GET", "/v1/models", correlation_id="corr-1")
    await client.aclose()


async def test_request_connection_error_maps_to_omniroute_connection_error(tmp_path: Path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused", request=request)

    client = _client(tmp_path, handler)
    with pytest.raises(OmniRouteConnectionError):
        await client.request("GET", "/v1/models", correlation_id="corr-1")
    await client.aclose()


async def test_request_captures_upstream_request_id_on_success(tmp_path: Path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers[REQUEST_ID_HEADER] == "corr-sent"
        return httpx.Response(
            200, json={"data": []}, headers={REQUEST_ID_HEADER: "omniroute-own-id"}
        )

    client = _client(tmp_path, handler)
    response = await client.request("GET", "/v1/models", correlation_id="corr-sent")
    assert response.upstream_request_id == "omniroute-own-id"
    await client.aclose()


async def test_request_captures_upstream_request_id_on_error(tmp_path: Path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, text="invalid key", headers={REQUEST_ID_HEADER: "omniroute-err-id"})

    client = _client(tmp_path, handler)
    with pytest.raises(OmniRouteAuthError) as exc_info:
        await client.request("GET", "/v1/models", correlation_id="corr-1")
    assert exc_info.value.upstream_request_id == "omniroute-err-id"
    await client.aclose()


async def test_chat_completions_posts_to_the_chat_endpoint(tmp_path: Path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert request.url.path == CHAT_COMPLETIONS_PATH
        assert json.loads(request.content) == {"model": "m", "messages": []}
        return httpx.Response(200, json={"id": "chatcmpl-1"})

    client = _client(tmp_path, handler)
    response = await client.chat_completions({"model": "m", "messages": []}, correlation_id="corr-1")
    assert response.status_code == 200
    assert response.body == {"id": "chatcmpl-1"}
    await client.aclose()


async def test_search_posts_to_the_search_endpoint(tmp_path: Path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert request.url.path == SEARCH_PATH
        return httpx.Response(200, json={"query": "x", "results": []})

    client = _client(tmp_path, handler)
    response = await client.search({"query": "x"}, correlation_id="corr-1")
    assert response.status_code == 200
    assert response.body == {"query": "x", "results": []}
    await client.aclose()


async def test_client_is_an_async_context_manager(tmp_path: Path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"status": "ok", "timestamp": "x"})

    async with _client(tmp_path, handler) as client:
        health = await client.health()
        assert health.status == "ok"
