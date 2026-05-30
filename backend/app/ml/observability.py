"""
FraudShield — ML Observability & Monitoring
Tracks model performance, inference latency, prediction distribution,
and system health in real-time.

Metrics tracked:
  - Precision, Recall, F1-Score, ROC-AUC, Fraud Capture Rate
  - Inference latency (p50/p95/p99)
  - Prediction score distribution
  - Model throughput (predictions/second)
  - Error rates
"""

from __future__ import annotations

import json
import logging
import time
from collections import deque
from datetime import datetime, timezone
from typing import Optional

import numpy as np

log = logging.getLogger("fraudshield.observability")

# ── In-memory ring buffers (cleared on restart — Redis is the durable store) ──
_latency_buffer: deque = deque(maxlen=10_000)   # last 10k inference latencies (ms)
_score_buffer: deque   = deque(maxlen=10_000)   # last 10k fraud scores
_error_count: int = 0
_prediction_count: int = 0
_startup_time: float = time.time()


# ── Latency Tracking ──────────────────────────────────────────────────────────

def record_inference(latency_ms: float, fraud_score: float, error: bool = False) -> None:
    """Called after every prediction to record latency and score."""
    global _error_count, _prediction_count
    _latency_buffer.append(latency_ms)
    _score_buffer.append(fraud_score)
    _prediction_count += 1
    if error:
        _error_count += 1


def get_latency_stats() -> dict:
    """Return latency percentiles from the in-memory ring buffer."""
    if not _latency_buffer:
        return {"p50": 0.0, "p95": 0.0, "p99": 0.0, "mean": 0.0, "count": 0}

    arr = np.array(_latency_buffer)
    return {
        "p50": round(float(np.percentile(arr, 50)), 3),
        "p95": round(float(np.percentile(arr, 95)), 3),
        "p99": round(float(np.percentile(arr, 99)), 3),
        "mean": round(float(arr.mean()), 3),
        "count": len(arr),
    }


def get_score_distribution() -> dict:
    """Return histogram of recent fraud score distribution."""
    if not _score_buffer:
        return {"bins": [], "counts": []}

    arr = np.array(_score_buffer)
    counts, bin_edges = np.histogram(arr, bins=10, range=(0.0, 1.0))
    return {
        "bins": [round(float(b), 2) for b in bin_edges[:-1]],
        "counts": counts.tolist(),
        "mean_score": round(float(arr.mean()), 4),
        "fraud_rate": round(float((arr >= 0.5).mean()), 4),
    }


# ── Performance Metrics (from DB) ────────────────────────────────────────────

async def compute_live_metrics(
    window_hours: int = 24,
    fraud_threshold: float = 0.5,
) -> dict:
    """
    Compute precision, recall, F1, ROC-AUC, fraud capture rate
    from confirmed fraud labels in the last N hours.
    Reads from PostgreSQL — requires confirmed fraud labels.
    """
    try:
        import psycopg2
        import psycopg2.extras
        from sklearn.metrics import (
            precision_score, recall_score, f1_score,
            roc_auc_score, average_precision_score,
        )
        from app.core.config import settings
        import re

        db_url = settings.database_url_sync
        m = re.match(r"postgresql://([^:]+):([^@]+)@([^:/]+):?(\d+)?/(.+)", db_url)
        if not m:
            return _empty_metrics()

        conn = psycopg2.connect(
            user=m.group(1), password=m.group(2),
            host=m.group(3), port=int(m.group(4) or 5432),
            dbname=m.group(5), connect_timeout=5,
        )
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("""
            SELECT fp.risk_score,
                   fp.is_confirmed_fraud,
                   fp.status
            FROM fraud_predictions fp
            WHERE fp.created_at >= NOW() - INTERVAL %s
              AND fp.is_confirmed_fraud IS NOT NULL
            LIMIT 100000
        """, (f"{window_hours} hours",))
        rows = cur.fetchall()
        cur.close()
        conn.close()

        if len(rows) < 10:
            return _empty_metrics(reason=f"Only {len(rows)} labeled samples in last {window_hours}h")

        scores = np.array([r["risk_score"] for r in rows], dtype=float)
        labels = np.array([int(r["is_confirmed_fraud"]) for r in rows], dtype=int)
        preds  = (scores >= fraud_threshold).astype(int)

        fraud_total = labels.sum()
        captured    = (preds & labels).sum()
        fraud_capture_rate = float(captured / max(fraud_total, 1))

        try:
            roc_auc = float(roc_auc_score(labels, scores))
        except Exception:
            roc_auc = 0.0

        try:
            avg_precision = float(average_precision_score(labels, scores))
        except Exception:
            avg_precision = 0.0

        return {
            "computed_at": datetime.now(timezone.utc).isoformat(),
            "window_hours": window_hours,
            "sample_count": len(rows),
            "labeled_fraud_count": int(fraud_total),
            "precision": round(float(precision_score(labels, preds, zero_division=0)), 4),
            "recall": round(float(recall_score(labels, preds, zero_division=0)), 4),
            "f1_score": round(float(f1_score(labels, preds, zero_division=0)), 4),
            "roc_auc": round(roc_auc, 4),
            "average_precision": round(avg_precision, 4),
            "fraud_capture_rate": round(fraud_capture_rate, 4),
            "fraud_threshold_used": fraud_threshold,
        }

    except Exception as exc:
        log.warning(f"[Observability] compute_live_metrics failed: {exc}")
        return _empty_metrics(reason=str(exc))


def _empty_metrics(reason: str = "No labeled data") -> dict:
    return {
        "computed_at": datetime.now(timezone.utc).isoformat(),
        "reason": reason,
        "precision": None,
        "recall": None,
        "f1_score": None,
        "roc_auc": None,
        "average_precision": None,
        "fraud_capture_rate": None,
    }


# ── MLflow Integration ────────────────────────────────────────────────────────

def log_training_metrics_to_mlflow(
    metrics: dict,
    params: dict,
    model_type: str,
    model_path: str,
    run_name: Optional[str] = None,
) -> Optional[str]:
    """
    Log a training run to MLflow.
    Returns the MLflow run_id or None if MLflow is unavailable.
    """
    try:
        import mlflow
        from app.core.config import settings

        tracking_uri = getattr(settings, "MLFLOW_TRACKING_URI", "file:./mlruns")
        mlflow.set_tracking_uri(tracking_uri)
        mlflow.set_experiment("fraudshield_ml")

        with mlflow.start_run(run_name=run_name or f"{model_type}-{datetime.now().strftime('%Y%m%d_%H%M%S')}") as run:
            mlflow.log_params(params)
            for key, val in metrics.items():
                if isinstance(val, (int, float)):
                    mlflow.log_metric(key, val)
            mlflow.log_param("model_type", model_type)
            mlflow.log_param("model_path", model_path)

            run_id = run.info.run_id
            log.info(f"[MLflow] Run logged: {run_id}")
            return run_id

    except ImportError:
        log.debug("[MLflow] mlflow not installed — skipping metric logging")
        return None
    except Exception as exc:
        log.warning(f"[MLflow] Logging failed: {exc}")
        return None


# ── Observability Dashboard Snapshot ─────────────────────────────────────────

async def get_observability_snapshot() -> dict:
    """
    Full observability snapshot combining all monitoring signals.
    Used by the /models/observability API endpoint.
    """
    global _prediction_count, _error_count, _startup_time
    from app.core.config import settings

    uptime_seconds = time.time() - _startup_time
    pps = _prediction_count / max(uptime_seconds, 1)  # predictions per second

    latency = get_latency_stats()
    score_dist = get_score_distribution()
    live_metrics = await compute_live_metrics(
        window_hours=24,
        fraud_threshold=settings.FRAUD_THRESHOLD,
    )

    # Drift status from Redis
    drift_status = {}
    try:
        from app.core.redis import get_redis_client
        r = await get_redis_client()
        raw = await r.get("drift:latest_report")
        if raw:
            report = json.loads(raw)
            drift_status = {
                "severity": report.get("overall_severity", "unknown"),
                "mean_psi": report.get("mean_feature_psi"),
                "drifted_features": report.get("drifted_features", []),
                "last_checked": report.get("detected_at"),
            }
    except Exception:
        pass

    # Auto-retrain scheduler
    scheduler_status = {}
    try:
        from app.ml.auto_retrain import get_scheduler_status
        scheduler_status = get_scheduler_status()
    except Exception:
        pass

    return {
        "snapshot_at": datetime.now(timezone.utc).isoformat(),
        "throughput": {
            "total_predictions": _prediction_count,
            "predictions_per_second": round(pps, 3),
            "error_count": _error_count,
            "error_rate": round(_error_count / max(_prediction_count, 1), 4),
            "uptime_seconds": round(uptime_seconds, 0),
        },
        "latency_ms": latency,
        "score_distribution": score_dist,
        "live_metrics": live_metrics,
        "drift": drift_status,
        "scheduler": scheduler_status,
    }
