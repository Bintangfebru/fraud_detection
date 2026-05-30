"""
FraudShield — Transaction Service
Query dan manajemen riwayat transaksi dari PostgreSQL.
"""

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc
from typing import Optional

from app.config.database import Transaction, FraudPrediction, Alert


async def list_transactions(
    db: AsyncSession,
    page: int = 1,
    page_size: int = 50,
    status: Optional[str] = None,
    merchant: Optional[str] = None,
) -> dict:
    """Ambil daftar transaksi dengan join ke prediction, support filter & paginasi."""
    offset = (page - 1) * page_size

    query = (
        select(Transaction, FraudPrediction)
        .join(FraudPrediction, Transaction.transaction_ref == FraudPrediction.transaction_ref, isouter=True)
        .order_by(desc(Transaction.created_at))
    )

    if status:
        query = query.where(FraudPrediction.status == status.upper())
    if merchant:
        query = query.where(Transaction.merchant.ilike(f"%{merchant}%"))

    # Total count
    count_q = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_q)
    total = total_result.scalar_one()

    # Paginate
    query = query.offset(offset).limit(page_size)
    result = await db.execute(query)
    rows = result.all()

    return {
        "items": rows,
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": max(1, -(-total // page_size)),
    }


async def get_transaction_detail(db: AsyncSession, transaction_ref: str) -> Optional[dict]:
    """Ambil satu transaksi beserta prediksi dan alert-nya."""
    txn_result = await db.execute(
        select(Transaction).where(Transaction.transaction_ref == transaction_ref)
    )
    txn = txn_result.scalar_one_or_none()
    if not txn:
        return None

    pred_result = await db.execute(
        select(FraudPrediction).where(FraudPrediction.transaction_ref == transaction_ref)
    )
    pred = pred_result.scalar_one_or_none()

    alerts_result = await db.execute(
        select(Alert).where(Alert.transaction_ref == transaction_ref)
    )
    alerts = alerts_result.scalars().all()

    return {"transaction": txn, "prediction": pred, "alerts": alerts}


async def get_analytics_summary(db: AsyncSession) -> dict:
    """Statistik ringkasan untuk dashboard."""
    total = await db.scalar(select(func.count()).select_from(Transaction))
    fraud = await db.scalar(
        select(func.count()).select_from(FraudPrediction).where(FraudPrediction.status == "FRAUD")
    )
    review = await db.scalar(
        select(func.count()).select_from(FraudPrediction).where(FraudPrediction.status == "REVIEW")
    )
    open_alerts = await db.scalar(
        select(func.count()).select_from(Alert).where(Alert.is_resolved == False)
    )

    return {
        "total_transactions": total or 0,
        "fraud_count": fraud or 0,
        "review_count": review or 0,
        "safe_count": max(0, (total or 0) - (fraud or 0) - (review or 0)),
        "open_alerts": open_alerts or 0,
        "fraud_rate": round((fraud or 0) / max(1, total or 1), 4),
    }
