"""Aplicação FastAPI do César Core."""

from fastapi import FastAPI, Request

from cesar_core.api.routes import capabilities, health
from cesar_core.telemetry.correlation import CORRELATION_HEADER, resolve_correlation_id


def create_app() -> FastAPI:
    app = FastAPI(title="César Core", version="0.1.0")

    @app.middleware("http")
    async def attach_correlation_id(request: Request, call_next):
        correlation_id = resolve_correlation_id(request.headers.get(CORRELATION_HEADER))
        request.state.correlation_id = correlation_id
        response = await call_next(request)
        response.headers[CORRELATION_HEADER] = correlation_id
        return response

    app.include_router(health.router)
    app.include_router(capabilities.router)

    return app


app = create_app()
