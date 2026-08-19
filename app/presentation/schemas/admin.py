from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

from app.domain.admin.models import AdminUserFinanceDetails, AdminUserSummary
from app.domain.identity.user import User
from app.presentation.schemas.ledger import SubscriptionResponse, TransactionResponse


class AdminUserSummaryResponse(BaseModel):
    id: UUID
    email: str
    display_name: str
    is_active: bool
    roles: list[str]
    created_at: datetime
    current_balance_minor: int
    total_income_minor: int
    total_expense_minor: int
    transaction_count: int

    @classmethod
    def from_domain(cls, user: AdminUserSummary) -> "AdminUserSummaryResponse":
        return cls(
            id=user.id,
            email=user.email,
            display_name=user.display_name,
            is_active=user.is_active,
            roles=list(user.roles),
            created_at=user.created_at,
            current_balance_minor=user.finances.current_balance_minor,
            total_income_minor=user.finances.total_income_minor,
            total_expense_minor=user.finances.total_expense_minor,
            transaction_count=user.finances.transaction_count,
        )


class AdminCategorySpendingResponse(BaseModel):
    category_id: UUID
    category_name: str
    category_color: str
    total_expense_minor: int


class AdminUserFinanceDetailsResponse(BaseModel):
    user_id: UUID
    recent_transactions: list[TransactionResponse]
    category_spending: list[AdminCategorySpendingResponse]
    subscriptions: list[SubscriptionResponse]

    @classmethod
    def from_domain(
        cls,
        details: AdminUserFinanceDetails,
    ) -> "AdminUserFinanceDetailsResponse":
        return cls(
            user_id=details.user_id,
            recent_transactions=[
                TransactionResponse.from_domain(transaction)
                for transaction in details.recent_transactions
            ],
            category_spending=[
                AdminCategorySpendingResponse(
                    category_id=category.category_id,
                    category_name=category.category_name,
                    category_color=category.category_color,
                    total_expense_minor=category.total_expense_minor,
                )
                for category in details.category_spending
            ],
            subscriptions=[
                SubscriptionResponse.from_domain(subscription)
                for subscription in details.subscriptions
            ],
        )


class ChangeAdminUserStatusRequest(BaseModel):
    is_active: bool


class AdminUserAccessResponse(BaseModel):
    id: UUID
    is_active: bool
    roles: list[str]

    @classmethod
    def from_user(cls, user: User) -> "AdminUserAccessResponse":
        return cls(
            id=user.id,
            is_active=user.is_active,
            roles=sorted(user.roles),
        )
