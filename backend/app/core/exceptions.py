"""
FraudShield — Custom Exceptions
Defines all domain-specific exceptions and their HTTP mappings.
"""

from __future__ import annotations

from typing import Any, Optional


# ── Base ──────────────────────────────────────────────────────────────────────

class FraudShieldError(Exception):
    """Base for all FraudShield exceptions."""

    http_status: int = 500
    error_code: str = "INTERNAL_ERROR"
    message: str = "An unexpected error occurred."

    def __init__(
        self,
        message: Optional[str] = None,
        detail: Optional[Any] = None,
        error_code: Optional[str] = None,
    ) -> None:
        self.message = message or self.__class__.message
        self.detail = detail
        if error_code:
            self.error_code = error_code
        super().__init__(self.message)


# ── Auth & Authorization ──────────────────────────────────────────────────────

class AuthenticationError(FraudShieldError):
    http_status = 401
    error_code = "AUTHENTICATION_FAILED"
    message = "Authentication required."


class InvalidTokenError(FraudShieldError):
    http_status = 401
    error_code = "INVALID_TOKEN"
    message = "Token is invalid or expired."


class ExpiredTokenError(FraudShieldError):
    http_status = 401
    error_code = "TOKEN_EXPIRED"
    message = "Token has expired."


class PermissionDeniedError(FraudShieldError):
    http_status = 403
    error_code = "PERMISSION_DENIED"
    message = "You do not have permission to perform this action."


class InactiveUserError(FraudShieldError):
    http_status = 403
    error_code = "ACCOUNT_INACTIVE"
    message = "Account is deactivated."


# ── Resource ──────────────────────────────────────────────────────────────────

class NotFoundError(FraudShieldError):
    http_status = 404
    error_code = "NOT_FOUND"
    message = "Resource not found."


class ConflictError(FraudShieldError):
    http_status = 409
    error_code = "CONFLICT"
    message = "Resource already exists."


# ── Validation ────────────────────────────────────────────────────────────────

class ValidationError(FraudShieldError):
    http_status = 422
    error_code = "VALIDATION_ERROR"
    message = "Input validation failed."


class InvalidThresholdError(FraudShieldError):
    http_status = 400
    error_code = "INVALID_THRESHOLD"
    message = "Review threshold must be less than fraud threshold."


# ── Rate Limiting ─────────────────────────────────────────────────────────────

class RateLimitExceededError(FraudShieldError):
    http_status = 429
    error_code = "RATE_LIMIT_EXCEEDED"
    message = "Too many requests. Please slow down."


# ── ML / Prediction ───────────────────────────────────────────────────────────

class PredictionError(FraudShieldError):
    http_status = 500
    error_code = "PREDICTION_FAILED"
    message = "Fraud prediction pipeline failed."


class ModelNotLoadedError(FraudShieldError):
    http_status = 503
    error_code = "MODEL_NOT_LOADED"
    message = "ML model is not loaded. Service degraded."


# ── Database ──────────────────────────────────────────────────────────────────

class DatabaseError(FraudShieldError):
    http_status = 503
    error_code = "DATABASE_ERROR"
    message = "Database operation failed."


# ── Training Jobs ─────────────────────────────────────────────────────────────

class TrainingJobError(FraudShieldError):
    http_status = 500
    error_code = "TRAINING_JOB_ERROR"
    message = "Training job encountered an error."


class JobNotFoundError(FraudShieldError):
    http_status = 404
    error_code = "JOB_NOT_FOUND"
    message = "Training job not found."
