"""Adapter do contrato AI do César Core para o transporte OmniRoute."""

import json
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
            "messages": [
                message.model_dump(mode="json") for message in request.messages
            ],
        }
        if target.provider is not None:
            payload["provider"] = target.provider
        if request.max_tokens is not None:
            payload["max_tokens"] = request.max_tokens
        if request.require_search_grounding:
            payload["tools"] = [{"type": "web_search", "search_context_size": "low"}]

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
        grounding_sources: tuple[str, ...] = ()
        grounding_usage: AIUsage | None = None
        if request.require_search_grounding:
            grounding_usage = _normalize_usage(upstream.body.get("usage"))
            payload, grounding_sources = _grounded_followup_payload(
                request, target, upstream.body, grounding_usage
            )
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

        usage = _sum_usage(grounding_usage, _normalize_usage(body.get("usage")))
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
            grounding_requested=request.require_search_grounding,
            grounding_performed=request.require_search_grounding,
            grounding_sources=grounding_sources,
        )


def _grounded_followup_payload(
    request: AIRequest,
    target: AIModelTarget,
    body: dict[str, Any],
    usage: AIUsage | None,
) -> tuple[dict[str, Any], tuple[str, ...]]:
    try:
        assistant = body["choices"][0]["message"]
        tool_calls = assistant["tool_calls"]
        tool_results = body["tool_results"]
    except (KeyError, IndexError, TypeError) as exc:
        raise AIUpstreamResponseError(
            "OmniRoute did not execute required Web grounding"
        ) from exc
    if not isinstance(tool_calls, list) or not tool_calls or not isinstance(tool_results, list):
        raise AIUpstreamResponseError("OmniRoute did not execute required Web grounding")

    tool_call_ids = {
        call.get("id")
        for call in tool_calls
        if isinstance(call, dict)
        and isinstance(call.get("function"), dict)
        and call["function"].get("name") == "omniroute_web_search"
    }
    if None in tool_call_ids or not tool_call_ids:
        raise AIUpstreamResponseError("OmniRoute returned an invalid grounding tool call")

    sources: list[str] = []
    tool_messages: list[dict[str, Any]] = []
    for result in tool_results:
        if (
            not isinstance(result, dict)
            or result.get("tool_call_id") not in tool_call_ids
            or not isinstance(result.get("output"), str)
        ):
            raise AIUpstreamResponseError("OmniRoute returned invalid grounding evidence")
        try:
            evidence = json.loads(result["output"])
            results = evidence["results"]
        except (json.JSONDecodeError, KeyError, TypeError) as exc:
            raise AIUpstreamResponseError("OmniRoute returned invalid grounding evidence") from exc
        if not evidence.get("success") or not isinstance(results, list) or not results:
            raise AIUpstreamResponseError("OmniRoute returned no grounding evidence")
        for item in results:
            if isinstance(item, dict) and isinstance(item.get("url"), str) and item["url"]:
                sources.append(item["url"])
        tool_messages.append(
            {
                "role": "tool",
                "tool_call_id": result.get("tool_call_id"),
                "content": result["output"],
            }
        )
    if not sources:
        raise AIUpstreamResponseError("OmniRoute returned no grounding sources")

    completion_used = usage.completion_tokens if usage else None
    if request.max_tokens is not None and completion_used is None:
        raise AIUpstreamResponseError("OmniRoute did not report grounding usage")
    remaining = request.max_tokens - completion_used if request.max_tokens is not None else None
    if remaining is not None and remaining < 1:
        raise AIUpstreamResponseError("Grounding consumed the completion-token budget")
    payload: dict[str, Any] = {
        "model": target.model,
        "messages": [
            *[message.model_dump(mode="json") for message in request.messages],
            {"role": "assistant", "content": assistant.get("content"), "tool_calls": tool_calls},
            *tool_messages,
        ],
    }
    if target.provider is not None:
        payload["provider"] = target.provider
    if remaining is not None:
        payload["max_tokens"] = remaining
    return payload, tuple(dict.fromkeys(sources))


def _sum_usage(first: AIUsage | None, second: AIUsage | None) -> AIUsage | None:
    if first is None:
        return second
    if second is None:
        return first

    def add(left: int | None, right: int | None) -> int | None:
        return left + right if left is not None and right is not None else None

    return AIUsage(
        prompt_tokens=add(first.prompt_tokens, second.prompt_tokens),
        completion_tokens=add(first.completion_tokens, second.completion_tokens),
        total_tokens=add(first.total_tokens, second.total_tokens),
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
