from datetime import UTC, datetime
from uuid import UUID

from app.application.identity.errors import (
    InvalidCredentialsError,
    PasswordUnchangedError,
)
from app.application.identity.ports import (
    PasswordHasher,
    RefreshTokenRepository,
    UserRepository,
)
from app.domain.identity.user import User


class ChangePassword:
    def __init__(
        self,
        users: UserRepository,
        passwords: PasswordHasher,
        refresh_token_repository: RefreshTokenRepository,
    ) -> None:
        self._users = users
        self._passwords = passwords
        self._refresh_token_repository = refresh_token_repository

    def execute(
        self,
        user_id: UUID,
        current_password: str,
        new_password: str,
    ) -> User:
        user = self._users.get_by_id(user_id)
        if user is None or not self._passwords.verify(
            current_password,
            user.password_hash,
        ):
            raise InvalidCredentialsError
        if self._passwords.verify(new_password, user.password_hash):
            raise PasswordUnchangedError

        updated = self._users.update_password(
            user_id,
            self._passwords.hash(new_password),
        )
        if updated is None:
            raise RuntimeError("Authenticated user could not be updated")

        # A changed password must end every session opened with the old one,
        # including any the owner no longer controls.
        self._refresh_token_repository.revoke_all_for_user(
            user_id,
            datetime.now(UTC),
        )
        return updated
