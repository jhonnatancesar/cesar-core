"""Autenticação Bearer legada e dinâmica de aplicações consumidoras."""

import hmac

from cesar_core.admin.config import AdminConfig
from cesar_core.admin.crypto import credential_hmac, parse_credential, read_required
from cesar_core.admin.storage import get_store
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
        pepper_path = AdminConfig().credential_pepper_file
        if not self._config.is_configured and not (
            pepper_path and pepper_path.is_file()
        ):
            raise AuthenticationNotConfiguredError(
                "Application authentication is not configured"
            )
        if authorization is None or not authorization.startswith("Bearer "):
            raise InvalidCredentialError("A valid Bearer credential is required")
        candidate = authorization.removeprefix("Bearer ").strip()
        if not candidate:
            raise InvalidCredentialError("A valid Bearer credential is required")

        dynamic = parse_credential(candidate)
        if dynamic:
            credential_id, secret = dynamic
            try:
                stored = get_store().credential_digest(credential_id)
                pepper = read_required(AdminConfig().credential_pepper_file)
            except (OSError, RuntimeError):
                raise AuthenticationNotConfiguredError(
                    "Application authentication is not configured"
                ) from None
            if stored is None or not hmac.compare_digest(
                credential_hmac(pepper, credential_id, secret), stored[1]
            ):
                raise InvalidCredentialError("Application credential was rejected")
            application_id = ApplicationId(stored[0])
            if not is_active(application_id):
                raise ApplicationAccessDeniedError("Application is not active")
            return application_id

        path = self._config.gg_oferta_api_key_file
        if path is None:
            raise InvalidCredentialError("Application credential was rejected")
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
