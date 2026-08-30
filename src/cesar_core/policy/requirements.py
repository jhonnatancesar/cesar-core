"""Requisitos de execução de uma chamada de AI/Search ao César Core."""

from pydantic import BaseModel

from cesar_core.policy.cost_policy import CostPolicy
from cesar_core.policy.service_class import ServiceClass


class Requirements(BaseModel):
    """O que uma execução exige em termos de qualidade/custo.

    Responsabilidade final (ver ADR 0009): ``ApplicationContext`` é
    quem está chamando + por quê + identidade/tracing da chamada;
    ``Requirements`` é quais capacidades/qualidade/custo a execução
    exige. Por isso não há campo ``service`` aqui -- ele já existe em
    ``ApplicationContext`` (o serviço/processo chamador) e um segundo
    campo de mesmo nome, com significado diferente (qual gateway:
    ai/search), era exatamente a duplicação que a TASK-118A pediu para
    remover. Qual gateway (AI vs Search) já é dado pelo tipo do request
    (``AIRequest`` vs ``SearchRequest``), não precisa ser repetido aqui.

    ``structured_output``, ``reasoning``, ``vision``, ``tool_calling``
    (capacidades específicas) não foram adicionados nesta correção:
    ficam para quando uma TASK futura precisar deles de fato.
    """

    service_class: ServiceClass
    cost_policy: CostPolicy
