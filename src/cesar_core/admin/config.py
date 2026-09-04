"""Configuração fail-closed do Control Plane."""

from pathlib import Path
from urllib.parse import urlsplit

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class AdminConfig(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="CESAR_CORE_ADMIN_", env_file=".env")

    database_path: Path = Path(".data/control-plane.sqlite3")
    password_hash_file: Path | None = None
    credential_pepper_file: Path | None = None
    cookie_secure: bool = True
    allowed_origin: str | None = None
    session_absolute_seconds: int = Field(default=28_800, ge=300, le=86_400)
    session_idle_seconds: int = Field(default=1_800, ge=60, le=14_400)
    login_attempts_per_minute: int = Field(default=5, ge=1, le=30)
    usage_retention_days: int = Field(default=30, ge=1, le=365)

    @model_validator(mode="after")
    def validate_browser_boundary(self):
        if self.allowed_origin is None:
            return self
        origin = self.allowed_origin.rstrip("/")
        parsed = urlsplit(origin)
        if (
            parsed.scheme not in {"http", "https"}
            or not parsed.hostname
            or parsed.path
            or parsed.query
            or parsed.fragment
            or parsed.username
            or parsed.password
        ):
            raise ValueError("Admin allowed origin must be an absolute origin")
        loopback = parsed.hostname in {"127.0.0.1", "localhost", "::1"}
        if not self.cookie_secure and (parsed.scheme != "http" or not loopback):
            raise ValueError("Insecure admin cookies are restricted to DEV loopback")
        if self.cookie_secure and parsed.scheme != "https":
            raise ValueError("Secure admin cookies require an HTTPS origin")
        self.allowed_origin = origin
        return self

    @property
    def auth_configured(self) -> bool:
        return bool(
            self.password_hash_file
            and self.password_hash_file.is_file()
            and self.credential_pepper_file
            and self.credential_pepper_file.is_file()
            and self.allowed_origin
        )
