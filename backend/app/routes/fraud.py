"""
FraudShield — Fraud Routes
POST /v1/predict       → prediksi satu transaksi
POST /v1/predict/batch → prediksi batch (maks 500)
GET  /v1/transactions  → riwayat transaksi
GET  /v1/transactions/{ref} → detail transaksi
PUT  /v1/predictions/{id}/review → update hasil review
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional
import logging

from app.config.database import get_db, FraudPrediction, Alert
from app.models.request_models import TransactionInput, BatchTransactionInput, ReviewUpdate, AlertResolve
from app.models.response_models import PredictionResult, BatchResult
from app.services.fraud_service import process_transaction
from app.services.transaction_service import (
    list_transactions, get_transaction_detail, get_analytics_summary
)
from app.services.scoring_service import score_summary
from sqlalchemy import select

router = APIRouter(prefix="/v1", tags=["Fraud Detection"])
log = logging.getLogger("fraudshield.routes.fraud")


@router.post("/predict", response_model=PredictionResult)
async def predict_single(
    txn: TransactionInput,
    db: AsyncSession = Depends(get_db),
):
    """Prediksi fraud untuk satu transaksi. Hasil disimpan ke PostgreSQL."""
    try:
        result = await process_transaction(txn, db)
        return result
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        log.error(f"Prediction error: {e}")
        raise HTTPException(status_code=500, detail="Prediction failed.")


@router.post("/predict/batch", response_model=BatchResult)
async def predict_batch(
    payload: BatchTransactionInput,
    db: AsyncSession = Depends(get_db),
):
    """Prediksi batch hingga 500 transaksi sekaligus."""
    from datetime import datetime
    start = datetime.now()
    results = []

    for txn in payload.transactions:
        try:
            result = await process_transaction(txn, db)
            results.append(result)
        except Exception as e:
            log.warning(f"Batch item error: {e}")

    processing_ms = (datetime.now() - start).total_seconds() * 1000
    scores = [r.risk_score for r in results]
    summary = score_summary(scores)

    return BatchResult(
        results=results,
        total=summary.get("total", len(results)),
        fraud_count=summary.get("fraud_count", 0),
        review_count=summary.get("review_count", 0),
        safe_count=summary.get("safe_count", 0),
        processing_ms=round(processing_ms, 2),
    )


@router.get("/transactions")
async def get_transactions(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    status: Optional[str] = Query(None, pattern="^(SAFE|REVIEW|FRAUD)$"),
    merchant: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    """Daftar transaksi dengan paginasi dan filter."""
    return await list_transactions(db, page, page_size, status, merchant)


@router.get("/transactions/{transaction_ref}")
async def get_transaction(
    transaction_ref: str,
    db: AsyncSession = Depends(get_db),
):
    """Detail satu transaksi beserta prediksi dan alert."""
    detail = await get_transaction_detail(db, transaction_ref)
    if not detail:
        raise HTTPException(status_code=404, detail="Transaksi tidak ditemukan.")
    return detail


@router.put("/predictions/{prediction_id}/review")
async def update_review(
    prediction_id: str,
    body: ReviewUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Update hasil review manual (konfirmasi fraud atau bukan)."""
    from datetime import datetime
    result = await db.execute(
        select(FraudPrediction).where(FraudPrediction.id == prediction_id)
    )
    pred = result.scalar_one_or_none()
    if not pred:
        raise HTTPException(status_code=404, detail="Prediction tidak ditemukan.")

    pred.is_confirmed_fraud = body.is_confirmed_fraud
    pred.review_notes = body.review_notes
    pred.reviewed_at = datetime.now()
    await db.commit()
    return {"message": "Review berhasil disimpan.", "prediction_id": prediction_id}


@router.put("/alerts/{alert_id}/resolve")
async def resolve_alert(
    alert_id: str,
    body: AlertResolve,
    db: AsyncSession = Depends(get_db),
):
    """Tandai alert sebagai resolved."""
    from datetime import datetime
    result = await db.execute(select(Alert).where(Alert.id == alert_id))
    alert = result.scalar_one_or_none()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert tidak ditemukan.")

    alert.is_resolved = True
    alert.resolved_by = body.resolved_by
    alert.resolved_at = datetime.now()
    await db.commit()
    return {"message": "Alert resolved.", "alert_id": alert_id}


@router.get("/analytics/summary")
async def analytics_summary(db: AsyncSession = Depends(get_db)):
    """Ringkasan statistik untuk dashboard."""
    return await get_analytics_summary(db)
