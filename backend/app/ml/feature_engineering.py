"""
FraudShield — Feature Engineering
Defines SELECTED_FEATURES, preprocessing transformers, and feature
derivation logic used by both training (model_service) and inference (predictor).

All modules that need SELECTED_FEATURES must import from here:
    from app.ml.feature_engineering import SELECTED_FEATURES, build_preprocessor
"""

from __future__ import annotations

import logging
from typing import Any, Optional

import numpy as np
import pandas as pd
from sklearn.base import BaseEstimator, TransformerMixin
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

log = logging.getLogger("fraudshield.feature_engineering")

# ── Canonical feature list ─────────────────────────────────────────────────────
# Order matters — must match the column order of every trained model.
# Do NOT reorder without retraining all models.

SELECTED_FEATURES: list[str] = [
    # Amount signals
    "amt",
    "amt_log",
    "amt_ratio",           # amt / card_mean_amt
    "amt_mean_per_card",
    "amt_std_per_card",

    # Temporal signals
    "hour",
    "month",

    # Velocity / behavioural aggregates
    "txn_count_per_card",
    "unique_merchants",
    "unique_categories",

    # Category one-hot flags
    "category_food_dining",
    "category_gas_transport",
    "category_grocery_pos",
    "category_kids_pets",
    "category_misc_net",
    "category_misc_pos",
    "category_personal_care",
    "category_shopping_net",

    # Encoded entity embeddings (merchant risk score, city risk score)
    "merchant",
    "city",
]

# Subset used for drift monitoring (must be numeric, no flags)
DRIFT_FEATURES: list[str] = [
    "amt", "hour", "amt_ratio", "txn_count_per_card",
    "unique_merchants", "amt_mean_per_card",
]

# ── Feature derivation helpers ─────────────────────────────────────────────────

def derive_features(row: dict) -> dict:
    """
    Derive engineered features from a raw transaction dict.
    Called at inference time — must be fast.

    Input keys expected:
        amt, card_mean_amt, card_std_amt, card_txn_count,
        hour, month, merchant_risk, city_risk,
        category (string), unique_merchants, unique_categories,
        amt_mean_per_card (alias of card_mean_amt), ...

    Returns dict with all SELECTED_FEATURES populated.
    """
    amt = float(row.get("amt", 0.0))
    card_mean = float(row.get("amt_mean_per_card") or row.get("card_mean_amt") or max(amt, 1.0))
    card_std  = float(row.get("amt_std_per_card")  or row.get("card_std_amt")  or 0.0)

    derived: dict[str, Any] = {
        # Amount
        "amt":               amt,
        "amt_log":           float(np.log1p(amt)),
        "amt_ratio":         round(amt / max(card_mean, 0.01), 4),
        "amt_mean_per_card": card_mean,
        "amt_std_per_card":  card_std,

        # Temporal
        "hour":  int(row.get("hour", 12)),
        "month": int(row.get("month", 1)),

        # Velocity
        "txn_count_per_card": int(row.get("txn_count_per_card", 1)),
        "unique_merchants":   int(row.get("unique_merchants", 1)),
        "unique_categories":  int(row.get("unique_categories", 1)),

        # Category flags (already pre-encoded or compute from string)
        "category_food_dining":    int(row.get("category_food_dining", 0)),
        "category_gas_transport":  int(row.get("category_gas_transport", 0)),
        "category_grocery_pos":    int(row.get("category_grocery_pos", 0)),
        "category_kids_pets":      int(row.get("category_kids_pets", 0)),
        "category_misc_net":       int(row.get("category_misc_net", 0)),
        "category_misc_pos":       int(row.get("category_misc_pos", 0)),
        "category_personal_care":  int(row.get("category_personal_care", 0)),
        "category_shopping_net":   int(row.get("category_shopping_net", 0)),

        # Entity embeddings (risk scores, 0–1 range)
        "merchant": float(row.get("merchant") or row.get("merchant_risk", 0.01)),
        "city":     float(row.get("city")     or row.get("city_risk",     0.01)),
    }

    # If category is a raw string, derive flags
    cat_str = str(row.get("category", "")).lower().replace(" ", "_")
    if cat_str and not any(row.get(f"category_{c}") for c in [
        "food_dining", "gas_transport", "grocery_pos", "kids_pets",
        "misc_net", "misc_pos", "personal_care", "shopping_net",
    ]):
        derived[f"category_{cat_str}"] = 1  # type: ignore[assignment]

    return derived


def features_to_array(feat_dict: dict, feature_names: list[str] | None = None) -> np.ndarray:
    """
    Convert a feature dict to a 2-D numpy array of shape (1, n_features).
    Missing features default to 0.0.
    """
    cols = feature_names or SELECTED_FEATURES
    row = [float(feat_dict.get(f, 0.0)) for f in cols]
    return np.array([row], dtype=np.float32)


# ── sklearn Transformer ────────────────────────────────────────────────────────

class FraudFeatureSelector(BaseEstimator, TransformerMixin):
    """
    sklearn-compatible transformer that:
      1. Selects only SELECTED_FEATURES columns from a DataFrame.
      2. Fills NaN values with column medians (fit on training data).
      3. Returns a numpy float32 array.

    Intended to be the first step in a sklearn Pipeline when using
    RandomForest / GradientBoosting (tree models don't need scaling).
    """

    def __init__(self, features: list[str] | None = None):
        self.features = features or SELECTED_FEATURES
        self._medians: dict[str, float] = {}

    def fit(self, X: pd.DataFrame, y=None) -> "FraudFeatureSelector":
        df = X if isinstance(X, pd.DataFrame) else pd.DataFrame(X)
        for f in self.features:
            if f in df.columns:
                self._medians[f] = float(df[f].median())
            else:
                self._medians[f] = 0.0
        return self

    def transform(self, X) -> np.ndarray:
        df = X if isinstance(X, pd.DataFrame) else pd.DataFrame(X)
        out = []
        for f in self.features:
            if f in df.columns:
                col = df[f].fillna(self._medians.get(f, 0.0)).astype(float)
            else:
                col = pd.Series([self._medians.get(f, 0.0)] * len(df))
            out.append(col.values)
        return np.column_stack(out).astype(np.float32)


def build_preprocessor(scale: bool = False) -> Pipeline:
    """
    Build a preprocessing Pipeline.
      scale=False → FraudFeatureSelector only (for tree-based models).
      scale=True  → FraudFeatureSelector + StandardScaler (for LR / SVM).
    """
    steps = [("selector", FraudFeatureSelector())]
    if scale:
        steps.append(("scaler", StandardScaler()))
    return Pipeline(steps)


# ── Fraud behavior feature enrichment (called before inference) ───────────────

async def enrich_from_feature_store(
    feat_dict: dict,
    card_hash: str,
    merchant: str,
) -> dict:
    """
    Pull card aggregates and behavioral patterns from the online feature store
    and merge into feat_dict.  Silently skips on cache miss or store error.
    """
    try:
        from app.ml.feature_store import get_feature_store
        store = get_feature_store()

        card_feats = await store.get_online_features(
            entity_key=f"card:{card_hash}", view="card_aggregates"
        )
        if card_feats:
            # Override/fill defaults with live aggregates
            for k, v in card_feats.items():
                if k in SELECTED_FEATURES and v is not None:
                    feat_dict.setdefault(k, v)

        behavior = await store.get_online_features(
            entity_key=f"card:{card_hash}", view="behavior_patterns"
        )
        if behavior:
            feat_dict["velocity_spike_flag"] = behavior.get("velocity_spike_flag", 0)
            feat_dict["night_txn_ratio"]     = behavior.get("night_txn_ratio", 0.0)

    except Exception as exc:
        log.debug(f"[FeatureEnrich] Feature store enrichment skipped: {exc}")

    return feat_dict
