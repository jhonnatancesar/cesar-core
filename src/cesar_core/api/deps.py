"""Dependências FastAPI compartilhadas pelas rotas do César Core.

``POST /v1/ai/generate`` e ``POST /v1/search`` usam uma variante request-aware
de ``get_application_context``: contexto confiável nos headers/dependencies e
payload funcional no body.

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
from cesar_core.ai.policy import (
    WILDCARD_PURPOSE as AI_WILDCARD_PURPOSE,
)
from cesar_core.ai.policy import AIModelTarget, AIPolicy, PolicyKey
from cesar_core.ai.providers.omniroute import OmniRouteAIProvider
from cesar_core.applications.context import ApplicationContext
from cesar_core.applications.identity import ApplicationId
from cesar_core.omniroute.client import OmniRouteClient
from cesar_core.omniroute.config import OmniRouteConfig
from cesar_core.policy.purpose import Purpose
from cesar_core.policy.service_class import ServiceClass
from cesar_core.search.config import TECHNICAL_DOCUMENTATION_PURPOSE, SearchConfig
from cesar_core.search.contracts import SearchRequest, SearchResponse
from cesar_core.search.errors import SearchUpstreamUnavailableError
from cesar_core.search.manager import SearchManager
from cesar_core.search.policy import (
    WILDCARD_PURPOSE as SEARCH_WILDCARD_PURPOSE,
)
from cesar_core.search.policy import PolicyKey as SearchPolicyKey
from cesar_core.search.policy import (
    SearchPolicy,
    SearchProviderTarget,
)
from cesar_core.search.providers.omniroute import OmniRouteSearchProvider
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
            rules[(ApplicationId.GG_OFERTA, AI_WILDCARD_PURPOSE, service_class)] = (
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


async def get_search_manager() -> AsyncIterator[SearchManager]:
    """Constrói o runtime Search configurado por variáveis de ambiente."""
    config = SearchConfig()
    if not config.is_configured:
        yield SearchManager(_UnavailableSearchProvider(), SearchPolicy({}))
        return

    rules: dict[SearchPolicyKey, SearchProviderTarget] = {}
    for service_class in ServiceClass:
        provider = config.provider_for(service_class)
        if provider is not None:
            rules[
                (
                    ApplicationId.GG_OFERTA,
                    SEARCH_WILDCARD_PURPOSE,
                    service_class,
                )
            ] = SearchProviderTarget(
                provider=provider,
                paid=config.provider_is_paid,
                max_results_limit=config.max_results_limit,
            )
        documentation_provider = config.normalized_technical_documentation_provider
        if documentation_provider is not None:
            rules[
                (
                    ApplicationId.GG_OFERTA,
                    TECHNICAL_DOCUMENTATION_PURPOSE,
                    service_class,
                )
            ] = SearchProviderTarget(
                provider=documentation_provider,
                paid=config.provider_is_paid,
                max_results_limit=config.max_results_limit,
            )

    try:
        omniroute_config = OmniRouteConfig()
    except ValueError:
        yield SearchManager(
            _UnavailableSearchProvider(
                SearchUpstreamUnavailableError("OmniRoute is not configured")
            ),
            SearchPolicy(rules),
        )
        return

    client = OmniRouteClient(omniroute_config)
    try:
        yield SearchManager(OmniRouteSearchProvider(client), SearchPolicy(rules))
    finally:
        await client.aclose()


class _UnavailableSearchProvider:
    """Provider sentinela para produzir erros públicos normalizados."""

    def __init__(self, error: Exception | None = None) -> None:
        self._error = error or SearchUpstreamUnavailableError(
            "Central Web Search Gateway is not configured"
        )

    async def search(
        self, request: SearchRequest, *, target: SearchProviderTarget
    ) -> SearchResponse:
        raise self._error
