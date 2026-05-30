# FraudShield — Setup & Running Guide

## Struktur Folder
```
fraudshield/
├── backend/               ← FastAPI server (Python)
│   ├── main.py            ← Entry point
│   ├── .env               ← Environment variables
│   ├── requirements.txt   ← Python dependencies
│   ├── start.sh           ← Startup script
│   ├── trained_models/    ← ML model (fraud_pipeline.pkl)
│   ├── app/
│   │   ├── config/        ← Database & settings
│   │   ├── ml/            ← Feature engineering & predictor
│   │   ├── models/        ← Pydantic schemas
│   │   ├── routes/        ← API endpoints
│   │   └── services/      ← Business logic
│   └── scripts/
│       └── init_db.sql    ← PostgreSQL setup
└── front end/             ← Static HTML/CSS/JS
    ├── pages/             ← All HTML pages
    └── assets/
        ├── css/           ← Stylesheets
        └── js/            ← JavaScript modules
```

## Cara Menjalankan

### 1. Setup PostgreSQL (Opsional)
Tanpa PostgreSQL, backend tetap berjalan dengan mode fallback (data di-reset tiap restart).

```bash
# Install PostgreSQL jika belum ada
# Ubuntu/Debian:
sudo apt-get install postgresql postgresql-contrib

# macOS:
brew install postgresql

# Setup database:
sudo -u postgres psql -f backend/scripts/init_db.sql
```

Edit `backend/.env` dan sesuaikan password:
```
POSTGRES_PASSWORD=fraudshield_pass
```

### 2. Jalankan Backend
```bash
cd backend

# Cara 1 - Pakai start.sh (otomatis buat venv & install deps):
chmod +x start.sh
./start.sh

# Cara 2 - Manual:
python3 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

Backend tersedia di: **http://127.0.0.1:8000**
Swagger UI: **http://127.0.0.1:8000/docs**

### 3. Jalankan Frontend
Buka file HTML langsung di browser, atau gunakan local server:

```bash
# Python simple server (dari folder fraudshield/front end):
cd "front end"
python3 -m http.server 8080

# Node.js live-server:
npx live-server --port=8080 --open=pages/index.html
```

Buka: **http://localhost:8080/pages/index.html**

## API Endpoints

| Method | Endpoint | Deskripsi |
|--------|----------|-----------|
| GET | /health | Health check |
| GET | /v1/model/status | Status model ML |
| POST | /v1/predict | Prediksi 1 transaksi |
| POST | /v1/predict/batch | Prediksi batch (max 500) |
| GET | /v1/transactions | List transaksi |
| GET | /v1/analytics/summary | Ringkasan statistik |
| GET | /v1/analytics/fraud-rate | Trend fraud rate |
| POST | /auth/login | Login (JWT) |

## Troubleshooting

**CORS Error**: Pastikan backend berjalan di port 8000. CORS sudah dikonfigurasi untuk allow all origins.


**DB connection failed**: Backend akan tetap berjalan tanpa DB. Hanya endpoint yang membutuhkan DB (transaksi history, analytics real) yang tidak tersedia.
