"""Configuração de conexão do César Core com o OmniRoute.

Só configuração de transporte (base URL, timeout, onde ler a credencial).
Nenhuma regra de negócio, nenhuma seleção de provider -- isso é do
OmniRoute em si, e das políticas do César Core em TASKs futuras.
"""

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class OmniRouteConfig(BaseSettings):
    """Onde e como falar com o OmniRoute.

    ``api_key_file`` aponta para um arquivo local contendo só a chave de
    API de inferência (``sk-...``, sem escopo ``manage``) -- nunca a
    chave em si dentro de env var, código ou Git, no mesmo padrão de
    secret já usado no projeto (``*_FILE``).
    """

    model_config = SettingsConfigDict(env_prefix="CESAR_CORE_OMNIROUTE_", env_file=".env")

    base_url: str = "http://127.0.0.1:20128"
    api_key_file: Path
    timeout_seconds: float = 30.0

    def read_api_key(self) -> str:
        """Lê a chave de API do arquivo local, sem nunca logar seu valor."""
        return self.api_key_file.read_text(encoding="utf-8").strip()
