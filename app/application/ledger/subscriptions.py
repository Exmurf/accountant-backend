from calendar import monthrange
from datetime import UTC, date, datetime, time
from uuid import UUID

from app.application.ledger.errors import (
    CategoryNotFoundError,
    SubscriptionNotFoundError,
)
from app.application.ledger.ports import (
    CategoryRepository,
    SubscriptionRepository,
    TransactionRepository,
)
from app.domain.ledger.models import Transaction, TransactionKind
from app.domain.ledger.subscription import Subscription


def next_month_charge(current: date, billing_day: int) -> date:
    year = current.year + (1 if current.month == 12 else 0)
    month = 1 if current.month == 12 else current.month + 1
    last_day = monthrange(year, month)[1]
    return date(year, month, min(billing_day, last_day))


class ListSubscriptions:
    def __init__(self, subscriptions: SubscriptionRepository) -> None:
        self._subscriptions = subscriptions

    def execute(self, user_id: UUID) -> list[Subscription]:
        return self._subscriptions.list_active(user_id)


class CreateSubscription:
    def __init__(
        self,
        categories: CategoryRepository,
        subscriptions: SubscriptionRepository,
    ) -> None:
        self._categories = categories
        self._subscriptions = subscriptions

    def execute(
        self,
        user_id: UUID,
        category_id: UUID,
        name: str,
        amount_minor: int,
        first_charge_date: date,
    ) -> Subscription:
        category = self._categories.get_available_by_id(user_id, category_id)
        if category is None:
            raise CategoryNotFoundError
        return self._subscriptions.add(
            user_id=user_id,
            category=category,
            name=name.strip(),
            amount_minor=amount_minor,
            first_charge_date=first_charge_date,
        )


class RemoveSubscription:
    def __init__(self, subscriptions: SubscriptionRepository) -> None:
        self._subscriptions = subscriptions

    def execute(self, user_id: UUID, subscription_id: UUID) -> None:
        if not self._subscriptions.deactivate(user_id, subscription_id):
            raise SubscriptionNotFoundError


class UpdateSubscription:
    def __init__(
        self,
        categories: CategoryRepository,
        subscriptions: SubscriptionRepository,
    ) -> None:
        self._categories = categories
        self._subscriptions = subscriptions

    def execute(
        self,
        user_id: UUID,
        subscription_id: UUID,
        category_id: UUID,
        name: str,
        amount_minor: int,
        billing_day: int,
    ) -> Subscription:
        category = self._categories.get_available_by_id(user_id, category_id)
        if category is None:
            raise CategoryNotFoundError

        subscription = self._subscriptions.update(
            user_id=user_id,
            subscription_id=subscription_id,
            category=category,
            name=name.strip(),
            amount_minor=amount_minor,
            billing_day=billing_day,
        )
        if subscription is None:
            raise SubscriptionNotFoundError
        return subscription


class ProcessDueSubscriptions:
    def __init__(
        self,
        subscriptions: SubscriptionRepository,
        transactions: TransactionRepository,
    ) -> None:
        self._subscriptions = subscriptions
        self._transactions = transactions

    def execute(self, user_id: UUID, through_date: date) -> list[Transaction]:
        created: list[Transaction] = []
        for subscription in self._subscriptions.list_due(user_id, through_date):
            charge_date = subscription.next_charge_date
            while charge_date <= through_date:
                occurred_at = datetime.combine(charge_date, time(hour=12), tzinfo=UTC)
                transaction = self._transactions.add_subscription_charge(
                    subscription,
                    charge_date,
                    occurred_at,
                )
                if transaction is not None:
                    created.append(transaction)
                charge_date = next_month_charge(charge_date, subscription.billing_day)
            self._subscriptions.update_next_charge(
                user_id,
                subscription.id,
                charge_date,
            )
        return created
