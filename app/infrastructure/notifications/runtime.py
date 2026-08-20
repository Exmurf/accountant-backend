import asyncio
import logging
from contextlib import suppress
from datetime import datetime, time, timedelta
from uuid import UUID
from zoneinfo import ZoneInfo

from app.application.notifications.services import (
    SendBudgetExceededNotification,
    SendDailyExpenseSummary,
)
from app.core.config import get_settings
from app.infrastructure.database.repositories.ledger import (
    SqlAlchemyBudgetRepository,
    SqlAlchemySubscriptionRepository,
    SqlAlchemyTransactionRepository,
)
from app.infrastructure.database.repositories.notifications import (
    SqlAlchemyNotificationDeliveryRepository,
)
from app.infrastructure.database.repositories.users import SqlAlchemyUserRepository
from app.infrastructure.database.session import session_factory
from app.infrastructure.mail.addresses import is_placeholder_address
from app.infrastructure.mail.smtp import SmtpMailSender

logger = logging.getLogger(__name__)


def _month_range(moment: datetime) -> tuple[datetime, datetime]:
    start = moment.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    if start.month == 12:
        end = start.replace(year=start.year + 1, month=1)
    else:
        end = start.replace(month=start.month + 1)
    return start, end


def notify_budget_limit(user_id: UUID, category_id: UUID) -> None:
    settings = get_settings()
    if not settings.mail_enabled:
        return
    now = datetime.now(ZoneInfo(settings.app_timezone))
    period_start, period_end = _month_range(now)
    try:
        with session_factory() as session:
            user = SqlAlchemyUserRepository(session).get_by_id(user_id)
            if (
                user is None
                or not user.is_active
                or is_placeholder_address(user.email)
                or not user.budget_alerts_enabled
            ):
                return
            SendBudgetExceededNotification(
                budgets=SqlAlchemyBudgetRepository(session),
                subscriptions=SqlAlchemySubscriptionRepository(session),
                transactions=SqlAlchemyTransactionRepository(session),
                deliveries=SqlAlchemyNotificationDeliveryRepository(session),
                mailer=SmtpMailSender(settings),
            ).execute(
                user=user,
                category_id=category_id,
                period_start=period_start,
                period_end=period_end,
                delivered_at=now,
            )
    except Exception:
        logger.exception("Budget notification could not be sent")


def send_daily_summaries() -> None:
    settings = get_settings()
    if not settings.mail_enabled:
        return
    timezone = ZoneInfo(settings.app_timezone)
    now = datetime.now(timezone)
    day_start = datetime.combine(now.date(), time.min, tzinfo=timezone)
    day_end = day_start + timedelta(days=1)

    try:
        with session_factory() as session:
            users = SqlAlchemyUserRepository(session).list_active()
            for user in users:
                if (
                    is_placeholder_address(user.email)
                    or not user.daily_summary_enabled
                ):
                    continue
                scheduled_at = datetime.combine(
                    now.date(),
                    user.daily_summary_time,
                    tzinfo=timezone,
                )
                if now < scheduled_at:
                    continue
                try:
                    SendDailyExpenseSummary(
                        transactions=SqlAlchemyTransactionRepository(session),
                        deliveries=SqlAlchemyNotificationDeliveryRepository(session),
                        mailer=SmtpMailSender(settings),
                    ).execute(
                        user=user,
                        summary_date=now.date(),
                        period_start=day_start,
                        period_end=day_end,
                        delivered_at=now,
                    )
                except Exception:
                    session.rollback()
                    logger.exception(
                        "Daily summary could not be sent for user %s",
                        user.id,
                    )
    except Exception:
        logger.exception("Daily summary job failed")


async def notification_scheduler() -> None:
    while True:
        await asyncio.to_thread(send_daily_summaries)
        await asyncio.sleep(60)


async def stop_scheduler(task: asyncio.Task[None]) -> None:
    task.cancel()
    with suppress(asyncio.CancelledError):
        await task
