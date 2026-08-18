from datetime import time
from uuid import UUID

from app.application.identity.ports import UserRepository
from app.domain.identity.user import User


class UpdateUserSettings:
    def __init__(self, users: UserRepository) -> None:
        self._users = users

    def execute(
        self,
        user_id: UUID,
        display_name: str,
        daily_summary_enabled: bool,
        daily_summary_time: time,
        budget_alerts_enabled: bool,
    ) -> User:
        normalized_name = display_name.strip()
        user = self._users.update_settings(
            user_id=user_id,
            display_name=normalized_name,
            daily_summary_enabled=daily_summary_enabled,
            daily_summary_time=daily_summary_time,
            budget_alerts_enabled=budget_alerts_enabled,
        )
        if user is None:
            raise RuntimeError("Authenticated user could not be updated")
        return user
