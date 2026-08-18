from datetime import datetime
from typing import Protocol
from uuid import UUID

from app.domain.identity.user import User


class UserRepository(Protocol):
    def list_active(self) -> list[User]: ...

    def get_by_email(self, email: str) -> User | None: ...

    def get_by_id(self, user_id: UUID) -> User | None: ...

    def add(self, email: str, display_name: str, password_hash: str) -> User: ...


class PasswordHasher(Protocol):
    def hash(self, password: str) -> str: ...

    def verify(self, password: str, password_hash: str) -> bool: ...


class AccessTokenService(Protocol):
    def create(self, user_id: UUID) -> str: ...

    def decode_subject(self, token: str) -> UUID: ...


class RefreshTokenService(Protocol):
    def create(self) -> str: ...

    def hash(self, token: str) -> str: ...


class RefreshTokenRepository(Protocol):
    def add(self, user_id: UUID, token_hash: str, expires_at: datetime) -> None: ...

    def rotate(
        self,
        token_hash: str,
        replacement_hash: str,
        replacement_expires_at: datetime,
        now: datetime,
    ) -> UUID | None: ...

    def revoke(self, token_hash: str, now: datetime) -> None: ...
