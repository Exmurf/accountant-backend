from datetime import UTC, datetime, timedelta

from app.application.identity.errors import (
    InactiveUserError,
    InvalidRefreshTokenError,
)
from app.application.identity.ports import (
    AccessTokenService,
    RefreshTokenRepository,
    RefreshTokenService,
    UserRepository,
)
from app.domain.identity.session import SessionTokens


class RefreshSession:
    def __init__(
        self,
        users: UserRepository,
        access_tokens: AccessTokenService,
        refresh_tokens: RefreshTokenService,
        refresh_token_repository: RefreshTokenRepository,
        refresh_token_days: int,
    ) -> None:
        self._users = users
        self._access_tokens = access_tokens
        self._refresh_tokens = refresh_tokens
        self._refresh_token_repository = refresh_token_repository
        self._refresh_token_lifetime = timedelta(days=refresh_token_days)

    def execute(self, current_refresh_token: str) -> SessionTokens:
        now = datetime.now(UTC)
        replacement = self._refresh_tokens.create()
        user_id = self._refresh_token_repository.rotate(
            token_hash=self._refresh_tokens.hash(current_refresh_token),
            replacement_hash=self._refresh_tokens.hash(replacement),
            replacement_expires_at=now + self._refresh_token_lifetime,
            now=now,
        )
        if user_id is None:
            raise InvalidRefreshTokenError

        user = self._users.get_by_id(user_id)
        if user is None:
            raise InvalidRefreshTokenError
        if not user.is_active:
            raise InactiveUserError

        return SessionTokens(
            access_token=self._access_tokens.create(user.id),
            refresh_token=replacement,
        )
