"""
FraudShield — Metrics Aggregator
Runs as a background task: every N seconds it queries the DB + Redis
and publishes a MetricsEvent to all WebSocket dashboard clients.
"""

from __future__ import annotations

import asyncio
import time
from collections import deque
from datetime import datetime, timezone
from typing import Deque

from app.core.logging import get_logger
from app.streaming.event_schemas import MetricsEvent

log = get_logger("streaming.metrics")

# Rolling windows for TPS and latency
_WINDOW_SIZE = 60   # samples kept for rolling average


class MetricsAggregator:
    """
    Collects per-prediction stats and periodically emits MetricsEvents.
    Thread-safe via asyncio.
    """

    def __init__(self, publish_interval_sec: float = 5.0):
        self._interval = publish_interval_sec
        self._task: asyncio.Task | None = None
        self._running = False

        # Rolling buffers
        self._risk_scores:  Deque[float] = deque(maxlen=_WINDOW_SIZE)
        self._latencies:    Deque[float] = deque(maxlen=_WINDOW_SIZE)
        self._txn_times:    Deque[float] = deque(maxlen=_WINDOW_SIZE)  # epoch seconds
        self._fraud_window: Deque[bool]  = deque(maxlen=_WINDOW_SIZE)

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    async def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._publish_loop(), name="metrics-aggregator")
        log.info(f"Metrics aggregator started (interval={self._interval}s).")

    async def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    # ── Ingest ────────────────────────────────────────────────────────────────

    def record_prediction(
        self,
        risk_score: float,
        latency_ms: float,
        is_fraud: bool,
    ) -> None:
        """Called from FraudService after each prediction."""
        self._risk_scores.append(risk_score)
        self._latencies.append(latency_ms)
        self._txn_times.append(time.monotonic())
        self._fraud_window.append(is_fraud)

    # ── Publish loop ──────────────────────────────────────────────────────────

    async def _publish_loop(self) -> None:
        while self._running:
            try:
                await asyncio.sleep(self._interval)
                await self._emit()
            except asyncio.CancelledError:
                break
            except Exception as exc:
                log.warning(f"Metrics publish error: {exc}")

    async def _emit(self) -> None:
        from app.streaming.redis_pubsub import redis_pubsub_bridge
        from app.streaming.kafka_consumer import event_replay
        from app.db.session import AsyncSessionFactory

        # ── TPS: transactions in the last 10 s ───────────────────────────────
        now = time.monotonic()
        recent = [t for t in self._txn_times if now - t <= 10]
        tps = len(recent) / 10.0

        # ── Rolling averages ─────────────────────────────────────────────────
        avg_risk = (
            sum(self._risk_scores) / len(self._risk_scores)
            if self._risk_scores else 0.0
        )
        avg_lat = (
            sum(self._latencies) / len(self._latencies)
            if self._latencies else 0.0
        )

        # ── DB snapshot ───────────────────────────────────────────────────────
        total = fraud = review = alerts = 0
        try:
            async with AsyncSessionFactory() as session:
                from app.services.fraud_service import FraudService
                svc = FraudService(session)
                summary = await svc.get_analytics_summary()
                total   = summary["total_transactions"]
                fraud   = summary["fraud_count"]
                review  = summary["review_count"]
                alerts  = summary["open_alerts"]
        except Exception as exc:
            log.warning(f"Metrics DB query failed: {exc}")

        event = MetricsEvent.build(
            total_transactions=total,
            fraud_count=fraud,
            review_count=review,
            safe_count=max(0, total - fraud - review),
            open_alerts=alerts,
            fraud_rate=fraud / max(1, total),
            tps=tps,
            avg_risk_score=avg_risk,
            avg_latency_ms=avg_lat,
        )

        await redis_pubsub_bridge.publish(event)
        await event_replay.store_event(event)

    @property
    def current_tps(self) -> float:
        now = time.monotonic()
        recent = [t for t in self._txn_times if now - t <= 10]
        return len(recent) / 10.0


# ── Singleton ─────────────────────────────────────────────────────────────────
metrics_aggregator = MetricsAggregator(publish_interval_sec=5.0)
