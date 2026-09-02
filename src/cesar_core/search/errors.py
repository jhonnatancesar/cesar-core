"""Erros normalizados do Central Web Search Gateway."""


class SearchError(Exception):
    """Erro base da camada de domínio Search."""


class SearchPolicyError(SearchError):
    """A busca não é permitida pela policy do César Core."""


class SearchApplicationDeniedError(SearchPolicyError):
    """A aplicação não está ativa para usar Search."""


class SearchNotConfiguredError(SearchPolicyError):
    """Não há alvo Search configurado para application/purpose/class."""


class SearchCostPolicyDeniedError(SearchPolicyError):
    """O alvo configurado viola a política de custo da chamada."""


class SearchRequestLimitExceededError(SearchPolicyError):
    """A chamada excede um limite definido pela policy."""


class SearchUpstreamError(SearchError):
    """Falha normalizada ao executar Search no gateway upstream."""

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


class SearchUpstreamAuthError(SearchUpstreamError):
    """A credencial César Core -> gateway foi rejeitada."""


class SearchUpstreamRequestError(SearchUpstreamError):
    """O gateway rejeitou o payload produzido pelo adapter."""


class SearchUpstreamUnavailableError(SearchUpstreamError):
    """Gateway indisponível, timeout ou falha 5xx."""


class SearchUpstreamResponseError(SearchUpstreamError):
    """O gateway respondeu com um envelope incompatível."""
