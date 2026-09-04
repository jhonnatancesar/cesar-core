"""Dependências FastAPI compartilhadas pelas rotas do César Core.

``POST /v1/ai/generate`` e ``POST /v1/search`` usam uma variante request-aware
de ``get_application_context``: contexto confiável nos headers/dependencies e
payload funcional no body.

Na TASK-118E, ``application_id`` vem exclusivamente da credencial Bearer
resolvida por ``security/``. ``service`` e ``purpose`` continuam como metadata
declarada, validada pelas policies; nenhum header de application ID é usado.
"""

from collections.abc import AsyncIterator

from fastapi import Depends, Header, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from cesar_core.admin.storage import get_store
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
from cesar_core.applications.registry import list_applications
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
from cesar_core.security.authentication import ApplicationAuthenticator
from cesar_core.security.authorization import authorize_capability
from cesar_core.security.config import SecurityConfig
from cesar_core.security.quota import QuotaLimiter
from cesar_core.telemetry.correlation import CORRELATION_HEADER, resolve_correlation_id
from cesar_core.telemetry.request_id import new_request_id

QUOTA_LIMITER = QuotaLimiter()
APPLICATION_BEARER = HTTPBearer(auto_error=False, scheme_name="ApplicationBearer")


def get_correlation_id(
    x_correlation_id: str | None = Header(default=None, alias=CORRELATION_HEADER),
) -> str:
    """Reaproveita o correlation ID do header, ou gera um novo por requisição."""
    return resolve_correlation_id(x_correlation_id)


def get_application_context(
    application_id: ApplicationId,
    service: str,
    purpose: str,
    correlation_id: str | None,
) -> ApplicationContext:
    """Monta contexto interno com uma identidade já resolvida.

    ``request_id`` é sempre gerado aqui (nunca lido de header): é a
    identidade desta requisição individual, distinta do correlation ID
    que se propaga pela cadeia inteira.
    """
    return ApplicationContext(
        application_id=application_id,
        service=service,
        purpose=Purpose(value=purpose),
        request_id=new_request_id(),
        correlation_id=resolve_correlation_id(correlation_id),
    )


def get_authenticated_application(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(APPLICATION_BEARER),
) -> ApplicationId:
    """Autentica Bearer e registra a identidade confiável no request state."""
    authorization = None
    if credentials is not None:
        authorization = f"{credentials.scheme} {credentials.credentials}"
    application_id = ApplicationAuthenticator(SecurityConfig()).authenticate(
        authorization
    )
    request.state.application_id = application_id
    return application_id


def _authorized_context(
    request: Request,
    application_id: ApplicationId,
    service: str,
    purpose: str,
    capability: str,
) -> ApplicationContext:
    authorize_capability(application_id, capability)
    limit = get_store().get_quota(application_id.value, capability)
    if limit is None:
        from cesar_core.security.errors import ApplicationAccessDeniedError

        raise ApplicationAccessDeniedError("Application has no quota policy")
    QUOTA_LIMITER.check(application_id, capability, limit)
    context = ApplicationContext(
        application_id=application_id,
        service=service,
        purpose=Purpose(value=purpose),
        request_id=request.state.request_id,
        correlation_id=request.state.correlation_id,
    )
    request.state.service = context.service
    request.state.purpose = context.purpose.value
    return context


def get_ai_application_context(
    request: Request,
    application_id: ApplicationId = Depends(get_authenticated_application),
    x_service: str = Header(alias="X-Service"),
    x_purpose: str = Header(alias="X-Purpose"),
) -> ApplicationContext:
    return _authorized_context(request, application_id, x_service, x_purpose, "ai")


def get_search_application_context(
    request: Request,
    application_id: ApplicationId = Depends(get_authenticated_application),
    x_service: str = Header(alias="X-Service"),
    x_purpose: str = Header(alias="X-Purpose"),
) -> ApplicationContext:
    return _authorized_context(request, application_id, x_service, x_purpose, "search")


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
            for application in list_applications():
                if (
                    application.state.value != "active"
                    or "ai" not in application.allowed_capabilities
                ):
                    continue
                rules[(application.id, AI_WILDCARD_PURPOSE, service_class)] = (
                    AIModelTarget(
                        model=model,
                        provider=config.provider or None,
                        paid=config.model_is_paid,
                        enforces_max_tokens=config.model_enforces_max_tokens,
                        max_tokens_limit=config.max_tokens_limit,
                    )
                )

    try:
        omniroute_config = OmniRouteConfig().for_capability("ai")
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
            for application in list_applications():
                if (
                    application.state.value != "active"
                    or "search" not in application.allowed_capabilities
                ):
                    continue
                rules[(application.id, SEARCH_WILDCARD_PURPOSE, service_class)] = (
                    SearchProviderTarget(
                        provider=provider,
                        paid=config.provider_is_paid,
                        max_results_limit=config.max_results_limit,
                    )
                )
        documentation_provider = config.normalized_technical_documentation_provider
        if documentation_provider is not None:
            for application in list_applications():
                if (
                    application.state.value != "active"
                    or "search" not in application.allowed_capabilities
                ):
                    continue
                rules[
                    (application.id, TECHNICAL_DOCUMENTATION_PURPOSE, service_class)
                ] = SearchProviderTarget(
                    provider=documentation_provider,
                    paid=config.provider_is_paid,
                    max_results_limit=config.max_results_limit,
                )

    try:
        omniroute_config = OmniRouteConfig().for_capability("search")
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
