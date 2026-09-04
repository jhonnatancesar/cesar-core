"""Primitivas de credenciais e sessões; nenhum segredo é persistido em claro."""

import hashlib
import hmac
import secrets
from pathlib import Path


def read_required(path: Path | None) -> bytes:
    if path is None:
        raise RuntimeError("Required secret file is not configured")
    value = path.read_bytes().strip()
    if len(value) < 32:
        raise RuntimeError("Secret file must contain at least 32 bytes")
    return value


def digest(value: str) -> bytes:
    return hashlib.sha256(value.encode()).digest()


def credential_hmac(pepper: bytes, credential_id: str, secret: str) -> bytes:
    message = f"{credential_id}.{secret}".encode()
    return hmac.new(pepper, message, hashlib.sha256).digest()


def issue_credential(pepper: bytes) -> tuple[str, str, str, bytes]:
    credential_id = secrets.token_urlsafe(12).replace("-", "x").replace("_", "y")
    secret = secrets.token_urlsafe(32)
    token = f"cc_{credential_id}.{secret}"
    fingerprint = hashlib.sha256(token.encode()).hexdigest()[-12:]
    return (
        credential_id,
        token,
        fingerprint,
        credential_hmac(pepper, credential_id, secret),
    )


def parse_credential(token: str) -> tuple[str, str] | None:
    if not token.startswith("cc_") or "." not in token:
        return None
    credential_id, secret = token[3:].split(".", 1)
    if not credential_id or len(secret) < 32:
        return None
    return credential_id, secret
