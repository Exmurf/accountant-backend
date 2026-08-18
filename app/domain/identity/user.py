from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True, slots=True)
class User:
    id: UUID
    email: str
    display_name: str
    password_hash: str
    is_active: bool
    roles: frozenset[str]
    permissions: frozenset[str]
    created_at: datetime
