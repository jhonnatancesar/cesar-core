"""Erros normalizados de baixo nível do transporte OmniRoute.

Guardrail obrigatório do plano-mestre da TASK-118: 400/401/403 nunca
podem ser mascarados por uma cascata de fallback -- por isso cada
categoria de falha tem sua própria classe, em vez de um erro genérico
único que apagaria essa distinção para quem chama.
"""


class OmniRouteError(Exception):
    """Erro base de qualquer falha ao falar com o OmniRoute."""


class OmniRouteConnectionError(OmniRouteError):
    """Falha de rede: OmniRoute inalcançável (conexão recusada, DNS, etc.)."""


class OmniRouteTimeoutError(OmniRouteError):
    """A requisição excedeu o timeout configurado."""


class OmniRouteAuthError(OmniRouteError):
    """401/403 -- credencial ausente, inválida ou sem escopo suficiente."""

    def __init__(self, status_code: int, body: str, upstream_request_id: str | None = None) -> None:
        super().__init__(f"OmniRoute auth error: HTTP {status_code}")
        self.status_code = status_code
        self.body = body
        self.upstream_request_id = upstream_request_id


class OmniRouteClientError(OmniRouteError):
    """Outro 4xx -- requisição malformada do lado do chamador."""

    def __init__(self, status_code: int, body: str, upstream_request_id: str | None = None) -> None:
        super().__init__(f"OmniRoute client error: HTTP {status_code}")
        self.status_code = status_code
        self.body = body
        self.upstream_request_id = upstream_request_id


class OmniRouteServerError(OmniRouteError):
    """5xx -- erro interno do próprio OmniRoute."""

    def __init__(self, status_code: int, body: str, upstream_request_id: str | None = None) -> None:
        super().__init__(f"OmniRoute server error: HTTP {status_code}")
        self.status_code = status_code
        self.body = body
        self.upstream_request_id = upstream_request_id
