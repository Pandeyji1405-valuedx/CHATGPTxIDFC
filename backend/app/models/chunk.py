"""
DocumentChunk ORM model.

Supports the sparse/lexical retrieval branch of the Phase 4 RAG pipeline.
Each record mirrors one text chunk already stored in ChromaDB so that
PostgreSQL Full-Text Search can be executed without touching the vector store.

A GIN index on the generated tsvector column enables fast keyword matching
over the entire RBI Knowledge Base.

Design rules:
  - chunk_id is the shared key between ChromaDB and this table.
  - status mirrors the parent document_version status (ACTIVE/INACTIVE/SUPERSEDED).
  - Only ACTIVE chunks with COMPLETED ingestion participate in retrieval.
  - Populated by the ingestion pipeline; backfilled for existing versions via
    a one-time idempotent migration utility.
"""

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.document import DocumentStatus


class DocumentChunk(Base):
    """
    Persists individual text chunks for PostgreSQL Full-Text Search.

    One row per chunk -- mirrors the ChromaDB entry for the same chunk.
    The search_vector column is populated by a PostgreSQL trigger defined
    in the Alembic migration so that it remains consistent automatically.
    """

    __tablename__ = "document_chunks"

    # Primary key
    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
        index=True,
        comment="UUID primary key.",
    )

    # FK to parent document (CASCADE delete)
    document_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Reference to the parent document.",
    )

    # FK to parent document version (CASCADE delete)
    version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("document_versions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Reference to the parent document version.",
    )

    # Shared identity with ChromaDB -- must be unique across the collection
    chunk_id: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        unique=True,
        index=True,
        comment="Deterministic chunk identifier shared with ChromaDB.",
    )

    # Raw text content used for FTS
    content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Plain-text chunk content for full-text search.",
    )

    # Provenance metadata -- sourced from extraction pipeline
    page_number: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
        comment="Source page number within the PDF.",
    )

    section: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        comment="Section heading extracted from the PDF structure.",
    )

    topic: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        comment="Regulatory topic inherited from the parent document.",
    )

    circular_number: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        comment="RBI circular number inherited from the parent document.",
    )

    # Mirrors parent version status for filtered retrieval
    status: Mapped[DocumentStatus] = mapped_column(
        Enum(DocumentStatus, name="documentstatus", create_type=False),
        nullable=False,
        default=DocumentStatus.ACTIVE,
        server_default=DocumentStatus.ACTIVE.value,
        index=True,
        comment="ACTIVE chunks participate in retrieval; INACTIVE/SUPERSEDED are excluded.",
    )

    # Timestamps (UTC)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    # Table-level indexes
    __table_args__ = (
        # Composite index to support version-scoped chunk lookups
        Index("ix_document_chunks_version_status", "version_id", "status"),
    )

    def __repr__(self) -> str:
        return (
            f"<DocumentChunk chunk_id={self.chunk_id!r} "
            f"page={self.page_number} status={self.status}>"
        )
