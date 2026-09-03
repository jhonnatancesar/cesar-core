import logging

from cesar_core.ai.contracts import AIResponse, AIUsage
from cesar_core.applications.context import ApplicationContext
from cesar_core.applications.identity import ApplicationId
from cesar_core.policy.purpose import Purpose
from cesar_core.search.contracts import SearchResponse, SearchUsage
from cesar_core.telemetry.tracing import (
    trace_ai_success,
    trace_http_completion,
    trace_search_success,
)


def _context() -> ApplicationContext:
    return ApplicationContext(
        application_id=ApplicationId.GG_OFERTA,
        service="backend",
        purpose=Purpose(value="market_research"),
        request_id="req-1",
        correlation_id="corr-1",
    )


def test_tracing_emits_operational_ai_fields_without_payload(caplog) -> None:
    response = AIResponse(
        request_id="req-1",
        correlation_id="corr-1",
        content="sensitive output",
        provider_gateway="omniroute",
        provider="free-provider",
        model="free-model",
        usage=AIUsage(prompt_tokens=2, completion_tokens=3, total_tokens=5),
        latency_ms=4,
    )
    with caplog.at_level(logging.INFO, logger="cesar_core.telemetry"):
        trace_ai_success(_context(), response)
    record = caplog.records[-1]
    assert record.application == "gg_oferta"
    assert record.service == "backend"
    assert record.purpose == "market_research"
    assert record.completion_tokens == 3
    assert "sensitive output" not in record.getMessage()


def test_tracing_emits_search_usage_and_cache(caplog) -> None:
    response = SearchResponse(
        request_id="req-1",
        correlation_id="corr-1",
        provider_gateway="omniroute",
        provider="context7",
        usage=SearchUsage(queries_used=1, search_cost_usd=0),
        latency_ms=4,
        cached=True,
    )
    with caplog.at_level(logging.INFO, logger="cesar_core.telemetry"):
        trace_search_success(_context(), response)
    record = caplog.records[-1]
    assert record.provider == "context7"
    assert record.queries == 1
    assert record.cached is True


def test_http_tracing_covers_failed_or_anonymous_requests(caplog) -> None:
    with caplog.at_level(logging.INFO, logger="cesar_core.telemetry"):
        trace_http_completion(
            method="POST",
            path="/v1/search",
            status=401,
            latency_ms=2,
            request_id="req",
            correlation_id="corr",
        )
    record = caplog.records[-1]
    assert record.application == "anonymous"
    assert record.status == 401
    assert record.path == "/v1/search"
