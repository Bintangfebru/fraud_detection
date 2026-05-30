# FraudShield — Backend API

## Quickstart

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Taruh model kamu
cp /path/to/model.pkl ./model.pkl

# 3. Jalankan server
uvicorn main:app --reload --port 8000

# 4. Swagger UI
open http://localhost:8000/docs
```

---

## Endpoints

| Method | Path                  | Deskripsi                          |
|--------|-----------------------|------------------------------------|
| GET    | /                     | Health check + model info          |
| GET    | /health               | Status operasional                 |
| POST   | /v1/predict           | Predict 1 transaksi                |
| POST   | /v1/predict/batch     | Predict batch (max 500)            |
| GET    | /v1/model/status      | Info model aktif + feature order   |

---

## Urutan Feature

Di `main.py`, sesuaikan `FEATURE_ORDER` dengan urutan kolom saat training:

```python
FEATURE_ORDER = [
    "amt", "category_enc", "city_pop",
    "hour", "day_of_week", "month",
    "is_night", "is_weekend", "age",
    "city_pop_log", "gender_enc",
    "distance_to_merch", "is_far_from_home",
    "amt_log", "is_round_amount",
]
```

Jika urutan beda dari waktu training, model akan return hasil yang salah.

Cara cek urutan dari model sklearn/XGBoost:
```python
import joblib
model = joblib.load("model.pkl")
print(model.feature_names_in_)   
```

---

## Koneksi ke Frontend

Di `submit.html` FraudShield, ganti bagian `generateResult()`:

```javascript
async function runAssessment() {
  const res = await fetch('http://localhost:8000/v1/predict', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      amt:                   parseFloat(document.getElementById('amount').value),
      merchant:              document.getElementById('merchant').value,
      category:              document.getElementById('category').value,
      trans_date_trans_time: document.getElementById('txnTime').value,
      merch_lat:             parseFloat(document.getElementById('merchLat').value) || null,
      merch_long:            parseFloat(document.getElementById('merchLong').value) || null,
    })
  });
  const { risk_score, status, transaction_id, features_used } = await res.json();

}
```
