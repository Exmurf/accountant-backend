from dataclasses import dataclass
from datetime import date, datetime
from uuid import UUID


@dataclass(frozen=True, slots=True)
class Subscription:
    id: UUID
    user_id: UUID
    category_id: UUID
    category_name: str
    category_color: str
    name: str
    amount_minor: int
    billing_day: int
    next_charge_date: date
    is_active: bool
    created_at: datetime
