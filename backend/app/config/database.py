"""
FraudShield — Database Configuration & ORM Models
PostgreSQL via SQLAlchemy async + asyncpg
"""

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase, mapped_column, Mapped
from sqlalchemy import (
    String, Float, Integer, Boolean, DateTime, Text, JSON,
    func, Index
)
from typing import Optional, AsyncGenerator
from datetime import datetime
import uuid

from app.config.settings import settings


# ── Engine & Session ──────────────────────────────────────────────────────────

engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency — yields a DB session per request."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


# ── Base ──────────────────────────────────────────────────────────────────────

class Base(DeclarativeBase):
    pass


# ── ORM Models ────────────────────────────────────────────────────────────────

class User(Base):
    """Tabel user/analyst yang menggunakan sistem FraudShield."""
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    username: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(32), default="analyst")   # admin | analyst | viewer
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_login: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("ix_users_email", "email"),
    )


class Transaction(Base):
    """Riwayat semua transaksi yang masuk ke sistem."""
    __tablename__ = "transactions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    transaction_ref: Mapped[str] = mapped_column(String(64), unique=True, index=True)

    # Raw fields
    amt: Mapped[float] = mapped_column(Float, nullable=False)
    merchant: Mapped[str] = mapped_column(String(255), nullable=False)
    category: Mapped[str] = mapped_column(String(64), nullable=False)
    city: Mapped[Optional[str]] = mapped_column(String(100))
    state: Mapped[Optional[str]] = mapped_column(String(50))
    cc_num_masked: Mapped[Optional[str]] = mapped_column(String(20))   # hanya 4 digit terakhir
    gender: Mapped[Optional[str]] = mapped_column(String(1))

    # Temporal
    trans_datetime: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    hour: Mapped[Optional[int]] = mapped_column(Integer)
    month: Mapped[Optional[int]] = mapped_column(Integer)

    # Engineered features (disimpan setelah feature engineering)
    amt_log: Mapped[Optional[float]] = mapped_column(Float)
    amt_mean_per_card: Mapped[Optional[float]] = mapped_column(Float)
    amt_ratio: Mapped[Optional[float]] = mapped_column(Float)
    amt_std_per_card: Mapped[Optional[float]] = mapped_column(Float)
    txn_count_per_card: Mapped[Optional[int]] = mapped_column(Integer)
    unique_merchants: Mapped[Optional[int]] = mapped_column(Integer)
    unique_categories: Mapped[Optional[int]] = mapped_column(Integer)

    # One-hot category flags
    category_food_dining: Mapped[Optional[int]] = mapped_column(Integer)
    category_gas_transport: Mapped[Optional[int]] = mapped_column(Integer)
    category_grocery_pos: Mapped[Optional[int]] = mapped_column(Integer)
    category_kids_pets: Mapped[Optional[int]] = mapped_column(Integer)
    category_misc_net: Mapped[Optional[int]] = mapped_column(Integer)
    category_misc_pos: Mapped[Optional[int]] = mapped_column(Integer)
    category_personal_care: Mapped[Optional[int]] = mapped_column(Integer)
    category_shopping_net: Mapped[Optional[int]] = mapped_column(Integer)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("ix_transactions_trans_datetime", "trans_datetime"),
        Index("ix_transactions_merchant", "merchant"),
        Index("ix_transactions_category", "category"),
    )


class FraudPrediction(Base):
    """Hasil prediksi fraud untuk setiap transaksi."""
    __tablename__ = "fraud_predictions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    transaction_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    transaction_ref: Mapped[str] = mapped_column(String(64), index=True)

    # Prediction output
    risk_score: Mapped[float] = mapped_column(Float, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)  # SAFE | REVIEW | FRAUD
    confidence: Mapped[float] = mapped_column(Float)
    model_version: Mapped[str] = mapped_column(String(64))
    latency_ms: Mapped[float] = mapped_column(Float)

    # Feature values saat prediksi
    features_snapshot: Mapped[Optional[dict]] = mapped_column(JSON)
    shap_values: Mapped[Optional[dict]] = mapped_column(JSON)

    # Ground truth (diisi setelah review manual)
    is_confirmed_fraud: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    reviewed_by: Mapped[Optional[str]] = mapped_column(String(64))
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    review_notes: Mapped[Optional[str]] = mapped_column(Text)

    predicted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("ix_fraud_predictions_status", "status"),
        Index("ix_fraud_predictions_risk_score", "risk_score"),
        Index("ix_fraud_predictions_predicted_at", "predicted_at"),
    )


class Alert(Base):
    """Alert yang dibuat otomatis saat deteksi fraud."""
    __tablename__ = "alerts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    prediction_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    transaction_ref: Mapped[str] = mapped_column(String(64))

    severity: Mapped[str] = mapped_column(String(16))     # HIGH | MEDIUM | LOW
    alert_type: Mapped[str] = mapped_column(String(64))   # FRAUD_DETECTED | HIGH_RISK | etc.
    message: Mapped[str] = mapped_column(Text)

    is_resolved: Mapped[bool] = mapped_column(Boolean, default=False)
    resolved_by: Mapped[Optional[str]] = mapped_column(String(64))
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("ix_alerts_severity", "severity"),
        Index("ix_alerts_is_resolved", "is_resolved"),
        Index("ix_alerts_created_at", "created_at"),
    )


class AuditLog(Base):
    """Log semua aksi user & system untuk keperluan audit."""
    __tablename__ = "audit_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    actor: Mapped[str] = mapped_column(String(64))         # username atau "system"
    action: Mapped[str] = mapped_column(String(128))       # predict | review | login | etc.
    resource_type: Mapped[Optional[str]] = mapped_column(String(64))
    resource_id: Mapped[Optional[str]] = mapped_column(String(64))
    detail: Mapped[Optional[dict]] = mapped_column(JSON)
    ip_address: Mapped[Optional[str]] = mapped_column(String(45))
    user_agent: Mapped[Optional[str]] = mapped_column(String(256))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("ix_audit_logs_actor", "actor"),
        Index("ix_audit_logs_action", "action"),
        Index("ix_audit_logs_created_at", "created_at"),
    )


# ── DB Init ───────────────────────────────────────────────────────────────────

async def init_db():
    """Buat semua tabel jika belum ada."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
