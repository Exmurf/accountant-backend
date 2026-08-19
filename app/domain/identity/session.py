from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True, slots=True)
class SessionTokens:
    access_token: str
    refresh_token: str


@dataclass(frozen=True, slots=True)
class AccessTokenClaims:
    user_id: UUID
    issued_at: datetime
