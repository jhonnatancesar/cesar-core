"""Rota pública do Central Web Search Gateway."""

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from cesar_core.api.deps import get_request_application_context, get_search_manager
from cesar_core.applications.context import ApplicationContext
from cesar_core.search.contracts import (
    SearchErrorDetail,
    SearchErrorResponse,
    SearchRequest,
    SearchRequestPayload,
    SearchResponse,
)
from cesar_core.search.errors import (
    SearchApplicationDeniedError,
    SearchCostPolicyDeniedError,
    SearchNotConfiguredError,
    SearchRequestLimitExceededError,
    SearchUpstreamAuthError,
    SearchUpstreamRequestError,
    SearchUpstreamResponseError,
    SearchUpstreamUnavailableError,
)
from cesar_core.search.manager import SearchManager

router = APIRouter(prefix="/v1", tags=["search"])


@router.post(
    "/search",
    response_model=SearchResponse,
    responses={
        403: {"model": SearchErrorResponse},
        502: {"model": SearchErrorResponse},
        503: {"model": SearchErrorResponse},
    },
)
async def search_web(
    payload: SearchRequestPayload,
    context: ApplicationContext = Depends(get_request_application_context),
    manager: SearchManager = Depends(get_search_manager),
) -> SearchResponse | JSONResponse:
    request = SearchRequest(context=context, **payload.model_dump())
    try:
        return await manager.search(request)
    except (
        SearchApplicationDeniedError,
        SearchCostPolicyDeniedError,
        SearchRequestLimitExceededError,
    ) as exc:
        return _error_response(403, "search_policy_denied", str(exc), context)
    except SearchNotConfiguredError as exc:
        return _error_response(503, "search_not_configured", str(exc), context)
    except (
        SearchUpstreamAuthError,
        SearchUpstreamRequestError,
        SearchUpstreamResponseError,
    ) as exc:
        return _error_response(
            502,
            "search_upstream_error",
            str(exc),
            context,
            upstream_request_id=exc.upstream_request_id,
        )
    except SearchUpstreamUnavailableError as exc:
        return _error_response(
            503,
            "search_upstream_unavailable",
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
    error = SearchErrorResponse(
        error=SearchErrorDetail(
            code=code,
            message=message,
            request_id=context.request_id,
            correlation_id=context.correlation_id,
            upstream_request_id=upstream_request_id,
        )
    )
    return JSONResponse(status_code=status_code, content=error.model_dump(mode="json"))
