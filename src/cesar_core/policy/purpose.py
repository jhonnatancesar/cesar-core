"""Finalidade declarada de uma requisição, em texto livre e neutro."""

from pydantic import BaseModel, Field


class Purpose(BaseModel):
    """Descreve por que uma aplicação está chamando AI/Search.

    Mantido como texto livre (em vez de um enum fechado) porque o César Core
    não define um catálogo global de finalidades de negócio para as
    aplicações consumidoras.
    """

    value: str = Field(min_length=1)
