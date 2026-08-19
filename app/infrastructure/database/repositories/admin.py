from datetime import datetime
from uuid import UUID

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app.domain.admin.models import UserFinanceTotals
from app.domain.ledger.models import TransactionKind
from app.infrastructure.database.models.ledger import TransactionModel


class SqlAlchemyAdminFinanceReader:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_totals(self, user_id: UUID, before: datetime) -> UserFinanceTotals:
        total_income, total_expense, transaction_count = self._session.execute(
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
                func.count(TransactionModel.id),
            ).where(
                TransactionModel.user_id == user_id,
                TransactionModel.occurred_at < before,
            )
        ).one()
        return UserFinanceTotals(
            total_income_minor=int(total_income),
            total_expense_minor=int(total_expense),
            transaction_count=int(transaction_count),
        )
