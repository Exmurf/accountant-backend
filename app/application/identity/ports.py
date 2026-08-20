from datetime import datetime, time
from typing import Protocol
from uuid import UUID

from app.domain.identity.email_change import PendingEmailChange
from app.domain.identity.session import AccessTokenClaims
from app.domain.identity.user import User


class UserRepository(Protocol):
    def list_all(self) -> list[User]: ...

    def list_active(self) -> list[User]: ...

    def get_by_email(self, email: str) -> User | None: ...

    def get_by_id(self, user_id: UUID) -> User | None: ...

    def add(self, email: str, display_name: str, password_hash: str) -> User: ...

    def update_settings(
        self,
        user_id: UUID,
        display_name: str,
        daily_summary_enabled: bool,
        daily_summary_time: time,
        budget_alerts_enabled: bool,
    ) -> User | None: ...

    def update_password(self, user_id: UUID, password_hash: str) -> User | None: ...

    def update_email(self, user_id: UUID, email: str) -> User | None: ...


class PasswordHasher(Protocol):
    def hash(self, password: str) -> str: ...

    def verify(self, password: str, password_hash: str) -> bool: ...


class AccessTokenService(Protocol):
    def create(self, user_id: UUID) -> str: ...

    def decode(self, token: str) -> AccessTokenClaims: ...


class RefreshTokenService(Protocol):
    def create(self) -> str: ...

    def hash(self, token: str) -> str: ...


class EmailChangeTokenRepository(Protocol):
    def replace_for_user(
        self,
        user_id: UUID,
        new_email: str,
        token_hash: str,
        expires_at: datetime,
        now: datetime,
    ) -> None: ...

    def consume(
        self,
        token_hash: str,
        now: datetime,
    ) -> PendingEmailChange | None: ...


class PasswordResetTokenRepository(Protocol):
    def replace_for_user(
        self,
        user_id: UUID,
        token_hash: str,
        expires_at: datetime,
        now: datetime,
    ) -> None: ...

    def consume(self, token_hash: str, now: datetime) -> UUID | None: ...


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

    def revoke_all_for_user(self, user_id: UUID, now: datetime) -> None: ...
