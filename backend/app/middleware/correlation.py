"""
Request Correlation ID Middleware (Phase 7).

Responsibilities:
  - Extract or generate an end-to-end request correlation ID (UUID4).
  - Bind correlation ID to ContextVar and request state.
  - Expose correlation ID in HTTP response header (X-Request-ID).
"""

import contextvars
import uuid
from typing import Optional

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

# ContextVar for logging and async context access
correlation_id_ctx: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    "correlation_id", default=None
)


def get_correlation_id() -> Optional[str]:
    """Return current request correlation ID from context."""
    return correlation_id_ctx.get()


class CorrelationMiddleware(BaseHTTPMiddleware):
    """
    HTTP middleware attaching request correlation IDs.
    """

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        # Check incoming request headers
        incoming_id = (
            request.headers.get("X-Request-ID")
            or request.headers.get("X-Correlation-ID")
        )

        correlation_id = incoming_id if incoming_id else str(uuid.uuid4())

        # Set context variable and request state
        token = correlation_id_ctx.set(correlation_id)
        request.state.correlation_id = correlation_id

        try:
            response = await call_next(request)
            response.headers["X-Request-ID"] = correlation_id
            return response
        finally:
            correlation_id_ctx.reset(token)
