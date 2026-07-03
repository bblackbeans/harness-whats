"""initial saas platform schema

Revision ID: 001
Revises:
Create Date: 2026-07-01
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "admin_users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("email", sa.String(255), nullable=False, unique=True),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("role", sa.String(50), server_default="super_admin"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_table(
        "tenants",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("language", sa.String(16), server_default="pt-BR"),
        sa.Column("active", sa.Boolean(), server_default=sa.text("true")),
        sa.Column("settings", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_table(
        "tenant_prompts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.String(64), sa.ForeignKey("tenants.id", ondelete="CASCADE")),
        sa.Column("name", sa.String(64), nullable=False),
        sa.Column("content", sa.Text(), server_default=""),
        sa.UniqueConstraint("tenant_id", "name", name="uq_tenant_prompt"),
    )
    op.create_table(
        "llm_providers",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("provider_type", sa.String(32), server_default="openai"),
        sa.Column("encrypted_api_key", sa.Text(), server_default=""),
        sa.Column("active", sa.Boolean(), server_default=sa.text("true")),
    )
    op.create_table(
        "llm_models",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("provider_id", sa.Integer(), sa.ForeignKey("llm_providers.id", ondelete="CASCADE")),
        sa.Column("model_id", sa.String(128), nullable=False),
        sa.Column("display_name", sa.String(255), nullable=False),
        sa.Column("cost_per_1m_input", sa.Float(), server_default="0"),
        sa.Column("cost_per_1m_output", sa.Float(), server_default="0"),
        sa.Column("temperature_default", sa.Float(), server_default="0.3"),
    )
    op.create_table(
        "tenant_allowed_models",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.String(64), sa.ForeignKey("tenants.id", ondelete="CASCADE")),
        sa.Column("model_id", sa.Integer(), sa.ForeignKey("llm_models.id", ondelete="CASCADE")),
        sa.Column("is_default", sa.Boolean(), server_default=sa.text("false")),
        sa.UniqueConstraint("tenant_id", "model_id", name="uq_tenant_model"),
    )
    op.create_table(
        "usage_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.String(64), sa.ForeignKey("tenants.id", ondelete="SET NULL"), nullable=True),
        sa.Column("model_ref", sa.String(128), server_default=""),
        sa.Column("tokens_in", sa.Integer(), server_default="0"),
        sa.Column("tokens_out", sa.Integer(), server_default="0"),
        sa.Column("cost_estimate", sa.Float(), server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("usage_events")
    op.drop_table("tenant_allowed_models")
    op.drop_table("llm_models")
    op.drop_table("llm_providers")
    op.drop_table("tenant_prompts")
    op.drop_table("tenants")
    op.drop_table("admin_users")
