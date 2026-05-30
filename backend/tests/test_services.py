"""
FraudShield — Service Tests
Jalankan: pytest tests/test_services.py -v
"""

import pytest
from app.services.scoring_service import (
    get_risk_label, get_severity, compute_confidence, score_summary
)
from app.config.settings import settings


def test_get_risk_label_fraud():
    assert get_risk_label(settings.FRAUD_THRESHOLD + 0.01) == "FRAUD"


def test_get_risk_label_review():
    assert get_risk_label(settings.REVIEW_THRESHOLD + 0.01) == "REVIEW"


def test_get_risk_label_safe():
    assert get_risk_label(0.1) == "SAFE"


def test_compute_confidence_high_score():
    # Score mendekati 1.0 → confidence tinggi
    conf = compute_confidence(0.95)
    assert conf > 0.7


def test_compute_confidence_ambiguous():
    # Score mendekati 0.5 → confidence rendah
    conf = compute_confidence(0.5)
    assert conf < 0.1


def test_score_summary():
    scores = [0.1, 0.3, 0.6, 0.9, 0.8]
    summary = score_summary(scores)
    assert summary["total"] == 5
    assert summary["fraud_count"] == 2    # 0.9, 0.8 >= 0.75
    assert summary["review_count"] == 1   # 0.6 >= 0.45
    assert summary["safe_count"] == 2


def test_score_summary_empty():
    assert score_summary([]) == {}
