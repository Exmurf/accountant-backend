"""Add a per-user savings goal.

Revision ID: 0013_savings_goal
Revises: 0012_password_changed
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0013_savings_goal"
down_revision: str | None = "0012_password_changed"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "savings_goal_minor",
            sa.BigInteger(),
            server_default="0",
            nullable=False,
        ),
    )
    op.create_check_constraint(
        "ck_users_savings_goal_non_negative",
        "users",
        "savings_goal_minor >= 0",
    )


def downgrade() -> None:
    op.drop_constraint("ck_users_savings_goal_non_negative", "users", type_="check")
    op.drop_column("users", "savings_goal_minor")
