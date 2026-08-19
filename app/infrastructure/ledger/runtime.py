import asyncio
import logging
from datetime import datetime
from zoneinfo import ZoneInfo

from app.application.ledger.subscriptions import ProcessDueSubscriptions
from app.core.config import get_settings
from app.domain.ledger.models import TransactionKind
from app.infrastructure.database.repositories.ledger import (
    SqlAlchemySubscriptionRepository,
    SqlAlchemyTransactionRepository,
)
from app.infrastructure.database.repositories.users import SqlAlchemyUserRepository
from app.infrastructure.database.session import session_factory
from app.infrastructure.notifications.runtime import notify_budget_limit

logger = logging.getLogger(__name__)

SUBSCRIPTION_INTERVAL_SECONDS = 3600


def process_due_subscriptions() -> None:
    """Post every recurring charge that has come due, for every active user."""
    settings = get_settings()
    today = datetime.now(ZoneInfo(settings.app_timezone)).date()

    try:
        with session_factory() as session:
            for user in SqlAlchemyUserRepository(session).list_active():
                try:
                    transactions = ProcessDueSubscriptions(
                        subscriptions=SqlAlchemySubscriptionRepository(session),
                        transactions=SqlAlchemyTransactionRepository(session),
                    ).execute(user.id, today)
                except Exception:
                    session.rollback()
                    logger.exception(
                        "Due subscriptions could not be processed for user %s",
                        user.id,
                    )
                    continue

                if not transactions:
                    continue
                logger.info(
                    "Posted %d recurring charges for user %s",
                    len(transactions),
                    user.id,
                )
                for category_id in {
                    transaction.category_id
                    for transaction in transactions
                    if transaction.kind == TransactionKind.EXPENSE
                }:
                    notify_budget_limit(user.id, category_id)
    except Exception:
        logger.exception("Due subscription job failed")


async def subscription_scheduler() -> None:
    while True:
        await asyncio.to_thread(process_due_subscriptions)
        await asyncio.sleep(SUBSCRIPTION_INTERVAL_SECONDS)
