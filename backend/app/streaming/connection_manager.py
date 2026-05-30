"""
FraudShield — WebSocket Connection Manager
Manages all active WebSocket connections, channels, and broadcasting.

Channels:
  - "transactions"  : all scored transactions (analysts, admins)
  - "alerts"        : fraud/review alerts only
  - "metrics"       : dashboard KPI updates
  - "system"        : health & system events
  - "all"           : firehose (everything)
"""

from __future__ import annotations

import asyncio
import json
from collections import defaultdict
from datetime import datetime, timezone
from typing import Dict, Optional, Set

from fastapi import WebSocket, WebSocketDisconnect
from starlette.websockets import WebSocketState

from app.core.logging import get_logger
from app.streaming.event_schemas import StreamEvent

log = get_logger("streaming.ws_manager")

# Valid channel names
VALID_CHANNELS = {"transactions", "alerts", "metrics", "system", "all"}


class _Connection:
    """Represents a single WebSocket client."""
    __slots__ = ("ws", "client_id", "channels", "user", "connected_at")

    def __init__(
        self,
        ws: WebSocket,
        client_id: str,
        channels: Set[str],
        user: Optional[str] = None,
    ):
        self.ws = ws
        self.client_id = client_id
        self.channels = channels
        self.user = user
        self.connected_at = datetime.now(timezone.utc).isoformat()

    async def send_json(self, data: dict) -> bool:
        """Send JSON, returns False if the socket is dead."""
        try:
            if self.ws.client_state == WebSocketState.CONNECTED:
                await self.ws.send_json(data)
                return True
        except Exception:
            pass
        return False


class ConnectionManager:
    """
    Thread-safe (asyncio) WebSocket hub.

    Usage:
        await ws_manager.connect(websocket, client_id, channels={"alerts","metrics"})
        await ws_manager.broadcast_event(event)   # fan-out to subscribed channels
        await ws_manager.disconnect(client_id)
    """

    def __init__(self):
        # client_id → _Connection
        self._connections: Dict[str, _Connection] = {}
        # channel → set of client_ids
        self._channel_index: Dict[str, Set[str]] = defaultdict(set)
        self._lock = asyncio.Lock()
        self._broadcast_count = 0
        self._error_count = 0

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    async def connect(
        self,
        websocket: WebSocket,
        client_id: str,
        channels: Optional[Set[str]] = None,
        user: Optional[str] = None,
    ) -> None:
        """Accept and register a WebSocket connection."""
        await websocket.accept()
        channels = (channels or {"all"}) & VALID_CHANNELS
        if not channels:
            channels = {"all"}

        conn = _Connection(websocket, client_id, channels, user)
        async with self._lock:
            self._connections[client_id] = conn
            for ch in channels:
                self._channel_index[ch].add(client_id)

        log.info(
            f"WS connected: {client_id} | channels={channels} | "
            f"total={len(self._connections)}"
        )

        # Send welcome handshake
        await websocket.send_json({
            "type": "connected",
            "client_id": client_id,
            "channels": list(channels),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "server": "FraudShield-Streaming/2.5",
        })

    async def disconnect(self, client_id: str) -> None:
        """Remove and clean up a connection."""
        async with self._lock:
            conn = self._connections.pop(client_id, None)
            if conn:
                for ch in conn.channels:
                    self._channel_index[ch].discard(client_id)
        log.info(f"WS disconnected: {client_id} | total={len(self._connections)}")

    # ── Broadcasting ──────────────────────────────────────────────────────────

    async def broadcast_event(self, event: StreamEvent) -> int:
        """Fan-out a StreamEvent to all matching channel subscribers."""
        channel = self._event_to_channel(event.event_type)
        target_ids = self._get_recipients(channel)
        if not target_ids:
            return 0

        payload = json.loads(event.model_dump_json())
        return await self._send_to(target_ids, payload)

    async def broadcast_raw(self, channel: str, data: dict) -> int:
        """Send arbitrary JSON to a channel."""
        target_ids = self._get_recipients(channel)
        if not target_ids:
            return 0
        return await self._send_to(target_ids, data)

    async def send_to_client(self, client_id: str, data: dict) -> bool:
        """Send directly to one client."""
        conn = self._connections.get(client_id)
        if conn:
            return await conn.send_json(data)
        return False

    async def ping_all(self) -> None:
        """Heartbeat ping — prune dead connections."""
        dead: list[str] = []
        for cid, conn in list(self._connections.items()):
            ok = await conn.send_json({"type": "ping", "timestamp": datetime.now(timezone.utc).isoformat()})
            if not ok:
                dead.append(cid)
        for cid in dead:
            await self.disconnect(cid)

    # ── Stats ─────────────────────────────────────────────────────────────────

    @property
    def active_connections(self) -> int:
        return len(self._connections)

    def get_stats(self) -> dict:
        channel_counts = {
            ch: len(ids) for ch, ids in self._channel_index.items() if ids
        }
        return {
            "active_connections": self.active_connections,
            "channel_subscribers": channel_counts,
            "total_broadcasts": self._broadcast_count,
            "broadcast_errors": self._error_count,
        }

    def get_connection_list(self) -> list:
        return [
            {
                "client_id": cid,
                "channels": list(conn.channels),
                "user": conn.user,
                "connected_at": conn.connected_at,
            }
            for cid, conn in self._connections.items()
        ]

    # ── Internal ──────────────────────────────────────────────────────────────

    def _get_recipients(self, channel: str) -> Set[str]:
        """Union of exact-channel subscribers + 'all' subscribers."""
        specific = self._channel_index.get(channel, set())
        firehose = self._channel_index.get("all", set())
        return specific | firehose

    async def _send_to(self, client_ids: Set[str], data: dict) -> int:
        """Concurrent fan-out send; removes dead sockets. Returns sent count."""
        dead: list[str] = []
        tasks = []
        cid_list = list(client_ids)

        for cid in cid_list:
            conn = self._connections.get(cid)
            if conn:
                tasks.append(conn.send_json(data))

        results = await asyncio.gather(*tasks, return_exceptions=True)
        sent = 0
        for cid, result in zip(cid_list, results):
            if isinstance(result, Exception) or result is False:
                dead.append(cid)
                self._error_count += 1
            elif result:
                sent += 1

        for cid in dead:
            await self.disconnect(cid)

        self._broadcast_count += 1
        return sent

    @staticmethod
    def _event_to_channel(event_type) -> str:
        """Map EventType to a channel name."""
        t = str(event_type)
        if t.startswith("transaction"):
            return "transactions"
        if t.startswith("fraud"):
            return "alerts"
        if t.startswith("metrics"):
            return "metrics"
        return "system"


# ── Singleton ─────────────────────────────────────────────────────────────────
ws_manager = ConnectionManager()
