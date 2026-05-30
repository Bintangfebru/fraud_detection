from __future__ import annotations

from functools import lru_cache
from typing import List, Optional

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # ── Application ─────────────────────────────────────────
    APP_NAME: str = "FraudShield"
    APP_VERSION: str = "2.5.0"
    APP_ENV: str = "development"
    DEBUG: bool = False

    # ── Security ────────────────────────────────────────────
    SECRET_KEY: str = "change-me-in-production-at-least-32-chars"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # ── PostgreSQL ──────────────────────────────────────────
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_DB: str = "fraudshield"
    POSTGRES_USER: str = "fraudshield_user"
    POSTGRES_PASSWORD: str = "fraudshield_pass"
    DATABASE_URL: Optional[str] = None

    DB_POOL_SIZE: int = 10
    DB_MAX_OVERFLOW: int = 20
    DB_POOL_PRE_PING: bool = True
    DB_ECHO: bool = False

    @property
    def database_url_async(self) -> str:
        if self.DATABASE_URL:
            return self.DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://")
        return (
            f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    @property
    def database_url_sync(self) -> str:
        if self.DATABASE_URL:
            return self.DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")
        return (
            f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    # ── Redis ───────────────────────────────────────────────
    REDIS_URL: str = "redis://localhost:6379/0"
    REDIS_MAX_CONNECTIONS: int = 20
    REDIS_SOCKET_TIMEOUT: float = 5.0

    RATE_LIMIT_REQUESTS: int = 100
    RATE_LIMIT_WINDOW_SECONDS: int = 60
    RATE_LIMIT_PREDICT: int = 60
    RATE_LIMIT_AUTH: int = 10

    # ── ML Model ────────────────────────────────────────────
    MODEL_PATH: str = "trained_models/fraud_pipeline.pkl"
    FRAUD_THRESHOLD: float = 0.75
    REVIEW_THRESHOLD: float = 0.45

    SELECTED_FEATURES: List[str] = [
        "amt","hour","month","amt_log",
        "amt_mean_per_card","amt_ratio","txn_count_per_card",
        "unique_merchants","unique_categories","amt_std_per_card",
        "category_food_dining","category_gas_transport","category_grocery_pos",
        "category_kids_pets","category_misc_net","category_misc_pos",
        "category_personal_care","category_shopping_net",
        "merchant","city",
    ]

    # ── CORS ────────────────────────────────────────────────
    ALLOWED_ORIGINS_STR: str = (
        "http://localhost:3000,http://localhost:8080,"
        "http://127.0.0.1:8080,http://localhost:5500,"
        "http://127.0.0.1:5500,"
        "http://localhost:5173,"
        "http://127.0.0.1:5173"
    )

    @property
    def ALLOWED_ORIGINS(self) -> List[str]:
        return [o.strip() for o in self.ALLOWED_ORIGINS_STR.split(",") if o.strip()]

    # ── Logging ─────────────────────────────────────────────
    LOG_LEVEL: str = "INFO"
    LOG_FILE: str = "logs/fraudshield.log"
    LOG_JSON: bool = True

    # ── Pagination (FIX ERROR DI SINI) ───────────────────────
    DEFAULT_PAGE_SIZE: int = 50
    MAX_PAGE_SIZE: int = 200

    # ── Other ───────────────────────────────────────────────
    TRAINING_JOB_TTL_HOURS: int = 24

    KAFKA_ENABLED: bool = False
    KAFKA_BOOTSTRAP_SERVERS: str = "localhost:9092"
    KAFKA_CONSUMER_GROUP: str = "fraudshield-consumers"

    WS_HEARTBEAT_INTERVAL: int = 30
    METRICS_PUBLISH_INTERVAL: float = 5.0

    @field_validator("APP_ENV")
    @classmethod
    def validate_env(cls, v: str) -> str:
        if v not in {"development", "staging", "production"}:
            raise ValueError("Invalid APP_ENV")
        return v

    @model_validator(mode="after")
    def validate_thresholds(self):
        if self.REVIEW_THRESHOLD >= self.FRAUD_THRESHOLD:
            raise ValueError("REVIEW_THRESHOLD must be less than FRAUD_THRESHOLD")
        return self

    @property
    def is_production(self) -> bool:
        return self.APP_ENV == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()