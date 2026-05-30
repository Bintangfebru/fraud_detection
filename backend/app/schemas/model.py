"""ML model management and analytics schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


# ── Threshold schemas ─────────────────────────────────────────────────────────

class ThresholdUpdate(BaseModel):
    fraud: float = Field(..., gt=0.0, lt=1.0)
    review: float = Field(..., gt=0.0, lt=1.0)
    notes: Optional[str] = Field(None, max_length=500)

    @classmethod
    def validate_order(cls, values: dict) -> dict:
        if values.get("review", 0) >= values.get("fraud", 1):
            raise ValueError("review threshold must be less than fraud threshold")
        return values


class ThresholdOut(BaseModel):
    fraud: float
    review: float
    set_by: Optional[str] = None
    updated_at: Optional[datetime] = None


# ── Model registry schemas ────────────────────────────────────────────────────

class ModelOut(BaseModel):
    id: str
    model_id: str
    name: str
    model_type: str
    status: str
    dataset_size: Optional[int] = None
    data_source: Optional[str] = None
    features: Optional[List[str]] = None
    metrics: Optional[Dict[str, float]] = None
    trained_at: Optional[datetime] = None
    created_at: datetime
    model_config = {"from_attributes": True}


class ModelRegistryOut(BaseModel):
    models: List[ModelOut]
    total: int


class ModelStatusOut(BaseModel):
    loaded: bool
    model_type: str
    name: str
    path: str
    selected_features: List[str]
    thresholds: Dict[str, float]
    deployed_model_id: Optional[str] = None


class PromoteModelRequest(BaseModel):
    notes: Optional[str] = Field(None, max_length=500)


# ── Training job schemas ──────────────────────────────────────────────────────

class TrainRequest(BaseModel):
    model_type: str = Field(
        default="RandomForest",
        pattern="^(RandomForest|GradientBoosting)$",
    )
    training_period: str = Field(
        default="Last 30 days",
        pattern=r"^Last (7|14|30|60|90) days$",
    )
    validation_split: str = Field(
        default="80/20",
        pattern=r"^(70/30|80/20|90/10)$",
    )
    features: List[str] = Field(default_factory=list)


class TrainingJobOut(BaseModel):
    job_id: str
    model_type: str
    training_period: str
    validation_split: str
    status: str
    progress_pct: int
    data_source: Optional[str] = None
    dataset_size: Optional[int] = None
    metrics: Optional[Dict[str, float]] = None
    model_id: Optional[str] = None
    error_message: Optional[str] = None
    warning_message: Optional[str] = None
    started_by: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    model_config = {"from_attributes": True}


# ── Feature importance schemas ────────────────────────────────────────────────

class FeatureImportanceItem(BaseModel):
    name: str
    importance: float
    direction: str  # positive | negative | neutral


class FeatureImportanceOut(BaseModel):
    features: List[FeatureImportanceItem]
    model_id: str
    method: str


# ── Analytics schemas ─────────────────────────────────────────────────────────

class AnalyticsSummaryOut(BaseModel):
    total_transactions: int
    fraud_count: int
    review_count: int
    safe_count: int
    open_alerts: int
    fraud_rate: float
    total_amount: float = 0.0   # prevents RpNaN in frontend
    fraud_amount: float = 0.0   # prevents RpNaN in frontend


class FraudRatePoint(BaseModel):
    date: str
    total: int
    fraud_count: int
    avg_score: float


class FraudRateTrendOut(BaseModel):
    """Matches frontend types/api.ts FraudRateTrend interface."""
    labels: List[str]
    fraud_counts: List[int]
    safe_counts: List[int]
    review_counts: List[int]
    fraud_rates: List[float]


class TopMerchantOut(BaseModel):
    merchant: str
    total_txn: int
    fraud_count: int
    avg_risk: float


class CategoryBreakdownOut(BaseModel):
    category: str
    total: int
    fraud_count: int


# ── Health schemas ────────────────────────────────────────────────────────────

class HealthOut(BaseModel):
    status: str
    model: str
    db: str
    redis: str
    version: str
    uptime_seconds: Optional[float] = None


# ── Pagination ────────────────────────────────────────────────────────────────

class PaginatedOut(BaseModel):
    items: List[Any]
    total: int
    page: int
    page_size: int
    pages: int