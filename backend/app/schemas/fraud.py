"""Fraud detection schemas — request/response."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator


# ── Request schemas ───────────────────────────────────────────────────────────

class TransactionInput(BaseModel):
    amt: float = Field(..., gt=0, description="Transaction amount (USD)")
    merchant: str = Field(..., min_length=1, max_length=255)
    category: str = Field(..., description="Merchant category (e.g. food_dining)")

    cc_num: Optional[str] = Field(None, description="Card number — will be masked")
    gender: Optional[str] = Field(None, pattern="^[MFmf]$")
    city: Optional[str] = Field(None, max_length=100)
    state: Optional[str] = Field(None, max_length=50)
    trans_date_trans_time: Optional[str] = Field(None, description="ISO datetime")

    # Card-level aggregates (optional — fallback to training medians)
    amt_mean_per_card: Optional[float] = Field(None, gt=0)
    amt_std_per_card: Optional[float] = Field(None, ge=0)
    txn_count_per_card: Optional[int] = Field(None, ge=0)
    unique_merchants: Optional[int] = Field(None, ge=0)
    unique_categories: Optional[int] = Field(None, ge=0)

    @field_validator("category")
    @classmethod
    def normalize_category(cls, v: str) -> str:
        return v.strip().lower().replace(" ", "_").replace("-", "_")

    @field_validator("merchant")
    @classmethod
    def clean_merchant(cls, v: str) -> str:
        return v.strip()

    model_config = {
        "json_schema_extra": {
            "example": {
                "amt": 312.50,
                "merchant": "Amazon.com",
                "category": "shopping_net",
                "gender": "F",
                "city": "San Francisco",
                "state": "CA",
                "trans_date_trans_time": "2024-06-15T23:45:00",
                "amt_mean_per_card": 75.0,
                "txn_count_per_card": 25,
            }
        }
    }


class BatchTransactionInput(BaseModel):
    transactions: List[TransactionInput] = Field(..., min_length=1, max_length=500)


class ReviewUpdate(BaseModel):
    is_confirmed_fraud: bool
    review_notes: Optional[str] = Field(None, max_length=2000)


class AlertResolve(BaseModel):
    resolved_by: str = Field(..., min_length=1, max_length=64)
    notes: Optional[str] = Field(None, max_length=2000)


# ── Response schemas ──────────────────────────────────────────────────────────

class PredictionResult(BaseModel):
    transaction_id: str
    risk_score: float = Field(..., ge=0.0, le=1.0)
    risk_pct: str
    status: str
    confidence: float
    model_version: str
    latency_ms: float
    features_used: Dict[str, Any]
    shap_values: Optional[Dict[str, float]] = None
    timestamp: str


class BatchResult(BaseModel):
    results: List[PredictionResult]
    total: int
    fraud_count: int
    review_count: int
    safe_count: int
    processing_ms: float


class TransactionOut(BaseModel):
    id: str
    transaction_ref: str
    amt: float
    merchant: str
    category: str
    city: Optional[str] = None
    state: Optional[str] = None
    trans_datetime: Optional[datetime] = None
    created_at: datetime
    model_config = {"from_attributes": True}


class FraudPredictionOut(BaseModel):
    id: str
    transaction_ref: str
    risk_score: float
    status: str
    confidence: float
    model_version: str
    latency_ms: float
    is_confirmed_fraud: Optional[bool] = None
    reviewed_by: Optional[str] = None
    reviewed_at: Optional[datetime] = None
    review_notes: Optional[str] = None
    predicted_at: datetime
    model_config = {"from_attributes": True}


class AlertOut(BaseModel):
    id: str
    prediction_id: str
    transaction_ref: str
    severity: str
    alert_type: str
    message: str
    is_resolved: bool
    resolved_by: Optional[str] = None
    resolved_at: Optional[datetime] = None
    created_at: datetime
    model_config = {"from_attributes": True}


class TransactionDetailOut(BaseModel):
    transaction: TransactionOut
    prediction: Optional[FraudPredictionOut] = None
    alerts: List[AlertOut] = []
