"""Registration: what the use case normalises, and what it refuses."""

import pytest

from app.application.identity.errors import EmailAlreadyRegisteredError
from app.application.identity.register_user import RegisterUser
from tests.factories import make_user
from tests.fakes import FakePasswordHasher, FakeUserRepository


def register(users: FakeUserRepository, **overrides: str):  # type: ignore[no-untyped-def]
    payload = {
        "email": "ahmet@mail.dev",
        "display_name": "Ahmet",
        "password": "parola123",
    }
    payload.update(overrides)
    return RegisterUser(users, FakePasswordHasher()).execute(**payload)


def test_stores_the_address_in_lower_case_without_padding() -> None:
    users = FakeUserRepository()

    user = register(users, email="  Ahmet@Mail.DEV  ")

    assert user.email == "ahmet@mail.dev"


def test_trims_the_display_name() -> None:
    users = FakeUserRepository()

    user = register(users, display_name="  Ahmet  ")

    assert user.display_name == "Ahmet"


def test_stores_what_the_hasher_returned_and_not_the_password() -> None:
    """The use case's job is to route the password through the hasher.

    Whether the digest is any good is the hasher's business, and it is tested
    against the real Argon2 adapter in test_password_hasher.py.
    """
    users = FakeUserRepository()

    user = register(users, password="parola123")

    assert user.password_hash == "hashed:parola123"


def test_refuses_an_address_that_is_already_registered() -> None:
    users = FakeUserRepository([make_user(email="ahmet@mail.dev")])

    with pytest.raises(EmailAlreadyRegisteredError):
        register(users, email="ahmet@mail.dev")


def test_refuses_the_same_address_written_differently() -> None:
    """The check runs after normalisation, or capitalising a letter would be
    enough to hold two accounts on one mailbox."""
    users = FakeUserRepository([make_user(email="ahmet@mail.dev")])

    with pytest.raises(EmailAlreadyRegisteredError):
        register(users, email="AHMET@Mail.dev")


def test_leaves_the_table_untouched_when_it_refuses() -> None:
    users = FakeUserRepository([make_user(email="ahmet@mail.dev")])

    with pytest.raises(EmailAlreadyRegisteredError):
        register(users, email="ahmet@mail.dev")

    assert len(users.users) == 1
