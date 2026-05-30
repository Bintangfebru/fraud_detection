"""Transaction ORM model."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Float, Index, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Transaction(Base):
    __tablename__ = "transactions"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    transaction_ref: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)

    # Core fields
    amt: Mapped[float] = mapped_column(Float, nullable=False)
    merchant: Mapped[str] = mapped_column(String(255), nullable=False)
    category: Mapped[str] = mapped_column(String(64), nullable=False)
    city: Mapped[Optional[str]] = mapped_column(String(100))
    state: Mapped[Optional[str]] = mapped_column(String(50))
    cc_num_masked: Mapped[Optional[str]] = mapped_column(String(20))
    gender: Mapped[Optional[str]] = mapped_column(String(1))

    # Temporal
    trans_datetime: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    hour: Mapped[Optional[int]] = mapped_column(Integer)
    month: Mapped[Optional[int]] = mapped_column(Integer)

    # Engineered features
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

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        Index("ix_transactions_transaction_ref", "transaction_ref"),
        Index("ix_transactions_trans_datetime", "trans_datetime"),
        Index("ix_transactions_merchant", "merchant"),
        Index("ix_transactions_category", "category"),
        Index("ix_transactions_created_at", "created_at"),
    )
