from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

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


class SavingsOverviewResponse(BaseModel):
    total_saved_minor: int
    current_month_projection_minor: int
    entries: list[MonthlySavingResponse]

    @classmethod
    def from_domain(cls, overview: SavingsOverview) -> "SavingsOverviewResponse":
        return cls(
            total_saved_minor=overview.total_saved_minor,
            current_month_projection_minor=(
                overview.current_month_projection_minor
            ),
            entries=[
                MonthlySavingResponse.from_domain(entry)
                for entry in overview.entries
            ],
        )
