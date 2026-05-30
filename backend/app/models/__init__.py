"""
FraudShield — Model Registry
Import all ORM models here so SQLAlchemy Base.metadata is fully populated.
Required by Alembic env.py and app/db/init_db.py.
"""

from app.models.user import User
from app.models.transaction import Transaction
from app.models.prediction import FraudPrediction, Alert, AuditLog
from app.models.ml_models import ModelRegistry, Threshold, TrainingJob

__all__ = [
    "User",
    "Transaction",
    "FraudPrediction",
    "Alert",
    "AuditLog",
    "ModelRegistry",
    "Threshold",
    "TrainingJob",
]
