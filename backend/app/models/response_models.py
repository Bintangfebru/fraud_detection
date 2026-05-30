"""
FraudShield — Response Models (Pydantic v2)
Output schema untuk semua endpoint API.
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime


class PredictionResult(BaseModel):
    transaction_id: str
    risk_score: float = Field(..., ge=0.0, le=1.0, description="Probabilitas fraud 0.0–1.0")
    risk_pct: str = Field(..., description="Tampilan human-readable, e.g. '73.2%'")
    status: str = Field(..., description="SAFE | REVIEW | FRAUD")
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
    city: Optional[str]
    state: Optional[str]
    trans_datetime: Optional[datetime]
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
    is_confirmed_fraud: Optional[bool]
    reviewed_by: Optional[str]
    reviewed_at: Optional[datetime]
    review_notes: Optional[str]
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
    resolved_by: Optional[str]
    resolved_at: Optional[datetime]
    created_at: datetime

    model_config = {"from_attributes": True}


class ModelStatus(BaseModel):
    loaded: bool
    type: str
    path: str
    selected_features: List[str]
    thresholds: Dict[str, float]


class HealthResponse(BaseModel):
    status: str
    model: str
    db: str
    version: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class PaginatedResponse(BaseModel):
    items: List[Any]
    total: int
    page: int
    page_size: int
    pages: int
