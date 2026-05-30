"""
FraudShield — Base Repository
Generic async CRUD operations. All domain repositories inherit from this.
"""

from __future__ import annotations

from typing import Any, Generic, List, Optional, Type, TypeVar

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import Base

ModelT = TypeVar("ModelT", bound=Base)


class BaseRepository(Generic[ModelT]):
    """
    Async repository providing generic CRUD.

    Usage:
        class UserRepository(BaseRepository[User]):
            model = User
    """

    model: Type[ModelT]

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_id(self, obj_id: str) -> Optional[ModelT]:
        return await self.session.get(self.model, obj_id)

    async def get_all(
        self,
        offset: int = 0,
        limit: int = 50,
    ) -> List[ModelT]:
        result = await self.session.execute(
            select(self.model).offset(offset).limit(limit)
        )
        return list(result.scalars().all())

    async def count(self) -> int:
        result = await self.session.execute(
            select(func.count()).select_from(self.model)
        )
        return result.scalar_one()

    async def create(self, obj: ModelT) -> ModelT:
        self.session.add(obj)
        await self.session.flush()
        return obj

    async def update(self, obj: ModelT, **fields: Any) -> ModelT:
        for key, value in fields.items():
            setattr(obj, key, value)
        await self.session.flush()
        return obj

    async def delete(self, obj: ModelT) -> None:
        await self.session.delete(obj)
        await self.session.flush()

    async def bulk_create(self, objs: List[ModelT]) -> List[ModelT]:
        self.session.add_all(objs)
        await self.session.flush()
        return objs
