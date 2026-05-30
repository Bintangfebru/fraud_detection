"""
FraudShield — Enterprise Backend API
FastAPI application entry point.
"""

from __future__ import annotations

import time
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.v1 import api_v1_router
from app.core.config import settings
from app.core.exceptions import FraudShieldError
from app.core.logging import get_logger, setup_logging
from app.core.redis import close_redis, get_redis_client
from app.db.init_db import init_db
from app.db.session import check_db_connection
from app.middleware.correlation import CorrelationIDMiddleware
from app.middleware.exception_handler import (
    UnhandledExceptionMiddleware,
    fraudshield_exception_handler,
    http_exception_handler,
    validation_exception_handler,
)

# ── Bootstrap logging ─────────────────────────────────────────────────────────
setup_logging()
log = get_logger("main")

_START_TIME = time.monotonic()


# ── Lifespan ──────────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info(f"FraudShield {settings.APP_VERSION} starting [env={settings.APP_ENV}]")

    # ── Database ──────────────────────────────────────────────────────────────
    try:
        if not settings.is_production:
            await init_db()
            log.info("Database initialized (dev).")
        else:
            if not await check_db_connection():
                log.error("Database unreachable at startup.")
            else:
                log.info("Database connected.")
    except Exception as exc:
        log.error(f"DB init failed: {exc}", exc_info=True)

    # ── Redis ─────────────────────────────────────────────────────────────────
    try:
        redis = await get_redis_client()
        await redis.ping()
        log.info("Redis connected.")
    except Exception as exc:
        log.warning(f"Redis unavailable: {exc}")

    # ── ML Model ──────────────────────────────────────────────────────────────
    try:
        from app.ml.predictor import startup_load
        startup_load()
        log.info("ML model loaded.")
    except Exception as exc:
        log.warning(f"ML model failed: {exc}")

    # ── Streaming (optional, safe) ────────────────────────────────────────────
    try:
        from app.streaming.kafka_producer import kafka_producer
        from app.streaming.kafka_consumer import kafka_consumer
        from app.streaming.redis_pubsub import redis_pubsub_bridge
        from app.streaming.metrics_aggregator import metrics_aggregator

        await kafka_producer.start()
        await kafka_consumer.start()
        await redis_pubsub_bridge.start()
        await metrics_aggregator.start()
        log.info("Streaming pipeline started.")
    except Exception as exc:
        log.warning(f"Streaming disabled: {exc}")

    if not settings.is_production:
        await _ensure_default_admin()

    log.info("Startup complete.")
    yield

    # ── Shutdown ──────────────────────────────────────────────────────────────
    try:
        from app.streaming.kafka_producer import kafka_producer
        from app.streaming.kafka_consumer import kafka_consumer
        from app.streaming.redis_pubsub import redis_pubsub_bridge
        from app.streaming.metrics_aggregator import metrics_aggregator

        await metrics_aggregator.stop()
        await redis_pubsub_bridge.stop()
        await kafka_consumer.stop()
        await kafka_producer.stop()
        log.info("Streaming stopped.")
    except Exception as exc:
        log.warning(f"Streaming shutdown error: {exc}")

    await close_redis()
    log.info("Shutdown complete.")


# ── App Factory ───────────────────────────────────────────────────────────────
def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        lifespan=lifespan,
        docs_url="/docs" if not settings.is_production else None,
        redoc_url="/redoc" if not settings.is_production else None,
        openapi_url="/openapi.json" if not settings.is_production else None,
    )

    # ── Middleware ────────────────────────────────────────────────────────────
    app.add_middleware(UnhandledExceptionMiddleware)
    app.add_middleware(CorrelationIDMiddleware)

    allowed_origins = settings.ALLOWED_ORIGINS or [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]

    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=[
            "X-Correlation-ID",
            "X-RateLimit-Limit",
            "X-RateLimit-Remaining",
            "X-RateLimit-Reset",
        ],
    )

    # ── Exception Handlers ────────────────────────────────────────────────────
    app.add_exception_handler(FraudShieldError, fraudshield_exception_handler)
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)

    # ── Routes ────────────────────────────────────────────────────────────────
    app.include_router(api_v1_router)

    @app.get("/", include_in_schema=False)
    async def root():
        return {
            "service": settings.APP_NAME,
            "status": "ok",
            "env": settings.APP_ENV,
        }

    @app.get("/health")
    async def health():
        uptime = round(time.monotonic() - _START_TIME, 1)
        return {
            "status": "ok",
            "uptime": uptime,
        }

    return app


app = create_app()


# ── Dev Helper ────────────────────────────────────────────────────────────────
async def _ensure_default_admin():
    from app.db.session import AsyncSessionFactory
    from app.core.security import hash_password
    from app.models.user import User
    from sqlalchemy import select

    async with AsyncSessionFactory() as session:
        result = await session.execute(
            select(User).where(User.username == "admin")
        )
        if not result.scalar_one_or_none():
            session.add(
                User(
                    username="admin",
                    email="admin@fraudshield.local",
                    hashed_password=hash_password("Admin1234!"),
                    role="admin",
                )
            )
            await session.commit()
            log.info("Default admin created.")


# ── Run ───────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG,
    )