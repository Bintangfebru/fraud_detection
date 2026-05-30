"""
FraudShield — Real-Time Streaming Package
Event-driven architecture: Kafka → Redis Pub/Sub → WebSocket
"""

from app.streaming.connection_manager import ConnectionManager, ws_manager
from app.streaming.event_schemas import (
    StreamEvent,
    TransactionEvent,
    FraudAlertEvent,
    MetricsEvent,
    SystemEvent,
    EventType,
)

__all__ = [
    "ConnectionManager",
    "ws_manager",
    "StreamEvent",
    "TransactionEvent",
    "FraudAlertEvent",
    "MetricsEvent",
    "SystemEvent",
    "EventType",
]
