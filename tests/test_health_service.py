from cesar_core.ai.config import AIConfig
from cesar_core.health.models import ServiceStatus
from cesar_core.health.service import (
    get_capabilities,
    get_health,
    get_readiness,
    probe_readiness,
)
from cesar_core.omniroute.errors import OmniRouteConnectionError


def test_get_health_reports_ok() -> None:
    assert get_health().status == "ok"


def test_get_capabilities_is_honest_about_unconfigured_services() -> None:
    capabilities = get_capabilities()
    assert capabilities.core is ServiceStatus.AVAILABLE
    assert capabilities.ai is ServiceStatus.NOT_CONFIGURED
    assert capabilities.search is ServiceStatus.NOT_CONFIGURED
    assert capabilities.omniroute is ServiceStatus.NOT_CONFIGURED


def test_readiness_is_ok_because_no_capability_is_enabled_yet() -> None:
    """/ready == apto a atender capacidades habilitadas (ADR 0008).

    Na configuração atual nenhuma capacidade está AVAILABLE, então não há
    dependência obrigatória pendente e o core está sempre pronto -- não
    porque o valor esteja hardcoded, mas porque a lista de capacidades
    habilitadas está vazia.
    """
    capabilities = get_capabilities()
    enabled = [
        status
        for status in (capabilities.ai, capabilities.search, capabilities.omniroute)
        if status is ServiceStatus.AVAILABLE
    ]
    assert enabled == []

    readiness = get_readiness()
    assert readiness.status == "ok"
    assert readiness.core is ServiceStatus.AVAILABLE


def test_ai_and_omniroute_capabilities_become_available_when_ai_is_configured() -> None:
    config = AIConfig(_env_file=None, enabled=True, default_model="model-a")
    capabilities = get_capabilities(ai_config=config)
    assert capabilities.ai is ServiceStatus.AVAILABLE
    assert capabilities.omniroute is ServiceStatus.AVAILABLE
    assert capabilities.search is ServiceStatus.NOT_CONFIGURED


def test_readiness_requires_enabled_dependencies_to_be_confirmed() -> None:
    config = AIConfig(_env_file=None, enabled=True, default_model="model-a")
    # Pass the configured capability through the environment-independent seam.
    capabilities = get_capabilities(ai_config=config)
    assert capabilities.ai is ServiceStatus.AVAILABLE

    assert (
        get_readiness(ai_config=config, dependencies_ready=False).status == "degraded"
    )
    assert get_readiness(ai_config=config, dependencies_ready=True).status == "ok"


async def test_probe_readiness_checks_omniroute_when_ai_is_enabled(
    monkeypatch,
    tmp_path,
) -> None:
    monkeypatch.setenv("CESAR_CORE_AI_ENABLED", "true")
    monkeypatch.setenv("CESAR_CORE_AI_DEFAULT_MODEL", "model-a")
    monkeypatch.setenv("CESAR_CORE_OMNIROUTE_API_KEY_FILE", str(tmp_path / "key"))

    class HealthyClient:
        def __init__(self, config) -> None:
            pass

        async def health(self) -> None:
            return None

        async def chat_authentication_enforced(self) -> bool:
            return True

        async def aclose(self) -> None:
            return None

    monkeypatch.setattr("cesar_core.health.service.OmniRouteClient", HealthyClient)
    assert (await probe_readiness()).status == "ok"


async def test_probe_readiness_degrades_when_chat_allows_anonymous_fallback(
    monkeypatch,
    tmp_path,
) -> None:
    monkeypatch.setenv("CESAR_CORE_AI_ENABLED", "true")
    monkeypatch.setenv("CESAR_CORE_AI_DEFAULT_MODEL", "model-a")
    monkeypatch.setenv("CESAR_CORE_OMNIROUTE_API_KEY_FILE", str(tmp_path / "key"))

    class AnonymousClient:
        def __init__(self, config) -> None:
            pass

        async def health(self) -> None:
            return None

        async def chat_authentication_enforced(self) -> bool:
            return False

        async def aclose(self) -> None:
            return None

    monkeypatch.setattr("cesar_core.health.service.OmniRouteClient", AnonymousClient)
    assert (await probe_readiness()).status == "degraded"


async def test_probe_readiness_degrades_when_omniroute_is_down(
    monkeypatch, tmp_path
) -> None:
    monkeypatch.setenv("CESAR_CORE_AI_ENABLED", "true")
    monkeypatch.setenv("CESAR_CORE_AI_DEFAULT_MODEL", "model-a")
    monkeypatch.setenv("CESAR_CORE_OMNIROUTE_API_KEY_FILE", str(tmp_path / "key"))

    class DownClient:
        def __init__(self, config) -> None:
            pass

        async def health(self) -> None:
            raise OmniRouteConnectionError("down")

        async def aclose(self) -> None:
            return None

    monkeypatch.setattr("cesar_core.health.service.OmniRouteClient", DownClient)
    assert (await probe_readiness()).status == "degraded"
