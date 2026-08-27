"""Notification preferences and display name."""

from datetime import time

import pytest

from app.application.identity.update_settings import UpdateUserSettings
from tests.factories import make_user
from tests.fakes import FakeUserRepository


def update(users: FakeUserRepository, user_id, **overrides):  # type: ignore[no-untyped-def]
    payload = {
        "display_name": "Ahmet",
        "daily_summary_enabled": True,
        "daily_summary_time": time(21, 0),
        "budget_alerts_enabled": True,
    }
    payload.update(overrides)
    return UpdateUserSettings(users).execute(user_id=user_id, **payload)


def test_the_display_name_is_trimmed() -> None:
    user = make_user()
    users = FakeUserRepository([user])

    updated = update(users, user.id, display_name="  Ahmet Faruk  ")

    assert updated.display_name == "Ahmet Faruk"


def test_preferences_are_stored_as_given() -> None:
    user = make_user()
    users = FakeUserRepository([user])

    updated = update(
        users,
        user.id,
        daily_summary_enabled=False,
        daily_summary_time=time(8, 30),
        budget_alerts_enabled=False,
    )

    assert updated.daily_summary_enabled is False
    assert updated.daily_summary_time == time(8, 30)
    assert updated.budget_alerts_enabled is False


def test_an_account_that_disappeared_is_a_bug_not_a_bad_request() -> None:
    """Reaching this code already required a valid session, so a missing row
    means something is wrong with the application, not with the request."""
    with pytest.raises(RuntimeError):
        update(FakeUserRepository(), make_user().id)
