"""Requisitos de uma chamada de AI/Search ao César Core."""

from pydantic import BaseModel

from cesar_core.policy.cost_policy import CostPolicy
from cesar_core.policy.purpose import Purpose
from cesar_core.policy.service_class import ServiceClass
from cesar_core.policy.service_kind import ServiceKind


class Requirements(BaseModel):
    """Contrato neutro do que uma aplicação exige de uma chamada.

    Não resolve provider/modelo: apenas descreve a intenção da aplicação
    consumidora. A resolução real é responsabilidade de fases futuras
    (OmniRoute), fora do escopo da TASK-118A.
    """

    service: ServiceKind
    service_class: ServiceClass
    cost_policy: CostPolicy
    purpose: Purpose
