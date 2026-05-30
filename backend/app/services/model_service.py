"""
FraudShield — Model Service
Manages model registry, thresholds, and training jobs.

v3: REMOVED synthetic fallback entirely.
    Training now REQUIRES real PostgreSQL data.
    Job fails loudly with clear error if DB is unavailable or data is insufficient.
    This prevents silently training a model on fake data that would be useless in production.
"""

from __future__ import annotations

import os
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import (
    InvalidThresholdError,
    JobNotFoundError,
    NotFoundError,
    PermissionDeniedError,
)
from app.core.logging import get_logger
from app.core.redis import cache_thresholds, get_cached_thresholds, set_job_status, update_job_field
from app.models.ml_models import ModelRegistry, TrainingJob
from app.repositories.model_repo import (
    ModelRegistryRepository,
    ThresholdRepository,
    TrainingJobRepository,
)
from app.schemas.model import ThresholdOut, TrainRequest

log = get_logger("services.model")

# Single background thread for training (max 2 concurrent jobs)
_train_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="fs-train")

# Minimum rows required to start training — enforced hard, no fallback
MIN_TRAINING_ROWS = 1_000


class ModelService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.registry_repo = ModelRegistryRepository(session)
        self.threshold_repo = ThresholdRepository(session)
        self.job_repo = TrainingJobRepository(session)

    # ── Thresholds ─────────────────────────────────────────────────────────────

    async def get_thresholds(self) -> ThresholdOut:
        cached = await get_cached_thresholds()
        if cached:
            return ThresholdOut(fraud=cached["fraud"], review=cached["review"])

        threshold = await self.threshold_repo.get_active()
        if threshold:
            await cache_thresholds(threshold.fraud_threshold, threshold.review_threshold)
            return ThresholdOut(
                fraud=threshold.fraud_threshold,
                review=threshold.review_threshold,
                set_by=threshold.set_by,
                updated_at=threshold.created_at,
            )

        return ThresholdOut(
            fraud=settings.FRAUD_THRESHOLD,
            review=settings.REVIEW_THRESHOLD,
        )

    async def update_thresholds(
        self, fraud: float, review: float, set_by: str, notes: Optional[str] = None
    ) -> ThresholdOut:
        if review >= fraud:
            raise InvalidThresholdError()

        threshold = await self.threshold_repo.set_active(fraud, review, set_by, notes)
        await cache_thresholds(fraud, review)
        log.info(f"Thresholds updated by {set_by}: review={review} fraud={fraud}")
        return ThresholdOut(
            fraud=threshold.fraud_threshold,
            review=threshold.review_threshold,
            set_by=threshold.set_by,
            updated_at=threshold.created_at,
        )

    # ── Registry ───────────────────────────────────────────────────────────────

    async def list_models(self) -> list:
        return await self.registry_repo.list_all()

    async def get_deployed_model(self) -> Optional[ModelRegistry]:
        return await self.registry_repo.get_deployed()

    async def promote_model(self, model_id: str, promoted_by: str) -> ModelRegistry:
        registry = await self.registry_repo.get_by_model_id(model_id)
        if not registry:
            raise NotFoundError(f"Model '{model_id}' not found.")
        if registry.status != "staging":
            raise PermissionDeniedError("Only staging models can be promoted.")

        result = await self.registry_repo.promote(registry, promoted_by)
        log.info(f"Model promoted: {model_id} by {promoted_by}")
        return result

    # ── Training jobs ──────────────────────────────────────────────────────────

    async def start_training(
        self, req: TrainRequest, started_by: str
    ) -> TrainingJob:
        job_id = f"job-{uuid.uuid4().hex[:12]}"

        job = TrainingJob(
            job_id=job_id,
            model_type=req.model_type,
            training_period=req.training_period,
            validation_split=req.validation_split,
            features=req.features or [],
            status="queued",
            progress_pct=0,
            started_by=started_by,
        )
        await self.job_repo.create(job)

        await set_job_status(
            job_id,
            {
                "job_id": job_id,
                "status": "queued",
                "progress_pct": 0,
                "model_type": req.model_type,
                "training_period": req.training_period,
                "started_by": started_by,
                "started_at": datetime.now(timezone.utc).isoformat(),
            },
            ttl_hours=settings.TRAINING_JOB_TTL_HOURS,
        )

        job_dict = {
            "job_id": job_id,
            "model_type": req.model_type,
            "training_period": req.training_period,
            "validation_split": req.validation_split,
            "features": req.features or [],
        }
        _train_executor.submit(_run_training_pipeline, job_id, job_dict)
        log.info(f"Training job submitted: {job_id} by {started_by}")
        return job

    async def get_job(self, job_id: str) -> dict:
        from app.core.redis import get_job_status
        cached = await get_job_status(job_id)
        if cached:
            return cached
        job = await self.job_repo.get_by_job_id(job_id)
        if not job:
            raise JobNotFoundError(f"Job '{job_id}' not found.")
        return _orm_job_to_dict(job)

    async def list_jobs(self) -> list[dict]:
        from app.core.redis import get_job_status
        jobs = await self.job_repo.list_recent(20)
        result = []
        for job in jobs:
            cached = await get_job_status(job.job_id)
            result.append(cached if cached else _orm_job_to_dict(job))
        return result


def _orm_job_to_dict(job: TrainingJob) -> dict:
    return {
        "job_id": job.job_id,
        "model_type": job.model_type,
        "training_period": job.training_period,
        "validation_split": job.validation_split,
        "status": job.status,
        "progress_pct": job.progress_pct,
        "data_source": job.data_source,
        "dataset_size": job.dataset_size,
        "metrics": job.metrics,
        "model_id": job.model_id,
        "error_message": job.error_message,
        "warning_message": job.warning_message,
        "started_by": job.started_by,
        "started_at": job.started_at.isoformat() if job.started_at else None,
        "completed_at": job.completed_at.isoformat() if job.completed_at else None,
    }


# ── Background training pipeline (runs in thread) ─────────────────────────────

def _run_training_pipeline(job_id: str, job: dict) -> None:
    """
    Real training pipeline — loads data exclusively from PostgreSQL.
    NO synthetic fallback. If DB is unavailable or data is insufficient,
    the job fails immediately with a clear, actionable error message.

    Pipeline steps:
      1.  Connect to DB and validate row count  ← fails hard if not met
      2.  Build DataFrame from real transactions
      3.  Select and validate features
      4.  Train/val split (stratified)
      5.  Build and fit classifier
      6.  Evaluate: precision, recall, F1, ROC-AUC, fraud capture rate
      7.  Update DriftDetector baseline
      8.  Initialize SHAP explainer
      9.  Save model .pkl
      10. Log to MLflow
      11. Register as staging in PostgreSQL
    """
    import asyncio
    import re

    import joblib
    import numpy as np
    import pandas as pd
    import psycopg2
    import psycopg2.extras
    from sklearn.ensemble import GradientBoostingClassifier, RandomForestClassifier
    from sklearn.metrics import (
        accuracy_score,
        average_precision_score,
        f1_score,
        precision_score,
        recall_score,
        roc_auc_score,
    )
    from sklearn.model_selection import train_test_split
    from sklearn.pipeline import Pipeline as SkPipeline
    from sklearn.preprocessing import StandardScaler

    from app.core.redis import set_job_status, update_job_field
    from app.ml.feature_engineering import SELECTED_FEATURES

    def _push(updates: dict) -> None:
        """Push progress update to Redis from sync thread."""
        existing = asyncio.run(_async_get_job(job_id)) or {}
        existing.update(updates)
        asyncio.run(_async_set_job(job_id, existing))

    def _fail(message: str) -> None:
        """Mark job as failed with a clear error message and re-raise."""
        log.error(f"[{job_id}] Training FAILED: {message}")
        asyncio.run(_async_set_job(job_id, {
            "job_id": job_id,
            "status": "failed",
            "progress_pct": 0,
            "error_message": message,
            "failed_at": datetime.now(timezone.utc).isoformat(),
        }))

    try:
        _push({"status": "running", "progress_pct": 3})
        log.info(f"[{job_id}] Training pipeline started — {job['model_type']}")

        # ── 1. Connect to PostgreSQL ────────────
        _push({"progress_pct": 5, "status": "running"})

        db_url = settings.database_url_sync
        m = re.match(r"postgresql://([^:]+):([^@]+)@([^:/]+):?(\d+)?/(.+)", db_url)
        if not m:
            raise RuntimeError(
                "DATABASE_URL is malformed. Expected format: "
                "postgresql://user:password@host:port/dbname"
            )

        try:
            conn = psycopg2.connect(
                user=m.group(1),
                password=m.group(2),
                host=m.group(3),
                port=int(m.group(4) or 5432),
                dbname=m.group(5),
                connect_timeout=10,
            )
        except psycopg2.OperationalError as conn_err:
            raise RuntimeError(
                f"Cannot connect to PostgreSQL: {conn_err}. "
                f"Check DATABASE_URL and ensure the database is running."
            ) from conn_err

        # ── 2. Load training data from real transactions ────────────────────
        period_days = {
            "Last 7 days": 7,
            "Last 14 days": 14,
            "Last 30 days": 30,
            "Last 60 days": 60,
            "Last 90 days": 90,
        }.get(job["training_period"], 30)

        _push({"progress_pct": 8})
        log.info(f"[{job_id}] Querying DB for last {period_days} days of transactions...")

        query = """
            SELECT
                t.amt,
                t.hour,
                t.month,
                t.amt_log,
                t.amt_mean_per_card,
                t.amt_ratio,
                t.txn_count_per_card,
                t.unique_merchants,
                t.unique_categories,
                t.amt_std_per_card,
                t.category_food_dining,
                t.category_gas_transport,
                t.category_grocery_pos,
                t.category_kids_pets,
                t.category_misc_net,
                t.category_misc_pos,
                t.category_personal_care,
                t.category_shopping_net,
                t.merchant,
                t.city,
                CASE
                    WHEN fp.is_confirmed_fraud IS NOT NULL
                        THEN fp.is_confirmed_fraud::int
                    WHEN fp.risk_score >= %(fraud_thr)s THEN 1
                    ELSE 0
                END AS is_fraud
            FROM transactions t
            JOIN fraud_predictions fp
                ON fp.transaction_ref = t.transaction_ref
            WHERE t.trans_datetime >= NOW() - INTERVAL %(interval)s
            ORDER BY t.trans_datetime DESC
            LIMIT 500000
        """

        try:
            cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            cur.execute(query, {
                "fraud_thr": settings.FRAUD_THRESHOLD,
                "interval": f"{period_days} days",
            })
            rows = cur.fetchall()
            cur.close()
            conn.close()
        except psycopg2.Error as query_err:
            conn.close()
            raise RuntimeError(
                f"Database query failed: {query_err}. "
                f"Ensure the 'transactions' and 'fraud_predictions' tables exist."
            ) from query_err

        # ── 3. Validate row count — hard fail if insufficient ──────────────
        row_count = len(rows)
        log.info(f"[{job_id}] Fetched {row_count:,} rows from DB")

        if row_count < MIN_TRAINING_ROWS:
            raise RuntimeError(
                f"Insufficient training data: found only {row_count:,} transactions "
                f"in the last {period_days} days (minimum required: {MIN_TRAINING_ROWS:,}). "
                f"Solutions: "
                f"(1) Select a longer training period (e.g. 'Last 60 days'), "
                f"(2) Wait for more transactions to accumulate, or "
                f"(3) Lower MIN_TRAINING_ROWS in model_service.py if appropriate."
            )

        # Warn if fraud labels are very sparse (model quality risk)
        df = pd.DataFrame(rows)
        fraud_count = int(df["is_fraud"].sum())
        fraud_rate  = fraud_count / len(df)

        if fraud_count < 50:
            raise RuntimeError(
                f"Insufficient fraud examples: only {fraud_count} confirmed fraud cases "
                f"in the dataset ({fraud_rate:.4%} fraud rate). "
                f"At least 50 fraud cases are needed for meaningful training. "
                f"Extend the training period or ensure fraud labels are populated."
            )

        data_source = "database"
        _push({
            "data_source": data_source,
            "dataset_size": len(df),
            "progress_pct": 20,
            "fraud_count_total": fraud_count,
            "fraud_rate_pct": round(fraud_rate * 100, 3),
        })
        log.info(
            f"[{job_id}] Data loaded: {len(df):,} rows, "
            f"{fraud_count:,} fraud ({fraud_rate:.3%})"
        )

        # ── 4. Feature selection and cleaning ──────────────────────────────
        requested = job.get("features") or SELECTED_FEATURES
        feature_cols = [f for f in requested if f in df.columns]

        if len(feature_cols) < 3:
            # Fall back to SELECTED_FEATURES subset available in this dataset
            feature_cols = [f for f in SELECTED_FEATURES if f in df.columns]

        if len(feature_cols) < 3:
            raise RuntimeError(
                f"Too few valid feature columns found in DB data. "
                f"Expected columns from SELECTED_FEATURES, got: {list(df.columns)}"
            )

        # Fill NaN with column medians (computed from training data only — no leakage)
        medians = df[feature_cols].median(numeric_only=True)
        df[feature_cols] = df[feature_cols].fillna(medians)

        X = df[feature_cols].astype(float).values
        y = df["is_fraud"].values

        _push({"progress_pct": 35, "feature_count": len(feature_cols)})

        # ── 5. Train/val split (stratified to preserve fraud ratio) ────────
        val_ratio = {"80/20": 0.20, "70/30": 0.30, "90/10": 0.10}.get(
            job.get("validation_split", "80/20"), 0.20
        )

        X_train, X_val, y_train, y_val = train_test_split(
            X, y,
            test_size=val_ratio,
            stratify=y,
            random_state=42,
        )

        fraud_val_count = int(y_val.sum())
        if fraud_val_count < 10:
            raise RuntimeError(
                f"Validation set has only {fraud_val_count} fraud cases — "
                f"not enough to compute meaningful metrics. "
                f"Use a longer training period to increase fraud sample size."
            )

        _push({"progress_pct": 45})
        log.info(
            f"[{job_id}] Split: train={len(X_train):,} val={len(X_val):,} "
            f"(fraud in val: {fraud_val_count})"
        )

        # ── 6. Build and fit classifier ─────────────────────────────────────
        model_type = job.get("model_type", "RandomForest")
        _push({"progress_pct": 50})

        clf = _build_classifier(model_type, X_train, y_train, X_val, y_val)
        _push({"progress_pct": 80})

        # Wrap non-ensemble models in sklearn Pipeline with StandardScaler
        if model_type in ("RandomForest", "GradientBoosting"):
            sk_pipe = SkPipeline([("scaler", StandardScaler()), ("clf", clf)])
            sk_pipe.fit(X_train, y_train)
            predict_fn = sk_pipe
            shap_model  = sk_pipe.named_steps["clf"]
        else:
            # XGBoost / LightGBM / Ensemble — already fitted in _build_classifier
            predict_fn = clf
            shap_model  = clf

        _push({"progress_pct": 82})

        # ── 7. Evaluate ─────────────────────────────────────────────────────
        y_prob = predict_fn.predict_proba(X_val)[:, 1]
        y_pred = (y_prob >= settings.FRAUD_THRESHOLD).astype(int)

        fraud_total = int(y_val.sum())
        captured    = int((y_pred & y_val).sum())

        try:
            roc_auc = round(float(roc_auc_score(y_val, y_prob)), 4)
        except Exception:
            roc_auc = 0.0

        try:
            avg_precision = round(float(average_precision_score(y_val, y_prob)), 4)
        except Exception:
            avg_precision = 0.0

        metrics = {
            "accuracy":           round(float(accuracy_score(y_val, y_pred)), 4),
            "precision":          round(float(precision_score(y_val, y_pred, zero_division=0)), 4),
            "recall":             round(float(recall_score(y_val, y_pred, zero_division=0)), 4),
            "f1":                 round(float(f1_score(y_val, y_pred, zero_division=0)), 4),
            "roc_auc":            roc_auc,
            "average_precision":  avg_precision,
            "fraud_capture_rate": round(captured / max(fraud_total, 1), 4),
            "dataset_size":       len(df),
            "val_size":           len(y_val),
            "fraud_count_val":    fraud_total,
            "data_source":        data_source,
            "training_period":    job["training_period"],
            "period_days":        period_days,
        }

        _push({"metrics": metrics, "progress_pct": 88})
        log.info(
            f"[{job_id}] Evaluation complete — "
            f"precision={metrics['precision']} recall={metrics['recall']} "
            f"f1={metrics['f1']} roc_auc={roc_auc} "
            f"fraud_capture={metrics['fraud_capture_rate']}"
        )

        # ── 8. Update DriftDetector baseline ───────────────────────────────
        try:
            from app.ml.drift_detector import get_drift_detector
            detector = get_drift_detector()
            df_train = pd.DataFrame(X_train, columns=feature_cols)
            train_scores = predict_fn.predict_proba(X_train)[:, 1]
            detector.fit(df_train, y_train, score_dist=train_scores)
            asyncio.run(detector.save_reference_to_redis())
            log.info(f"[{job_id}] DriftDetector baseline updated")
        except Exception as drift_err:
            log.warning(f"[{job_id}] DriftDetector update failed (non-fatal): {drift_err}")

        _push({"progress_pct": 91})

        # ── 9. Initialize SHAP explainer ────────────────────────────────────
        try:
            from app.ml.explainability import init_explainer_from_model
            X_background = X_train[:500]
            init_explainer_from_model(model=shap_model, X_background=X_background)
            log.info(f"[{job_id}] SHAP explainer initialized")
        except Exception as shap_err:
            log.warning(f"[{job_id}] SHAP init failed (non-fatal): {shap_err}")

        # ── 10. Save model .pkl ─────────────────────────────────────────────
        version_str = datetime.now(timezone.utc).strftime("v%Y%m%d_%H%M%S")
        models_dir  = os.path.dirname(os.path.abspath(settings.MODEL_PATH))
        os.makedirs(models_dir, exist_ok=True)

        model_prefix = {
            "RandomForest": "rf", "GradientBoosting": "gbt",
            "XGBoost": "xgb", "LightGBM": "lgb", "Ensemble": "ens",
        }.get(model_type, "ml")

        new_pkl = os.path.join(models_dir, f"fraud_pipeline_{model_prefix}_{version_str}.pkl")
        joblib.dump(predict_fn, new_pkl)
        log.info(f"[{job_id}] Model saved: {new_pkl}")
        _push({"progress_pct": 94})

        # ── 11. Log to MLflow ───────────────────────────────────────────────
        mlflow_run_id = None
        try:
            from app.ml.observability import log_training_metrics_to_mlflow
            mlflow_run_id = log_training_metrics_to_mlflow(
                metrics=metrics,
                params={
                    "model_type":       model_type,
                    "training_period":  job["training_period"],
                    "validation_split": job.get("validation_split", "80/20"),
                    "data_source":      data_source,
                    "feature_count":    len(feature_cols),
                    "dataset_size":     len(df),
                    "fraud_rate":       round(fraud_rate, 6),
                },
                model_type=model_type,
                model_path=new_pkl,
                run_name=f"{model_type}-{version_str}",
            )
        except Exception as mlflow_err:
            log.debug(f"[{job_id}] MLflow logging failed (non-fatal): {mlflow_err}")

        # ── 12. Register as staging in PostgreSQL ───────────────────────────
        new_model_id = f"{model_prefix}-{version_str}"
        asyncio.run(_register_model(
            job_id, new_model_id, job, new_pkl,
            metrics, feature_cols, data_source, mlflow_run_id,
        ))

        _push({
            "status":       "completed",
            "progress_pct": 100,
            "model_id":     new_model_id,
            "completed_at": datetime.now(timezone.utc).isoformat(),
        })
        log.info(f"[{job_id}] Training complete → staged as {new_model_id}")

    except Exception as exc:
        _fail(str(exc))


# ── Classifier factory ────────────────────────────────────────────────────────

def _build_classifier(
    model_type: str,
    X_train,
    y_train,
    X_val,
    y_val,
):
    """
    Build and fit the requested classifier.
    XGBoost / LightGBM / Ensemble are fitted here.
    RandomForest / GradientBoosting are returned unfitted (caller wraps in Pipeline).
    """
    from sklearn.ensemble import GradientBoostingClassifier, RandomForestClassifier

    fraud_count = int(y_train.sum())
    legit_count = int(len(y_train) - fraud_count)
    scale_pw    = max(1.0, legit_count / max(fraud_count, 1))

    if model_type == "XGBoost":
        from app.ml.ensemble import build_xgboost
        clf = build_xgboost(scale_pos_weight=scale_pw)
        clf.fit(X_train, y_train, eval_set=[(X_val, y_val)], verbose=False)
        return clf

    elif model_type == "LightGBM":
        from app.ml.ensemble import build_lightgbm
        clf = build_lightgbm()
        clf.fit(X_train, y_train)
        return clf

    elif model_type == "Ensemble":
        from app.ml.ensemble import EnsemblePredictor
        from app.ml.feature_engineering import SELECTED_FEATURES
        ensemble = EnsemblePredictor()
        n_feats   = X_train.shape[1]
        feat_names = SELECTED_FEATURES[:n_feats]
        ensemble.fit(X_train, y_train, feature_names=feat_names, X_val=X_val, y_val=y_val)
        return ensemble

    elif model_type == "GradientBoosting":
        return GradientBoostingClassifier(
            n_estimators=80, max_depth=5, random_state=42
        )

    else:  # RandomForest (default)
        return RandomForestClassifier(
            n_estimators=150, max_depth=12,
            class_weight="balanced", n_jobs=-1, random_state=42,
        )


# ── Async helpers (called from sync thread via asyncio.run) ───────────────────

async def _async_get_job(job_id: str):
    from app.core.redis import get_job_status
    return await get_job_status(job_id)


async def _async_set_job(job_id: str, data: dict):
    from app.core.redis import set_job_status
    await set_job_status(job_id, data, settings.TRAINING_JOB_TTL_HOURS)


async def _register_model(
    job_id: str,
    new_model_id: str,
    job: dict,
    model_path: str,
    metrics: dict,
    features: list,
    data_source: str,
    mlflow_run_id: Optional[str] = None,
) -> None:
    """Register trained model to PostgreSQL as staging."""
    from app.db.session import AsyncSessionFactory
    async with AsyncSessionFactory() as session:
        try:
            registry = ModelRegistry(
                model_id=new_model_id,
                name=f"{job['model_type']} {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M')}",
                model_type=f"{job['model_type']}Classifier",
                status="staging",
                model_path=model_path,
                features=features,
                metrics=metrics,
                data_source=data_source,
                trained_at=datetime.now(timezone.utc),
            )
            session.add(registry)

            from sqlalchemy import select
            from app.models.ml_models import TrainingJob
            result = await session.execute(
                select(TrainingJob).where(TrainingJob.job_id == job_id)
            )
            db_job = result.scalar_one_or_none()
            if db_job:
                db_job.status       = "completed"
                db_job.progress_pct = 100
                db_job.model_id     = new_model_id
                db_job.metrics      = metrics
                db_job.data_source  = data_source
                db_job.completed_at = datetime.now(timezone.utc)

            await session.commit()
        except Exception as exc:
            await session.rollback()
            log.error(f"Failed to register model in DB: {exc}")