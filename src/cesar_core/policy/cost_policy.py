"""Política de custo aplicável a uma chamada de AI/Search."""

from enum import StrEnum


class CostPolicy(StrEnum):
    """Restrição de custo que a aplicação consumidora aceita para a chamada."""

    FREE_ONLY = "free_only"
    FREE_PREFERRED = "free_preferred"
    PAID_ALLOWED = "paid_allowed"
