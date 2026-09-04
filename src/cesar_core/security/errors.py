"""Erros da fronteira de segurança do César Core."""


class SecurityError(Exception):
    """Erro base seguro para exposição pela API."""

    code = "security_error"
    status_code = 500


class AuthenticationNotConfiguredError(SecurityError):
    code = "authentication_not_configured"
    status_code = 503


class InvalidCredentialError(SecurityError):
    code = "invalid_credential"
    status_code = 401


class ApplicationAccessDeniedError(SecurityError):
    code = "application_access_denied"
    status_code = 403


class QuotaExceededError(SecurityError):
    code = "quota_exceeded"
    status_code = 429

    def __init__(self, retry_after_seconds: int) -> None:
        super().__init__("Application request quota exceeded")
        self.retry_after_seconds = retry_after_seconds


class QuotaStoreUnavailableError(SecurityError):
    code = "quota_store_unavailable"
    status_code = 503

    def __init__(self) -> None:
        super().__init__("Application quota storage unavailable")


class QuotaStoreMisconfiguredError(QuotaStoreUnavailableError):
    code = "quota_store_misconfigured"

    def __init__(self) -> None:
        SecurityError.__init__(self, "Application quota storage durability requirements not met")
