from cesar_core.policy.service_class import ServiceClass
from cesar_core.search.config import SearchConfig


def test_search_config_is_disabled_by_default() -> None:
    assert SearchConfig(_env_file=None).is_configured is False


def test_search_config_selects_class_override_or_default() -> None:
    config = SearchConfig(
        _env_file=None,
        enabled=True,
        default_provider="duckduckgo-free",
        quality_provider="exa-search",
    )
    assert config.is_configured is True
    assert config.provider_for(ServiceClass.ECONOMY) == "duckduckgo-free"
    assert config.provider_for(ServiceClass.QUALITY) == "exa-search"


def test_search_config_rejects_blank_default_as_unconfigured() -> None:
    config = SearchConfig(_env_file=None, enabled=True, default_provider=" ")
    assert config.is_configured is False
    assert config.provider_for(ServiceClass.STANDARD) is None


def test_documentation_target_does_not_configure_general_web() -> None:
    config = SearchConfig(
        _env_file=None,
        enabled=True,
        technical_documentation_provider="context7",
    )
    assert config.is_configured is True
    assert config.has_general_web_provider is False
    assert config.provider_for(ServiceClass.ECONOMY) is None
    assert config.normalized_technical_documentation_provider == "context7"
