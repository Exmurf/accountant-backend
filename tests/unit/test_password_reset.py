"""Forgotten-password links: asking for one, and spending it."""

from datetime import UTC, datetime, timedelta

import pytest

from app.application.identity.errors import InvalidPasswordResetTokenError
from app.application.identity.request_password_reset import RequestPasswordReset
from app.application.identity.reset_password import ResetPassword
from tests.factories import make_user
from tests.fakes import (
    FakeMailSender,
    FakePasswordHasher,
    FakePasswordResetTokenRepository,
    FakeRefreshTokenRepository,
    FakeRefreshTokenService,
    FakeUserRepository,
)

WEB_ORIGIN = "https://accountant.mail.dev"


def request_reset(
    users: FakeUserRepository,
    tokens: FakePasswordResetTokenRepository,
    mailer: FakeMailSender,
    email: str,
    lifetime_minutes: int = 60,
    token_service: FakeRefreshTokenService | None = None,
) -> bool:
    return RequestPasswordReset(
        users=users,
        reset_tokens=tokens,
        token_service=token_service or FakeRefreshTokenService(),
        mailer=mailer,
        web_origin=WEB_ORIGIN,
        token_lifetime_minutes=lifetime_minutes,
    ).execute(email)


def test_a_registered_address_gets_a_link() -> None:
    user = make_user(email="ahmet@mail.dev")
    mailer = FakeMailSender()

    sent = request_reset(
        FakeUserRepository([user]),
        FakePasswordResetTokenRepository(),
        mailer,
        "ahmet@mail.dev",
    )

    assert sent is True
    assert mailer.last.recipient == "ahmet@mail.dev"
    assert mailer.last.message.action is not None
    assert mailer.last.message.action.url.startswith(f"{WEB_ORIGIN}/?reset_token=")


def test_an_unknown_address_is_answered_with_silence() -> None:
    """Nothing about the outcome reaches the caller, so this endpoint cannot be
    used to find out who holds an account here."""
    mailer = FakeMailSender()

    sent = request_reset(
        FakeUserRepository(),
        FakePasswordResetTokenRepository(),
        mailer,
        "kimse@mail.dev",
    )

    assert sent is False
    assert mailer.sent == []


def test_a_deactivated_account_gets_no_link() -> None:
    mailer = FakeMailSender()
    user = make_user(email="ahmet@mail.dev", is_active=False)

    sent = request_reset(
        FakeUserRepository([user]),
        FakePasswordResetTokenRepository(),
        mailer,
        "ahmet@mail.dev",
    )

    assert sent is False
    assert mailer.sent == []


def test_only_the_digest_of_the_link_is_kept() -> None:
    """The usable token exists for exactly as long as it takes to write the
    mail. What stays behind cannot be turned back into a working link."""
    user = make_user(email="ahmet@mail.dev")
    tokens = FakePasswordResetTokenRepository()
    mailer = FakeMailSender()

    request_reset(FakeUserRepository([user]), tokens, mailer, "ahmet@mail.dev")

    link = mailer.last.message.action.url
    stored_hash = next(iter(tokens.tokens))
    assert stored_hash not in link


def test_asking_again_retires_the_previous_link() -> None:
    user = make_user(email="ahmet@mail.dev")
    users = FakeUserRepository([user])
    tokens = FakePasswordResetTokenRepository()

    # One service across both calls, so the second link is genuinely a
    # different token rather than the same string handed out twice.
    token_service = FakeRefreshTokenService()

    request_reset(users, tokens, FakeMailSender(), "ahmet@mail.dev", token_service=token_service)
    first_hash = next(iter(tokens.tokens))
    request_reset(users, tokens, FakeMailSender(), "ahmet@mail.dev", token_service=token_service)

    assert tokens.tokens[first_hash].used_at is not None


@pytest.mark.parametrize(
    ("minutes", "expected"),
    [(30, "30 dakika"), (60, "1 saat"), (90, "1.5 saat")],
)
def test_the_mail_says_how_long_the_link_lasts(minutes: int, expected: str) -> None:
    user = make_user(email="ahmet@mail.dev")
    mailer = FakeMailSender()

    request_reset(
        FakeUserRepository([user]),
        FakePasswordResetTokenRepository(),
        mailer,
        "ahmet@mail.dev",
        lifetime_minutes=minutes,
    )

    assert expected in " ".join(mailer.last.message.paragraphs)


def reset_with(
    users: FakeUserRepository,
    tokens: FakePasswordResetTokenRepository,
    refresh_tokens: FakeRefreshTokenRepository,
    token: str,
    new_password: str = "yeniparola456",
):  # type: ignore[no-untyped-def]
    return ResetPassword(
        users=users,
        passwords=FakePasswordHasher(),
        reset_tokens=tokens,
        token_service=FakeRefreshTokenService(),
        refresh_token_repository=refresh_tokens,
    ).execute(token=token, new_password=new_password)


def stored_token(tokens: FakePasswordResetTokenRepository, user_id, token: str = "gecerli") -> str:  # type: ignore[no-untyped-def]
    tokens.replace_for_user(
        user_id=user_id,
        token_hash=f"sha:{token}",
        expires_at=datetime.now(UTC) + timedelta(hours=1),
        now=datetime.now(UTC),
    )
    return token


def test_a_valid_link_sets_the_new_password() -> None:
    user = make_user()
    users = FakeUserRepository([user])
    tokens = FakePasswordResetTokenRepository()
    token = stored_token(tokens, user.id)

    updated = reset_with(users, tokens, FakeRefreshTokenRepository(), token)

    assert updated.password_hash == "hashed:yeniparola456"


def test_a_link_works_only_once() -> None:
    user = make_user()
    users = FakeUserRepository([user])
    tokens = FakePasswordResetTokenRepository()
    token = stored_token(tokens, user.id)

    reset_with(users, tokens, FakeRefreshTokenRepository(), token)

    with pytest.raises(InvalidPasswordResetTokenError):
        reset_with(users, tokens, FakeRefreshTokenRepository(), token)


def test_an_unknown_link_is_refused() -> None:
    users = FakeUserRepository([make_user()])

    with pytest.raises(InvalidPasswordResetTokenError):
        reset_with(
            users,
            FakePasswordResetTokenRepository(),
            FakeRefreshTokenRepository(),
            "uydurma",
        )


def test_an_expired_link_is_refused() -> None:
    user = make_user()
    users = FakeUserRepository([user])
    tokens = FakePasswordResetTokenRepository()
    tokens.replace_for_user(
        user_id=user.id,
        token_hash="sha:eski",
        expires_at=datetime.now(UTC) - timedelta(minutes=1),
        now=datetime.now(UTC) - timedelta(hours=2),
    )

    with pytest.raises(InvalidPasswordResetTokenError):
        reset_with(users, tokens, FakeRefreshTokenRepository(), "eski")


def test_a_deactivated_account_cannot_be_reset_into() -> None:
    user = make_user(is_active=False)
    users = FakeUserRepository([user])
    tokens = FakePasswordResetTokenRepository()
    token = stored_token(tokens, user.id)

    with pytest.raises(InvalidPasswordResetTokenError):
        reset_with(users, tokens, FakeRefreshTokenRepository(), token)


def test_resetting_ends_every_open_session() -> None:
    user = make_user()
    users = FakeUserRepository([user])
    tokens = FakePasswordResetTokenRepository()
    refresh_tokens = FakeRefreshTokenRepository()
    refresh_tokens.add(user.id, "sha:eski-oturum", datetime.now(UTC) + timedelta(days=1))
    token = stored_token(tokens, user.id)

    reset_with(users, tokens, refresh_tokens, token)

    assert refresh_tokens.live_tokens_for(user.id) == []


def test_the_old_password_may_be_set_again() -> None:
    """Whoever reached this screen does not know what the old password was.
    Refusing would answer a question they never asked."""
    user = make_user(password_hash="hashed:parola123")
    users = FakeUserRepository([user])
    tokens = FakePasswordResetTokenRepository()
    token = stored_token(tokens, user.id)

    updated = reset_with(
        users,
        tokens,
        FakeRefreshTokenRepository(),
        token,
        new_password="parola123",
    )

    assert updated.password_hash == "hashed:parola123"
