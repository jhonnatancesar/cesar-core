"""Rotas HTTP de health/readiness."""

from fastapi import APIRouter

from cesar_core.health.models import HealthStatus, ReadinessStatus
from cesar_core.health.service import get_health, probe_readiness

router = APIRouter()


@router.get("/health", response_model=HealthStatus)
def read_health() -> HealthStatus:
    return get_health()


@router.get("/ready", response_model=ReadinessStatus, response_model_exclude_none=True)
async def read_readiness() -> ReadinessStatus:
    return await probe_readiness()
