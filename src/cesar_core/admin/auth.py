"""Autenticação e proteção do Control Plane administrativo."""

import hashlib
import secrets
from dataclasses import dataclass
from urllib.parse import urlsplit

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError
from fastapi import HTTPException, Request
from redis import RedisError

from cesar_core.admin.config import AdminConfig
from cesar_core.admin.crypto import digest
from cesar_core.admin.storage import get_store
from cesar_core.security.config import SecurityConfig
from cesar_core.security.quota import build_store

COOKIE_NAME = "cesar_core_admin_session"
CSRF_HEADER = "X-CSRF-Token"


@dataclass(frozen=True)
class AdminSession:
    token: str
    csrf: str


def verify_password(password: str, config: AdminConfig) -> bool:
    if not config.auth_configured or config.password_hash_file is None:
        raise HTTPException(503, "Control Plane authentication is not configured")
    try:
        encoded = config.password_hash_file.read_text(encoding="utf-8").strip()
        if not encoded.startswith("$argon2id$"):
            return False
        return PasswordHasher().verify(encoded, password)
    except (OSError, InvalidHashError, VerifyMismatchError):
        return False


def rate_limit_login(request: Request, config: AdminConfig) -> None:
    address = request.client.host if request.client else "unknown"
    subject = hashlib.sha256(address.encode()).hexdigest()[:24]
    key = f"{SecurityConfig().quota_namespace}:admin-login:{subject}"
    try:
        with build_store(SecurityConfig())._client() as client:
            count = int(client.incr(key))
            if count == 1:
                client.expire(key, 60)
    except (RedisError, OSError, ValueError):
        raise HTTPException(503, "Login protection unavailable") from None
    if count > config.login_attempts_per_minute:
        raise HTTPException(429, "Too many login attempts")


def issue_session(config: AdminConfig) -> AdminSession:
    token = secrets.token_urlsafe(48)
    csrf = secrets.token_urlsafe(32)
    get_store().create_session(
        secrets.token_urlsafe(18),
        digest(token),
        digest(csrf),
        config.session_absolute_seconds,
    )
    return AdminSession(token, csrf)


def validate_origin(request: Request, config: AdminConfig) -> None:
    if not config.allowed_origin:
        raise HTTPException(503, "Control Plane origin is not configured")
    origin = request.headers.get("origin")
    if origin != config.allowed_origin.rstrip("/"):
        raise HTTPException(403, "Origin rejected")
    expected = urlsplit(config.allowed_origin)
    host = request.headers.get("host", "").lower()
    if host != expected.netloc.lower():
        raise HTTPException(403, "Host rejected")


def require_session(request: Request, *, write: bool = False) -> dict:
    config = AdminConfig()
    if not config.auth_configured:
        raise HTTPException(503, "Control Plane authentication is not configured")
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        raise HTTPException(401, "Administrator session required")
    csrf = None
    if write:
        validate_origin(request, config)
        csrf = request.headers.get(CSRF_HEADER)
        if not csrf:
            raise HTTPException(403, "CSRF token required")
    row = get_store().validate_session(
        digest(token), digest(csrf) if csrf else None, config.session_idle_seconds
    )
    if not row:
        raise HTTPException(401, "Administrator session expired")
    return row


def revoke_request_session(request: Request) -> None:
    token = request.cookies.get(COOKIE_NAME)
    if token:
        get_store().revoke_session(digest(token))
