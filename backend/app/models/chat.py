"""
Conversation and Message ORM models (Phase 4).

Persists the full chat history for authenticated users.
Each conversation belongs to one user; each message belongs to one conversation.

Key design decisions:
  - Conversations are user-owned; cross-user access is forbidden at the API layer.
  - The user raw question is stored verbatim in messages.content (role=USER).
  - The assistant answer is stored in messages.content (role=ASSISTANT).
  - citations (JSONB) is backend-assembled metadata -- never Gemini-invented values.
  - metrics (JSONB) stores diagnostic latencies and retrieval counts for observability.
  - retrieval_type signals the pipeline outcome ('rag' or 'insufficient_evidence').
"""

import enum
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, Text, func
from sqlalchemy import JSON as JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class MessageRole(str, enum.Enum):
    """Participant role in a conversation turn."""

    USER = "USER"
    ASSISTANT = "ASSISTANT"


class Conversation(Base):
    """
    A named session grouping one user's question-answer exchanges.

    Title is nullable -- callers may set it; the backend may auto-derive it
    from the first user message in a future phase.
    """

    __tablename__ = "conversations"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
        index=True,
        comment="UUID primary key.",
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Owning user. Only this user may read or extend the conversation.",
    )

    title: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        comment="Optional display title (first question excerpt or user-supplied).",
    )

    message_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
        comment="Denormalised count of messages for fast listing queries.",
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

    # Relationships
    messages: Mapped[list["Message"]] = relationship(
        "Message",
        back_populates="conversation",
        cascade="all, delete-orphan",
        order_by="Message.created_at",
    )

    def __repr__(self) -> str:
        return f"<Conversation id={self.id} user_id={self.user_id} title={self.title!r}>"


class Message(Base):
    """
    A single turn (question or answer) within a conversation.

    For role=USER:  content = verbatim user question; citations = None.
    For role=ASSISTANT: content = RAG answer; citations = backend-assembled list.
    """

    __tablename__ = "messages"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
        index=True,
        comment="UUID primary key.",
    )

    conversation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Parent conversation.",
    )

    role: Mapped[MessageRole] = mapped_column(
        Enum(MessageRole, name="messagerole"),
        nullable=False,
        comment="USER or ASSISTANT.",
    )

    content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Verbatim user question or full assistant answer text.",
    )

    retrieval_type: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        comment="Pipeline outcome: 'rag', 'insufficient_evidence', or None for user messages.",
    )

    citations: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
        comment="Backend-constructed citation list (JSONB). Never contains Gemini-invented metadata.",
    )

    metrics: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
        comment="Diagnostic payload: retrieval latencies, candidate counts, reranker scores.",
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    # Relationships
    conversation: Mapped["Conversation"] = relationship(
        "Conversation",
        back_populates="messages",
    )

    def __repr__(self) -> str:
        return (
            f"<Message id={self.id} role={self.role} "
            f"conv_id={self.conversation_id}>"
        )
