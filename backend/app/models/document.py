"""
Document and DocumentVersion ORM models.

Defines the PostgreSQL schema for the RBI Knowledge Base (Phase 3).
- `documents`: System-of-record registry for unique RBI regulatory document identities.
- `document_versions`: Individual document versions, file tracking, status, and ingestion lifecycle.

Security and lifecycle rules:
  - Version status is INACTIVE while ingestion is in progress.
  - Becomes ACTIVE only after PDF extraction, chunking, embedding, and ChromaDB indexing succeed.
  - An older version is marked SUPERSEDED only through explicit supersession confirmation.
  - Versions with ingestion_status != COMPLETED are never considered active knowledge sources.
"""

import enum
import uuid
from datetime import date, datetime
from typing import Optional

from sqlalchemy import (
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class DocumentStatus(str, enum.Enum):
    """
    Lifecycle status of a document version.

    ACTIVE     — Current authoritative regulatory version.
    INACTIVE   — Under processing, draft, or administrative hold.
    SUPERSEDED — Explicitly replaced by a newer regulatory version.
    """

    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"
    SUPERSEDED = "SUPERSEDED"


class IngestionStatus(str, enum.Enum):
    """
    Pipeline processing state for a document version.

    PENDING    — Uploaded, queued for ingestion.
    PROCESSING — Extracting, cleaning, chunking, or embedding.
    COMPLETED  — Fully indexed in ChromaDB and ready for retrieval.
    FAILED     — Extraction, embedding, or indexing failed.
    """

    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class Document(Base):
    """
    Top-level registry representing a unique RBI regulatory instrument.

    Examples:
      - Master Direction on KYC (2016)
      - Cyber Security Framework in Banks (2016)
      - Digital Payment Security Controls (2021)
    """

    __tablename__ = "documents"

    # Primary key
    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
        index=True,
        comment="UUID primary key for regulatory document.",
    )

    # Unique slug / identifier for API & search (e.g. "rbi-kyc-master-direction-2016")
    document_key: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        nullable=False,
        index=True,
        comment="Deterministic unique key/slug for the document.",
    )

    # Human-readable title
    title: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
        comment="Official title of the RBI circular / master direction.",
    )

    # Instrument type (e.g. "circular", "master_direction", "notification", "guideline")
    document_type: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        default="circular",
        server_default="circular",
        comment="Type of RBI regulatory instrument.",
    )

    # RBI official circular / reference number (e.g. "RBI/2023-24/108")
    circular_number: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        index=True,
        comment="Official RBI circular or notification number.",
    )

    # Domain / regulatory topic (e.g. "KYC", "Cyber Security", "Lending", "Cards")
    topic: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        index=True,
        comment="Regulatory topic or category.",
    )

    # Source attribution
    source_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        default="Reserve Bank of India",
        server_default="Reserve Bank of India",
        comment="Issuer / regulatory authority.",
    )

    # URL to the official source publication if available
    source_url: Mapped[Optional[str]] = mapped_column(
        String(1024),
        nullable=True,
        comment="Original RBI publication URL.",
    )

    # Timestamps (UTC)
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

    # One-to-many relationship with version history
    versions: Mapped[list["DocumentVersion"]] = relationship(
        "DocumentVersion",
        back_populates="document",
        cascade="all, delete-orphan",
        order_by="desc(DocumentVersion.version_number)",
        foreign_keys="[DocumentVersion.document_id]",
    )

    def __repr__(self) -> str:
        return f"<Document id={self.id} key={self.document_key!r} title={self.title[:30]!r}>"


class DocumentVersion(Base):
    """
    An immutable revision of an RBI regulatory document.

    Stores the raw file metadata, page/chunk metrics, pipeline state,
    and regulatory timeline (published & effective dates).
    """

    __tablename__ = "document_versions"

    # Primary key
    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
        index=True,
        comment="UUID primary key for this specific document version.",
    )

    # Foreign key to parent document
    document_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Reference to the parent document.",
    )

    # Version sequence number (1, 2, 3...)
    version_number: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
        server_default="1",
        comment="Monotonically increasing version number for this document.",
    )

    # Regulatory dates
    published_date: Mapped[Optional[date]] = mapped_column(
        Date,
        nullable=True,
        comment="Date published officially by the RBI.",
    )

    effective_date: Mapped[Optional[date]] = mapped_column(
        Date,
        nullable=True,
        comment="Date the circular / directions come into force.",
    )

    # Lifecycle status: begins as INACTIVE, becomes ACTIVE only when ingestion completes
    status: Mapped[DocumentStatus] = mapped_column(
        Enum(DocumentStatus, name="documentstatus"),
        nullable=False,
        default=DocumentStatus.INACTIVE,
        server_default=DocumentStatus.INACTIVE.value,
        index=True,
        comment="ACTIVE, INACTIVE, or SUPERSEDED.",
    )

    # File identity & storage details
    file_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Original uploaded PDF filename.",
    )

    file_hash: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        index=True,
        comment="SHA-256 hex digest of the file content for duplicate detection.",
    )

    storage_path: Mapped[str] = mapped_column(
        String(1024),
        nullable=False,
        comment="Local filesystem storage path for the original PDF file.",
    )

    file_size_bytes: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
        comment="File size in bytes.",
    )

    # Ingestion metrics
    page_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
        comment="Total pages extracted from the PDF.",
    )

    chunk_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
        comment="Total text chunks indexed into ChromaDB.",
    )

    # Ingestion pipeline state
    ingestion_status: Mapped[IngestionStatus] = mapped_column(
        Enum(IngestionStatus, name="ingestionstatus"),
        nullable=False,
        default=IngestionStatus.PENDING,
        server_default=IngestionStatus.PENDING.value,
        index=True,
        comment="PENDING, PROCESSING, COMPLETED, or FAILED.",
    )

    error_message: Mapped[Optional[str]] = mapped_column(
        String(2048),
        nullable=True,
        comment="Error diagnostics if ingestion fails.",
    )

    # Optional explicit pointer to the newer version that supersedes this one
    superseded_by_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("document_versions.id", ondelete="SET NULL"),
        nullable=True,
        comment="Version ID of the newer regulation that explicitly supersedes this version.",
    )

    # Timestamps (UTC)
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

    # Relationship to parent document
    document: Mapped["Document"] = relationship(
        "Document",
        back_populates="versions",
        foreign_keys=[document_id],
    )

    def __repr__(self) -> str:
        return (
            f"<DocumentVersion id={self.id} doc_id={self.document_id} "
            f"v={self.version_number} status={self.status} ingestion={self.ingestion_status}>"
        )
