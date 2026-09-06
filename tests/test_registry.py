from cesar_core.applications.identity import ApplicationId, ApplicationState
from cesar_core.applications.registry import (
    REGISTRY,
    allows_capability,
    get_application,
    is_active,
)


def test_gg_oferta_is_active() -> None:
    entry = get_application(ApplicationId.GG_OFERTA)
    assert entry.state is ApplicationState.ACTIVE
    assert is_active(ApplicationId.GG_OFERTA) is True
    assert entry.client_id == "ggoferta-core-client"
    assert entry.allowed_capabilities == frozenset({"ai", "search", "fetch"})


def test_claudiao_is_reserved() -> None:
    entry = get_application(ApplicationId.CLAUDIAO)
    assert entry.state is ApplicationState.RESERVED
    assert is_active(ApplicationId.CLAUDIAO) is False
    assert entry.client_id == "claudiao-core-client"
    assert entry.allowed_capabilities == frozenset()
    assert allows_capability(ApplicationId.CLAUDIAO, "ai") is False


def test_registry_has_exactly_the_known_applications() -> None:
    assert set(REGISTRY.keys()) == {ApplicationId.GG_OFERTA, ApplicationId.CLAUDIAO}
