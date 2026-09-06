"""Configuração de runtime do Central Web Fetch/Enrichment Gateway."""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from cesar_core.policy.service_class import ServiceClass


class FetchConfig(BaseSettings):
    """Configuração neutra que liga classes de serviço a providers de fetch."""

    model_config = SettingsConfigDict(env_prefix="CESAR_CORE_FETCH_", env_file=".env")

    enabled: bool = False
    default_provider: str | None = None
    economy_provider: str | None = None
    standard_provider: str | None = None
    quality_provider: str | None = None
    provider_is_paid: bool = False
    max_content_length: int = Field(default=20_000, ge=100)

    @property
    def is_configured(self) -> bool:
        return self.enabled and any(
            self.provider_for(service_class) for service_class in ServiceClass
        )

    def provider_for(self, service_class: ServiceClass) -> str | None:
        configured = {
            ServiceClass.ECONOMY: self.economy_provider,
            ServiceClass.STANDARD: self.standard_provider,
            ServiceClass.QUALITY: self.quality_provider,
        }[service_class]
        selected = (configured or self.default_provider or "").strip()
        return selected or None
