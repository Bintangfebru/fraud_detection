"""
FraudShield — Feature Store
Feast-compatible feature store API backed by Redis (online) + Postgres (offline).

Architecture:
  - Online store  → Redis (low-latency, TTL-based)
  - Offline store → Postgres (historical training data)
  - Feature views → registered schemas for entity groups

Usage:
    from app.ml.feature_store import FeatureStore, CardFeatureView

    store = FeatureStore()
    feats = await store.get_online_features(entity_key="card:1234", view="card_aggregates")
    await store.push_online_features(entity_key="card:1234", view="card_aggregates", features={...})
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

log = logging.getLogger("fraudshield.feature_store")

# ── Feature Schemas (Views) ───────────────────────────────────────────────────

@dataclass
class FeatureView:
    """Defines a named group of features for a given entity type."""
    name: str
    entity: str                         # e.g. "card", "merchant", "user"
    features: list[str]                 # feature names in this view
    ttl_seconds: int = 3600             # online store TTL
    description: str = ""

    def redis_key(self, entity_key: str) -> str:
        return f"fs:{self.name}:{entity_key}"


# ── Registered Feature Views ──────────────────────────────────────────────────

CARD_AGGREGATES_VIEW = FeatureView(
    name="card_aggregates",
    entity="card",
    features=[
        "amt_mean_per_card", "amt_std_per_card", "txn_count_per_card",
        "unique_merchants", "unique_categories", "last_txn_amount",
        "last_txn_hour", "txn_count_last_1h", "txn_count_last_24h",
        "max_amt_last_24h",
    ],
    ttl_seconds=7200,
    description="Card-level rolling aggregates for real-time scoring",
)

MERCHANT_STATS_VIEW = FeatureView(
    name="merchant_stats",
    entity="merchant",
    features=[
        "merchant_fraud_rate_30d", "merchant_txn_count_30d",
        "merchant_avg_amount", "merchant_chargeback_rate",
        "merchant_unique_cards_30d",
    ],
    ttl_seconds=3600,
    description="Merchant-level fraud stats",
)

BEHAVIOR_PATTERNS_VIEW = FeatureView(
    name="behavior_patterns",
    entity="card",
    features=[
        "typical_hour_mean", "typical_amt_mean", "typical_category",
        "velocity_spike_flag", "new_merchant_flag", "geo_anomaly_flag",
        "night_txn_ratio", "weekend_txn_ratio",
    ],
    ttl_seconds=14400,
    description="Behavioral pattern features for fraud behavior analysis",
)

_REGISTRY: dict[str, FeatureView] = {
    v.name: v for v in [
        CARD_AGGREGATES_VIEW,
        MERCHANT_STATS_VIEW,
        BEHAVIOR_PATTERNS_VIEW,
    ]
}


# ── Feature Store ─────────────────────────────────────────────────────────────

class FeatureStore:
    """
    Online/offline feature store.
    Online  → Redis (sub-ms reads for inference)
    Offline → Postgres (training data hydration)
    """

    def __init__(self):
        self._redis = None

    async def _get_redis(self):
        if self._redis is None:
            from app.core.redis import get_redis_client
            self._redis = await get_redis_client()
        return self._redis

    # ── Online store (Redis) ──────────────────────────────────────────────────

    async def get_online_features(
        self,
        entity_key: str,
        view: str,
    ) -> Optional[dict[str, Any]]:
        """
        Retrieve features from online store (Redis).
        Returns None if entity not found (cache miss).
        """
        feature_view = _REGISTRY.get(view)
        if not feature_view:
            log.warning(f"[FeatureStore] Unknown view '{view}'")
            return None

        try:
            r = await self._get_redis()
            raw = await r.get(feature_view.redis_key(entity_key))
            if raw is None:
                return None
            payload = json.loads(raw)
            return payload.get("features")
        except Exception as exc:
            log.debug(f"[FeatureStore] Online get error: {exc}")
            return None

    async def push_online_features(
        self,
        entity_key: str,
        view: str,
        features: dict[str, Any],
    ) -> bool:
        """
        Write features to online store (Redis) with TTL.
        Called after each transaction to keep aggregates fresh.
        """
        feature_view = _REGISTRY.get(view)
        if not feature_view:
            return False

        try:
            r = await self._get_redis()
            payload = {
                "entity_key": entity_key,
                "view": view,
                "features": features,
                "written_at": datetime.now(timezone.utc).isoformat(),
            }
            await r.setex(
                feature_view.redis_key(entity_key),
                feature_view.ttl_seconds,
                json.dumps(payload),
            )
            return True
        except Exception as exc:
            log.debug(f"[FeatureStore] Online push error: {exc}")
            return False

    async def delete_online_features(self, entity_key: str, view: str) -> None:
        """Invalidate cached features for an entity (e.g., after label update)."""
        feature_view = _REGISTRY.get(view)
        if not feature_view:
            return
        try:
            r = await self._get_redis()
            await r.delete(feature_view.redis_key(entity_key))
        except Exception as exc:
            log.debug(f"[FeatureStore] Delete error: {exc}")

    # ── Behavior feature computation ─────────────────────────────────────────

    async def compute_and_push_card_features(
        self,
        card_hash: str,
        new_txn_amount: float,
        new_txn_hour: int,
        merchant: str,
        category: str,
        history: Optional[list[dict]] = None,
    ) -> dict[str, Any]:
        """
        Compute card aggregate features from transaction history and push to store.
        Falls back to defaults for cold-start cards.
        """
        import numpy as np

        if not history:
            # Cold-start defaults
            features = {
                "amt_mean_per_card": new_txn_amount,
                "amt_std_per_card": 0.0,
                "txn_count_per_card": 1,
                "unique_merchants": 1,
                "unique_categories": 1,
                "last_txn_amount": new_txn_amount,
                "last_txn_hour": new_txn_hour,
                "txn_count_last_1h": 1,
                "txn_count_last_24h": 1,
                "max_amt_last_24h": new_txn_amount,
            }
        else:
            amounts = [h["amount"] for h in history if "amount" in h]
            merchants = [h.get("merchant", "") for h in history]
            categories = [h.get("category", "") for h in history]
            hours = [h.get("hour", 12) for h in history]

            features = {
                "amt_mean_per_card": float(np.mean(amounts)) if amounts else new_txn_amount,
                "amt_std_per_card": float(np.std(amounts)) if len(amounts) > 1 else 0.0,
                "txn_count_per_card": len(history),
                "unique_merchants": len(set(merchants)),
                "unique_categories": len(set(categories)),
                "last_txn_amount": amounts[-1] if amounts else new_txn_amount,
                "last_txn_hour": hours[-1] if hours else new_txn_hour,
                "txn_count_last_1h": sum(
                    1 for h in history
                    if abs(h.get("hour", new_txn_hour) - new_txn_hour) <= 1
                ),
                "txn_count_last_24h": len(history),
                "max_amt_last_24h": float(max(amounts)) if amounts else new_txn_amount,
            }

        await self.push_online_features(
            entity_key=f"card:{card_hash}",
            view="card_aggregates",
            features=features,
        )
        return features

    async def compute_behavior_patterns(
        self,
        card_hash: str,
        history: list[dict],
    ) -> dict[str, Any]:
        """
        Compute behavioral pattern features from transaction history.
        Detects velocity spikes, new merchants, geo anomalies.
        """
        import numpy as np

        if not history:
            features = {
                "typical_hour_mean": 12.0,
                "typical_amt_mean": 75.0,
                "typical_category": "misc_pos",
                "velocity_spike_flag": 0,
                "new_merchant_flag": 0,
                "geo_anomaly_flag": 0,
                "night_txn_ratio": 0.0,
                "weekend_txn_ratio": 0.0,
            }
        else:
            hours = [h.get("hour", 12) for h in history]
            amounts = [h.get("amount", 0.0) for h in history]
            merchants = [h.get("merchant", "") for h in history]
            categories = [h.get("category", "") for h in history]

            night_count = sum(1 for h in hours if h < 6 or h >= 22)
            txn_count_last_1h = sum(
                1 for h in history
                if abs(h.get("hour", 0) - (history[-1].get("hour", 0) if history else 0)) <= 1
            )

            features = {
                "typical_hour_mean": float(np.mean(hours)) if hours else 12.0,
                "typical_amt_mean": float(np.mean(amounts)) if amounts else 75.0,
                "typical_category": max(set(categories), key=categories.count) if categories else "misc_pos",
                "velocity_spike_flag": 1 if txn_count_last_1h >= 5 else 0,
                "new_merchant_flag": 0,  # set externally if merchant is new
                "geo_anomaly_flag": 0,   # set externally via geo comparison
                "night_txn_ratio": round(night_count / max(len(hours), 1), 4),
                "weekend_txn_ratio": 0.0,  # requires date info
            }

        await self.push_online_features(
            entity_key=f"card:{card_hash}",
            view="behavior_patterns",
            features=features,
        )
        return features

    # ── Registry inspection ───────────────────────────────────────────────────

    def list_views(self) -> list[dict]:
        """List all registered feature views."""
        return [
            {
                "name": v.name,
                "entity": v.entity,
                "features": v.features,
                "ttl_seconds": v.ttl_seconds,
                "description": v.description,
            }
            for v in _REGISTRY.values()
        ]

    def get_view(self, name: str) -> Optional[FeatureView]:
        return _REGISTRY.get(name)


# ── Module-level singleton ────────────────────────────────────────────────────

_feature_store: Optional[FeatureStore] = None


def get_feature_store() -> FeatureStore:
    global _feature_store
    if _feature_store is None:
        _feature_store = FeatureStore()
    return _feature_store
