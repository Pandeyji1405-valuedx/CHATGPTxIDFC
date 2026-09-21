"""
Health-check router.

Provides a single endpoint for verifying that the FastAPI application
is running and reachable. Suitable for use by:
  - Load balancers
  - Container orchestrators (Kubernetes liveness/readiness probes)
  - Frontend connectivity checks

Endpoint: GET /api/v1/health
"""

from datetime import datetime, timezone

from fastapi import APIRouter

from app.core.config import get_settings
from app.schemas.health import HealthResponse

router = APIRouter(prefix="/health", tags=["Health"])

settings = get_settings()


@router.get(
    "",
    response_model=HealthResponse,
    summary="Application health check",
    description=(
        "Returns the current application status, version, and environment. "
        "A 200 response indicates the application is running correctly."
    ),
)
async def health_check() -> HealthResponse:
    """
    Return application health status.

    This endpoint does not check database connectivity in Phase 1.
    Database health checks will be added in a later phase.
    """
    return HealthResponse(
        status="ok",
        app_name=settings.APP_NAME,
        version=settings.APP_VERSION,
        environment=settings.APP_ENV,
        timestamp=datetime.now(timezone.utc),
    )
