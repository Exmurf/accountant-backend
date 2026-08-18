from datetime import datetime, time, timedelta
from typing import Annotated
from uuid import UUID
from zoneinfo import ZoneInfo

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.application.ledger.categories import CreateCategory, ListCategories
from app.application.ledger.budgets import (
    ListMonthlyBudgets,
    RemoveMonthlyBudget,
    SetMonthlyBudget,
    UpdateMonthlyBudget,
)
from app.application.ledger.errors import (
    BudgetAlreadyExistsError,
    BudgetNotFoundError,
    CategoryAlreadyExistsError,
    CategoryKindMismatchError,
    CategoryNotFoundError,
    SubscriptionNotFoundError,
)
from app.application.ledger.subscriptions import (
    CreateSubscription,
    ListSubscriptions,
    ProcessDueSubscriptions,
    RemoveSubscription,
    UpdateSubscriptionPrice,
)
from app.application.ledger.transactions import (
    CreateTransaction,
    GetAccountBalance,
    ListTransactions,
)
from app.domain.identity.user import User
from app.domain.ledger.models import TransactionKind
from app.core.config import get_settings
from app.infrastructure.database.repositories.ledger import (
    SqlAlchemyCategoryRepository,
    SqlAlchemyBudgetRepository,
    SqlAlchemySubscriptionRepository,
    SqlAlchemyTransactionRepository,
)
from app.infrastructure.database.session import get_database_session
from app.infrastructure.notifications.runtime import notify_budget_limit
from app.presentation.dependencies.auth import require_permission
from app.presentation.schemas.ledger import (
    AccountBalanceResponse,
    CategoryResponse,
    CreateCategoryRequest,
    CreateTransactionRequest,
    CreateSubscriptionRequest,
    MonthlyBudgetResponse,
    SetMonthlyBudgetRequest,
    SuccessResponse,
    SubscriptionResponse,
    TransactionResponse,
    UpdateSubscriptionPriceRequest,
    UpdateMonthlyBudgetRequest,
)

router = APIRouter(tags=["ledger"])


@router.get("/balance", response_model=AccountBalanceResponse)
def get_account_balance(
    session: Annotated[Session, Depends(get_database_session)],
    user: Annotated[User, Depends(require_permission("finance.read.self"))],
) -> AccountBalanceResponse:
    timezone = ZoneInfo(get_settings().app_timezone)
    tomorrow = datetime.now(timezone).date() + timedelta(days=1)
    balance = GetAccountBalance(SqlAlchemyTransactionRepository(session)).execute(
        user.id,
        datetime.combine(tomorrow, time.min, tzinfo=timezone),
    )
    return AccountBalanceResponse.from_domain(balance)


@router.get("/budgets", response_model=list[MonthlyBudgetResponse])
def list_monthly_budgets(
    session: Annotated[Session, Depends(get_database_session)],
    user: Annotated[User, Depends(require_permission("finance.read.self"))],
) -> list[MonthlyBudgetResponse]:
    budgets = ListMonthlyBudgets(SqlAlchemyBudgetRepository(session)).execute(user.id)
    return [MonthlyBudgetResponse.from_domain(budget) for budget in budgets]


@router.put(
    "/budgets/{category_id}",
    response_model=MonthlyBudgetResponse,
)
def set_monthly_budget(
    category_id: UUID,
    payload: SetMonthlyBudgetRequest,
    background_tasks: BackgroundTasks,
    session: Annotated[Session, Depends(get_database_session)],
    user: Annotated[User, Depends(require_permission("finance.write.self"))],
) -> MonthlyBudgetResponse:
    try:
        budget = SetMonthlyBudget(
            categories=SqlAlchemyCategoryRepository(session),
            budgets=SqlAlchemyBudgetRepository(session),
        ).execute(
            user_id=user.id,
            category_id=category_id,
            limit_minor=payload.limit_as_minor(),
        )
    except CategoryNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Kategori bulunamadı.",
        ) from None
    except CategoryKindMismatchError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Yalnızca gider kategorilerine bütçe limiti eklenebilir.",
        ) from None
    background_tasks.add_task(notify_budget_limit, user.id, budget.category_id)
    return MonthlyBudgetResponse.from_domain(budget)


@router.patch(
    "/budgets/{budget_id}",
    response_model=MonthlyBudgetResponse,
)
def update_monthly_budget(
    budget_id: UUID,
    payload: UpdateMonthlyBudgetRequest,
    background_tasks: BackgroundTasks,
    session: Annotated[Session, Depends(get_database_session)],
    user: Annotated[User, Depends(require_permission("finance.write.self"))],
) -> MonthlyBudgetResponse:
    try:
        budget = UpdateMonthlyBudget(
            categories=SqlAlchemyCategoryRepository(session),
            budgets=SqlAlchemyBudgetRepository(session),
        ).execute(
            user_id=user.id,
            budget_id=budget_id,
            category_id=payload.category_id,
            limit_minor=payload.limit_as_minor(),
        )
    except (CategoryNotFoundError, BudgetNotFoundError):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Bütçe limiti veya kategori bulunamadı.",
        ) from None
    except CategoryKindMismatchError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Yalnızca gider kategorilerine bütçe limiti eklenebilir.",
        ) from None
    except BudgetAlreadyExistsError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Bu kategorinin zaten bir bütçe limiti var.",
        ) from None
    background_tasks.add_task(notify_budget_limit, user.id, budget.category_id)
    return MonthlyBudgetResponse.from_domain(budget)


@router.delete("/budgets/{category_id}", response_model=SuccessResponse)
def remove_monthly_budget(
    category_id: UUID,
    session: Annotated[Session, Depends(get_database_session)],
    user: Annotated[User, Depends(require_permission("finance.write.self"))],
) -> SuccessResponse:
    try:
        RemoveMonthlyBudget(SqlAlchemyBudgetRepository(session)).execute(
            user.id,
            category_id,
        )
    except BudgetNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Bütçe limiti bulunamadı.",
        ) from None
    return SuccessResponse()


@router.get("/categories", response_model=list[CategoryResponse])
def list_categories(
    session: Annotated[Session, Depends(get_database_session)],
    user: Annotated[User, Depends(require_permission("finance.read.self"))],
    kind: Annotated[TransactionKind | None, Query()] = None,
) -> list[CategoryResponse]:
    categories = ListCategories(SqlAlchemyCategoryRepository(session)).execute(
        user.id,
        kind,
    )
    return [CategoryResponse.from_domain(category) for category in categories]


@router.post(
    "/categories",
    response_model=CategoryResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_category(
    payload: CreateCategoryRequest,
    session: Annotated[Session, Depends(get_database_session)],
    user: Annotated[User, Depends(require_permission("finance.write.self"))],
) -> CategoryResponse:
    try:
        category = CreateCategory(SqlAlchemyCategoryRepository(session)).execute(
            user_id=user.id,
            name=payload.name,
            kind=payload.kind,
            color=payload.color.lower(),
        )
    except CategoryAlreadyExistsError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Bu kategori zaten mevcut.",
        ) from None
    return CategoryResponse.from_domain(category)


@router.get("/transactions", response_model=list[TransactionResponse])
def list_transactions(
    start: Annotated[datetime, Query()],
    end: Annotated[datetime, Query()],
    session: Annotated[Session, Depends(get_database_session)],
    user: Annotated[User, Depends(require_permission("finance.read.self"))],
) -> list[TransactionResponse]:
    if start.tzinfo is None or end.tzinfo is None or start >= end:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Geçerli, saat dilimli bir tarih aralığı girin.",
        )
    transactions = ListTransactions(SqlAlchemyTransactionRepository(session)).execute(
        user.id,
        start,
        end,
    )
    return [
        TransactionResponse.from_domain(transaction) for transaction in transactions
    ]


@router.post(
    "/transactions",
    response_model=TransactionResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_transaction(
    payload: CreateTransactionRequest,
    background_tasks: BackgroundTasks,
    session: Annotated[Session, Depends(get_database_session)],
    user: Annotated[User, Depends(require_permission("finance.write.self"))],
) -> TransactionResponse:
    categories = SqlAlchemyCategoryRepository(session)
    transactions = SqlAlchemyTransactionRepository(session)
    try:
        transaction = CreateTransaction(categories, transactions).execute(
            user_id=user.id,
            category_id=payload.category_id,
            kind=payload.kind,
            amount_minor=payload.amount_as_minor(),
            description=payload.description,
            occurred_at=datetime.combine(
                payload.occurred_on,
                time(hour=12),
                tzinfo=ZoneInfo(get_settings().app_timezone),
            ),
        )
    except CategoryNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Kategori bulunamadı.",
        ) from None
    except CategoryKindMismatchError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Kategori ile hareket türü uyuşmuyor.",
        ) from None
    if transaction.kind == TransactionKind.EXPENSE:
        background_tasks.add_task(
            notify_budget_limit,
            user.id,
            transaction.category_id,
        )
    return TransactionResponse.from_domain(transaction)


@router.get("/subscriptions", response_model=list[SubscriptionResponse])
def list_subscriptions(
    session: Annotated[Session, Depends(get_database_session)],
    user: Annotated[User, Depends(require_permission("finance.read.self"))],
) -> list[SubscriptionResponse]:
    subscriptions = ListSubscriptions(
        SqlAlchemySubscriptionRepository(session)
    ).execute(user.id)
    return [
        SubscriptionResponse.from_domain(subscription)
        for subscription in subscriptions
    ]


@router.post(
    "/subscriptions",
    response_model=SubscriptionResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_subscription(
    payload: CreateSubscriptionRequest,
    background_tasks: BackgroundTasks,
    session: Annotated[Session, Depends(get_database_session)],
    user: Annotated[User, Depends(require_permission("finance.write.self"))],
) -> SubscriptionResponse:
    try:
        subscription = CreateSubscription(
            categories=SqlAlchemyCategoryRepository(session),
            subscriptions=SqlAlchemySubscriptionRepository(session),
        ).execute(
            user_id=user.id,
            category_id=payload.category_id,
            name=payload.name,
            amount_minor=payload.amount_as_minor(),
            first_charge_date=payload.first_charge_date,
        )
    except CategoryNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Kategori bulunamadı.",
        ) from None
    except CategoryKindMismatchError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Abonelik yalnızca gider kategorisine bağlanabilir.",
        ) from None
    background_tasks.add_task(
        notify_budget_limit,
        user.id,
        subscription.category_id,
    )
    return SubscriptionResponse.from_domain(subscription)


@router.delete("/subscriptions/{subscription_id}", response_model=SuccessResponse)
def remove_subscription(
    subscription_id: UUID,
    session: Annotated[Session, Depends(get_database_session)],
    user: Annotated[User, Depends(require_permission("finance.write.self"))],
) -> SuccessResponse:
    try:
        RemoveSubscription(SqlAlchemySubscriptionRepository(session)).execute(
            user.id,
            subscription_id,
        )
    except SubscriptionNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Abonelik bulunamadı.",
        ) from None
    return SuccessResponse()


@router.patch(
    "/subscriptions/{subscription_id}/price",
    response_model=SubscriptionResponse,
)
def update_subscription_price(
    subscription_id: UUID,
    payload: UpdateSubscriptionPriceRequest,
    background_tasks: BackgroundTasks,
    session: Annotated[Session, Depends(get_database_session)],
    user: Annotated[User, Depends(require_permission("finance.write.self"))],
) -> SubscriptionResponse:
    try:
        subscription = UpdateSubscriptionPrice(
            SqlAlchemySubscriptionRepository(session)
        ).execute(
            user_id=user.id,
            subscription_id=subscription_id,
            amount_minor=payload.amount_as_minor(),
        )
    except SubscriptionNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Abonelik bulunamadı.",
        ) from None
    background_tasks.add_task(
        notify_budget_limit,
        user.id,
        subscription.category_id,
    )
    return SubscriptionResponse.from_domain(subscription)


@router.post(
    "/subscriptions/process-due",
    response_model=list[TransactionResponse],
)
def process_due_subscriptions(
    background_tasks: BackgroundTasks,
    session: Annotated[Session, Depends(get_database_session)],
    user: Annotated[User, Depends(require_permission("finance.write.self"))],
) -> list[TransactionResponse]:
    today = datetime.now(ZoneInfo(get_settings().app_timezone)).date()
    transactions = ProcessDueSubscriptions(
        subscriptions=SqlAlchemySubscriptionRepository(session),
        transactions=SqlAlchemyTransactionRepository(session),
    ).execute(user.id, today)
    for category_id in {transaction.category_id for transaction in transactions}:
        background_tasks.add_task(notify_budget_limit, user.id, category_id)
    return [
        TransactionResponse.from_domain(transaction) for transaction in transactions
    ]
