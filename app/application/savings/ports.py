from datetime import datetime
from typing import Protocol
from uuid import UUID

from app.domain.savings.models import MonthlySaving


class MonthlyCashFlowReader(Protocol):
    def totals_for_period(
        self,
        user_id: UUID,
        start: datetime,
        end: datetime,
    ) -> tuple[int, int]: ...


class SavingsRepository(Protocol):
    def list_for_user(self, user_id: UUID) -> list[MonthlySaving]: ...

    def upsert_month(
        self,
        user_id: UUID,
        year: int,
        month: int,
        amount_minor: int,
    ) -> MonthlySaving: ...
