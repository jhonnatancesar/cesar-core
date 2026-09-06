from cesar_core.fetch.config import FetchConfig
from cesar_core.policy.service_class import ServiceClass


def test_fetch_config_is_disabled_by_default() -> None:
    assert FetchConfig(_env_file=None).is_configured is False


def test_fetch_config_selects_class_override_or_default() -> None:
    config = FetchConfig(
        _env_file=None,
        enabled=True,
        default_provider="firecrawl",
        quality_provider="tavily-search",
    )
    assert config.is_configured is True
    assert config.provider_for(ServiceClass.ECONOMY) == "firecrawl"
    assert config.provider_for(ServiceClass.QUALITY) == "tavily-search"


def test_fetch_config_rejects_blank_default_as_unconfigured() -> None:
    config = FetchConfig(_env_file=None, enabled=True, default_provider=" ")
    assert config.is_configured is False
    assert config.provider_for(ServiceClass.STANDARD) is None


def test_fetch_config_default_max_content_length_is_positive() -> None:
    assert FetchConfig(_env_file=None).max_content_length > 0
