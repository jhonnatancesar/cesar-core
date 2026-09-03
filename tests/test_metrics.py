from cesar_core.ai.contracts import AIResponse, AIUsage
from cesar_core.applications.identity import ApplicationId
from cesar_core.search.contracts import SearchResponse, SearchUsage
from cesar_core.telemetry.metrics import MetricsRegistry


def test_metrics_render_ai_search_http_usage_and_flags() -> None:
    registry = MetricsRegistry()
    registry.observe_http(
        method="POST",
        path="/v1/ai/generate",
        status=200,
        duration_ms=12.5,
        application_id=ApplicationId.GG_OFERTA,
    )
    registry.observe_ai(
        ApplicationId.GG_OFERTA,
        AIResponse(
            request_id="req",
            correlation_id="corr",
            content="ok",
            provider_gateway="omniroute",
            model="model",
            usage=AIUsage(prompt_tokens=2, completion_tokens=3, total_tokens=5),
            latency_ms=10,
            fallback_used=True,
        ),
    )
    registry.observe_search(
        ApplicationId.GG_OFERTA,
        SearchResponse(
            request_id="req",
            correlation_id="corr",
            provider_gateway="omniroute",
            provider="context7",
            usage=SearchUsage(queries_used=1, search_cost_usd=0),
            latency_ms=5,
            cached=True,
            fallback_used=True,
        ),
    )
    rendered = registry.render()
    assert "cesar_core_http_requests_total" in rendered
    assert 'type="prompt"} 2' in rendered
    assert 'type="completion"} 3' in rendered
    assert "cesar_core_ai_fallbacks_total" in rendered
    assert "cesar_core_search_cache_hits_total" in rendered
    assert "cesar_core_search_fallbacks_total" in rendered
    registry.reset()
    assert registry.render() == ""
