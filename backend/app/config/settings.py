"""
FraudShield — Application Settings
Semua konfigurasi dibaca dari environment variables / .env
"""
from typing import Optional, List
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # ── App ──────────────────────────────────────────────────
    APP_NAME: str = "FraudShield"
    APP_VERSION: str = "2.4.1"
    DEBUG: bool = False
    SECRET_KEY: str = "change-me-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    # ── Database ─────────────────────────────────────────────
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_DB: str = "fraudshield"
    POSTGRES_USER: str = "fraudshield_user"
    POSTGRES_PASSWORD: str = "postgres"

    DATABASE_URL: Optional[str] = None

    @property
    def database_url(self) -> str:
        if self.DATABASE_URL:
            return self.DATABASE_URL
        return (
            f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    @property
    def DATABASE_URL_SYNC(self) -> str:
        return (
            f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    # ── Redis ─────────────────────────────────────────────────
    REDIS_URL: str = "redis://localhost:6379/0"

    # ── ML Model ──────────────────────────────────────────────
    MODEL_PATH: str = "trained_models/fraud_pipeline.pkl"
    FRAUD_THRESHOLD: float = 0.75
    REVIEW_THRESHOLD: float = 0.45

    SELECTED_FEATURES: List[str] = [
        "amt", "hour", "month", "amt_log",
        "amt_mean_per_card", "amt_ratio", "txn_count_per_card",
        "unique_merchants", "unique_categories", "amt_std_per_card",
        "category_food_dining", "category_gas_transport", "category_grocery_pos",
        "category_kids_pets", "category_misc_net", "category_misc_pos",
        "category_personal_care", "category_shopping_net",
        "merchant", "city",
    ]

    # ── CORS ──────────────────────────────────────────────────
    ALLOWED_ORIGINS_STR: str = "http://localhost:3000,http://localhost:8080,http://127.0.0.1:8080"

    @property
    def ALLOWED_ORIGINS(self) -> List[str]:
        return [o.strip() for o in self.ALLOWED_ORIGINS_STR.split(",") if o.strip()]

    # ── Logging ───────────────────────────────────────────────
    LOG_LEVEL: str = "INFO"
    LOG_FILE: str = "logs/fraudshield.log"

    # ── Rate Limiting ─────────────────────────────────────────
    RATE_LIMIT_AUTH: int = 10
    RATE_LIMIT_PREDICT: int = 60

    # ── Real-Time Streaming ───────────────────────────────────
    KAFKA_ENABLED: bool = False
    KAFKA_BOOTSTRAP_SERVERS: str = "localhost:9092"
    KAFKA_CONSUMER_GROUP: str = "fraudshield-consumers"
    WS_HEARTBEAT_INTERVAL: int = 30
    METRICS_PUBLISH_INTERVAL: float = 5.0

    class Config:
        env_file = ".env"
        case_sensitive = True
        extra = "ignore"


settings = Settings()