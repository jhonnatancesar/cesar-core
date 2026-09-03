from cesar_core.ai.config import AIConfig
from cesar_core.health.models import ServiceStatus
from cesar_core.health.service import (
    get_capabilities,
    get_health,
    get_readiness,
    probe_readiness,
)
from cesar_core.omniroute.errors import OmniRouteConnectionError
from cesar_core.search.config import SearchConfig
from cesar_core.security.config import SecurityConfig


def _security_config(tmp_path) -> SecurityConfig:
    path = tmp_path / "ggoferta-core-client"
    path.write_text("credential", encoding="utf-8")
    return SecurityConfig(_env_file=None, gg_oferta_api_key_file=path)


def _configure_security(monkeypatch, tmp_path) -> None:
    config = _security_config(tmp_path)
    monkeypatch.setenv(
        "CESAR_CORE_SECURITY_GG_OFERTA_API_KEY_FILE",
        str(config.gg_oferta_api_key_file),
    )


def test_get_health_reports_ok() -> None:
    assert get_health().status == "ok"


def test_get_capabilities_is_honest_about_unconfigured_services() -> None:
    capabilities = get_capabilities()
    assert capabilities.core is ServiceStatus.AVAILABLE
    assert capabilities.application_registry is ServiceStatus.AVAILABLE
    assert capabilities.application_authentication is ServiceStatus.NOT_CONFIGURED
    assert capabilities.metrics is ServiceStatus.AVAILABLE
    assert capabilities.ai is ServiceStatus.NOT_CONFIGURED
    assert capabilities.search is ServiceStatus.NOT_CONFIGURED
    assert capabilities.search_general_web is ServiceStatus.NOT_CONFIGURED
    assert capabilities.search_technical_documentation is ServiceStatus.NOT_CONFIGURED
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
    assert capabilities.search_general_web is ServiceStatus.NOT_CONFIGURED
    assert capabilities.search_technical_documentation is ServiceStatus.NOT_CONFIGURED


def test_readiness_requires_authentication_and_dependencies(tmp_path) -> None:
    config = AIConfig(_env_file=None, enabled=True, default_model="model-a")
    security = _security_config(tmp_path)
    # Pass the configured capability through the environment-independent seam.
    capabilities = get_capabilities(ai_config=config)
    assert capabilities.ai is ServiceStatus.AVAILABLE

    assert (
        get_readiness(
            ai_config=config,
            security_config=security,
            dependencies_ready=False,
        ).status
        == "degraded"
    )
    assert get_readiness(ai_config=config, dependencies_ready=True).status == "degraded"
    assert (
        get_readiness(
            ai_config=config,
            security_config=security,
            dependencies_ready=True,
        ).status
        == "ok"
    )


def test_search_capability_is_independent_and_enables_omniroute() -> None:
    ai_config = AIConfig(_env_file=None)
    search_config = SearchConfig(
        _env_file=None, enabled=True, default_provider="duckduckgo-free"
    )
    capabilities = get_capabilities(ai_config=ai_config, search_config=search_config)
    assert capabilities.ai is ServiceStatus.NOT_CONFIGURED
    assert capabilities.search is ServiceStatus.AVAILABLE
    assert capabilities.search_general_web is ServiceStatus.AVAILABLE
    assert capabilities.search_technical_documentation is ServiceStatus.NOT_CONFIGURED
    assert capabilities.omniroute is ServiceStatus.AVAILABLE
    assert (
        get_readiness(
            ai_config=ai_config,
            search_config=search_config,
            dependencies_ready=False,
        ).status
        == "degraded"
    )


def test_documentation_target_is_available_without_claiming_general_web() -> None:
    config = SearchConfig(
        _env_file=None,
        enabled=True,
        technical_documentation_provider="context7",
    )
    capabilities = get_capabilities(
        ai_config=AIConfig(_env_file=None), search_config=config
    )
    assert capabilities.search is ServiceStatus.AVAILABLE
    assert capabilities.search_general_web is ServiceStatus.NOT_CONFIGURED
    assert capabilities.search_technical_documentation is ServiceStatus.AVAILABLE
    assert capabilities.omniroute is ServiceStatus.AVAILABLE


async def test_probe_readiness_checks_omniroute_when_ai_is_enabled(
    monkeypatch,
    tmp_path,
) -> None:
    monkeypatch.setenv("CESAR_CORE_AI_ENABLED", "true")
    monkeypatch.setenv("CESAR_CORE_AI_DEFAULT_MODEL", "model-a")
    monkeypatch.setenv("CESAR_CORE_OMNIROUTE_AI_API_KEY_FILE", str(tmp_path / "key"))
    _configure_security(monkeypatch, tmp_path)

    class HealthyClient:
        def __init__(self, config) -> None:
            pass

        async def health(self) -> None:
            return None

        async def chat_authentication_enforced(self) -> bool:
            return True

        async def chat_credential_accepted(self) -> bool:
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
    monkeypatch.setenv("CESAR_CORE_OMNIROUTE_AI_API_KEY_FILE", str(tmp_path / "key"))
    _configure_security(monkeypatch, tmp_path)

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
    monkeypatch.setenv("CESAR_CORE_OMNIROUTE_AI_API_KEY_FILE", str(tmp_path / "key"))
    _configure_security(monkeypatch, tmp_path)

    class DownClient:
        def __init__(self, config) -> None:
            pass

        async def health(self) -> None:
            raise OmniRouteConnectionError("down")

        async def aclose(self) -> None:
            return None

    monkeypatch.setattr("cesar_core.health.service.OmniRouteClient", DownClient)
    assert (await probe_readiness()).status == "degraded"


async def test_probe_readiness_checks_search_auth_when_search_is_enabled(
    monkeypatch, tmp_path
) -> None:
    monkeypatch.setenv("CESAR_CORE_AI_ENABLED", "false")
    monkeypatch.setenv("CESAR_CORE_SEARCH_ENABLED", "true")
    monkeypatch.setenv("CESAR_CORE_SEARCH_DEFAULT_PROVIDER", "duckduckgo-free")
    monkeypatch.setenv("CESAR_CORE_OMNIROUTE_SEARCH_API_KEY_FILE", str(tmp_path / "key"))
    _configure_security(monkeypatch, tmp_path)

    class HealthyClient:
        def __init__(self, config) -> None:
            pass

        async def health(self) -> None:
            return None

        async def search_authentication_enforced(self) -> bool:
            return True

        async def search_credential_accepted(self) -> bool:
            return True

        async def aclose(self) -> None:
            return None

    monkeypatch.setattr("cesar_core.health.service.OmniRouteClient", HealthyClient)
    assert (await probe_readiness()).status == "ok"


async def test_probe_readiness_degrades_when_search_auth_is_not_enforced(
    monkeypatch, tmp_path
) -> None:
    monkeypatch.setenv("CESAR_CORE_AI_ENABLED", "false")
    monkeypatch.setenv("CESAR_CORE_SEARCH_ENABLED", "true")
    monkeypatch.setenv("CESAR_CORE_SEARCH_DEFAULT_PROVIDER", "duckduckgo-free")
    monkeypatch.setenv("CESAR_CORE_OMNIROUTE_SEARCH_API_KEY_FILE", str(tmp_path / "key"))
    _configure_security(monkeypatch, tmp_path)

    class AnonymousClient:
        def __init__(self, config) -> None:
            pass

        async def health(self) -> None:
            return None

        async def search_authentication_enforced(self) -> bool:
            return False

        async def aclose(self) -> None:
            return None

    monkeypatch.setattr("cesar_core.health.service.OmniRouteClient", AnonymousClient)
    assert (await probe_readiness()).status == "degraded"
