"""ML model registry and threshold repository."""

from __future__ import annotations

from typing import List, Optional

from sqlalchemy import desc, select, update

from app.models.ml_models import ModelRegistry, Threshold, TrainingJob
from app.repositories.base import BaseRepository


class ModelRegistryRepository(BaseRepository[ModelRegistry]):
    model = ModelRegistry

    async def get_by_model_id(self, model_id: str) -> Optional[ModelRegistry]:
        result = await self.session.execute(
            select(ModelRegistry).where(ModelRegistry.model_id == model_id)
        )
        return result.scalar_one_or_none()

    async def get_deployed(self) -> Optional[ModelRegistry]:
        result = await self.session.execute(
            select(ModelRegistry).where(ModelRegistry.status == "deployed")
        )
        return result.scalar_one_or_none()

    async def list_all(self) -> List[ModelRegistry]:
        result = await self.session.execute(
            select(ModelRegistry).order_by(desc(ModelRegistry.created_at))
        )
        return list(result.scalars().all())

    async def archive_deployed(self) -> None:
        """Archive any currently deployed model before promoting a new one."""
        await self.session.execute(
            update(ModelRegistry)
            .where(ModelRegistry.status == "deployed")
            .values(status="archived")
        )

    async def promote(self, registry: ModelRegistry, promoted_by: str) -> ModelRegistry:
        from datetime import datetime, timezone
        await self.archive_deployed()
        registry.status = "deployed"
        registry.promoted_at = datetime.now(timezone.utc)
        registry.promoted_by = promoted_by
        await self.session.flush()
        return registry


class ThresholdRepository(BaseRepository[Threshold]):
    model = Threshold

    async def get_active(self) -> Optional[Threshold]:
        result = await self.session.execute(
            select(Threshold)
            .where(Threshold.is_active == True)  # noqa: E712
            .order_by(desc(Threshold.created_at))
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def set_active(
        self,
        fraud: float,
        review: float,
        set_by: str,
        notes: Optional[str] = None,
    ) -> Threshold:
        """Deactivate all existing thresholds and insert a new active one."""
        await self.session.execute(
            update(Threshold).values(is_active=False)
        )
        threshold = Threshold(
            fraud_threshold=fraud,
            review_threshold=review,
            is_active=True,
            set_by=set_by,
            notes=notes,
        )
        self.session.add(threshold)
        await self.session.flush()
        return threshold


class TrainingJobRepository(BaseRepository[TrainingJob]):
    model = TrainingJob

    async def get_by_job_id(self, job_id: str) -> Optional[TrainingJob]:
        result = await self.session.execute(
            select(TrainingJob).where(TrainingJob.job_id == job_id)
        )
        return result.scalar_one_or_none()

    async def list_recent(self, limit: int = 20) -> List[TrainingJob]:
        result = await self.session.execute(
            select(TrainingJob)
            .order_by(desc(TrainingJob.started_at))
            .limit(limit)
        )
        return list(result.scalars().all())

    async def update_status(
        self, job: TrainingJob, **fields
    ) -> TrainingJob:
        return await self.update(job, **fields)
