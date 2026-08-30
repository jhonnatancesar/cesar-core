from cesar_core.health.models import ServiceStatus
from cesar_core.health.service import get_capabilities, get_health, get_readiness


def test_get_health_reports_ok() -> None:
    assert get_health().status == "ok"


def test_get_readiness_reports_core_available() -> None:
    readiness = get_readiness()
    assert readiness.status == "ok"
    assert readiness.core is ServiceStatus.AVAILABLE


def test_get_capabilities_is_honest_about_unconfigured_services() -> None:
    capabilities = get_capabilities()
    assert capabilities.core is ServiceStatus.AVAILABLE
    assert capabilities.ai is ServiceStatus.NOT_CONFIGURED
    assert capabilities.search is ServiceStatus.NOT_CONFIGURED
    assert capabilities.omniroute is ServiceStatus.NOT_CONFIGURED
