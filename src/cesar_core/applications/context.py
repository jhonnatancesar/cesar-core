"""Contexto de identidade de uma execução, ponta a ponta.

Reúne, num único contrato, tudo que TASKs futuras (AI Gateway, Search
Gateway, OmniRoute) precisam para atribuir uma execução à aplicação, ao
serviço/processo chamador e à finalidade corretos -- para que esses
campos não fiquem espalhados depois como parâmetros soltos em cada
assinatura de função.

``correlation_id`` também cobre o papel de "trace_id": nesta V1 não
existem dois identificadores redundantes para a mesma correlação ponta
a ponta (decisão registrada em ADR 0007). ``request_id`` é distinto:
identifica esta requisição individual, nunca é reaproveitado de um
header (ver ``telemetry/request_id.py``), enquanto ``correlation_id`` se
propaga pela cadeia inteira.
"""

from pydantic import BaseModel, Field

from cesar_core.applications.identity import ApplicationId
from cesar_core.policy.purpose import Purpose


class ApplicationContext(BaseModel):
    """Identidade completa de uma execução no César Core.

    ``service`` é o serviço/processo chamador dentro da aplicação
    consumidora (ex.: ``collection_worker``, ``backend``, ``bot``) --
    não confundir com ``policy.ServiceKind`` (que descreve o gateway de
    domínio: ``ai``/``search``), um conceito ortogonal usado em
    ``Requirements``.
    """

    application_id: ApplicationId
    service: str = Field(min_length=1)
    purpose: Purpose
    request_id: str = Field(min_length=1)
    correlation_id: str = Field(min_length=1)
