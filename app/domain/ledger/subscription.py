from dataclasses import dataclass
from datetime import date, datetime
from uuid import UUID

from app.domain.ledger.models import TransactionKind


@dataclass(frozen=True, slots=True)
class Subscription:
    id: UUID
    user_id: UUID
    category_id: UUID
    category_name: str
    category_color: str
    kind: TransactionKind
    name: str
    amount_minor: int
    billing_day: int
    next_charge_date: date
    is_active: bool
    created_at: datetime
