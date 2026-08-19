from datetime import date, datetime, time, tzinfo
from uuid import UUID

from app.application.savings.ports import MonthlyCashFlowReader, SavingsRepository
from app.domain.savings.models import SavingsOverview


def _next_month(value: date) -> date:
    if value.month == 12:
        return date(value.year + 1, 1, 1)
    return date(value.year, value.month + 1, 1)


class ProcessMonthlySavings:
    def __init__(
        self,
        cash_flow: MonthlyCashFlowReader,
        savings: SavingsRepository,
    ) -> None:
        self._cash_flow = cash_flow
        self._savings = savings

    def execute(
        self,
        user_id: UUID,
        account_created_at: datetime,
        today: date,
        timezone: tzinfo,
    ) -> SavingsOverview:
        account_created_local = account_created_at.astimezone(timezone)
        cursor = date(
            account_created_local.year,
            account_created_local.month,
            1,
        )
        current_month = date(today.year, today.month, 1)
        accumulated_minor = 0

        while cursor < current_month:
            following_month = _next_month(cursor)
            income_minor, expense_minor = self._cash_flow.totals_for_period(
                user_id,
                datetime.combine(cursor, time.min, tzinfo=timezone),
                datetime.combine(following_month, time.min, tzinfo=timezone),
            )
            monthly_change_minor = max(
                income_minor - expense_minor,
                -accumulated_minor,
            )
            self._savings.upsert_month(
                user_id=user_id,
                year=cursor.year,
                month=cursor.month,
                amount_minor=monthly_change_minor,
            )
            accumulated_minor += monthly_change_minor
            cursor = following_month

        following_month = _next_month(current_month)
        current_income_minor, current_expense_minor = (
            self._cash_flow.totals_for_period(
                user_id,
                datetime.combine(current_month, time.min, tzinfo=timezone),
                datetime.combine(following_month, time.min, tzinfo=timezone),
            )
        )
        entries = self._savings.list_for_user(user_id)
        return SavingsOverview(
            total_saved_minor=sum(entry.amount_minor for entry in entries),
            current_month_projection_minor=max(
                current_income_minor - current_expense_minor,
                -accumulated_minor,
            ),
            entries=tuple(entries),
        )
