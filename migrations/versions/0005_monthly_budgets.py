"""Add recurring monthly category budgets.

Revision ID: 0005_monthly_budgets
Revises: 0004_subscriptions
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005_monthly_budgets"
down_revision: str | None = "0004_subscriptions"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "monthly_budgets",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("category_id", sa.Uuid(), nullable=False),
        sa.Column("limit_minor", sa.BigInteger(), nullable=False),
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
            "limit_minor > 0",
            name="ck_monthly_budgets_limit_positive",
        ),
        sa.ForeignKeyConstraint(
            ["category_id"],
            ["categories.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "user_id",
            "category_id",
            name="uq_monthly_budgets_user_category",
        ),
    )
    op.create_index(
        "ix_monthly_budgets_category_id",
        "monthly_budgets",
        ["category_id"],
    )
    op.create_index(
        "ix_monthly_budgets_user_id",
        "monthly_budgets",
        ["user_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_monthly_budgets_user_id", table_name="monthly_budgets")
    op.drop_index("ix_monthly_budgets_category_id", table_name="monthly_budgets")
    op.drop_table("monthly_budgets")
