"""
Alembic env.py — FraudShield
Supports both online (async, direct DB) and offline (SQL script) modes.
Reads the database URL from app.core.config.settings so the single .env
file is the only source of truth.
"""

from __future__ import annotations

import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

# ── Alembic config object ─────────────────────────────────────────────────────
config = context.config

# ── Logging ───────────────────────────────────────────────────────────────────
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# ── Import all models so metadata is populated ────────────────────────────────
# This import triggers all model definitions and associates them with Base.metadata.
from app.db.base import Base
import app.models  # noqa: F401 — registers all ORM models

target_metadata = Base.metadata

# ── Override sqlalchemy.url with app settings ─────────────────────────────────
# This ensures Alembic always uses the same DB URL as the running application.
from app.core.config import settings as _settings

config.set_main_option("sqlalchemy.url", _settings.database_url_sync)


# ── Offline mode ──────────────────────────────────────────────────────────────

def run_migrations_offline() -> None:
    """
    Run migrations in 'offline' mode.
    Generates SQL statements without an actual DB connection.
    Useful for generating migration scripts to apply manually.
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
    )
    with context.begin_transaction():
        context.run_migrations()


# ── Online mode (async) ───────────────────────────────────────────────────────

def do_run_migrations(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
        compare_server_default=True,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Run migrations in async online mode using asyncpg."""
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """Entry point for online migration mode."""
    asyncio.run(run_async_migrations())


# ── Dispatch ──────────────────────────────────────────────────────────────────

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
