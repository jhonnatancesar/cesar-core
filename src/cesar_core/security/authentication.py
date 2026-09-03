"""Autenticação Bearer de aplicações consumidoras."""

from cesar_core.applications.identity import ApplicationId
from cesar_core.applications.registry import get_application, is_active
from cesar_core.security.config import SecurityConfig
from cesar_core.security.credentials import credential_matches, read_secret
from cesar_core.security.errors import (
    ApplicationAccessDeniedError,
    AuthenticationNotConfiguredError,
    InvalidCredentialError,
)


class ApplicationAuthenticator:
    """Resolve a aplicação a partir de uma credencial, nunca de headers de ID."""

    def __init__(self, config: SecurityConfig) -> None:
        self._config = config

    def authenticate(self, authorization: str | None) -> ApplicationId:
        if not self._config.is_configured:
            raise AuthenticationNotConfiguredError(
                "Application authentication is not configured"
            )
        if authorization is None or not authorization.startswith("Bearer "):
            raise InvalidCredentialError("A valid Bearer credential is required")
        candidate = authorization.removeprefix("Bearer ").strip()
        if not candidate:
            raise InvalidCredentialError("A valid Bearer credential is required")

        path = self._config.gg_oferta_api_key_file
        assert path is not None
        try:
            expected = read_secret(path)
        except (OSError, ValueError) as exc:
            raise AuthenticationNotConfiguredError(
                "Application authentication is not configured"
            ) from exc
        if not credential_matches(candidate, expected):
            raise InvalidCredentialError("Application credential was rejected")

        application_id = ApplicationId.GG_OFERTA
        get_application(application_id)
        if not is_active(application_id):
            raise ApplicationAccessDeniedError("Application is not active")
        return application_id
