from datetime import datetime

from app.application.admin.ports import AdminFinanceReader, AdminUserReader
from app.domain.admin.models import AdminUserSummary


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
