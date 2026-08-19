from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field

from app.domain.savings.models import MonthlySaving, SavingsOverview


class MonthlySavingResponse(BaseModel):
    id: UUID
    year: int
    month: int
    amount_minor: int
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_domain(cls, saving: MonthlySaving) -> "MonthlySavingResponse":
        return cls(
            id=saving.id,
            year=saving.year,
            month=saving.month,
            amount_minor=saving.amount_minor,
            created_at=saving.created_at,
            updated_at=saving.updated_at,
        )


class SetSavingsGoalRequest(BaseModel):
    goal: Decimal = Field(ge=0, max_digits=12, decimal_places=2)

    def goal_as_minor(self) -> int:
        return int(self.goal * 100)


class SavingsOverviewResponse(BaseModel):
    total_saved_minor: int
    current_month_projection_minor: int
    goal_minor: int
    entries: list[MonthlySavingResponse]

    @classmethod
    def from_domain(cls, overview: SavingsOverview) -> "SavingsOverviewResponse":
        return cls(
            total_saved_minor=overview.total_saved_minor,
            current_month_projection_minor=(
                overview.current_month_projection_minor
            ),
            goal_minor=overview.goal_minor,
            entries=[
                MonthlySavingResponse.from_domain(entry)
                for entry in overview.entries
            ],
        )
