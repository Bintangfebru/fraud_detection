"""
FraudShield — API v1 Router Assembly

FIX: Added audit_router so GET /api/v1/audit?page=1&page_size=50 returns 200 instead of 404.
"""

from fastapi import APIRouter

from app.api.v1.auth import router as auth_router
from app.api.v1.fraud import router as fraud_router
from app.api.v1.models import router as models_router
from app.api.v1.analytics import router as analytics_router
from app.api.v1.users import router as users_router
from app.api.v1.streaming import router as streaming_router
from app.api.v1.audit import router as audit_router  

api_v1_router = APIRouter(prefix="/api/v1")

api_v1_router.include_router(auth_router)
api_v1_router.include_router(fraud_router)
api_v1_router.include_router(models_router)
api_v1_router.include_router(analytics_router)
api_v1_router.include_router(users_router)
api_v1_router.include_router(streaming_router)
api_v1_router.include_router(audit_router)         

__all__ = ["api_v1_router"]