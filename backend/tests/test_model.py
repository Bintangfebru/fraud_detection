"""
FraudShield — Model Tests
Jalankan: pytest tests/test_model.py -v
"""

import pytest
from app.ml.feature_engineering import engineer_features, SELECTED_FEATURES
from app.ml.predictor import predict, model_info
from app.ml.preprocessing import normalize_category, sanitize_amount, mask_cc_num


def test_feature_engineering_output_keys():
    feats = engineer_features(amt=100.0, merchant="Shopee", category="shopping_net", city="Jakarta")
    for key in SELECTED_FEATURES:
        assert key in feats, f"Missing feature: {key}"


def test_category_onehot_shopping_net():
    feats = engineer_features(amt=100.0, merchant="Shopee", category="shopping_net")
    assert feats["category_shopping_net"] == 1
    assert feats["category_food_dining"] == 0


def test_category_onehot_food():
    feats = engineer_features(amt=50.0, merchant="KFC", category="food_dining")
    assert feats["category_food_dining"] == 1
    assert feats["category_shopping_net"] == 0


def test_amt_log_correct():
    import numpy as np
    feats = engineer_features(amt=100.0, merchant="X", category="misc_pos")
    assert abs(feats["amt_log"] - np.log1p(100.0)) < 1e-6


def test_amt_ratio():
    feats = engineer_features(amt=300.0, merchant="X", category="misc_pos", amt_mean_per_card=100.0)
    assert abs(feats["amt_ratio"] - 3.0) < 1e-6


def test_normalize_category_unknown():
    cat = normalize_category("invalid_category_xyz")
    assert cat == "misc_pos"


def test_sanitize_amount_valid():
    assert sanitize_amount(150.5) == 150.5


def test_sanitize_amount_negative():
    with pytest.raises(ValueError):
        sanitize_amount(-10)


def test_mask_cc_num():
    assert mask_cc_num("4111111111111234") == "****1234"
    assert mask_cc_num(None) is None


def test_predict_returns_valid_range():
    feats = engineer_features(amt=200.0, merchant="Test", category="misc_net")
    score, status = predict(feats)
    assert 0.0 <= score <= 1.0
    assert status in ("SAFE", "REVIEW", "FRAUD")


def test_model_info_keys():
    info = model_info()
    assert "loaded" in info
    assert "selected_features" in info
    assert "thresholds" in info
