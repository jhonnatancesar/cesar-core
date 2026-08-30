"""Identidade das aplicações consumidoras do César Core."""

from enum import StrEnum


class ApplicationId(StrEnum):
    """Aplicações conhecidas pelo registry do César Core."""

    GG_OFERTA = "gg_oferta"
    CLAUDIAO = "claudiao"


class ApplicationState(StrEnum):
    """Estado de uma aplicação dentro do registry."""

    ACTIVE = "active"
    RESERVED = "reserved"
