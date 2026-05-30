"""
FraudShield — Preprocessing
Normalisasi dan validasi input sebelum feature engineering.
"""

import re
from datetime import datetime
from typing import Optional
import logging

log = logging.getLogger("fraudshield.preprocessing")

VALID_CATEGORIES = [
    "entertainment", "food_dining", "gas_transport", "grocery_net",
    "grocery_pos", "health_fitness", "home", "kids_pets",
    "misc_net", "misc_pos", "personal_care", "shopping_net",
    "shopping_pos", "travel",
]


def normalize_category(raw: str) -> str:
    """Normalisasi string kategori ke format lowercase_underscore."""
    norm = raw.strip().lower().replace(" ", "_").replace("-", "_")
    if norm not in VALID_CATEGORIES:
        log.warning(f"Unknown category '{raw}' → fallback ke 'misc_pos'")
        return "misc_pos"
    return norm


def normalize_merchant(raw: str) -> str:
    """Bersihkan nama merchant."""
    return re.sub(r"\s+", " ", raw.strip())[:255]


def parse_datetime(raw: Optional[str]) -> Optional[datetime]:
    """Parse datetime string dengan berbagai format."""
    if not raw:
        return None
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S",
                "%d/%m/%Y %H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(raw, fmt)
        except ValueError:
            continue
    log.warning(f"Tidak bisa parse datetime: '{raw}' → pakai now()")
    return datetime.now()


def sanitize_amount(amt: float) -> float:
    """Pastikan amount positif dan finite."""
    if not isinstance(amt, (int, float)) or amt < 0 or not (amt == amt):
        raise ValueError(f"Amount tidak valid: {amt}")
    return float(amt)


def mask_cc_num(cc_num: Optional[str]) -> Optional[str]:
    """Simpan hanya 4 digit terakhir untuk keamanan."""
    if not cc_num:
        return None
    clean = re.sub(r"\D", "", str(cc_num))
    return f"****{clean[-4:]}" if len(clean) >= 4 else "****"
