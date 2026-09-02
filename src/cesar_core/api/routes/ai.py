"""Rota pública do Central AI Gateway."""

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from cesar_core.ai.contracts import (
    AIErrorDetail,
    AIErrorResponse,
    AIRequest,
    AIRequestPayload,
    AIResponse,
)
from cesar_core.ai.errors import (
    AIApplicationDeniedError,
    AICostPolicyDeniedError,
    AIMaxTokensUnsupportedError,
    AINotConfiguredError,
    AIRequestLimitExceededError,
    AIUpstreamAuthError,
    AIUpstreamRequestError,
    AIUpstreamResponseError,
    AIUpstreamUnavailableError,
)
from cesar_core.ai.manager import AIManager
from cesar_core.api.deps import get_ai_manager, get_request_application_context
from cesar_core.applications.context import ApplicationContext

router = APIRouter(prefix="/v1/ai", tags=["ai"])


@router.post(
    "/generate",
    response_model=AIResponse,
    responses={
        403: {"model": AIErrorResponse},
        502: {"model": AIErrorResponse},
        503: {"model": AIErrorResponse},
    },
)
async def generate_ai(
    payload: AIRequestPayload,
    context: ApplicationContext = Depends(get_request_application_context),
    manager: AIManager = Depends(get_ai_manager),
) -> AIResponse | JSONResponse:
    request = AIRequest(context=context, **payload.model_dump())
    try:
        return await manager.generate(request)
    except (
        AIApplicationDeniedError,
        AICostPolicyDeniedError,
        AIMaxTokensUnsupportedError,
        AIRequestLimitExceededError,
    ) as exc:
        return _error_response(403, "ai_policy_denied", str(exc), context)
    except AINotConfiguredError as exc:
        return _error_response(503, "ai_not_configured", str(exc), context)
    except (
        AIUpstreamAuthError,
        AIUpstreamRequestError,
        AIUpstreamResponseError,
    ) as exc:
        return _error_response(
            502,
            "ai_upstream_error",
            str(exc),
            context,
            upstream_request_id=exc.upstream_request_id,
        )
    except AIUpstreamUnavailableError as exc:
        return _error_response(
            503,
            "ai_upstream_unavailable",
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
    error = AIErrorResponse(
        error=AIErrorDetail(
            code=code,
            message=message,
            request_id=context.request_id,
            correlation_id=context.correlation_id,
            upstream_request_id=upstream_request_id,
        )
    )
    return JSONResponse(status_code=status_code, content=error.model_dump(mode="json"))
