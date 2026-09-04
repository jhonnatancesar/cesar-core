"""Isolamento de configuração do harness, complemento aos contracts reais."""

import importlib.util
import os
import sys
from pathlib import Path

from cesar_core.ai.config import AIConfig
from cesar_core.config.settings import Settings
from cesar_core.omniroute.config import OmniRouteConfig
from cesar_core.search.config import SearchConfig
from cesar_core.security.config import SecurityConfig


def test_harness_does_not_inherit_dotenv_or_production_flags(monkeypatch, tmp_path):
    path = Path(__file__).resolve().parents[1] / "scripts/run_118h_contracts.py"
    spec = importlib.util.spec_from_file_location("harness_118h", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(
        os, "environ", {
            "AISHOPPING_ENVIRONMENT": "production",
            "AISHOPPING_CESAR_CORE_DISASTER_FALLBACK_ENABLED": "true",
            "CESAR_CORE_AI_QUALITY_MODEL": "unexpected-inherited-model",
        },
    )
    monkeypatch.setattr(sys, "path", list(sys.path))
    configs = (AIConfig, Settings, OmniRouteConfig, SearchConfig, SecurityConfig)
    for config in configs:
        monkeypatch.setattr(config, "model_config", dict(config.model_config))
    module.configure(tmp_path)
    assert os.environ["AISHOPPING_ENVIRONMENT"] == "development"
    assert "AISHOPPING_CESAR_CORE_DISASTER_FALLBACK_ENABLED" not in os.environ
    assert "CESAR_CORE_AI_QUALITY_MODEL" not in os.environ
    assert os.environ["CESAR_CORE_OMNIROUTE_AI_API_KEY_FILE"] != os.environ[
        "CESAR_CORE_OMNIROUTE_SEARCH_API_KEY_FILE"
    ]
    for config in configs:
        assert config.model_config["env_file"] is None
        assert config.model_config["hide_input_in_errors"] is True
