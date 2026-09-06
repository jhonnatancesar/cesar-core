"""Static release guardrails, complementary to real container validation."""

import json
import tomllib
from pathlib import Path

import yaml

from cesar_core import __version__

ROOT = Path(__file__).resolve().parents[1]


def test_release_versions_agree():
    project = tomllib.loads((ROOT / "pyproject.toml").read_text())
    schema = json.loads((ROOT / "contracts/openapi.json").read_text())
    assert project["project"]["version"] == schema["info"]["version"] == __version__
    assert project["project"]["license"] == "LicenseRef-Proprietary"


def test_official_compose_topology_and_secrets():
    config = yaml.safe_load((ROOT / "compose.yaml").read_text())
    services = config["services"]
    assert set(services) == {"cesar-core", "redis", "omniroute", "searxng"}
    core = services["cesar-core"]
    assert "build" not in core and "ghcr.io/" in core["image"]
    assert core["read_only"] is True and core["cap_drop"] == ["ALL"]
    assert core["ports"][0].startswith("127.0.0.1:")
    assert config["networks"]["backend"]["internal"] is True
    assert "ingress" in core["networks"]
    for service in ("redis", "omniroute", "searxng"):
        assert "ports" not in services[service]
        assert "@sha256:" in services[service]["image"]
    env = core["environment"]
    omniroute_key_files = {
        env["CESAR_CORE_OMNIROUTE_AI_API_KEY_FILE"],
        env["CESAR_CORE_OMNIROUTE_SEARCH_API_KEY_FILE"],
        env["CESAR_CORE_OMNIROUTE_FETCH_API_KEY_FILE"],
    }
    assert len(omniroute_key_files) == 3  # uma credencial distinta por capability
    assert services["omniroute"]["environment"]["REQUIRE_API_KEY"] == "true"
    # application, omniroute_ai, omniroute_search, omniroute_fetch (FASE E.1), searxng
    assert len(config["secrets"]) == 5


def test_image_context_and_durable_redis():
    dockerfile = (ROOT / "Dockerfile").read_text()
    assert "USER 10001:10001" in dockerfile
    assert "--require-hashes" in dockerfile
    assert "r['status']=='ok'" in dockerfile
    assert "COPY . " not in dockerfile
    rules = [
        line
        for line in (ROOT / ".dockerignore").read_text().splitlines()
        if line.strip() and not line.startswith("#")
    ]
    assert rules[0] == "**"
    redis = (ROOT / "deploy/redis/redis.conf").read_text()
    for setting in (
        "appendonly yes",
        "appendfsync always",
        "maxmemory-policy noeviction",
        "no-appendfsync-on-rewrite no",
    ):
        assert setting in redis
