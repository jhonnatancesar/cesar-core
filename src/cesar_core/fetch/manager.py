"""Orquestra policy, provider e telemetria do Central Web Fetch/Enrichment Gateway."""

from time import perf_counter

from cesar_core.fetch.contracts import FetchRequest, FetchResponse
from cesar_core.fetch.policy import FetchPolicy
from cesar_core.fetch.provider import FetchProvider


class FetchManager:
    """Ponto central de execução de Fetch/Enrichment no César Core."""

    def __init__(self, provider: FetchProvider, policy: FetchPolicy) -> None:
        self._provider = provider
        self._policy = policy

    async def fetch(self, request: FetchRequest) -> FetchResponse:
        target = self._policy.resolve(request)
        started_at = perf_counter()
        response = await self._provider.fetch(request, target=target)
        latency_ms = (perf_counter() - started_at) * 1000
        return response.model_copy(update={"latency_ms": latency_ms})
