"""Métricas agregadas e sem segredos do César Core."""

from collections import defaultdict
from threading import Lock

from cesar_core.ai.contracts import AIResponse
from cesar_core.applications.identity import ApplicationId
from cesar_core.search.contracts import SearchResponse


def _labels(**values: str) -> str:
    encoded = ",".join(f'{key}="{value}"' for key, value in sorted(values.items()))
    return "{" + encoded + "}"


class MetricsRegistry:
    """Registro em memória para o processo único, exportado em Prometheus text."""

    def __init__(self) -> None:
        self._values: dict[tuple[str, tuple[tuple[str, str], ...]], float] = defaultdict(float)
        self._lock = Lock()

    def increment(self, name: str, value: float = 1, **labels: str) -> None:
        key = (name, tuple(sorted(labels.items())))
        with self._lock:
            self._values[key] += value

    def observe_http(
        self,
        *,
        method: str,
        path: str,
        status: int,
        duration_ms: float,
        application_id: ApplicationId | None,
    ) -> None:
        application = application_id.value if application_id else "anonymous"
        labels = {
            "application": application,
            "method": method,
            "path": path,
            "status": str(status),
        }
        self.increment("cesar_core_http_requests_total", **labels)
        self.increment(
            "cesar_core_http_request_duration_ms_sum", duration_ms, **labels
        )

    def observe_ai(self, application_id: ApplicationId, response: AIResponse) -> None:
        labels = {"application": application_id.value}
        self.increment("cesar_core_ai_requests_total", **labels)
        if response.usage is not None:
            if response.usage.prompt_tokens is not None:
                self.increment(
                    "cesar_core_ai_tokens_total",
                    response.usage.prompt_tokens,
                    **labels,
                    type="prompt",
                )
            if response.usage.completion_tokens is not None:
                self.increment(
                    "cesar_core_ai_tokens_total",
                    response.usage.completion_tokens,
                    **labels,
                    type="completion",
                )
        if response.fallback_used:
            self.increment("cesar_core_ai_fallbacks_total", **labels)

    def observe_search(
        self, application_id: ApplicationId, response: SearchResponse
    ) -> None:
        labels = {"application": application_id.value}
        self.increment("cesar_core_search_requests_total", **labels)
        self.increment(
            "cesar_core_search_queries_total", response.usage.queries_used, **labels
        )
        self.increment(
            "cesar_core_search_cost_usd_total",
            response.usage.search_cost_usd,
            **labels,
        )
        if response.cached:
            self.increment("cesar_core_search_cache_hits_total", **labels)
        if response.fallback_used:
            self.increment("cesar_core_search_fallbacks_total", **labels)

    def render(self) -> str:
        with self._lock:
            items = sorted(self._values.items())
        lines = []
        for (name, label_items), value in items:
            label_text = _labels(**dict(label_items)) if label_items else ""
            lines.append(f"{name}{label_text} {value:g}")
        return "\n".join(lines) + ("\n" if lines else "")

    def reset(self) -> None:
        with self._lock:
            self._values.clear()


METRICS = MetricsRegistry()
