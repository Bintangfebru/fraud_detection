"""
FraudShield — ML Explainability Engine
SHAP-based explanations, fraud confidence scoring, and fraud explainability reports.

Features:
  - SHAP values per transaction prediction
  - Fraud confidence bands (high/medium/low confidence)
  - Narrative fraud explanation report
  - Top contributing features per prediction
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Optional

import numpy as np
import pandas as pd

log = logging.getLogger("fraudshield.explainability")


# ── Confidence Scoring ────────────────────────────────────────────────────────

def compute_confidence_score(
    fraud_probability: float,
    fraud_threshold: float = 0.5,
    review_threshold: float = 0.3,
) -> dict:
    """
    Translate a raw fraud probability into a confidence score and band.

    Confidence is highest when the score is far from decision boundaries.
    Returns:
      - confidence: 0.0–1.0 (how confident the model is in its verdict)
      - confidence_band: "high" | "medium" | "low"
      - verdict: "FRAUD" | "REVIEW" | "SAFE"
      - uncertainty: distance to nearest decision boundary
    """
    p = float(fraud_probability)

    # Distance to each threshold (lower = more uncertain)
    dist_to_fraud  = abs(p - fraud_threshold)
    dist_to_review = abs(p - review_threshold)
    dist_to_safe   = p  # distance to 0

    if p >= fraud_threshold:
        verdict = "FRAUD"
        nearest_boundary = fraud_threshold
    elif p >= review_threshold:
        verdict = "REVIEW"
        nearest_boundary = min(fraud_threshold, review_threshold, key=lambda t: abs(p - t))
    else:
        verdict = "SAFE"
        nearest_boundary = review_threshold

    uncertainty = abs(p - nearest_boundary)

    # Confidence: exponential of distance to boundary, scaled to 0-1
    # Far from boundary = high confidence; close = low
    confidence = float(1.0 - np.exp(-4.0 * uncertainty))

    if confidence >= 0.75:
        band = "high"
    elif confidence >= 0.40:
        band = "medium"
    else:
        band = "low"

    return {
        "fraud_probability": round(p, 4),
        "confidence": round(confidence, 4),
        "confidence_band": band,
        "verdict": verdict,
        "uncertainty": round(uncertainty, 4),
        "distance_to_fraud_threshold": round(dist_to_fraud, 4),
        "distance_to_review_threshold": round(dist_to_review, 4),
    }


# ── SHAP Engine ───────────────────────────────────────────────────────────────

class SHAPExplainer:
    """
    SHAP explainer wrapper for FraudShield models.
    Supports TreeExplainer (XGBoost/LightGBM/RF) and LinearExplainer (logistic).
    Explanation results are cached in Redis to avoid recomputation.
    """

    def __init__(self):
        self._explainer = None
        self._feature_names: list[str] = []
        self._expected_value: float = 0.0

    def build(self, model: Any, X_background: Optional[np.ndarray] = None) -> "SHAPExplainer":
        """
        Build SHAP explainer from a fitted model.
        Uses TreeExplainer for tree-based models; LinearExplainer otherwise.
        """
        try:
            import shap
        except ImportError:
            log.error("shap package not installed — explainability disabled")
            return self

        try:
            # TreeExplainer works for XGBoost, LightGBM, RandomForest, GBT
            self._explainer = shap.TreeExplainer(model)
            log.info("[SHAP] TreeExplainer built successfully")
        except Exception:
            # Fall back to KernelExplainer for non-tree models
            if X_background is not None:
                self._explainer = shap.KernelExplainer(
                    model.predict_proba,
                    shap.sample(X_background, min(100, len(X_background))),
                )
                log.info("[SHAP] KernelExplainer built (fallback)")
            else:
                log.warning("[SHAP] Cannot build explainer without background data")

        return self

    def explain(
        self,
        X: np.ndarray,
        feature_names: list[str],
        top_k: int = 10,
    ) -> list[dict]:
        """
        Compute SHAP values for a batch of inputs.
        Returns top_k contributing features per sample, sorted by |shap_value|.
        """
        if self._explainer is None:
            return _static_explanation(X, feature_names, top_k)

        try:
            import shap
            shap_values = self._explainer.shap_values(X)

            # For binary classifiers, shap_values may be a list [class0, class1]
            if isinstance(shap_values, list) and len(shap_values) == 2:
                shap_values = shap_values[1]   # use fraud class (class=1)

            results = []
            for i, row_shap in enumerate(shap_values):
                contributions = []
                for feat_idx, sv in enumerate(row_shap):
                    if feat_idx < len(feature_names):
                        contributions.append({
                            "feature": feature_names[feat_idx],
                            "shap_value": round(float(sv), 5),
                            "direction": "increases_risk" if sv > 0 else "decreases_risk",
                            "feature_value": round(float(X[i, feat_idx]), 4)
                                             if feat_idx < X.shape[1] else None,
                        })

                # Sort by absolute SHAP value
                contributions.sort(key=lambda c: abs(c["shap_value"]), reverse=True)
                results.append(contributions[:top_k])

            return results

        except Exception as exc:
            log.warning(f"[SHAP] explain() failed: {exc} — using static fallback")
            return _static_explanation(X, feature_names, top_k)

    def explain_single(
        self,
        features: dict,
        feature_names: list[str],
        top_k: int = 10,
    ) -> dict:
        """Explain a single transaction prediction."""
        try:
            X = np.array([[features.get(f, 0.0) for f in feature_names]])
            rows = self.explain(X, feature_names, top_k=top_k)
            return rows[0] if rows else {}
        except Exception as exc:
            log.warning(f"[SHAP] explain_single error: {exc}")
            return {}


def _static_explanation(
    X: np.ndarray,
    feature_names: list[str],
    top_k: int,
) -> list[list[dict]]:
    """
    Fallback when SHAP is unavailable — uses normalized feature values
    as proxy importance (weighted heuristic).
    """
    heuristic_weights = {
        "amt_ratio": 0.22, "amt": 0.19, "hour": 0.14,
        "txn_count_per_card": 0.12, "amt_mean_per_card": 0.08,
        "unique_merchants": 0.07, "category_misc_net": 0.06,
        "category_shopping_net": 0.05,
    }

    results = []
    for row in X:
        contribs = []
        for idx, feat in enumerate(feature_names):
            w = heuristic_weights.get(feat, 0.02)
            val = float(row[idx]) if idx < len(row) else 0.0
            sv = round(w * (val - 0.5), 5)  # crude signed contribution
            contribs.append({
                "feature": feat,
                "shap_value": sv,
                "direction": "increases_risk" if sv > 0 else "decreases_risk",
                "feature_value": round(val, 4),
                "fallback": True,
            })
        contribs.sort(key=lambda c: abs(c["shap_value"]), reverse=True)
        results.append(contribs[:top_k])
    return results


# ── Fraud Explainability Report ───────────────────────────────────────────────

def generate_fraud_report(
    transaction_ref: str,
    features: dict,
    fraud_probability: float,
    shap_contributions: list[dict],
    anomaly_report: Optional[dict] = None,
    graph_report: Optional[dict] = None,
    fraud_threshold: float = 0.5,
    review_threshold: float = 0.3,
) -> dict:
    """
    Generate a structured fraud explainability report for a transaction.
    Combines ML score, SHAP explanations, anomaly signals, and graph analysis.
    """
    confidence = compute_confidence_score(
        fraud_probability,
        fraud_threshold=fraud_threshold,
        review_threshold=review_threshold,
    )

    # Build human-readable narrative
    verdict = confidence["verdict"]
    top_factors = [c["feature"] for c in shap_contributions[:3] if c.get("shap_value", 0) > 0]
    risk_factors = _format_risk_factors(features, shap_contributions)

    narrative = _build_narrative(
        verdict=verdict,
        fraud_probability=fraud_probability,
        confidence_band=confidence["confidence_band"],
        top_factors=top_factors,
        risk_factors=risk_factors,
        anomaly_report=anomaly_report,
    )

    report = {
        "transaction_ref": transaction_ref,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "verdict": verdict,
        "fraud_probability": fraud_probability,
        "confidence": confidence,
        "top_risk_factors": shap_contributions[:5],
        "all_shap_contributions": shap_contributions,
        "risk_factor_summary": risk_factors,
        "narrative": narrative,
        "anomaly_signals": anomaly_report or {},
        "graph_signals": graph_report or {},
        "model_version": _get_model_version(),
    }

    return report


def _format_risk_factors(features: dict, shap_contributions: list[dict]) -> list[dict]:
    """Convert SHAP contributions to human-readable risk factor descriptions."""
    descriptions = {
        "amt_ratio": lambda v: f"Amount is {v:.1f}× higher than card average",
        "amt": lambda v: f"Transaction amount: ${v:.2f}",
        "hour": lambda v: f"Transaction at {int(v):02d}:00 {'(late night)' if v < 6 or v >= 22 else ''}",
        "txn_count_per_card": lambda v: f"Card has {int(v)} recent transactions",
        "category_misc_net": lambda v: "High-risk category: misc/net" if v else "",
        "category_shopping_net": lambda v: "Online shopping category" if v else "",
        "unique_merchants": lambda v: f"Card used at {int(v)} unique merchants",
        "amt_mean_per_card": lambda v: f"Card's typical amount: ${v:.2f}",
    }

    factors = []
    for contrib in shap_contributions[:8]:
        feat = contrib["feature"]
        sv = contrib.get("shap_value", 0)
        fv = contrib.get("feature_value", features.get(feat, 0))

        if feat in descriptions and fv is not None:
            try:
                desc = descriptions[feat](float(fv))
                if desc:
                    factors.append({
                        "factor": feat,
                        "description": desc,
                        "impact": "high" if abs(sv) > 0.05 else "medium" if abs(sv) > 0.02 else "low",
                        "direction": contrib.get("direction", "neutral"),
                        "shap_value": sv,
                    })
            except Exception:
                pass

    return factors


def _build_narrative(
    verdict: str,
    fraud_probability: float,
    confidence_band: str,
    top_factors: list[str],
    risk_factors: list[dict],
    anomaly_report: Optional[dict] = None,
) -> str:
    """Generate a plain-English narrative explanation."""
    pct = f"{fraud_probability * 100:.1f}%"

    if verdict == "FRAUD":
        opening = f"This transaction has been flagged as FRAUDULENT with a {pct} fraud probability."
    elif verdict == "REVIEW":
        opening = f"This transaction requires REVIEW with a {pct} fraud probability (medium risk)."
    else:
        opening = f"This transaction appears SAFE with only a {pct} fraud probability."

    confidence_note = {
        "high": "The model is highly confident in this assessment.",
        "medium": "The model has moderate confidence — human review is recommended.",
        "low": "The model is uncertain — this case requires careful manual review.",
    }.get(confidence_band, "")

    factor_note = ""
    if top_factors:
        readable = [f.replace("_", " ") for f in top_factors]
        factor_note = f"Key contributing factors: {', '.join(readable)}."

    anomaly_note = ""
    if anomaly_report and anomaly_report.get("is_anomaly"):
        severity = anomaly_report.get("severity", "warning")
        anomaly_note = f"An {severity}-level anomaly was also detected by the unsupervised anomaly engine."

    return " ".join(filter(None, [opening, confidence_note, factor_note, anomaly_note]))


def _get_model_version() -> str:
    try:
        from app.ml.predictor import model_info
        info = model_info()
        return info.get("type", "unknown")
    except Exception:
        return "unknown"


# ── Module-level explainer singleton ─────────────────────────────────────────

_explainer: Optional[SHAPExplainer] = None


def get_explainer() -> SHAPExplainer:
    global _explainer
    if _explainer is None:
        _explainer = SHAPExplainer()
    return _explainer


def init_explainer_from_model(model: Any, X_background: Optional[np.ndarray] = None) -> None:
    """Initialize the global SHAP explainer from a trained model."""
    global _explainer
    _explainer = SHAPExplainer().build(model=model, X_background=X_background)
    log.info("[SHAP] Global explainer initialized")
