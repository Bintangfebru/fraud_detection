"""
FraudShield — Automatic Retraining Pipeline
Schedules and triggers model retraining based on:
  1. Time-based schedule (e.g., weekly retrain)
  2. Drift-triggered retrain (PSI > threshold)
  3. Performance degradation (precision/recall drop)

Uses APScheduler for background scheduling, integrated with the FastAPI lifespan.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional

log = logging.getLogger("fraudshield.auto_retrain")

# ── Configuration ─────────────────────────────────────────────────────────────

AUTO_RETRAIN_ENABLED       = True
SCHEDULE_INTERVAL_HOURS    = 24 * 7      # weekly scheduled retrain
DRIFT_CHECK_INTERVAL_HOURS = 6           # check drift every 6 hours
MIN_SAMPLES_FOR_DRIFT      = 500         # minimum recent predictions to check drift
PERFORMANCE_DROP_THRESHOLD = 0.05        # retrain if precision drops > 5%


# ── Retraining Trigger ────────────────────────────────────────────────────────

async def trigger_auto_retrain(reason: str, model_type: str = "Ensemble") -> Optional[str]:
    """
    Programmatically kick off a training job via ModelService.
    Returns job_id or None on failure.
    """
    try:
        from app.db.session import AsyncSessionFactory
        from app.services.model_service import ModelService
        from app.schemas.model import TrainRequest

        async with AsyncSessionFactory() as session:
            svc = ModelService(session)
            req = TrainRequest(
                model_type=model_type,
                training_period="Last 30 days",
                validation_split="80/20",
                features=None,           # use default SELECTED_FEATURES
            )
            job = await svc.start_training(req=req, started_by=f"auto-retrain:{reason}")
            log.info(f"[AutoRetrain] Job started: {job.job_id} — reason={reason}")
            return job.job_id
    except Exception as exc:
        log.error(f"[AutoRetrain] Failed to trigger retrain: {exc}")
        return None


# ── Drift-based retrain check ─────────────────────────────────────────────────

async def check_drift_and_retrain() -> None:
    """
    Pull recent predictions from DB, run drift detection,
    and trigger retraining if drift is critical.
    """
    log.info("[AutoRetrain] Running drift check...")
    try:
        import pandas as pd
        import numpy as np
        import psycopg2
        import psycopg2.extras

        from app.core.config import settings
        from app.ml.drift_detector import get_drift_detector

        detector = get_drift_detector()
        if not detector._fitted:
            log.info("[AutoRetrain] Drift detector not fitted — skipping drift check")
            return

        # Pull last N predictions from Postgres
        import re
        db_url = settings.database_url_sync
        m = re.match(r"postgresql://([^:]+):([^@]+)@([^:/]+):?(\d+)?/(.+)", db_url)
        if not m:
            return

        conn = psycopg2.connect(
            user=m.group(1), password=m.group(2),
            host=m.group(3), port=int(m.group(4) or 5432),
            dbname=m.group(5), connect_timeout=5,
        )
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("""
            SELECT t.amt, t.hour, t.amt_ratio, t.txn_count_per_card,
                   t.unique_merchants, t.amt_mean_per_card,
                   fp.risk_score,
                   CASE WHEN fp.is_confirmed_fraud IS NOT NULL
                        THEN fp.is_confirmed_fraud::int
                        WHEN fp.risk_score >= %s THEN 1
                        ELSE 0 END AS is_fraud
            FROM transactions t
            JOIN fraud_predictions fp ON fp.transaction_ref = t.transaction_ref
            WHERE fp.created_at >= NOW() - INTERVAL '6 hours'
            ORDER BY fp.created_at DESC
            LIMIT 5000
        """, (settings.FRAUD_THRESHOLD,))
        rows = cur.fetchall()
        cur.close()
        conn.close()

        if len(rows) < MIN_SAMPLES_FOR_DRIFT:
            log.info(f"[AutoRetrain] Only {len(rows)} samples — insufficient for drift check")
            return

        df = pd.DataFrame(rows)
        scores = df["risk_score"].values
        labels = df["is_fraud"].values

        drift_report = detector.detect(
            X_current=df.drop(columns=["risk_score", "is_fraud"], errors="ignore"),
            current_scores=scores,
            current_labels=labels,
        )

        severity = drift_report.get("overall_severity", "stable")
        log.info(f"[AutoRetrain] Drift check result: {severity} — PSI={drift_report.get('mean_feature_psi')}")

        if drift_report.get("should_retrain"):
            drifted = drift_report.get("drifted_features", [])
            reason = f"drift_critical:psi={drift_report.get('mean_feature_psi', 0):.3f}:features={','.join(drifted[:3])}"
            await trigger_auto_retrain(reason=reason, model_type="Ensemble")

        # Persist drift report to Redis for dashboard
        try:
            import json
            from app.core.redis import get_redis_client
            r = await get_redis_client()
            await r.setex("drift:latest_report", 3600 * 8, json.dumps(drift_report))
        except Exception:
            pass

    except Exception as exc:
        log.warning(f"[AutoRetrain] Drift check error: {exc}")


# ── Scheduled retrain (time-based) ────────────────────────────────────────────

async def scheduled_weekly_retrain() -> None:
    """
    Weekly full retrain job. Runs regardless of drift status.
    Ensures the model stays up-to-date with the most recent data.
    """
    log.info("[AutoRetrain] Scheduled weekly retrain triggered")
    await trigger_auto_retrain(reason="scheduled_weekly", model_type="Ensemble")


# ── Scheduler setup ───────────────────────────────────────────────────────────

_scheduler = None


def start_scheduler() -> None:
    """
    Start the APScheduler background scheduler.
    Call this from FastAPI lifespan startup.
    """
    global _scheduler
    if not AUTO_RETRAIN_ENABLED:
        log.info("[AutoRetrain] Scheduler disabled (AUTO_RETRAIN_ENABLED=False)")
        return

    try:
        from apscheduler.schedulers.asyncio import AsyncIOScheduler
        from apscheduler.triggers.interval import IntervalTrigger

        _scheduler = AsyncIOScheduler(timezone="UTC")

        # Drift check every 6 hours
        _scheduler.add_job(
            check_drift_and_retrain,
            trigger=IntervalTrigger(hours=DRIFT_CHECK_INTERVAL_HOURS),
            id="drift_check",
            name="Concept Drift Check",
            replace_existing=True,
            misfire_grace_time=600,
        )

        # Scheduled weekly retrain
        _scheduler.add_job(
            scheduled_weekly_retrain,
            trigger=IntervalTrigger(hours=SCHEDULE_INTERVAL_HOURS),
            id="weekly_retrain",
            name="Scheduled Weekly Retrain",
            replace_existing=True,
            misfire_grace_time=3600,
        )

        _scheduler.start()
        log.info(
            f"[AutoRetrain] Scheduler started — "
            f"drift_check every {DRIFT_CHECK_INTERVAL_HOURS}h, "
            f"weekly_retrain every {SCHEDULE_INTERVAL_HOURS}h"
        )

    except ImportError:
        log.warning("[AutoRetrain] apscheduler not installed — auto-retrain scheduler disabled")
    except Exception as exc:
        log.error(f"[AutoRetrain] Scheduler start failed: {exc}")


def stop_scheduler() -> None:
    """Stop the scheduler. Call from FastAPI lifespan shutdown."""
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
        log.info("[AutoRetrain] Scheduler stopped")


def get_scheduler_status() -> dict:
    """Return current scheduler status for the observability dashboard."""
    global _scheduler
    if _scheduler is None or not _scheduler.running:
        return {
            "running": False,
            "jobs": [],
            "auto_retrain_enabled": AUTO_RETRAIN_ENABLED,
        }

    jobs = []
    for job in _scheduler.get_jobs():
        next_run = job.next_run_time
        jobs.append({
            "id": job.id,
            "name": job.name,
            "next_run": next_run.isoformat() if next_run else None,
        })

    return {
        "running": True,
        "jobs": jobs,
        "auto_retrain_enabled": AUTO_RETRAIN_ENABLED,
        "drift_check_interval_hours": DRIFT_CHECK_INTERVAL_HOURS,
        "weekly_retrain_interval_hours": SCHEDULE_INTERVAL_HOURS,
    }
