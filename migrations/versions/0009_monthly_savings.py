"""Add persisted monthly savings.

Revision ID: 0009_monthly_savings
Revises: 0008_user_summary_time
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0009_monthly_savings"
down_revision: str | None = "0008_user_summary_time"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "monthly_savings",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("year", sa.SmallInteger(), nullable=False),
        sa.Column("month", sa.SmallInteger(), nullable=False),
        sa.Column("amount_minor", sa.BigInteger(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "month BETWEEN 1 AND 12",
            name="ck_monthly_savings_month",
        ),
        sa.CheckConstraint(
            "amount_minor >= 0",
            name="ck_monthly_savings_amount_non_negative",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "user_id",
            "year",
            "month",
            name="uq_monthly_savings_user_period",
        ),
    )
    op.create_index(
        "ix_monthly_savings_user_id",
        "monthly_savings",
        ["user_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_monthly_savings_user_id", table_name="monthly_savings")
    op.drop_table("monthly_savings")
