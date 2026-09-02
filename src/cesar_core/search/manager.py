"""Orquestra policy, provider e telemetria do Central Web Search Gateway."""

from time import perf_counter

from cesar_core.search.contracts import SearchRequest, SearchResponse
from cesar_core.search.policy import SearchPolicy
from cesar_core.search.provider import SearchProvider


class SearchManager:
    """Ponto central de execução de Search no César Core."""

    def __init__(self, provider: SearchProvider, policy: SearchPolicy) -> None:
        self._provider = provider
        self._policy = policy

    async def search(self, request: SearchRequest) -> SearchResponse:
        target = self._policy.resolve(request)
        started_at = perf_counter()
        response = await self._provider.search(request, target=target)
        latency_ms = (perf_counter() - started_at) * 1000
        return response.model_copy(update={"latency_ms": latency_ms})
