"""
FraudShield — Graph-Based Fraud Analysis
Deteksi fraud rings dan relationship patterns menggunakan graph analysis.

Tanpa external graph DB (Neo4j dll), ini menggunakan in-memory networkx
untuk analisis batch atau Redis untuk real-time shared-entity detection.
"""

from __future__ import annotations

import json
import logging
from collections import defaultdict
from datetime import datetime, timezone, timedelta
from typing import Optional

log = logging.getLogger("fraudshield.graph")

# Thresholds
SHARED_ENTITY_THRESHOLD = 3   # berapa card berbeda share merchant/IP
RING_DETECTION_WINDOW_HOURS = 24


class GraphFraudAnalyzer:
    """
    Analisis fraud berbasis graph:
    1. Shared entity detection (multiple cards → same merchant/IP/city)
    2. Transaction velocity graph (card → merchant subgraph)
    3. Fraud ring detection (bipartite graph card-merchant)
    """

    def __init__(self):
        self._redis = None

    async def _get_redis(self):
        if self._redis is None:
            from app.core.redis import get_redis_client
            self._redis = await get_redis_client()
        return self._redis

    # ── Real-time shared entity ───────────────────────────────────────────────

    async def record_transaction_entity(
        self,
        card_hash: str,
        merchant: str,
        city: str,
        amount: float,
    ) -> None:
        """
        Catat asosiasi card → merchant/city dalam Redis.
        Dipakai untuk mendeteksi shared entities secara real-time.
        """
        try:
            r = await self._get_redis()
            ts = int(datetime.now(timezone.utc).timestamp())
            window = RING_DETECTION_WINDOW_HOURS * 3600

            # merchant → set of cards
            pipe = r.pipeline()
            pipe.zadd(f"graph:merchant:{_safe_key(merchant)}:cards",
                     {card_hash: ts})
            pipe.expire(f"graph:merchant:{_safe_key(merchant)}:cards", window)

            # card → set of merchants
            pipe.zadd(f"graph:card:{card_hash}:merchants",
                     {_safe_key(merchant): ts})
            pipe.expire(f"graph:card:{card_hash}:merchants", window)

            # city → set of cards
            if city:
                pipe.zadd(f"graph:city:{_safe_key(city)}:cards",
                         {card_hash: ts})
                pipe.expire(f"graph:city:{_safe_key(city)}:cards", window)

            await pipe.execute()
        except Exception as e:
            log.debug(f"record_transaction_entity error: {e}")

    async def check_shared_entities(
        self, card_hash: str, merchant: str, city: str
    ) -> dict:
        """
        Cek apakah merchant/city ini digunakan oleh banyak cards lain.
        Ini adalah signal kuat untuk fraud ring.
        """
        try:
            r = await self._get_redis()
            window_start = int(
                (datetime.now(timezone.utc) - timedelta(hours=RING_DETECTION_WINDOW_HOURS))
                .timestamp()
            )

            # Count cards sharing this merchant
            merchant_cards = await r.zrangebyscore(
                f"graph:merchant:{_safe_key(merchant)}:cards",
                window_start, "+inf"
            )
            n_cards_on_merchant = len(set(merchant_cards))

            # Count merchants this card visited
            card_merchants = await r.zrangebyscore(
                f"graph:card:{card_hash}:merchants",
                window_start, "+inf"
            )
            n_merchants_by_card = len(set(card_merchants))

            # Count cards in same city
            city_cards = []
            if city:
                city_cards = await r.zrangebyscore(
                    f"graph:city:{_safe_key(city)}:cards",
                    window_start, "+inf"
                )

            is_suspicious = (
                n_cards_on_merchant >= SHARED_ENTITY_THRESHOLD or
                n_merchants_by_card >= 10
            )

            return {
                "is_suspicious": is_suspicious,
                "n_cards_on_merchant": n_cards_on_merchant,
                "n_merchants_by_card": n_merchants_by_card,
                "n_cards_in_city": len(set(city_cards)),
                "merchant_risk_level": (
                    "high" if n_cards_on_merchant >= SHARED_ENTITY_THRESHOLD * 2
                    else "medium" if n_cards_on_merchant >= SHARED_ENTITY_THRESHOLD
                    else "normal"
                ),
                "window_hours": RING_DETECTION_WINDOW_HOURS,
                "signals": _build_graph_signals(
                    n_cards_on_merchant, n_merchants_by_card, len(set(city_cards))
                ),
            }
        except Exception as e:
            log.warning(f"check_shared_entities error: {e}")
            return {"is_suspicious": False, "error": str(e)}

    # ── Batch fraud ring detection ────────────────────────────────────────────

    async def detect_fraud_rings(self, session=None, min_ring_size: int = 3) -> list[dict]:
        """
        Detect fraud rings dari DB menggunakan bipartite graph analysis.
        Mencari clusters of cards yang share merchants secara berlebihan.
        """
        if session is None:
            return []

        try:
            from sqlalchemy import text
            sql = text("""
                WITH merchant_card_pairs AS (
                    SELECT
                        t.merchant,
                        COALESCE(t.card_hash, 'unknown') AS card_hash,
                        COUNT(*) AS txn_count,
                        SUM(t.amt) AS total_amt,
                        MAX(fp.risk_score) AS max_risk_score
                    FROM transactions t
                    LEFT JOIN fraud_predictions fp
                        ON fp.transaction_ref = t.transaction_ref
                    WHERE t.trans_datetime >= NOW() - INTERVAL '24 hours'
                    GROUP BY t.merchant, t.card_hash
                    HAVING COUNT(*) >= 1
                ),
                suspicious_merchants AS (
                    SELECT merchant, COUNT(DISTINCT card_hash) AS n_cards
                    FROM merchant_card_pairs
                    GROUP BY merchant
                    HAVING COUNT(DISTINCT card_hash) >= :min_cards
                )
                SELECT
                    sm.merchant,
                    sm.n_cards,
                    ARRAY_AGG(DISTINCT mcp.card_hash) AS involved_cards,
                    AVG(mcp.max_risk_score) AS avg_risk_score,
                    SUM(mcp.total_amt) AS total_amount
                FROM suspicious_merchants sm
                JOIN merchant_card_pairs mcp ON mcp.merchant = sm.merchant
                GROUP BY sm.merchant, sm.n_cards
                ORDER BY sm.n_cards DESC
                LIMIT 50
            """)
            result = await session.execute(sql, {"min_cards": min_ring_size})
            rows = result.mappings().all()

            rings = []
            for row in rows:
                involved = row.get("involved_cards") or []
                rings.append({
                    "merchant": row["merchant"],
                    "n_cards": int(row["n_cards"]),
                    "involved_cards": [c[:8] + "..." for c in involved[:10]],
                    "avg_risk_score": round(float(row.get("avg_risk_score") or 0), 3),
                    "total_amount": round(float(row.get("total_amount") or 0), 2),
                    "ring_type": "merchant_concentration",
                    "severity": (
                        "high" if int(row["n_cards"]) >= 10
                        else "medium" if int(row["n_cards"]) >= 5
                        else "low"
                    ),
                })
            return rings

        except Exception as e:
            log.warning(f"detect_fraud_rings error: {e}")
            return []

    # ── Card relationship graph ────────────────────────────────────────────────

    async def get_card_relationship_graph(
        self, card_hash: str, depth: int = 2
    ) -> dict:
        """
        Get immediate fraud network around a card.
        Returns node/edge structure for visualization.
        """
        try:
            r = await self._get_redis()
            window_start = int(
                (datetime.now(timezone.utc) - timedelta(hours=RING_DETECTION_WINDOW_HOURS))
                .timestamp()
            )

            # Get merchants visited by this card
            merchants = await r.zrangebyscore(
                f"graph:card:{card_hash}:merchants",
                window_start, "+inf",
            )

            nodes = [{"id": card_hash[:8], "type": "card", "is_target": True}]
            edges = []
            related_cards = set()

            for m in merchants[:10]:  # limit to top 10 merchants
                m_str = m if isinstance(m, str) else m.decode()
                nodes.append({"id": m_str[:20], "type": "merchant"})
                edges.append({
                    "source": card_hash[:8],
                    "target": m_str[:20],
                    "type": "transacted_at",
                })

                # Find other cards at this merchant
                sibling_cards = await r.zrangebyscore(
                    f"graph:merchant:{m_str}:cards",
                    window_start, "+inf",
                )
                for sc in sibling_cards[:5]:
                    sc_str = sc if isinstance(sc, str) else sc.decode()
                    if sc_str != card_hash and sc_str not in related_cards:
                        related_cards.add(sc_str)
                        nodes.append({"id": sc_str[:8], "type": "card", "is_related": True})
                        edges.append({
                            "source": sc_str[:8],
                            "target": m_str[:20],
                            "type": "transacted_at",
                        })

            return {
                "nodes": nodes[:50],
                "edges": edges[:100],
                "n_related_cards": len(related_cards),
                "n_shared_merchants": len(merchants),
            }
        except Exception as e:
            log.warning(f"get_card_relationship_graph error: {e}")
            return {"nodes": [], "edges": []}


# ── Helpers ───────────────────────────────────────────────────────────────────

def _safe_key(s: str) -> str:
    """Sanitize string for use as Redis key component."""
    return s.replace(" ", "_").replace(":", "_").replace("/", "_")[:50]


def _build_graph_signals(n_cards_on_merchant: int, n_merchants_by_card: int, n_city_cards: int) -> list[str]:
    signals = []
    if n_cards_on_merchant >= SHARED_ENTITY_THRESHOLD * 2:
        signals.append(f"HIGH: {n_cards_on_merchant} different cards at same merchant (fraud ring signal)")
    elif n_cards_on_merchant >= SHARED_ENTITY_THRESHOLD:
        signals.append(f"MEDIUM: {n_cards_on_merchant} cards sharing this merchant")
    if n_merchants_by_card >= 10:
        signals.append(f"Card visited {n_merchants_by_card} merchants recently (unusual)")
    if n_city_cards >= 20:
        signals.append(f"High card concentration in this city ({n_city_cards} cards)")
    return signals
