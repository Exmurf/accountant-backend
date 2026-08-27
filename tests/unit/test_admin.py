"""The administrator's read-only view, and the one thing it can change."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from app.application.admin.errors import (
    AdminUserNotFoundError,
    CannotDeactivateSelfError,
)
from app.application.admin.services import (
    ChangeAdminUserStatus,
    GetAdminUserFinanceDetails,
    ListAdminUserSummaries,
)
from app.domain.admin.models import UserFinanceTotals
from tests.factories import ADMIN_PERMISSIONS, make_transaction, make_user
from tests.fakes import FakeAdminFinanceReader, FakeUserRepository

BEFORE = datetime(2026, 3, 2, tzinfo=UTC)


def test_a_summary_reports_the_users_own_opening_balance() -> None:
    """The finance reader knows about transactions; the opening amount lives on
    the account, so the summary has to take it from there."""
    user = make_user(opening_balance_minor=100_000)
    finances = FakeAdminFinanceReader(
        {
            user.id: UserFinanceTotals(
                total_income_minor=250_000,
                total_expense_minor=40_000,
                transaction_count=7,
            )
        }
    )

    summaries = ListAdminUserSummaries(FakeUserRepository([user]), finances).execute(
        BEFORE
    )

    assert summaries[0].finances.opening_balance_minor == 100_000
    assert summaries[0].finances.current_balance_minor == 310_000
    assert summaries[0].finances.transaction_count == 7


def test_a_summary_lists_the_roles_in_a_settled_order() -> None:
    user = make_user(roles=frozenset({"USER", "ADMIN"}))

    summaries = ListAdminUserSummaries(
        FakeUserRepository([user]),
        FakeAdminFinanceReader(),
    ).execute(BEFORE)

    assert summaries[0].roles == ("ADMIN", "USER")


def test_a_summary_carries_no_password_material() -> None:
    user = make_user()

    summaries = ListAdminUserSummaries(
        FakeUserRepository([user]),
        FakeAdminFinanceReader(),
    ).execute(BEFORE)

    assert not hasattr(summaries[0], "password_hash")


def test_the_detail_view_asks_for_a_bounded_number_of_entries() -> None:
    """It is a glance at recent activity, not an export, and an account with
    years of history must not turn one screen into an unbounded read."""
    user = make_user()
    finances = FakeAdminFinanceReader(
        transactions=[make_transaction(user_id=user.id) for _ in range(30)]
    )

    details = GetAdminUserFinanceDetails(
        FakeUserRepository([user]),
        finances,
    ).execute(user.id, BEFORE)

    assert finances.limits_asked == [20]
    assert len(details.recent_transactions) == 20


def test_asking_about_an_account_that_is_not_there_is_reported() -> None:
    with pytest.raises(AdminUserNotFoundError):
        GetAdminUserFinanceDetails(
            FakeUserRepository(),
            FakeAdminFinanceReader(),
        ).execute(uuid4(), BEFORE)


def test_an_administrator_can_deactivate_somebody_else() -> None:
    admin = make_user(email="yonetici@mail.dev", permissions=ADMIN_PERMISSIONS)
    target = make_user(email="ahmet@mail.dev")
    users = FakeUserRepository([admin, target])

    updated = ChangeAdminUserStatus(users).execute(
        actor_id=admin.id,
        target_user_id=target.id,
        is_active=False,
    )

    assert updated.is_active is False


def test_an_administrator_cannot_lock_themselves_out() -> None:
    """The first ADMIN is granted by hand at the database prompt. Losing the
    last one would mean going back there to get it back."""
    admin = make_user(permissions=ADMIN_PERMISSIONS)
    users = FakeUserRepository([admin])

    with pytest.raises(CannotDeactivateSelfError):
        ChangeAdminUserStatus(users).execute(
            actor_id=admin.id,
            target_user_id=admin.id,
            is_active=False,
        )


def test_an_administrator_may_still_reactivate_themselves() -> None:
    admin = make_user(permissions=ADMIN_PERMISSIONS, is_active=False)
    users = FakeUserRepository([admin])

    updated = ChangeAdminUserStatus(users).execute(
        actor_id=admin.id,
        target_user_id=admin.id,
        is_active=True,
    )

    assert updated.is_active is True


def test_changing_the_status_of_an_unknown_account_is_reported() -> None:
    admin = make_user(permissions=ADMIN_PERMISSIONS)

    with pytest.raises(AdminUserNotFoundError):
        ChangeAdminUserStatus(FakeUserRepository([admin])).execute(
            actor_id=admin.id,
            target_user_id=uuid4(),
            is_active=False,
        )
