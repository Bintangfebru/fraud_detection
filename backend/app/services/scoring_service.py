"""
FraudShield — Scoring Service
Helper untuk risk scoring, threshold management, dan confidence calculation.
"""

from app.config.settings import settings


def get_risk_label(score: float) -> str:
    if score >= settings.FRAUD_THRESHOLD:
        return "FRAUD"
    elif score >= settings.REVIEW_THRESHOLD:
        return "REVIEW"
    return "SAFE"


def get_severity(status: str) -> str:
    return {"FRAUD": "HIGH", "REVIEW": "MEDIUM", "SAFE": "LOW"}.get(status, "LOW")


def compute_confidence(risk_score: float) -> float:
    """
    Confidence tinggi saat score jauh dari ambiguity zone (0.5).
    Formula: 1 - |score - 0.5| * 1.8, di-clip ke [0, 1].
    """
    return round(float(min(1.0, max(0.0, 1 - abs(risk_score - 0.5) * 1.8))), 4)


def score_summary(scores: list[float]) -> dict:
    """Ringkasan distribusi risk score untuk batch/analytics."""
    if not scores:
        return {}
    fraud = sum(1 for s in scores if s >= settings.FRAUD_THRESHOLD)
    review = sum(1 for s in scores if settings.REVIEW_THRESHOLD <= s < settings.FRAUD_THRESHOLD)
    safe = len(scores) - fraud - review
    return {
        "total": len(scores),
        "fraud_count": fraud,
        "review_count": review,
        "safe_count": safe,
        "fraud_rate": round(fraud / len(scores), 4),
        "avg_score": round(sum(scores) / len(scores), 4),
        "max_score": round(max(scores), 4),
    }
