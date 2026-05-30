"""
FraudShield — Ensemble ML Engine
Combines XGBoost, LightGBM, and RandomForest into a soft-voting ensemble.

Usage:
    from app.ml.ensemble import EnsemblePredictor, build_ensemble_pipeline
"""

from __future__ import annotations

import logging
import os
from typing import Optional

import joblib
import numpy as np
import pandas as pd

log = logging.getLogger("fraudshield.ensemble")


# ── Individual model builders ─────────────────────────────────────────────────

def build_xgboost(scale_pos_weight: float = 10.0, n_jobs: int = -1):
    """XGBoost classifier tuned for imbalanced fraud detection."""
    try:
        from xgboost import XGBClassifier
    except ImportError as exc:
        raise ImportError("xgboost is required: pip install xgboost") from exc

    return XGBClassifier(
        n_estimators=300,
        max_depth=6,
        learning_rate=0.05,
        subsample=0.8,
        colsample_bytree=0.8,
        scale_pos_weight=scale_pos_weight,   # handles class imbalance
        eval_metric="aucpr",
        use_label_encoder=False,
        random_state=42,
        n_jobs=n_jobs,
        tree_method="hist",                  # fast histogram-based training
    )


def build_lightgbm(class_weight: str = "balanced", n_jobs: int = -1):
    """LightGBM classifier with leaf-wise growth and DART boosting."""
    try:
        from lightgbm import LGBMClassifier
    except ImportError as exc:
        raise ImportError("lightgbm is required: pip install lightgbm") from exc

    return LGBMClassifier(
        n_estimators=400,
        max_depth=7,
        learning_rate=0.04,
        num_leaves=63,
        subsample=0.85,
        colsample_bytree=0.85,
        class_weight=class_weight,
        boosting_type="gbdt",
        random_state=42,
        n_jobs=n_jobs,
        verbose=-1,                          # suppress LightGBM stdout
    )


def build_random_forest(n_jobs: int = -1):
    """RandomForest — kept as third voter for ensemble diversity."""
    from sklearn.ensemble import RandomForestClassifier
    return RandomForestClassifier(
        n_estimators=200,
        max_depth=14,
        class_weight="balanced",
        random_state=42,
        n_jobs=n_jobs,
    )


# ── Soft-voting ensemble ──────────────────────────────────────────────────────

class EnsemblePredictor:
    """
    Soft-voting ensemble: XGBoost + LightGBM + RandomForest.
    Final probability = weighted average of individual probabilities.

    Weights default to [0.40, 0.40, 0.20] — XGB & LGB dominate because
    they are better calibrated on tabular fraud data.
    """

    DEFAULT_WEIGHTS = [0.40, 0.40, 0.20]  # [xgb, lgb, rf]

    def __init__(self, weights: Optional[list[float]] = None):
        self.weights = weights or self.DEFAULT_WEIGHTS
        self._xgb = None
        self._lgb = None
        self._rf = None
        self._feature_names: list[str] = []
        self._is_fitted = False

    # ── Training ──────────────────────────────────────────────────────────────

    def fit(
        self,
        X_train: np.ndarray,
        y_train: np.ndarray,
        feature_names: list[str],
        X_val: Optional[np.ndarray] = None,
        y_val: Optional[np.ndarray] = None,
    ) -> "EnsemblePredictor":
        """
        Train all three base learners.
        X_train / X_val should be numeric arrays (after preprocessing).
        """
        self._feature_names = feature_names
        fraud_count = int(y_train.sum())
        legit_count = int(len(y_train) - fraud_count)
        scale_pw = max(1.0, legit_count / max(fraud_count, 1))

        log.info(
            f"[Ensemble] Training on {len(X_train):,} samples  "
            f"(fraud={fraud_count:,}, legit={legit_count:,}, "
            f"scale_pos_weight={scale_pw:.1f})"
        )

        self._xgb = build_xgboost(scale_pos_weight=scale_pw)
        self._lgb = build_lightgbm()
        self._rf = build_random_forest()

        # XGBoost with early-stopping if validation set provided
        if X_val is not None and y_val is not None:
            from xgboost import XGBClassifier
            eval_set = [(X_val, y_val)]
            self._xgb.fit(
                X_train, y_train,
                eval_set=eval_set,
                verbose=False,
            )
        else:
            self._xgb.fit(X_train, y_train)

        log.info("[Ensemble] XGBoost trained.")

        self._lgb.fit(X_train, y_train)
        log.info("[Ensemble] LightGBM trained.")

        self._rf.fit(X_train, y_train)
        log.info("[Ensemble] RandomForest trained.")

        self._is_fitted = True
        return self

    # ── Inference ─────────────────────────────────────────────────────────────

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        """
        Weighted soft-voting probability.
        Returns array of shape (n_samples, 2).
        """
        if not self._is_fitted:
            raise RuntimeError("EnsemblePredictor is not fitted yet.")

        p_xgb = self._xgb.predict_proba(X)[:, 1]
        p_lgb = self._lgb.predict_proba(X)[:, 1]
        p_rf  = self._rf.predict_proba(X)[:, 1]

        w = self.weights
        p_fraud = w[0] * p_xgb + w[1] * p_lgb + w[2] * p_rf
        p_legit = 1.0 - p_fraud
        return np.column_stack([p_legit, p_fraud])

    def predict(self, X: np.ndarray, threshold: float = 0.5) -> np.ndarray:
        return (self.predict_proba(X)[:, 1] >= threshold).astype(int)

    # ── Feature importance (averaged across base learners) ────────────────────

    def feature_importances(self) -> dict[str, float]:
        """
        Return averaged feature importances from XGBoost and LightGBM.
        (RF also included with lower weight.)
        """
        if not self._is_fitted:
            return {}

        names = self._feature_names
        imp_xgb = self._xgb.feature_importances_
        imp_lgb = self._lgb.feature_importances_
        imp_rf  = self._rf.feature_importances_

        # Normalize each to sum = 1
        def _norm(arr):
            s = arr.sum()
            return arr / s if s > 0 else arr

        combined = (
            0.40 * _norm(imp_xgb) +
            0.40 * _norm(imp_lgb) +
            0.20 * _norm(imp_rf)
        )
        return {
            name: round(float(imp), 5)
            for name, imp in zip(names, combined)
        }

    # ── Serialization ─────────────────────────────────────────────────────────

    def save(self, path: str) -> None:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        joblib.dump(self, path)
        log.info(f"[Ensemble] Saved to {path}")

    @classmethod
    def load(cls, path: str) -> "EnsemblePredictor":
        obj = joblib.load(path)
        if not isinstance(obj, cls):
            raise TypeError(f"Loaded object is {type(obj)}, expected EnsemblePredictor")
        return obj


# ── sklearn-compatible wrapper for Pipeline ───────────────────────────────────

class EnsemblePipelineWrapper:
    """
    Thin sklearn-compatible wrapper so EnsemblePredictor works inside
    a sklearn Pipeline and is compatible with the existing ModelService/predictor.
    """

    def __init__(self, weights: Optional[list[float]] = None):
        self._ensemble = EnsemblePredictor(weights=weights)

    def fit(self, X, y):
        feature_names = list(range(X.shape[1])) if isinstance(X, np.ndarray) else list(X.columns)
        self._ensemble.fit(np.asarray(X), np.asarray(y), feature_names=feature_names)
        return self

    def predict_proba(self, X):
        return self._ensemble.predict_proba(np.asarray(X))

    def predict(self, X):
        return self._ensemble.predict(np.asarray(X))

    @property
    def feature_importances_(self):
        d = self._ensemble.feature_importances()
        return np.array(list(d.values()))

    @property
    def classes_(self):
        return np.array([0, 1])
