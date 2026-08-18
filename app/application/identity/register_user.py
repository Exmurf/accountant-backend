from app.application.identity.errors import EmailAlreadyRegisteredError
from app.application.identity.ports import PasswordHasher, UserRepository
from app.domain.identity.user import User


class RegisterUser:
    def __init__(self, users: UserRepository, passwords: PasswordHasher) -> None:
        self._users = users
        self._passwords = passwords

    def execute(self, email: str, display_name: str, password: str) -> User:
        normalized_email = email.strip().lower()
        normalized_name = display_name.strip()

        if self._users.get_by_email(normalized_email) is not None:
            raise EmailAlreadyRegisteredError

        return self._users.add(
            email=normalized_email,
            display_name=normalized_name,
            password_hash=self._passwords.hash(password),
        )
