"""Aplicação FastAPI do César Core."""

from time import perf_counter

from fastapi import FastAPI, Request
from fastapi.exception_handlers import request_validation_exception_handler
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from cesar_core.api.routes import ai, capabilities, health, metrics, search
from cesar_core.security.contracts import SecurityErrorDetail, SecurityErrorResponse
from cesar_core.security.errors import (
    InvalidCredentialError,
    QuotaExceededError,
    SecurityError,
)
from cesar_core.telemetry.correlation import CORRELATION_HEADER, resolve_correlation_id
from cesar_core.telemetry.metrics import METRICS
from cesar_core.telemetry.request_id import new_request_id
from cesar_core.telemetry.tracing import trace_http_completion


def create_app() -> FastAPI:
    app = FastAPI(title="César Core", version="0.1.0")

    @app.exception_handler(RequestValidationError)
    async def handle_request_validation(request: Request, exc: RequestValidationError):
        if request.url.path == "/v1/ai/generate":
            # Não ecoar input/ctx de ValidationError: podem conter instruções privadas.
            return JSONResponse(
                status_code=400,
                content={
                    "error": {
                        "code": "ai_invalid_request",
                        "message": "Invalid AI request: provide exactly one valid prompt or messages",
                        "request_id": request.state.request_id,
                        "correlation_id": request.state.correlation_id,
                        "upstream_request_id": None,
                    }
                },
            )
        return await request_validation_exception_handler(request, exc)

    @app.middleware("http")
    async def attach_correlation_id(request: Request, call_next):
        started_at = perf_counter()
        correlation_id = resolve_correlation_id(request.headers.get(CORRELATION_HEADER))
        request.state.correlation_id = correlation_id
        request.state.request_id = new_request_id()
        response = await call_next(request)
        response.headers[CORRELATION_HEADER] = correlation_id
        matched_route = request.scope.get("route")
        metric_path = getattr(matched_route, "path", "unmatched")
        duration_ms = (perf_counter() - started_at) * 1000
        application_id = getattr(request.state, "application_id", None)
        METRICS.observe_http(
            method=request.method,
            path=metric_path,
            status=response.status_code,
            duration_ms=duration_ms,
            application_id=application_id,
        )
        trace_http_completion(
            method=request.method,
            path=metric_path,
            status=response.status_code,
            latency_ms=duration_ms,
            request_id=request.state.request_id,
            correlation_id=correlation_id,
            application=(application_id.value if application_id else "anonymous"),
            service=getattr(request.state, "service", None),
            purpose=getattr(request.state, "purpose", None),
        )
        return response

    @app.exception_handler(SecurityError)
    async def handle_security_error(request: Request, exc: SecurityError):
        payload = SecurityErrorResponse(
            error=SecurityErrorDetail(
                code=exc.code,
                message=str(exc),
                request_id=request.state.request_id,
                correlation_id=request.state.correlation_id,
            )
        )
        headers = {}
        if isinstance(exc, InvalidCredentialError):
            headers["WWW-Authenticate"] = "Bearer"
        if isinstance(exc, QuotaExceededError):
            headers["Retry-After"] = str(exc.retry_after_seconds)
        return JSONResponse(
            status_code=exc.status_code,
            content=payload.model_dump(mode="json"),
            headers=headers,
        )

    app.include_router(health.router)
    app.include_router(capabilities.router)
    app.include_router(ai.router)
    app.include_router(search.router)
    app.include_router(metrics.router)

    return app


app = create_app()
