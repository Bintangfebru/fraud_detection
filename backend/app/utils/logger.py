"""FraudShield — Structured Logger"""

import logging
import sys
import os
from app.config.settings import settings


def setup_logging():
    log_level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)

    formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s — %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    handlers = [logging.StreamHandler(sys.stdout)]

    log_dir = os.path.dirname(settings.LOG_FILE)
    if log_dir:
        os.makedirs(log_dir, exist_ok=True)
        handlers.append(logging.FileHandler(settings.LOG_FILE))

    logging.basicConfig(level=log_level, handlers=handlers)
    for handler in logging.root.handlers:
        handler.setFormatter(formatter)

    # Suppress noisy libs
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
