"""
FraudShield — Redis Pub/Sub Bridge
Subscribes to Redis channels and fans-out to WebSocket clients.
Acts as the last-mile delivery layer: Kafka → Redis → WebSocket.
Also provides direct-publish API when Kafka is unavailable.
"""

from __future__ import annotations

import asyncio
import json
from typing import Optional

from app.core.logging import get_logger
from app.streaming.event_schemas import StreamEvent, EventType

log = get_logger("streaming.redis_pubsub")

# ── Channel names ─────────────────────────────────────────────────────────────
REDIS_CHANNELS = {
    "transactions": "fs:stream:transactions",
    "alerts":       "fs:stream:alerts",
    "metrics":      "fs:stream:metrics",
    "system":       "fs:stream:system",
    "dlq":          "fs:stream:dlq",
}

ALL_CHANNELS = list(REDIS_CHANNELS.values())


class RedisPubSubBridge:
    """
    Subscribes to all Redis stream channels and re-broadcasts
    incoming messages to the WebSocket ConnectionManager.
    """

    def __init__(self):
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._message_count = 0
        self._error_count = 0

    async def start(self) -> None:
        """Start the background listener task."""
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._listen_loop(), name="redis-pubsub-bridge")
        log.info("Redis Pub/Sub bridge started.")

    async def stop(self) -> None:
        """Gracefully stop the listener."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        log.info("Redis Pub/Sub bridge stopped.")

    # ── Listener loop ─────────────────────────────────────────────────────────

    async def _listen_loop(self) -> None:
        """
        Main pub/sub listener. Reconnects on transient failures.
        Each message is parsed as a StreamEvent and broadcast to matching WS clients.
        """
        from app.core.redis import get_redis_client

        retry_delay = 1.0
        while self._running:
            pubsub = None
            try:
                client = await get_redis_client()
                # Pub/Sub needs a dedicated connection
                pubsub = client.pubsub()
                await pubsub.subscribe(*ALL_CHANNELS)
                log.info(f"Subscribed to Redis channels: {ALL_CHANNELS}")
                retry_delay = 1.0  # reset on successful connection

                async for message in pubsub.listen():
                    if not self._running:
                        break
                    if message["type"] == "message":
                        await self._dispatch(message)

            except asyncio.CancelledError:
                break
            except Exception as exc:
                self._error_count += 1
                log.error(
                    f"Redis Pub/Sub error (reconnecting in {retry_delay}s): {exc}"
                )
                await asyncio.sleep(retry_delay)
                retry_delay = min(retry_delay * 2, 30.0)  # cap at 30 s
            finally:
                if pubsub:
                    try:
                        await pubsub.unsubscribe()
                        await pubsub.aclose()
                    except Exception:
                        pass

    async def _dispatch(self, message: dict) -> None:
        """Parse a Redis message and fan-out to WebSocket clients."""
        from app.streaming.connection_manager import ws_manager

        try:
            raw = message.get("data", "")
            if isinstance(raw, bytes):
                raw = raw.decode("utf-8")

            # Detect channel
            channel_name = message.get("channel", "")
            if isinstance(channel_name, bytes):
                channel_name = channel_name.decode("utf-8")

            ws_channel = _redis_channel_to_ws(channel_name)

            # Parse and broadcast
            data = json.loads(raw)
            sent = await ws_manager.broadcast_raw(ws_channel, data)
            self._message_count += 1

            if data.get("event_type", "").startswith("fraud"):
                log.info(
                    f"Fraud event dispatched → {sent} WS clients | "
                    f"type={data.get('event_type')} ref={data.get('payload', {}).get('transaction_ref')}"
                )

        except Exception as exc:
            self._error_count += 1
            log.warning(f"Dispatch failed: {exc} | raw={str(message)[:200]}")

    # ── Direct publish (bypass Kafka) ─────────────────────────────────────────

    async def publish(self, event: StreamEvent) -> bool:
        """Directly publish an event to Redis Pub/Sub."""
        try:
            from app.core.redis import get_redis_client
            ch_key = _event_type_to_channel_key(event.event_type)
            channel = REDIS_CHANNELS.get(ch_key, REDIS_CHANNELS["transactions"])
            client = await get_redis_client()
            await client.publish(channel, event.model_dump_json())
            return True
        except Exception as exc:
            log.error(f"Redis direct publish failed: {exc}")
            return False

    @property
    def stats(self) -> dict:
        return {
            "messages_dispatched": self._message_count,
            "dispatch_errors": self._error_count,
            "running": self._running,
        }


def _redis_channel_to_ws(redis_channel: str) -> str:
    inverse = {v: k for k, v in REDIS_CHANNELS.items()}
    return inverse.get(redis_channel, "system")


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
redis_pubsub_bridge = RedisPubSubBridge()
