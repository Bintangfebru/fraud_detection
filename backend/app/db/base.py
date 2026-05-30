"""
FraudShield — SQLAlchemy Declarative Base
Shared by all ORM models and Alembic migrations.
"""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """All ORM models inherit from this base."""
    pass
