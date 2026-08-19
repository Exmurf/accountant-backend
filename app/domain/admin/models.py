from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from app.domain.ledger.models import Transaction
from app.domain.ledger.subscription import Subscription


@dataclass(frozen=True, slots=True)
class UserFinanceTotals:
    total_income_minor: int
    total_expense_minor: int
    transaction_count: int
    opening_balance_minor: int = 0

    @property
    def current_balance_minor(self) -> int:
        return (
            self.opening_balance_minor
            + self.total_income_minor
            - self.total_expense_minor
        )


@dataclass(frozen=True, slots=True)
class AdminUserSummary:
    id: UUID
    email: str
    display_name: str
    is_active: bool
    roles: tuple[str, ...]
    created_at: datetime
    finances: UserFinanceTotals


@dataclass(frozen=True, slots=True)
class AdminCategorySpending:
    category_id: UUID
    category_name: str
    category_color: str
    total_expense_minor: int


@dataclass(frozen=True, slots=True)
class AdminUserFinanceDetails:
    user_id: UUID
    recent_transactions: tuple[Transaction, ...]
    category_spending: tuple[AdminCategorySpending, ...]
    subscriptions: tuple[Subscription, ...]
