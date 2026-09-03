"""Configuração de conexão do César Core com o OmniRoute.

Só configuração de transporte (base URL, timeout, onde ler a credencial).
Nenhuma regra de negócio, nenhuma seleção de provider -- isso é do
OmniRoute em si, e das políticas do César Core em TASKs futuras.
"""

from pathlib import Path

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class OmniRouteConfig(BaseSettings):
    """Onde e como falar com o OmniRoute.

    AI e Search usam arquivos independentes no runtime da aplicação. O campo
    genérico ``api_key_file`` permanece apenas como seam explícito do client de
    baixo nível e dos contract tests; os gateways selecionam sua capability.
    """

    model_config = SettingsConfigDict(env_prefix="CESAR_CORE_OMNIROUTE_", env_file=".env")

    base_url: str = "http://127.0.0.1:20128"
    api_key_file: Path | None = None
    ai_api_key_file: Path | None = None
    search_api_key_file: Path | None = None
    timeout_seconds: float = 30.0

    @model_validator(mode="after")
    def require_distinct_capability_files(self) -> "OmniRouteConfig":
        if (
            self.ai_api_key_file is not None
            and self.search_api_key_file is not None
            and self.ai_api_key_file.resolve() == self.search_api_key_file.resolve()
        ):
            raise ValueError("AI and Search must use distinct OmniRoute key files")
        return self

    def read_api_key(self) -> str:
        """Lê a chave de API do arquivo local, sem nunca logar seu valor."""
        if self.api_key_file is None:
            raise OSError("OmniRoute API credential is not configured")
        return self.api_key_file.read_text(encoding="utf-8").strip()

    def for_capability(self, capability: str) -> "OmniRouteConfig":
        """Seleciona a credencial de menor privilégio para AI ou Search."""
        paths = {
            "ai": self.ai_api_key_file,
            "search": self.search_api_key_file,
        }
        try:
            path = paths[capability]
        except KeyError as exc:
            raise ValueError(f"Unknown OmniRoute capability: {capability}") from exc
        if path is None:
            raise ValueError(f"OmniRoute {capability} credential is not configured")
        return self.model_copy(update={"api_key_file": path})
