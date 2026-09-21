"""
Pydantic schemas for Audit Logging (Phase 7).
"""

import uuid
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class AuditLogResponse(BaseModel):
    """Response payload for an audit log entry."""

    id: uuid.UUID
    timestamp: datetime
    tenant_id: str
    actor_id: Optional[uuid.UUID] = None
    action: str
    resource_type: str
    resource_id: Optional[str] = None
    outcome: str
    correlation_id: Optional[str] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    details: Optional[dict] = None

    model_config = {"from_attributes": True}


class AuditLogListResponse(BaseModel):
    """Paginated list response for audit logs."""

    items: List[AuditLogResponse]
    total: int
    limit: int
    offset: int
