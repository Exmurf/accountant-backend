"""Opening, rotating and ending a session."""

from datetime import UTC, datetime, timedelta

import pytest

from app.application.identity.errors import (
    InactiveUserError,
    InvalidRefreshTokenError,
)
from app.application.identity.issue_session import IssueSession
from app.application.identity.refresh_session import RefreshSession
from app.application.identity.revoke_session import RevokeSession
from tests.factories import make_user
from tests.fakes import (
    FakeAccessTokenService,
    FakeRefreshTokenRepository,
    FakeRefreshTokenService,
    FakeUserRepository,
)

REFRESH_DAYS = 30


def issue_for(user, tokens: FakeRefreshTokenRepository):  # type: ignore[no-untyped-def]
    return IssueSession(
        access_tokens=FakeAccessTokenService(),
        refresh_tokens=FakeRefreshTokenService(),
        refresh_token_repository=tokens,
        refresh_token_days=REFRESH_DAYS,
    ).execute(user)


def test_opening_a_session_returns_both_tokens() -> None:
    user = make_user()

    session = issue_for(user, FakeRefreshTokenRepository())

    assert session.access_token == f"access:{user.id}"
    assert session.refresh_token == "refresh-1"


def test_only_the_digest_of_the_refresh_token_is_stored() -> None:
    """A stolen copy of the table has to be useless on its own."""
    user = make_user()
    tokens = FakeRefreshTokenRepository()

    session = issue_for(user, tokens)

    assert session.refresh_token not in tokens.tokens
    assert f"sha:{session.refresh_token}" in tokens.tokens


def test_the_stored_token_expires_a_month_out() -> None:
    tokens = FakeRefreshTokenRepository()

    issue_for(make_user(), tokens)

    stored = next(iter(tokens.tokens.values()))
    expected = datetime.now(UTC) + timedelta(days=REFRESH_DAYS)
    assert abs((stored.expires_at - expected).total_seconds()) < 5


def refresh_with(
    users: FakeUserRepository,
    tokens: FakeRefreshTokenRepository,
    token_service: FakeRefreshTokenService,
    current: str,
):  # type: ignore[no-untyped-def]
    return RefreshSession(
        users=users,
        access_tokens=FakeAccessTokenService(),
        refresh_tokens=token_service,
        refresh_token_repository=tokens,
        refresh_token_days=REFRESH_DAYS,
    ).execute(current)


def test_refreshing_hands_back_a_different_token() -> None:
    user = make_user()
    users = FakeUserRepository([user])
    tokens = FakeRefreshTokenRepository()
    token_service = FakeRefreshTokenService()
    tokens.add(user.id, token_service.hash("refresh-0"), datetime.now(UTC) + timedelta(days=1))

    session = refresh_with(users, tokens, token_service, "refresh-0")

    assert session.refresh_token != "refresh-0"


def test_a_spent_token_cannot_be_used_twice() -> None:
    """Rotation is what makes a stolen token worth little: the moment the real
    owner refreshes, the copy stops working."""
    user = make_user()
    users = FakeUserRepository([user])
    tokens = FakeRefreshTokenRepository()
    token_service = FakeRefreshTokenService()
    tokens.add(user.id, token_service.hash("refresh-0"), datetime.now(UTC) + timedelta(days=1))

    refresh_with(users, tokens, token_service, "refresh-0")

    with pytest.raises(InvalidRefreshTokenError):
        refresh_with(users, tokens, token_service, "refresh-0")


def test_an_unknown_token_is_refused() -> None:
    users = FakeUserRepository([make_user()])

    with pytest.raises(InvalidRefreshTokenError):
        refresh_with(users, FakeRefreshTokenRepository(), FakeRefreshTokenService(), "uydurma")


def test_an_expired_token_is_refused() -> None:
    user = make_user()
    users = FakeUserRepository([user])
    tokens = FakeRefreshTokenRepository()
    token_service = FakeRefreshTokenService()
    tokens.add(user.id, token_service.hash("refresh-0"), datetime.now(UTC) - timedelta(seconds=1))

    with pytest.raises(InvalidRefreshTokenError):
        refresh_with(users, tokens, token_service, "refresh-0")


def test_a_deactivated_account_cannot_refresh() -> None:
    user = make_user(is_active=False)
    users = FakeUserRepository([user])
    tokens = FakeRefreshTokenRepository()
    token_service = FakeRefreshTokenService()
    tokens.add(user.id, token_service.hash("refresh-0"), datetime.now(UTC) + timedelta(days=1))

    with pytest.raises(InactiveUserError):
        refresh_with(users, tokens, token_service, "refresh-0")


def test_signing_out_revokes_the_token() -> None:
    user = make_user()
    tokens = FakeRefreshTokenRepository()
    token_service = FakeRefreshTokenService()
    tokens.add(user.id, token_service.hash("refresh-0"), datetime.now(UTC) + timedelta(days=1))

    RevokeSession(token_service, tokens).execute("refresh-0")

    assert tokens.live_tokens_for(user.id) == []


def test_signing_out_with_a_token_nobody_issued_is_quiet() -> None:
    """The endpoint clears the cookies either way; there is nothing to report
    to somebody who is already leaving."""
    tokens = FakeRefreshTokenRepository()

    RevokeSession(FakeRefreshTokenService(), tokens).execute("uydurma")

    assert tokens.tokens == {}
