"""
ModelRegistry and Threshold ORM models.
Replaces the in-memory _model_registry and _thresholds dicts in main.py.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, Float, Index, Integer, JSON, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ModelRegistry(Base):
    """Tracks all ML model versions: deployed, staging, archived."""
    __tablename__ = "model_registry"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    model_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    model_type: Mapped[str] = mapped_column(String(64), nullable=False)   # RandomForestClassifier|etc
    status: Mapped[str] = mapped_column(String(16), nullable=False)        # deployed|staging|archived
    model_path: Mapped[Optional[str]] = mapped_column(String(512))
    dataset_size: Mapped[Optional[int]] = mapped_column(Integer)
    data_source: Mapped[str] = mapped_column(String(32), default="synthetic")
    features: Mapped[Optional[list]] = mapped_column(JSON)
    metrics: Mapped[Optional[dict]] = mapped_column(JSON)        # accuracy, precision, recall, f1
    notes: Mapped[Optional[str]] = mapped_column(Text)
    trained_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    promoted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    promoted_by: Mapped[Optional[str]] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        Index("ix_model_registry_status", "status"),
        Index("ix_model_registry_model_id", "model_id"),
    )


class Threshold(Base):
    """
    Active fraud/review thresholds.
    Only one row should exist (id='active'). History is append-only.
    """
    __tablename__ = "thresholds"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    fraud_threshold: Mapped[float] = mapped_column(Float, nullable=False)
    review_threshold: Mapped[float] = mapped_column(Float, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    set_by: Mapped[Optional[str]] = mapped_column(String(64))
    notes: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        Index("ix_thresholds_is_active", "is_active"),
        Index("ix_thresholds_created_at", "created_at"),
    )


class TrainingJob(Base):
    """Persistent training job records. Status mirrored to Redis for fast polling."""
    __tablename__ = "training_jobs"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    job_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    model_type: Mapped[str] = mapped_column(String(64), nullable=False)
    training_period: Mapped[str] = mapped_column(String(32), nullable=False)
    validation_split: Mapped[str] = mapped_column(String(16), nullable=False)
    features: Mapped[Optional[list]] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(16), default="queued", nullable=False)
    progress_pct: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    data_source: Mapped[Optional[str]] = mapped_column(String(32))
    dataset_size: Mapped[Optional[int]] = mapped_column(Integer)
    metrics: Mapped[Optional[dict]] = mapped_column(JSON)
    model_id: Mapped[Optional[str]] = mapped_column(String(64))
    error_message: Mapped[Optional[str]] = mapped_column(Text)
    warning_message: Mapped[Optional[str]] = mapped_column(Text)
    started_by: Mapped[Optional[str]] = mapped_column(String(64))
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        Index("ix_training_jobs_status", "status"),
        Index("ix_training_jobs_started_at", "started_at"),
    )
