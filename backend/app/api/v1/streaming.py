"""
FraudShield — WebSocket & Streaming API Endpoints

WebSocket endpoints:
  WS  /api/v1/stream/ws           — full event firehose (auth via ?token=)
  WS  /api/v1/stream/ws/{channel} — channel-specific stream

REST control endpoints:
  GET /api/v1/stream/status       — streaming system health
  GET /api/v1/stream/connections  — active WS connections (admin only)
  POST /api/v1/stream/replay      — trigger event replay for caller
  GET /api/v1/stream/dlq          — dead-letter queue stats
  POST /api/v1/stream/dlq/retry   — retry DLQ events
  GET /api/v1/stream/buffer/stats — replay buffer stats
"""

from __future__ import annotations

import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, Query, WebSocket, WebSocketDisconnect, status
from fastapi.responses import JSONResponse
from starlette.websockets import WebSocketState

from app.api.deps import AdminOnly, AnyRole, get_current_user
from app.core.logging import get_logger
from app.models.user import User
from app.streaming.connection_manager import ws_manager, VALID_CHANNELS
from app.streaming.kafka_producer import kafka_producer
from app.streaming.kafka_consumer import kafka_consumer, event_replay
from app.streaming.redis_pubsub import redis_pubsub_bridge
from app.streaming.metrics_aggregator import metrics_aggregator

router = APIRouter(prefix="/stream", tags=["Real-Time Streaming"])
log = get_logger("api.streaming")


# ── WebSocket — full firehose ─────────────────────────────────────────────────

@router.websocket("/ws")
async def websocket_firehose(
    websocket: WebSocket,
    token: Optional[str] = Query(None),
    channels: Optional[str] = Query(None, description="Comma-separated: transactions,alerts,metrics,system"),
):
    """
    WebSocket firehose endpoint.
    Auth: pass JWT via ?token=<access_token>  OR  Authorization header.
    Channels: ?channels=transactions,alerts   (default: all)
    """
    client_id = str(uuid.uuid4())
    user_id: Optional[str] = None

    # ── Token validation ──────────────────────────────────────────────────────
    if token:
        try:
            from app.core.security import decode_access_token
            payload = decode_access_token(token)
            user_id = payload.get("sub")
        except Exception:
            await websocket.close(code=4001, reason="Invalid token")
            return

    # ── Channel parsing ───────────────────────────────────────────────────────
    requested_channels = set()
    if channels:
        for ch in channels.split(","):
            ch = ch.strip().lower()
            if ch in VALID_CHANNELS:
                requested_channels.add(ch)

    if not requested_channels:
        requested_channels = {"all"}

    # ── Connect ───────────────────────────────────────────────────────────────
    await ws_manager.connect(
        websocket,
        client_id=client_id,
        channels=requested_channels,
        user=user_id,
    )
    log.info(f"WS firehose: client={client_id} user={user_id} channels={requested_channels}")

    try:
        while True:
            # Keep the connection alive; handle client messages (ping/replay)
            try:
                msg = await websocket.receive_json()
                await _handle_client_message(client_id, msg)
            except WebSocketDisconnect:
                break
            except Exception:
                # receive can throw on close
                break
    finally:
        await ws_manager.disconnect(client_id)


# ── WebSocket — channel-specific ──────────────────────────────────────────────

@router.websocket("/ws/{channel}")
async def websocket_channel(
    websocket: WebSocket,
    channel: str,
    token: Optional[str] = Query(None),
):
    """Subscribe to a single channel: transactions | alerts | metrics | system"""
    if channel not in VALID_CHANNELS:
        await websocket.close(code=4004, reason=f"Unknown channel: {channel}")
        return

    client_id = str(uuid.uuid4())
    user_id: Optional[str] = None

    if token:
        try:
            from app.core.security import decode_access_token
            payload = decode_access_token(token)
            user_id = payload.get("sub")
        except Exception:
            await websocket.close(code=4001, reason="Invalid token")
            return

    await ws_manager.connect(
        websocket,
        client_id=client_id,
        channels={channel},
        user=user_id,
    )

    try:
        while True:
            try:
                msg = await websocket.receive_json()
                await _handle_client_message(client_id, msg)
            except WebSocketDisconnect:
                break
            except Exception:
                break
    finally:
        await ws_manager.disconnect(client_id)


# ── Client-message handler (bi-directional commands) ─────────────────────────

async def _handle_client_message(client_id: str, msg: dict) -> None:
    """Handle commands sent by the WebSocket client."""
    action = msg.get("action")

    if action == "ping":
        await ws_manager.send_to_client(client_id, {"type": "pong"})

    elif action == "replay":
        last_n = min(int(msg.get("last_n", 50)), 200)
        event_types = msg.get("event_types")
        asyncio.create_task(
            event_replay.replay(client_id, last_n=last_n, event_types=event_types)
        )

    elif action == "subscribe":
        channels = set(msg.get("channels", []))
        if client_id in ws_manager._connections:
            conn = ws_manager._connections[client_id]
            new_channels = channels & VALID_CHANNELS
            for ch in new_channels:
                conn.channels.add(ch)
                ws_manager._channel_index[ch].add(client_id)
            await ws_manager.send_to_client(client_id, {
                "type": "subscribed",
                "channels": list(conn.channels)
            })


# ── REST control endpoints ────────────────────────────────────────────────────

@router.get("/status", summary="Streaming system status")
async def streaming_status():
    """Returns health of all streaming components."""
    ws_stats      = ws_manager.get_stats()
    consumer_stats = kafka_consumer.stats
    pubsub_stats   = redis_pubsub_bridge.stats
    buffer_stats   = await event_replay.get_buffer_stats()

    return {
        "websocket":      ws_stats,
        "kafka_consumer": consumer_stats,
        "redis_pubsub":   pubsub_stats,
        "replay_buffer":  buffer_stats,
        "tps_current":    round(metrics_aggregator.current_tps, 2),
    }


@router.get(
    "/connections",
    summary="Active WebSocket connections",
    dependencies=[AdminOnly],
)
async def list_connections():
    return {
        "connections": ws_manager.get_connection_list(),
        "total": ws_manager.active_connections,
    }


@router.post("/replay", summary="Replay recent events to caller")
async def trigger_replay(
    last_n: int = Query(50, ge=1, le=200),
    event_types: Optional[str] = Query(None, description="Comma-separated event types"),
    client_id: Optional[str] = Query(None, description="Target WS client ID"),
):
    """
    Triggers replay of the last N buffered events.
    If client_id not given, broadcasts to all metrics-channel subscribers.
    """
    types = event_types.split(",") if event_types else None
    if client_id:
        replayed = await event_replay.replay(client_id, last_n=last_n, event_types=types)
        return {"replayed": replayed, "target": client_id}
    return {"message": "Specify client_id for targeted replay"}


@router.get("/dlq/stats", summary="Dead-letter queue statistics")
async def dlq_stats():
    try:
        from app.core.redis import get_redis_client
        client = await get_redis_client()
        dlq_len = await client.llen("fs:dlq:events")
        return {
            "dlq_size": dlq_len,
            "consumer_dlq_count": kafka_consumer.stats["dlq_count"],
        }
    except Exception as exc:
        return {"error": str(exc), "dlq_size": 0}


@router.post("/dlq/retry", summary="Retry DLQ events", dependencies=[AdminOnly])
async def retry_dlq(max_events: int = Query(10, ge=1, le=100)):
    """Re-publish up to N events from DLQ back into the main stream."""
    try:
        from app.core.redis import get_redis_client
        import json
        client = await get_redis_client()
        retried = 0
        for _ in range(max_events):
            raw = await client.rpop("fs:dlq:events")
            if not raw:
                break
            try:
                event = StreamEvent.model_validate_json(raw)
                event.retry_count = 0  # reset for fresh attempt
                await kafka_producer.publish(event)
                retried += 1
            except Exception as exc:
                log.warning(f"DLQ retry parse error: {exc}")
        return {"retried": retried}
    except Exception as exc:
        return JSONResponse(
            status_code=500,
            content={"error": str(exc)}
        )


@router.get("/buffer/stats", summary="Event replay buffer statistics")
async def buffer_stats():
    return await event_replay.get_buffer_stats()


# ── Missing import fix ────────────────────────────────────────────────────────
import asyncio
from app.streaming.event_schemas import StreamEvent
