"""
FraudShield — Request Models (Pydantic v2)
Input schema untuk semua endpoint API.
"""

from pydantic import BaseModel, Field, field_validator
from typing import Optional, List
from datetime import datetime


class TransactionInput(BaseModel):
    """Input untuk prediksi fraud satu transaksi."""

    # Wajib
    amt: float = Field(..., gt=0, description="Jumlah transaksi (USD)")
    merchant: str = Field(..., min_length=1, max_length=255, description="Nama merchant")
    category: str = Field(..., description="Kategori merchant (misal: food_dining)")

    # Identitas kartu
    cc_num: Optional[str] = Field(None, description="Nomor kartu (akan di-mask)")
    gender: Optional[str] = Field(None, pattern="^[MFmf]$", description="M atau F")
    city: Optional[str] = Field(None, max_length=100)
    state: Optional[str] = Field(None, max_length=50)

    # Datetime transaksi
    trans_date_trans_time: Optional[str] = Field(
        None, description="ISO datetime: 2024-06-15T23:45:00"
    )

    # Pre-computed card aggregates (opsional — fallback ke training median jika kosong)
    amt_mean_per_card: Optional[float] = Field(None, gt=0)
    amt_std_per_card: Optional[float] = Field(None, ge=0)
    txn_count_per_card: Optional[int] = Field(None, ge=0)
    unique_merchants: Optional[int] = Field(None, ge=0)
    unique_categories: Optional[int] = Field(None, ge=0)

    @field_validator("category")
    @classmethod
    def validate_category(cls, v: str) -> str:
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
    """Input batch — maks 500 transaksi per request."""
    transactions: List[TransactionInput] = Field(..., min_length=1, max_length=500)


class ReviewUpdate(BaseModel):
    """Update status review setelah investigasi manual."""
    is_confirmed_fraud: bool
    review_notes: Optional[str] = Field(None, max_length=1000)


class AlertResolve(BaseModel):
    """Tandai alert sebagai resolved."""
    resolved_by: str = Field(..., min_length=1)
    notes: Optional[str] = None


class UserCreate(BaseModel):
    username: str = Field(..., min_length=3, max_length=64)
    email: str = Field(..., pattern=r"^[^@]+@[^@]+\.[^@]+$")
    password: str = Field(..., min_length=8)
    role: str = Field(default="analyst", pattern="^(admin|analyst|viewer)$")


class LoginRequest(BaseModel):
    username: str
    password: str
