"""Adapter do contrato Search do César Core para o transporte OmniRoute."""

from typing import Any

from pydantic import ValidationError

from cesar_core.omniroute.client import OmniRouteClient
from cesar_core.omniroute.errors import (
    OmniRouteAuthError,
    OmniRouteClientError,
    OmniRouteConnectionError,
    OmniRouteServerError,
    OmniRouteTimeoutError,
)
from cesar_core.search.contracts import (
    SearchRequest,
    SearchResponse,
    SearchResult,
    SearchUpstreamIssue,
    SearchUsage,
)
from cesar_core.search.errors import (
    SearchUpstreamAuthError,
    SearchUpstreamRequestError,
    SearchUpstreamResponseError,
    SearchUpstreamUnavailableError,
)
from cesar_core.search.policy import SearchProviderTarget


class OmniRouteSearchProvider:
    """Traduz requests/responses de Search sem vazar o payload upstream."""

    def __init__(self, client: OmniRouteClient) -> None:
        self._client = client

    async def search(
        self, request: SearchRequest, *, target: SearchProviderTarget
    ) -> SearchResponse:
        payload: dict[str, Any] = {
            "query": request.query,
            "provider": target.provider,
            "search_type": "web",
            "max_results": request.max_results,
        }
        try:
            upstream = await self._client.search(
                payload, correlation_id=request.context.correlation_id
            )
        except OmniRouteAuthError as exc:
            raise SearchUpstreamAuthError(
                "Search gateway authentication failed",
                status_code=exc.status_code,
                upstream_request_id=exc.upstream_request_id,
            ) from exc
        except OmniRouteClientError as exc:
            raise SearchUpstreamRequestError(
                "Search gateway rejected the normalized request",
                status_code=exc.status_code,
                upstream_request_id=exc.upstream_request_id,
            ) from exc
        except (
            OmniRouteConnectionError,
            OmniRouteTimeoutError,
            OmniRouteServerError,
            OSError,
        ) as exc:
            raise SearchUpstreamUnavailableError(
                "Search gateway is unavailable",
                status_code=getattr(exc, "status_code", None),
                upstream_request_id=getattr(exc, "upstream_request_id", None),
            ) from exc

        body = upstream.body
        try:
            provider = _required_string(body.get("provider"))
            if body.get("query") != request.query:
                raise ValueError("query mismatch")
            raw_results = body["results"]
            if not isinstance(raw_results, list):
                raise TypeError("results must be a list")
            results = [_normalize_result(value) for value in raw_results]
            usage = _normalize_usage(body["usage"])
            metrics = body.get("metrics")
            total_results = (
                _optional_non_negative_int(metrics.get("total_results_available"))
                if isinstance(metrics, dict)
                else None
            )
            issues = _normalize_issues(body.get("errors", []))
        except (KeyError, TypeError, ValueError, ValidationError) as exc:
            raise SearchUpstreamResponseError(
                "OmniRoute returned an invalid search envelope",
                status_code=upstream.status_code,
                upstream_request_id=upstream.upstream_request_id,
            ) from exc

        return SearchResponse(
            request_id=request.context.request_id,
            correlation_id=request.context.correlation_id,
            results=results,
            provider_gateway="omniroute",
            provider=provider,
            usage=usage,
            latency_ms=0,
            total_results_available=total_results,
            cached=bool(body.get("cached", False)),
            fallback_used=provider != target.provider,
            upstream_request_id=upstream.upstream_request_id,
            upstream_issues=issues,
        )


def _normalize_result(value: object) -> SearchResult:
    if not isinstance(value, dict):
        raise TypeError("search result must be an object")
    return SearchResult(
        title=_required_string(value.get("title")),
        url=_required_string(value.get("url")),
        snippet=value.get("snippet") if isinstance(value.get("snippet"), str) else "",
        position=_optional_positive_int(value.get("position")),
        score=_optional_non_negative_number(value.get("score")),
        published_at=(
            value.get("published_at")
            if isinstance(value.get("published_at"), str)
            else None
        ),
    )


def _normalize_usage(value: object) -> SearchUsage:
    if not isinstance(value, dict):
        raise TypeError("usage must be an object")
    queries_used = value.get("queries_used")
    search_cost_usd = value.get("search_cost_usd")
    if not isinstance(queries_used, int) or queries_used < 0:
        raise ValueError("invalid queries_used")
    if (
        not isinstance(search_cost_usd, (int, float))
        or isinstance(search_cost_usd, bool)
        or search_cost_usd < 0
    ):
        raise ValueError("invalid search_cost_usd")
    return SearchUsage(
        queries_used=queries_used,
        search_cost_usd=float(search_cost_usd),
        llm_tokens=_optional_non_negative_int(value.get("llm_tokens")),
    )


def _normalize_issues(value: object) -> list[SearchUpstreamIssue]:
    if not isinstance(value, list):
        raise TypeError("errors must be a list")
    issues: list[SearchUpstreamIssue] = []
    for item in value:
        if not isinstance(item, dict):
            raise TypeError("search issue must be an object")
        issues.append(
            SearchUpstreamIssue(
                provider=_required_string(item.get("provider")),
                code=_required_string(item.get("code")),
                message=_required_string(item.get("message")),
            )
        )
    return issues


def _required_string(value: object) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError("required string is missing")
    return value


def _optional_non_negative_int(value: object) -> int | None:
    return (
        value
        if isinstance(value, int) and not isinstance(value, bool) and value >= 0
        else None
    )


def _optional_positive_int(value: object) -> int | None:
    return (
        value
        if isinstance(value, int) and not isinstance(value, bool) and value >= 1
        else None
    )


def _optional_non_negative_number(value: object) -> float | None:
    if isinstance(value, (int, float)) and not isinstance(value, bool) and value >= 0:
        return float(value)
    return None
