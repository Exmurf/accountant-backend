from datetime import datetime
from typing import Protocol
from uuid import UUID

from app.domain.admin.models import AdminCategorySpending, UserFinanceTotals
from app.domain.identity.user import User
from app.domain.ledger.models import Transaction
from app.domain.ledger.subscription import Subscription


class AdminUserReader(Protocol):
    def list_all(self) -> list[User]: ...

    def get_by_id(self, user_id: UUID) -> User | None: ...


class AdminFinanceReader(Protocol):
    def get_totals(self, user_id: UUID, before: datetime) -> UserFinanceTotals: ...

    def list_recent_transactions(
        self,
        user_id: UUID,
        before: datetime,
        limit: int,
    ) -> list[Transaction]: ...

    def list_category_spending(
        self,
        user_id: UUID,
        before: datetime,
    ) -> list[AdminCategorySpending]: ...

    def list_active_subscriptions(self, user_id: UUID) -> list[Subscription]: ...
