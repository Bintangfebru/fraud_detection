"""
FraudShield — Fraud Detection Router  (POST /api/v1/fraud/*)
Endpoints: predict, batch predict, transactions, predictions review, alerts
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Path, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import (
    AnalystOrAbove,
    AnyRole,
    get_current_user,
    get_session,
    rate_limit,
    require_min_role,
)
from app.core.config import settings
from app.core.exceptions import NotFoundError
from app.core.logging import get_logger
from app.core.security import Role
from app.models.user import User
from app.repositories.fraud_repo import (
    AlertRepository,
    AuditLogRepository,
    FraudPredictionRepository,
    TransactionRepository,
)
from app.schemas.fraud import (
    AlertOut,
    AlertResolve,
    BatchResult,
    BatchTransactionInput,
    FraudPredictionOut,
    PredictionResult,
    ReviewUpdate,
    TransactionDetailOut,
    TransactionInput,
    TransactionOut,
)
from app.services.fraud_service import FraudService

router = APIRouter(prefix="/fraud", tags=["Fraud Detection"])
log = get_logger("api.fraud")


# ── Single prediction ─────────────────────────────────────────────────────────

@router.post(
    "/predict",
    response_model=PredictionResult,
    status_code=status.HTTP_200_OK,
    summary="Score a single transaction for fraud risk",
    dependencies=[
        AnalystOrAbove,
        Depends(rate_limit(
            max_requests=settings.RATE_LIMIT_PREDICT,
            window_seconds=60,
        )),
    ],
)
async def predict_single(
    txn: TransactionInput,
    request: Request,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> PredictionResult:
    """
    Run the ML fraud scoring pipeline on a single transaction.
    Result is persisted to PostgreSQL. Alerts generated automatically for FRAUD/REVIEW.
    """
    ip = _client_ip(request)
    svc = FraudService(session)
    return await svc.process_transaction(
        txn_input=txn,
        actor=current_user.username,
        ip_address=ip,
    )


# ── Batch prediction ──────────────────────────────────────────────────────────

@router.post(
    "/predict/batch",
    response_model=BatchResult,
    status_code=status.HTTP_200_OK,
    summary="Score up to 500 transactions in a single request",
    dependencies=[
        AnalystOrAbove,
        Depends(rate_limit(
            max_requests=10,        # batch is expensive — tighter limit
            window_seconds=60,
        )),
    ],
)
async def predict_batch(
    payload: BatchTransactionInput,
    request: Request,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> BatchResult:
    """
    Process a batch of transactions. Each is scored independently.
    Items that fail validation are skipped; the batch does not abort.
    """
    start = datetime.now(timezone.utc)
    ip = _client_ip(request)
    svc = FraudService(session)

    results = []
    for txn in payload.transactions:
        try:
            result = await svc.process_transaction(
                txn_input=txn, actor=current_user.username, ip_address=ip
            )
            results.append(result)
        except Exception as exc:
            log.warning(f"Batch item skipped [{txn.merchant}]: {exc}")

    elapsed = (datetime.now(timezone.utc) - start).total_seconds() * 1000
    fraud_count = sum(1 for r in results if r.status == "FRAUD")
    review_count = sum(1 for r in results if r.status == "REVIEW")

    return BatchResult(
        results=results,
        total=len(results),
        fraud_count=fraud_count,
        review_count=review_count,
        safe_count=len(results) - fraud_count - review_count,
        processing_ms=round(elapsed, 2),
    )


# ── Transactions ──────────────────────────────────────────────────────────────

@router.get(
    "/transactions",
    summary="Paginated transaction list with optional filters",
    dependencies=[AnyRole],
)
async def list_transactions(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(
        settings.DEFAULT_PAGE_SIZE,
        ge=1,
        le=settings.MAX_PAGE_SIZE,
        description="Items per page",
    ),
    status_filter: Optional[str] = Query(
        None, alias="status", pattern="^(SAFE|REVIEW|FRAUD)$"
    ),
    merchant: Optional[str] = Query(None, description="Partial merchant name filter"),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """
    List transactions with their latest fraud prediction.
    Auditors can view all transactions in read-only mode.
    """
    repo = TransactionRepository(session)
    return await repo.list_with_predictions(
        page=page,
        page_size=page_size,
        status=status_filter,
        merchant=merchant,
    )


@router.get(
    "/transactions/{transaction_ref}",
    response_model=TransactionDetailOut,
    summary="Full detail for a single transaction",
    dependencies=[AnyRole],
)
async def get_transaction(
    transaction_ref: str = Path(..., description="Transaction reference (TXN-*)"),
    session: AsyncSession = Depends(get_session),
) -> TransactionDetailOut:
    """Return transaction, fraud prediction, and all associated alerts."""
    txn_repo = TransactionRepository(session)
    pred_repo = FraudPredictionRepository(session)
    alert_repo = AlertRepository(session)

    txn = await txn_repo.get_by_ref(transaction_ref)
    if not txn:
        raise NotFoundError(f"Transaction '{transaction_ref}' not found.")

    prediction = await pred_repo.get_by_ref(transaction_ref)
    alerts = await alert_repo.get_by_transaction_ref(transaction_ref)

    return TransactionDetailOut(
        transaction=TransactionOut.model_validate(txn),
        prediction=FraudPredictionOut.model_validate(prediction) if prediction else None,
        alerts=[AlertOut.model_validate(a) for a in alerts],
    )


# ── Prediction review ─────────────────────────────────────────────────────────

@router.put(
    "/predictions/{prediction_id}/review",
    response_model=FraudPredictionOut,
    summary="Record a manual fraud review decision",
    dependencies=[Depends(require_min_role(Role.ANALYST))],
)
async def review_prediction(
    prediction_id: str = Path(..., description="FraudPrediction UUID"),
    body: ReviewUpdate = ...,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> FraudPredictionOut:
    """
    Submit a manual review decision (confirmed fraud or cleared).
    Analyst or Admin role required.
    """
    repo = FraudPredictionRepository(session)
    prediction = await repo.get_by_id(prediction_id)
    if not prediction:
        raise NotFoundError(f"Prediction '{prediction_id}' not found.")

    updated = await repo.update(
        prediction,
        is_confirmed_fraud=body.is_confirmed_fraud,
        review_notes=body.review_notes,
        reviewed_by=current_user.username,
        reviewed_at=datetime.now(timezone.utc),
    )

    # Write audit entry
    audit_repo = AuditLogRepository(session)
    from app.models.prediction import AuditLog
    await audit_repo.create(
        AuditLog(
            actor=current_user.username,
            action="review_prediction",
            resource_type="fraud_prediction",
            resource_id=prediction_id,
            detail={
                "is_confirmed_fraud": body.is_confirmed_fraud,
                "notes": body.review_notes,
            },
        )
    )

    log.info(
        f"[{current_user.username}] Review: prediction={prediction_id} "
        f"confirmed_fraud={body.is_confirmed_fraud}"
    )
    return FraudPredictionOut.model_validate(updated)


# ── Alerts ────────────────────────────────────────────────────────────────────

@router.get(
    "/alerts",
    summary="List open fraud alerts",
    dependencies=[AnyRole],
)
async def list_open_alerts(
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Return all unresolved fraud alerts ordered by creation time (newest first)."""
    repo = AlertRepository(session)
    alerts = await repo.get_open_alerts()
    return {
        "alerts": [AlertOut.model_validate(a).model_dump() for a in alerts],
        "total": len(alerts),
    }


@router.put(
    "/alerts/{alert_id}/resolve",
    response_model=AlertOut,
    summary="Mark an alert as resolved",
    dependencies=[Depends(require_min_role(Role.ANALYST))],
)
async def resolve_alert(
    alert_id: str = Path(..., description="Alert UUID"),
    body: AlertResolve = ...,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> AlertOut:
    """Mark a fraud alert as resolved with optional resolution notes."""
    repo = AlertRepository(session)
    alert = await repo.get_by_id(alert_id)
    if not alert:
        raise NotFoundError(f"Alert '{alert_id}' not found.")

    updated = await repo.update(
        alert,
        is_resolved=True,
        resolved_by=current_user.username,
        resolved_at=datetime.now(timezone.utc),
        resolution_notes=body.notes,
    )
    log.info(f"[{current_user.username}] Alert resolved: {alert_id}")
    return AlertOut.model_validate(updated)


# ── Audit log ─────────────────────────────────────────────────────────────────

@router.get(
    "/audit",
    summary="Retrieve audit log (Auditor+ only)",
    dependencies=[AnyRole],   # further filtered below by role
)
async def get_audit_log(
    actor: Optional[str] = Query(None, description="Filter by actor username"),
    limit: int = Query(100, ge=1, le=500),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """
    Returns audit log entries.
    - Auditors see their own entries only.
    - Analysts and Admins see all entries (filtered by actor if provided).
    """
    from app.core.security import _ROLE_RANK

    repo = AuditLogRepository(session)
    # Auditors can only see their own audit entries
    effective_actor = (
        actor if _ROLE_RANK.get(current_user.role, 0) > 0
        else current_user.username
    )
    logs = await repo.list_by_actor(
        actor=effective_actor or current_user.username, limit=limit
    )
    from app.repositories.base import BaseRepository
    return {
        "logs": [
            {
                "id": e.id,
                "actor": e.actor,
                "action": e.action,
                "resource_type": e.resource_type,
                "resource_id": e.resource_id,
                "detail": e.detail,
                "ip_address": e.ip_address,
                "created_at": e.created_at.isoformat(),
            }
            for e in logs
        ],
        "total": len(logs),
    }


# ── Helpers ───────────────────────────────────────────────────────────────────

def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"
