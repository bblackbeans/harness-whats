"""Migration 014: banco de imagens (mídia) por cliente

Revision ID: 014
Revises: 013
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "014"
down_revision: Union[str, None] = "013"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "tenant_media",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.String(64), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("filename", sa.String(255), nullable=False),
        sa.Column("original_name", sa.String(255), nullable=False),
        sa.Column("mime_type", sa.String(128), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("width", sa.Integer(), nullable=True),
        sa.Column("height", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_tenant_media_tenant", "tenant_media", ["tenant_id"])
    op.create_index("ix_tenant_media_filename", "tenant_media", ["filename"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_tenant_media_filename", table_name="tenant_media")
    op.drop_index("ix_tenant_media_tenant", table_name="tenant_media")
    op.drop_table("tenant_media")
