from cesar_core.ai.config import AIConfig
from cesar_core.health.service import get_capabilities
from cesar_core.search.config import SearchConfig


def test_searxng_requires_explicit_dependency_configuration():
    config = SearchConfig(
        _env_file=None, enabled=True, default_provider="searxng-search"
    )
    assert not config.has_general_web_provider
    configured = config.model_copy(
        update={"provider_health_url": "http://127.0.0.1:18888/healthz"}
    )
    assert configured.has_general_web_provider
    assert (
        get_capabilities(
            ai_config=AIConfig(_env_file=None), search_config=configured
        ).search_general_web
        == "available"
    )


def test_context7_never_supplies_general_web():
    config = SearchConfig(
        _env_file=None, enabled=True, technical_documentation_provider="context7"
    )
    assert config.is_configured and not config.has_general_web_provider
