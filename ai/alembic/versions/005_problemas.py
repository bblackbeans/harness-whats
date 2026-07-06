"""Migration 005: problemas (feedback do portal)

Revision ID: 005
Revises: 004
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "005"
down_revision: Union[str, None] = "004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "problemas",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(64), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("usuario_id", sa.Integer(), sa.ForeignKey("tenant_users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("titulo", sa.String(200), nullable=False),
        sa.Column("descricao", sa.Text(), nullable=False),
        sa.Column("passos", sa.Text(), server_default=""),
        sa.Column("origem", sa.String(32), server_default="feedback"),
        sa.Column("status", sa.String(32), server_default="novo"),
        sa.Column("url", sa.String(2048), server_default=""),
        sa.Column("correlation_id", sa.String(36), nullable=False),
        sa.Column("contexto_json", JSONB(), server_default=sa.text("'{}'::jsonb")),
        sa.Column("notas_internas", sa.Text(), server_default=""),
        sa.Column("criado_em", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("atualizado_em", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_problemas_tenant_id", "problemas", ["tenant_id"])
    op.create_index("ix_problemas_status", "problemas", ["status"])
    op.create_index("ix_problemas_criado_em", "problemas", ["criado_em"])


def downgrade() -> None:
    op.drop_index("ix_problemas_criado_em", table_name="problemas")
    op.drop_index("ix_problemas_status", table_name="problemas")
    op.drop_index("ix_problemas_tenant_id", table_name="problemas")
    op.drop_table("problemas")
