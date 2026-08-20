from typing import Protocol
from uuid import UUID

from app.domain.savings.models import MonthlySaving


class MonthlyCashFlowReader(Protocol):
    def monthly_totals(
        self,
        user_id: UUID,
        timezone_name: str,
    ) -> dict[tuple[int, int], tuple[int, int]]: ...


class SavingsGoalRepository(Protocol):
    def set_savings_goal(self, user_id: UUID, amount_minor: int) -> int | None: ...


class SavingsRepository(Protocol):
    def list_for_user(self, user_id: UUID) -> list[MonthlySaving]: ...

    def upsert_month(
        self,
        user_id: UUID,
        year: int,
        month: int,
        amount_minor: int,
    ) -> MonthlySaving: ...
