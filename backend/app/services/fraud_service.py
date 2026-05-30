"""
FraudShield — Fraud Service
Orchestrates: feature engineering → prediction → DB persistence → alert creation.
Refactored to use repository pattern.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import PredictionError
from app.core.logging import get_logger
from app.ml.feature_engineering import derive_features, features_to_array
from app.ml.predictor import predict_fraud
from app.ml.preprocessing import (
    mask_cc_num,
    normalize_category,
    normalize_merchant,
    parse_datetime,
    sanitize_amount,
)
from app.models.prediction import Alert, AuditLog, FraudPrediction
from app.models.transaction import Transaction
from app.repositories.fraud_repo import (
    AlertRepository,
    AuditLogRepository,
    FraudPredictionRepository,
    TransactionRepository,
)
from app.schemas.fraud import PredictionResult, TransactionInput

# ── Streaming imports (lazy to avoid circular imports) ────────────────────────
def _get_streaming():
    from app.streaming.kafka_producer import kafka_producer
    from app.streaming.redis_pubsub import redis_pubsub_bridge
    from app.streaming.kafka_consumer import event_replay
    from app.streaming.metrics_aggregator import metrics_aggregator
    return kafka_producer, redis_pubsub_bridge, event_replay, metrics_aggregator

log = get_logger("services.fraud")

# ── Thresholds ────────────────────────────────────────────────────────────────
FRAUD_THRESHOLD  = 0.5
REVIEW_THRESHOLD = 0.3


class FraudService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.txn_repo = TransactionRepository(session)
        self.pred_repo = FraudPredictionRepository(session)
        self.alert_repo = AlertRepository(session)
        self.audit_repo = AuditLogRepository(session)

    async def process_transaction(
        self,
        txn_input: TransactionInput,
        actor: str = "api",
        ip_address: Optional[str] = None,
    ) -> PredictionResult:
        """
        Full prediction pipeline:
        1. Preprocess & sanitize input
        2. Feature engineering
        3. ML inference
        4. Persist Transaction + FraudPrediction
        5. Create alert if needed
        6. Write audit log
        7. Return PredictionResult
        """
        start = datetime.now(timezone.utc)
        txn_ref = (
            f"TXN-{start.strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:6].upper()}"
        )

        try:
            # ── 1. Preprocess ──────────────────────────────────────────────
            amt = sanitize_amount(txn_input.amt)
            merchant = normalize_merchant(txn_input.merchant)
            category = normalize_category(txn_input.category)
            city = (txn_input.city or "").strip()
            cc_masked = mask_cc_num(txn_input.cc_num)
            trans_dt = parse_datetime(txn_input.trans_date_trans_time)

            # ── 2. Feature engineering ─────────────────────────────────────
            features = derive_features({
                "amt":                amt,
                "merchant":           merchant,
                "category":           category,
                "city":               city,
                "hour":               trans_dt.hour,
                "month":              trans_dt.month,
                "amt_mean_per_card":  txn_input.amt_mean_per_card,
                "amt_std_per_card":   txn_input.amt_std_per_card,
                "txn_count_per_card": txn_input.txn_count_per_card,
                "unique_merchants":   txn_input.unique_merchants,
                "unique_categories":  txn_input.unique_categories,
            })

            # ── 3. ML inference ────────────────────────────────────────────
            X = features_to_array(features)
            risk_score, elapsed = predict_fraud(X)

            if risk_score >= FRAUD_THRESHOLD:
                status = "FRAUD"
            elif risk_score >= REVIEW_THRESHOLD:
                status = "REVIEW"
            else:
                status = "SAFE"

            confidence = float(min(1.0, max(0.0, 1 - abs(risk_score - 0.5) * 1.8)))

            # ── 4. Persist ─────────────────────────────────────────────────
            txn_record = Transaction(
                transaction_ref=txn_ref,
                amt=amt,
                merchant=merchant,
                category=category,
                city=city or None,
                state=txn_input.state,
                cc_num_masked=cc_masked,
                gender=txn_input.gender,
                trans_datetime=trans_dt,
                hour=features.get("hour"),
                month=features.get("month"),
                amt_log=features.get("amt_log"),
                amt_mean_per_card=features.get("amt_mean_per_card"),
                amt_ratio=features.get("amt_ratio"),
                amt_std_per_card=features.get("amt_std_per_card"),
                txn_count_per_card=features.get("txn_count_per_card"),
                unique_merchants=features.get("unique_merchants"),
                unique_categories=features.get("unique_categories"),
                category_food_dining=features.get("category_food_dining"),
                category_gas_transport=features.get("category_gas_transport"),
                category_grocery_pos=features.get("category_grocery_pos"),
                category_kids_pets=features.get("category_kids_pets"),
                category_misc_net=features.get("category_misc_net"),
                category_misc_pos=features.get("category_misc_pos"),
                category_personal_care=features.get("category_personal_care"),
                category_shopping_net=features.get("category_shopping_net"),
            )
            await self.txn_repo.create(txn_record)

            pred_record = FraudPrediction(
                transaction_id=txn_record.id,
                transaction_ref=txn_ref,
                risk_score=risk_score,
                status=status,
                confidence=confidence,
                model_version="fraud_pipeline_v1",
                latency_ms=elapsed,
                features_snapshot=features,
            )
            await self.pred_repo.create(pred_record)

            # ── 5. Alert ───────────────────────────────────────────────────
            if status in ("FRAUD", "REVIEW"):
                severity = "HIGH" if status == "FRAUD" else "MEDIUM"
                alert = Alert(
                    prediction_id=pred_record.id,
                    transaction_ref=txn_ref,
                    severity=severity,
                    alert_type=f"{status}_DETECTED",
                    message=(
                        f"Transaction {txn_ref} from '{merchant}' "
                        f"${amt:,.2f} scored {risk_score:.1%} → {status}."
                    ),
                )
                await self.alert_repo.create(alert)

            # ── 6. Audit log ───────────────────────────────────────────────
            audit = AuditLog(
                actor=actor,
                action="predict",
                resource_type="transaction",
                resource_id=txn_ref,
                detail={"status": status, "risk_score": round(risk_score, 4)},
                ip_address=ip_address,
            )
            await self.audit_repo.create(audit)

            log.info(
                f"[{actor}] {txn_ref} | {status} | "
                f"score={risk_score:.4f} | amt=${amt:.2f} | {elapsed:.1f}ms"
            )

            # ── 7. Return ──────────────────────────────────────────────────
            return PredictionResult(
                transaction_id=txn_ref,
                risk_score=round(risk_score, 6),
                risk_pct=f"{risk_score * 100:.1f}%",
                status=status,
                confidence=round(confidence, 4),
                model_version="fraud_pipeline_v1",
                latency_ms=round(elapsed, 2),
                features_used=features,
                timestamp=start.isoformat(),
            )

        except PredictionError:
            raise
        except Exception as exc:
            log.error(f"process_transaction failed for {txn_ref}: {exc}", exc_info=True)
            raise PredictionError(str(exc)) from exc

    async def get_analytics_summary(self) -> dict:
        from sqlalchemy import func, select
        from app.models.transaction import Transaction as TxnModel
        from app.models.prediction import FraudPrediction as FPModel, Alert as AlertModel

        total = await self.session.scalar(
            select(func.count()).select_from(TxnModel)
        ) or 0
        fraud = await self.session.scalar(
            select(func.count()).select_from(FPModel).where(FPModel.status == "FRAUD")
        ) or 0
        review = await self.session.scalar(
            select(func.count()).select_from(FPModel).where(FPModel.status == "REVIEW")
        ) or 0
        open_alerts = await self.session.scalar(
            select(func.count()).select_from(AlertModel).where(
                AlertModel.is_resolved == False  # noqa: E712
            )
        ) or 0

        return {
            "total_transactions": total,
            "fraud_count": fraud,
            "review_count": review,
            "safe_count": max(0, total - fraud - review),
            "open_alerts": open_alerts,
            "fraud_rate": round(fraud / max(1, total), 4),
        }