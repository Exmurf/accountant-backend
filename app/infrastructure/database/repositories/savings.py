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

    def totals_for_period(
        self,
        user_id: UUID,
        start: datetime,
        end: datetime,
    ) -> tuple[int, int]:
        income_minor, expense_minor = self._session.execute(
            select(
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
            ).where(
                TransactionModel.user_id == user_id,
                TransactionModel.occurred_at >= start,
                TransactionModel.occurred_at < end,
            )
        ).one()
        return int(income_minor), int(expense_minor)

    def earliest_transaction_at(self, user_id: UUID) -> datetime | None:
        return self._session.scalar(
            select(func.min(TransactionModel.occurred_at)).where(
                TransactionModel.user_id == user_id
            )
        )


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
