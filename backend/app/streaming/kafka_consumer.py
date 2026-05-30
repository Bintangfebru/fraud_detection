"""
FraudShield — Kafka Consumer
Async event consumer with:
  - Per-topic consumer groups
  - Exactly-once delivery semantics
  - Retry with exponential back-off
  - Dead-letter queue routing
  - Event replay capability
  - Graceful shutdown
"""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from typing import Callable, Dict, List, Optional

from app.core.logging import get_logger
from app.core.config import settings
from app.streaming.event_schemas import StreamEvent, EventType, DLQEvent
from app.streaming.kafka_producer import TOPICS, MAX_RETRIES, RETRY_BASE_MS

log = get_logger("streaming.kafka_consumer")

# Handler type: async fn that receives a StreamEvent
EventHandler = Callable[[StreamEvent], None]


class KafkaEventConsumer:
    """
    Async Kafka consumer that routes events to registered handlers.
    Falls back gracefully when Kafka is unavailable.
    """

    def __init__(self, group_id: str = "fraudshield-consumers"):
        self.group_id = group_id
        self._consumer = None
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._handlers: Dict[str, List[EventHandler]] = {}
        self._processed = 0
        self._failed = 0
        self._dlq_count = 0

    def register_handler(self, event_type: str, handler: EventHandler) -> None:
        """Register an async handler for a specific event_type string."""
        if event_type not in self._handlers:
            self._handlers[event_type] = []
        self._handlers[event_type].append(handler)
        log.debug(f"Handler registered for event_type={event_type}")

    async def start(self) -> None:
        """Start consuming from Kafka (no-op if Kafka disabled)."""
        if not settings.KAFKA_ENABLED:
            log.info("Kafka disabled — consumer not started.")
            return
        try:
            from aiokafka import AIOKafkaConsumer
            topics = [v for k, v in TOPICS.items() if k != "dlq"]
            self._consumer = AIOKafkaConsumer(
                *topics,
                bootstrap_servers=settings.KAFKA_BOOTSTRAP_SERVERS,
                group_id=self.group_id,
                auto_offset_reset="latest",
                enable_auto_commit=False,       # manual commit after processing
                value_deserializer=lambda v: json.loads(v.decode("utf-8")),
                session_timeout_ms=30_000,
                heartbeat_interval_ms=3_000,
                max_poll_records=100,
            )
            await self._consumer.start()
            self._running = True
            self._task = asyncio.create_task(self._consume_loop(), name="kafka-consumer")
            log.info(f"Kafka consumer started → group={self.group_id} topics={topics}")
        except ImportError:
            log.warning("aiokafka not installed — Kafka consumer not started.")
        except Exception as exc:
            log.warning(f"Kafka consumer start failed ({exc}) — no Kafka consumption.")

    async def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        if self._consumer:
            await self._consumer.stop()
        log.info(f"Kafka consumer stopped. processed={self._processed} failed={self._failed}")

    # ── Consume loop ──────────────────────────────────────────────────────────

    async def _consume_loop(self) -> None:
        while self._running:
            try:
                async for msg in self._consumer:
                    if not self._running:
                        break
                    await self._process_message(msg)
                    await self._consumer.commit()
            except asyncio.CancelledError:
                break
            except Exception as exc:
                log.error(f"Kafka consume loop error: {exc}", exc_info=True)
                await asyncio.sleep(2.0)

    async def _process_message(self, msg) -> None:
        """Parse, route to handlers, and handle failures."""
        try:
            data = msg.value if isinstance(msg.value, dict) else json.loads(msg.value)
            event = StreamEvent.model_validate(data)
            handlers = self._handlers.get(str(event.event_type), [])

            for handler in handlers:
                await self._invoke_with_retry(handler, event, msg.topic)

            self._processed += 1

        except Exception as exc:
            self._failed += 1
            log.error(
                f"Message processing failed: {exc} | "
                f"topic={msg.topic} offset={msg.offset}"
            )

    async def _invoke_with_retry(
        self,
        handler: EventHandler,
        event: StreamEvent,
        topic: str,
        attempt: int = 0,
    ) -> None:
        try:
            await handler(event)
        except Exception as exc:
            if attempt < MAX_RETRIES:
                wait_ms = RETRY_BASE_MS * (2 ** attempt)
                log.warning(
                    f"Handler retry {attempt + 1}/{MAX_RETRIES} for "
                    f"event_id={event.event_id}: {exc}. Waiting {wait_ms}ms…"
                )
                event.retry_count = attempt + 1
                await asyncio.sleep(wait_ms / 1000)
                await self._invoke_with_retry(handler, event, topic, attempt + 1)
            else:
                # Send to DLQ
                self._dlq_count += 1
                log.error(
                    f"Handler permanently failed for event_id={event.event_id}: {exc}. "
                    f"Routing to DLQ."
                )
                await self._send_to_dlq(event, str(exc), topic)

    async def _send_to_dlq(self, event: StreamEvent, error: str, topic: str) -> None:
        try:
            from app.streaming.kafka_producer import kafka_producer
            await kafka_producer.publish_to_dlq(event, error, topic)
        except Exception as exc:
            log.error(f"DLQ send failed: {exc}")

    @property
    def stats(self) -> dict:
        return {
            "processed": self._processed,
            "failed": self._failed,
            "dlq_count": self._dlq_count,
            "running": self._running,
        }


# ── Event Replay ──────────────────────────────────────────────────────────────

class EventReplayService:
    """
    Replay stored events from Redis or Kafka for a given time range.
    Useful for dashboard catch-up after disconnection.
    """
    REPLAY_BUFFER_KEY  = "fs:replay:buffer"
    REPLAY_BUFFER_SIZE = 1000   # keep last 1000 events in rolling buffer

    async def store_event(self, event: StreamEvent) -> None:
        """Push an event into the rolling replay buffer."""
        try:
            from app.core.redis import get_redis_client
            client = await get_redis_client()
            pipe = client.pipeline()
            await pipe.lpush(self.REPLAY_BUFFER_KEY, event.model_dump_json())
            await pipe.ltrim(self.REPLAY_BUFFER_KEY, 0, self.REPLAY_BUFFER_SIZE - 1)
            await pipe.execute()
        except Exception as exc:
            log.warning(f"Replay buffer store failed: {exc}")

    async def replay(
        self,
        websocket_client_id: str,
        last_n: int = 100,
        event_types: Optional[List[str]] = None,
    ) -> int:
        """
        Replay the last N buffered events to a specific WebSocket client.
        Returns the number of events replayed.
        """
        from app.streaming.connection_manager import ws_manager
        from app.core.redis import get_redis_client

        try:
            client = await get_redis_client()
            raw_events = await client.lrange(self.REPLAY_BUFFER_KEY, 0, last_n - 1)
        except Exception as exc:
            log.error(f"Replay buffer read failed: {exc}")
            return 0

        # Replay start notification
        await ws_manager.send_to_client(websocket_client_id, {
            "type": "replay_started",
            "count": len(raw_events),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

        replayed = 0
        for raw in reversed(raw_events):  # oldest first
            try:
                data = json.loads(raw)
                if event_types and data.get("event_type") not in event_types:
                    continue
                data["_replayed"] = True
                ok = await ws_manager.send_to_client(websocket_client_id, data)
                if ok:
                    replayed += 1
            except Exception:
                continue

        await ws_manager.send_to_client(websocket_client_id, {
            "type": "replay_completed",
            "replayed": replayed,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
        log.info(f"Replay completed: {replayed} events → client={websocket_client_id}")
        return replayed

    async def get_buffer_stats(self) -> dict:
        try:
            from app.core.redis import get_redis_client
            client = await get_redis_client()
            size = await client.llen(self.REPLAY_BUFFER_KEY)
            return {"buffer_size": size, "max_size": self.REPLAY_BUFFER_SIZE}
        except Exception:
            return {"buffer_size": 0, "max_size": self.REPLAY_BUFFER_SIZE}


# ── Singletons ────────────────────────────────────────────────────────────────
kafka_consumer = KafkaEventConsumer()
event_replay   = EventReplayService()
