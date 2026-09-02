"""Configuração de runtime do Central AI Gateway."""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from cesar_core.policy.service_class import ServiceClass


class AIConfig(BaseSettings):
    """Configuração neutra que liga classes de serviço a modelos upstream."""

    model_config = SettingsConfigDict(env_prefix="CESAR_CORE_AI_", env_file=".env")

    enabled: bool = False
    default_model: str | None = None
    economy_model: str | None = None
    standard_model: str | None = None
    quality_model: str | None = None
    provider: str | None = None
    model_is_paid: bool = False
    model_enforces_max_tokens: bool = False
    max_tokens_limit: int = Field(default=4096, ge=1)

    @property
    def is_configured(self) -> bool:
        return self.enabled and bool(self.default_model and self.default_model.strip())

    def model_for(self, service_class: ServiceClass) -> str | None:
        configured = {
            ServiceClass.ECONOMY: self.economy_model,
            ServiceClass.STANDARD: self.standard_model,
            ServiceClass.QUALITY: self.quality_model,
        }[service_class]
        selected = configured or self.default_model
        return selected.strip() if selected and selected.strip() else None
