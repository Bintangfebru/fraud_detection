"""
FraudShield — ML Model Management Router  (/api/v1/models/*)
Endpoints: status, registry, thresholds, feature importance, training jobs, promote,
           SHAP explanations, drift detection, observability, confidence scoring,
           fraud explainability reports, versioning, rollback, version comparison.

v3: Added /versions, /versions/compare, /versions/rollback, /versions/cleanup
    Wired model promotion through ModelVersionManager for proper hot-swap.
"""

from __future__ import annotations

import time
from typing import Optional

from fastapi import APIRouter, Depends, Path, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import (
    AdminOnly,
    AnalystOrAbove,
    AnyRole,
    get_current_user,
    get_session,
    require_roles,
)
from app.core.config import settings
from app.core.logging import get_logger
from app.core.security import Role
from app.ml.predictor import model_info
from app.models.user import User
from app.schemas.model import (
    FeatureImportanceOut,
    ModelOut,
    ModelRegistryOut,
    ModelStatusOut,
    PromoteModelRequest,
    ThresholdOut,
    ThresholdUpdate,
    TrainRequest,
    TrainingJobOut,
)
from app.services.model_service import ModelService

router = APIRouter(prefix="/models", tags=["Model Management"])
log = get_logger("api.models")


# ── Root (alias of /registry) ─────────────────────────────────────────────────

@router.get(
    "",
    response_model=ModelRegistryOut,
    summary="All model versions — alias of /registry",
    dependencies=[AnyRole],
)
async def list_models_root(
    session: AsyncSession = Depends(get_session),
) -> ModelRegistryOut:
    svc = ModelService(session)
    models = await svc.list_models()
    return ModelRegistryOut(
        models=[ModelOut.model_validate(m) for m in models],
        total=len(models),
    )


# ── Status ────────────────────────────────────────────────────────────────────

@router.get(
    "/status",
    response_model=ModelStatusOut,
    summary="Current deployed model status and active thresholds",
    dependencies=[AnyRole],
)
async def model_status(
    session: AsyncSession = Depends(get_session),
) -> ModelStatusOut:
    svc = ModelService(session)
    info = model_info()
    thresholds = await svc.get_thresholds()
    deployed = await svc.get_deployed_model()

    return ModelStatusOut(
        loaded=info.get("loaded", False),
        model_type=info.get("type", "Unknown"),
        name=info.get("name", "Unknown"),
        path=settings.MODEL_PATH,
        selected_features=settings.SELECTED_FEATURES,
        thresholds={"fraud": thresholds.fraud, "review": thresholds.review},
        deployed_model_id=deployed.model_id if deployed else None,
    )


# ── Registry ──────────────────────────────────────────────────────────────────

@router.get(
    "/registry",
    response_model=ModelRegistryOut,
    summary="All model versions (deployed, staging, archived)",
    dependencies=[AnyRole],
)
async def list_registry(
    session: AsyncSession = Depends(get_session),
) -> ModelRegistryOut:
    svc = ModelService(session)
    models = await svc.list_models()
    return ModelRegistryOut(
        models=[ModelOut.model_validate(m) for m in models],
        total=len(models),
    )


@router.post(
    "/registry/{model_id}/promote",
    response_model=ModelOut,
    summary="Promote a staging model to production (Admin only)",
    dependencies=[AdminOnly],
)
async def promote_model(
    model_id: str = Path(..., description="Model ID string (e.g. ens-v20260101_120000)"),
    body: PromoteModelRequest = ...,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> ModelOut:
    svc = ModelService(session)

    # Use ModelVersionManager for proper hot-swap + archival
    from app.ml.model_versioning import get_version_manager
    mgr = get_version_manager(session)
    try:
        await mgr.promote(model_id=model_id, promoted_by=current_user.username)
    except Exception as exc:
        log.warning(f"[Versioning] promote via manager failed ({exc}), falling back to DB-only promote")

    result = await svc.promote_model(model_id=model_id, promoted_by=current_user.username)
    log.info(f"[{current_user.username}] Promoted model: {model_id}")
    return ModelOut.model_validate(result)


# ── Thresholds ────────────────────────────────────────────────────────────────

@router.get(
    "/thresholds",
    response_model=ThresholdOut,
    summary="Current active fraud/review thresholds",
    dependencies=[AnyRole],
)
async def get_thresholds(
    session: AsyncSession = Depends(get_session),
) -> ThresholdOut:
    svc = ModelService(session)
    return await svc.get_thresholds()


@router.put(
    "/thresholds",
    response_model=ThresholdOut,
    summary="Update fraud decision thresholds (Admin only)",
    dependencies=[AdminOnly],
)
async def update_thresholds(
    body: ThresholdUpdate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> ThresholdOut:
    svc = ModelService(session)
    result = await svc.update_thresholds(
        fraud=body.fraud,
        review=body.review,
        set_by=current_user.username,
        notes=body.notes,
    )
    log.info(f"[{current_user.username}] Thresholds updated: fraud={body.fraud} review={body.review}")
    return result


# ── Feature importance ────────────────────────────────────────────────────────

@router.get(
    "/feature-importance",
    response_model=FeatureImportanceOut,
    summary="SHAP / model feature importance for the deployed model",
    dependencies=[AnyRole],
)
async def feature_importance(
    session: AsyncSession = Depends(get_session),
) -> FeatureImportanceOut:
    deployed = await ModelService(session).get_deployed_model()
    model_id = deployed.model_id if deployed else "unknown"
    raw = _extract_importances()
    return FeatureImportanceOut(
        features=raw,
        model_id=model_id,
        method="feature_importances_" if raw else "static_fallback",
    )


def _extract_importances() -> list:
    """Pull feature_importances_ from the loaded model if available."""
    try:
        from app.ml.predictor import _pipeline  # type: ignore[attr-defined]
        clf = _pipeline.named_steps.get("clf") if hasattr(_pipeline, "named_steps") else _pipeline
        if hasattr(clf, "feature_importances_"):
            features = settings.SELECTED_FEATURES
            importances = clf.feature_importances_
            ranked = sorted(
                zip(features, importances),
                key=lambda x: x[1],
                reverse=True,
            )
            return [
                {
                    "name": name,
                    "importance": round(float(imp), 4),
                    "direction": "positive" if imp > 0.05 else "neutral",
                }
                for name, imp in ranked
            ]
        # Ensemble models expose feature_importances() dict
        if hasattr(clf, "feature_importances") and callable(clf.feature_importances):
            ranked = sorted(clf.feature_importances().items(), key=lambda x: x[1], reverse=True)
            return [
                {"name": k, "importance": round(v, 4), "direction": "positive" if v > 0.05 else "neutral"}
                for k, v in ranked
            ]
    except Exception:
        pass

    # Static fallback
    return [
        {"name": "amt_log",               "importance": 0.21, "direction": "positive"},
        {"name": "amt_ratio",             "importance": 0.18, "direction": "positive"},
        {"name": "hour",                  "importance": 0.14, "direction": "positive"},
        {"name": "txn_count_per_card",    "importance": 0.12, "direction": "positive"},
        {"name": "unique_merchants",      "importance": 0.09, "direction": "negative"},
        {"name": "category_misc_net",     "importance": 0.07, "direction": "positive"},
        {"name": "category_shopping_net", "importance": 0.06, "direction": "positive"},
        {"name": "amt_mean_per_card",     "importance": 0.05, "direction": "neutral"},
    ]


# ── Training jobs ─────────────────────────────────────────────────────────────

@router.post(
    "/training/start",
    response_model=TrainingJobOut,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Trigger a new model training job (Admin only) — supports XGBoost, LightGBM, Ensemble",
    dependencies=[AdminOnly],
)
async def start_training(
    req: TrainRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> TrainingJobOut:
    """
    Kick off an asynchronous training job against real PostgreSQL data.
    model_type options: RandomForest, GradientBoosting, XGBoost, LightGBM, Ensemble
    Returns immediately with job_id — poll /training/{job_id} for status.
    """
    svc = ModelService(session)
    job = await svc.start_training(req=req, started_by=current_user.username)
    log.info(f"[{current_user.username}] Training started: {job.job_id} type={req.model_type}")
    return TrainingJobOut(
        job_id=job.job_id,
        model_type=job.model_type,
        status=job.status,
        progress_pct=job.progress_pct,
        started_by=job.started_by,
        started_at=job.started_at,
    )


@router.get(
    "/training/{job_id}",
    summary="Poll training job status",
    dependencies=[AnyRole],
)
async def get_training_job(
    job_id: str = Path(...),
    session: AsyncSession = Depends(get_session),
) -> dict:
    svc = ModelService(session)
    return await svc.get_job(job_id)


@router.get(
    "/training",
    summary="List recent training jobs",
    dependencies=[AnalystOrAbove],
)
async def list_training_jobs(
    session: AsyncSession = Depends(get_session),
) -> dict:
    svc = ModelService(session)
    jobs = await svc.list_jobs()
    return {"jobs": jobs, "total": len(jobs)}


# ── SHAP Explanations ─────────────────────────────────────────────────────────

@router.get(
    "/shap",
    summary="SHAP feature importance summary for recent transactions",
    dependencies=[AnalystOrAbove],
)
async def get_shap_summary() -> dict:
    try:
        from app.ml.explainability import get_explainer
        explainer = get_explainer()
        is_ready = explainer._explainer is not None
        return {
            "explainer_ready": is_ready,
            "explainer_type": type(explainer._explainer).__name__ if is_ready else "none",
            "top_features": _extract_importances()[:10],
        }
    except Exception as exc:
        return {"explainer_ready": False, "error": str(exc)}


# ── Confidence Scoring ────────────────────────────────────────────────────────

@router.get(
    "/confidence/{transaction_ref}",
    summary="Fraud confidence score for a specific transaction",
    dependencies=[AnalystOrAbove],
)
async def get_confidence_score(
    transaction_ref: str = Path(..., description="Transaction reference ID"),
    session: AsyncSession = Depends(get_session),
) -> dict:
    pred = await _fetch_prediction_features(transaction_ref, session)
    if not pred:
        return {"transaction_ref": transaction_ref, "error": "Prediction not found"}

    from app.ml.explainability import compute_confidence_score
    thresholds = await ModelService(session).get_thresholds()

    confidence = compute_confidence_score(
        fraud_probability=float(pred.get("risk_score", 0.0)),
        fraud_threshold=thresholds.fraud,
        review_threshold=thresholds.review,
    )
    confidence["transaction_ref"] = transaction_ref
    return confidence


# ── Fraud Explainability Report ───────────────────────────────────────────────

@router.get(
    "/report/{transaction_ref}",
    summary="Full fraud explainability report for a transaction",
    dependencies=[AnalystOrAbove],
)
async def get_fraud_report(
    transaction_ref: str = Path(..., description="Transaction reference ID"),
    session: AsyncSession = Depends(get_session),
) -> dict:
    pred = await _fetch_prediction_features(transaction_ref, session)
    if not pred:
        return {"transaction_ref": transaction_ref, "error": "Prediction not found"}

    from app.ml.explainability import get_explainer, generate_fraud_report
    from app.ml.feature_engineering import SELECTED_FEATURES

    thresholds = await ModelService(session).get_thresholds()
    features   = pred.get("features", {})
    risk_score = float(pred.get("risk_score", 0.0))

    explainer = get_explainer()
    shap_contribs = explainer.explain_single(
        features=features,
        feature_names=SELECTED_FEATURES,
        top_k=10,
    )

    report = generate_fraud_report(
        transaction_ref=transaction_ref,
        features=features,
        fraud_probability=risk_score,
        shap_contributions=shap_contribs if isinstance(shap_contribs, list) else [],
        fraud_threshold=thresholds.fraud,
        review_threshold=thresholds.review,
    )
    return report


# ── Concept Drift Detection ───────────────────────────────────────────────────

@router.get(
    "/drift/status",
    summary="Latest concept drift detection report",
    dependencies=[AnalystOrAbove],
)
async def get_drift_status() -> dict:
    try:
        import json
        from app.core.redis import get_redis_client
        r = await get_redis_client()
        raw = await r.get("drift:latest_report")
        if raw:
            return json.loads(raw)
        return {
            "status": "no_data",
            "message": "Drift detection not yet run — scheduler runs every 6 hours",
        }
    except Exception as exc:
        return {"status": "error", "detail": str(exc)}


@router.post(
    "/drift/check",
    summary="Trigger an immediate drift check (Admin only)",
    dependencies=[AdminOnly],
)
async def trigger_drift_check() -> dict:
    try:
        from app.ml.auto_retrain import check_drift_and_retrain
        import asyncio
        asyncio.create_task(check_drift_and_retrain())
        return {"triggered": True, "message": "Drift check triggered in background"}
    except Exception as exc:
        return {"triggered": False, "error": str(exc)}


# ── ML Observability ─────────────────────────────────────────────────────────

@router.get(
    "/observability",
    summary="ML observability dashboard — latency, metrics, drift, scheduler",
    dependencies=[AnalystOrAbove],
)
async def get_observability() -> dict:
    from app.ml.observability import get_observability_snapshot
    return await get_observability_snapshot()


# ── Feature Store ─────────────────────────────────────────────────────────────

@router.get(
    "/feature-store/views",
    summary="List registered feature store views",
    dependencies=[AnyRole],
)
async def list_feature_views() -> dict:
    from app.ml.feature_store import get_feature_store
    store = get_feature_store()
    return {
        "views": store.list_views(),
        "total": len(store.list_views()),
    }


@router.get(
    "/feature-store/entity/{entity_key}",
    summary="Get online features for an entity from the feature store",
    dependencies=[AnalystOrAbove],
)
async def get_entity_features(
    entity_key: str = Path(..., description="Entity key e.g. card:abc123"),
    view: str = Query("card_aggregates", description="Feature view name"),
) -> dict:
    from app.ml.feature_store import get_feature_store
    store = get_feature_store()
    features = await store.get_online_features(entity_key=entity_key, view=view)
    return {
        "entity_key": entity_key,
        "view": view,
        "features": features or {},
        "cache_hit": features is not None,
    }


# ── Auto-retrain scheduler ────────────────────────────────────────────────────

@router.get(
    "/scheduler/status",
    summary="Auto-retraining scheduler status",
    dependencies=[AnalystOrAbove],
)
async def get_scheduler_status() -> dict:
    from app.ml.auto_retrain import get_scheduler_status
    return get_scheduler_status()


# ── Model Versioning ──────────────────────────────────────────────────────────

@router.get(
    "/versions",
    summary="Full model version history (deployed, staging, archived)",
    dependencies=[AnalystOrAbove],
)
async def get_version_history(
    limit: int = Query(20, ge=1, le=100),
    session: AsyncSession = Depends(get_session),
) -> dict:
    from app.ml.model_versioning import get_version_manager
    mgr = get_version_manager(session)
    history = await mgr.get_version_history(limit=limit)
    active  = await mgr.get_active_version()
    return {
        "active_model": active,
        "history": history,
        "total": len(history),
    }


@router.get(
    "/versions/compare",
    summary="Compare metrics of two model versions side by side",
    dependencies=[AnalystOrAbove],
)
async def compare_model_versions(
    model_id_a: str = Query(..., description="First model ID"),
    model_id_b: str = Query(..., description="Second model ID"),
    session: AsyncSession = Depends(get_session),
) -> dict:
    from app.ml.model_versioning import get_version_manager
    mgr = get_version_manager(session)
    return await mgr.compare_versions(model_id_a, model_id_b)


@router.post(
    "/versions/rollback",
    summary="Roll back to the previously deployed model (Admin only)",
    dependencies=[AdminOnly],
)
async def rollback_model(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    from app.ml.model_versioning import get_version_manager
    mgr = get_version_manager(session)
    result = await mgr.rollback(promoted_by=current_user.username)
    if result:
        log.info(f"[{current_user.username}] Rollback to {result['model_id']}")
        return {"rolled_back_to": result["model_id"], "details": result}
    return {"error": "No archived model available for rollback"}


@router.delete(
    "/versions/cleanup",
    summary="Delete old archived model files from disk (Admin only)",
    dependencies=[AdminOnly],
)
async def cleanup_old_versions(
    keep: int = Query(5, ge=1, le=20, description="Number of archived models to keep"),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    from app.ml.model_versioning import get_version_manager
    mgr = get_version_manager(session)
    cleaned = await mgr.cleanup_old_models(keep_archived=keep)
    log.info(f"[{current_user.username}] Cleaned up {cleaned} old model files")
    return {"cleaned_files": cleaned, "kept_archived": keep}


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _fetch_prediction_features(
    transaction_ref: str,
    session: AsyncSession,
) -> Optional[dict]:
    try:
        from sqlalchemy import text
        result = await session.execute(
            text("""
                SELECT fp.risk_score, fp.status,
                       t.amt, t.hour, t.month, t.amt_log, t.amt_mean_per_card,
                       t.amt_ratio, t.txn_count_per_card, t.unique_merchants,
                       t.unique_categories, t.amt_std_per_card,
                       t.category_food_dining, t.category_gas_transport,
                       t.category_grocery_pos, t.category_kids_pets,
                       t.category_misc_net, t.category_misc_pos,
                       t.category_personal_care, t.category_shopping_net,
                       t.merchant, t.city
                FROM fraud_predictions fp
                JOIN transactions t ON fp.transaction_ref = t.transaction_ref
                WHERE fp.transaction_ref = :ref
                LIMIT 1
            """),
            {"ref": transaction_ref},
        )
        row = result.mappings().first()
        if not row:
            return None

        features = {
            k: float(v) if isinstance(v, (int, float)) else str(v) if v is not None else 0.0
            for k, v in row.items()
            if k not in ("risk_score", "status")
        }
        return {
            "risk_score": float(row["risk_score"]),
            "status": row["status"],
            "features": features,
        }
    except Exception as exc:
        log.warning(f"_fetch_prediction_features error for {transaction_ref}: {exc}")
        return None


def _now_iso() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()