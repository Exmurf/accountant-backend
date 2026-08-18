"""Add per-user daily summary time.

Revision ID: 0008_user_summary_time
Revises: 0007_user_mail_preferences
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0008_user_summary_time"
down_revision: str | None = "0007_user_mail_preferences"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "daily_summary_time",
            sa.Time(),
            server_default=sa.text("'21:00:00'"),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("users", "daily_summary_time")
