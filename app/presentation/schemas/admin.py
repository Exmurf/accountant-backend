from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

from app.domain.admin.models import AdminUserSummary


class AdminUserSummaryResponse(BaseModel):
    id: UUID
    email: str
    display_name: str
    is_active: bool
    roles: list[str]
    created_at: datetime
    current_balance_minor: int
    total_income_minor: int
    total_expense_minor: int
    transaction_count: int

    @classmethod
    def from_domain(cls, user: AdminUserSummary) -> "AdminUserSummaryResponse":
        return cls(
            id=user.id,
            email=user.email,
            display_name=user.display_name,
            is_active=user.is_active,
            roles=list(user.roles),
            created_at=user.created_at,
            current_balance_minor=user.finances.current_balance_minor,
            total_income_minor=user.finances.total_income_minor,
            total_expense_minor=user.finances.total_expense_minor,
            transaction_count=user.finances.transaction_count,
        )
