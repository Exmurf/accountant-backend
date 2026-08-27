"""Closing each month and adding up what was left over."""

from datetime import UTC, date, datetime
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

import pytest

from app.application.savings.services import ProcessMonthlySavings, SetSavingsGoal
from tests.factories import make_user
from tests.fakes import FakeCashFlowReader, FakeSavingsRepository, FakeUserRepository

ISTANBUL = ZoneInfo("Europe/Istanbul")
SIGNED_UP = datetime(2026, 1, 5, 9, 0, tzinfo=UTC)


def process(
    totals: dict[tuple[int, int], tuple[int, int]],
    savings: FakeSavingsRepository,
    today: date = date(2026, 4, 10),
    created_at: datetime = SIGNED_UP,
    goal_minor: int = 0,
    user_id: UUID | None = None,
):  # type: ignore[no-untyped-def]
    return ProcessMonthlySavings(FakeCashFlowReader(totals), savings).execute(
        user_id=user_id or uuid4(),
        account_created_at=created_at,
        today=today,
        timezone=ISTANBUL,
        goal_minor=goal_minor,
    )


def test_each_closed_month_keeps_what_was_left_over() -> None:
    savings = FakeSavingsRepository()

    process(
        {
            (2026, 1): (100_000, 40_000),
            (2026, 2): (50_000, 90_000),
        },
        savings,
    )

    assert [(item.month, item.amount_minor) for item in savings.entries] == [
        (1, 60_000),
        (2, -40_000),
        (3, 0),
    ]


def test_the_current_month_is_a_projection_and_is_not_written_down() -> None:
    """It is not over yet. Writing it would make a figure that still moves look
    like a closed one."""
    savings = FakeSavingsRepository()

    overview = process({(2026, 4): (80_000, 30_000)}, savings)

    assert overview.current_month_projection_minor == 50_000
    assert all(item.month != 4 for item in savings.entries)


def test_a_month_with_no_activity_still_gets_closed() -> None:
    savings = FakeSavingsRepository()

    process({}, savings)

    assert [item.month for item in savings.entries] == [1, 2, 3]


def test_savings_never_fall_below_nothing() -> None:
    """There is no such thing as owing the piggy bank. A month that spent more
    than it earned can empty what was put aside, and no further."""
    savings = FakeSavingsRepository()

    process(
        {
            (2026, 1): (50_000, 20_000),
            (2026, 2): (0, 500_000),
        },
        savings,
    )

    assert [item.amount_minor for item in savings.entries] == [30_000, -30_000, 0]


def test_the_first_month_cannot_go_negative_on_its_own() -> None:
    savings = FakeSavingsRepository()

    process({(2026, 1): (0, 90_000)}, savings)

    assert savings.entries[0].amount_minor == 0


def test_months_before_the_account_existed_are_still_closed() -> None:
    """A transaction may carry any past date. A month the walk never reaches is
    a month that never gets closed, so it would be missing for good."""
    savings = FakeSavingsRepository()

    process(
        {(2025, 11): (40_000, 10_000)},
        savings,
        created_at=datetime(2026, 1, 5, 9, 0, tzinfo=UTC),
    )

    assert (savings.entries[0].year, savings.entries[0].month) == (2025, 11)


def test_the_total_is_the_sum_of_the_closed_months() -> None:
    overview = process(
        {(2026, 1): (100_000, 40_000), (2026, 2): (10_000, 5_000)},
        FakeSavingsRepository(),
    )

    assert overview.total_saved_minor == 65_000


def test_the_goal_is_carried_into_the_overview() -> None:
    overview = process({}, FakeSavingsRepository(), goal_minor=500_000)

    assert overview.goal_minor == 500_000


def test_the_months_are_bucketed_in_the_users_own_timezone() -> None:
    """An expense at half past midnight in Istanbul belongs to that day, not to
    the one UTC was still on."""
    cash_flow = FakeCashFlowReader({})

    ProcessMonthlySavings(cash_flow, FakeSavingsRepository()).execute(
        user_id=make_user().id,
        account_created_at=SIGNED_UP,
        today=date(2026, 4, 10),
        timezone=ISTANBUL,
    )

    assert cash_flow.timezones_asked == ["Europe/Istanbul"]


def test_running_it_again_rewrites_rather_than_duplicates() -> None:
    """The endpoint is called on every visit to the savings screen, so the walk
    has to settle on the same rows rather than pile new ones on top."""
    savings = FakeSavingsRepository()
    totals = {(2026, 1): (100_000, 40_000)}
    user_id = uuid4()

    process(totals, savings, user_id=user_id)
    process(totals, savings, user_id=user_id)

    assert len(savings.entries) == 3


def test_setting_a_goal_returns_what_was_stored() -> None:
    user = make_user()
    users = FakeUserRepository([user])

    assert SetSavingsGoal(users).execute(user.id, 750_000) == 750_000


def test_setting_a_goal_for_an_account_that_vanished_is_a_bug() -> None:
    with pytest.raises(RuntimeError):
        SetSavingsGoal(FakeUserRepository()).execute(make_user().id, 1)
