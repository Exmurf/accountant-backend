"""Record when a user last changed their password.

Revision ID: 0012_password_changed
Revises: 0011_opening_balance
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0012_password_changed"
down_revision: str | None = "0011_opening_balance"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("password_changed_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("users", "password_changed_at")
