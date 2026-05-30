"""
FraudShield — Low-Latency Inference Pipeline
Handles real-time fraud scoring with sub-10ms target latency.

Responsibilities:
  - Load and hot-reload the deployed model from disk
  - Assemble feature vectors from raw transaction input
  - Run model prediction with latency tracking
  - Enrich predictions with SHAP, anomaly, graph signals (optional)
  - Expose model_info() used by the API router

Architecture:
  TransactionRequest
    → feature_engineering.derive_features()
    → feature_store enrichment (async, Redis)
    → _pipeline.predict_proba()          ← core ML inference
    → observability.record_inference()
    → (optional) SHAP + anomaly + graph
    → PredictionResult
"""

from __future__ import annotations

import logging
import os
import time
from datetime import datetime, timezone
from typing import Any, Optional

import joblib
import numpy as np

log = logging.getLogger("fraudshield.predictor")

# ── Module-level model state ──────────────────────────────────────────────────

_pipeline: Any = None          # loaded sklearn Pipeline or EnsemblePredictor
_model_meta: dict = {
    "loaded": False,
    "type": "Unknown",
    "name": "Unknown",
    "path": "",
    "loaded_at": None,
    "version": "unknown",
}

# ── Model Loading ─────────────────────────────────────────────────────────────

def load_model(path: str) -> bool:
    """
    Load (or hot-reload) the fraud detection model from a .pkl file.
    Thread-safe: replaces the global _pipeline atomically.
    Returns True on success.
    """
    global _pipeline, _model_meta
    if not os.path.exists(path):
        log.warning(f"[Predictor] Model file not found: {path}")
        return False

    try:
        obj = joblib.load(path)
        _pipeline = obj
        _model_meta = {
            "loaded": True,
            "type":   _detect_model_type(obj),
            "name":   os.path.basename(path),
            "path":   path,
            "loaded_at": datetime.now(timezone.utc).isoformat(),
            "version": _extract_version_from_path(path),
        }
        log.info(f"[Predictor] Model loaded: {_model_meta['type']} from {path}")
        return True
    except Exception as exc:
        log.error(f"[Predictor] Failed to load model from {path}: {exc}")
        return False


def _detect_model_type(obj: Any) -> str:
    """Infer model type string from the loaded object."""
    name = type(obj).__name__
    if name == "EnsemblePredictor":
        return "Ensemble"
    if name == "EnsemblePipelineWrapper":
        return "Ensemble"
    if "Pipeline" in name:
        # Look inside pipeline
        if hasattr(obj, "named_steps"):
            clf = obj.named_steps.get("clf")
            if clf:
                inner = type(clf).__name__
                return inner.replace("Classifier", "")
    return name.replace("Classifier", "")


def _extract_version_from_path(path: str) -> str:
    """Extract version string like v20260101_120000 from model filename."""
    import re
    m = re.search(r"(v\d{8}_\d{6})", os.path.basename(path))
    return m.group(1) if m else "unknown"


def model_info() -> dict:
    """Return current model metadata. Used by /models/status endpoint."""
    return dict(_model_meta)


def is_loaded() -> bool:
    return _pipeline is not None and _model_meta.get("loaded", False)


# ── Core Prediction ───────────────────────────────────────────────────────────

def predict_fraud(
    feature_vector: np.ndarray,
) -> tuple[float, float]:
    """
    Run inference on a pre-built feature vector.

    Args:
        feature_vector: shape (1, n_features) float32 array

    Returns:
        (fraud_probability, inference_latency_ms)

    Raises:
        RuntimeError if no model is loaded.
    """
    if _pipeline is None:
        raise RuntimeError("No model loaded. Call load_model() first.")

    t0 = time.perf_counter()
    proba = _pipeline.predict_proba(feature_vector)
    latency_ms = (time.perf_counter() - t0) * 1000.0

    fraud_prob = float(proba[0, 1])
    return fraud_prob, latency_ms


# ── Full inference pipeline (async, used by transaction endpoints) ─────────────

async def run_inference(
    transaction: dict,
    card_hash: str = "",
    merchant: str = "",
    city: str = "",
    fraud_threshold: float = 0.5,
    review_threshold: float = 0.3,
    enrich_from_store: bool = True,
    run_anomaly: bool = True,
    run_graph: bool = False,
    run_shap: bool = False,
    top_k_shap: int = 5,
) -> dict:
    """
    End-to-end inference for a single transaction dict.

    Steps:
      1. Derive engineered features
      2. Enrich from online feature store (Redis)
      3. Core ML inference
      4. Record latency/score in observability ring buffer
      5. (Optional) anomaly detection
      6. (Optional) graph shared-entity check
      7. (Optional) SHAP explanation
      8. Compose result dict

    Returns a PredictionResult-compatible dict.
    """
    from app.ml.feature_engineering import derive_features, features_to_array, enrich_from_feature_store
    from app.ml.observability import record_inference

    # 1. Derive features
    feat_dict = derive_features(transaction)

    # 2. Enrich from feature store
    if enrich_from_store and card_hash:
        feat_dict = await enrich_from_feature_store(feat_dict, card_hash, merchant)

    # 3. Core inference
    X = features_to_array(feat_dict)
    fraud_prob, latency_ms = predict_fraud(X)

    # 4. Observability
    error_flag = False
    record_inference(latency_ms=latency_ms, fraud_score=fraud_prob, error=error_flag)

    # Determine verdict
    if fraud_prob >= fraud_threshold:
        verdict = "FRAUD"
        status  = "flagged"
    elif fraud_prob >= review_threshold:
        verdict = "REVIEW"
        status  = "review"
    else:
        verdict = "SAFE"
        status  = "approved"

    result: dict = {
        "risk_score":      round(fraud_prob, 4),
        "verdict":         verdict,
        "status":          status,
        "latency_ms":      round(latency_ms, 3),
        "features_used":   list(feat_dict.keys()),
        "model_version":   _model_meta.get("version", "unknown"),
        "scored_at":       datetime.now(timezone.utc).isoformat(),
    }

    # 5. Anomaly detection
    if run_anomaly:
        try:
            from app.ml.anomaly_detector import AnomalyDetector
            _anm = _get_anomaly_detector()
            if _anm:
                anomaly_report = _anm.score_transaction(feat_dict)
                result["anomaly"] = anomaly_report
        except Exception as exc:
            log.debug(f"[Predictor] Anomaly detection skipped: {exc}")

    # 6. Graph analysis
    if run_graph and card_hash and merchant:
        try:
            from app.ml.graph_analyzer import GraphFraudAnalyzer
            analyzer = GraphFraudAnalyzer()
            await analyzer.record_transaction_entity(card_hash, merchant, city, transaction.get("amt", 0))
            graph_report = await analyzer.check_shared_entities(card_hash, merchant, city)
            result["graph"] = graph_report
        except Exception as exc:
            log.debug(f"[Predictor] Graph analysis skipped: {exc}")

    # 7. SHAP explanation
    if run_shap:
        try:
            from app.ml.explainability import get_explainer
            from app.ml.feature_engineering import SELECTED_FEATURES
            explainer = get_explainer()
            contribs = explainer.explain_single(
                features=feat_dict,
                feature_names=SELECTED_FEATURES,
                top_k=top_k_shap,
            )
            result["shap_contributions"] = contribs
        except Exception as exc:
            log.debug(f"[Predictor] SHAP explanation skipped: {exc}")

    return result


# ── Batch inference ───────────────────────────────────────────────────────────

def predict_batch(
    X: np.ndarray,
    threshold: float = 0.5,
) -> np.ndarray:
    """
    Batch inference for training evaluation / drift checking.
    Returns fraud probability array of shape (n_samples,).
    """
    if _pipeline is None:
        raise RuntimeError("No model loaded.")
    return _pipeline.predict_proba(X)[:, 1]


# ── Anomaly detector singleton ────────────────────────────────────────────────

_anomaly_detector = None


def _get_anomaly_detector():
    """Lazy-load anomaly detector from disk if available."""
    global _anomaly_detector
    if _anomaly_detector is not None:
        return _anomaly_detector
    try:
        from app.core.config import settings
        anomaly_path = getattr(settings, "ANOMALY_MODEL_PATH", "models/anomaly_detector.pkl")
        if os.path.exists(anomaly_path):
            from app.ml.anomaly_detector import AnomalyDetector
            _anomaly_detector = AnomalyDetector.load(anomaly_path)
            log.info(f"[Predictor] AnomalyDetector loaded from {anomaly_path}")
        return _anomaly_detector
    except Exception as exc:
        log.debug(f"[Predictor] Could not load anomaly detector: {exc}")
        return None


def set_anomaly_detector(detector) -> None:
    """Inject anomaly detector (called after training)."""
    global _anomaly_detector
    _anomaly_detector = detector
    log.info("[Predictor] AnomalyDetector updated")


# ── Startup initialisation (called from FastAPI lifespan) ─────────────────────

def startup_load() -> None:
    """
    Called once at FastAPI startup.
    Loads the model defined in settings.MODEL_PATH.
    Logs a warning (not error) if the file doesn't exist yet —
    the first training job will produce it.
    """
    try:
        from app.core.config import settings
        path = settings.MODEL_PATH
        if os.path.exists(path):
            load_model(path)
        else:
            log.warning(
                f"[Predictor] MODEL_PATH '{path}' not found at startup. "
                "A training job must complete before inference is available."
            )
    except Exception as exc:
        log.error(f"[Predictor] startup_load failed: {exc}")
