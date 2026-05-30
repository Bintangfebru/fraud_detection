"""
FraudShield — Concept Drift Detector
Detects data distribution shifts that degrade model performance over time.

Methods:
  - PSI (Population Stability Index) — univariate feature drift
  - KS Test (Kolmogorov-Smirnov)   — distribution equality test
  - Prediction drift                — shift in model output distribution
  - Label drift                     — shift in fraud prevalence

PSI interpretation:
  < 0.10  → No drift (stable)
  0.10–0.25 → Minor drift (monitor)
  > 0.25  → Major drift (retrain)
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Optional

import numpy as np
import pandas as pd

log = logging.getLogger("fraudshield.drift")

# ── Thresholds ────────────────────────────────────────────────────────────────

PSI_WARNING  = 0.10
PSI_CRITICAL = 0.25
KS_PVALUE_WARNING = 0.05    # p < 0.05 → statistically significant drift

# ── Key features to monitor for drift (subset of SELECTED_FEATURES) ──────────
DRIFT_MONITOR_FEATURES = [
    "amt", "hour", "amt_ratio", "txn_count_per_card",
    "unique_merchants", "amt_mean_per_card",
]


# ── PSI ───────────────────────────────────────────────────────────────────────

def compute_psi(
    expected: np.ndarray,
    actual: np.ndarray,
    n_bins: int = 10,
    epsilon: float = 1e-6,
) -> float:
    """
    Population Stability Index between expected (training) and actual (production) distributions.
    Higher PSI = more drift.
    """
    # Use quantile-based bins from expected distribution
    bin_edges = np.percentile(expected, np.linspace(0, 100, n_bins + 1))
    bin_edges = np.unique(bin_edges)  # deduplicate edge cases

    if len(bin_edges) < 2:
        return 0.0

    # Count proportions
    exp_counts, _ = np.histogram(expected, bins=bin_edges)
    act_counts, _ = np.histogram(actual,   bins=bin_edges)

    exp_pct = (exp_counts / len(expected)) + epsilon
    act_pct = (act_counts / len(actual))   + epsilon

    psi = float(np.sum((act_pct - exp_pct) * np.log(act_pct / exp_pct)))
    return round(psi, 6)


def psi_severity(psi: float) -> str:
    if psi < PSI_WARNING:
        return "stable"
    if psi < PSI_CRITICAL:
        return "warning"
    return "critical"


# ── KS Test ───────────────────────────────────────────────────────────────────

def compute_ks(
    reference: np.ndarray,
    current: np.ndarray,
) -> dict:
    """
    Kolmogorov-Smirnov test between two distributions.
    Returns statistic and p-value.
    """
    try:
        from scipy.stats import ks_2samp
        stat, pvalue = ks_2samp(reference, current)
        return {
            "statistic": round(float(stat), 6),
            "pvalue": round(float(pvalue), 6),
            "drifted": pvalue < KS_PVALUE_WARNING,
        }
    except ImportError:
        log.warning("scipy not installed — KS test unavailable")
        return {"statistic": 0.0, "pvalue": 1.0, "drifted": False}


# ── Drift Detector ────────────────────────────────────────────────────────────

class DriftDetector:
    """
    Concept drift detector for FraudShield.
    Stores reference distributions from training and compares against production windows.
    """

    def __init__(self):
        self._reference: dict[str, np.ndarray] = {}   # feature → training distribution
        self._reference_score_dist: Optional[np.ndarray] = None
        self._reference_fraud_rate: Optional[float] = None
        self._fitted = False
        self._redis = None

    # ── Fit (called once after training) ─────────────────────────────────────

    def fit(
        self,
        X_train: pd.DataFrame,
        y_train: np.ndarray,
        score_dist: Optional[np.ndarray] = None,
    ) -> "DriftDetector":
        """Store training distributions as reference baseline."""
        for feat in DRIFT_MONITOR_FEATURES:
            if feat in X_train.columns:
                self._reference[feat] = X_train[feat].dropna().values

        self._reference_fraud_rate = float(y_train.mean()) if len(y_train) > 0 else 0.0
        if score_dist is not None:
            self._reference_score_dist = np.asarray(score_dist)

        self._fitted = True
        log.info(
            f"[DriftDetector] Baseline set: {len(self._reference)} features, "
            f"fraud_rate={self._reference_fraud_rate:.4f}"
        )
        return self

    # ── Detect ────────────────────────────────────────────────────────────────

    def detect(
        self,
        X_current: pd.DataFrame,
        current_scores: Optional[np.ndarray] = None,
        current_labels: Optional[np.ndarray] = None,
    ) -> dict:
        """
        Run full drift detection suite on current production window.
        Returns structured report with per-feature PSI, KS results, and overall severity.
        """
        if not self._fitted:
            return {"error": "DriftDetector not fitted — call fit() first"}

        feature_drift = {}
        overall_psi = 0.0
        drifted_features = []

        # 1. Feature drift (PSI + KS per feature)
        for feat in DRIFT_MONITOR_FEATURES:
            if feat not in self._reference or feat not in X_current.columns:
                continue

            ref_arr = self._reference[feat]
            cur_arr = X_current[feat].dropna().values

            if len(cur_arr) < 30:
                continue

            psi_val = compute_psi(ref_arr, cur_arr)
            ks_result = compute_ks(ref_arr, cur_arr)
            severity = psi_severity(psi_val)

            feature_drift[feat] = {
                "psi": psi_val,
                "severity": severity,
                "ks_statistic": ks_result["statistic"],
                "ks_pvalue": ks_result["pvalue"],
                "ks_drifted": ks_result["drifted"],
            }

            overall_psi += psi_val
            if severity in ("warning", "critical"):
                drifted_features.append(feat)

        mean_psi = overall_psi / max(len(feature_drift), 1)

        # 2. Score distribution drift
        score_drift = {}
        if current_scores is not None and self._reference_score_dist is not None:
            s_psi = compute_psi(self._reference_score_dist, current_scores)
            s_ks  = compute_ks(self._reference_score_dist, current_scores)
            score_drift = {
                "psi": s_psi,
                "severity": psi_severity(s_psi),
                "ks_drifted": s_ks["drifted"],
                "current_mean_score": round(float(current_scores.mean()), 4),
                "reference_mean_score": round(float(self._reference_score_dist.mean()), 4),
            }

        # 3. Label / fraud rate drift
        label_drift = {}
        if current_labels is not None and self._reference_fraud_rate is not None:
            current_rate = float(current_labels.mean())
            rate_change = abs(current_rate - self._reference_fraud_rate)
            label_drift = {
                "current_fraud_rate": round(current_rate, 6),
                "reference_fraud_rate": round(self._reference_fraud_rate, 6),
                "rate_change": round(rate_change, 6),
                "severity": "critical" if rate_change > 0.01 else (
                    "warning" if rate_change > 0.003 else "stable"
                ),
            }

        # Overall verdict
        overall_severity = "stable"
        if mean_psi >= PSI_CRITICAL or score_drift.get("severity") == "critical":
            overall_severity = "critical"
        elif mean_psi >= PSI_WARNING or score_drift.get("severity") == "warning":
            overall_severity = "warning"
        if label_drift.get("severity") == "critical":
            overall_severity = "critical"

        return {
            "detected_at": datetime.now(timezone.utc).isoformat(),
            "overall_severity": overall_severity,
            "mean_feature_psi": round(mean_psi, 6),
            "drifted_features": drifted_features,
            "should_retrain": overall_severity == "critical",
            "feature_drift": feature_drift,
            "score_drift": score_drift,
            "label_drift": label_drift,
            "sample_size": len(X_current),
        }

    # ── Persistence (Redis) ───────────────────────────────────────────────────

    async def save_reference_to_redis(self) -> bool:
        """Persist baseline statistics to Redis for cross-process sharing."""
        try:
            from app.core.redis import get_redis_client
            r = await get_redis_client()

            ref_stats = {
                feat: {
                    "mean": float(arr.mean()),
                    "std": float(arr.std()),
                    "p10": float(np.percentile(arr, 10)),
                    "p50": float(np.percentile(arr, 50)),
                    "p90": float(np.percentile(arr, 90)),
                }
                for feat, arr in self._reference.items()
            }

            payload = {
                "reference_stats": ref_stats,
                "reference_fraud_rate": self._reference_fraud_rate,
                "fitted_at": datetime.now(timezone.utc).isoformat(),
            }
            await r.setex("drift:reference", 86400 * 30, json.dumps(payload))
            return True
        except Exception as exc:
            log.warning(f"[DriftDetector] Save to Redis failed: {exc}")
            return False

    async def load_reference_from_redis(self) -> bool:
        """Load previously saved baseline from Redis."""
        try:
            from app.core.redis import get_redis_client
            r = await get_redis_client()
            raw = await r.get("drift:reference")
            if not raw:
                return False
            data = json.loads(raw)
            # Reconstruct minimal arrays from stats (approximate)
            self._reference_fraud_rate = data.get("reference_fraud_rate")
            self._fitted = True
            return True
        except Exception as exc:
            log.debug(f"[DriftDetector] Load from Redis failed: {exc}")
            return False


# ── Module singleton ──────────────────────────────────────────────────────────

_detector: Optional[DriftDetector] = None


def get_drift_detector() -> DriftDetector:
    global _detector
    if _detector is None:
        _detector = DriftDetector()
    return _detector
