"""Signing in: who gets in, and what each refusal gives away."""

import pytest

from app.application.identity.errors import (
    InactiveUserError,
    InvalidCredentialsError,
)
from app.application.identity.login_user import LoginUser
from tests.factories import make_user
from tests.fakes import FakePasswordHasher, FakeUserRepository


def login_with(users: FakeUserRepository, email: str, password: str):  # type: ignore[no-untyped-def]
    return LoginUser(users, FakePasswordHasher()).execute(email, password)


def test_the_right_password_returns_the_account() -> None:
    user = make_user(email="ahmet@mail.dev", password_hash="hashed:parola123")
    users = FakeUserRepository([user])

    assert login_with(users, "ahmet@mail.dev", "parola123") == user


def test_the_address_is_matched_however_it_was_typed() -> None:
    users = FakeUserRepository([make_user(email="ahmet@mail.dev")])

    signed_in = login_with(users, "  AHMET@Mail.DEV  ", "parola123")

    assert signed_in.email == "ahmet@mail.dev"


def test_an_unknown_address_is_refused() -> None:
    users = FakeUserRepository()

    with pytest.raises(InvalidCredentialsError):
        login_with(users, "kimse@mail.dev", "parola123")


def test_a_wrong_password_is_refused() -> None:
    users = FakeUserRepository([make_user(email="ahmet@mail.dev")])

    with pytest.raises(InvalidCredentialsError):
        login_with(users, "ahmet@mail.dev", "yanlisparola")


def test_a_deactivated_account_is_told_apart_only_after_the_password() -> None:
    """The order is the point.

    A wrong password on a deactivated account has to look exactly like a wrong
    password on any other, or the error becomes a way to find out which
    addresses are registered here.
    """
    users = FakeUserRepository([make_user(email="ahmet@mail.dev", is_active=False)])

    with pytest.raises(InvalidCredentialsError):
        login_with(users, "ahmet@mail.dev", "yanlisparola")

    with pytest.raises(InactiveUserError):
        login_with(users, "ahmet@mail.dev", "parola123")
