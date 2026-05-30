"""
FraudShield — Model Versioning System
Tracks model versions, lineage, and promotion history.

Integrates with:
  - PostgreSQL (model_registry table via ModelRegistryRepository)
  - MLflow (experiment tracking)
  - Redis (active version cache for zero-downtime hot-swap)

Usage:
    from app.ml.model_versioning import ModelVersionManager

    mgr = ModelVersionManager(session)
    await mgr.register(model_id, path, metrics, features, data_source)
    await mgr.promote(model_id, promoted_by="admin")
    await mgr.rollback(promoted_by="admin")
    snapshot = await mgr.get_version_history()
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from typing import Optional

log = logging.getLogger("fraudshield.versioning")

# Redis key for the active deployed version
_ACTIVE_VERSION_KEY = "model:active_version"
_VERSION_HISTORY_KEY = "model:version_history"


class ModelVersionManager:
    """
    Manages the full lifecycle of FraudShield model versions:
      TRAINED → STAGING → DEPLOYED → ARCHIVED

    Invariant: at most ONE model has status='deployed' at any time.
    """

    def __init__(self, session=None):
        self._session = session

    # ── Registration ──────────────────────────────────────────────────────────

    async def register(
        self,
        model_id: str,
        model_path: str,
        model_type: str,
        metrics: dict,
        features: list[str],
        data_source: str = "database",
        mlflow_run_id: Optional[str] = None,
        notes: Optional[str] = None,
    ) -> dict:
        """
        Register a newly trained model as STAGING.
        Called automatically at the end of _run_training_pipeline.
        """
        version = {
            "model_id":      model_id,
            "model_type":    model_type,
            "model_path":    model_path,
            "status":        "staging",
            "metrics":       metrics,
            "features":      features,
            "data_source":   data_source,
            "mlflow_run_id": mlflow_run_id,
            "notes":         notes or "",
            "registered_at": datetime.now(timezone.utc).isoformat(),
            "deployed_at":   None,
            "archived_at":   None,
        }

        # Append to Redis version history
        await self._append_version_history(version)

        log.info(f"[Versioning] Registered model {model_id} as staging")
        return version

    # ── Promotion ─────────────────────────────────────────────────────────────

    async def promote(self, model_id: str, promoted_by: str) -> dict:
        """
        Promote a staging model to deployed.
        Archives the currently deployed model (if any).
        Hot-swaps the in-memory predictor with zero downtime.
        """
        history = await self._load_version_history()
        target = next((v for v in history if v["model_id"] == model_id), None)
        if not target:
            raise ValueError(f"Model '{model_id}' not found in version history")
        if target["status"] != "staging":
            raise ValueError(f"Model '{model_id}' is not in staging (status={target['status']})")

        # Archive current deployed model
        for v in history:
            if v["status"] == "deployed":
                v["status"] = "archived"
                v["archived_at"] = datetime.now(timezone.utc).isoformat()
                log.info(f"[Versioning] Archived previous model: {v['model_id']}")

        # Promote target
        target["status"]      = "deployed"
        target["deployed_at"] = datetime.now(timezone.utc).isoformat()
        target["promoted_by"] = promoted_by

        await self._save_version_history(history)

        # Update Redis active version pointer
        await self._set_active_version(target)

        # Hot-swap predictor
        try:
            from app.ml.predictor import load_model
            load_model(target["model_path"])
            log.info(f"[Versioning] Hot-swapped predictor to {model_id}")
        except Exception as exc:
            log.warning(f"[Versioning] Predictor hot-swap failed: {exc}")

        log.info(f"[Versioning] Promoted {model_id} to deployed by {promoted_by}")
        return target

    # ── Rollback ──────────────────────────────────────────────────────────────

    async def rollback(self, promoted_by: str) -> Optional[dict]:
        """
        Roll back to the most recently archived model.
        Demotes current deployed → staging, promotes last archive → deployed.
        """
        history = await self._load_version_history()

        current = next((v for v in history if v["status"] == "deployed"), None)
        archived = sorted(
            [v for v in history if v["status"] == "archived"],
            key=lambda v: v.get("archived_at") or "",
            reverse=True,
        )

        if not archived:
            log.warning("[Versioning] No archived model to roll back to")
            return None

        previous = archived[0]

        if current:
            current["status"] = "staging"
            current["deployed_at"] = None
            log.info(f"[Versioning] Demoted {current['model_id']} back to staging")

        previous["status"]      = "deployed"
        previous["deployed_at"] = datetime.now(timezone.utc).isoformat()
        previous["promoted_by"] = f"rollback:{promoted_by}"
        previous["archived_at"] = None

        await self._save_version_history(history)
        await self._set_active_version(previous)

        # Hot-swap predictor
        try:
            from app.ml.predictor import load_model
            load_model(previous["model_path"])
            log.info(f"[Versioning] Rolled back predictor to {previous['model_id']}")
        except Exception as exc:
            log.warning(f"[Versioning] Rollback predictor swap failed: {exc}")

        log.info(f"[Versioning] Rollback complete → {previous['model_id']}")
        return previous

    # ── History / snapshot ────────────────────────────────────────────────────

    async def get_version_history(self, limit: int = 20) -> list[dict]:
        """Return the most recent N model versions, newest first."""
        history = await self._load_version_history()
        return sorted(history, key=lambda v: v.get("registered_at") or "", reverse=True)[:limit]

    async def get_active_version(self) -> Optional[dict]:
        """Return metadata of the currently deployed model."""
        try:
            from app.core.redis import get_redis_client
            r = await get_redis_client()
            raw = await r.get(_ACTIVE_VERSION_KEY)
            if raw:
                return json.loads(raw)
        except Exception:
            pass

        # Fallback: scan history
        history = await self._load_version_history()
        return next((v for v in history if v["status"] == "deployed"), None)

    async def compare_versions(self, model_id_a: str, model_id_b: str) -> dict:
        """Compare metrics of two model versions side by side."""
        history = await self._load_version_history()
        lookup = {v["model_id"]: v for v in history}

        a = lookup.get(model_id_a)
        b = lookup.get(model_id_b)
        if not a or not b:
            return {"error": "One or both model IDs not found"}

        metrics_a = a.get("metrics", {})
        metrics_b = b.get("metrics", {})
        all_keys = set(metrics_a) | set(metrics_b)

        comparison = {}
        for k in sorted(all_keys):
            va = metrics_a.get(k)
            vb = metrics_b.get(k)
            if isinstance(va, (int, float)) and isinstance(vb, (int, float)):
                comparison[k] = {
                    model_id_a: round(float(va), 4),
                    model_id_b: round(float(vb), 4),
                    "delta":    round(float(vb) - float(va), 4),
                    "winner":   model_id_b if float(vb) > float(va) else model_id_a,
                }
        return {
            "model_a": {"model_id": model_id_a, "status": a["status"], "type": a.get("model_type")},
            "model_b": {"model_id": model_id_b, "status": b["status"], "type": b.get("model_type")},
            "metrics_comparison": comparison,
        }

    # ── Cleanup ───────────────────────────────────────────────────────────────

    async def cleanup_old_models(self, keep_archived: int = 5) -> int:
        """
        Remove oldest archived models from history (and disk) beyond keep_archived.
        Returns number of models cleaned up.
        """
        history = await self._load_version_history()
        archived = sorted(
            [v for v in history if v["status"] == "archived"],
            key=lambda v: v.get("archived_at") or "",
            reverse=True,
        )
        to_delete = archived[keep_archived:]
        cleaned = 0
        for v in to_delete:
            path = v.get("model_path", "")
            if path and os.path.exists(path):
                try:
                    os.remove(path)
                    cleaned += 1
                    log.info(f"[Versioning] Deleted old model file: {path}")
                except Exception as exc:
                    log.warning(f"[Versioning] Could not delete {path}: {exc}")
            history.remove(v)

        if cleaned:
            await self._save_version_history(history)
        return cleaned

    # ── Redis helpers ─────────────────────────────────────────────────────────

    async def _load_version_history(self) -> list[dict]:
        try:
            from app.core.redis import get_redis_client
            r = await get_redis_client()
            raw = await r.get(_VERSION_HISTORY_KEY)
            if raw:
                return json.loads(raw)
        except Exception as exc:
            log.debug(f"[Versioning] Redis load failed: {exc}")

        # Fallback: read from DB if session provided
        if self._session:
            try:
                from app.repositories.model_repo import ModelRegistryRepository
                repo = ModelRegistryRepository(self._session)
                models = await repo.list_all()
                return [self._orm_to_version(m) for m in models]
            except Exception as exc:
                log.debug(f"[Versioning] DB fallback load failed: {exc}")
        return []

    async def _save_version_history(self, history: list[dict]) -> None:
        try:
            from app.core.redis import get_redis_client
            r = await get_redis_client()
            # Keep for 90 days
            await r.setex(_VERSION_HISTORY_KEY, 86400 * 90, json.dumps(history))
        except Exception as exc:
            log.warning(f"[Versioning] Redis save failed: {exc}")

    async def _append_version_history(self, version: dict) -> None:
        history = await self._load_version_history()
        # Deduplicate by model_id
        history = [v for v in history if v["model_id"] != version["model_id"]]
        history.append(version)
        await self._save_version_history(history)

    async def _set_active_version(self, version: dict) -> None:
        try:
            from app.core.redis import get_redis_client
            r = await get_redis_client()
            await r.setex(_ACTIVE_VERSION_KEY, 86400 * 30, json.dumps(version))
        except Exception as exc:
            log.warning(f"[Versioning] Could not update active version in Redis: {exc}")

    @staticmethod
    def _orm_to_version(orm_model) -> dict:
        """Convert a ModelRegistry ORM object to a version dict."""
        return {
            "model_id":      orm_model.model_id,
            "model_type":    orm_model.model_type,
            "model_path":    orm_model.model_path,
            "status":        orm_model.status,
            "metrics":       orm_model.metrics or {},
            "features":      orm_model.features or [],
            "data_source":   getattr(orm_model, "data_source", "unknown"),
            "mlflow_run_id": getattr(orm_model, "mlflow_run_id", None),
            "notes":         "",
            "registered_at": orm_model.trained_at.isoformat() if orm_model.trained_at else None,
            "deployed_at":   None,
            "archived_at":   None,
        }


# ── Module-level singleton ────────────────────────────────────────────────────

_version_manager: Optional[ModelVersionManager] = None


def get_version_manager(session=None) -> ModelVersionManager:
    """Return module-level singleton, optionally injecting a DB session."""
    global _version_manager
    if _version_manager is None or session is not None:
        _version_manager = ModelVersionManager(session)
    return _version_manager
