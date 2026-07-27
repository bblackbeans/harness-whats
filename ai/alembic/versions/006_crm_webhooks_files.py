"""Migration 006: contact profiles, custom fields, webhooks, http tools, sendable files

Revision ID: 006
Revises: 005
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "006"
down_revision: Union[str, None] = "005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "tenant_custom_fields",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.String(64), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("key", sa.String(64), nullable=False),
        sa.Column("label", sa.String(255), nullable=False),
        sa.Column("field_type", sa.String(32), server_default="text"),
        sa.Column("required", sa.Boolean(), server_default=sa.text("false")),
        sa.Column("sort_order", sa.Integer(), server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("tenant_id", "key", name="uq_tenant_custom_field_key"),
    )
    op.create_index("ix_tenant_custom_fields_tenant_id", "tenant_custom_fields", ["tenant_id"])

    op.create_table(
        "contact_profiles",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.String(64), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("phone", sa.String(32), nullable=False),
        sa.Column("name", sa.String(255), server_default=""),
        sa.Column("email", sa.String(255), server_default=""),
        sa.Column("fields", JSONB(), server_default=sa.text("'{}'::jsonb")),
        sa.Column("chatwoot_contact_id", sa.Integer(), nullable=True),
        sa.Column("last_conversation_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("tenant_id", "phone", name="uq_contact_tenant_phone"),
    )
    op.create_index("ix_contact_profiles_tenant_id", "contact_profiles", ["tenant_id"])
    op.create_index("ix_contact_profiles_phone", "contact_profiles", ["phone"])

    op.create_table(
        "tenant_inbound_webhooks",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.String(64), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("slug", sa.String(64), nullable=False),
        sa.Column("secret", sa.String(128), nullable=False),
        sa.Column("field_mapping", JSONB(), server_default=sa.text("'{}'::jsonb")),
        sa.Column("start_conversation", sa.Boolean(), server_default=sa.text("false")),
        sa.Column("initial_message", sa.Text(), server_default=""),
        sa.Column("active", sa.Boolean(), server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("tenant_id", "slug", name="uq_tenant_webhook_slug"),
    )
    op.create_index("ix_tenant_inbound_webhooks_tenant_id", "tenant_inbound_webhooks", ["tenant_id"])

    op.create_table(
        "tenant_http_tools",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.String(64), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("slug", sa.String(64), nullable=False),
        sa.Column("method", sa.String(16), server_default="POST"),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("headers", JSONB(), server_default=sa.text("'{}'::jsonb")),
        sa.Column("body_template", sa.Text(), server_default=""),
        sa.Column("include_fields", JSONB(), server_default=sa.text("'[]'::jsonb")),
        sa.Column("auth_header", sa.String(512), server_default=""),
        sa.Column("description", sa.Text(), server_default=""),
        sa.Column("active", sa.Boolean(), server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("tenant_id", "slug", name="uq_tenant_http_tool_slug"),
    )
    op.create_index("ix_tenant_http_tools_tenant_id", "tenant_http_tools", ["tenant_id"])

    op.create_table(
        "tenant_sendable_files",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.String(64), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("filename", sa.String(255), nullable=False),
        sa.Column("original_name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), server_default=""),
        sa.Column("mime_type", sa.String(128), server_default="application/octet-stream"),
        sa.Column("size_bytes", sa.Integer(), server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_tenant_sendable_files_tenant_id", "tenant_sendable_files", ["tenant_id"])


def downgrade() -> None:
    op.drop_index("ix_tenant_sendable_files_tenant_id", table_name="tenant_sendable_files")
    op.drop_table("tenant_sendable_files")
    op.drop_index("ix_tenant_http_tools_tenant_id", table_name="tenant_http_tools")
    op.drop_table("tenant_http_tools")
    op.drop_index("ix_tenant_inbound_webhooks_tenant_id", table_name="tenant_inbound_webhooks")
    op.drop_table("tenant_inbound_webhooks")
    op.drop_index("ix_contact_profiles_phone", table_name="contact_profiles")
    op.drop_index("ix_contact_profiles_tenant_id", table_name="contact_profiles")
    op.drop_table("contact_profiles")
    op.drop_index("ix_tenant_custom_fields_tenant_id", table_name="tenant_custom_fields")
    op.drop_table("tenant_custom_fields")
