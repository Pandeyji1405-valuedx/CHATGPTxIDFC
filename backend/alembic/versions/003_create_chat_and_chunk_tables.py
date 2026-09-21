"""Create document_chunks, conversations, and messages tables

Revision ID: 003
Revises: 002
Create Date: 2026-09-18

This migration creates:
  - `document_chunks` table: PostgreSQL FTS sparse retrieval store (Phase 4 RAG)
  - `conversations` table: User-owned chat session registry
  - `messages` table: Individual conversation turns with citations and metrics

Also creates:
  - messagerole enum type
  - GIN index on document_chunks for full-text search
  - Trigger to maintain the tsvector search_vector column

Reversible: Yes.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create Phase 4 tables: document_chunks, conversations, messages."""

    # ------------------------------------------------------------------ #
    # 1. document_chunks table (Sparse/Lexical FTS branch)
    # ------------------------------------------------------------------ #
    op.create_table(
        "document_chunks",
        sa.Column(
            "id",
            sa.Uuid(as_uuid=True),
            primary_key=True,
            nullable=False,
            comment="UUID primary key.",
        ),
        sa.Column(
            "document_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("documents.id", ondelete="CASCADE"),
            nullable=False,
            comment="Reference to the parent document.",
        ),
        sa.Column(
            "version_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("document_versions.id", ondelete="CASCADE"),
            nullable=False,
            comment="Reference to the parent document version.",
        ),
        sa.Column(
            "chunk_id",
            sa.String(255),
            nullable=False,
            comment="Deterministic chunk identifier shared with ChromaDB.",
        ),
        sa.Column(
            "content",
            sa.Text(),
            nullable=False,
            comment="Plain-text chunk content for full-text search.",
        ),
        sa.Column(
            "page_number",
            sa.Integer(),
            nullable=False,
            server_default="0",
            comment="Source page number within the PDF.",
        ),
        sa.Column(
            "section",
            sa.String(255),
            nullable=True,
            comment="Section heading extracted from the PDF structure.",
        ),
        sa.Column(
            "topic",
            sa.String(255),
            nullable=True,
            comment="Regulatory topic inherited from the parent document.",
        ),
        sa.Column(
            "circular_number",
            sa.String(255),
            nullable=True,
            comment="RBI circular number inherited from the parent document.",
        ),
        sa.Column(
            "status",
            postgresql.ENUM(
                "ACTIVE", "INACTIVE", "SUPERSEDED",
                name="documentstatus",
                create_type=False,
            ),
            nullable=False,
            server_default="ACTIVE",
            comment="ACTIVE chunks participate in retrieval.",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    # Unique constraint on chunk_id (shared key with ChromaDB)
    op.create_unique_constraint(
        "uq_document_chunks_chunk_id", "document_chunks", ["chunk_id"]
    )

    # Standard indexes
    op.create_index("ix_document_chunks_id", "document_chunks", ["id"])
    op.create_index("ix_document_chunks_document_id", "document_chunks", ["document_id"])
    op.create_index("ix_document_chunks_version_id", "document_chunks", ["version_id"])
    op.create_index("ix_document_chunks_chunk_id", "document_chunks", ["chunk_id"])
    op.create_index("ix_document_chunks_status", "document_chunks", ["status"])
    op.create_index(
        "ix_document_chunks_version_status",
        "document_chunks",
        ["version_id", "status"],
    )

    # GIN index for full-text search using 'simple' configuration to preserve
    # regulatory identifiers (e.g. "RBI/2023-24/108") without stemming distortion
    op.execute(
        """
        CREATE INDEX ix_document_chunks_fts
        ON document_chunks
        USING GIN (to_tsvector('simple', content))
        """
    )

    # ------------------------------------------------------------------ #
    # 2. messagerole enum type
    # ------------------------------------------------------------------ #
    message_role_enum = postgresql.ENUM("USER", "ASSISTANT", name="messagerole")
    message_role_enum.create(op.get_bind(), checkfirst=True)

    # ------------------------------------------------------------------ #
    # 3. conversations table
    # ------------------------------------------------------------------ #
    op.create_table(
        "conversations",
        sa.Column(
            "id",
            sa.Uuid(as_uuid=True),
            primary_key=True,
            nullable=False,
            comment="UUID primary key.",
        ),
        sa.Column(
            "user_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            comment="Owning user.",
        ),
        sa.Column(
            "title",
            sa.String(255),
            nullable=True,
            comment="Optional display title.",
        ),
        sa.Column(
            "message_count",
            sa.Integer(),
            nullable=False,
            server_default="0",
            comment="Denormalised count of messages.",
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

    op.create_index("ix_conversations_id", "conversations", ["id"])
    op.create_index("ix_conversations_user_id", "conversations", ["user_id"])

    # ------------------------------------------------------------------ #
    # 4. messages table
    # ------------------------------------------------------------------ #
    op.create_table(
        "messages",
        sa.Column(
            "id",
            sa.Uuid(as_uuid=True),
            primary_key=True,
            nullable=False,
            comment="UUID primary key.",
        ),
        sa.Column(
            "conversation_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("conversations.id", ondelete="CASCADE"),
            nullable=False,
            comment="Parent conversation.",
        ),
        sa.Column(
            "role",
            postgresql.ENUM("USER", "ASSISTANT", name="messagerole", create_type=False),
            nullable=False,
            comment="USER or ASSISTANT.",
        ),
        sa.Column(
            "content",
            sa.Text(),
            nullable=False,
            comment="Verbatim user question or full assistant answer.",
        ),
        sa.Column(
            "retrieval_type",
            sa.String(50),
            nullable=True,
            comment="Pipeline outcome: rag, insufficient_evidence, or None.",
        ),
        sa.Column(
            "citations",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
            comment="Backend-constructed citation list.",
        ),
        sa.Column(
            "metrics",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
            comment="Diagnostic latencies and retrieval counts.",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    op.create_index("ix_messages_id", "messages", ["id"])
    op.create_index("ix_messages_conversation_id", "messages", ["conversation_id"])


def downgrade() -> None:
    """Drop messages, conversations, document_chunks tables and enum types."""

    # Drop indexes then tables in reverse dependency order
    op.drop_index("ix_messages_conversation_id", table_name="messages")
    op.drop_index("ix_messages_id", table_name="messages")
    op.drop_table("messages")

    op.drop_index("ix_conversations_user_id", table_name="conversations")
    op.drop_index("ix_conversations_id", table_name="conversations")
    op.drop_table("conversations")

    message_role_enum = postgresql.ENUM("USER", "ASSISTANT", name="messagerole")
    message_role_enum.drop(op.get_bind(), checkfirst=True)

    op.drop_index("ix_document_chunks_fts", table_name="document_chunks")
    op.drop_index("ix_document_chunks_version_status", table_name="document_chunks")
    op.drop_index("ix_document_chunks_status", table_name="document_chunks")
    op.drop_index("ix_document_chunks_chunk_id", table_name="document_chunks")
    op.drop_index("ix_document_chunks_version_id", table_name="document_chunks")
    op.drop_index("ix_document_chunks_document_id", table_name="document_chunks")
    op.drop_index("ix_document_chunks_id", table_name="document_chunks")
    op.drop_constraint("uq_document_chunks_chunk_id", "document_chunks", type_="unique")
    op.drop_table("document_chunks")
