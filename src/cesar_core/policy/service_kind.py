"""Tipos de serviço que o César Core expõe a aplicações consumidoras."""

from enum import StrEnum


class ServiceKind(StrEnum):
    """Gateway de domínio visado por uma requisição."""

    AI = "ai"
    SEARCH = "search"
