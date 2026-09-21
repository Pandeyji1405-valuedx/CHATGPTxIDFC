"""
Pydantic schemas for API health responses.
"""

from datetime import datetime, timezone

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    """Response schema for the health-check endpoint."""

    status: str = Field(..., description="Application status: 'ok' or 'error'")
    app_name: str = Field(..., description="Application name")
    version: str = Field(..., description="Application version")
    environment: str = Field(..., description="Deployment environment")
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="UTC timestamp of the health response",
    )

    model_config = {"json_schema_extra": {"example": {
        "status": "ok",
        "app_name": "IDFC RBI Compliance Chatbot",
        "version": "0.1.0",
        "environment": "development",
        "timestamp": "<runtime-generated timestamp>",
    }}}
