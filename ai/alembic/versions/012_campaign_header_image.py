"""Migration 012: imagem de cabeçalho em campanhas de template

Revision ID: 012
Revises: 011
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "012"
down_revision: Union[str, None] = "011"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "dispatch_campaigns",
        sa.Column("header_image_url", sa.Text(), server_default="", nullable=False),
    )


def downgrade() -> None:
    op.drop_column("dispatch_campaigns", "header_image_url")
