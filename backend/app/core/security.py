"""
FraudShield — Security Module
JWT access + refresh tokens, bcrypt hashing, RBAC role enforcement.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Optional
from enum import Enum

import bcrypt
import jwt

from app.core.config import settings
from app.core.exceptions import (
    ExpiredTokenError,
    InvalidTokenError,
    PermissionDeniedError,
)


# ── Roles ─────────────────────────────────────────────────────────────────────

class Role(str, Enum):
    ADMIN = "admin"
    ANALYST = "analyst"
    AUDITOR = "auditor"


# Role hierarchy — higher index = more permissions
_ROLE_RANK: dict[str, int] = {
    Role.AUDITOR: 0,
    Role.ANALYST: 1,
    Role.ADMIN: 2,
}


def role_has_permission(user_role: str, required_role: str) -> bool:
    """Return True if user_role meets or exceeds required_role in hierarchy."""
    user_rank = _ROLE_RANK.get(user_role, -1)
    req_rank = _ROLE_RANK.get(required_role, 999)
    return user_rank >= req_rank


# ── Password Hashing ──────────────────────────────────────────────────────────

def hash_password(plain: str) -> str:
    """Hash a plaintext password using bcrypt (work factor 12)."""
    salt = bcrypt.gensalt(rounds=12)
    return bcrypt.hashpw(plain.encode("utf-8"), salt).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    """Verify a plaintext password against a bcrypt hash."""
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except Exception:
        return False


# ── Token Payloads ────────────────────────────────────────────────────────────

class TokenType(str, Enum):
    ACCESS = "access"
    REFRESH = "refresh"


# ── JWT Tokens ────────────────────────────────────────────────────────────────

def create_access_token(
    subject: str,
    role: str,
    extra: Optional[dict[str, Any]] = None,
) -> str:
    """Create a short-lived JWT access token."""
    now = datetime.now(timezone.utc)
    expire = now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    payload: dict[str, Any] = {
        "sub": subject,
        "role": role,
        "type": TokenType.ACCESS,
        "iat": now,
        "exp": expire,
    }
    if extra:
        payload.update(extra)
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def create_refresh_token(subject: str, role: str) -> str:
    """Create a long-lived JWT refresh token."""
    now = datetime.now(timezone.utc)
    expire = now + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    payload: dict[str, Any] = {
        "sub": subject,
        "role": role,
        "type": TokenType.REFRESH,
        "iat": now,
        "exp": expire,
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def decode_token(token: str, expected_type: TokenType = TokenType.ACCESS) -> dict[str, Any]:
    """
    Decode and validate a JWT token.
    Raises InvalidTokenError or ExpiredTokenError on failure.
    """
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM],
        )
    except jwt.ExpiredSignatureError:
        raise ExpiredTokenError()
    except jwt.PyJWTError:
        raise InvalidTokenError()

    if payload.get("type") != expected_type:
        raise InvalidTokenError(
            f"Expected token type '{expected_type}', got '{payload.get('type')}'"
        )
    if not payload.get("sub"):
        raise InvalidTokenError("Token missing subject claim.")

    return payload


def decode_refresh_token(token: str) -> dict[str, Any]:
    """Decode a refresh token specifically."""
    return decode_token(token, expected_type=TokenType.REFRESH)
