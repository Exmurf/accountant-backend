"""Add categories and transactions.

Revision ID: 0003_ledger_core
Revises: 0002_refresh_tokens
"""

from collections.abc import Sequence
from uuid import UUID

import sqlalchemy as sa
from alembic import op

revision: str = "0003_ledger_core"
down_revision: str | None = "0002_refresh_tokens"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "categories",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=True),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column("kind", sa.String(length=10), nullable=False),
        sa.Column("color", sa.String(length=7), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "kind IN ('INCOME', 'EXPENSE')",
            name="ck_categories_kind",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "user_id",
            "name",
            "kind",
            name="uq_categories_user_name_kind",
        ),
    )
    op.create_index("ix_categories_user_id", "categories", ["user_id"])

    op.create_table(
        "transactions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("category_id", sa.Uuid(), nullable=False),
        sa.Column("kind", sa.String(length=10), nullable=False),
        sa.Column("amount_minor", sa.BigInteger(), nullable=False),
        sa.Column("description", sa.String(length=200), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "amount_minor > 0",
            name="ck_transactions_amount_positive",
        ),
        sa.CheckConstraint(
            "kind IN ('INCOME', 'EXPENSE')",
            name="ck_transactions_kind",
        ),
        sa.ForeignKeyConstraint(
            ["category_id"],
            ["categories.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_transactions_category_id", "transactions", ["category_id"])
    op.create_index("ix_transactions_occurred_at", "transactions", ["occurred_at"])
    op.create_index("ix_transactions_user_id", "transactions", ["user_id"])
    op.create_index(
        "ix_transactions_user_occurred_at",
        "transactions",
        ["user_id", "occurred_at"],
    )

    categories = sa.table(
        "categories",
        sa.column("id", sa.Uuid()),
        sa.column("user_id", sa.Uuid()),
        sa.column("name", sa.String()),
        sa.column("kind", sa.String()),
        sa.column("color", sa.String()),
    )
    op.bulk_insert(
        categories,
        [
            {
                "id": UUID("10000000-0000-0000-0000-000000000001"),
                "user_id": None,
                "name": "Maaş",
                "kind": "INCOME",
                "color": "#2d8066",
            },
            {
                "id": UUID("10000000-0000-0000-0000-000000000002"),
                "user_id": None,
                "name": "Ek gelir",
                "kind": "INCOME",
                "color": "#65a98f",
            },
            {
                "id": UUID("20000000-0000-0000-0000-000000000001"),
                "user_id": None,
                "name": "Yemek",
                "kind": "EXPENSE",
                "color": "#ec8c5a",
            },
            {
                "id": UUID("20000000-0000-0000-0000-000000000002"),
                "user_id": None,
                "name": "Eğlence",
                "kind": "EXPENSE",
                "color": "#e8bb4f",
            },
            {
                "id": UUID("20000000-0000-0000-0000-000000000003"),
                "user_id": None,
                "name": "Abonelik",
                "kind": "EXPENSE",
                "color": "#8c7ab8",
            },
            {
                "id": UUID("20000000-0000-0000-0000-000000000004"),
                "user_id": None,
                "name": "Konut",
                "kind": "EXPENSE",
                "color": "#265e55",
            },
            {
                "id": UUID("20000000-0000-0000-0000-000000000005"),
                "user_id": None,
                "name": "Ulaşım",
                "kind": "EXPENSE",
                "color": "#4f7fa5",
            },
            {
                "id": UUID("20000000-0000-0000-0000-000000000006"),
                "user_id": None,
                "name": "Sağlık",
                "kind": "EXPENSE",
                "color": "#bb6f78",
            },
            {
                "id": UUID("20000000-0000-0000-0000-000000000007"),
                "user_id": None,
                "name": "Diğer",
                "kind": "EXPENSE",
                "color": "#7b8580",
            },
        ],
    )


def downgrade() -> None:
    op.drop_index("ix_transactions_user_occurred_at", table_name="transactions")
    op.drop_index("ix_transactions_user_id", table_name="transactions")
    op.drop_index("ix_transactions_occurred_at", table_name="transactions")
    op.drop_index("ix_transactions_category_id", table_name="transactions")
    op.drop_table("transactions")
    op.drop_index("ix_categories_user_id", table_name="categories")
    op.drop_table("categories")
