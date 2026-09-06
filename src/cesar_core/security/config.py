"""Configuração da fronteira aplicação -> César Core."""

from pathlib import Path
from urllib.parse import urlsplit

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class SecurityConfig(BaseSettings):
    """Credencial e quotas do primeiro consumidor ativo.

    Segredos são lidos via arquivo. Somente GG Oferta possui configuração de
    credencial de aplicação; não há equivalente para Claudião enquanto RESERVED.
    Redis mantém quotas em namespace compartilhado, independente das credenciais
    de aplicação e das credenciais upstream do OmniRoute.
    """

    model_config = SettingsConfigDict(
        env_prefix="CESAR_CORE_SECURITY_", env_file=".env"
    )

    gg_oferta_api_key_file: Path | None = None
    ai_requests_per_minute: int = Field(default=60, ge=1)
    search_requests_per_minute: int = Field(default=60, ge=1)
    fetch_requests_per_minute: int = Field(default=60, ge=1)
    quota_redis_url: str = Field(default="redis://127.0.0.1:6379/0", repr=False)
    quota_redis_username: str | None = None
    quota_redis_password_file: Path | None = None
    quota_redis_timeout_seconds: float = Field(default=1.0, gt=0, le=10)
    quota_namespace: str = Field(
        default="cesar-core:quota:v1", pattern=r"^[a-zA-Z0-9:_-]{1,100}$"
    )

    @field_validator("quota_redis_url")
    @classmethod
    def validate_redis_url(cls, value: str) -> str:
        parsed = urlsplit(value)
        if (
            parsed.scheme not in {"redis", "rediss"}
            or not parsed.hostname
            or parsed.username is not None
            or parsed.password is not None
            or parsed.query
            or parsed.fragment
            or (parsed.path not in {"", "/"} and not parsed.path[1:].isdigit())
        ):
            raise ValueError(
                "Use redis/rediss URL without credentials or query parameters"
            )
        return value

    @property
    def is_configured(self) -> bool:
        path = self.gg_oferta_api_key_file
        if path is None or not path.is_file():
            return False
        try:
            return bool(path.read_text(encoding="utf-8").strip())
        except OSError:
            return False
