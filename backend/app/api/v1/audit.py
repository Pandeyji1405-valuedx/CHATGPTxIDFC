"""
Audit Log API Router (Phase 7).

Endpoints:
  GET /api/v1/audit/logs — Paginated audit trail for enterprise governance.

Security & Authorization:
  - Admin-only access enforced server-side via require_role(UserRole.ADMIN).
  - Unauthenticated access returns 401; non-admin users return 403.
"""

import uuid
import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import require_role
from app.db.session import get_db
from app.models.user import User, UserRole
from app.schemas.audit import AuditLogListResponse, AuditLogResponse
from app.services.security.audit_service import AuditService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/audit", tags=["Audit Logs"])


@router.get(
    "/logs",
    response_model=AuditLogListResponse,
    status_code=status.HTTP_200_OK,
    summary="Query audit logs (Admin only).",
)
async def list_audit_logs(
    actor_id: Optional[uuid.UUID] = Query(None, description="Filter by actor user UUID"),
    action: Optional[str] = Query(None, description="Filter by event action type"),
    outcome: Optional[str] = Query(None, description="Filter by outcome (SUCCESS, FAILURE, DENIED)"),
    start_time: Optional[datetime] = Query(None, description="Filter by ISO start timestamp"),
    end_time: Optional[datetime] = Query(None, description="Filter by ISO end timestamp"),
    limit: int = Query(50, ge=1, le=100, description="Items per page"),
    offset: int = Query(0, ge=0, description="Page offset"),
    admin_user: User = Depends(require_role(UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
) -> AuditLogListResponse:
    """
    Retrieve paginated audit logs. Only accessible by ADMIN users.
    """
    tenant_id = getattr(admin_user, "tenant_id", "idfc_bank")

    items, total = await AuditService.get_audit_logs(
        db=db,
        tenant_id=tenant_id,
        actor_id=actor_id,
        action=action,
        outcome=outcome,
        start_time=start_time,
        end_time=end_time,
        limit=limit,
        offset=offset,
    )

    return AuditLogListResponse(
        items=[AuditLogResponse.model_validate(item) for item in items],
        total=total,
        limit=limit,
        offset=offset,
    )
