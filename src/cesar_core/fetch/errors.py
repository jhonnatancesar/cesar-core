"""Erros normalizados do Central Web Fetch/Enrichment Gateway."""


class FetchError(Exception):
    """Erro base da camada de domínio Fetch."""


class FetchPolicyError(FetchError):
    """O enriquecimento não é permitido pela policy do César Core."""


class FetchApplicationDeniedError(FetchPolicyError):
    """A aplicação não está ativa para usar Fetch."""


class FetchNotConfiguredError(FetchPolicyError):
    """Não há alvo Fetch configurado para application/purpose/class."""


class FetchCostPolicyDeniedError(FetchPolicyError):
    """O alvo configurado viola a política de custo da chamada."""


class FetchUpstreamError(FetchError):
    """Falha normalizada ao executar Fetch no gateway upstream."""

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


class FetchUpstreamAuthError(FetchUpstreamError):
    """A credencial César Core -> gateway foi rejeitada."""


class FetchUpstreamRequestError(FetchUpstreamError):
    """O gateway rejeitou o payload produzido pelo adapter."""


class FetchUpstreamUnavailableError(FetchUpstreamError):
    """Gateway indisponível, timeout ou falha 5xx."""


class FetchUpstreamResponseError(FetchUpstreamError):
    """O gateway respondeu com um envelope incompatível."""
