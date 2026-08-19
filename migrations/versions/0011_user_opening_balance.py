"""Add a per-user opening balance.

Revision ID: 0011_opening_balance
Revises: 0010_signed_savings
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0011_opening_balance"
down_revision: str | None = "0010_signed_savings"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "opening_balance_minor",
            sa.BigInteger(),
            server_default="0",
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("users", "opening_balance_minor")
