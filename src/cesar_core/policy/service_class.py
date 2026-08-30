"""Classe de serviço solicitada para uma chamada de AI/Search."""

from enum import StrEnum


class ServiceClass(StrEnum):
    """Nível de custo/qualidade desejado para atender a uma requisição."""

    ECONOMY = "economy"
    STANDARD = "standard"
    QUALITY = "quality"
