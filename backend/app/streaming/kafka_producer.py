"""
FraudShield — Kafka Producer
Async event producer with:
  - Automatic retry with exponential back-off
  - Dead-letter queue on max retry exhaustion
  - Topic auto-creation (dev mode)
  - Graceful degradation when Kafka unavailable
"""

from __future__ import annotations

import asyncio
import json
from typing import Optional

from app.core.logging import get_logger
from app.core.config import settings
from app.streaming.event_schemas import StreamEvent, DLQEvent

log = get_logger("streaming.kafka_producer")

# ── Topic definitions ─────────────────────────────────────────────────────────
TOPICS = {
    "transactions": "fraudshield.transactions",
    "alerts":       "fraudshield.alerts",
    "metrics":      "fraudshield.metrics",
    "system":       "fraudshield.system",
    "dlq":          "fraudshield.dlq",
    "replay":       "fraudshield.replay",
}

MAX_RETRIES    = 3
RETRY_BASE_MS  = 200   # ms, doubled on each attempt


class KafkaEventProducer:
    """
    Async Kafka producer wrapping aiokafka.
    Falls back to Redis Pub/Sub when Kafka is unavailable.
    """

    def __init__(self):
        self._producer = None
        self._available = False
        self._fallback_mode = False   # use Redis pub/sub directly

    async def start(self) -> None:
        """Initialize Kafka producer connection."""
        if not settings.KAFKA_ENABLED:
            log.info("Kafka disabled — using Redis Pub/Sub fallback for all events.")
            self._fallback_mode = True
            return
        try:
            from aiokafka import AIOKafkaProducer
            self._producer = AIOKafkaProducer(
                bootstrap_servers=settings.KAFKA_BOOTSTRAP_SERVERS,
                value_serializer=lambda v: json.dumps(v).encode("utf-8"),
                acks="all",                       # wait for all replicas
                enable_idempotence=True,          # exactly-once semantics
                request_timeout_ms=10_000,
                retry_backoff_ms=RETRY_BASE_MS,
                max_in_flight_requests_per_connection=1,
            )
            await self._producer.start()
            self._available = True
            log.info(f"Kafka producer connected → {settings.KAFKA_BOOTSTRAP_SERVERS}")
        except ImportError:
            log.warning("aiokafka not installed — falling back to Redis Pub/Sub.")
            self._fallback_mode = True
        except Exception as exc:
            log.warning(f"Kafka unavailable ({exc}) — falling back to Redis Pub/Sub.")
            self._fallback_mode = True

    async def stop(self) -> None:
        if self._producer:
            await self._producer.stop()
            self._available = False
            log.info("Kafka producer stopped.")

    # ── Public API ────────────────────────────────────────────────────────────

    async def publish(self, event: StreamEvent, topic_key: str = "transactions") -> bool:
        """
        Publish a StreamEvent to Kafka (or Redis fallback).
        Returns True on success.
        """
        if self._fallback_mode or not self._available:
            return await self._publish_redis(event)
        return await self._publish_kafka(event, topic_key)

    async def publish_to_dlq(self, failed_event: StreamEvent, error: str, topic: str) -> None:
        """Route a permanently-failed event to the dead-letter queue."""
        dlq_event = DLQEvent.from_failed(failed_event, error=error, failed_topic=topic)
        log.warning(
            f"DLQ ← event_id={failed_event.event_id} "
            f"type={failed_event.event_type} error={error}"
        )
        if self._fallback_mode:
            await self._publish_redis(dlq_event, channel="dlq")
        else:
            await self._publish_kafka(dlq_event, "dlq")

    # ── Internal ──────────────────────────────────────────────────────────────

    async def _publish_kafka(
        self,
        event: StreamEvent,
        topic_key: str,
        attempt: int = 0,
    ) -> bool:
        topic = TOPICS.get(topic_key, TOPICS["transactions"])
        try:
            payload = json.loads(event.model_dump_json())
            await self._producer.send_and_wait(topic, payload)
            return True
        except Exception as exc:
            if attempt < MAX_RETRIES:
                wait_ms = RETRY_BASE_MS * (2 ** attempt)
                log.warning(
                    f"Kafka send failed (attempt {attempt + 1}/{MAX_RETRIES}): {exc}. "
                    f"Retrying in {wait_ms}ms…"
                )
                event.retry_count = attempt + 1
                await asyncio.sleep(wait_ms / 1000)
                return await self._publish_kafka(event, topic_key, attempt + 1)
            else:
                log.error(f"Kafka send permanently failed after {MAX_RETRIES} retries: {exc}")
                await self.publish_to_dlq(event, str(exc), topic)
                # Still try Redis so the event reaches WebSocket clients
                return await self._publish_redis(event)

    async def _publish_redis(
        self,
        event: StreamEvent,
        channel: Optional[str] = None,
    ) -> bool:
        """Publish directly to Redis Pub/Sub (fallback path)."""
        try:
            from app.core.redis import get_redis_client
            from app.streaming.redis_pubsub import REDIS_CHANNELS

            ch_key = channel or _event_type_to_channel_key(event.event_type)
            redis_channel = REDIS_CHANNELS.get(ch_key, REDIS_CHANNELS["transactions"])
            client = await get_redis_client()
            await client.publish(redis_channel, event.model_dump_json())
            return True
        except Exception as exc:
            log.error(f"Redis publish fallback also failed: {exc}")
            return False


def _event_type_to_channel_key(event_type) -> str:
    t = str(event_type)
    if t.startswith("transaction"):
        return "transactions"
    if t.startswith("fraud"):
        return "alerts"
    if t.startswith("metrics"):
        return "metrics"
    return "system"


# ── Singleton ─────────────────────────────────────────────────────────────────
kafka_producer = KafkaEventProducer()
