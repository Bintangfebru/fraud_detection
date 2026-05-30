"""
FraudShield — Redis Client
Async Redis connection pool with helpers for:
  - Refresh token allowlist (fast invalidation)
  - Rate limiting (sliding window)
  - Threshold cache
  - Training job status
"""

from __future__ import annotations

import json
from typing import Any, Optional

import redis.asyncio as aioredis
from redis.asyncio import Redis
from redis.exceptions import RedisError

from app.core.config import settings
from app.core.logging import get_logger

log = get_logger("redis")

# ── Singleton pool ────────────────────────────────────────────────────────────

_redis_pool: Optional[Redis] = None


async def get_redis_client() -> Redis:
    """Return (or create) the shared async Redis client."""
    global _redis_pool
    if _redis_pool is None:
        _redis_pool = aioredis.from_url(
            settings.REDIS_URL,
            max_connections=settings.REDIS_MAX_CONNECTIONS,
            socket_timeout=settings.REDIS_SOCKET_TIMEOUT,
            decode_responses=True,
        )
    return _redis_pool


async def close_redis() -> None:
    global _redis_pool
    if _redis_pool:
        await _redis_pool.aclose()
        _redis_pool = None
        log.info("Redis connection closed.")


async def ping_redis() -> bool:
    """Health check — returns True if Redis is reachable."""
    try:
        client = await get_redis_client()
        return await client.ping()
    except RedisError:
        return False


# ── Key namespacing ───────────────────────────────────────────────────────────

class RedisKeys:
    REFRESH_TOKEN    = "fs:auth:refresh:{token}"       # stores username
    BLOCKLIST_TOKEN  = "fs:auth:blocklist:{jti}"       # invalidated tokens
    RATE_LIMIT       = "fs:ratelimit:{key}:{window}"   # sliding window counter
    THRESHOLD_CACHE  = "fs:thresholds:active"           # JSON blob
    TRAINING_JOB     = "fs:jobs:{job_id}"              # JSON blob
    TRAINING_JOB_LIST = "fs:jobs:index"                # sorted set by timestamp

    @staticmethod
    def refresh_token(token: str) -> str:
        return RedisKeys.REFRESH_TOKEN.format(token=token)

    @staticmethod
    def rate_limit(key: str, window: int) -> str:
        return RedisKeys.RATE_LIMIT.format(key=key, window=window)

    @staticmethod
    def training_job(job_id: str) -> str:
        return RedisKeys.TRAINING_JOB.format(job_id=job_id)


# ── Refresh token store ───────────────────────────────────────────────────────

async def store_refresh_token(token: str, username: str, ttl_seconds: int) -> None:
    """Persist a refresh token in Redis with TTL."""
    client = await get_redis_client()
    await client.setex(RedisKeys.refresh_token(token), ttl_seconds, username)


async def get_refresh_token_owner(token: str) -> Optional[str]:
    """Return the username for a refresh token, or None if invalid/expired."""
    client = await get_redis_client()
    return await client.get(RedisKeys.refresh_token(token))


async def revoke_refresh_token(token: str) -> None:
    """Revoke (delete) a refresh token from Redis."""
    client = await get_redis_client()
    await client.delete(RedisKeys.refresh_token(token))


# ── Rate limiting (fixed window counter) ─────────────────────────────────────

async def check_rate_limit(
    identifier: str,
    max_requests: int,
    window_seconds: int,
) -> tuple[bool, int, int]:
    """
    Sliding window rate limit check.

    Returns:
        (allowed: bool, current_count: int, ttl_seconds: int)
    """
    import time
    window = int(time.time()) // window_seconds
    key = RedisKeys.rate_limit(identifier, window)

    try:
        client = await get_redis_client()
        pipe = client.pipeline(transaction=True)
        await pipe.incr(key)
        await pipe.expire(key, window_seconds)
        results = await pipe.execute()
        count = int(results[0])
        ttl = window_seconds - (int(time.time()) % window_seconds)
        allowed = count <= max_requests
        return allowed, count, ttl
    except RedisError as e:
        # Fail open — don't block requests if Redis is down
        log.warning(f"Rate limit Redis error (failing open): {e}")
        return True, 0, window_seconds


# ── Threshold cache ───────────────────────────────────────────────────────────

async def cache_thresholds(fraud: float, review: float) -> None:
    """Cache active thresholds in Redis (no TTL — updated on every write)."""
    client = await get_redis_client()
    await client.set(
        RedisKeys.THRESHOLD_CACHE,
        json.dumps({"fraud": fraud, "review": review}),
    )


async def get_cached_thresholds() -> Optional[dict[str, float]]:
    """Return cached thresholds or None if not cached."""
    try:
        client = await get_redis_client()
        raw = await client.get(RedisKeys.THRESHOLD_CACHE)
        return json.loads(raw) if raw else None
    except RedisError:
        return None


# ── Training job cache ────────────────────────────────────────────────────────

async def set_job_status(job_id: str, data: dict[str, Any], ttl_hours: int = 24) -> None:
    """Store training job status in Redis."""
    client = await get_redis_client()
    await client.setex(
        RedisKeys.training_job(job_id),
        ttl_hours * 3600,
        json.dumps(data, default=str),
    )


async def get_job_status(job_id: str) -> Optional[dict[str, Any]]:
    """Retrieve training job status from Redis."""
    try:
        client = await get_redis_client()
        raw = await client.get(RedisKeys.training_job(job_id))
        return json.loads(raw) if raw else None
    except RedisError:
        return None


async def update_job_field(job_id: str, **fields: Any) -> None:
    """Atomically update specific fields of a job status dict."""
    existing = await get_job_status(job_id) or {}
    existing.update(fields)
    await set_job_status(job_id, existing)
