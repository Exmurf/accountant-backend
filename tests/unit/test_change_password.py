"""Changing a password from inside a session."""

import pytest

from app.application.identity.change_password import ChangePassword
from app.application.identity.errors import (
    InvalidCredentialsError,
    PasswordUnchangedError,
)
from datetime import UTC, datetime, timedelta
from tests.factories import make_user
from tests.fakes import (
    FakePasswordHasher,
    FakeRefreshTokenRepository,
    FakeUserRepository,
)


def change(users: FakeUserRepository, tokens: FakeRefreshTokenRepository, user_id, **kwargs):  # type: ignore[no-untyped-def]
    payload = {"current_password": "parola123", "new_password": "yeniparola456"}
    payload.update(kwargs)
    return ChangePassword(users, FakePasswordHasher(), tokens).execute(
        user_id=user_id,
        **payload,
    )


def test_the_new_password_replaces_the_old_one() -> None:
    user = make_user(password_hash="hashed:parola123")
    users = FakeUserRepository([user])

    updated = change(users, FakeRefreshTokenRepository(), user.id)

    assert updated.password_hash == "hashed:yeniparola456"


def test_a_wrong_current_password_changes_nothing() -> None:
    user = make_user(password_hash="hashed:parola123")
    users = FakeUserRepository([user])

    with pytest.raises(InvalidCredentialsError):
        change(users, FakeRefreshTokenRepository(), user.id, current_password="yanlis")

    assert users.get_by_id(user.id).password_hash == "hashed:parola123"


def test_reusing_the_current_password_is_refused() -> None:
    user = make_user(password_hash="hashed:parola123")
    users = FakeUserRepository([user])

    with pytest.raises(PasswordUnchangedError):
        change(users, FakeRefreshTokenRepository(), user.id, new_password="parola123")


def test_every_other_session_ends_with_the_change() -> None:
    """The reason to change a password is usually that somebody else knows it,
    so a session opened with the old one must not survive."""
    user = make_user(password_hash="hashed:parola123")
    users = FakeUserRepository([user])
    tokens = FakeRefreshTokenRepository()
    expires_at = datetime.now(UTC) + timedelta(days=1)
    tokens.add(user.id, "sha:telefon", expires_at)
    tokens.add(user.id, "sha:dizustu", expires_at)

    change(users, tokens, user.id)

    assert tokens.live_tokens_for(user.id) == []


def test_another_users_sessions_are_left_alone() -> None:
    user = make_user(password_hash="hashed:parola123")
    other = make_user(email="baskasi@mail.dev")
    users = FakeUserRepository([user, other])
    tokens = FakeRefreshTokenRepository()
    expires_at = datetime.now(UTC) + timedelta(days=1)
    tokens.add(user.id, "sha:benim", expires_at)
    tokens.add(other.id, "sha:onunki", expires_at)

    change(users, tokens, user.id)

    assert tokens.live_tokens_for(other.id) == ["sha:onunki"]


def test_the_change_is_stamped_so_old_access_tokens_stop_working() -> None:
    """An access token is not stored anywhere and cannot be revoked one by one.
    The marker on the account is what makes the ones minted earlier invalid."""
    user = make_user(password_hash="hashed:parola123", password_changed_at=None)
    users = FakeUserRepository([user])

    updated = change(users, FakeRefreshTokenRepository(), user.id)

    assert updated.password_changed_at is not None
