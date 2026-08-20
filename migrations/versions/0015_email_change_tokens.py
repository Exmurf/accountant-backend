"""Add single-use email change tokens.

Revision ID: 0015_email_changes
Revises: 0014_password_resets
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0015_email_changes"
down_revision: str | None = "0014_password_resets"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "email_change_tokens",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("new_email", sa.String(length=320), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_email_change_tokens_token_hash",
        "email_change_tokens",
        ["token_hash"],
        unique=True,
    )
    op.create_index(
        "ix_email_change_tokens_user_id",
        "email_change_tokens",
        ["user_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_email_change_tokens_user_id", table_name="email_change_tokens")
    op.drop_index("ix_email_change_tokens_token_hash", table_name="email_change_tokens")
    op.drop_table("email_change_tokens")
