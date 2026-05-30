from sqlalchemy import create_engine

DATABASE_URL = "postgresql://fraudshield_user:fraudshield_pass@localhost:5432/fraudshield"

try:
    engine = create_engine(DATABASE_URL)
    conn = engine.connect()
    print("✅ Connected to PostgreSQL!")
    conn.close()
except Exception as e:
    print("❌ Connection failed:", e)