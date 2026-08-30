from cesar_core.config.settings import Settings


def test_settings_default_to_local_loopback() -> None:
    settings = Settings(_env_file=None)
    assert settings.host == "127.0.0.1"
    assert settings.port == 8100
    assert settings.app_env == "development"
