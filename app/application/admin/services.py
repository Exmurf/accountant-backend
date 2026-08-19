from dataclasses import replace
from datetime import datetime
from uuid import UUID

from app.application.admin.errors import (
    AdminUserNotFoundError,
    CannotDeactivateSelfError,
    CannotRemoveOwnAdminRoleError,
)
from app.application.admin.ports import (
    AdminFinanceReader,
    AdminUserManager,
    AdminUserReader,
)
from app.domain.identity.user import User
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
                finances=replace(
                    self._finances.get_totals(user.id, before),
                    opening_balance_minor=user.opening_balance_minor,
                ),
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


class ChangeAdminUserStatus:
    def __init__(self, users: AdminUserManager) -> None:
        self._users = users

    def execute(
        self,
        actor_id: UUID,
        target_user_id: UUID,
        is_active: bool,
    ) -> User:
        if actor_id == target_user_id and not is_active:
            raise CannotDeactivateSelfError
        user = self._users.set_active(target_user_id, is_active)
        if user is None:
            raise AdminUserNotFoundError
        return user


class ChangeAdminUserRole:
    def __init__(self, users: AdminUserManager) -> None:
        self._users = users

    def execute(
        self,
        actor_id: UUID,
        target_user_id: UUID,
        is_admin: bool,
    ) -> User:
        if actor_id == target_user_id and not is_admin:
            raise CannotRemoveOwnAdminRoleError
        user = self._users.set_admin_role(target_user_id, is_admin)
        if user is None:
            raise AdminUserNotFoundError
        return user
