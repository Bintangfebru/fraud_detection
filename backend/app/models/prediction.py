"""FraudPrediction, Alert, and AuditLog ORM models."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, Float, Index, JSON, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class FraudPrediction(Base):
    __tablename__ = "fraud_predictions"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    transaction_id: Mapped[str] = mapped_column(String(36), nullable=False)
    transaction_ref: Mapped[str] = mapped_column(String(64), nullable=False)

    risk_score: Mapped[float] = mapped_column(Float, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)     # SAFE|REVIEW|FRAUD
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    model_version: Mapped[str] = mapped_column(String(64), nullable=False)
    latency_ms: Mapped[float] = mapped_column(Float, nullable=False)

    features_snapshot: Mapped[Optional[dict]] = mapped_column(JSON)
    shap_values: Mapped[Optional[dict]] = mapped_column(JSON)

    # Ground truth after manual review
    is_confirmed_fraud: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    reviewed_by: Mapped[Optional[str]] = mapped_column(String(64))
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    review_notes: Mapped[Optional[str]] = mapped_column(Text)

    predicted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        Index("ix_fp_transaction_ref", "transaction_ref"),
        Index("ix_fp_status", "status"),
        Index("ix_fp_risk_score", "risk_score"),
        Index("ix_fp_predicted_at", "predicted_at"),
        Index("ix_fp_is_confirmed_fraud", "is_confirmed_fraud"),
    )


class Alert(Base):
    __tablename__ = "alerts"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    prediction_id: Mapped[str] = mapped_column(String(36), nullable=False)
    transaction_ref: Mapped[str] = mapped_column(String(64), nullable=False)

    severity: Mapped[str] = mapped_column(String(16), nullable=False)   # HIGH|MEDIUM|LOW
    alert_type: Mapped[str] = mapped_column(String(64), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)

    is_resolved: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    resolved_by: Mapped[Optional[str]] = mapped_column(String(64))
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    resolution_notes: Mapped[Optional[str]] = mapped_column(Text)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        Index("ix_alerts_prediction_id", "prediction_id"),
        Index("ix_alerts_severity", "severity"),
        Index("ix_alerts_is_resolved", "is_resolved"),
        Index("ix_alerts_created_at", "created_at"),
    )


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    actor: Mapped[str] = mapped_column(String(64), nullable=False)         # username | "system"
    action: Mapped[str] = mapped_column(String(128), nullable=False)       # predict | login | etc.
    resource_type: Mapped[Optional[str]] = mapped_column(String(64))
    resource_id: Mapped[Optional[str]] = mapped_column(String(64))
    detail: Mapped[Optional[dict]] = mapped_column(JSON)
    ip_address: Mapped[Optional[str]] = mapped_column(String(45))
    user_agent: Mapped[Optional[str]] = mapped_column(String(512))
    status_code: Mapped[Optional[int]] = mapped_column()

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        Index("ix_audit_actor", "actor"),
        Index("ix_audit_action", "action"),
        Index("ix_audit_created_at", "created_at"),
        Index("ix_audit_resource", "resource_type", "resource_id"),
    )
