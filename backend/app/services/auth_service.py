"""
FraudShield — Auth Service
Business logic for registration, login, token refresh, and logout.
"""

from __future__ import annotations

from datetime import timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import (
    AuthenticationError,
    ConflictError,
    InactiveUserError,
    InvalidTokenError,
)
from app.core.logging import get_logger
from app.core.redis import (
    get_cached_thresholds,
    get_refresh_token_owner,
    revoke_refresh_token,
    store_refresh_token,
)
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_refresh_token,
    hash_password,
    verify_password,
)
from app.models.user import User
from app.repositories.user_repo import UserRepository
from app.schemas.auth import TokenResponse, UserCreate

log = get_logger("services.auth")


class AuthService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = UserRepository(session)

    async def register(self, data: UserCreate) -> User:
        if await self.repo.username_exists(data.username):
            raise ConflictError(f"Username '{data.username}' is already taken.")
        if await self.repo.email_exists(data.email):
            raise ConflictError(f"Email '{data.email}' is already registered.")

        user = User(
            username=data.username,
            email=data.email,
            hashed_password=hash_password(data.password),
            role=data.role,
        )
        await self.repo.create(user)
        log.info(f"New user registered: {data.username} role={data.role}")
        return user

    async def login(self, username: str, password: str) -> TokenResponse:
        user = await self.repo.get_by_username(username)
        if not user or not verify_password(password, user.hashed_password):
            raise AuthenticationError("Invalid username or password.")
        if not user.is_active:
            raise InactiveUserError()

        await self.repo.touch_last_login(user)

        access_token = create_access_token(subject=user.username, role=user.role)
        refresh_token = create_refresh_token(subject=user.username, role=user.role)

        # Persist refresh token in Redis with TTL
        ttl = int(timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS).total_seconds())
        await store_refresh_token(refresh_token, user.username, ttl)

        log.info(f"User logged in: {user.username}")
        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            role=user.role,
        )

    async def refresh_access_token(self, refresh_token: str) -> TokenResponse:
        # Validate JWT structure
        payload = decode_refresh_token(refresh_token)
        username = payload["sub"]

        # Check token is in Redis allowlist (revocation check)
        owner = await get_refresh_token_owner(refresh_token)
        if not owner or owner != username:
            raise InvalidTokenError("Refresh token has been revoked or is invalid.")

        # Fetch user
        user = await self.repo.get_by_username(username)
        if not user or not user.is_active:
            raise InvalidTokenError("User no longer active.")

        # Issue new access token (token rotation — revoke old refresh, issue new one)
        await revoke_refresh_token(refresh_token)
        new_refresh = create_refresh_token(subject=user.username, role=user.role)
        ttl = int(timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS).total_seconds())
        await store_refresh_token(new_refresh, user.username, ttl)

        new_access = create_access_token(subject=user.username, role=user.role)
        return TokenResponse(
            access_token=new_access,
            refresh_token=new_refresh,
            expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            role=user.role,
        )

    async def logout(self, refresh_token: str) -> None:
        await revoke_refresh_token(refresh_token)
        log.info("User logged out — refresh token revoked.")
