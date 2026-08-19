from datetime import datetime, time, timedelta
from typing import Annotated
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.application.admin.services import ListAdminUserSummaries
from app.core.config import get_settings
from app.domain.identity.user import User
from app.infrastructure.database.repositories.admin import (
    SqlAlchemyAdminFinanceReader,
)
from app.infrastructure.database.repositories.users import SqlAlchemyUserRepository
from app.infrastructure.database.session import get_database_session
from app.presentation.dependencies.auth import require_permissions
from app.presentation.schemas.admin import AdminUserSummaryResponse

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
