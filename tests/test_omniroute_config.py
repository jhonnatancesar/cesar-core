from pathlib import Path

from cesar_core.omniroute.config import OmniRouteConfig


def test_config_defaults_to_local_loopback(tmp_path: Path) -> None:
    key_file = tmp_path / "omniroute_api_key"
    key_file.write_text("sk-test-key\n", encoding="utf-8")

    config = OmniRouteConfig(_env_file=None, api_key_file=key_file)

    assert config.base_url == "http://127.0.0.1:20128"
    assert config.timeout_seconds == 30.0


def test_read_api_key_strips_whitespace(tmp_path: Path) -> None:
    key_file = tmp_path / "omniroute_api_key"
    key_file.write_text("  sk-test-key  \n", encoding="utf-8")

    config = OmniRouteConfig(_env_file=None, api_key_file=key_file)

    assert config.read_api_key() == "sk-test-key"
