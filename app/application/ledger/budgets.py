from uuid import UUID

from app.application.ledger.errors import (
    BudgetNotFoundError,
    CategoryKindMismatchError,
    CategoryNotFoundError,
)
from app.application.ledger.ports import BudgetRepository, CategoryRepository
from app.domain.ledger.budget import MonthlyBudget
from app.domain.ledger.models import TransactionKind


class ListMonthlyBudgets:
    def __init__(self, budgets: BudgetRepository) -> None:
        self._budgets = budgets

    def execute(self, user_id: UUID) -> list[MonthlyBudget]:
        return self._budgets.list_for_user(user_id)


class SetMonthlyBudget:
    def __init__(
        self,
        categories: CategoryRepository,
        budgets: BudgetRepository,
    ) -> None:
        self._categories = categories
        self._budgets = budgets

    def execute(
        self,
        user_id: UUID,
        category_id: UUID,
        limit_minor: int,
    ) -> MonthlyBudget:
        category = self._categories.get_available_by_id(user_id, category_id)
        if category is None:
            raise CategoryNotFoundError
        if category.kind != TransactionKind.EXPENSE:
            raise CategoryKindMismatchError
        return self._budgets.upsert(user_id, category, limit_minor)


class RemoveMonthlyBudget:
    def __init__(self, budgets: BudgetRepository) -> None:
        self._budgets = budgets

    def execute(self, user_id: UUID, category_id: UUID) -> None:
        if not self._budgets.remove(user_id, category_id):
            raise BudgetNotFoundError
