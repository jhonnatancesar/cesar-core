"""Configuração base do processo César Core."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuração mínima de processo/deployment do César Core.

    Nenhuma configuração de provider de AI/Search (Gemini/Groq/OpenRouter)
    pertence aqui: isso é responsabilidade do OmniRoute em fases futuras.
    """

    model_config = SettingsConfigDict(env_prefix="CESAR_CORE_", env_file=".env")

    app_env: str = "development"
    host: str = "127.0.0.1"
    port: int = 8100
    log_level: str = "info"
