from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True, slots=True)
class MonthlySaving:
    id: UUID
    user_id: UUID
    year: int
    month: int
    amount_minor: int
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class SavingsOverview:
    total_saved_minor: int
    current_month_projection_minor: int
    entries: tuple[MonthlySaving, ...]
