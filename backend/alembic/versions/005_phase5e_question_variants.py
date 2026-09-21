"""Add is_active and tenant_id columns to question_variants table.

Revision ID: 005
Revises: 004
Create Date: 2026-09-19

Phase 5E: Extends the question_variants table so that variants can be:
  - Governed by tenant isolation (tenant_id)
  - Deactivated when the underlying cached_answer is invalidated (is_active)

This migration is additive-only and fully reversible.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "005"
down_revision: Union[str, None] = "004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add is_active column — default True (existing variants are active)
    op.add_column(
        "question_variants",
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default="true",
            comment="False when the underlying cached_answer is invalidated.",
        ),
    )
    # Add index on is_active for fast lookup filtering
    op.create_index(
        "ix_question_variants_is_active",
        "question_variants",
        ["is_active"],
    )

    # Add tenant_id column — default idfc_bank (single-tenant Phase 5)
    op.add_column(
        "question_variants",
        sa.Column(
            "tenant_id",
            sa.String(100),
            nullable=False,
            server_default="idfc_bank",
            comment="Tenant identifier for isolation. Inherited from the cached_answer.",
        ),
    )


def downgrade() -> None:
    op.drop_index("ix_question_variants_is_active", table_name="question_variants")
    op.drop_column("question_variants", "is_active")
    op.drop_column("question_variants", "tenant_id")
