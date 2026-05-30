#!/bin/bash
# Backend Startup Script

set -e
cd "$(dirname "$0")"

# Check Python
if ! command -v python3 &>/dev/null; then
    echo "ERROR: Python 3 tidak ditemukan."
    exit 1
fi

# Create virtual environment if not exists
if [ ! -d "venv" ]; then
    echo "[1/4] Creating virtual environment..."
    python3 -m venv venv
fi

# Activate venv
source venv/bin/activate

# Install dependencies
echo "[2/4] Installing dependencies..."
pip install -q -r requirements.txt

# Check .env file
if [ ! -f ".env" ]; then
    echo "[WARN] .env tidak ditemukan, menyalin dari env..."
    cp env .env
fi

# Check model file
MODEL_PATH="trained_models/fraud_pipeline.pkl"
if [ ! -f "$MODEL_PATH" ]; then
    echo "[WARN] Model tidak ditemukan di $MODEL_PATH"
    echo "       Akan menggunakan fallback heuristic scoring."
fi

# Start server
echo "[3/4] Starting FastAPI server..."
echo "  URL: http://127.0.0.1:8000"
echo "  Docs: http://127.0.0.1:8000/docs"
echo ""
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
