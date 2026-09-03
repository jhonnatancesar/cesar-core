from pathlib import Path

import pytest

from cesar_core.applications.identity import ApplicationId
from cesar_core.security.authentication import ApplicationAuthenticator
from cesar_core.security.authorization import authorize_capability
from cesar_core.security.config import SecurityConfig
from cesar_core.security.credentials import read_secret
from cesar_core.security.errors import (
    ApplicationAccessDeniedError,
    AuthenticationNotConfiguredError,
    InvalidCredentialError,
    QuotaExceededError,
)
from cesar_core.security.quota import QuotaLimiter


def _config(path: Path | None) -> SecurityConfig:
    return SecurityConfig(_env_file=None, gg_oferta_api_key_file=path)


def test_authenticator_resolves_gg_oferta_from_bearer_file(tmp_path) -> None:
    path = tmp_path / "credential"
    path.write_text("secret-value\n", encoding="utf-8")
    result = ApplicationAuthenticator(_config(path)).authenticate(
        "Bearer secret-value"
    )
    assert result is ApplicationId.GG_OFERTA


@pytest.mark.parametrize("header", [None, "", "Basic value", "Bearer ", "Bearer bad"])
def test_authenticator_rejects_missing_or_invalid_credentials(tmp_path, header) -> None:
    path = tmp_path / "credential"
    path.write_text("expected", encoding="utf-8")
    with pytest.raises(InvalidCredentialError):
        ApplicationAuthenticator(_config(path)).authenticate(header)


def test_authenticator_fails_closed_without_a_configured_file() -> None:
    with pytest.raises(AuthenticationNotConfiguredError):
        ApplicationAuthenticator(_config(None)).authenticate("Bearer value")


def test_authenticator_fails_closed_for_empty_credential_file(tmp_path) -> None:
    path = tmp_path / "credential"
    path.write_text("  ", encoding="utf-8")
    with pytest.raises(AuthenticationNotConfiguredError):
        ApplicationAuthenticator(_config(path)).authenticate("Bearer value")


def test_secret_reader_does_not_accept_an_empty_file(tmp_path) -> None:
    path = tmp_path / "credential"
    path.write_text("", encoding="utf-8")
    with pytest.raises(ValueError, match="empty"):
        read_secret(path)


def test_registry_authorization_is_minimum_privilege() -> None:
    authorize_capability(ApplicationId.GG_OFERTA, "ai")
    authorize_capability(ApplicationId.GG_OFERTA, "search")
    with pytest.raises(ApplicationAccessDeniedError):
        authorize_capability(ApplicationId.GG_OFERTA, "admin")
    with pytest.raises(ApplicationAccessDeniedError):
        authorize_capability(ApplicationId.CLAUDIAO, "ai")


def test_quota_limiter_rejects_before_the_next_request() -> None:
    limiter = QuotaLimiter(window_seconds=60)
    limiter.check(ApplicationId.GG_OFERTA, "ai", 1)
    with pytest.raises(QuotaExceededError) as exc_info:
        limiter.check(ApplicationId.GG_OFERTA, "ai", 1)
    assert exc_info.value.retry_after_seconds == 60
    limiter.reset()
    limiter.check(ApplicationId.GG_OFERTA, "ai", 1)


def test_quotas_are_independent_per_capability() -> None:
    limiter = QuotaLimiter(window_seconds=60)
    limiter.check(ApplicationId.GG_OFERTA, "ai", 1)
    limiter.check(ApplicationId.GG_OFERTA, "search", 1)
    with pytest.raises(QuotaExceededError):
        limiter.check(ApplicationId.GG_OFERTA, "ai", 1)


def test_security_config_requires_a_real_credential_file(tmp_path) -> None:
    assert _config(None).is_configured is False
    assert _config(tmp_path / "missing").is_configured is False
    path = tmp_path / "credential"
    path.write_text("", encoding="utf-8")
    assert _config(path).is_configured is False
    path.write_text("value", encoding="utf-8")
    assert _config(path).is_configured is True
