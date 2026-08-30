"""Requisitos de uma chamada de AI/Search ao César Core."""

from pydantic import BaseModel

from cesar_core.policy.cost_policy import CostPolicy
from cesar_core.policy.service_class import ServiceClass
from cesar_core.policy.service_kind import ServiceKind


class Requirements(BaseModel):
    """Contrato neutro do que uma aplicação exige de uma chamada.

    Não resolve provider/modelo: apenas descreve a política desejada
    (que gateway, qual tier, qual restrição de custo). A resolução real
    é responsabilidade de fases futuras (OmniRoute), fora do escopo da
    TASK-118A.

    ``purpose`` não é repetido aqui: ele já viaja em
    ``ApplicationContext`` (ver ADR 0007) -- duplicar o mesmo campo em
    dois contratos aninhados é exatamente a metadata espalhada que a
    TASK-118A pediu para eliminar.
    """

    service: ServiceKind
    service_class: ServiceClass
    cost_policy: CostPolicy
