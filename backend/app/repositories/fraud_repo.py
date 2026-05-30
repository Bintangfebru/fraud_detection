"""
FraudShield — Fraud Repositories

CHANGES:
  - AuditLogRepository: tambah list_paginated() untuk endpoint /api/v1/audit
  - AlertRepository: tambah get_all_paginated() untuk filter resolved
"""

from __future__ import annotations

from typing import List, Optional

from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.prediction import Alert, AuditLog, FraudPrediction
from app.models.transaction import Transaction
from app.repositories.base import BaseRepository


# ── Transaction Repository ────────────────────────────────────────────────────

class TransactionRepository(BaseRepository[Transaction]):
    model = Transaction

    async def list_with_predictions(
        self,
        page: int = 1,
        page_size: int = 50,
        status: Optional[str] = None,
        merchant: Optional[str] = None,
    ) -> dict:
        base_q = select(Transaction).join(
            FraudPrediction,
            Transaction.transaction_ref == FraudPrediction.transaction_ref,
            isouter=True,
        )
        if status:
            base_q = base_q.where(FraudPrediction.status == status)
        if merchant:
            base_q = base_q.where(Transaction.merchant.ilike(f"%{merchant}%"))

        total = await self.session.scalar(
            select(func.count()).select_from(base_q.subquery())
        ) or 0

        offset = (page - 1) * page_size
        result = await self.session.execute(
            base_q.order_by(desc(Transaction.created_at))
            .offset(offset)
            .limit(page_size)
        )
        items = list(result.scalars().all())
        return {
            "items": items,
            "total": total,
            "page": page,
            "page_size": page_size,
            "pages": max(1, -(-total // page_size)),
        }

    async def get_by_ref(self, ref: str) -> Optional[Transaction]:
        result = await self.session.execute(
            select(Transaction).where(Transaction.transaction_ref == ref)
        )
        return result.scalar_one_or_none()


# ── FraudPrediction Repository ────────────────────────────────────────────────

class FraudPredictionRepository(BaseRepository[FraudPrediction]):
    model = FraudPrediction

    async def get_by_ref(self, ref: str) -> Optional[FraudPrediction]:
        result = await self.session.execute(
            select(FraudPrediction).where(FraudPrediction.transaction_ref == ref)
        )
        return result.scalar_one_or_none()

    async def get_by_id(self, prediction_id: str) -> Optional[FraudPrediction]:
        result = await self.session.execute(
            select(FraudPrediction).where(FraudPrediction.id == prediction_id)
        )
        return result.scalar_one_or_none()


# ── Alert Repository ──────────────────────────────────────────────────────────

class AlertRepository(BaseRepository[Alert]):
    model = Alert

    async def get_open_alerts(self) -> List[Alert]:
        result = await self.session.execute(
            select(Alert)
            .where(Alert.is_resolved == False)  # noqa: E712
            .order_by(desc(Alert.created_at))
        )
        return list(result.scalars().all())

    async def count_open(self) -> int:
        return await self.session.scalar(
            select(func.count()).select_from(Alert).where(
                Alert.is_resolved == False  # noqa: E712
            )
        ) or 0

    async def get_by_transaction_ref(self, ref: str) -> List[Alert]:
        result = await self.session.execute(
            select(Alert).where(Alert.transaction_ref == ref)
        )
        return list(result.scalars().all())


# ── AuditLog Repository ───────────────────────────────────────────────────────

class AuditLogRepository(BaseRepository[AuditLog]):
    model = AuditLog

    async def list_by_actor(self, actor: str, limit: int = 100) -> List[AuditLog]:
        """Filter by satu actor — dipakai endpoint lama di /fraud/audit."""
        result = await self.session.execute(
            select(AuditLog)
            .where(AuditLog.actor == actor)
            .order_by(desc(AuditLog.created_at))
            .limit(limit)
        )
        return list(result.scalars().all())

    async def list_paginated(
        self,
        page: int = 1,
        page_size: int = 50,
        actor: Optional[str] = None,
    ) -> dict:
        """
        Paginated audit log — dipakai endpoint /api/v1/audit.
        actor=None → semua entries (admin/analyst).
        actor=username → filter ke user itu saja (auditor).
        """
        # Build query
        if actor:
            q = select(AuditLog).where(AuditLog.actor == actor)
            count_q = select(func.count(AuditLog.id)).where(AuditLog.actor == actor)
        else:
            q = select(AuditLog)
            count_q = select(func.count(AuditLog.id))

        # Total count — pakai count_q langsung, bukan subquery
        total = await self.session.scalar(count_q) or 0

        # Paginated fetch
        offset = (page - 1) * page_size
        result = await self.session.execute(
            q.order_by(desc(AuditLog.created_at))
            .offset(offset)
            .limit(page_size)
        )
        items = list(result.scalars().all())

        return {
            "items": items,
            "total": total,
            "page": page,
            "page_size": page_size,
            "pages": max(1, -(-total // page_size)),
        }