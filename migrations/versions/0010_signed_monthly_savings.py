"""Allow monthly savings to decrease in deficit months.

Revision ID: 0010_signed_savings
Revises: 0009_monthly_savings
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0010_signed_savings"
down_revision: str | None = "0009_monthly_savings"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint(
        "ck_monthly_savings_amount_non_negative",
        "monthly_savings",
        type_="check",
    )


def downgrade() -> None:
    op.create_check_constraint(
        "ck_monthly_savings_amount_non_negative",
        "monthly_savings",
        "amount_minor >= 0",
    )
