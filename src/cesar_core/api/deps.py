"""Dependências FastAPI compartilhadas pelas rotas do César Core.

Nenhuma rota de AI/Search existe ainda nesta TASK, então
``get_application_context`` não é usada por um endpoint concreto por
enquanto — mas o contrato precisa existir pronto para quando essas rotas
chegarem, sem exigir refatoração (item 13 da TASK-118A).
"""

from fastapi import Header

from cesar_core.applications.context import ApplicationContext
from cesar_core.applications.identity import ApplicationId
from cesar_core.telemetry.correlation import CORRELATION_HEADER, resolve_correlation_id


def get_correlation_id(
    x_correlation_id: str | None = Header(default=None, alias=CORRELATION_HEADER),
) -> str:
    """Reaproveita o correlation ID do header, ou gera um novo por requisição."""
    return resolve_correlation_id(x_correlation_id)


def get_application_context(
    x_application_id: ApplicationId = Header(alias="X-Application-Id"),
    correlation_id: str = Header(default=None, alias=CORRELATION_HEADER),
) -> ApplicationContext:
    """Monta o contexto da aplicação chamadora a partir dos headers da requisição."""
    return ApplicationContext(
        application_id=x_application_id,
        correlation_id=resolve_correlation_id(correlation_id),
    )
