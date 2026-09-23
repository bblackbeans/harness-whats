"""Migration 011: campanhas de disparo WhatsApp

Revision ID: 011
Revises: 010
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "011"
down_revision: Union[str, None] = "010"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "dispatch_campaigns",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.String(64), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("mode", sa.String(32), server_default="template", nullable=False),
        sa.Column("template_name", sa.String(255), server_default="", nullable=False),
        sa.Column("language", sa.String(16), server_default="pt_BR", nullable=False),
        sa.Column("message", sa.Text(), server_default="", nullable=False),
        sa.Column("account_id", sa.Integer(), nullable=True),
        sa.Column("inbox_id", sa.Integer(), nullable=True),
        sa.Column("agent_id", sa.Integer(), nullable=True),
        sa.Column("flow_id", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(32), server_default="draft", nullable=False),
        sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("default_params", JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("error", sa.Text(), server_default="", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_dispatch_campaigns_tenant_id", "dispatch_campaigns", ["tenant_id"])
    op.create_index("ix_dispatch_campaigns_status_scheduled", "dispatch_campaigns", ["status", "scheduled_at"])

    op.create_table(
        "dispatch_campaign_recipients",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "campaign_id",
            sa.Integer(),
            sa.ForeignKey("dispatch_campaigns.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "contact_id",
            sa.Integer(),
            sa.ForeignKey("contact_profiles.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("phone", sa.String(32), nullable=False),
        sa.Column("name", sa.String(255), server_default="", nullable=False),
        sa.Column("chatwoot_contact_id", sa.Integer(), nullable=True),
        sa.Column("conversation_id", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(32), server_default="pending", nullable=False),
        sa.Column("error", sa.Text(), server_default="", nullable=False),
        sa.Column("variables", JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_dispatch_campaign_recipients_campaign_id",
        "dispatch_campaign_recipients",
        ["campaign_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_dispatch_campaign_recipients_campaign_id", table_name="dispatch_campaign_recipients")
    op.drop_table("dispatch_campaign_recipients")
    op.drop_index("ix_dispatch_campaigns_status_scheduled", table_name="dispatch_campaigns")
    op.drop_index("ix_dispatch_campaigns_tenant_id", table_name="dispatch_campaigns")
    op.drop_table("dispatch_campaigns")
