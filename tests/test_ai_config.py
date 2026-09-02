from cesar_core.ai.config import AIConfig
from cesar_core.policy.service_class import ServiceClass


def test_ai_config_is_disabled_by_default() -> None:
    config = AIConfig(_env_file=None)
    assert config.is_configured is False
    assert config.model_enforces_max_tokens is False


def test_ai_config_selects_class_override_or_default() -> None:
    config = AIConfig(
        _env_file=None,
        enabled=True,
        default_model="default-model",
        quality_model="quality-model",
    )
    assert config.is_configured is True
    assert config.model_for(ServiceClass.ECONOMY) == "default-model"
    assert config.model_for(ServiceClass.QUALITY) == "quality-model"
