from datetime import datetime
from typing import Annotated
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.application.savings.services import ProcessMonthlySavings
from app.core.config import get_settings
from app.domain.identity.user import User
from app.infrastructure.database.repositories.savings import (
    SqlAlchemyMonthlyCashFlowReader,
    SqlAlchemySavingsRepository,
)
from app.infrastructure.database.session import get_database_session
from app.presentation.dependencies.auth import require_permission
from app.presentation.schemas.savings import SavingsOverviewResponse

router = APIRouter(tags=["savings"])


@router.post(
    "/savings/process-month-end",
    response_model=SavingsOverviewResponse,
)
def process_monthly_savings(
    session: Annotated[Session, Depends(get_database_session)],
    user: Annotated[User, Depends(require_permission("finance.write.self"))],
) -> SavingsOverviewResponse:
    timezone = ZoneInfo(get_settings().app_timezone)
    overview = ProcessMonthlySavings(
        cash_flow=SqlAlchemyMonthlyCashFlowReader(session),
        savings=SqlAlchemySavingsRepository(session),
    ).execute(
        user_id=user.id,
        account_created_at=user.created_at,
        today=datetime.now(timezone).date(),
        timezone=timezone,
    )
    return SavingsOverviewResponse.from_domain(overview)
