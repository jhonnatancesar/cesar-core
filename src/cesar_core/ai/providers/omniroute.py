"""Adapter do contrato AI do César Core para o transporte OmniRoute."""

from typing import Any

from cesar_core.ai.contracts import AIRequest, AIResponse, AIUsage
from cesar_core.ai.errors import (
    AIUpstreamAuthError,
    AIUpstreamRequestError,
    AIUpstreamResponseError,
    AIUpstreamUnavailableError,
)
from cesar_core.ai.policy import AIModelTarget
from cesar_core.omniroute.client import OmniRouteClient
from cesar_core.omniroute.errors import (
    OmniRouteAuthError,
    OmniRouteClientError,
    OmniRouteConnectionError,
    OmniRouteServerError,
    OmniRouteTimeoutError,
)


class OmniRouteAIProvider:
    """Traduz requests/responses de AI sem vazar o payload upstream."""

    def __init__(self, client: OmniRouteClient) -> None:
        self._client = client

    async def complete(
        self, request: AIRequest, *, target: AIModelTarget
    ) -> AIResponse:
        payload: dict[str, Any] = {
            "model": target.model,
            "messages": [{"role": "user", "content": request.prompt}],
        }
        if target.provider is not None:
            payload["provider"] = target.provider
        if request.max_tokens is not None:
            payload["max_tokens"] = request.max_tokens

        try:
            upstream = await self._client.chat_completions(
                payload, correlation_id=request.context.correlation_id
            )
        except OmniRouteAuthError as exc:
            raise AIUpstreamAuthError(
                "AI gateway authentication failed",
                status_code=exc.status_code,
                upstream_request_id=exc.upstream_request_id,
            ) from exc
        except OmniRouteClientError as exc:
            raise AIUpstreamRequestError(
                "AI gateway rejected the normalized request",
                status_code=exc.status_code,
                upstream_request_id=exc.upstream_request_id,
            ) from exc
        except (
            OmniRouteConnectionError,
            OmniRouteTimeoutError,
            OmniRouteServerError,
            OSError,
        ) as exc:
            raise AIUpstreamUnavailableError(
                "AI gateway is unavailable",
                status_code=getattr(exc, "status_code", None),
                upstream_request_id=getattr(exc, "upstream_request_id", None),
            ) from exc
        body = upstream.body
        try:
            choice = body["choices"][0]
            content = choice["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise AIUpstreamResponseError(
                "OmniRoute returned an invalid chat completion envelope",
                status_code=upstream.status_code,
                upstream_request_id=upstream.upstream_request_id,
            ) from exc
        if not isinstance(content, str):
            raise AIUpstreamResponseError(
                "OmniRoute returned non-text chat content",
                status_code=upstream.status_code,
                upstream_request_id=upstream.upstream_request_id,
            )

        usage = _normalize_usage(body.get("usage"))
        _verify_max_tokens(
            request, usage, upstream.status_code, upstream.upstream_request_id
        )
        return AIResponse(
            request_id=request.context.request_id,
            correlation_id=request.context.correlation_id,
            content=content,
            provider_gateway="omniroute",
            provider=_optional_string(body.get("provider")) or target.provider,
            model=_optional_string(body.get("model")) or target.model,
            usage=usage,
            latency_ms=0,
            fallback_used=bool(body.get("fallback_used", False)),
            upstream_request_id=upstream.upstream_request_id,
        )


def _normalize_usage(value: object) -> AIUsage | None:
    if not isinstance(value, dict):
        return None
    return AIUsage(
        prompt_tokens=_optional_non_negative_int(value.get("prompt_tokens")),
        completion_tokens=_optional_non_negative_int(value.get("completion_tokens")),
        total_tokens=_optional_non_negative_int(value.get("total_tokens")),
    )


def _verify_max_tokens(
    request: AIRequest,
    usage: AIUsage | None,
    status_code: int,
    upstream_request_id: str | None,
) -> None:
    """Falha fechada quando o upstream não comprova o hard cap solicitado."""
    if request.max_tokens is None:
        return
    completion_tokens = usage.completion_tokens if usage is not None else None
    if completion_tokens is None:
        raise AIUpstreamResponseError(
            "OmniRoute did not report completion usage required to verify max_tokens",
            status_code=status_code,
            upstream_request_id=upstream_request_id,
        )
    if completion_tokens > request.max_tokens:
        raise AIUpstreamResponseError(
            "OmniRoute exceeded the requested max_tokens hard limit",
            status_code=status_code,
            upstream_request_id=upstream_request_id,
        )


def _optional_non_negative_int(value: object) -> int | None:
    return value if isinstance(value, int) and value >= 0 else None


def _optional_string(value: object) -> str | None:
    return value if isinstance(value, str) and value else None
