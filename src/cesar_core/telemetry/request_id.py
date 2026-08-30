"""Geração do request ID: identidade individual de cada requisição.

Ao contrário do correlation ID (``telemetry/correlation.py``), que se
propaga por toda a cadeia quando reenviado pelo chamador, o request ID
nunca é reaproveitado de um header: cada requisição ganha o seu, gerado
pelo próprio César Core.
"""

import uuid


def new_request_id() -> str:
    """Gera um novo request ID para a requisição atual."""
    return str(uuid.uuid4())
