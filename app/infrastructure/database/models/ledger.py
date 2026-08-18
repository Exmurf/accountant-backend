from datetime import date, datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    String,
    SmallInteger,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.database.base import Base


class CategoryModel(Base):
    __tablename__ = "categories"
    __table_args__ = (
        CheckConstraint("kind IN ('INCOME', 'EXPENSE')", name="ck_categories_kind"),
        UniqueConstraint(
            "user_id",
            "name",
            "kind",
            name="uq_categories_user_name_kind",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    user_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
    )
    name: Mapped[str] = mapped_column(String(80))
    kind: Mapped[str] = mapped_column(String(10))
    color: Mapped[str] = mapped_column(String(7))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    transactions: Mapped[list["TransactionModel"]] = relationship(
        back_populates="category"
    )
    subscriptions: Mapped[list["SubscriptionModel"]] = relationship(
        back_populates="category"
    )


class SubscriptionModel(Base):
    __tablename__ = "subscriptions"
    __table_args__ = (
        CheckConstraint(
            "amount_minor > 0",
            name="ck_subscriptions_amount_positive",
        ),
        CheckConstraint(
            "billing_day BETWEEN 1 AND 31",
            name="ck_subscriptions_billing_day",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    user_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
    )
    category_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("categories.id", ondelete="RESTRICT"),
        index=True,
    )
    name: Mapped[str] = mapped_column(String(120))
    amount_minor: Mapped[int] = mapped_column(BigInteger)
    billing_day: Mapped[int] = mapped_column(SmallInteger)
    next_charge_date: Mapped[date] = mapped_column(Date, index=True)
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        server_default="true",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )
    category: Mapped[CategoryModel] = relationship(back_populates="subscriptions")
    transactions: Mapped[list["TransactionModel"]] = relationship(
        back_populates="subscription"
    )


class MonthlyBudgetModel(Base):
    __tablename__ = "monthly_budgets"
    __table_args__ = (
        CheckConstraint(
            "limit_minor > 0",
            name="ck_monthly_budgets_limit_positive",
        ),
        UniqueConstraint(
            "user_id",
            "category_id",
            name="uq_monthly_budgets_user_category",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    user_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
    )
    category_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("categories.id", ondelete="CASCADE"),
        index=True,
    )
    limit_minor: Mapped[int] = mapped_column(BigInteger)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )
    category: Mapped[CategoryModel] = relationship()


class TransactionModel(Base):
    __tablename__ = "transactions"
    __table_args__ = (
        CheckConstraint("kind IN ('INCOME', 'EXPENSE')", name="ck_transactions_kind"),
        CheckConstraint("amount_minor > 0", name="ck_transactions_amount_positive"),
        UniqueConstraint(
            "subscription_id",
            "subscription_charge_date",
            name="uq_transactions_subscription_charge",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    user_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
    )
    category_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("categories.id", ondelete="RESTRICT"),
        index=True,
    )
    kind: Mapped[str] = mapped_column(String(10))
    amount_minor: Mapped[int] = mapped_column(BigInteger)
    description: Mapped[str] = mapped_column(String(200))
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    subscription_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("subscriptions.id", ondelete="SET NULL"),
        index=True,
    )
    subscription_charge_date: Mapped[date | None] = mapped_column(Date)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    category: Mapped[CategoryModel] = relationship(back_populates="transactions")
    subscription: Mapped[SubscriptionModel | None] = relationship(
        back_populates="transactions"
    )
