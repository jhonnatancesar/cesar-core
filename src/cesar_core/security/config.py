"""Configuração da fronteira aplicação -> César Core."""

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class SecurityConfig(BaseSettings):
    """Credencial e quotas do primeiro consumidor ativo.

    O segredo nunca é aceito diretamente em variável de ambiente. A única
    configuração funcional é o caminho para o arquivo da credencial do GG
    Oferta; não existe campo equivalente para o Claudião enquanto RESERVED.
    """

    model_config = SettingsConfigDict(
        env_prefix="CESAR_CORE_SECURITY_", env_file=".env"
    )

    gg_oferta_api_key_file: Path | None = None
    ai_requests_per_minute: int = Field(default=60, ge=1)
    search_requests_per_minute: int = Field(default=60, ge=1)

    @property
    def is_configured(self) -> bool:
        path = self.gg_oferta_api_key_file
        if path is None or not path.is_file():
            return False
        try:
            return bool(path.read_text(encoding="utf-8").strip())
        except OSError:
            return False
