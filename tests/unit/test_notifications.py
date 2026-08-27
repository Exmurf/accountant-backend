"""The two mails the application sends on its own."""

from datetime import UTC, date, datetime

from app.application.notifications.message import format_lira
from app.application.notifications.services import (
    SendBudgetExceededNotification,
    SendDailyExpenseSummary,
)
from app.domain.ledger.models import TransactionKind
from tests.factories import (
    make_budget,
    make_category,
    make_subscription,
    make_transaction,
    make_user,
)
from tests.fakes import (
    FakeBudgetRepository,
    FakeDeliveryRepository,
    FakeMailSender,
    FakeSubscriptionRepository,
    FakeTransactionRepository,
)

MONTH_START = datetime(2026, 3, 1, tzinfo=UTC)
MONTH_END = datetime(2026, 4, 1, tzinfo=UTC)
SENT_AT = datetime(2026, 3, 15, 12, 0, tzinfo=UTC)


def warn_about_budget(
    user,  # type: ignore[no-untyped-def]
    category_id,  # type: ignore[no-untyped-def]
    budgets: FakeBudgetRepository,
    transactions: FakeTransactionRepository,
    mailer: FakeMailSender,
    subscriptions: FakeSubscriptionRepository | None = None,
    deliveries: FakeDeliveryRepository | None = None,
) -> bool:
    return SendBudgetExceededNotification(
        budgets=budgets,
        subscriptions=subscriptions or FakeSubscriptionRepository(),
        transactions=transactions,
        deliveries=deliveries or FakeDeliveryRepository(),
        mailer=mailer,
    ).execute(
        user=user,
        category_id=category_id,
        period_start=MONTH_START,
        period_end=MONTH_END,
        delivered_at=SENT_AT,
    )


def test_a_category_with_no_limit_is_never_warned_about() -> None:
    user = make_user()
    food = make_category()
    mailer = FakeMailSender()

    warned = warn_about_budget(
        user,
        food.id,
        FakeBudgetRepository(),
        FakeTransactionRepository(),
        mailer,
    )

    assert warned is False
    assert mailer.sent == []


def test_spending_under_the_limit_says_nothing() -> None:
    user = make_user()
    food = make_category()
    budgets = FakeBudgetRepository(
        [make_budget(user_id=user.id, category_id=food.id, limit_minor=100_000)]
    )
    transactions = FakeTransactionRepository(
        [
            make_transaction(
                user_id=user.id,
                category=food,
                amount_minor=99_999,
                occurred_at=SENT_AT,
            )
        ]
    )
    mailer = FakeMailSender()

    assert warn_about_budget(user, food.id, budgets, transactions, mailer) is False
    assert mailer.sent == []


def test_going_over_the_limit_sends_one_mail() -> None:
    user = make_user(email="ahmet@mail.dev")
    food = make_category(name="Yemek")
    budgets = FakeBudgetRepository(
        [make_budget(user_id=user.id, category_id=food.id, limit_minor=100_000)]
    )
    transactions = FakeTransactionRepository(
        [
            make_transaction(
                user_id=user.id,
                category=food,
                amount_minor=120_000,
                occurred_at=SENT_AT,
            )
        ]
    )
    mailer = FakeMailSender()

    assert warn_about_budget(user, food.id, budgets, transactions, mailer) is True
    assert mailer.last.recipient == "ahmet@mail.dev"
    assert "Yemek" in mailer.last.subject
    assert format_lira(20_000) in mailer.last.message.notice


def test_the_same_overrun_is_only_reported_once() -> None:
    """The alert fires from a background task after every expense, so without
    a record every later purchase that month would send the same mail again."""
    user = make_user()
    food = make_category()
    budgets = FakeBudgetRepository(
        [make_budget(user_id=user.id, category_id=food.id, limit_minor=100_000)]
    )
    transactions = FakeTransactionRepository(
        [
            make_transaction(
                user_id=user.id,
                category=food,
                amount_minor=120_000,
                occurred_at=SENT_AT,
            )
        ]
    )
    deliveries = FakeDeliveryRepository()
    mailer = FakeMailSender()

    warn_about_budget(user, food.id, budgets, transactions, mailer, deliveries=deliveries)
    second = warn_about_budget(
        user, food.id, budgets, transactions, mailer, deliveries=deliveries
    )

    assert second is False
    assert len(mailer.sent) == 1


def test_raising_the_limit_opens_a_fresh_warning() -> None:
    """Somebody who deliberately moved the line still expects to hear about
    crossing the new one."""
    user = make_user()
    food = make_category()
    budget = make_budget(user_id=user.id, category_id=food.id, limit_minor=100_000)
    budgets = FakeBudgetRepository([budget])
    transactions = FakeTransactionRepository(
        [
            make_transaction(
                user_id=user.id,
                category=food,
                amount_minor=250_000,
                occurred_at=SENT_AT,
            )
        ]
    )
    deliveries = FakeDeliveryRepository()
    mailer = FakeMailSender()

    warn_about_budget(user, food.id, budgets, transactions, mailer, deliveries=deliveries)
    budgets.upsert(user.id, food, 200_000)
    warned_again = warn_about_budget(
        user, food.id, budgets, transactions, mailer, deliveries=deliveries
    )

    assert warned_again is True
    assert len(mailer.sent) == 2


def test_a_subscription_not_yet_charged_counts_against_the_limit() -> None:
    """The money is already committed. Waiting for the charge to post would
    warn on the day it is too late to do anything about it."""
    user = make_user()
    food = make_category()
    budgets = FakeBudgetRepository(
        [make_budget(user_id=user.id, category_id=food.id, limit_minor=100_000)]
    )
    transactions = FakeTransactionRepository(
        [
            make_transaction(
                user_id=user.id,
                category=food,
                amount_minor=80_000,
                occurred_at=SENT_AT,
            )
        ]
    )
    subscriptions = FakeSubscriptionRepository(
        [
            make_subscription(
                user_id=user.id,
                category_id=food.id,
                amount_minor=30_000,
            )
        ]
    )
    mailer = FakeMailSender()

    warned = warn_about_budget(
        user,
        food.id,
        budgets,
        transactions,
        mailer,
        subscriptions=subscriptions,
    )

    assert warned is True


def test_a_subscription_already_charged_is_not_counted_twice() -> None:
    user = make_user()
    food = make_category()
    subscription = make_subscription(
        user_id=user.id,
        category_id=food.id,
        amount_minor=30_000,
    )
    budgets = FakeBudgetRepository(
        [make_budget(user_id=user.id, category_id=food.id, limit_minor=100_000)]
    )
    transactions = FakeTransactionRepository(
        [
            make_transaction(
                user_id=user.id,
                category=food,
                amount_minor=80_000,
                occurred_at=SENT_AT,
                subscription_id=subscription.id,
                subscription_charge_date=date(2026, 3, 15),
            )
        ]
    )
    mailer = FakeMailSender()

    warned = warn_about_budget(
        user,
        food.id,
        budgets,
        transactions,
        mailer,
        subscriptions=FakeSubscriptionRepository([subscription]),
    )

    assert warned is False


def test_income_filed_under_the_category_does_not_count_as_spending() -> None:
    user = make_user()
    food = make_category()
    budgets = FakeBudgetRepository(
        [make_budget(user_id=user.id, category_id=food.id, limit_minor=100_000)]
    )
    transactions = FakeTransactionRepository(
        [
            make_transaction(
                user_id=user.id,
                category=food,
                kind=TransactionKind.INCOME,
                amount_minor=500_000,
                occurred_at=SENT_AT,
            )
        ]
    )
    mailer = FakeMailSender()

    assert warn_about_budget(user, food.id, budgets, transactions, mailer) is False


def send_summary(
    user,  # type: ignore[no-untyped-def]
    transactions: FakeTransactionRepository,
    mailer: FakeMailSender,
    summary_date: date = date(2026, 3, 15),
    delivered_at: datetime = SENT_AT,
    deliveries: FakeDeliveryRepository | None = None,
) -> bool:
    day_start = datetime(
        summary_date.year,
        summary_date.month,
        summary_date.day,
        tzinfo=UTC,
    )
    return SendDailyExpenseSummary(
        transactions=transactions,
        deliveries=deliveries or FakeDeliveryRepository(),
        mailer=mailer,
    ).execute(
        user=user,
        summary_date=summary_date,
        period_start=day_start,
        period_end=datetime(2026, 3, 16, tzinfo=UTC),
        delivered_at=delivered_at,
    )


def test_the_summary_adds_the_days_expenses_up() -> None:
    user = make_user()
    food = make_category(name="Yemek")
    transport = make_category(name="Ulaşım")
    transactions = FakeTransactionRepository(
        [
            make_transaction(user_id=user.id, category=food, amount_minor=4_000, occurred_at=SENT_AT),
            make_transaction(user_id=user.id, category=transport, amount_minor=9_000, occurred_at=SENT_AT),
        ]
    )
    mailer = FakeMailSender()

    assert send_summary(user, transactions, mailer) is True
    assert mailer.last.message.figure.value == format_lira(13_000)


def test_the_categories_are_listed_biggest_first() -> None:
    user = make_user()
    food = make_category(name="Yemek")
    transport = make_category(name="Ulaşım")
    transactions = FakeTransactionRepository(
        [
            make_transaction(user_id=user.id, category=food, amount_minor=4_000, occurred_at=SENT_AT),
            make_transaction(user_id=user.id, category=transport, amount_minor=9_000, occurred_at=SENT_AT),
        ]
    )
    mailer = FakeMailSender()

    send_summary(user, transactions, mailer)

    assert [row.label for row in mailer.last.message.rows] == ["Ulaşım", "Yemek"]


def test_a_day_with_nothing_spent_says_so_plainly() -> None:
    user = make_user()
    mailer = FakeMailSender()

    send_summary(user, FakeTransactionRepository(), mailer)

    assert mailer.last.message.rows == ()
    assert "kayıtlı bir gider bulunmuyor" in " ".join(mailer.last.message.paragraphs)


def test_the_same_day_is_only_summarised_once() -> None:
    user = make_user()
    deliveries = FakeDeliveryRepository()
    mailer = FakeMailSender()

    send_summary(user, FakeTransactionRepository(), mailer, deliveries=deliveries)
    second = send_summary(
        user, FakeTransactionRepository(), mailer, deliveries=deliveries
    )

    assert second is False
    assert len(mailer.sent) == 1


def test_a_catch_up_summary_says_which_day_it_is_about() -> None:
    """It goes out after the service was down, so calling it today would be
    wrong in the one place the reader is looking."""
    user = make_user()
    mailer = FakeMailSender()

    send_summary(
        user,
        FakeTransactionRepository(),
        mailer,
        summary_date=date(2026, 3, 13),
        delivered_at=SENT_AT,
    )

    assert "13.03.2026" in mailer.last.subject


def test_todays_summary_is_called_today() -> None:
    user = make_user()
    mailer = FakeMailSender()

    send_summary(user, FakeTransactionRepository(), mailer, summary_date=SENT_AT.date())

    assert mailer.last.subject.startswith("Bugün")
