"""
Message Feedback ORM model (Phase 7).

Persists user rating (thumbs up / thumbs down) and structured feedback
reasons on generated assistant answers.

Key design decisions:
  - Attached to specific message_id, conversation_id, user_id, tenant_id.
  - One user rating per message (unique constraint / update on conflict).
  - Preserves underlying message and conversation intact.
"""

import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class MessageFeedback(Base):
    """
    User feedback record attached to an assistant chat message.
    """

    __tablename__ = "message_feedback"
    __table_args__ = (
        UniqueConstraint("message_id", "user_id", name="uq_message_user_feedback"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
        index=True,
        comment="UUID primary key.",
    )

    message_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("messages.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="The assistant message being evaluated.",
    )

    conversation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Parent conversation.",
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="User who submitted feedback.",
    )

    tenant_id: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
        default="idfc_bank",
        server_default="idfc_bank",
        comment="Tenant identifier for multi-tenant isolation.",
    )

    rating: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        index=True,
        comment="User rating: POSITIVE or NEGATIVE.",
    )

    reason_category: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        comment="Optional structured feedback reason (e.g. INACCURATE, OUTDATED, UNHELPFUL).",
    )

    comment: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Optional free-form user comment.",
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    def __repr__(self) -> str:
        return (
            f"<MessageFeedback id={self.id} message_id={self.message_id} "
            f"rating={self.rating!r} user_id={self.user_id}>"
        )
