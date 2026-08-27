"""Moving an account to another mailbox."""

from datetime import UTC, datetime, timedelta

import pytest

from app.application.identity.change_email import (
    ConfirmEmailChange,
    RequestEmailChange,
    announce_address_change,
    warn_previous_address,
)
from app.application.identity.errors import (
    EmailAlreadyRegisteredError,
    EmailUnchangedError,
    InvalidCredentialsError,
    InvalidEmailChangeTokenError,
    UnreachableEmailError,
)
from tests.factories import make_user
from tests.fakes import (
    FakeEmailChangeTokenRepository,
    FakeMailSender,
    FakePasswordHasher,
    FakeRefreshTokenService,
    FakeUserRepository,
)

WEB_ORIGIN = "https://accountant.mail.dev"


def request_change(
    users: FakeUserRepository,
    tokens: FakeEmailChangeTokenRepository,
    mailer: FakeMailSender,
    user,  # type: ignore[no-untyped-def]
    new_email: str = "yeni@mail.dev",
    current_password: str = "parola123",
) -> str:
    return RequestEmailChange(
        users=users,
        passwords=FakePasswordHasher(),
        change_tokens=tokens,
        token_service=FakeRefreshTokenService(),
        mailer=mailer,
        web_origin=WEB_ORIGIN,
        token_lifetime_minutes=60,
    ).execute(user=user, new_email=new_email, current_password=current_password)


def test_the_confirmation_goes_to_the_address_being_claimed() -> None:
    """Holding the new mailbox is the only thing that proves it is theirs, so
    the link has to arrive there and nowhere else."""
    user = make_user(email="ahmet@mail.dev")
    mailer = FakeMailSender()

    request_change(
        FakeUserRepository([user]),
        FakeEmailChangeTokenRepository(),
        mailer,
        user,
    )

    assert mailer.last.recipient == "yeni@mail.dev"
    assert mailer.last.message.action.url.startswith(f"{WEB_ORIGIN}/?email_token=")


def test_the_address_is_normalised_before_anything_else() -> None:
    user = make_user(email="ahmet@mail.dev")

    normalised = request_change(
        FakeUserRepository([user]),
        FakeEmailChangeTokenRepository(),
        FakeMailSender(),
        user,
        new_email="  YENI@Mail.DEV  ",
    )

    assert normalised == "yeni@mail.dev"


def test_a_session_alone_is_not_enough() -> None:
    """Mail is the recovery channel. Letting a borrowed session repoint it
    would turn a stolen session into a permanent takeover."""
    user = make_user()
    mailer = FakeMailSender()

    with pytest.raises(InvalidCredentialsError):
        request_change(
            FakeUserRepository([user]),
            FakeEmailChangeTokenRepository(),
            mailer,
            user,
            current_password="yanlisparola",
        )

    assert mailer.sent == []


def test_moving_to_the_address_already_in_use_is_refused() -> None:
    user = make_user(email="ahmet@mail.dev")

    with pytest.raises(EmailUnchangedError):
        request_change(
            FakeUserRepository([user]),
            FakeEmailChangeTokenRepository(),
            FakeMailSender(),
            user,
            new_email="AHMET@mail.dev",
        )


@pytest.mark.parametrize("domain", ["example.com", "example.org", "example.net"])
def test_an_address_no_mail_can_reach_is_refused(domain: str) -> None:
    """Refusing now beats leaving somebody waiting for a mail that was never
    going to be deliverable."""
    user = make_user(email="ahmet@mail.dev")

    with pytest.raises(UnreachableEmailError):
        request_change(
            FakeUserRepository([user]),
            FakeEmailChangeTokenRepository(),
            FakeMailSender(),
            user,
            new_email=f"yeni@{domain}",
        )


def test_an_address_another_account_holds_is_refused() -> None:
    user = make_user(email="ahmet@mail.dev")
    taken = make_user(email="yeni@mail.dev")

    with pytest.raises(EmailAlreadyRegisteredError):
        request_change(
            FakeUserRepository([user, taken]),
            FakeEmailChangeTokenRepository(),
            FakeMailSender(),
            user,
        )


def test_the_account_is_untouched_until_the_link_is_followed() -> None:
    user = make_user(email="ahmet@mail.dev")
    users = FakeUserRepository([user])

    request_change(users, FakeEmailChangeTokenRepository(), FakeMailSender(), user)

    assert users.get_by_id(user.id).email == "ahmet@mail.dev"


def test_the_old_address_is_warned_without_being_given_the_link() -> None:
    """A link here would hand somebody who only reads the old mailbox exactly
    what they are missing."""
    user = make_user(email="ahmet@mail.dev")
    mailer = FakeMailSender()

    warn_previous_address(mailer, user, "yeni@mail.dev")

    assert mailer.last.recipient == "ahmet@mail.dev"
    assert mailer.last.message.action is None
    assert "yeni@mail.dev" in " ".join(mailer.last.message.paragraphs)


def confirm(
    users: FakeUserRepository,
    tokens: FakeEmailChangeTokenRepository,
    token: str,
):  # type: ignore[no-untyped-def]
    return ConfirmEmailChange(
        users=users,
        change_tokens=tokens,
        token_service=FakeRefreshTokenService(),
    ).execute(token)


def pending(
    tokens: FakeEmailChangeTokenRepository,
    user_id,  # type: ignore[no-untyped-def]
    new_email: str = "yeni@mail.dev",
    token: str = "gecerli",
) -> str:
    tokens.replace_for_user(
        user_id=user_id,
        new_email=new_email,
        token_hash=f"sha:{token}",
        expires_at=datetime.now(UTC) + timedelta(hours=1),
        now=datetime.now(UTC),
    )
    return token


def test_following_the_link_moves_the_account() -> None:
    user = make_user(email="ahmet@mail.dev")
    users = FakeUserRepository([user])
    tokens = FakeEmailChangeTokenRepository()
    token = pending(tokens, user.id)

    updated, previous = confirm(users, tokens, token)

    assert updated.email == "yeni@mail.dev"
    assert previous == "ahmet@mail.dev"


def test_the_link_works_only_once() -> None:
    user = make_user(email="ahmet@mail.dev")
    users = FakeUserRepository([user])
    tokens = FakeEmailChangeTokenRepository()
    token = pending(tokens, user.id)

    confirm(users, tokens, token)

    with pytest.raises(InvalidEmailChangeTokenError):
        confirm(users, tokens, token)


def test_an_unknown_link_is_refused() -> None:
    users = FakeUserRepository([make_user()])

    with pytest.raises(InvalidEmailChangeTokenError):
        confirm(users, FakeEmailChangeTokenRepository(), "uydurma")


def test_an_expired_link_is_refused() -> None:
    user = make_user()
    users = FakeUserRepository([user])
    tokens = FakeEmailChangeTokenRepository()
    tokens.replace_for_user(
        user_id=user.id,
        new_email="yeni@mail.dev",
        token_hash="sha:eski",
        expires_at=datetime.now(UTC) - timedelta(minutes=1),
        now=datetime.now(UTC) - timedelta(hours=2),
    )

    with pytest.raises(InvalidEmailChangeTokenError):
        confirm(users, tokens, "eski")


def test_a_deactivated_account_cannot_be_moved() -> None:
    user = make_user(is_active=False)
    users = FakeUserRepository([user])
    tokens = FakeEmailChangeTokenRepository()
    token = pending(tokens, user.id)

    with pytest.raises(InvalidEmailChangeTokenError):
        confirm(users, tokens, token)


def test_an_address_taken_while_the_mail_sat_unread_is_refused() -> None:
    """It was free when the link went out. The check runs again here because
    the only thing that settles it is the state at the moment of the write."""
    user = make_user(email="ahmet@mail.dev")
    users = FakeUserRepository([user])
    tokens = FakeEmailChangeTokenRepository()
    token = pending(tokens, user.id)
    users.users[user.id] = users.get_by_id(user.id)
    latecomer = make_user(email="yeni@mail.dev")
    users.users[latecomer.id] = latecomer

    with pytest.raises(EmailAlreadyRegisteredError):
        confirm(users, tokens, token)


def test_the_old_address_is_told_after_the_move() -> None:
    user = make_user(email="yeni@mail.dev")
    mailer = FakeMailSender()

    announce_address_change(mailer, user, "ahmet@mail.dev")

    assert mailer.last.recipient == "ahmet@mail.dev"
    assert "yeni@mail.dev" in " ".join(mailer.last.message.paragraphs)
