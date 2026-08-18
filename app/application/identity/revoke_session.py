from datetime import UTC, datetime

from app.application.identity.ports import (
    RefreshTokenRepository,
    RefreshTokenService,
)


class RevokeSession:
    def __init__(
        self,
        refresh_tokens: RefreshTokenService,
        refresh_token_repository: RefreshTokenRepository,
    ) -> None:
        self._refresh_tokens = refresh_tokens
        self._refresh_token_repository = refresh_token_repository

    def execute(self, refresh_token: str) -> None:
        self._refresh_token_repository.revoke(
            token_hash=self._refresh_tokens.hash(refresh_token),
            now=datetime.now(UTC),
        )
