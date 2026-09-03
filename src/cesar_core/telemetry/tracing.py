"""Eventos estruturados de tracing/usage, sem payload ou credencial."""

import logging

from cesar_core.ai.contracts import AIResponse
from cesar_core.applications.context import ApplicationContext
from cesar_core.search.contracts import SearchResponse

LOGGER = logging.getLogger("cesar_core.telemetry")


def trace_http_completion(
    *,
    method: str,
    path: str,
    status: int,
    latency_ms: float,
    request_id: str,
    correlation_id: str,
    application: str = "anonymous",
    service: str | None = None,
    purpose: str | None = None,
) -> None:
    """Registra toda resposta sem incluir headers, body ou credenciais."""
    LOGGER.info(
        "http_request_completed",
        extra={
            "application": application,
            "service": service,
            "purpose": purpose,
            "request_id": request_id,
            "correlation_id": correlation_id,
            "method": method,
            "path": path,
            "status": status,
            "latency_ms": latency_ms,
        },
    )


def trace_ai_success(context: ApplicationContext, response: AIResponse) -> None:
    usage = response.usage
    LOGGER.info(
        "ai_request_completed",
        extra={
            "application": context.application_id.value,
            "service": context.service,
            "purpose": context.purpose.value,
            "request_id": context.request_id,
            "correlation_id": context.correlation_id,
            "provider": response.provider,
            "model": response.model,
            "latency_ms": response.latency_ms,
            "fallback": response.fallback_used,
            "prompt_tokens": usage.prompt_tokens if usage else None,
            "completion_tokens": usage.completion_tokens if usage else None,
        },
    )


def trace_search_success(context: ApplicationContext, response: SearchResponse) -> None:
    LOGGER.info(
        "search_request_completed",
        extra={
            "application": context.application_id.value,
            "service": context.service,
            "purpose": context.purpose.value,
            "request_id": context.request_id,
            "correlation_id": context.correlation_id,
            "provider": response.provider,
            "latency_ms": response.latency_ms,
            "fallback": response.fallback_used,
            "queries": response.usage.queries_used,
            "cost_usd": response.usage.search_cost_usd,
            "cached": response.cached,
        },
    )
