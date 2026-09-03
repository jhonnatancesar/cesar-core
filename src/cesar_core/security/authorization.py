"""Autorização de capabilities pelo registry de aplicações."""

from cesar_core.applications.identity import ApplicationId
from cesar_core.applications.registry import allows_capability
from cesar_core.security.errors import ApplicationAccessDeniedError


def authorize_capability(application_id: ApplicationId, capability: str) -> None:
    """Nega por padrão capabilities ausentes do registro da aplicação."""
    if not allows_capability(application_id, capability):
        raise ApplicationAccessDeniedError(
            f"Application is not authorized for {capability}"
        )
