"""Contexto de requisição de uma aplicação consumidora."""

from pydantic import BaseModel, Field

from cesar_core.applications.identity import ApplicationId


class ApplicationContext(BaseModel):
    """Identifica, por requisição, qual aplicação está chamando o César Core.

    Carrega o correlation/request ID já neste momento de fundação (TASK-118A)
    para que rotas e futuros gateways (AI/Search/OmniRoute) não precisem de
    refatoração quando passarem a existir de fato.
    """

    application_id: ApplicationId
    correlation_id: str = Field(min_length=1)
