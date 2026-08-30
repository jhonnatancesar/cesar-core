"""Contexto de identidade de uma execução, ponta a ponta.

Reúne, num único contrato, tudo que TASKs futuras (AI Gateway, Search
Gateway, OmniRoute) precisam para atribuir uma execução à aplicação, ao
serviço/processo chamador e à finalidade corretos -- para que esses
campos não fiquem espalhados depois como parâmetros soltos em cada
assinatura de função.

Responsabilidade final (ver ADR 0009): ``ApplicationContext`` é quem
está chamando + por quê + identidade/tracing da chamada.
``policy.Requirements`` é quais capacidades/qualidade/custo a execução
exige -- por isso não há campo de "qual gateway" aqui nem em
``Requirements``: isso já é dado pelo tipo do request (``AIRequest`` vs
``SearchRequest``, ver ADR 0010).

``request_id`` = ID próprio da execução recebida pelo César Core: nunca
é reaproveitado de um header, é sempre gerado pelo próprio Core (ver
``telemetry/request_id.py``). ``correlation_id`` = ID ponta a ponta,
preservado quando fornecido pelo chamador e gerado quando ausente (ver
``telemetry/correlation.py``). Não existe ``trace_id`` separado nesta V1
-- ``correlation_id`` cobre esse papel (ADR 0007).
"""

from pydantic import BaseModel, Field

from cesar_core.applications.identity import ApplicationId
from cesar_core.policy.purpose import Purpose


class ApplicationContext(BaseModel):
    """Identidade completa de uma execução no César Core.

    ``service`` é o serviço/processo chamador dentro da aplicação
    consumidora (ex.: ``collection_worker``, ``backend``, ``bot``).

    Construída de forma confiável pelo próprio César Core -- em 118A a
    partir de headers (``api/deps.py``), e futuramente a partir da
    identidade autenticada (TASK-118E, ver ADR 0010) -- nunca a partir de
    um campo arbitrário dentro do corpo de uma requisição HTTP pública.
    """

    application_id: ApplicationId
    service: str = Field(min_length=1)
    purpose: Purpose
    request_id: str = Field(min_length=1)
    correlation_id: str = Field(min_length=1)
