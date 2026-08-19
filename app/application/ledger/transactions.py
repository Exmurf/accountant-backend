from datetime import datetime
from uuid import UUID

from app.application.ledger.errors import (
    CategoryKindMismatchError,
    CategoryNotFoundError,
    TransactionNotFoundError,
)
from app.application.ledger.ports import (
    CategoryRepository,
    OpeningBalanceRepository,
    TransactionRepository,
)
from app.domain.identity.user import User
from app.domain.ledger.models import AccountBalance, Transaction, TransactionKind


class GetAccountBalance:
    def __init__(self, transactions: TransactionRepository) -> None:
        self._transactions = transactions

    def execute(self, user: User, before: datetime) -> AccountBalance:
        totals = self._transactions.get_balance(user.id, before)
        return AccountBalance(
            total_income_minor=totals.total_income_minor,
            total_expense_minor=totals.total_expense_minor,
            opening_balance_minor=user.opening_balance_minor,
        )


class SetOpeningBalance:
    def __init__(
        self,
        users: OpeningBalanceRepository,
        transactions: TransactionRepository,
    ) -> None:
        self._users = users
        self._transactions = transactions

    def execute(
        self,
        user_id: UUID,
        amount_minor: int,
        before: datetime,
    ) -> AccountBalance:
        opening_balance_minor = self._users.set_opening_balance(user_id, amount_minor)
        if opening_balance_minor is None:
            raise RuntimeError("Authenticated user could not be updated")

        totals = self._transactions.get_balance(user_id, before)
        return AccountBalance(
            total_income_minor=totals.total_income_minor,
            total_expense_minor=totals.total_expense_minor,
            opening_balance_minor=opening_balance_minor,
        )


class ListTransactions:
    def __init__(self, transactions: TransactionRepository) -> None:
        self._transactions = transactions

    def execute(
        self,
        user_id: UUID,
        start: datetime,
        end: datetime,
        category_id: UUID | None = None,
        kind: TransactionKind | None = None,
    ) -> list[Transaction]:
        return self._transactions.list_for_user(
            user_id,
            start,
            end,
            category_id=category_id,
            kind=kind,
        )


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


class UpdateTransaction:
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
        transaction_id: UUID,
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

        transaction = self._transactions.update(
            user_id=user_id,
            transaction_id=transaction_id,
            category=category,
            kind=kind,
            amount_minor=amount_minor,
            description=description.strip(),
            occurred_at=occurred_at,
        )
        if transaction is None:
            raise TransactionNotFoundError
        return transaction


class DeleteTransaction:
    def __init__(self, transactions: TransactionRepository) -> None:
        self._transactions = transactions

    def execute(self, user_id: UUID, transaction_id: UUID) -> None:
        if not self._transactions.remove(user_id, transaction_id):
            raise TransactionNotFoundError
