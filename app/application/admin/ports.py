from datetime import datetime
from typing import Protocol
from uuid import UUID

from app.domain.admin.models import UserFinanceTotals
from app.domain.identity.user import User


class AdminUserReader(Protocol):
    def list_all(self) -> list[User]: ...


class AdminFinanceReader(Protocol):
    def get_totals(self, user_id: UUID, before: datetime) -> UserFinanceTotals: ...
