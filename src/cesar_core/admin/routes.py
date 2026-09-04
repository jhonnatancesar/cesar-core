"""API administrativa autenticada e shell da interface web."""

from datetime import UTC, datetime
from pathlib import Path
from time import monotonic, perf_counter

from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.responses import FileResponse

from cesar_core.admin.auth import (
    COOKIE_NAME,
    issue_session,
    rate_limit_login,
    require_session,
    revoke_request_session,
    validate_origin,
    verify_password,
)
from cesar_core.admin.config import AdminConfig
from cesar_core.admin.crypto import issue_credential, read_required
from cesar_core.admin.health import detailed_health
from cesar_core.admin.models import (
    ApplicationCreate,
    ApplicationUpdate,
    CredentialCreate,
    LoginRequest,
)
from cesar_core.admin.storage import get_store
from cesar_core.health.service import get_capabilities
from cesar_core.security.config import SecurityConfig
from cesar_core.security.quota import build_store

api = APIRouter(prefix="/admin/api", tags=["admin"], include_in_schema=False)
ui = APIRouter(include_in_schema=False)
STARTED_AT = monotonic()


def _audit(
    request: Request,
    action: str,
    outcome: str,
    target_type=None,
    target_id=None,
    metadata: dict | None = None,
) -> None:
    get_store().audit(
        action,
        outcome,
        target_type=target_type,
        target_id=target_id,
        correlation_id=getattr(request.state, "correlation_id", None),
        metadata=metadata,
    )


@api.post("/login")
def login(payload: LoginRequest, request: Request, response: Response) -> dict:
    config = AdminConfig()
    validate_origin(request, config)
    rate_limit_login(request, config)
    if not verify_password(payload.password, config):
        _audit(request, "admin.login", "denied")
        raise HTTPException(401, "Invalid administrator credentials")
    session = issue_session(config)
    response.set_cookie(
        COOKIE_NAME,
        session.token,
        httponly=True,
        secure=config.cookie_secure,
        samesite="strict",
        max_age=config.session_absolute_seconds,
        path="/admin",
    )
    _audit(request, "admin.login", "success")
    return {"authenticated": True, "csrf_token": session.csrf}


@api.get("/session")
def session(request: Request) -> dict:
    require_session(request)
    return {"authenticated": True}


@api.post("/logout", status_code=204)
def logout(request: Request, response: Response) -> None:
    require_session(request, write=True)
    revoke_request_session(request)
    response.delete_cookie(COOKIE_NAME, path="/admin")
    _audit(request, "admin.logout", "success")


@api.get("/overview")
async def overview(request: Request) -> dict:
    require_session(request)
    store = get_store()
    applications = store.list_applications()
    usage = store.usage(1)
    components = await detailed_health()
    failed = next(
        (item for item in components if item["status"] in {"degraded", "unavailable"}),
        None,
    )
    return {
        "version": request.app.version,
        "uptime_seconds": round(monotonic() - STARTED_AT),
        "applications": len(applications),
        "active_applications": sum(item["state"] == "active" for item in applications),
        "credentials": len(
            [item for item in store.list_credentials() if not item["revoked_at"]]
        ),
        "requests_24h": sum(item["requests"] for item in usage),
        "ai_requests_24h": sum(
            item["requests"] for item in usage if item["capability"] == "ai"
        ),
        "search_requests_24h": sum(
            item["requests"] for item in usage if item["capability"] == "search"
        ),
        "errors_24h": sum(
            item["requests"] for item in usage if item["status_class"] == "error"
        ),
        "readiness": {
            "status": "degraded" if failed else "ok",
            **({"reason": failed.get("reason")} if failed else {}),
        },
        "dependencies": components,
    }


@api.get("/applications")
def applications(request: Request) -> list[dict]:
    require_session(request)
    return get_store().list_applications()


@api.post("/applications", status_code=201)
def create_application(payload: ApplicationCreate, request: Request) -> dict:
    require_session(request, write=True)
    try:
        result = get_store().create_application(
            payload.id, payload.display_name, payload.client_id
        )
    except Exception as exc:
        _audit(request, "application.create", "failed", "application", payload.id)
        if "UNIQUE" in str(exc):
            raise HTTPException(
                409, "Application id or client id already exists"
            ) from None
        raise
    _audit(request, "application.create", "success", "application", payload.id)
    return result


@api.put("/applications/{application_id}")
def update_application(
    application_id: str, payload: ApplicationUpdate, request: Request
) -> dict:
    require_session(request, write=True)
    current = get_store().get_application(application_id)
    if current is None:
        raise HTTPException(404, "Application not found")
    if current["protected"]:
        _audit(request, "application.update", "denied", "application", application_id)
        raise HTTPException(409, "Protected application cannot be changed")
    if payload.state == "active":
        if not payload.capabilities or any(
            payload.quotas.get(cap, 0) < 1 for cap in payload.capabilities
        ):
            raise HTTPException(
                409, "Active applications require capabilities and quotas"
            )
        legacy = application_id == "gg_oferta" and SecurityConfig().is_configured
        if not legacy and get_store().active_credential_count(application_id) == 0:
            raise HTTPException(409, "Active applications require an active credential")
    try:
        result = get_store().update_application(
            application_id,
            display_name=payload.display_name,
            state=payload.state,
            capabilities=set(payload.capabilities),
            quotas={
                key: value
                for key, value in payload.quotas.items()
                if key in payload.capabilities
            },
        )
    except KeyError:
        raise HTTPException(404, "Application not found") from None
    except PermissionError as exc:
        raise HTTPException(409, str(exc)) from None
    _audit(request, "application.update", "success", "application", application_id)
    if current["state"] != result["state"]:
        _audit(
            request,
            "application.status_change",
            "success",
            "application",
            application_id,
            {"from": current["state"], "to": result["state"]},
        )
    if set(current["capabilities"]) != set(result["capabilities"]):
        _audit(
            request,
            "application.capability_change",
            "success",
            "application",
            application_id,
            {"capabilities": result["capabilities"]},
        )
    if current["quotas"] != result["quotas"]:
        _audit(
            request,
            "application.quota_change",
            "success",
            "application",
            application_id,
            {"quotas": result["quotas"]},
        )
    return result


@api.get("/credentials")
def credentials(request: Request, application_id: str | None = None) -> list[dict]:
    require_session(request)
    result = get_store().list_credentials(application_id)
    if (
        not application_id or application_id == "gg_oferta"
    ) and SecurityConfig().is_configured:
        result.append(
            {
                "id": "legacy_gg_oferta",
                "application_id": "gg_oferta",
                "name": "Legacy file credential",
                "fingerprint": None,
                "created_at": None,
                "revoked_at": None,
                "last_used_at": None,
                "read_only": True,
            }
        )
    return result


@api.post("/credentials", status_code=201)
def create_credential(
    payload: CredentialCreate, request: Request, response: Response
) -> dict:
    require_session(request, write=True)
    application = get_store().get_application(payload.application_id)
    if application is None:
        raise HTTPException(404, "Application not found")
    if application["protected"] or application["state"] == "reserved":
        _audit(
            request,
            "credential.create",
            "denied",
            "application",
            payload.application_id,
        )
        raise HTTPException(409, "Protected application cannot receive credentials")
    try:
        pepper = read_required(AdminConfig().credential_pepper_file)
    except (OSError, RuntimeError):
        raise HTTPException(503, "Credential issuing is not configured") from None
    credential_id, token, fingerprint, secret_hmac = issue_credential(pepper)
    get_store().insert_credential(
        credential_id, payload.application_id, payload.name, fingerprint, secret_hmac
    )
    _audit(request, "credential.create", "success", "credential", credential_id)
    response.headers["Cache-Control"] = "no-store"
    return {
        "id": credential_id,
        "credential": token,
        "fingerprint": fingerprint,
        "shown_once": True,
    }


@api.post("/credentials/{credential_id}/revoke")
def revoke_credential(credential_id: str, request: Request) -> dict:
    require_session(request, write=True)
    if not get_store().revoke_credential(credential_id):
        raise HTTPException(404, "Active credential not found")
    _audit(request, "credential.revoke", "success", "credential", credential_id)
    return {"revoked": True}


@api.get("/usage")
def usage(request: Request, days: int = 7) -> dict:
    require_session(request)
    if not 1 <= days <= 30:
        raise HTTPException(400, "days must be between 1 and 30")
    rows = get_store().usage(days)
    quotas = []
    config = SecurityConfig()
    for app in get_store().list_applications():
        for capability, limit in app["quotas"].items():
            try:
                key = f"{config.quota_namespace}:{app['id']}:{capability}"
                used, ttl_ms = build_store(config).snapshot(key)
                quotas.append(
                    {
                        "application_id": app["id"],
                        "capability": capability,
                        "used": used,
                        "limit": limit,
                        "ttl_seconds": (ttl_ms + 999) // 1000,
                    }
                )
            except Exception:
                quotas.append(
                    {
                        "application_id": app["id"],
                        "capability": capability,
                        "used": None,
                        "limit": limit,
                        "ttl_seconds": None,
                    }
                )
    return {"period_days": days, "rollups": rows, "quotas": quotas}


@api.get("/routes")
def routes(request: Request) -> list[dict]:
    require_session(request)
    schema = request.app.openapi()
    statuses = get_capabilities().model_dump(mode="json")
    result = []
    for path, operations in schema["paths"].items():
        if path.startswith("/admin"):
            continue
        for method, operation in operations.items():
            capability = (
                "ai"
                if path.startswith("/v1/ai")
                else "search"
                if path == "/v1/search"
                else None
            )
            availability = (
                statuses.get(capability, "available") if capability else "available"
            )
            result.append(
                {
                    "method": method.upper(),
                    "path": path,
                    "summary": operation.get("summary", ""),
                    "capability": capability,
                    "authenticated": bool(operation.get("security")),
                    "availability": availability,
                }
            )
    return result


@api.get("/health")
async def health(request: Request) -> dict:
    require_session(request)
    started = perf_counter()
    checked_at = datetime.now(UTC).isoformat()
    components = await detailed_health()
    components.insert(
        0,
        {
            "name": "core",
            "status": "healthy",
            "checked_at": checked_at,
            "latency_ms": 0,
        },
    )
    failed = next(
        (item for item in components if item["status"] in {"degraded", "unavailable"}),
        None,
    )
    return {
        "status": "degraded" if failed else "ok",
        "reason": failed.get("reason") if failed else None,
        "checked_at": checked_at,
        "latency_ms": round((perf_counter() - started) * 1000, 2),
        "version": request.app.version,
        "components": components,
    }


@api.get("/audit")
def audit(request: Request) -> list[dict]:
    require_session(request)
    return get_store().list_audit()


STATIC = Path(__file__).with_name("static")


@ui.get("/admin")
@ui.get("/admin/{path:path}")
def admin_ui(path: str = ""):
    if not AdminConfig().auth_configured:
        raise HTTPException(503, "Control Plane authentication is not configured")
    candidate = STATIC / path
    if path and candidate.is_file() and STATIC.resolve() in candidate.resolve().parents:
        return FileResponse(candidate)
    index = STATIC / "index.html"
    if not index.is_file():
        raise HTTPException(503, "Control Plane assets are not installed")
    return FileResponse(index)
