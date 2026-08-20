from datetime import date, datetime
from uuid import UUID
from zoneinfo import ZoneInfo

from app.application.savings.ports import (
    MonthlyCashFlowReader,
    SavingsGoalRepository,
    SavingsRepository,
)
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
        timezone: ZoneInfo,
        goal_minor: int = 0,
    ) -> SavingsOverview:
        # The whole ledger, bucketed by month, in one read. Every month the walk
        # covers is answered from here.
        totals = self._cash_flow.monthly_totals(user_id, timezone.key)

        account_created_local = account_created_at.astimezone(timezone)
        cursor = date(
            account_created_local.year,
            account_created_local.month,
            1,
        )

        # Signing up is not where the history starts. A transaction may carry
        # any past date, and a month the walk never reaches is a month that
        # never gets closed, so it would be missing from savings for good.
        if totals:
            earliest_year, earliest_month = min(totals)
            cursor = min(cursor, date(earliest_year, earliest_month, 1))

        current_month = date(today.year, today.month, 1)
        accumulated_minor = 0

        while cursor < current_month:
            income_minor, expense_minor = totals.get(
                (cursor.year, cursor.month),
                (0, 0),
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
            cursor = _next_month(cursor)

        current_income_minor, current_expense_minor = totals.get(
            (current_month.year, current_month.month),
            (0, 0),
        )
        entries = self._savings.list_for_user(user_id)
        return SavingsOverview(
            total_saved_minor=sum(entry.amount_minor for entry in entries),
            current_month_projection_minor=max(
                current_income_minor - current_expense_minor,
                -accumulated_minor,
            ),
            entries=tuple(entries),
            goal_minor=goal_minor,
        )


class SetSavingsGoal:
    """Store the amount the savings chart is measured against."""

    def __init__(self, users: SavingsGoalRepository) -> None:
        self._users = users

    def execute(self, user_id: UUID, goal_minor: int) -> int:
        stored = self._users.set_savings_goal(user_id, goal_minor)
        if stored is None:
            raise RuntimeError("Authenticated user could not be updated")
        return stored
