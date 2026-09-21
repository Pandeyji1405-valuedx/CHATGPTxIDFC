"""
Phase 5 Cache & Memory ORM Models.

Provides persistent database schemas for:
  - `cached_answers`: Governed exact and pgvector semantic cache records.
  - `cache_document_dependencies`: Relational mapping of cached answers to cited document_versions.
  - `question_variants`: Bounded canonical query aliases pointing to approved cached answers.
"""

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy import JSON as JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

# Try importing pgvector Vector type; if unavailable (e.g. SQLite test DB), fall back to String/JSON placeholder
try:
    from pgvector.sqlalchemy import Vector
    VECTOR_TYPE = Vector(768)
except ImportError:
    VECTOR_TYPE = Text  # Fallback for environments without pgvector C library


class CachedAnswer(Base):
    """
    Authoritative persistent cache entry for approved regulatory Q&A turns.
    """

    __tablename__ = "cached_answers"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
        index=True,
        comment="UUID primary key.",
    )

    query_hash: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        index=True,
        comment="SHA-256 hex digest of normalized canonical query.",
    )

    original_user_query: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Raw user query string that originated this answer.",
    )

    canonical_query: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Normalized canonical query string used for retrieval and caching.",
    )

    answer: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Authoritative grounded RAG answer.",
    )

    citations: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
        comment="Validated page-level citations (JSON list).",
    )

    query_vector = mapped_column(
        VECTOR_TYPE,
        nullable=True,
        comment="768-dimensional normalized query embedding for pgvector cosine search.",
    )

    tenant_id: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        default="idfc_bank",
        server_default="idfc_bank",
        comment="Tenant/bank identifier for strict isolation.",
    )

    required_role: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="USER",
        server_default="USER",
        comment="Minimum user role (USER or ADMIN) required to access this cached answer.",
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default="true",
        index=True,
        comment="True if active; updated to False when dependent document versions are superseded.",
    )

    hit_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
        comment="Usage counter for cache analytics.",
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        comment="Expiration timestamp after which entry is ineligible.",
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    # Relationships
    document_dependencies: Mapped[list["CacheDocumentDependency"]] = relationship(
        "CacheDocumentDependency",
        back_populates="cached_answer",
        cascade="all, delete-orphan",
    )

    variants: Mapped[list["QuestionVariant"]] = relationship(
        "QuestionVariant",
        back_populates="cached_answer",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<CachedAnswer id={self.id} hash={self.query_hash[:8]} active={self.is_active}>"


class CacheDocumentDependency(Base):
    """
    Join table linking cached answers to specific DocumentVersion records.
    Used for atomic version-aware invalidation.
    """

    __tablename__ = "cache_document_dependencies"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
        index=True,
    )

    cache_answer_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("cached_answers.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    document_version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("document_versions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    # Relationships
    cached_answer: Mapped["CachedAnswer"] = relationship(
        "CachedAnswer",
        back_populates="document_dependencies",
    )


class QuestionVariant(Base):
    """
    Bounded question alias linked to an authoritative cached answer.

    Phase 5E additions:
    - is_active: False when the underlying cached_answer is invalidated.
    - tenant_id: Inherited from the cached_answer for hard tenant isolation.

    Variants are NEVER independent authoritative answers.
    They are aliases that resolve through the full 10-gate governance validation
    of the underlying CachedAnswer.
    """

    __tablename__ = "question_variants"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
        index=True,
    )

    cache_answer_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("cached_answers.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    variant_query: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="The variant question text.",
    )

    variant_hash: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        index=True,
        comment="SHA-256 hash of the normalized variant_query.",
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default="true",
        index=True,
        comment="False when the underlying cached_answer is deactivated/invalidated.",
    )

    tenant_id: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        default="idfc_bank",
        server_default="idfc_bank",
        comment="Tenant identifier inherited from the parent cached_answer.",
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    # Relationships
    cached_answer: Mapped["CachedAnswer"] = relationship(
        "CachedAnswer",
        back_populates="variants",
    )
