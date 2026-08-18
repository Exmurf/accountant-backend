from datetime import date, datetime
from typing import Protocol
from uuid import UUID

from app.domain.ledger.models import Category, Transaction, TransactionKind
from app.domain.ledger.subscription import Subscription


class CategoryRepository(Protocol):
    def list_available(
        self,
        user_id: UUID,
        kind: TransactionKind | None = None,
    ) -> list[Category]: ...

    def get_available_by_id(
        self,
        user_id: UUID,
        category_id: UUID,
    ) -> Category | None: ...

    def add(
        self,
        user_id: UUID,
        name: str,
        kind: TransactionKind,
        color: str,
    ) -> Category: ...


class TransactionRepository(Protocol):
    def list_for_user(
        self,
        user_id: UUID,
        start: datetime,
        end: datetime,
    ) -> list[Transaction]: ...

    def add(
        self,
        user_id: UUID,
        category: Category,
        kind: TransactionKind,
        amount_minor: int,
        description: str,
        occurred_at: datetime,
    ) -> Transaction: ...

    def add_subscription_charge(
        self,
        subscription: Subscription,
        charge_date: date,
        occurred_at: datetime,
    ) -> Transaction | None: ...


class SubscriptionRepository(Protocol):
    def list_active(self, user_id: UUID) -> list[Subscription]: ...

    def list_due(self, user_id: UUID, through_date: date) -> list[Subscription]: ...

    def add(
        self,
        user_id: UUID,
        category: Category,
        name: str,
        amount_minor: int,
        first_charge_date: date,
    ) -> Subscription: ...

    def update_next_charge(
        self,
        user_id: UUID,
        subscription_id: UUID,
        next_charge_date: date,
    ) -> None: ...

    def update_amount(
        self,
        user_id: UUID,
        subscription_id: UUID,
        amount_minor: int,
    ) -> Subscription | None: ...

    def deactivate(self, user_id: UUID, subscription_id: UUID) -> bool: ...
