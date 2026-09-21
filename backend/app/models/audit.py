"""
Audit Log ORM model (Phase 7).

Persists immutable audit events for enterprise governance, traceability,
and regulatory compliance.

Key design decisions:
  - Immutable append-only log.
  - Indexed by tenant_id, actor_id, action, resource_type, correlation_id, timestamp.
  - Sanitized metadata stored in details (JSONB). No secrets, passwords, or raw PII.
"""

import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy import JSON as JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class AuditLog(Base):
    """
    An immutable audit log event record.
    """

    __tablename__ = "audit_logs"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
        index=True,
        comment="UUID primary key.",
    )

    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        index=True,
        comment="UTC timestamp of the audited event.",
    )

    tenant_id: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
        default="idfc_bank",
        server_default="idfc_bank",
        comment="Tenant identifier for multi-tenant isolation.",
    )

    actor_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="User ID who initiated the event (null for unauthenticated actions).",
    )

    action: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
        comment="Action event type (e.g. auth.login.success, document.upload, chat.request).",
    )

    resource_type: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
        comment="Target resource category (e.g. user, document, cache_answer, chat_message).",
    )

    resource_id: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        index=True,
        comment="Specific resource identifier.",
    )

    outcome: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
        comment="Event outcome: SUCCESS, FAILURE, DENIED, REJECTED.",
    )

    correlation_id: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        index=True,
        comment="Request correlation ID for end-to-end tracing.",
    )

    ip_address: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        comment="Client IP address.",
    )

    user_agent: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        comment="Client HTTP User-Agent string.",
    )

    details: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
        comment="Sanitized metadata dictionary. Never contains secrets or unmasked PII.",
    )

    def __repr__(self) -> str:
        return (
            f"<AuditLog id={self.id} action={self.action!r} "
            f"outcome={self.outcome!r} actor_id={self.actor_id}>"
        )
