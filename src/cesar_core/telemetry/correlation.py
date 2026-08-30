"""Preparação de correlation/request ID, usada por toda requisição HTTP."""

import uuid

CORRELATION_HEADER = "X-Correlation-Id"


def new_correlation_id() -> str:
    """Gera um novo correlation ID para requisições sem um informado."""
    return str(uuid.uuid4())


def resolve_correlation_id(header_value: str | None) -> str:
    """Reaproveita o correlation ID recebido, ou gera um novo."""
    if header_value:
        return header_value
    return new_correlation_id()
