"""
FraudShield — Anomaly Detector
Deteksi anomali transaksi menggunakan:
  - Isolation Forest (unsupervised)
  - Z-score / IQR outlier detection
  - Velocity-based anomalies (too many txn in short time)
  - Amount spike detection
"""

from __future__ import annotations

import logging
import os
import pickle
from datetime import datetime, timezone
from typing import Optional

import numpy as np
import pandas as pd

log = logging.getLogger("fraudshield.anomaly")

# Anomaly score thresholds
ANOMALY_SCORE_WARNING = -0.05    # Isolation Forest score (more negative = more anomalous)
ANOMALY_SCORE_CRITICAL = -0.15
ZSCORE_THRESHOLD = 3.0
VELOCITY_THRESHOLD = 10          # max txn per card per hour


class AnomalyDetector:
    """
    Unsupervised anomaly detection menggunakan Isolation Forest.
    Bisa digunakan sebagai layer kedua setelah ML prediction.
    """

    def __init__(
        self,
        contamination: float = 0.01,
        n_estimators: int = 100,
        random_state: int = 42,
    ):
        self.contamination = contamination
        self.n_estimators = n_estimators
        self.random_state = random_state
        self._model = None
        self._fitted_features: list[str] = []
        self._stats: dict = {}  # training distribution stats

    # ── Training ──────────────────────────────────────────────────────────────

    def fit(self, X: pd.DataFrame) -> "AnomalyDetector":
        """Fit Isolation Forest."""
        from sklearn.ensemble import IsolationForest

        self._fitted_features = list(X.columns)
        self._stats = self._compute_stats(X)

        log.info(f"Training Isolation Forest on {len(X):,} samples...")
        self._model = IsolationForest(
            contamination=self.contamination,
            n_estimators=self.n_estimators,
            random_state=self.random_state,
            n_jobs=-1,
        )
        self._model.fit(X[self._numeric_features(X)])
        log.info("Isolation Forest trained.")
        return self

    # ── Inference ─────────────────────────────────────────────────────────────

    def score_transaction(self, features: dict) -> dict:
        """
        Score satu transaksi dengan multiple anomaly checks.
        Returns comprehensive anomaly report.
        """
        results = {
            "is_anomaly": False,
            "anomaly_score": 0.0,
            "severity": "normal",
            "anomaly_types": [],
            "details": {},
        }

        # 1. Isolation Forest score
        if self._model is not None:
            try:
                iso_score = self._isolation_forest_score(features)
                results["anomaly_score"] = round(iso_score, 4)
                if iso_score < ANOMALY_SCORE_CRITICAL:
                    results["anomaly_types"].append("isolation_forest_critical")
                    results["severity"] = "critical"
                elif iso_score < ANOMALY_SCORE_WARNING:
                    results["anomaly_types"].append("isolation_forest_warning")
                    if results["severity"] == "normal":
                        results["severity"] = "warning"
            except Exception as e:
                log.debug(f"Isolation forest score error: {e}")

        # 2. Z-score anomalies
        z_anomalies = self._zscore_check(features)
        results["anomaly_types"].extend(z_anomalies)
        results["details"]["zscore_flags"] = z_anomalies
        if z_anomalies and results["severity"] == "normal":
            results["severity"] = "warning"

        # 3. Amount spike
        spike = self._amount_spike_check(features)
        if spike:
            results["anomaly_types"].append("amount_spike")
            results["details"]["amount_spike"] = spike
            if results["severity"] == "normal":
                results["severity"] = "warning"

        # 4. Time anomaly (late night + high amount)
        time_anom = self._time_anomaly_check(features)
        if time_anom:
            results["anomaly_types"].append("time_anomaly")
            results["details"]["time_anomaly"] = time_anom

        results["is_anomaly"] = len(results["anomaly_types"]) > 0
        return results

    def _isolation_forest_score(self, features: dict) -> float:
        """Isolation Forest anomaly score (-1 = anomaly, 0 = borderline, +1 = normal)."""
        numeric_feats = [f for f in self._fitted_features
                        if isinstance(features.get(f), (int, float))]
        row = [[float(features.get(f, 0)) for f in numeric_feats]]
        return float(self._model.score_samples(row)[0])

    def _zscore_check(self, features: dict) -> list[str]:
        """Flag features yang jauh dari distribusi training (|z| > threshold)."""
        flags = []
        for feat, val in features.items():
            if feat not in self._stats or not isinstance(val, (int, float)):
                continue
            mean = self._stats[feat].get("mean", 0)
            std = self._stats[feat].get("std", 1) or 1
            z = abs(float(val) - mean) / std
            if z > ZSCORE_THRESHOLD:
                flags.append(f"zscore_{feat}_{z:.1f}σ")
        return flags

    def _amount_spike_check(self, features: dict) -> Optional[str]:
        """Detect if amount is unusually high relative to card history."""
        amt = features.get("amt", 0)
        mean = features.get("amt_mean_per_card", 75)
        std = features.get("amt_std_per_card", 110) or 110
        if std <= 0:
            return None
        z = (amt - mean) / std
        if z > 5.0:
            return f"Amount ${amt:.2f} is {z:.1f}σ above card mean ${mean:.2f}"
        return None

    def _time_anomaly_check(self, features: dict) -> Optional[str]:
        """High-amount transaction in unusual hours."""
        hour = features.get("hour", 12)
        amt = features.get("amt", 0)
        is_night = hour <= 4 or hour >= 23
        if is_night and amt > 500:
            return f"High-amount (${amt:.2f}) transaction at {hour}:00 (unusual hour)"
        return None

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _numeric_features(self, X: pd.DataFrame) -> list[str]:
        return [c for c in X.columns if X[c].dtype in [np.float64, np.int64, float, int]]

    def _compute_stats(self, X: pd.DataFrame) -> dict:
        stats = {}
        for col in X.select_dtypes(include=[np.number]).columns:
            stats[col] = {
                "mean": float(X[col].mean()),
                "std": float(X[col].std()),
                "p5": float(X[col].quantile(0.05)),
                "p95": float(X[col].quantile(0.95)),
            }
        return stats

    # ── Serialization ─────────────────────────────────────────────────────────

    def save(self, path: str) -> None:
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        with open(path, "wb") as f:
            pickle.dump(self, f)
        log.info(f"AnomalyDetector saved to {path}")

    @classmethod
    def load(cls, path: str) -> "AnomalyDetector":
        with open(path, "rb") as f:
            obj = pickle.load(f)
        log.info(f"AnomalyDetector loaded from {path}")
        return obj


# ── Velocity Anomaly Checker (stateless, Redis-based) ─────────────────────────

class VelocityChecker:
    """
    Cek kecepatan transaksi (berapa banyak dalam window waktu tertentu).
    Menggunakan Redis sliding window counter.
    """

    def __init__(self):
        self._redis = None

    async def _get_redis(self):
        if self._redis is None:
            from app.core.redis import get_redis_client
            self._redis = await get_redis_client()
        return self._redis

    async def check_and_record(
        self,
        card_hash: str,
        window_minutes: int = 60,
    ) -> dict:
        """
        Catat transaksi baru dan cek apakah melebihi velocity threshold.
        """
        from datetime import datetime, timezone
        try:
            r = await self._get_redis()
            now_ts = int(datetime.now(timezone.utc).timestamp())
            window_start = now_ts - window_minutes * 60
            key = f"velocity:{card_hash}"

            pipe = r.pipeline()
            pipe.zadd(key, {str(now_ts): now_ts})
            pipe.zremrangebyscore(key, "-inf", window_start)
            pipe.zcard(key)
            pipe.expire(key, window_minutes * 60 * 2)
            results = await pipe.execute()

            count = int(results[2])
            is_anomaly = count > VELOCITY_THRESHOLD
            return {
                "card_hash": card_hash[:8] + "...",
                "txn_count_in_window": count,
                "window_minutes": window_minutes,
                "threshold": VELOCITY_THRESHOLD,
                "is_velocity_anomaly": is_anomaly,
                "message": (
                    f"Velocity alert: {count} transactions in {window_minutes}min"
                    if is_anomaly else None
                ),
            }
        except Exception as e:
            log.warning(f"VelocityChecker error: {e}")
            return {"is_velocity_anomaly": False, "txn_count_in_window": 0}
