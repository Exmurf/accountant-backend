from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from app.domain.ledger.budget import MonthlyBudget
from app.domain.ledger.models import Category, Transaction, TransactionKind
from app.domain.ledger.subscription import Subscription


class CreateCategoryRequest(BaseModel):
    name: str = Field(min_length=2, max_length=80)
    kind: TransactionKind
    color: str = Field(pattern=r"^#[0-9a-fA-F]{6}$")


class CategoryResponse(BaseModel):
    id: UUID
    name: str
    kind: TransactionKind
    color: str
    is_default: bool

    @classmethod
    def from_domain(cls, category: Category) -> "CategoryResponse":
        return cls(
            id=category.id,
            name=category.name,
            kind=category.kind,
            color=category.color,
            is_default=category.user_id is None,
        )


class CreateTransactionRequest(BaseModel):
    category_id: UUID
    kind: TransactionKind
    amount: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    description: str = Field(min_length=1, max_length=200)
    occurred_at: datetime

    @field_validator("occurred_at")
    @classmethod
    def occurred_at_must_have_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("occurred_at must include a timezone")
        return value

    def amount_as_minor(self) -> int:
        return int(self.amount * 100)


class TransactionResponse(BaseModel):
    id: UUID
    category_id: UUID
    category_name: str
    category_color: str
    kind: TransactionKind
    amount_minor: int
    description: str
    occurred_at: datetime
    created_at: datetime
    subscription_id: UUID | None
    subscription_charge_date: date | None

    @classmethod
    def from_domain(cls, transaction: Transaction) -> "TransactionResponse":
        return cls(
            id=transaction.id,
            category_id=transaction.category_id,
            category_name=transaction.category_name,
            category_color=transaction.category_color,
            kind=transaction.kind,
            amount_minor=transaction.amount_minor,
            description=transaction.description,
            occurred_at=transaction.occurred_at,
            created_at=transaction.created_at,
            subscription_id=transaction.subscription_id,
            subscription_charge_date=transaction.subscription_charge_date,
        )


class CreateSubscriptionRequest(BaseModel):
    category_id: UUID
    name: str = Field(min_length=2, max_length=120)
    amount: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    first_charge_date: date

    def amount_as_minor(self) -> int:
        return int(self.amount * 100)


class UpdateSubscriptionPriceRequest(BaseModel):
    amount: Decimal = Field(gt=0, max_digits=12, decimal_places=2)

    def amount_as_minor(self) -> int:
        return int(self.amount * 100)


class SubscriptionResponse(BaseModel):
    id: UUID
    category_id: UUID
    category_name: str
    category_color: str
    name: str
    amount_minor: int
    billing_day: int
    next_charge_date: date

    @classmethod
    def from_domain(cls, subscription: Subscription) -> "SubscriptionResponse":
        return cls(
            id=subscription.id,
            category_id=subscription.category_id,
            category_name=subscription.category_name,
            category_color=subscription.category_color,
            name=subscription.name,
            amount_minor=subscription.amount_minor,
            billing_day=subscription.billing_day,
            next_charge_date=subscription.next_charge_date,
        )


class SuccessResponse(BaseModel):
    success: bool = True


class SetMonthlyBudgetRequest(BaseModel):
    limit: Decimal = Field(gt=0, max_digits=12, decimal_places=2)

    def limit_as_minor(self) -> int:
        return int(self.limit * 100)


class MonthlyBudgetResponse(BaseModel):
    id: UUID
    category_id: UUID
    category_name: str
    category_color: str
    limit_minor: int

    @classmethod
    def from_domain(cls, budget: MonthlyBudget) -> "MonthlyBudgetResponse":
        return cls(
            id=budget.id,
            category_id=budget.category_id,
            category_name=budget.category_name,
            category_color=budget.category_color,
            limit_minor=budget.limit_minor,
        )
