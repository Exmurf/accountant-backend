from datetime import datetime, time, timedelta
from typing import Annotated
from uuid import UUID
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.application.admin.errors import AdminUserNotFoundError
from app.application.admin.services import (
    GetAdminUserFinanceDetails,
    ListAdminUserSummaries,
)
from app.core.config import get_settings
from app.domain.identity.user import User
from app.infrastructure.database.repositories.admin import (
    SqlAlchemyAdminFinanceReader,
)
from app.infrastructure.database.repositories.users import SqlAlchemyUserRepository
from app.infrastructure.database.session import get_database_session
from app.presentation.dependencies.auth import require_permissions
from app.presentation.schemas.admin import (
    AdminUserFinanceDetailsResponse,
    AdminUserSummaryResponse,
)

router = APIRouter(prefix="/admin", tags=["administration"])


@router.get("/users", response_model=list[AdminUserSummaryResponse])
def list_users(
    session: Annotated[Session, Depends(get_database_session)],
    _: Annotated[
        User,
        Depends(require_permissions("users.read", "finance.read.any")),
    ],
) -> list[AdminUserSummaryResponse]:
    timezone = ZoneInfo(get_settings().app_timezone)
    tomorrow = datetime.now(timezone).date() + timedelta(days=1)
    users = ListAdminUserSummaries(
        users=SqlAlchemyUserRepository(session),
        finances=SqlAlchemyAdminFinanceReader(session),
    ).execute(datetime.combine(tomorrow, time.min, tzinfo=timezone))
    return [AdminUserSummaryResponse.from_domain(user) for user in users]


@router.get(
    "/users/{user_id}/finance",
    response_model=AdminUserFinanceDetailsResponse,
)
def get_user_finance_details(
    user_id: UUID,
    session: Annotated[Session, Depends(get_database_session)],
    _: Annotated[
        User,
        Depends(require_permissions("users.read", "finance.read.any")),
    ],
) -> AdminUserFinanceDetailsResponse:
    timezone = ZoneInfo(get_settings().app_timezone)
    tomorrow = datetime.now(timezone).date() + timedelta(days=1)
    try:
        details = GetAdminUserFinanceDetails(
            users=SqlAlchemyUserRepository(session),
            finances=SqlAlchemyAdminFinanceReader(session),
        ).execute(
            user_id,
            datetime.combine(tomorrow, time.min, tzinfo=timezone),
        )
    except AdminUserNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Kullanıcı bulunamadı.",
        ) from None
    return AdminUserFinanceDetailsResponse.from_domain(details)
