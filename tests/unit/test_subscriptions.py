"""Recurring charges, and the calendar arithmetic behind them."""

from datetime import date
from uuid import uuid4

import pytest

from app.application.ledger.errors import (
    CategoryNotFoundError,
    SubscriptionNotFoundError,
)
from app.application.ledger.subscriptions import (
    CreateSubscription,
    ListSubscriptions,
    ProcessDueSubscriptions,
    RemoveSubscription,
    UpdateSubscription,
    next_month_charge,
)
from app.domain.ledger.models import TransactionKind
from tests.factories import make_category, make_subscription, make_user
from tests.fakes import (
    FakeCategoryRepository,
    FakeSubscriptionRepository,
    FakeTransactionRepository,
)


@pytest.mark.parametrize(
    ("current", "billing_day", "expected"),
    [
        (date(2026, 1, 15), 15, date(2026, 2, 15)),
        # December rolls the year over.
        (date(2026, 12, 10), 10, date(2027, 1, 10)),
        # February is too short for the 31st, so the charge lands on its last day.
        (date(2026, 1, 31), 31, date(2026, 2, 28)),
        (date(2028, 1, 31), 31, date(2028, 2, 29)),
    ],
)
def test_the_next_charge_lands_on_the_billing_day_or_the_last_day(
    current: date,
    billing_day: int,
    expected: date,
) -> None:
    assert next_month_charge(current, billing_day) == expected


def test_a_short_month_does_not_move_the_billing_day_for_good() -> None:
    """The day the account was signed up on is remembered, so a February that
    clamped it to the 28th does not turn every later month into the 28th."""
    after_february = next_month_charge(date(2026, 2, 28), 31)

    assert after_february == date(2026, 3, 31)


def test_a_new_subscription_bills_on_the_day_it_starts() -> None:
    user = make_user()
    category = make_category(name="Abonelik", kind=TransactionKind.EXPENSE)
    subscriptions = FakeSubscriptionRepository()

    created = CreateSubscription(
        FakeCategoryRepository([category]),
        subscriptions,
    ).execute(
        user_id=user.id,
        category_id=category.id,
        name="  Müzik servisi  ",
        amount_minor=6_000,
        first_charge_date=date(2026, 3, 12),
    )

    assert created.name == "Müzik servisi"
    assert created.billing_day == 12
    assert created.next_charge_date == date(2026, 3, 12)


def test_a_subscription_needs_a_category_the_user_can_see() -> None:
    with pytest.raises(CategoryNotFoundError):
        CreateSubscription(
            FakeCategoryRepository(),
            FakeSubscriptionRepository(),
        ).execute(
            user_id=make_user().id,
            category_id=uuid4(),
            name="Müzik servisi",
            amount_minor=6_000,
            first_charge_date=date(2026, 3, 12),
        )


def test_listing_shows_only_the_live_ones() -> None:
    user = make_user()
    subscriptions = FakeSubscriptionRepository(
        [
            make_subscription(user_id=user.id, name="Müzik"),
            make_subscription(user_id=user.id, name="İptal", is_active=False),
        ]
    )

    listed = ListSubscriptions(subscriptions).execute(user.id)

    assert [item.name for item in listed] == ["Müzik"]


def test_cancelling_leaves_the_charges_already_posted_alone() -> None:
    """It is deactivated rather than deleted: the money that already left the
    account is history, and history does not change because a plan ended."""
    user = make_user()
    subscription = make_subscription(user_id=user.id)
    subscriptions = FakeSubscriptionRepository([subscription])

    RemoveSubscription(subscriptions).execute(user.id, subscription.id)

    assert subscriptions.list_active(user.id) == []
    assert subscriptions.subscriptions[0].is_active is False


def test_cancelling_someone_elses_subscription_is_refused() -> None:
    theirs = make_subscription(user_id=uuid4())
    subscriptions = FakeSubscriptionRepository([theirs])

    with pytest.raises(SubscriptionNotFoundError):
        RemoveSubscription(subscriptions).execute(make_user().id, theirs.id)


def test_editing_updates_the_plan() -> None:
    user = make_user()
    category = make_category(name="Abonelik", kind=TransactionKind.EXPENSE)
    subscription = make_subscription(
        user_id=user.id,
        category_id=category.id,
        amount_minor=6_000,
    )
    subscriptions = FakeSubscriptionRepository([subscription])

    updated = UpdateSubscription(
        FakeCategoryRepository([category]),
        subscriptions,
    ).execute(
        user_id=user.id,
        subscription_id=subscription.id,
        category_id=category.id,
        name="  Müzik servisi  ",
        amount_minor=9_000,
        billing_day=20,
    )

    assert updated.name == "Müzik servisi"
    assert updated.amount_minor == 9_000
    assert updated.billing_day == 20


def test_editing_a_subscription_that_is_not_there_is_reported() -> None:
    category = make_category()

    with pytest.raises(SubscriptionNotFoundError):
        UpdateSubscription(
            FakeCategoryRepository([category]),
            FakeSubscriptionRepository(),
        ).execute(
            user_id=make_user().id,
            subscription_id=uuid4(),
            category_id=category.id,
            name="Müzik",
            amount_minor=1,
            billing_day=1,
        )


def test_a_charge_is_posted_for_every_month_that_was_missed() -> None:
    """The service may have been stopped for a while. Catching up matters more
    than being on time, because a charge nobody posts is money the balance
    never accounts for."""
    user = make_user()
    subscription = make_subscription(
        user_id=user.id,
        amount_minor=6_000,
        billing_day=15,
        next_charge_date=date(2026, 1, 15),
    )
    subscriptions = FakeSubscriptionRepository([subscription])
    transactions = FakeTransactionRepository()

    created = ProcessDueSubscriptions(subscriptions, transactions).execute(
        user.id,
        date(2026, 4, 20),
    )

    assert [item.subscription_charge_date for item in created] == [
        date(2026, 1, 15),
        date(2026, 2, 15),
        date(2026, 3, 15),
        date(2026, 4, 15),
    ]


def test_the_next_charge_moves_past_the_day_it_ran() -> None:
    user = make_user()
    subscription = make_subscription(
        user_id=user.id,
        billing_day=15,
        next_charge_date=date(2026, 1, 15),
    )
    subscriptions = FakeSubscriptionRepository([subscription])

    ProcessDueSubscriptions(subscriptions, FakeTransactionRepository()).execute(
        user.id,
        date(2026, 4, 20),
    )

    assert subscriptions.subscriptions[0].next_charge_date == date(2026, 5, 15)


def test_running_it_twice_posts_nothing_the_second_time() -> None:
    """The scheduler runs every hour, and a request can trigger it too, so
    posting the same charge twice has to be impossible rather than unlikely."""
    user = make_user()
    subscription = make_subscription(
        user_id=user.id,
        billing_day=15,
        next_charge_date=date(2026, 1, 15),
    )
    subscriptions = FakeSubscriptionRepository([subscription])
    transactions = FakeTransactionRepository()
    use_case = ProcessDueSubscriptions(subscriptions, transactions)

    use_case.execute(user.id, date(2026, 4, 20))
    second_run = use_case.execute(user.id, date(2026, 4, 20))

    assert second_run == []
    assert len(transactions.transactions) == 4


def test_a_subscription_that_is_not_due_yet_is_left_alone() -> None:
    user = make_user()
    subscriptions = FakeSubscriptionRepository(
        [make_subscription(user_id=user.id, next_charge_date=date(2026, 5, 15))]
    )
    transactions = FakeTransactionRepository()

    created = ProcessDueSubscriptions(subscriptions, transactions).execute(
        user.id,
        date(2026, 4, 20),
    )

    assert created == []
    assert transactions.transactions == []


def test_a_cancelled_subscription_stops_being_charged() -> None:
    user = make_user()
    subscriptions = FakeSubscriptionRepository(
        [
            make_subscription(
                user_id=user.id,
                is_active=False,
                next_charge_date=date(2026, 1, 15),
            )
        ]
    )

    created = ProcessDueSubscriptions(
        subscriptions,
        FakeTransactionRepository(),
    ).execute(user.id, date(2026, 4, 20))

    assert created == []
