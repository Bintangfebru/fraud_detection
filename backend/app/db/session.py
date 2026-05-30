"""
FraudShield — Async Database Session
Engine + session factory using SQLAlchemy 2.0 async API.
"""

from __future__ import annotations

from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import settings
from app.core.logging import get_logger

log = get_logger("db.session")

# ── Engine ────────────────────────────────────────────────────────────────────

engine = create_async_engine(
    settings.database_url_async,
    echo=settings.DB_ECHO,
    pool_size=settings.DB_POOL_SIZE,
    max_overflow=settings.DB_MAX_OVERFLOW,
    pool_pre_ping=settings.DB_POOL_PRE_PING,
    # Connection recycling (8 hrs) prevents stale connections
    pool_recycle=28_800,
)

# ── Session factory ───────────────────────────────────────────────────────────

AsyncSessionFactory = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False,
)


# ── FastAPI dependency ────────────────────────────────────────────────────────

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Yield an async DB session per request.
    Automatically commits on success, rolls back on exception.
    """
    async with AsyncSessionFactory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


# ── Utility ───────────────────────────────────────────────────────────────────

async def check_db_connection() -> bool:
    """Health check — verify the DB is reachable."""
    from sqlalchemy import text
    try:
        async with AsyncSessionFactory() as session:
            await session.execute(text("SELECT 1"))
        return True
    except Exception as exc:
        log.error(f"DB health check failed: {exc}")
        return False
