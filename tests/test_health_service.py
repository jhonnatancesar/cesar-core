from cesar_core.health.models import ServiceStatus
from cesar_core.health.service import get_capabilities, get_health, get_readiness


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

    Nesta fase nenhuma capacidade está AVAILABLE, então não há
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
