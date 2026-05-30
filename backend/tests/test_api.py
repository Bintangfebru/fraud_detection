"""
FraudShield API Tests
Jalankan: pytest tests/test_api.py -v
"""

import pytest
from httpx import AsyncClient, ASGITransport
from main import app


@pytest.fixture
async def client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


@pytest.mark.asyncio
async def test_health(client):
    resp = await client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] in ("ok", "degraded")


@pytest.mark.asyncio
async def test_predict_valid(client):
    payload = {
        "amt": 150.00,
        "merchant": "Test Merchant",
        "category": "shopping_net",
        "city": "Jakarta",
        "trans_date_trans_time": "2024-06-15T14:00:00",
    }
    resp = await client.post("/v1/predict", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert "risk_score" in data
    assert data["status"] in ("SAFE", "REVIEW", "FRAUD")
    assert 0.0 <= data["risk_score"] <= 1.0


@pytest.mark.asyncio
async def test_predict_invalid_amount(client):
    payload = {"amt": -50, "merchant": "Bad", "category": "misc_pos"}
    resp = await client.post("/v1/predict", json=payload)
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_batch_predict(client):
    payload = {
        "transactions": [
            {"amt": 50.0, "merchant": "Coffee Shop", "category": "food_dining"},
            {"amt": 3500.0, "merchant": "Unknown Store", "category": "misc_net"},
        ]
    }
    resp = await client.post("/v1/predict/batch", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 2
    assert len(data["results"]) == 2


@pytest.mark.asyncio
async def test_model_status(client):
    resp = await client.get("/v1/model/status")
    assert resp.status_code == 200
    data = resp.json()
    assert "selected_features" in data
    assert "thresholds" in data
