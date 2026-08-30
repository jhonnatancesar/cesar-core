"""Finalidade declarada de uma requisição, em texto livre e neutro."""

from pydantic import BaseModel, Field


class Purpose(BaseModel):
    """Descreve por que uma aplicação está chamando AI/Search.

    Mantido como texto livre (em vez de um enum fechado) porque, nesta fase
    de fundação, o César Core ainda não define o catálogo de finalidades de
    negócio de cada aplicação consumidora — isso pertence às próximas TASKs.
    """

    value: str = Field(min_length=1)
