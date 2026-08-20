import asyncio
import logging
from collections.abc import Iterator
from contextlib import suppress
from datetime import date, datetime, time, timedelta
from uuid import UUID
from zoneinfo import ZoneInfo

from app.application.notifications.services import (
    SendBudgetExceededNotification,
    SendDailyExpenseSummary,
)
from app.core.config import get_settings
from app.domain.identity.user import User
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


def _summary_dates_owed(
    user: User,
    now: datetime,
    catchup_days: int,
) -> Iterator[date]:
    """The days that still owe this user a summary, oldest first.

    Only today was ever considered before, so a night with the service stopped
    meant that day's summary was lost for good; unlike due subscriptions, which
    have always caught up on every month they missed. The look-back is short on
    purpose: coming back from a long outage should not fire off a fortnight of
    mail at once. Days before the account existed are never owed, and whether a
    day was already sent is settled by the delivery record.
    """
    created_on = user.created_at.astimezone(now.tzinfo).date()
    for offset in range(catchup_days, -1, -1):
        summary_date = now.date() - timedelta(days=offset)
        if summary_date < created_on:
            continue
        if offset == 0:
            # Today is the only day whose chosen hour may still be ahead of us.
            scheduled_at = datetime.combine(
                summary_date,
                user.daily_summary_time,
                tzinfo=now.tzinfo,
            )
            if now < scheduled_at:
                continue
        yield summary_date


def send_daily_summaries() -> None:
    settings = get_settings()
    if not settings.mail_enabled:
        return
    timezone = ZoneInfo(settings.app_timezone)
    now = datetime.now(timezone)

    try:
        with session_factory() as session:
            users = SqlAlchemyUserRepository(session).list_active()
            for user in users:
                if (
                    is_placeholder_address(user.email)
                    or not user.daily_summary_enabled
                ):
                    continue
                for summary_date in _summary_dates_owed(
                    user,
                    now,
                    settings.daily_summary_catchup_days,
                ):
                    day_start = datetime.combine(
                        summary_date,
                        time.min,
                        tzinfo=timezone,
                    )
                    try:
                        SendDailyExpenseSummary(
                            transactions=SqlAlchemyTransactionRepository(session),
                            deliveries=SqlAlchemyNotificationDeliveryRepository(
                                session
                            ),
                            mailer=SmtpMailSender(settings),
                        ).execute(
                            user=user,
                            summary_date=summary_date,
                            period_start=day_start,
                            period_end=day_start + timedelta(days=1),
                            delivered_at=now,
                        )
                    except Exception:
                        session.rollback()
                        logger.exception(
                            "Daily summary for %s could not be sent for user %s",
                            summary_date,
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
