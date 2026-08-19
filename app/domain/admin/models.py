from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True, slots=True)
class UserFinanceTotals:
    total_income_minor: int
    total_expense_minor: int
    transaction_count: int

    @property
    def current_balance_minor(self) -> int:
        return self.total_income_minor - self.total_expense_minor


@dataclass(frozen=True, slots=True)
class AdminUserSummary:
    id: UUID
    email: str
    display_name: str
    is_active: bool
    roles: tuple[str, ...]
    created_at: datetime
    finances: UserFinanceTotals
