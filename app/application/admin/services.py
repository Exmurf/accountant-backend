from datetime import datetime
from uuid import UUID

from app.application.admin.errors import AdminUserNotFoundError
from app.application.admin.ports import AdminFinanceReader, AdminUserReader
from app.domain.admin.models import AdminUserFinanceDetails, AdminUserSummary


class ListAdminUserSummaries:
    def __init__(
        self,
        users: AdminUserReader,
        finances: AdminFinanceReader,
    ) -> None:
        self._users = users
        self._finances = finances

    def execute(self, before: datetime) -> tuple[AdminUserSummary, ...]:
        return tuple(
            AdminUserSummary(
                id=user.id,
                email=user.email,
                display_name=user.display_name,
                is_active=user.is_active,
                roles=tuple(sorted(user.roles)),
                created_at=user.created_at,
                finances=self._finances.get_totals(user.id, before),
            )
            for user in self._users.list_all()
        )


class GetAdminUserFinanceDetails:
    def __init__(
        self,
        users: AdminUserReader,
        finances: AdminFinanceReader,
    ) -> None:
        self._users = users
        self._finances = finances

    def execute(
        self,
        user_id: UUID,
        before: datetime,
    ) -> AdminUserFinanceDetails:
        if self._users.get_by_id(user_id) is None:
            raise AdminUserNotFoundError

        return AdminUserFinanceDetails(
            user_id=user_id,
            recent_transactions=tuple(
                self._finances.list_recent_transactions(
                    user_id,
                    before,
                    limit=20,
                )
            ),
            category_spending=tuple(
                self._finances.list_category_spending(user_id, before)
            ),
            subscriptions=tuple(
                self._finances.list_active_subscriptions(user_id)
            ),
        )
