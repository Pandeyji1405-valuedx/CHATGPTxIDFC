"""
Audit Logging Service (Phase 7).

Responsibilities:
  - Persist immutable audit records to PostgreSQL for enterprise governance.
  - Automatically sanitize all log details via PIIService.
  - Expose admin-only audit trail query API.
  - Fail-safe execution: audit errors log a warning without throwing unexpected exceptions.
"""

import logging
import uuid
from datetime import datetime
from typing import Dict, List, Optional, Tuple

from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import AuditLog
from app.services.security.pii_service import PIIService

logger = logging.getLogger(__name__)


class AuditService:
    """
    Service for writing and reading immutable audit log events.
    """

    @staticmethod
    async def log_event(
        db: AsyncSession,
        action: str,
        resource_type: str,
        outcome: str,
        tenant_id: str = "idfc_bank",
        actor_id: Optional[uuid.UUID] = None,
        resource_id: Optional[str] = None,
        correlation_id: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        details: Optional[Dict] = None,
    ) -> Optional[AuditLog]:
        """
        Record an audit log entry in PostgreSQL.

        Args:
            db: Async database session. Caller or local commit.
            action: Action event category (e.g. 'auth.login.success').
            resource_type: Target category (e.g. 'user', 'document', 'chat_message').
            outcome: Outcome string ('SUCCESS', 'FAILURE', 'DENIED', 'REJECTED').
            tenant_id: Tenant identifier.
            actor_id: Optional user UUID.
            resource_id: Target resource ID.
            correlation_id: Request correlation ID.
            ip_address: Client IP.
            user_agent: HTTP User-Agent.
            details: Unsanitized metadata dict (sanitized automatically).

        Returns:
            The created AuditLog instance, or None if creation failed non-fatally.
        """
        try:
            # Automatically sanitize metadata dictionary
            sanitized_details = (
                PIIService.sanitize_dict(details) if details else None
            )

            log_entry = AuditLog(
                id=uuid.uuid4(),
                tenant_id=tenant_id,
                actor_id=actor_id,
                action=action,
                resource_type=resource_type,
                resource_id=str(resource_id) if resource_id else None,
                outcome=outcome,
                correlation_id=correlation_id,
                ip_address=ip_address,
                user_agent=user_agent,
                details=sanitized_details,
            )
            db.add(log_entry)
            await db.flush()

            logger.info(
                "Audit log recorded: action=%s outcome=%s actor=%s resource=%s/%s tenant=%s",
                action,
                outcome,
                actor_id,
                resource_type,
                resource_id,
                tenant_id,
            )
            return log_entry
        except Exception as exc:
            logger.warning("Failed to record audit log event: %s", exc)
            return None

    @staticmethod
    async def get_audit_logs(
        db: AsyncSession,
        tenant_id: str = "idfc_bank",
        actor_id: Optional[uuid.UUID] = None,
        action: Optional[str] = None,
        outcome: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Tuple[List[AuditLog], int]:
        """
        Retrieve paginated audit logs for admin audit trail viewing.

        Args:
            db: Async database session.
            tenant_id: Filter by tenant.
            actor_id: Optional user filter.
            action: Optional action pattern/filter.
            outcome: Optional outcome filter.
            start_time: Start timestamp bound.
            end_time: End timestamp bound.
            limit: Page limit (default 50, max 100).
            offset: Page offset.

        Returns:
            Tuple of (list of AuditLog records, total matching count).
        """
        limit = min(max(1, limit), 100)

        conditions = [AuditLog.tenant_id == tenant_id]

        if actor_id:
            conditions.append(AuditLog.actor_id == actor_id)
        if action:
            conditions.append(AuditLog.action == action)
        if outcome:
            conditions.append(AuditLog.outcome == outcome)
        if start_time:
            conditions.append(AuditLog.timestamp >= start_time)
        if end_time:
            conditions.append(AuditLog.timestamp <= end_time)

        # Count total
        count_stmt = select(func.count(AuditLog.id)).where(*conditions)
        total_res = await db.execute(count_stmt)
        total = total_res.scalar_one()

        # Query items
        stmt = (
            select(AuditLog)
            .where(*conditions)
            .order_by(desc(AuditLog.timestamp))
            .limit(limit)
            .offset(offset)
        )
        res = await db.execute(stmt)
        items = res.scalars().all()

        return list(items), total
