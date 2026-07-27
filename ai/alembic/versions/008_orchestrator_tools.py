"""Migration 008: agent roles, tool bindings, orchestrator seed

Revision ID: 008
Revises: 007
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "008"
down_revision: Union[str, None] = "007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_ORCHESTRATOR_PROMPT = """Você é o orquestrador de atendimento.
Analise a mensagem do cliente e escolha o agente especializado mais adequado.
Responda APENAS com JSON válido (sem markdown):
{"agent_id": <número>, "reason": "<motivo curto>"}
Escolha somente entre os agentes listados. Se estiver em dúvida, prefira o agente padrão/geral.
"""


def upgrade() -> None:
    op.add_column(
        "tenant_agents",
        sa.Column("role", sa.String(32), server_default="specialist", nullable=False),
    )
    op.create_index("ix_tenant_agents_role", "tenant_agents", ["tenant_id", "role"])

    op.create_table(
        "agent_tool_bindings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "tenant_id",
            sa.String(64),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "agent_id",
            sa.Integer(),
            sa.ForeignKey("tenant_agents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("tool_kind", sa.String(32), nullable=False),
        sa.Column("tool_ref", sa.String(128), server_default="*", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint(
            "agent_id", "tool_kind", "tool_ref", name="uq_agent_tool_binding"
        ),
    )
    op.create_index("ix_agent_tool_bindings_agent", "agent_tool_bindings", ["agent_id"])
    op.create_index("ix_agent_tool_bindings_tenant", "agent_tool_bindings", ["tenant_id"])

    conn = op.get_bind()

    # Existing agents are specialists
    conn.execute(sa.text("UPDATE tenant_agents SET role = 'specialist' WHERE role IS NULL OR role = ''"))

    tenants = conn.execute(sa.text("SELECT id FROM tenants")).fetchall()
    for (tenant_id,) in tenants:
        existing_orch = conn.execute(
            sa.text(
                "SELECT id FROM tenant_agents WHERE tenant_id = :tid AND role = 'orchestrator' LIMIT 1"
            ),
            {"tid": tenant_id},
        ).fetchone()
        if existing_orch:
            orch_id = existing_orch[0]
        else:
            result = conn.execute(
                sa.text(
                    """
                    INSERT INTO tenant_agents
                      (tenant_id, name, description, system_prompt, is_default, active, role)
                    VALUES
                      (:tid, 'Orquestrador Principal', 'Roteia a conversa para o agente especializado',
                       :prompt, false, true, 'orchestrator')
                    RETURNING id
                    """
                ),
                {"tid": tenant_id, "prompt": _ORCHESTRATOR_PROMPT},
            )
            orch_id = result.scalar()

        # Bind built-ins + all HTTP tools to every specialist
        specialists = conn.execute(
            sa.text(
                "SELECT id FROM tenant_agents WHERE tenant_id = :tid AND role = 'specialist'"
            ),
            {"tid": tenant_id},
        ).fetchall()
        http_tools = conn.execute(
            sa.text("SELECT slug FROM tenant_http_tools WHERE tenant_id = :tid"),
            {"tid": tenant_id},
        ).fetchall()
        for (agent_id,) in specialists:
            for kind in ("save_field", "send_file", "handoff", "transfer_agent"):
                conn.execute(
                    sa.text(
                        """
                        INSERT INTO agent_tool_bindings (tenant_id, agent_id, tool_kind, tool_ref)
                        VALUES (:tid, :aid, :kind, '*')
                        ON CONFLICT DO NOTHING
                        """
                    ),
                    {"tid": tenant_id, "aid": agent_id, "kind": kind},
                )
            for (slug,) in http_tools:
                conn.execute(
                    sa.text(
                        """
                        INSERT INTO agent_tool_bindings (tenant_id, agent_id, tool_kind, tool_ref)
                        VALUES (:tid, :aid, 'http', :ref)
                        ON CONFLICT DO NOTHING
                        """
                    ),
                    {"tid": tenant_id, "aid": agent_id, "ref": slug},
                )
        _ = orch_id  # ensure orchestrator exists


def downgrade() -> None:
    op.drop_index("ix_agent_tool_bindings_tenant", table_name="agent_tool_bindings")
    op.drop_index("ix_agent_tool_bindings_agent", table_name="agent_tool_bindings")
    op.drop_table("agent_tool_bindings")
    op.drop_index("ix_tenant_agents_role", table_name="tenant_agents")
    op.drop_column("tenant_agents", "role")
