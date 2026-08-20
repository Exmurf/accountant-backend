from datetime import UTC, datetime

from app.application.identity.errors import InvalidPasswordResetTokenError
from app.application.identity.ports import (
    PasswordHasher,
    PasswordResetTokenRepository,
    RefreshTokenRepository,
    RefreshTokenService,
    UserRepository,
)
from app.domain.identity.user import User


class ResetPassword:
    def __init__(
        self,
        users: UserRepository,
        passwords: PasswordHasher,
        reset_tokens: PasswordResetTokenRepository,
        token_service: RefreshTokenService,
        refresh_token_repository: RefreshTokenRepository,
    ) -> None:
        self._users = users
        self._passwords = passwords
        self._reset_tokens = reset_tokens
        self._token_service = token_service
        self._refresh_token_repository = refresh_token_repository

    def execute(self, token: str, new_password: str) -> User:
        now = datetime.now(UTC)
        # Spending the token is the first thing that happens, so a link cannot
        # be replayed even if two requests arrive at once.
        user_id = self._reset_tokens.consume(self._token_service.hash(token), now)
        if user_id is None:
            raise InvalidPasswordResetTokenError

        user = self._users.get_by_id(user_id)
        if user is None or not user.is_active:
            raise InvalidPasswordResetTokenError

        # Reusing the current password is allowed here. Somebody who reached
        # this screen does not know what the old one was, and refusing would
        # answer a question they never asked.
        updated = self._users.update_password(
            user_id,
            self._passwords.hash(new_password),
        )
        if updated is None:
            raise RuntimeError("User behind a valid reset token could not be updated")

        # The likely reason for a reset is that somebody else got in, so every
        # session opened with the old password ends here.
        self._refresh_token_repository.revoke_all_for_user(user_id, now)
        return updated
