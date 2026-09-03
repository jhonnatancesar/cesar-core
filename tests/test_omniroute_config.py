from pathlib import Path

import pytest
from pydantic import ValidationError

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


def test_config_selects_independent_capability_credentials(tmp_path: Path) -> None:
    ai_key = tmp_path / "ggoferta-ai"
    search_key = tmp_path / "ggoferta-search"
    config = OmniRouteConfig(
        _env_file=None,
        ai_api_key_file=ai_key,
        search_api_key_file=search_key,
    )
    assert config.for_capability("ai").api_key_file == ai_key
    assert config.for_capability("search").api_key_file == search_key


def test_config_rejects_missing_or_unknown_capability_credential() -> None:
    config = OmniRouteConfig(_env_file=None)
    for capability in ("ai", "search", "admin"):
        try:
            config.for_capability(capability)
        except ValueError:
            pass
        else:
            raise AssertionError(f"{capability} credential should be rejected")


def test_read_api_key_fails_without_an_explicit_file() -> None:
    config = OmniRouteConfig(_env_file=None)
    try:
        config.read_api_key()
    except OSError:
        pass
    else:
        raise AssertionError("missing credential should fail closed")


def test_config_rejects_a_shared_ai_and_search_credential_file(tmp_path) -> None:
    shared = tmp_path / "shared-key"
    with pytest.raises(ValidationError, match="distinct"):
        OmniRouteConfig(
            _env_file=None,
            ai_api_key_file=shared,
            search_api_key_file=shared,
        )
