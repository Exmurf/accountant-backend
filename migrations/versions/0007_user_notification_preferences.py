"""Add user notification preferences.

Revision ID: 0007_user_mail_preferences
Revises: 0006_notification_deliveries
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0007_user_mail_preferences"
down_revision: str | None = "0006_notification_deliveries"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "daily_summary_enabled",
            sa.Boolean(),
            server_default=sa.true(),
            nullable=False,
        ),
    )
    op.add_column(
        "users",
        sa.Column(
            "budget_alerts_enabled",
            sa.Boolean(),
            server_default=sa.true(),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("users", "budget_alerts_enabled")
    op.drop_column("users", "daily_summary_enabled")
