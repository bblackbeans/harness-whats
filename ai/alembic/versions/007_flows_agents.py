"""Migration 007: tenant_agents, flows, flow_runs + seed default agents from agent_system

Revision ID: 007
Revises: 006
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "007"
down_revision: Union[str, None] = "006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "tenant_agents",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.String(64), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("description", sa.Text(), server_default=""),
        sa.Column("system_prompt", sa.Text(), server_default=""),
        sa.Column("is_default", sa.Boolean(), server_default=sa.text("false")),
        sa.Column("active", sa.Boolean(), server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_tenant_agents_tenant_id", "tenant_agents", ["tenant_id"])

    op.create_table(
        "flows",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.String(64), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("agent_id", sa.Integer(), sa.ForeignKey("tenant_agents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), server_default=""),
        sa.Column("base_prompt", sa.Text(), server_default=""),
        sa.Column("status", sa.String(32), server_default="draft"),
        sa.Column("is_default", sa.Boolean(), server_default=sa.text("false")),
        sa.Column("source_filename", sa.String(255), server_default=""),
        sa.Column("source_raw", sa.Text(), server_default=""),
        sa.Column("import_summary", JSONB(), server_default=sa.text("'{}'::jsonb")),
        sa.Column("roteiro", JSONB(), server_default=sa.text("'{}'::jsonb")),
        sa.Column("checklist", JSONB(), server_default=sa.text("'[]'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_flows_tenant_id", "flows", ["tenant_id"])
    op.create_index("ix_flows_agent_id", "flows", ["agent_id"])

    op.create_table(
        "flow_runs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.String(64), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("flow_id", sa.Integer(), sa.ForeignKey("flows.id", ondelete="CASCADE"), nullable=False),
        sa.Column("conversation_id", sa.Integer(), nullable=False),
        sa.Column("phone", sa.String(32), server_default=""),
        sa.Column("checklist_state", JSONB(), server_default=sa.text("'{}'::jsonb")),
        sa.Column("current_step_id", sa.String(128), server_default=""),
        sa.Column("variables", JSONB(), server_default=sa.text("'{}'::jsonb")),
        sa.Column("tools_log", JSONB(), server_default=sa.text("'[]'::jsonb")),
        sa.Column("status", sa.String(32), server_default="active"),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("tenant_id", "conversation_id", "flow_id", name="uq_flow_run_conversation"),
    )
    op.create_index("ix_flow_runs_tenant_id", "flow_runs", ["tenant_id"])
    op.create_index("ix_flow_runs_flow_id", "flow_runs", ["flow_id"])
    op.create_index("ix_flow_runs_conversation_id", "flow_runs", ["conversation_id"])

    # Seed default agent per tenant from agent_system prompt
    conn = op.get_bind()
    tenants = conn.execute(sa.text("SELECT id, name FROM tenants")).fetchall()
    for tenant_id, tenant_name in tenants:
        prompt_row = conn.execute(
            sa.text(
                "SELECT content FROM tenant_prompts WHERE tenant_id = :tid AND name = 'agent_system' LIMIT 1"
            ),
            {"tid": tenant_id},
        ).fetchone()
        prompt = (prompt_row[0] if prompt_row else "") or (
            "Você é um assistente virtual de atendimento por mensagem. "
            "Responda em português do Brasil de forma natural e útil."
        )
        # Skip if already has a default agent (idempotent-ish)
        existing = conn.execute(
            sa.text(
                "SELECT id FROM tenant_agents WHERE tenant_id = :tid AND is_default = true LIMIT 1"
            ),
            {"tid": tenant_id},
        ).fetchone()
        if existing:
            continue
        conn.execute(
            sa.text(
                """
                INSERT INTO tenant_agents (tenant_id, name, description, system_prompt, is_default, active)
                VALUES (:tid, :name, :desc, :prompt, true, true)
                """
            ),
            {
                "tid": tenant_id,
                "name": "Agente padrão",
                "desc": f"Agente principal de {tenant_name}",
                "prompt": prompt,
            },
        )


def downgrade() -> None:
    op.drop_index("ix_flow_runs_conversation_id", table_name="flow_runs")
    op.drop_index("ix_flow_runs_flow_id", table_name="flow_runs")
    op.drop_index("ix_flow_runs_tenant_id", table_name="flow_runs")
    op.drop_table("flow_runs")
    op.drop_index("ix_flows_agent_id", table_name="flows")
    op.drop_index("ix_flows_tenant_id", table_name="flows")
    op.drop_table("flows")
    op.drop_index("ix_tenant_agents_tenant_id", table_name="tenant_agents")
    op.drop_table("tenant_agents")
