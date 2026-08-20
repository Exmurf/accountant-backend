from datetime import datetime
from uuid import UUID

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app.domain.ledger.models import TransactionKind
from app.domain.savings.models import MonthlySaving
from app.infrastructure.database.models.ledger import TransactionModel
from app.infrastructure.database.models.savings import MonthlySavingModel


class SqlAlchemyMonthlyCashFlowReader:
    def __init__(self, session: Session) -> None:
        self._session = session

    def monthly_totals(
        self,
        user_id: UUID,
        timezone_name: str,
    ) -> dict[tuple[int, int], tuple[int, int]]:
        """Every month's income and expense in a single pass.

        Months used to be totalled one query at a time as the walk stepped
        through them, which made the savings page slower the longer somebody
        had been using the app. Grouping happens in the user's own zone, so a
        purchase made just before midnight belongs to the month they made it in
        rather than the month UTC happened to be in.
        """
        month_start = func.date_trunc(
            "month",
            func.timezone(timezone_name, TransactionModel.occurred_at),
        ).label("month_start")
        rows = self._session.execute(
            select(
                month_start,
                func.coalesce(
                    func.sum(
                        case(
                            (
                                TransactionModel.kind
                                == TransactionKind.INCOME.value,
                                TransactionModel.amount_minor,
                            ),
                            else_=0,
                        )
                    ),
                    0,
                ),
                func.coalesce(
                    func.sum(
                        case(
                            (
                                TransactionModel.kind
                                == TransactionKind.EXPENSE.value,
                                TransactionModel.amount_minor,
                            ),
                            else_=0,
                        )
                    ),
                    0,
                ),
            )
            .where(TransactionModel.user_id == user_id)
            .group_by(month_start)
        ).all()
        return {
            (row[0].year, row[0].month): (int(row[1]), int(row[2]))
            for row in rows
        }


class SqlAlchemySavingsRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def list_for_user(self, user_id: UUID) -> list[MonthlySaving]:
        models = self._session.scalars(
            select(MonthlySavingModel)
            .where(MonthlySavingModel.user_id == user_id)
            .order_by(MonthlySavingModel.year, MonthlySavingModel.month)
        ).all()
        return [self._to_domain(model) for model in models]

    def upsert_month(
        self,
        user_id: UUID,
        year: int,
        month: int,
        amount_minor: int,
    ) -> MonthlySaving:
        model = self._session.scalar(
            select(MonthlySavingModel).where(
                MonthlySavingModel.user_id == user_id,
                MonthlySavingModel.year == year,
                MonthlySavingModel.month == month,
            )
        )
        if model is None:
            model = MonthlySavingModel(
                user_id=user_id,
                year=year,
                month=month,
                amount_minor=amount_minor,
            )
            self._session.add(model)
        else:
            model.amount_minor = amount_minor

        self._session.commit()
        self._session.refresh(model)
        return self._to_domain(model)

    @staticmethod
    def _to_domain(model: MonthlySavingModel) -> MonthlySaving:
        return MonthlySaving(
            id=model.id,
            user_id=model.user_id,
            year=model.year,
            month=model.month,
            amount_minor=model.amount_minor,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )
