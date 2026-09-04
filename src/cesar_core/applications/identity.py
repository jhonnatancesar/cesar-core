"""Identidade das aplicações consumidoras do César Core."""

import re
from enum import StrEnum
from typing import ClassVar

from pydantic_core import core_schema


class ApplicationId(str):
    """ID canônico extensível; constantes históricas permanecem compatíveis."""

    PATTERN: ClassVar[re.Pattern[str]] = re.compile(r"^[a-z][a-z0-9_]{2,62}$")
    GG_OFERTA: ClassVar["ApplicationId"]
    CLAUDIAO: ClassVar["ApplicationId"]
    _CACHE: ClassVar[dict[str, "ApplicationId"]] = {}

    def __new__(cls, value: str):
        if not cls.PATTERN.fullmatch(value):
            raise ValueError("Invalid application id")
        if value not in cls._CACHE:
            cls._CACHE[value] = super().__new__(cls, value)
        return cls._CACHE[value]

    @property
    def value(self) -> str:
        return str(self)

    @classmethod
    def __get_pydantic_core_schema__(cls, _source, _handler):
        return core_schema.no_info_after_validator_function(
            cls, core_schema.str_schema(pattern=cls.PATTERN.pattern)
        )


class ApplicationState(StrEnum):
    """Estado de uma aplicação dentro do registry."""

    ACTIVE = "active"
    DISABLED = "disabled"
    RESERVED = "reserved"


ApplicationId.GG_OFERTA = ApplicationId("gg_oferta")
ApplicationId.CLAUDIAO = ApplicationId("claudiao")
