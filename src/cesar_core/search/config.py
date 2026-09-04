"""Configuração de runtime do Central Web Search Gateway."""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from cesar_core.policy.service_class import ServiceClass

TECHNICAL_DOCUMENTATION_PURPOSE = "technical_documentation"


class SearchConfig(BaseSettings):
    """Configuração neutra que liga classes de serviço a providers."""

    model_config = SettingsConfigDict(env_prefix="CESAR_CORE_SEARCH_", env_file=".env")

    enabled: bool = False
    default_provider: str | None = None
    economy_provider: str | None = None
    standard_provider: str | None = None
    quality_provider: str | None = None
    technical_documentation_provider: str | None = None
    provider_health_url: str | None = None
    provider_is_paid: bool = False
    max_results_limit: int = Field(default=20, ge=1, le=100)

    @property
    def is_configured(self) -> bool:
        return self.enabled and (
            self.has_general_web_provider
            or self.normalized_technical_documentation_provider is not None
        )

    @property
    def has_general_web_provider(self) -> bool:
        """Há target para busca Web geral em ao menos uma service class."""
        return any(self.provider_for(service_class) for service_class in ServiceClass)

    @property
    def normalized_technical_documentation_provider(self) -> str | None:
        """Target especializado, sem promovê-lo a default geral."""
        provider = self.technical_documentation_provider
        return provider.strip() if provider and provider.strip() else None

    def provider_for(self, service_class: ServiceClass) -> str | None:
        configured = {
            ServiceClass.ECONOMY: self.economy_provider,
            ServiceClass.STANDARD: self.standard_provider,
            ServiceClass.QUALITY: self.quality_provider,
        }[service_class]
        selected = (configured or self.default_provider or "").strip()
        if selected == "searxng-search" and not self.provider_health_url:
            return None
        return selected or None
