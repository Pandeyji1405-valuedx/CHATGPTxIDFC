"""Create documents and document_versions tables

Revision ID: 002
Revises: 001
Create Date: 2026-09-18

This migration creates:
  - `documents` table: System of record for RBI regulatory document identities
  - `document_versions` table: Version history, ingestion states, file tracking
  - PostgreSQL enum types: `documentstatus` and `ingestionstatus`

Reversible: Yes — downgrade() drops the tables and enum types cleanly.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create documentstatus, ingestionstatus enums and document tables."""

    # 1. Create PostgreSQL native enum types
    doc_status_enum = postgresql.ENUM(
        "ACTIVE", "INACTIVE", "SUPERSEDED", name="documentstatus"
    )
    doc_status_enum.create(op.get_bind(), checkfirst=True)

    ingest_status_enum = postgresql.ENUM(
        "PENDING", "PROCESSING", "COMPLETED", "FAILED", name="ingestionstatus"
    )
    ingest_status_enum.create(op.get_bind(), checkfirst=True)

    # 2. Create `documents` table
    op.create_table(
        "documents",
        sa.Column(
            "id",
            sa.Uuid(as_uuid=True),
            primary_key=True,
            nullable=False,
            comment="UUID primary key for regulatory document.",
        ),
        sa.Column(
            "document_key",
            sa.String(255),
            nullable=False,
            comment="Deterministic unique key/slug for the document.",
        ),
        sa.Column(
            "title",
            sa.String(500),
            nullable=False,
            comment="Official title of the RBI circular / master direction.",
        ),
        sa.Column(
            "document_type",
            sa.String(100),
            nullable=False,
            server_default="circular",
            comment="Type of RBI regulatory instrument.",
        ),
        sa.Column(
            "circular_number",
            sa.String(255),
            nullable=True,
            comment="Official RBI circular or notification number.",
        ),
        sa.Column(
            "topic",
            sa.String(255),
            nullable=True,
            comment="Regulatory topic or category.",
        ),
        sa.Column(
            "source_name",
            sa.String(255),
            nullable=False,
            server_default="Reserve Bank of India",
            comment="Issuer / regulatory authority.",
        ),
        sa.Column(
            "source_url",
            sa.String(1024),
            nullable=True,
            comment="Original RBI publication URL.",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    op.create_unique_constraint("uq_documents_key", "documents", ["document_key"])
    op.create_index("ix_documents_key", "documents", ["document_key"], unique=True)
    op.create_index("ix_documents_circular_number", "documents", ["circular_number"])
    op.create_index("ix_documents_topic", "documents", ["topic"])
    op.create_index("ix_documents_id", "documents", ["id"])

    # 3. Create `document_versions` table
    op.create_table(
        "document_versions",
        sa.Column(
            "id",
            sa.Uuid(as_uuid=True),
            primary_key=True,
            nullable=False,
            comment="UUID primary key for this specific document version.",
        ),
        sa.Column(
            "document_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("documents.id", ondelete="CASCADE"),
            nullable=False,
            comment="Reference to the parent document.",
        ),
        sa.Column(
            "version_number",
            sa.Integer(),
            nullable=False,
            server_default="1",
            comment="Monotonically increasing version number for this document.",
        ),
        sa.Column(
            "published_date",
            sa.Date(),
            nullable=True,
            comment="Date published officially by the RBI.",
        ),
        sa.Column(
            "effective_date",
            sa.Date(),
            nullable=True,
            comment="Date the circular / directions come into force.",
        ),
        sa.Column(
            "status",
            postgresql.ENUM("ACTIVE", "INACTIVE", "SUPERSEDED", name="documentstatus", create_type=False),
            nullable=False,
            server_default="INACTIVE",
            comment="ACTIVE, INACTIVE, or SUPERSEDED.",
        ),
        sa.Column(
            "file_name",
            sa.String(255),
            nullable=False,
            comment="Original uploaded PDF filename.",
        ),
        sa.Column(
            "file_hash",
            sa.String(64),
            nullable=False,
            comment="SHA-256 hex digest of the file content for duplicate detection.",
        ),
        sa.Column(
            "storage_path",
            sa.String(1024),
            nullable=False,
            comment="Local filesystem storage path for the original PDF file.",
        ),
        sa.Column(
            "file_size_bytes",
            sa.Integer(),
            nullable=False,
            server_default="0",
            comment="File size in bytes.",
        ),
        sa.Column(
            "page_count",
            sa.Integer(),
            nullable=False,
            server_default="0",
            comment="Total pages extracted from the PDF.",
        ),
        sa.Column(
            "chunk_count",
            sa.Integer(),
            nullable=False,
            server_default="0",
            comment="Total text chunks indexed into ChromaDB.",
        ),
        sa.Column(
            "ingestion_status",
            postgresql.ENUM("PENDING", "PROCESSING", "COMPLETED", "FAILED", name="ingestionstatus", create_type=False),
            nullable=False,
            server_default="PENDING",
            comment="PENDING, PROCESSING, COMPLETED, or FAILED.",
        ),
        sa.Column(
            "error_message",
            sa.String(2048),
            nullable=True,
            comment="Error diagnostics if ingestion fails.",
        ),
        sa.Column(
            "superseded_by_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("document_versions.id", ondelete="SET NULL"),
            nullable=True,
            comment="Version ID of the newer regulation that explicitly supersedes this version.",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    op.create_index("ix_document_versions_document_id", "document_versions", ["document_id"])
    op.create_index("ix_document_versions_file_hash", "document_versions", ["file_hash"])
    op.create_index("ix_document_versions_status", "document_versions", ["status"])
    op.create_index("ix_document_versions_ingestion_status", "document_versions", ["ingestion_status"])
    op.create_index("ix_document_versions_id", "document_versions", ["id"])
    op.create_unique_constraint(
        "uq_document_versions_doc_ver", "document_versions", ["document_id", "version_number"]
    )


def downgrade() -> None:
    """Drop document_versions, documents tables and enum types."""
    op.drop_constraint("uq_document_versions_doc_ver", "document_versions", type_="unique")
    op.drop_index("ix_document_versions_id", table_name="document_versions")
    op.drop_index("ix_document_versions_ingestion_status", table_name="document_versions")
    op.drop_index("ix_document_versions_status", table_name="document_versions")
    op.drop_index("ix_document_versions_file_hash", table_name="document_versions")
    op.drop_index("ix_document_versions_document_id", table_name="document_versions")
    op.drop_table("document_versions")

    op.drop_index("ix_documents_id", table_name="documents")
    op.drop_index("ix_documents_topic", table_name="documents")
    op.drop_index("ix_documents_circular_number", table_name="documents")
    op.drop_index("ix_documents_key", table_name="documents")
    op.drop_constraint("uq_documents_key", "documents", type_="unique")
    op.drop_table("documents")

    ingest_status_enum = postgresql.ENUM(
        "PENDING", "PROCESSING", "COMPLETED", "FAILED", name="ingestionstatus"
    )
    ingest_status_enum.drop(op.get_bind(), checkfirst=True)

    doc_status_enum = postgresql.ENUM(
        "ACTIVE", "INACTIVE", "SUPERSEDED", name="documentstatus"
    )
    doc_status_enum.drop(op.get_bind(), checkfirst=True)
