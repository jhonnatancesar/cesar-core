"""Rota pública do Central Web Fetch/Enrichment Gateway."""

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from cesar_core.admin.storage import get_store
from cesar_core.api.deps import get_fetch_application_context, get_fetch_manager
from cesar_core.applications.context import ApplicationContext
from cesar_core.fetch.contracts import (
    FetchErrorDetail,
    FetchErrorResponse,
    FetchRequest,
    FetchRequestPayload,
    FetchResponse,
    reject_ssrf_target,
)
from cesar_core.fetch.errors import (
    FetchApplicationDeniedError,
    FetchCostPolicyDeniedError,
    FetchNotConfiguredError,
    FetchUpstreamAuthError,
    FetchUpstreamRequestError,
    FetchUpstreamResponseError,
    FetchUpstreamUnavailableError,
)
from cesar_core.fetch.manager import FetchManager
from cesar_core.security.contracts import SecurityErrorResponse
from cesar_core.telemetry.metrics import METRICS
from cesar_core.telemetry.tracing import trace_fetch_success

router = APIRouter(prefix="/v1", tags=["fetch"])


@router.post(
    "/fetch",
    response_model=FetchResponse,
    responses={
        400: {"model": FetchErrorResponse},
        403: {"model": FetchErrorResponse},
        401: {"model": SecurityErrorResponse},
        429: {"model": SecurityErrorResponse},
        502: {"model": FetchErrorResponse},
        503: {"model": FetchErrorResponse},
    },
)
async def fetch_url(
    payload: FetchRequestPayload,
    context: ApplicationContext = Depends(get_fetch_application_context),
    manager: FetchManager = Depends(get_fetch_manager),
) -> FetchResponse | JSONResponse:
    try:
        reject_ssrf_target(payload.url)
    except ValueError as exc:
        return _error_response(400, "fetch_target_rejected", str(exc), context)
    request = FetchRequest(context=context, **payload.model_dump())
    try:
        response = await manager.fetch(request)
        METRICS.observe_fetch(context.application_id, response)
        trace_fetch_success(context, response)
        get_store().record_usage(
            context.application_id.value,
            "fetch",
            "success",
            provider=response.provider,
        )
        return response
    except (
        FetchApplicationDeniedError,
        FetchCostPolicyDeniedError,
    ) as exc:
        return _error_response(403, "fetch_policy_denied", str(exc), context)
    except FetchNotConfiguredError as exc:
        return _error_response(503, "fetch_not_configured", str(exc), context)
    except (
        FetchUpstreamAuthError,
        FetchUpstreamRequestError,
        FetchUpstreamResponseError,
    ) as exc:
        return _error_response(
            502,
            "fetch_upstream_error",
            str(exc),
            context,
            upstream_request_id=exc.upstream_request_id,
        )
    except FetchUpstreamUnavailableError as exc:
        return _error_response(
            503,
            "fetch_upstream_unavailable",
            str(exc),
            context,
            upstream_request_id=exc.upstream_request_id,
        )


def _error_response(
    status_code: int,
    code: str,
    message: str,
    context: ApplicationContext,
    *,
    upstream_request_id: str | None = None,
) -> JSONResponse:
    get_store().record_usage(context.application_id.value, "fetch", "error")
    error = FetchErrorResponse(
        error=FetchErrorDetail(
            code=code,
            message=message,
            request_id=context.request_id,
            correlation_id=context.correlation_id,
            upstream_request_id=upstream_request_id,
        )
    )
    return JSONResponse(status_code=status_code, content=error.model_dump(mode="json"))
