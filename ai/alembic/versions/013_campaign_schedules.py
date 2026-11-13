"""Migration 013: disparos recorrentes (mensais)

Revision ID: 013
Revises: 012
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "013"
down_revision: Union[str, None] = "012"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "campaign_schedules",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.String(64), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("mode", sa.String(32), server_default="template", nullable=False),
        sa.Column("template_name", sa.String(255), server_default="", nullable=False),
        sa.Column("language", sa.String(16), server_default="pt_BR", nullable=False),
        sa.Column("message", sa.Text(), server_default="", nullable=False),
        sa.Column("header_image_url", sa.Text(), server_default="", nullable=False),
        sa.Column("account_id", sa.Integer(), nullable=True),
        sa.Column("inbox_id", sa.Integer(), nullable=True),
        sa.Column("contact_ids", postgresql.JSONB(), server_default="[]", nullable=False),
        sa.Column("phones", postgresql.JSONB(), server_default="[]", nullable=False),
        sa.Column("all_contacts", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("day_of_month", sa.Integer(), server_default="1", nullable=False),
        sa.Column("hour", sa.Integer(), server_default="9", nullable=False),
        sa.Column("minute", sa.Integer(), server_default="0", nullable=False),
        sa.Column("timezone", sa.String(64), server_default="America/Sao_Paulo", nullable=False),
        sa.Column("active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("next_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_campaign_id", sa.Integer(), nullable=True),
        sa.Column("last_error", sa.Text(), server_default="", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.add_column("dispatch_campaigns", sa.Column("schedule_id", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("dispatch_campaigns", "schedule_id")
    op.drop_table("campaign_schedules")
