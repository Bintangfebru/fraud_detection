"""
FraudShield — Dependency Injection
Reusable FastAPI dependencies for auth, RBAC, DB, Redis, and rate limiting.
"""

from __future__ import annotations

from typing import Callable, List

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import (
    ExpiredTokenError,
    InactiveUserError,
    InvalidTokenError,
    PermissionDeniedError,
    RateLimitExceededError,
)
from app.core.redis import check_rate_limit, get_redis_client
from app.core.security import Role, decode_token, role_has_permission
from app.db.session import get_db
from app.models.user import User
from app.repositories.user_repo import UserRepository

# ── OAuth2 bearer scheme ──────────────────────────────────────────────────────

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


# ── Database ──────────────────────────────────────────────────────────────────

async def get_session(session: AsyncSession = Depends(get_db)) -> AsyncSession:
    """Thin alias so routes import from deps, not db.session."""
    return session


# ── Redis ─────────────────────────────────────────────────────────────────────

async def get_redis() -> Redis:
    """Inject the shared async Redis client."""
    return await get_redis_client()


# ── Current user ──────────────────────────────────────────────────────────────

async def get_current_user(
    token: str = Depends(oauth2_scheme),
    session: AsyncSession = Depends(get_session),
) -> User:
    """Decode JWT and return the active User. Raises 401 on any failure."""
    try:
        payload = decode_token(token)
        username: str = payload["sub"]
    except (ExpiredTokenError, InvalidTokenError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=exc.message,
            headers={"WWW-Authenticate": "Bearer"},
        )

    repo = UserRepository(session)
    user = await repo.get_by_username(username)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is deactivated.",
        )
    return user


# ── RBAC factory ──────────────────────────────────────────────────────────────

def require_roles(*roles: Role) -> Callable:
    """
    Dependency factory — enforces that the current user has one of the allowed roles.

    Usage:
        @router.get("/admin-only", dependencies=[Depends(require_roles(Role.ADMIN))])
        @router.get("/analysts", dependencies=[Depends(require_roles(Role.ADMIN, Role.ANALYST))])
    """
    async def _check(
        current_user: User = Depends(get_current_user),
    ) -> User:
        if current_user.role not in [r.value for r in roles]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied. Required roles: {[r.value for r in roles]}",
            )
        return current_user

    return _check


def require_min_role(min_role: Role) -> Callable:
    """
    Dependency factory — enforces role hierarchy (admin ≥ analyst ≥ auditor).

    Usage:
        @router.put("/thresholds", dependencies=[Depends(require_min_role(Role.ADMIN))])
    """
    async def _check(
        current_user: User = Depends(get_current_user),
    ) -> User:
        if not role_has_permission(current_user.role, min_role.value):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Requires '{min_role.value}' role or higher.",
            )
        return current_user

    return _check


# ── Rate limiting ─────────────────────────────────────────────────────────────

def rate_limit(
    max_requests: int = settings.RATE_LIMIT_REQUESTS,
    window_seconds: int = settings.RATE_LIMIT_WINDOW_SECONDS,
) -> Callable:
    """
    Sliding-window rate limit dependency.

    Identifies clients by: authenticated username > X-Forwarded-For > client IP.

    Usage:
        @router.post("/predict", dependencies=[Depends(rate_limit(60, 60))])
    """
    async def _check(
        request: Request,
        redis: Redis = Depends(get_redis),
    ) -> None:
        # Determine client identifier
        token = request.headers.get("Authorization", "")
        if token.startswith("Bearer "):
            try:
                payload = decode_token(token.split(" ", 1)[1])
                identifier = f"user:{payload['sub']}"
            except Exception:
                identifier = f"ip:{_get_client_ip(request)}"
        else:
            identifier = f"ip:{_get_client_ip(request)}"

        # Scope the key to the endpoint path
        rate_key = f"{identifier}:{request.url.path}"
        allowed, count, ttl = await check_rate_limit(rate_key, max_requests, window_seconds)

        # Always set headers
        request.state.rate_limit_remaining = max(0, max_requests - count)
        request.state.rate_limit_reset = ttl

        if not allowed:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Rate limit exceeded. Try again in {ttl}s.",
                headers={
                    "X-RateLimit-Limit": str(max_requests),
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Reset": str(ttl),
                    "Retry-After": str(ttl),
                },
            )

    return _check


def _get_client_ip(request: Request) -> str:
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client:
        return request.client.host
    return "unknown"


# ── Shorthand role dependencies ───────────────────────────────────────────────

AdminOnly = Depends(require_roles(Role.ADMIN))
AnalystOrAbove = Depends(require_min_role(Role.ANALYST))
AnyRole = Depends(get_current_user)
