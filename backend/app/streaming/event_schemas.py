"""
FraudShield — Streaming Event Schemas
Pydantic models for all real-time events flowing through Kafka → Redis → WebSocket.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class EventType(str, Enum):
    # Transaction lifecycle
    TRANSACTION_RECEIVED   = "transaction.received"
    TRANSACTION_SCORED     = "transaction.scored"
    TRANSACTION_COMPLETED  = "transaction.completed"

    # Fraud events
    FRAUD_DETECTED         = "fraud.detected"
    FRAUD_REVIEW_REQUIRED  = "fraud.review_required"
    FRAUD_ALERT_CREATED    = "fraud.alert_created"
    FRAUD_ALERT_RESOLVED   = "fraud.alert_resolved"

    # Metrics
    METRICS_UPDATE         = "metrics.update"
    RISK_SCORE_UPDATE      = "metrics.risk_score"
    TPS_UPDATE             = "metrics.tps"

    # System
    SYSTEM_HEALTH          = "system.health"
    CONSUMER_ERROR         = "system.consumer_error"
    DLQ_EVENT              = "system.dlq"
    REPLAY_STARTED         = "system.replay_started"
    REPLAY_COMPLETED       = "system.replay_completed"


class StreamEvent(BaseModel):
    """Base event envelope for all streaming events."""
    event_id:   str      = Field(default_factory=lambda: str(uuid.uuid4()))
    event_type: EventType
    timestamp:  str      = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    version:    str      = "1.0"
    source:     str      = "fraudshield-backend"
    retry_count: int     = 0
    payload:    Dict[str, Any] = Field(default_factory=dict)

    def to_kafka_bytes(self) -> bytes:
        return self.model_dump_json().encode("utf-8")

    @classmethod
    def from_kafka_bytes(cls, data: bytes) -> "StreamEvent":
        return cls.model_validate_json(data.decode("utf-8"))


class TransactionEvent(StreamEvent):
    """Emitted when a transaction is received and after scoring."""
    event_type: EventType = EventType.TRANSACTION_RECEIVED

    @classmethod
    def from_prediction(
        cls,
        txn_ref: str,
        amount: float,
        merchant: str,
        category: str,
        risk_score: float,
        status: str,
        confidence: float,
        latency_ms: float,
        city: Optional[str] = None,
        cc_masked: Optional[str] = None,
    ) -> "TransactionEvent":
        return cls(
            event_type=EventType.TRANSACTION_SCORED,
            payload={
                "transaction_ref": txn_ref,
                "amount": amount,
                "merchant": merchant,
                "category": category,
                "city": city,
                "cc_masked": cc_masked,
                "risk_score": round(risk_score, 4),
                "risk_pct": f"{risk_score * 100:.1f}%",
                "status": status,
                "confidence": round(confidence, 4),
                "latency_ms": round(latency_ms, 2),
            },
        )


class FraudAlertEvent(StreamEvent):
    """Emitted when a fraud or review alert is created."""
    event_type: EventType = EventType.FRAUD_ALERT_CREATED

    @classmethod
    def from_alert(
        cls,
        alert_id: int,
        txn_ref: str,
        severity: str,
        alert_type: str,
        message: str,
        risk_score: float,
        amount: float,
        merchant: str,
    ) -> "FraudAlertEvent":
        etype = (
            EventType.FRAUD_DETECTED
            if severity == "HIGH"
            else EventType.FRAUD_REVIEW_REQUIRED
        )
        return cls(
            event_type=etype,
            payload={
                "alert_id": alert_id,
                "transaction_ref": txn_ref,
                "severity": severity,
                "alert_type": alert_type,
                "message": message,
                "risk_score": round(risk_score, 4),
                "amount": amount,
                "merchant": merchant,
            },
        )


class MetricsEvent(StreamEvent):
    """Periodic metrics snapshot for dashboard auto-refresh."""
    event_type: EventType = EventType.METRICS_UPDATE

    @classmethod
    def build(
        cls,
        total_transactions: int,
        fraud_count: int,
        review_count: int,
        safe_count: int,
        open_alerts: int,
        fraud_rate: float,
        tps: float = 0.0,
        avg_risk_score: float = 0.0,
        avg_latency_ms: float = 0.0,
    ) -> "MetricsEvent":
        return cls(
            payload={
                "total_transactions": total_transactions,
                "fraud_count": fraud_count,
                "review_count": review_count,
                "safe_count": safe_count,
                "open_alerts": open_alerts,
                "fraud_rate": round(fraud_rate, 4),
                "fraud_rate_pct": f"{fraud_rate * 100:.2f}%",
                "tps": round(tps, 2),
                "avg_risk_score": round(avg_risk_score, 4),
                "avg_latency_ms": round(avg_latency_ms, 2),
            }
        )


class SystemEvent(StreamEvent):
    """System-level events (health, errors, DLQ, replay)."""
    event_type: EventType = EventType.SYSTEM_HEALTH


class DLQEvent(StreamEvent):
    """Dead-letter queue event wrapping a failed original event."""
    event_type: EventType = EventType.DLQ_EVENT

    @classmethod
    def from_failed(
        cls,
        original_event: StreamEvent,
        error: str,
        failed_topic: str,
    ) -> "DLQEvent":
        return cls(
            payload={
                "original_event_id": original_event.event_id,
                "original_event_type": original_event.event_type,
                "original_payload": original_event.payload,
                "error": error,
                "failed_topic": failed_topic,
                "retry_count": original_event.retry_count,
            }
        )
