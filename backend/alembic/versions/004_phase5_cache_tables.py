"""Create Phase 5 cache and memory tables

Revision ID: 004
Revises: 003
Create Date: 2026-09-19

This migration creates:
  - `cached_answers`: Governed exact and pgvector semantic cache table
  - `cache_document_dependencies`: Version-aware dependency join table
  - `question_variants`: Alias table for canonical queries

Includes explicit pgvector extension binary check before executing extension creation.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "004"
down_revision: Union[str, None] = "003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    is_postgres = bind.dialect.name == "postgresql"

    if is_postgres:
        # 1. Prerequisite check: verify pgvector extension binary is installed on PG server
        res = bind.execute(
            sa.text("SELECT 1 FROM pg_available_extensions WHERE name = 'vector'")
        )
        if not res.scalar():
            raise RuntimeError(
                "\n"
                "========================================================================\n"
                "CRITICAL PRE-REQUISITE ERROR: PostgreSQL 'vector' extension is NOT available.\n"
                "The pgvector extension binary is missing from your PostgreSQL server installation.\n"
                "Please install pgvector (e.g. `apt install postgresql-15-pgvector` or\n"
                "download Windows pgvector binaries) before running Phase 5 migrations.\n"
                "========================================================================"
            )

        # 2. Enable pgvector extension
        op.execute("CREATE EXTENSION IF NOT EXISTS vector;")

    # 3. Create cached_answers table
    op.create_table(
        "cached_answers",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("query_hash", sa.String(64), nullable=False, index=True),
        sa.Column("original_user_query", sa.Text(), nullable=False),
        sa.Column("canonical_query", sa.Text(), nullable=False),
        sa.Column("answer", sa.Text(), nullable=False),
        sa.Column("citations", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("tenant_id", sa.String(100), nullable=False, server_default="idfc_bank"),
        sa.Column("required_role", sa.String(50), nullable=False, server_default="USER"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true", index=True),
        sa.Column("hit_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    if is_postgres:
        # Add vector(768) column and HNSW index on PostgreSQL
        op.execute("ALTER TABLE cached_answers ADD COLUMN query_vector vector(768);")
        op.execute(
            "CREATE INDEX IF NOT EXISTS ix_cached_answers_query_vector_hnsw "
            "ON cached_answers USING hnsw (query_vector vector_cosine_ops);"
        )

    # 4. Create cache_document_dependencies table
    op.create_table(
        "cache_document_dependencies",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("cache_answer_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("cached_answers.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("document_version_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("document_versions.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    # 5. Create question_variants table
    op.create_table(
        "question_variants",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("cache_answer_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("cached_answers.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("variant_query", sa.Text(), nullable=False),
        sa.Column("variant_hash", sa.String(64), nullable=False, index=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("question_variants")
    op.drop_table("cache_document_dependencies")
    op.drop_table("cached_answers")
