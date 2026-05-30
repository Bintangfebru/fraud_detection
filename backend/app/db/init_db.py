"""
FraudShield — Database Initialization
Creates tables if they don't exist (dev/test convenience).
In production, use Alembic migrations instead.
"""

from __future__ import annotations

from app.core.logging import get_logger
from app.db.base import Base
from app.db.session import engine

log = get_logger("db.init")

# Import all models so Base.metadata is populated
import app.models  # noqa: F401


async def init_db() -> None:
    """Create all tables. Safe to call on every startup."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    log.info("Database tables initialized.")


async def drop_all_tables() -> None:
    """Drop all tables — only for test environments!"""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    log.warning("All database tables dropped.")
