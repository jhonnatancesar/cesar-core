"""Erros normalizados do Central AI Gateway."""


class AIError(Exception):
    """Erro base da camada de domínio AI."""


class AIPolicyError(AIError):
    """A chamada não é permitida pela policy do César Core."""


class AIApplicationDeniedError(AIPolicyError):
    """A aplicação não está ativa para usar AI."""


class AINotConfiguredError(AIPolicyError):
    """Não há alvo AI configurado para application/purpose/class."""


class AICostPolicyDeniedError(AIPolicyError):
    """O alvo configurado viola a política de custo da chamada."""


class AIRequestLimitExceededError(AIPolicyError):
    """A chamada excede um limite definido pela policy."""


class AIMaxTokensUnsupportedError(AIPolicyError):
    """O alvo não comprova enforcement upstream de max_tokens."""


class AIUpstreamError(AIError):
    """Falha normalizada ao executar AI no gateway upstream."""

    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        upstream_request_id: str | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.upstream_request_id = upstream_request_id


class AIUpstreamAuthError(AIUpstreamError):
    """A credencial César Core -> gateway foi rejeitada."""


class AIUpstreamRequestError(AIUpstreamError):
    """O gateway rejeitou o payload produzido pelo adapter."""


class AIUpstreamUnavailableError(AIUpstreamError):
    """Gateway indisponível, timeout ou falha 5xx."""


class AIUpstreamResponseError(AIUpstreamError):
    """O gateway respondeu com um envelope incompatível."""
