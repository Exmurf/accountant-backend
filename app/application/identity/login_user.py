from app.application.identity.errors import (
    InactiveUserError,
    InvalidCredentialsError,
)
from app.application.identity.ports import PasswordHasher, UserRepository
from app.domain.identity.user import User


class LoginUser:
    def __init__(self, users: UserRepository, passwords: PasswordHasher) -> None:
        self._users = users
        self._passwords = passwords

    def execute(self, email: str, password: str) -> User:
        user = self._users.get_by_email(email.strip().lower())

        if user is None or not self._passwords.verify(password, user.password_hash):
            raise InvalidCredentialsError
        if not user.is_active:
            raise InactiveUserError

        return user
