"""Rota HTTP de capabilities."""

from fastapi import APIRouter

from cesar_core.health.models import CapabilitiesResponse
from cesar_core.health.service import get_capabilities

router = APIRouter()


@router.get("/v1/capabilities", response_model=CapabilitiesResponse)
def read_capabilities() -> CapabilitiesResponse:
    return get_capabilities()
