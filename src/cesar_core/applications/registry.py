"""Registry estático das aplicações conhecidas pelo César Core.

GG Oferta é o primeiro consumidor registrado como ativo. Claudião permanece
reservado: sua identidade existe para permitir ativação sem refatorar o
contrato, mas não há integração funcional para ele.
"""

from cesar_core.applications.identity import ApplicationId, ApplicationState
from cesar_core.applications.models import Application

REGISTRY: dict[ApplicationId, Application] = {
    ApplicationId.GG_OFERTA: Application(
        id=ApplicationId.GG_OFERTA,
        state=ApplicationState.ACTIVE,
        display_name="GG Oferta",
        client_id="ggoferta-core-client",
        allowed_capabilities=frozenset({"ai", "search"}),
    ),
    ApplicationId.CLAUDIAO: Application(
        id=ApplicationId.CLAUDIAO,
        state=ApplicationState.RESERVED,
        display_name="Claudião",
        client_id="claudiao-core-client",
        allowed_capabilities=frozenset(),
    ),
}


def get_application(application_id: ApplicationId) -> Application:
    """Retorna a entrada do registry para a aplicação informada."""
    return REGISTRY[application_id]


def is_active(application_id: ApplicationId) -> bool:
    """Indica se a aplicação está com estado ACTIVE no registry."""
    return REGISTRY[application_id].state is ApplicationState.ACTIVE


def allows_capability(application_id: ApplicationId, capability: str) -> bool:
    """Aplica privilégio mínimo do registry antes do domínio/upstream."""
    application = get_application(application_id)
    return is_active(application_id) and capability in application.allowed_capabilities
