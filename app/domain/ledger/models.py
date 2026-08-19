from dataclasses import dataclass
from datetime import date, datetime
from enum import StrEnum
from uuid import UUID


class TransactionKind(StrEnum):
    INCOME = "INCOME"
    EXPENSE = "EXPENSE"


@dataclass(frozen=True, slots=True)
class AccountBalance:
    total_income_minor: int
    total_expense_minor: int
    opening_balance_minor: int = 0

    @property
    def current_balance_minor(self) -> int:
        return (
            self.opening_balance_minor
            + self.total_income_minor
            - self.total_expense_minor
        )


@dataclass(frozen=True, slots=True)
class Category:
    id: UUID
    user_id: UUID | None
    name: str
    kind: TransactionKind
    color: str


@dataclass(frozen=True, slots=True)
class Transaction:
    id: UUID
    user_id: UUID
    category_id: UUID
    category_name: str
    category_color: str
    kind: TransactionKind
    amount_minor: int
    description: str
    occurred_at: datetime
    created_at: datetime
    subscription_id: UUID | None = None
    subscription_charge_date: date | None = None
