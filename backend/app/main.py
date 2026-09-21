"""
IDFC RBI Compliance Chatbot — FastAPI Application Entrypoint
Phase 2: Authentication added

This module constructs and configures the FastAPI application instance.
All route registration, middleware, and lifecycle events are wired here.
"""

import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.v1 import health as health_router
from app.api.v1 import auth as auth_router
from app.api.v1 import documents as documents_router
from app.api.v1 import chat as chat_router
from app.api.v1 import feedback as feedback_router
from app.api.v1 import audit as audit_router
from app.middleware.correlation import CorrelationMiddleware
from app.core.config import get_settings

# ------------------------------------------------------------------ #
# Logging
# ------------------------------------------------------------------ #
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
logger = logging.getLogger(__name__)

settings = get_settings()


# ------------------------------------------------------------------ #
# Application Lifecycle
# ------------------------------------------------------------------ #
@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Application lifespan context manager.

    Runs startup logic before yielding and teardown logic after.
    Currently only logs startup/shutdown events.

    Phase 2+: Initialize database connection pool, Redis, etc. here.
    """
    logger.info(
        "Starting %s v%s [env=%s]",
        settings.APP_NAME,
        settings.APP_VERSION,
        settings.APP_ENV,
    )
    yield
    logger.info("Shutting down %s", settings.APP_NAME)


# ------------------------------------------------------------------ #
# Application Factory
# ------------------------------------------------------------------ #
def create_application() -> FastAPI:
    """
    Construct and configure the FastAPI application.

    Separating construction into a factory function makes it easy
    to create isolated app instances for testing.
    """
    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        description=(
            "Internal IDFC Bank regulatory chatbot API. "
            "Phase 7: Governance, Security, Audit & Feedback."
        ),
        docs_url="/api/docs" if not settings.is_production else None,
        redoc_url="/api/redoc" if not settings.is_production else None,
        openapi_url="/api/openapi.json" if not settings.is_production else None,
        lifespan=lifespan,
    )

    # ---------------------------------------------------------------- #
    # Middleware
    # ---------------------------------------------------------------- #
    app.add_middleware(CorrelationMiddleware)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ---------------------------------------------------------------- #
    # Exception Handlers
    # ---------------------------------------------------------------- #
    @app.exception_handler(Exception)
    async def generic_exception_handler(
        request: Request, exc: Exception
    ) -> JSONResponse:
        """
        Catch-all exception handler.

        Returns a structured JSON error response instead of an unhandled
        500 traceback. Never exposes internal error details in production.
        """
        logger.exception("Unhandled exception on %s %s", request.method, request.url)
        detail = str(exc) if settings.DEBUG else "An internal error occurred."
        return JSONResponse(
            status_code=500,
            content={"detail": detail, "status": "error"},
        )

    # ---------------------------------------------------------------- #
    # Routers
    # ---------------------------------------------------------------- #
    app.include_router(
        health_router.router,
        prefix="/api/v1",
    )

    app.include_router(
        auth_router.router,
        prefix="/api/v1",
    )

    app.include_router(
        documents_router.router,
        prefix="/api/v1",
    )

    app.include_router(
        chat_router.router,
        prefix="/api/v1",
    )

    app.include_router(
        feedback_router.router,
        prefix="/api/v1",
    )

    app.include_router(
        audit_router.router,
        prefix="/api/v1",
    )

    return app


# ------------------------------------------------------------------ #
# Application Instance
# ------------------------------------------------------------------ #
app: FastAPI = create_application()
