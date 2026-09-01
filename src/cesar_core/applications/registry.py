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
    ),
    ApplicationId.CLAUDIAO: Application(
        id=ApplicationId.CLAUDIAO,
        state=ApplicationState.RESERVED,
        display_name="Claudião",
    ),
}


def get_application(application_id: ApplicationId) -> Application:
    """Retorna a entrada do registry para a aplicação informada."""
    return REGISTRY[application_id]


def is_active(application_id: ApplicationId) -> bool:
    """Indica se a aplicação está com estado ACTIVE no registry."""
    return REGISTRY[application_id].state is ApplicationState.ACTIVE
