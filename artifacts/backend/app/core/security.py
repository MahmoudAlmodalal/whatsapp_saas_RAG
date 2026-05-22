"""
app/core/security.py
────────────────────
JWT creation / verification and password hashing utilities.

All secret material comes from `app.config.Settings` — never hard-coded.

Tokens
------
- access_token  : short-lived (default 60 min), contains user_id / tenant_id / role
- refresh_token : long-lived (default 7 days), contains only user_id + type="refresh"
"""
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.config import get_settings

settings = get_settings()

# ── Password hashing ──────────────────────────────────────────────────────────
_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(plain: str) -> str:
    """Return bcrypt hash for *plain* password."""
    return _pwd_context.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    """Return True if *plain* matches stored *hashed* password."""
    return _pwd_context.verify(plain, hashed)


# ── Token helpers ─────────────────────────────────────────────────────────────
def _make_token(payload: dict[str, Any], expires_delta: timedelta) -> str:
    """Sign and return a JWT with the given *payload* and expiry."""
    now = datetime.now(tz=timezone.utc)
    payload = payload.copy()
    payload["iat"] = now
    payload["exp"] = now + expires_delta
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def create_access_token(user_id: UUID, tenant_id: UUID, role: str) -> str:
    """
    Create a short-lived access token.

    Payload: user_id, tenant_id, role, type="access"
    """
    return _make_token(
        {
            "sub": str(user_id),
            "tenant_id": str(tenant_id),
            "role": role,
            "type": "access",
        },
        timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES),
    )


def create_refresh_token(user_id: UUID) -> str:
    """
    Create a long-lived refresh token.

    Payload: user_id, type="refresh"  (minimal — no tenant/role to reduce blast radius)
    """
    return _make_token(
        {"sub": str(user_id), "type": "refresh"},
        timedelta(days=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS),
    )


def decode_token(token: str) -> dict[str, Any]:
    """
    Decode and verify *token*.

    Raises
    ------
    jose.JWTError — propagated as-is so callers decide the HTTP status code.
    """
    return jwt.decode(
        token,
        settings.SECRET_KEY,
        algorithms=[settings.JWT_ALGORITHM],
    )


def decode_access_token(token: str) -> dict[str, Any]:
    """Decode an access token and assert its `type` field."""
    payload = decode_token(token)
    if payload.get("type") != "access":
        raise JWTError("رمز التحديث غير صالح كرمز وصول")  # wrong token type
    return payload


def decode_refresh_token(token: str) -> dict[str, Any]:
    """Decode a refresh token and assert its `type` field."""
    payload = decode_token(token)
    if payload.get("type") != "refresh":
        raise JWTError("رمز الوصول غير صالح كرمز تحديث")  # wrong token type
    return payload
