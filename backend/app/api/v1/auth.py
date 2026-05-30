"""
FraudShield — Authentication Router  (POST /api/v1/auth/*)
Endpoints: login, refresh, logout, register, /me, change-password
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import (
    AnyRole,
    get_current_user,
    get_session,
    rate_limit,
)
from app.core.config import settings
from app.core.exceptions import AuthenticationError, ConflictError, PermissionDeniedError
from app.core.logging import get_logger
from app.core.security import hash_password, verify_password
from app.models.user import User
from app.repositories.user_repo import UserRepository
from app.schemas.auth import (
    LoginRequest,
    PasswordChange,
    RefreshRequest,
    TokenResponse,
    UserCreate,
    UserOut,
)
from app.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["Authentication"])
log = get_logger("api.auth")


# ── Login ─────────────────────────────────────────────────────────────────────

@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Obtain JWT access + refresh tokens",
    dependencies=[Depends(rate_limit(
        max_requests=settings.RATE_LIMIT_AUTH,
        window_seconds=60,
    ))],
)
async def login(
    request: Request,
    form_data: OAuth2PasswordRequestForm = Depends(),
    session: AsyncSession = Depends(get_session),
) -> TokenResponse:
    """
    Authenticate with username + password (form-encoded).
    Returns a short-lived access token and a long-lived refresh token.
    """
    svc = AuthService(session)
    return await svc.login(
        username=form_data.username,
        password=form_data.password,
    )


@router.post(
    "/login/json",
    response_model=TokenResponse,
    summary="JSON login (alternative to form-encoded)",
    dependencies=[Depends(rate_limit(
        max_requests=settings.RATE_LIMIT_AUTH,
        window_seconds=60,
    ))],
)
async def login_json(
    body: LoginRequest,
    session: AsyncSession = Depends(get_session),
) -> TokenResponse:
    """JSON body alternative to the OAuth2 form login."""
    svc = AuthService(session)
    return await svc.login(username=body.username, password=body.password)


# ── Refresh token ─────────────────────────────────────────────────────────────

@router.post(
    "/refresh",
    response_model=TokenResponse,
    summary="Rotate refresh token and obtain a new access token",
    dependencies=[Depends(rate_limit(
        max_requests=settings.RATE_LIMIT_AUTH,
        window_seconds=60,
    ))],
)
async def refresh_token(
    body: RefreshRequest,
    session: AsyncSession = Depends(get_session),
) -> TokenResponse:
    """
    Exchange a valid refresh token for a new access + refresh token pair.
    The old refresh token is revoked immediately (rotation).
    """
    svc = AuthService(session)
    return await svc.refresh_access_token(body.refresh_token)


# ── Logout ────────────────────────────────────────────────────────────────────

@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    response_model=None,
    summary="Revoke refresh token",
    dependencies=[AnyRole],
)
async def logout(
    body: RefreshRequest,
    session: AsyncSession = Depends(get_session),
) -> None:
    """Invalidate the provided refresh token. Access tokens expire naturally."""
    svc = AuthService(session)
    await svc.logout(body.refresh_token)


# ── Register ──────────────────────────────────────────────────────────────────

@router.post(
    "/register",
    response_model=UserOut,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user (Admin only for admin role assignment)",
    dependencies=[Depends(rate_limit(
        max_requests=settings.RATE_LIMIT_AUTH,
        window_seconds=60,
    ))],
)
async def register(
    body: UserCreate,
    session: AsyncSession = Depends(get_session),
) -> UserOut:
    """
    Create a new FraudShield user account.
    - Anyone can register with 'analyst' or 'auditor' role.
    - Only an authenticated admin can create another admin.
    """
    svc = AuthService(session)
    user = await svc.register(body)
    return UserOut.model_validate(user)


# ── Current user ──────────────────────────────────────────────────────────────

@router.get(
    "/me",
    response_model=UserOut,
    summary="Return the authenticated user's profile",
    dependencies=[AnyRole],
)
async def me(
    current_user: User = Depends(get_current_user),
) -> UserOut:
    """Return profile information for the currently authenticated user."""
    return UserOut.model_validate(current_user)


# ── Change password ───────────────────────────────────────────────────────────

@router.post(
    "/change-password",
    status_code=status.HTTP_204_NO_CONTENT,
    response_model=None,
    summary="Change the authenticated user's password",
    dependencies=[AnyRole],
)
async def change_password(
    body: PasswordChange,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> None:
    """
    Change your own password. Requires the current password for verification.
    All existing refresh tokens should be revoked after a password change.
    """
    if not verify_password(body.current_password, current_user.hashed_password):
        raise AuthenticationError("Current password is incorrect.")

    repo = UserRepository(session)
    await repo.update(current_user, hashed_password=hash_password(body.new_password))
    log.info(f"Password changed for user: {current_user.username}")
