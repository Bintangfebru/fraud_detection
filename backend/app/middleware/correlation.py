"""
FraudShield — Correlation ID Middleware
Attaches a unique X-Correlation-ID header to every request and response.
Used for distributed tracing and log correlation across services.
"""

from __future__ import annotations

import uuid
import logging
from contextvars import ContextVar

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

# Context variable — safe for async; each task gets its own copy
_correlation_id_var: ContextVar[str] = ContextVar("correlation_id", default="")

HEADER_NAME = "X-Correlation-ID"


def get_correlation_id() -> str:
    """Return the correlation ID for the current request context."""
    return _correlation_id_var.get()


class CorrelationIDMiddleware(BaseHTTPMiddleware):
    """
    Reads X-Correlation-ID from the incoming request (or generates one),
    stores it in a context var, and echoes it back in the response header.

    Every log record emitted inside the request lifecycle can call
    get_correlation_id() to attach the same ID for traceability.
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        # Accept from client (e.g. API gateway forwards it) or generate fresh
        correlation_id = (
            request.headers.get(HEADER_NAME)
            or f"fs-{uuid.uuid4().hex[:16]}"
        )

        # Bind to context so all code in this async task can read it
        token = _correlation_id_var.set(correlation_id)

        # Attach to request state for easy access in route handlers
        request.state.correlation_id = correlation_id

        # Inject into logging records via a filter
        _inject_log_filter(correlation_id)

        try:
            response: Response = await call_next(request)
        finally:
            _correlation_id_var.reset(token)

        response.headers[HEADER_NAME] = correlation_id
        return response


# ── Logging integration ────────────────────────────────────────────────────────

class _CorrelationFilter(logging.Filter):
    """Injects correlation_id into every LogRecord."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.correlation_id = get_correlation_id()  # type: ignore[attr-defined]
        return True


_filter_instance = _CorrelationFilter()
_filter_installed = False


def _inject_log_filter(correlation_id: str) -> None:
    """Install the filter once on the root logger."""
    global _filter_installed
    if not _filter_installed:
        logging.getLogger().addFilter(_filter_instance)
        _filter_installed = True
