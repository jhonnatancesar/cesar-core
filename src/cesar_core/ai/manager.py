"""Orquestra policy, provider e telemetria do Central AI Gateway."""

from time import perf_counter

from cesar_core.ai.contracts import AIRequest, AIResponse
from cesar_core.ai.policy import AIPolicy
from cesar_core.ai.provider import AIProvider


class AIManager:
    """Ponto central de execução de AI no César Core."""

    def __init__(self, provider: AIProvider, policy: AIPolicy) -> None:
        self._provider = provider
        self._policy = policy

    async def generate(self, request: AIRequest) -> AIResponse:
        target = self._policy.resolve(request)
        started_at = perf_counter()
        response = await self._provider.complete(request, target=target)

        latency_ms = (perf_counter() - started_at) * 1000
        return response.model_copy(update={"latency_ms": latency_ms})
