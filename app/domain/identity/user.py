from dataclasses import dataclass
from datetime import datetime, time
from uuid import UUID


@dataclass(frozen=True, slots=True)
class User:
    id: UUID
    email: str
    display_name: str
    password_hash: str
    is_active: bool
    daily_summary_enabled: bool
    daily_summary_time: time
    budget_alerts_enabled: bool
    roles: frozenset[str]
    permissions: frozenset[str]
    created_at: datetime
