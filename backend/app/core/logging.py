"""
FraudShield — Structured Logging
Outputs JSON in production, human-readable in development.
Integrates with the request correlation ID middleware.
"""

from __future__ import annotations

import logging
import logging.handlers
import sys
from pathlib import Path
from typing import Any

# python-json-logger provides JSON formatting
try:
    from pythonjsonlogger import jsonlogger
    _HAS_JSON_LOGGER = True
except ImportError:
    _HAS_JSON_LOGGER = False

from app.core.config import settings

# ── Custom JSON Formatter ──────────────────────────────────────────────────────

class FraudShieldJSONFormatter(jsonlogger.JsonFormatter if _HAS_JSON_LOGGER else logging.Formatter):
    """Adds standard enterprise fields to every log record."""

    def add_fields(self, log_record: dict, record: logging.LogRecord, message_dict: dict) -> None:
        super().add_fields(log_record, record, message_dict)
        log_record["app"] = settings.APP_NAME
        log_record["version"] = settings.APP_VERSION
        log_record["env"] = settings.APP_ENV
        log_record["level"] = record.levelname
        log_record["logger"] = record.name

        # Attach correlation ID if present (set by middleware)
        correlation_id = getattr(record, "correlation_id", None)
        if correlation_id:
            log_record["correlation_id"] = correlation_id


# ── Setup ──────────────────────────────────────────────────────────────────────

def setup_logging() -> None:
    """Configure application-wide logging. Call once at startup."""
    log_level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)
    use_json = settings.LOG_JSON and _HAS_JSON_LOGGER

    # ── Handlers ──────────────────────────────────────────────────────────────
    handlers: list[logging.Handler] = []

    # Console handler
    console = logging.StreamHandler(sys.stdout)
    console.setLevel(log_level)
    if use_json:
        console.setFormatter(
            FraudShieldJSONFormatter("%(asctime)s %(name)s %(levelname)s %(message)s")
        )
    else:
        console.setFormatter(
            logging.Formatter(
                "%(asctime)s [%(levelname)-8s] %(name)s — %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
        )
    handlers.append(console)

    # Rotating file handler
    try:
        log_path = Path(settings.LOG_FILE)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.handlers.RotatingFileHandler(
            log_path,
            maxBytes=10 * 1024 * 1024,   # 10 MB
            backupCount=5,
            encoding="utf-8",
        )
        file_handler.setLevel(log_level)
        if use_json:
            file_handler.setFormatter(
                FraudShieldJSONFormatter("%(asctime)s %(name)s %(levelname)s %(message)s")
            )
        else:
            file_handler.setFormatter(
                logging.Formatter(
                    "%(asctime)s [%(levelname)-8s] %(name)s — %(message)s",
                    datefmt="%Y-%m-%d %H:%M:%S",
                )
            )
        handlers.append(file_handler)
    except (OSError, PermissionError) as exc:
        print(f"[WARN] Could not create log file handler: {exc}", file=sys.stderr)

    # ── Root logger ────────────────────────────────────────────────────────────
    root = logging.getLogger()
    root.setLevel(log_level)
    root.handlers.clear()
    for h in handlers:
        root.addHandler(h)

    # Quiet noisy third-party loggers
    for noisy in ("sqlalchemy.engine", "asyncpg", "httpx", "uvicorn.access"):
        logging.getLogger(noisy).setLevel(
            logging.DEBUG if settings.DEBUG else logging.WARNING
        )

    logging.getLogger("uvicorn.error").setLevel(logging.ERROR)
    logging.getLogger("fraudshield").setLevel(log_level)


def get_logger(name: str) -> logging.Logger:
    """Convenience factory — use instead of logging.getLogger()."""
    return logging.getLogger(f"fraudshield.{name}")


class LogContext:
    """
    Thread/task-local key-value extras attached to every log record.

    Usage:
        LogContext.set(correlation_id="abc123", user="alice")
        logger.info("Processing")
        LogContext.clear()
    """

    _store: dict[str, Any] = {}

    @classmethod
    def set(cls, **kwargs: Any) -> None:
        cls._store.update(kwargs)

    @classmethod
    def get(cls) -> dict[str, Any]:
        return dict(cls._store)

    @classmethod
    def clear(cls) -> None:
        cls._store.clear()
