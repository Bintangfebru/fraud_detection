"""
FraudShield — Exception Handling Middleware
Catches all unhandled exceptions and converts them to consistent JSON error responses.
Handles both domain FraudShieldError subclasses and unexpected runtime errors.
"""

from __future__ import annotations

import traceback
from typing import Any

from fastapi import Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from app.core.exceptions import FraudShieldError
from app.core.logging import get_logger
from app.middleware.correlation import get_correlation_id

log = get_logger("middleware.exception")


# ── Helpers ───────────────────────────────────────────────────────────────────

def _error_envelope(
    error_code: str,
    message: str,
    detail: Any = None,
    status_code: int = 500,
    correlation_id: str = "",
) -> JSONResponse:
    body: dict[str, Any] = {
        "error": {
            "code": error_code,
            "message": message,
        },
        "correlation_id": correlation_id or get_correlation_id(),
        "status_code": status_code,
    }
    if detail is not None:
        body["error"]["detail"] = detail
    return JSONResponse(status_code=status_code, content=body)


# ── FastAPI exception handlers (registered on the app directly) ───────────────

async def fraudshield_exception_handler(
    request: Request, exc: FraudShieldError
) -> JSONResponse:
    """Handle all domain-specific FraudShield exceptions."""
    log.warning(
        f"Domain exception [{exc.error_code}]: {exc.message}",
        extra={"path": request.url.path, "method": request.method},
    )
    return _error_envelope(
        error_code=exc.error_code,
        message=exc.message,
        detail=exc.detail,
        status_code=exc.http_status,
    )


async def http_exception_handler(
    request: Request, exc: StarletteHTTPException
) -> JSONResponse:
    """Handle FastAPI/Starlette HTTP exceptions (404, 405, 422, etc.)."""
    return _error_envelope(
        error_code="HTTP_ERROR",
        message=str(exc.detail),
        status_code=exc.status_code,
    )


async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """Handle Pydantic v2 request body / query validation failures."""
    errors = []
    for err in exc.errors():
        errors.append(
            {
                "field": " → ".join(str(loc) for loc in err["loc"]),
                "message": err["msg"],
                "type": err["type"],
            }
        )
    log.info(
        f"Validation error on {request.method} {request.url.path}",
        extra={"errors": errors},
    )
    return _error_envelope(
        error_code="VALIDATION_ERROR",
        message="Request validation failed.",
        detail=errors,
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
    )


# ── Catch-all middleware for truly unexpected errors ──────────────────────────

class UnhandledExceptionMiddleware(BaseHTTPMiddleware):
    """
    Last-resort safety net — catches any exception not handled by FastAPI's
    exception handler system (e.g. exceptions raised inside middleware).
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        try:
            return await call_next(request)
        except FraudShieldError as exc:
            # Should already be caught by the exception handler, but just in case
            return _error_envelope(
                error_code=exc.error_code,
                message=exc.message,
                detail=exc.detail,
                status_code=exc.http_status,
            )
        except Exception as exc:
            log.error(
                f"Unhandled exception on {request.method} {request.url.path}: {exc}",
                extra={
                    "traceback": traceback.format_exc(),
                    "correlation_id": get_correlation_id(),
                },
                exc_info=True,
            )
            return _error_envelope(
                error_code="INTERNAL_ERROR",
                message="An unexpected error occurred. Please try again later.",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
