"""The real Argon2 adapter, not a fake.

Only a handful of calls: each one is deliberately expensive, which is exactly
why every other test hashes with a fake.
"""

from app.infrastructure.security.passwords import Argon2PasswordHasher


def test_a_digest_does_not_contain_the_password() -> None:
    digest = Argon2PasswordHasher().hash("parola123")

    assert "parola123" not in digest


def test_accepts_the_password_it_was_given() -> None:
    hasher = Argon2PasswordHasher()

    assert hasher.verify("parola123", hasher.hash("parola123")) is True


def test_rejects_a_password_that_is_merely_close() -> None:
    hasher = Argon2PasswordHasher()

    assert hasher.verify("parola124", hasher.hash("parola123")) is False


def test_two_digests_of_one_password_differ() -> None:
    """Each digest carries its own salt, so a leaked table cannot be read by
    matching identical rows against each other."""
    hasher = Argon2PasswordHasher()

    assert hasher.hash("parola123") != hasher.hash("parola123")
