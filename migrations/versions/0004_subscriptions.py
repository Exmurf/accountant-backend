"""Add recurring subscriptions.

Revision ID: 0004_subscriptions
Revises: 0003_ledger_core
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004_subscriptions"
down_revision: str | None = "0003_ledger_core"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "subscriptions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("category_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("amount_minor", sa.BigInteger(), nullable=False),
        sa.Column("billing_day", sa.SmallInteger(), nullable=False),
        sa.Column("next_charge_date", sa.Date(), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False),
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
            "amount_minor > 0",
            name="ck_subscriptions_amount_positive",
        ),
        sa.CheckConstraint(
            "billing_day BETWEEN 1 AND 31",
            name="ck_subscriptions_billing_day",
        ),
        sa.ForeignKeyConstraint(
            ["category_id"],
            ["categories.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_subscriptions_category_id",
        "subscriptions",
        ["category_id"],
    )
    op.create_index(
        "ix_subscriptions_next_charge_date",
        "subscriptions",
        ["next_charge_date"],
    )
    op.create_index("ix_subscriptions_user_id", "subscriptions", ["user_id"])

    op.add_column("transactions", sa.Column("subscription_id", sa.Uuid()))
    op.add_column(
        "transactions",
        sa.Column("subscription_charge_date", sa.Date()),
    )
    op.create_foreign_key(
        "fk_transactions_subscription_id",
        "transactions",
        "subscriptions",
        ["subscription_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_transactions_subscription_id",
        "transactions",
        ["subscription_id"],
    )
    op.create_unique_constraint(
        "uq_transactions_subscription_charge",
        "transactions",
        ["subscription_id", "subscription_charge_date"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_transactions_subscription_charge",
        "transactions",
        type_="unique",
    )
    op.drop_index("ix_transactions_subscription_id", table_name="transactions")
    op.drop_constraint(
        "fk_transactions_subscription_id",
        "transactions",
        type_="foreignkey",
    )
    op.drop_column("transactions", "subscription_charge_date")
    op.drop_column("transactions", "subscription_id")
    op.drop_index("ix_subscriptions_user_id", table_name="subscriptions")
    op.drop_index("ix_subscriptions_next_charge_date", table_name="subscriptions")
    op.drop_index("ix_subscriptions_category_id", table_name="subscriptions")
    op.drop_table("subscriptions")
