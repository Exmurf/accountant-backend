from datetime import datetime
from uuid import UUID

from app.application.ledger.errors import (
    CategoryKindMismatchError,
    CategoryNotFoundError,
)
from app.application.ledger.ports import CategoryRepository, TransactionRepository
from app.domain.ledger.models import AccountBalance, Transaction, TransactionKind


class GetAccountBalance:
    def __init__(self, transactions: TransactionRepository) -> None:
        self._transactions = transactions

    def execute(self, user_id: UUID, as_of: datetime) -> AccountBalance:
        return self._transactions.get_balance(user_id, as_of)


class ListTransactions:
    def __init__(self, transactions: TransactionRepository) -> None:
        self._transactions = transactions

    def execute(
        self,
        user_id: UUID,
        start: datetime,
        end: datetime,
    ) -> list[Transaction]:
        return self._transactions.list_for_user(user_id, start, end)


class CreateTransaction:
    def __init__(
        self,
        categories: CategoryRepository,
        transactions: TransactionRepository,
    ) -> None:
        self._categories = categories
        self._transactions = transactions

    def execute(
        self,
        user_id: UUID,
        category_id: UUID,
        kind: TransactionKind,
        amount_minor: int,
        description: str,
        occurred_at: datetime,
    ) -> Transaction:
        category = self._categories.get_available_by_id(user_id, category_id)
        if category is None:
            raise CategoryNotFoundError
        if category.kind != kind:
            raise CategoryKindMismatchError

        return self._transactions.add(
            user_id=user_id,
            category=category,
            kind=kind,
            amount_minor=amount_minor,
            description=description.strip(),
            occurred_at=occurred_at,
        )
