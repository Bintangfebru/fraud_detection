"""
FraudShield — Analytics Router  (/api/v1/analytics/*)
Endpoints: summary, fraud-rate trend, top-merchants, category-breakdown

FIXES:
  1. /fraud-rate now accepts ?range=24h|7d|30d (matching frontend) instead of ?days=N
  2. Returns FraudRateTrend object {labels, fraud_counts, safe_counts, review_counts, fraud_rates}
     instead of list[FraudRatePoint] — matching frontend types/api.ts FraudRateTrend interface
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import AnyRole, get_session
from app.core.logging import get_logger
from app.schemas.model import (
    AnalyticsSummaryOut,
    CategoryBreakdownOut,
    FraudRateTrendOut,
    HealthOut,
    TopMerchantOut,
)
from app.services.fraud_service import FraudService

router = APIRouter(prefix="/analytics", tags=["Analytics"])
log = get_logger("api.analytics")


# ── Summary ───────────────────────────────────────────────────────────────────

@router.get(
    "/summary",
    response_model=AnalyticsSummaryOut,
    summary="Dashboard KPI summary (total transactions, fraud rate, open alerts)",
    dependencies=[AnyRole],
)
async def analytics_summary(
    session: AsyncSession = Depends(get_session),
) -> AnalyticsSummaryOut:
    svc = FraudService(session)
    data = await svc.get_analytics_summary()
    return AnalyticsSummaryOut(**data)


# ── Fraud rate trend ──────────────────────────────────────────────────────────

RANGE_TO_DAYS = {"24h": 1, "7d": 7, "30d": 30}


@router.get(
    "/fraud-rate",
    response_model=FraudRateTrendOut,
    summary="Daily fraud rate trend (24h / 7d / 30d)",
    dependencies=[AnyRole],
)
async def fraud_rate_trend(
    range: str = Query("7d", pattern="^(24h|7d|30d)$", description="Lookback window"),
    session: AsyncSession = Depends(get_session),
) -> FraudRateTrendOut:
    """
    Returns a FraudRateTrend object with parallel arrays:
      labels, fraud_counts, safe_counts, review_counts, fraud_rates
    Matches the FraudRateTrend interface in frontend/src/types/api.ts.
    """
    days = RANGE_TO_DAYS.get(range, 7)

    q = text("""
        SELECT
            DATE(predicted_at)                                          AS date,
            COUNT(*)                                                    AS total,
            SUM(CASE WHEN status = 'FRAUD'  THEN 1 ELSE 0 END)        AS fraud_count,
            SUM(CASE WHEN status = 'SAFE'   THEN 1 ELSE 0 END)        AS safe_count,
            SUM(CASE WHEN status = 'REVIEW' THEN 1 ELSE 0 END)        AS review_count
        FROM fraud_predictions
        WHERE predicted_at >= NOW() - INTERVAL :interval
        GROUP BY DATE(predicted_at)
        ORDER BY date
    """)
    result = await session.execute(q, {"interval": f"{days} days"})
    rows = result.mappings().all()

    labels: list[str] = []
    fraud_counts: list[int] = []
    safe_counts: list[int] = []
    review_counts: list[int] = []
    fraud_rates: list[float] = []

    for r in rows:
        total = r["total"] or 0
        fraud = r["fraud_count"] or 0
        safe = r["safe_count"] or 0
        review = r["review_count"] or 0
        rate = round(fraud / total, 4) if total > 0 else 0.0

        labels.append(str(r["date"]))
        fraud_counts.append(fraud)
        safe_counts.append(safe)
        review_counts.append(review)
        fraud_rates.append(rate)

    return FraudRateTrendOut(
        labels=labels,
        fraud_counts=fraud_counts,
        safe_counts=safe_counts,
        review_counts=review_counts,
        fraud_rates=fraud_rates,
    )


# ── Top risky merchants ───────────────────────────────────────────────────────

@router.get(
    "/top-merchants",
    response_model=list[TopMerchantOut],
    summary="Top merchants by fraud count",
    dependencies=[AnyRole],
)
async def top_risky_merchants(
    limit: int = Query(10, ge=1, le=50),
    session: AsyncSession = Depends(get_session),
) -> list[TopMerchantOut]:
    q = text("""
        SELECT
            t.merchant,
            COUNT(*)                                                  AS total_txn,
            SUM(CASE WHEN fp.status = 'FRAUD' THEN 1 ELSE 0 END)    AS fraud_count,
            ROUND(AVG(fp.risk_score)::numeric, 4)                    AS avg_risk
        FROM transactions t
        JOIN fraud_predictions fp ON t.transaction_ref = fp.transaction_ref
        GROUP BY t.merchant
        ORDER BY fraud_count DESC, avg_risk DESC
        LIMIT :limit
    """)
    result = await session.execute(q, {"limit": limit})
    rows = result.mappings().all()
    return [
        TopMerchantOut(
            merchant=r["merchant"],
            total_txn=r["total_txn"],
            fraud_count=r["fraud_count"],
            avg_risk=float(r["avg_risk"] or 0),
        )
        for r in rows
    ]


# ── Category breakdown ────────────────────────────────────────────────────────

@router.get(
    "/category-breakdown",
    response_model=list[CategoryBreakdownOut],
    summary="Fraud distribution by merchant category",
    dependencies=[AnyRole],
)
async def category_breakdown(
    session: AsyncSession = Depends(get_session),
) -> list[CategoryBreakdownOut]:
    q = text("""
        SELECT
            t.category,
            COUNT(*)                                                  AS total,
            SUM(CASE WHEN fp.status = 'FRAUD' THEN 1 ELSE 0 END)    AS fraud_count
        FROM transactions t
        JOIN fraud_predictions fp ON t.transaction_ref = fp.transaction_ref
        GROUP BY t.category
        ORDER BY fraud_count DESC
    """)
    result = await session.execute(q)
    rows = result.mappings().all()
    return [
        CategoryBreakdownOut(
            category=r["category"],
            total=r["total"],
            fraud_count=r["fraud_count"],
        )
        for r in rows
    ]


# ── Health endpoint ───────────────────────────────────────────────────────────

@router.get(
    "/health",
    response_model=HealthOut,
    summary="Deep health check: DB + Redis + ML model",
    tags=["Health"],
    include_in_schema=True,
)
async def deep_health(
    session: AsyncSession = Depends(get_session),
) -> HealthOut:
    import time
    from app.core.redis import ping_redis
    from app.ml.predictor import model_info
    from app.core.config import settings
    from app.db.session import check_db_connection

    start = time.monotonic()
    db_ok = await check_db_connection()
    redis_ok = await ping_redis()
    ml_info = model_info()
    model_ok = ml_info.get("loaded", False)
    overall = "ok" if (db_ok and redis_ok) else "degraded"
    uptime = time.monotonic() - start

    return HealthOut(
        status=overall,
        model="loaded" if model_ok else "fallback",
        db="ok" if db_ok else "error",
        redis="ok" if redis_ok else "error",
        version=settings.APP_VERSION,
        uptime_seconds=round(uptime, 3),
    )