from datetime import datetime
from uuid import UUID

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session, joinedload

from app.domain.admin.models import AdminCategorySpending, UserFinanceTotals
from app.domain.identity.user import User
from app.domain.ledger.models import Transaction, TransactionKind
from app.domain.ledger.subscription import Subscription
from app.infrastructure.database.models.ledger import (
    CategoryModel,
    SubscriptionModel,
    TransactionModel,
)
from app.infrastructure.database.repositories.ledger import (
    to_subscription_domain,
    to_transaction_domain,
)
from app.infrastructure.database.models.identity import UserModel
from app.infrastructure.database.repositories.users import SqlAlchemyUserRepository


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

    def list_recent_transactions(
        self,
        user_id: UUID,
        before: datetime,
        limit: int,
    ) -> list[Transaction]:
        models = self._session.scalars(
            select(TransactionModel)
            .options(joinedload(TransactionModel.category))
            .where(
                TransactionModel.user_id == user_id,
                TransactionModel.occurred_at < before,
            )
            .order_by(TransactionModel.occurred_at.desc())
            .limit(limit)
        ).all()
        return [to_transaction_domain(model) for model in models]

    def list_category_spending(
        self,
        user_id: UUID,
        before: datetime,
    ) -> list[AdminCategorySpending]:
        rows = self._session.execute(
            select(
                CategoryModel.id,
                CategoryModel.name,
                CategoryModel.color,
                func.sum(TransactionModel.amount_minor).label("total_expense"),
            )
            .join(TransactionModel, TransactionModel.category_id == CategoryModel.id)
            .where(
                TransactionModel.user_id == user_id,
                TransactionModel.kind == TransactionKind.EXPENSE.value,
                TransactionModel.occurred_at < before,
            )
            .group_by(CategoryModel.id, CategoryModel.name, CategoryModel.color)
            .order_by(func.sum(TransactionModel.amount_minor).desc())
        ).all()
        return [
            AdminCategorySpending(
                category_id=row.id,
                category_name=row.name,
                category_color=row.color,
                total_expense_minor=int(row.total_expense),
            )
            for row in rows
        ]

    def list_active_subscriptions(self, user_id: UUID) -> list[Subscription]:
        models = self._session.scalars(
            select(SubscriptionModel)
            .options(joinedload(SubscriptionModel.category))
            .where(
                SubscriptionModel.user_id == user_id,
                SubscriptionModel.is_active.is_(True),
            )
            .order_by(SubscriptionModel.next_charge_date, SubscriptionModel.name)
        ).all()
        return [to_subscription_domain(model) for model in models]


class SqlAlchemyAdminUserManager:
    def __init__(self, session: Session) -> None:
        self._session = session

    def set_active(self, user_id: UUID, is_active: bool) -> User | None:
        model = self._session.get(UserModel, user_id)
        if model is None:
            return None
        model.is_active = is_active
        self._session.commit()
        return SqlAlchemyUserRepository(self._session).get_by_id(user_id)
