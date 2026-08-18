from datetime import UTC, datetime, timedelta

from app.application.identity.ports import (
    AccessTokenService,
    RefreshTokenRepository,
    RefreshTokenService,
)
from app.domain.identity.session import SessionTokens
from app.domain.identity.user import User


class IssueSession:
    def __init__(
        self,
        access_tokens: AccessTokenService,
        refresh_tokens: RefreshTokenService,
        refresh_token_repository: RefreshTokenRepository,
        refresh_token_days: int,
    ) -> None:
        self._access_tokens = access_tokens
        self._refresh_tokens = refresh_tokens
        self._refresh_token_repository = refresh_token_repository
        self._refresh_token_lifetime = timedelta(days=refresh_token_days)

    def execute(self, user: User) -> SessionTokens:
        refresh_token = self._refresh_tokens.create()
        self._refresh_token_repository.add(
            user_id=user.id,
            token_hash=self._refresh_tokens.hash(refresh_token),
            expires_at=datetime.now(UTC) + self._refresh_token_lifetime,
        )
        return SessionTokens(
            access_token=self._access_tokens.create(user.id),
            refresh_token=refresh_token,
        )
