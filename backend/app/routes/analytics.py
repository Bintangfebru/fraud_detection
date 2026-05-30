"""
FraudShield — Analytics & Health Routes
"""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from app.config.database import get_db
from app.config.settings import settings
from app.ml.predictor import model_info
from app.models.response_models import HealthResponse, ModelStatus

analytics_router = APIRouter(prefix="/v1/analytics", tags=["Analytics"])
health_router = APIRouter(tags=["Health"])


@health_router.get("/", response_model=HealthResponse)
async def root():
    return HealthResponse(
        status="operational",
        model="loaded" if model_info()["loaded"] else "fallback",
        db="ok",
        version=settings.APP_VERSION,
    )


@health_router.get("/health", response_model=HealthResponse)
async def health(db: AsyncSession = Depends(get_db)):
    """Health check — ping DB dan cek model."""
    db_status = "ok"
    try:
        await db.execute(text("SELECT 1"))
    except Exception:
        db_status = "error"

    return HealthResponse(
        status="ok" if db_status == "ok" else "degraded",
        model="loaded" if model_info()["loaded"] else "fallback",
        db=db_status,
        version=settings.APP_VERSION,
    )


@health_router.get("/v1/model/status", response_model=ModelStatus)
async def model_status():
    """Info model yang sedang aktif."""
    info = model_info()
    return ModelStatus(**info)


@analytics_router.get("/fraud-rate")
async def fraud_rate_trend(db: AsyncSession = Depends(get_db)):
    """Trend fraud rate per hari (30 hari terakhir)."""
    q = text("""
        SELECT
            DATE(predicted_at) AS date,
            COUNT(*) AS total,
            SUM(CASE WHEN status = 'FRAUD' THEN 1 ELSE 0 END) AS fraud_count,
            ROUND(AVG(risk_score)::numeric, 4) AS avg_score
        FROM fraud_predictions
        WHERE predicted_at >= NOW() - INTERVAL '30 days'
        GROUP BY DATE(predicted_at)
        ORDER BY date
    """)
    result = await db.execute(q)
    rows = result.fetchall()
    return [dict(r._mapping) for r in rows]


@analytics_router.get("/top-merchants")
async def top_risky_merchants(db: AsyncSession = Depends(get_db)):
    """Merchant dengan fraud terbanyak."""
    q = text("""
        SELECT t.merchant,
               COUNT(*) AS total_txn,
               SUM(CASE WHEN fp.status = 'FRAUD' THEN 1 ELSE 0 END) AS fraud_count,
               ROUND(AVG(fp.risk_score)::numeric, 4) AS avg_risk
        FROM transactions t
        JOIN fraud_predictions fp ON t.transaction_ref = fp.transaction_ref
        GROUP BY t.merchant
        ORDER BY fraud_count DESC
        LIMIT 10
    """)
    result = await db.execute(q)
    return [dict(r._mapping) for r in result.fetchall()]


@analytics_router.get("/category-breakdown")
async def category_breakdown(db: AsyncSession = Depends(get_db)):
    """Distribusi fraud per kategori."""
    q = text("""
        SELECT t.category,
               COUNT(*) AS total,
               SUM(CASE WHEN fp.status = 'FRAUD' THEN 1 ELSE 0 END) AS fraud_count
        FROM transactions t
        JOIN fraud_predictions fp ON t.transaction_ref = fp.transaction_ref
        GROUP BY t.category
        ORDER BY fraud_count DESC
    """)
    result = await db.execute(q)
    return [dict(r._mapping) for r in result.fetchall()]
