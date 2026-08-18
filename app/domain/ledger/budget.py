from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True, slots=True)
class MonthlyBudget:
    id: UUID
    user_id: UUID
    category_id: UUID
    category_name: str
    category_color: str
    limit_minor: int
    created_at: datetime
    updated_at: datetime
