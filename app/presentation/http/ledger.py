from datetime import datetime
from typing import Annotated
from uuid import UUID
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.application.ledger.categories import CreateCategory, ListCategories
from app.application.ledger.errors import (
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
)
from app.application.ledger.transactions import CreateTransaction, ListTransactions
from app.domain.identity.user import User
from app.domain.ledger.models import TransactionKind
from app.core.config import get_settings
from app.infrastructure.database.repositories.ledger import (
    SqlAlchemyCategoryRepository,
    SqlAlchemySubscriptionRepository,
    SqlAlchemyTransactionRepository,
)
from app.infrastructure.database.session import get_database_session
from app.presentation.dependencies.auth import require_permission
from app.presentation.schemas.ledger import (
    CategoryResponse,
    CreateCategoryRequest,
    CreateTransactionRequest,
    CreateSubscriptionRequest,
    SuccessResponse,
    SubscriptionResponse,
    TransactionResponse,
)

router = APIRouter(tags=["ledger"])


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
            occurred_at=payload.occurred_at,
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


@router.post(
    "/subscriptions/process-due",
    response_model=list[TransactionResponse],
)
def process_due_subscriptions(
    session: Annotated[Session, Depends(get_database_session)],
    user: Annotated[User, Depends(require_permission("finance.write.self"))],
) -> list[TransactionResponse]:
    today = datetime.now(ZoneInfo(get_settings().app_timezone)).date()
    transactions = ProcessDueSubscriptions(
        subscriptions=SqlAlchemySubscriptionRepository(session),
        transactions=SqlAlchemyTransactionRepository(session),
    ).execute(user.id, today)
    return [
        TransactionResponse.from_domain(transaction) for transaction in transactions
    ]
