"""Migration 009: agent_tools — tools editáveis por agente (regras + endpoint)

Revision ID: 009
Revises: 008
"""

from __future__ import annotations

import json
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "009"
down_revision: Union[str, None] = "008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "agent_tools",
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
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("slug", sa.String(64), nullable=False),
        sa.Column("kind", sa.String(32), server_default="http", nullable=False),
        sa.Column("rules", sa.Text(), server_default=""),
        sa.Column("method", sa.String(16), server_default="POST"),
        sa.Column("url", sa.Text(), server_default=""),
        sa.Column("headers", JSONB(), server_default=sa.text("'{}'::jsonb")),
        sa.Column("body_template", sa.Text(), server_default=""),
        sa.Column("auth_header", sa.String(512), server_default=""),
        sa.Column("active", sa.Boolean(), server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("agent_id", "slug", name="uq_agent_tool_slug"),
    )
    op.create_index("ix_agent_tools_tenant", "agent_tools", ["tenant_id"])
    op.create_index("ix_agent_tools_agent", "agent_tools", ["agent_id"])

    conn = op.get_bind()
    bindings = conn.execute(
        sa.text(
            "SELECT tenant_id, agent_id, tool_kind, tool_ref FROM agent_tool_bindings"
        )
    ).fetchall()

    kind_labels = {
        "save_field": (
            "Salvar campo",
            "Salve no perfil do contato os dados que o cliente informar (field_updates).",
        ),
        "send_file": (
            "Enviar arquivo",
            "Envie arquivos da biblioteca quando o cliente pedir ou o roteiro indicar (files_to_send).",
        ),
        "handoff": (
            "Transferir humano",
            "Transfira para atendente humano quando o cliente pedir ou o caso exigir (handoff_to_human).",
        ),
        "transfer_agent": (
            "Transferir agente",
            "Transfira para outro especialista quando o assunto mudar (transfer_to_agent).",
        ),
    }

    insert_sql = sa.text(
        """
        INSERT INTO agent_tools
          (tenant_id, agent_id, name, slug, kind, rules, method, url, headers, body_template, auth_header, active)
        VALUES
          (:tid, :aid, :name, :slug, :kind, :rules, :method, :url, CAST(:headers AS jsonb), :body, :auth, true)
        ON CONFLICT ON CONSTRAINT uq_agent_tool_slug DO NOTHING
        """
    )

    for tenant_id, agent_id, tool_kind, tool_ref in bindings:
        if tool_kind == "http":
            slug = str(tool_ref or "http")[:64]
            http = conn.execute(
                sa.text(
                    "SELECT name, method, url, headers, body_template, auth_header, description "
                    "FROM tenant_http_tools WHERE tenant_id = :tid AND slug = :slug LIMIT 1"
                ),
                {"tid": tenant_id, "slug": slug},
            ).fetchone()
            if http:
                name, method, url, headers, body_template, auth_header, description = http
                conn.execute(
                    insert_sql,
                    {
                        "tid": tenant_id,
                        "aid": agent_id,
                        "name": name or slug,
                        "slug": slug,
                        "kind": "http",
                        "rules": description or f"Chame a API {slug} quando necessário no atendimento.",
                        "method": method or "POST",
                        "url": url or "",
                        "headers": json.dumps(headers or {}),
                        "body": body_template or "",
                        "auth": auth_header or "",
                    },
                )
            else:
                conn.execute(
                    insert_sql,
                    {
                        "tid": tenant_id,
                        "aid": agent_id,
                        "name": slug,
                        "slug": slug,
                        "kind": "http",
                        "rules": f"Use a integração '{slug}' quando fizer sentido.",
                        "method": "POST",
                        "url": "",
                        "headers": "{}",
                        "body": "",
                        "auth": "",
                    },
                )
        elif tool_kind in kind_labels:
            name, rules = kind_labels[tool_kind]
            conn.execute(
                insert_sql,
                {
                    "tid": tenant_id,
                    "aid": agent_id,
                    "name": name,
                    "slug": tool_kind,
                    "kind": tool_kind,
                    "rules": rules,
                    "method": "POST",
                    "url": "",
                    "headers": "{}",
                    "body": "",
                    "auth": "",
                },
            )


def downgrade() -> None:
    op.drop_index("ix_agent_tools_agent", table_name="agent_tools")
    op.drop_index("ix_agent_tools_tenant", table_name="agent_tools")
    op.drop_table("agent_tools")
