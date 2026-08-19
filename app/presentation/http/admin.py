from datetime import datetime, time, timedelta
from typing import Annotated
from uuid import UUID
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.application.admin.errors import (
    AdminUserNotFoundError,
    CannotDeactivateSelfError,
    CannotRemoveOwnAdminRoleError,
)
from app.application.admin.services import (
    ChangeAdminUserRole,
    ChangeAdminUserStatus,
    GetAdminUserFinanceDetails,
    ListAdminUserSummaries,
)
from app.core.config import get_settings
from app.domain.identity.user import User
from app.infrastructure.database.repositories.admin import (
    SqlAlchemyAdminFinanceReader,
    SqlAlchemyAdminUserManager,
)
from app.infrastructure.database.repositories.users import SqlAlchemyUserRepository
from app.infrastructure.database.session import get_database_session
from app.presentation.dependencies.auth import require_permissions
from app.presentation.schemas.admin import (
    AdminUserAccessResponse,
    AdminUserFinanceDetailsResponse,
    AdminUserSummaryResponse,
    ChangeAdminUserRoleRequest,
    ChangeAdminUserStatusRequest,
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


@router.patch(
    "/users/{user_id}/status",
    response_model=AdminUserAccessResponse,
)
def change_user_status(
    user_id: UUID,
    payload: ChangeAdminUserStatusRequest,
    session: Annotated[Session, Depends(get_database_session)],
    actor: Annotated[User, Depends(require_permissions("users.manage"))],
) -> AdminUserAccessResponse:
    try:
        user = ChangeAdminUserStatus(SqlAlchemyAdminUserManager(session)).execute(
            actor_id=actor.id,
            target_user_id=user_id,
            is_active=payload.is_active,
        )
    except AdminUserNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Kullanıcı bulunamadı.",
        ) from None
    except CannotDeactivateSelfError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Kendi hesabını pasife alamazsın.",
        ) from None
    return AdminUserAccessResponse.from_user(user)


@router.patch(
    "/users/{user_id}/role",
    response_model=AdminUserAccessResponse,
)
def change_user_role(
    user_id: UUID,
    payload: ChangeAdminUserRoleRequest,
    session: Annotated[Session, Depends(get_database_session)],
    actor: Annotated[User, Depends(require_permissions("users.manage"))],
) -> AdminUserAccessResponse:
    try:
        user = ChangeAdminUserRole(SqlAlchemyAdminUserManager(session)).execute(
            actor_id=actor.id,
            target_user_id=user_id,
            is_admin=payload.is_admin,
        )
    except AdminUserNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Kullanıcı bulunamadı.",
        ) from None
    except CannotRemoveOwnAdminRoleError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Kendi admin yetkini kaldıramazsın.",
        ) from None
    return AdminUserAccessResponse.from_user(user)
