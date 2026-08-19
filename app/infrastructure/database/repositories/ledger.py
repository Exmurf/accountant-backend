from datetime import date, datetime
from uuid import UUID

from sqlalchemy import case, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload, selectinload

from app.application.ledger.errors import (
    BudgetAlreadyExistsError,
    CategoryAlreadyExistsError,
)
from app.domain.ledger.budget import MonthlyBudget
from app.domain.ledger.models import (
    AccountBalance,
    Category,
    Transaction,
    TransactionKind,
)
from app.domain.ledger.subscription import Subscription
from app.infrastructure.database.models.ledger import (
    CategoryModel,
    MonthlyBudgetModel,
    SubscriptionModel,
    TransactionModel,
)


class SqlAlchemyCategoryRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def list_available(
        self,
        user_id: UUID,
        kind: TransactionKind | None = None,
    ) -> list[Category]:
        query = select(CategoryModel).where(
            or_(CategoryModel.user_id.is_(None), CategoryModel.user_id == user_id)
        )
        if kind is not None:
            query = query.where(CategoryModel.kind == kind.value)
        models = self._session.scalars(query.order_by(CategoryModel.name)).all()
        return [self._category_to_domain(model) for model in models]

    def get_available_by_id(
        self,
        user_id: UUID,
        category_id: UUID,
    ) -> Category | None:
        model = self._session.scalar(
            select(CategoryModel).where(
                CategoryModel.id == category_id,
                or_(CategoryModel.user_id.is_(None), CategoryModel.user_id == user_id),
            )
        )
        return self._category_to_domain(model) if model is not None else None

    def add(
        self,
        user_id: UUID,
        name: str,
        kind: TransactionKind,
        color: str,
    ) -> Category:
        model = CategoryModel(
            user_id=user_id,
            name=name,
            kind=kind.value,
            color=color,
        )
        self._session.add(model)
        try:
            self._session.commit()
        except IntegrityError as error:
            self._session.rollback()
            raise CategoryAlreadyExistsError from error
        return self._category_to_domain(model)

    @staticmethod
    def _category_to_domain(model: CategoryModel) -> Category:
        return Category(
            id=model.id,
            user_id=model.user_id,
            name=model.name,
            kind=TransactionKind(model.kind),
            color=model.color,
        )


class SqlAlchemyTransactionRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_balance(self, user_id: UUID, before: datetime) -> AccountBalance:
        total_income, total_expense = self._session.execute(
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
                TransactionModel.occurred_at < before,
            )
        ).one()
        return AccountBalance(
            total_income_minor=int(total_income),
            total_expense_minor=int(total_expense),
        )

    def list_for_user(
        self,
        user_id: UUID,
        start: datetime,
        end: datetime,
        category_id: UUID | None = None,
        kind: TransactionKind | None = None,
    ) -> list[Transaction]:
        query = (
            select(TransactionModel)
            .options(joinedload(TransactionModel.category))
            .where(
                TransactionModel.user_id == user_id,
                TransactionModel.occurred_at >= start,
                TransactionModel.occurred_at < end,
            )
        )
        if category_id is not None:
            query = query.where(TransactionModel.category_id == category_id)
        if kind is not None:
            query = query.where(TransactionModel.kind == kind.value)
        models = self._session.scalars(
            query.order_by(TransactionModel.occurred_at.desc())
        ).all()
        return [self._transaction_to_domain(model) for model in models]

    def add(
        self,
        user_id: UUID,
        category: Category,
        kind: TransactionKind,
        amount_minor: int,
        description: str,
        occurred_at: datetime,
    ) -> Transaction:
        model = TransactionModel(
            user_id=user_id,
            category_id=category.id,
            kind=kind.value,
            amount_minor=amount_minor,
            description=description,
            occurred_at=occurred_at,
            subscription_id=None,
            subscription_charge_date=None,
        )
        self._session.add(model)
        self._session.commit()
        model.category = self._session.get(CategoryModel, category.id)
        return self._transaction_to_domain(model)

    def update(
        self,
        user_id: UUID,
        transaction_id: UUID,
        category: Category,
        kind: TransactionKind,
        amount_minor: int,
        description: str,
        occurred_at: datetime,
    ) -> Transaction | None:
        model = self._session.scalar(
            select(TransactionModel).where(
                TransactionModel.id == transaction_id,
                TransactionModel.user_id == user_id,
            )
        )
        if model is None:
            return None

        model.category_id = category.id
        model.kind = kind.value
        model.amount_minor = amount_minor
        model.description = description
        model.occurred_at = occurred_at
        self._session.commit()
        model.category = self._session.get(CategoryModel, category.id)
        return self._transaction_to_domain(model)

    def remove(self, user_id: UUID, transaction_id: UUID) -> bool:
        model = self._session.scalar(
            select(TransactionModel).where(
                TransactionModel.id == transaction_id,
                TransactionModel.user_id == user_id,
            )
        )
        if model is None:
            return False

        self._session.delete(model)
        self._session.commit()
        return True

    def add_subscription_charge(
        self,
        subscription: Subscription,
        charge_date: date,
        occurred_at: datetime,
    ) -> Transaction | None:
        existing = self._session.scalar(
            select(TransactionModel).where(
                TransactionModel.subscription_id == subscription.id,
                TransactionModel.subscription_charge_date == charge_date,
            )
        )
        if existing is not None:
            return None

        model = TransactionModel(
            user_id=subscription.user_id,
            category_id=subscription.category_id,
            kind=TransactionKind.EXPENSE.value,
            amount_minor=subscription.amount_minor,
            description=subscription.name,
            occurred_at=occurred_at,
            subscription_id=subscription.id,
            subscription_charge_date=charge_date,
        )
        self._session.add(model)
        try:
            self._session.commit()
        except IntegrityError:
            self._session.rollback()
            return None
        model.category = self._session.get(CategoryModel, subscription.category_id)
        return self._transaction_to_domain(model)

    @staticmethod
    def _transaction_to_domain(model: TransactionModel) -> Transaction:
        return Transaction(
            id=model.id,
            user_id=model.user_id,
            category_id=model.category_id,
            category_name=model.category.name,
            category_color=model.category.color,
            kind=TransactionKind(model.kind),
            amount_minor=model.amount_minor,
            description=model.description,
            occurred_at=model.occurred_at,
            created_at=model.created_at,
            subscription_id=model.subscription_id,
            subscription_charge_date=model.subscription_charge_date,
        )


class SqlAlchemySubscriptionRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def list_active(self, user_id: UUID) -> list[Subscription]:
        models = self._session.scalars(
            self._subscription_query()
            .where(
                SubscriptionModel.user_id == user_id,
                SubscriptionModel.is_active.is_(True),
            )
            .order_by(SubscriptionModel.next_charge_date, SubscriptionModel.name)
        ).all()
        return [self._subscription_to_domain(model) for model in models]

    def list_due(self, user_id: UUID, through_date: date) -> list[Subscription]:
        models = self._session.scalars(
            self._subscription_query()
            .where(
                SubscriptionModel.user_id == user_id,
                SubscriptionModel.is_active.is_(True),
                SubscriptionModel.next_charge_date <= through_date,
            )
            .with_for_update()
        ).all()
        return [self._subscription_to_domain(model) for model in models]

    def add(
        self,
        user_id: UUID,
        category: Category,
        name: str,
        amount_minor: int,
        first_charge_date: date,
    ) -> Subscription:
        model = SubscriptionModel(
            user_id=user_id,
            category_id=category.id,
            name=name,
            amount_minor=amount_minor,
            billing_day=first_charge_date.day,
            next_charge_date=first_charge_date,
        )
        self._session.add(model)
        self._session.commit()
        model.category = self._session.get(CategoryModel, category.id)
        return self._subscription_to_domain(model)

    def update_next_charge(
        self,
        user_id: UUID,
        subscription_id: UUID,
        next_charge_date: date,
    ) -> None:
        model = self._session.scalar(
            select(SubscriptionModel).where(
                SubscriptionModel.id == subscription_id,
                SubscriptionModel.user_id == user_id,
            )
        )
        if model is not None:
            model.next_charge_date = next_charge_date
            self._session.commit()

    def update_amount(
        self,
        user_id: UUID,
        subscription_id: UUID,
        amount_minor: int,
    ) -> Subscription | None:
        model = self._session.scalar(
            self._subscription_query().where(
                SubscriptionModel.id == subscription_id,
                SubscriptionModel.user_id == user_id,
                SubscriptionModel.is_active.is_(True),
            )
        )
        if model is None:
            return None
        model.amount_minor = amount_minor
        self._session.commit()
        return self._subscription_to_domain(model)

    def deactivate(self, user_id: UUID, subscription_id: UUID) -> bool:
        model = self._session.scalar(
            select(SubscriptionModel).where(
                SubscriptionModel.id == subscription_id,
                SubscriptionModel.user_id == user_id,
                SubscriptionModel.is_active.is_(True),
            )
        )
        if model is None:
            return False
        model.is_active = False
        self._session.commit()
        return True

    @staticmethod
    def _subscription_query():  # type: ignore[no-untyped-def]
        return select(SubscriptionModel).options(
            selectinload(SubscriptionModel.category)
        )

    @staticmethod
    def _subscription_to_domain(model: SubscriptionModel) -> Subscription:
        return Subscription(
            id=model.id,
            user_id=model.user_id,
            category_id=model.category_id,
            category_name=model.category.name,
            category_color=model.category.color,
            name=model.name,
            amount_minor=model.amount_minor,
            billing_day=model.billing_day,
            next_charge_date=model.next_charge_date,
            is_active=model.is_active,
            created_at=model.created_at,
        )


class SqlAlchemyBudgetRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def list_for_user(self, user_id: UUID) -> list[MonthlyBudget]:
        models = self._session.scalars(
            self._budget_query()
            .join(MonthlyBudgetModel.category)
            .where(MonthlyBudgetModel.user_id == user_id)
            .order_by(CategoryModel.name)
        ).all()
        return [self._budget_to_domain(model) for model in models]

    def upsert(
        self,
        user_id: UUID,
        category: Category,
        limit_minor: int,
    ) -> MonthlyBudget:
        model = self._session.scalar(
            self._budget_query().where(
                MonthlyBudgetModel.user_id == user_id,
                MonthlyBudgetModel.category_id == category.id,
            )
        )
        if model is None:
            model = MonthlyBudgetModel(
                user_id=user_id,
                category_id=category.id,
                limit_minor=limit_minor,
            )
            self._session.add(model)
        else:
            model.limit_minor = limit_minor
        self._session.commit()
        model.category = self._session.get(CategoryModel, category.id)
        return self._budget_to_domain(model)

    def update(
        self,
        user_id: UUID,
        budget_id: UUID,
        category: Category,
        limit_minor: int,
    ) -> MonthlyBudget | None:
        model = self._session.scalar(
            self._budget_query().where(
                MonthlyBudgetModel.id == budget_id,
                MonthlyBudgetModel.user_id == user_id,
            )
        )
        if model is None:
            return None
        model.category_id = category.id
        model.limit_minor = limit_minor
        try:
            self._session.commit()
        except IntegrityError as error:
            self._session.rollback()
            raise BudgetAlreadyExistsError from error
        model.category = self._session.get(CategoryModel, category.id)
        return self._budget_to_domain(model)

    def remove(self, user_id: UUID, category_id: UUID) -> bool:
        model = self._session.scalar(
            select(MonthlyBudgetModel).where(
                MonthlyBudgetModel.user_id == user_id,
                MonthlyBudgetModel.category_id == category_id,
            )
        )
        if model is None:
            return False
        self._session.delete(model)
        self._session.commit()
        return True

    @staticmethod
    def _budget_query():  # type: ignore[no-untyped-def]
        return select(MonthlyBudgetModel).options(
            selectinload(MonthlyBudgetModel.category)
        )

    @staticmethod
    def _budget_to_domain(model: MonthlyBudgetModel) -> MonthlyBudget:
        return MonthlyBudget(
            id=model.id,
            user_id=model.user_id,
            category_id=model.category_id,
            category_name=model.category.name,
            category_color=model.category.color,
            limit_minor=model.limit_minor,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )
