"""Endpoint de métricas agregadas do César Core."""

from fastapi import APIRouter
from fastapi.responses import PlainTextResponse

from cesar_core.telemetry.metrics import METRICS

router = APIRouter()


@router.get("/metrics", response_class=PlainTextResponse, include_in_schema=False)
def read_metrics() -> str:
    """Expõe somente dimensões operacionais de baixa cardinalidade."""
    return METRICS.render()
