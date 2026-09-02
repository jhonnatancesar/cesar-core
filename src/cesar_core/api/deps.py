"""Dependências FastAPI compartilhadas pelas rotas do César Core.

``POST /v1/ai/generate`` usa uma variante request-aware de
``get_application_context``. Search deverá adotar a mesma fronteira: contexto
confiável nos headers/dependencies e payload funcional no body.

``X-Application-Id`` NÃO é autoridade de segurança em produção -- é um
valor arbitrário que qualquer chamador pode declarar. Ele existe aqui
apenas como conveniência de teste/dev enquanto ``security/`` é uma fronteira
reservada, sem autenticação implementada. Na TASK-118E,
``application_id`` passa a vir da identidade autenticada resolvida por
``security/`` -- este header deixa de ser a fonte, sem exigir mudança
no contrato de ``ApplicationContext`` (ver ADR 0010).
"""

from collections.abc import AsyncIterator

from fastapi import Header, Request

from cesar_core.ai.config import AIConfig
from cesar_core.ai.contracts import AIRequest, AIResponse
from cesar_core.ai.errors import AIUpstreamUnavailableError
from cesar_core.ai.manager import AIManager
from cesar_core.ai.policy import WILDCARD_PURPOSE, AIModelTarget, AIPolicy, PolicyKey
from cesar_core.ai.providers.omniroute import OmniRouteAIProvider
from cesar_core.applications.context import ApplicationContext
from cesar_core.applications.identity import ApplicationId
from cesar_core.omniroute.client import OmniRouteClient
from cesar_core.omniroute.config import OmniRouteConfig
from cesar_core.policy.purpose import Purpose
from cesar_core.policy.service_class import ServiceClass
from cesar_core.telemetry.correlation import CORRELATION_HEADER, resolve_correlation_id
from cesar_core.telemetry.request_id import new_request_id


def get_correlation_id(
    x_correlation_id: str | None = Header(default=None, alias=CORRELATION_HEADER),
) -> str:
    """Reaproveita o correlation ID do header, ou gera um novo por requisição."""
    return resolve_correlation_id(x_correlation_id)


def get_application_context(
    x_application_id: ApplicationId = Header(alias="X-Application-Id"),
    x_service: str = Header(alias="X-Service"),
    x_purpose: str = Header(alias="X-Purpose"),
    x_correlation_id: str | None = Header(default=None, alias=CORRELATION_HEADER),
) -> ApplicationContext:
    """Monta o contexto da aplicação chamadora a partir dos headers da requisição.

    ``request_id`` é sempre gerado aqui (nunca lido de header): é a
    identidade desta requisição individual, distinta do correlation ID
    que se propaga pela cadeia inteira.
    """
    return ApplicationContext(
        application_id=x_application_id,
        service=x_service,
        purpose=Purpose(value=x_purpose),
        request_id=new_request_id(),
        correlation_id=resolve_correlation_id(x_correlation_id),
    )


def get_request_application_context(
    request: Request,
    x_application_id: ApplicationId = Header(alias="X-Application-Id"),
    x_service: str = Header(alias="X-Service"),
    x_purpose: str = Header(alias="X-Purpose"),
) -> ApplicationContext:
    """Monta o contexto usando o correlation ID já resolvido pelo middleware."""
    return get_application_context(
        x_application_id,
        x_service,
        x_purpose,
        request.state.correlation_id,
    )


async def get_ai_manager() -> AsyncIterator[AIManager]:
    """Constrói o runtime AI configurado por variáveis de ambiente."""
    config = AIConfig()
    if not config.is_configured:
        yield AIManager(_UnavailableAIProvider(), AIPolicy({}))
        return

    rules: dict[PolicyKey, AIModelTarget] = {}
    for service_class in ServiceClass:
        model = config.model_for(service_class)
        if model is not None:
            rules[(ApplicationId.GG_OFERTA, WILDCARD_PURPOSE, service_class)] = (
                AIModelTarget(
                    model=model,
                    provider=config.provider or None,
                    paid=config.model_is_paid,
                    enforces_max_tokens=config.model_enforces_max_tokens,
                    max_tokens_limit=config.max_tokens_limit,
                )
            )

    try:
        omniroute_config = OmniRouteConfig()
    except ValueError:
        yield AIManager(
            _UnavailableAIProvider(
                AIUpstreamUnavailableError("OmniRoute is not configured")
            ),
            AIPolicy(rules),
        )
        return

    client = OmniRouteClient(omniroute_config)
    try:
        yield AIManager(OmniRouteAIProvider(client), AIPolicy(rules))
    finally:
        await client.aclose()


class _UnavailableAIProvider:
    """Provider sentinela para produzir erros públicos normalizados."""

    def __init__(self, error: Exception | None = None) -> None:
        self._error = error or AIUpstreamUnavailableError(
            "Central AI Gateway is not configured"
        )

    async def complete(
        self, request: AIRequest, *, target: AIModelTarget
    ) -> AIResponse:
        raise self._error
