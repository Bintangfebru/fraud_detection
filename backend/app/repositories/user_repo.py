"""User repository — data access layer for the users table."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select

from app.models.user import User
from app.repositories.base import BaseRepository


class UserRepository(BaseRepository[User]):
    model = User

    async def get_by_username(self, username: str) -> Optional[User]:
        result = await self.session.execute(
            select(User).where(User.username == username)
        )
        return result.scalar_one_or_none()

    async def get_by_email(self, email: str) -> Optional[User]:
        result = await self.session.execute(
            select(User).where(User.email == email)
        )
        return result.scalar_one_or_none()

    async def username_exists(self, username: str) -> bool:
        return await self.get_by_username(username) is not None

    async def email_exists(self, email: str) -> bool:
        return await self.get_by_email(email) is not None

    async def touch_last_login(self, user: User) -> None:
        user.last_login = datetime.now(timezone.utc)
        await self.session.flush()

    async def deactivate(self, user: User) -> User:
        user.is_active = False
        await self.session.flush()
        return user
