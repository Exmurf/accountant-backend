from datetime import date, datetime
from uuid import UUID

from app.application.ledger.ports import (
    BudgetRepository,
    SubscriptionRepository,
    TransactionRepository,
)
from app.application.notifications.ports import (
    MailSender,
    NotificationDeliveryRepository,
)
from app.domain.identity.user import User
from app.domain.ledger.models import TransactionKind


class SendBudgetExceededNotification:
    def __init__(
        self,
        budgets: BudgetRepository,
        subscriptions: SubscriptionRepository,
        transactions: TransactionRepository,
        deliveries: NotificationDeliveryRepository,
        mailer: MailSender,
    ) -> None:
        self._budgets = budgets
        self._subscriptions = subscriptions
        self._transactions = transactions
        self._deliveries = deliveries
        self._mailer = mailer

    def execute(
        self,
        user: User,
        category_id: UUID,
        period_start: datetime,
        period_end: datetime,
        delivered_at: datetime,
    ) -> bool:
        budget = next(
            (
                item
                for item in self._budgets.list_for_user(user.id)
                if item.category_id == category_id
            ),
            None,
        )
        if budget is None:
            return False

        transactions = self._transactions.list_for_user(
            user.id,
            period_start,
            period_end,
        )
        category_expenses = [
            item
            for item in transactions
            if item.kind == TransactionKind.EXPENSE
            and item.category_id == category_id
        ]
        actual_minor = sum(item.amount_minor for item in category_expenses)
        charged_subscription_ids = {
            item.subscription_id
            for item in category_expenses
            if item.subscription_id is not None
        }
        planned_minor = sum(
            item.amount_minor
            for item in self._subscriptions.list_active(user.id)
            if item.category_id == category_id
            and item.id not in charged_subscription_ids
        )
        used_minor = actual_minor + planned_minor
        if used_minor <= budget.limit_minor:
            return False

        # The limit is part of the key, so raising it opens a fresh warning
        # for the new ceiling: somebody who deliberately moved the line still
        # expects to hear about crossing it. Leaving the limit alone keeps the
        # old key, which is what stops a warning every time money is spent.
        reference_key = f"{category_id}:{period_start:%Y-%m}:{budget.limit_minor}"
        kind = "BUDGET_EXCEEDED"
        if self._deliveries.was_delivered(user.id, kind, reference_key):
            return False

        exceeded_minor = used_minor - budget.limit_minor
        self._mailer.send(
            recipient=user.email,
            subject=f"{budget.category_name} aylık limitini aştın",
            text_body=(
                f"Merhaba {user.display_name},\n\n"
                f"{budget.category_name} kategorisinde bu ay "
                f"{used_minor / 100:,.2f} TL kullandın. "
                f"Aylık limitin {budget.limit_minor / 100:,.2f} TL ve "
                f"limiti {exceeded_minor / 100:,.2f} TL aştın.\n\n"
                "Accountant"
            ),
        )
        self._deliveries.mark_delivered(
            user.id,
            kind,
            reference_key,
            delivered_at,
        )
        return True


class SendDailyExpenseSummary:
    def __init__(
        self,
        transactions: TransactionRepository,
        deliveries: NotificationDeliveryRepository,
        mailer: MailSender,
    ) -> None:
        self._transactions = transactions
        self._deliveries = deliveries
        self._mailer = mailer

    def execute(
        self,
        user: User,
        summary_date: date,
        period_start: datetime,
        period_end: datetime,
        delivered_at: datetime,
    ) -> bool:
        reference_key = summary_date.isoformat()
        kind = "DAILY_EXPENSE_SUMMARY"
        if self._deliveries.was_delivered(user.id, kind, reference_key):
            return False

        # A catch-up summary is for a day that has already passed, so it says
        # which one rather than calling it today.
        is_today = delivered_at.date() == summary_date
        day_label = "Bugün" if is_today else f"{summary_date:%d.%m.%Y} günü"
        total_label = (
            "Bugünkü" if is_today else f"{summary_date:%d.%m.%Y} tarihli"
        )

        expenses = [
            item
            for item in self._transactions.list_for_user(
                user.id,
                period_start,
                period_end,
            )
            if item.kind == TransactionKind.EXPENSE
        ]
        total_minor = sum(item.amount_minor for item in expenses)
        category_totals: dict[str, int] = {}
        for item in expenses:
            category_totals[item.category_name] = (
                category_totals.get(item.category_name, 0) + item.amount_minor
            )
        breakdown = "\n".join(
            f"- {name}: {amount / 100:,.2f} TL"
            for name, amount in sorted(
                category_totals.items(),
                key=lambda pair: pair[1],
                reverse=True,
            )
        )
        if not breakdown:
            breakdown = "- Gider kaydı bulunmuyor."

        self._mailer.send(
            recipient=user.email,
            subject=f"{day_label} {total_minor / 100:,.2f} TL harcadın",
            text_body=(
                f"Merhaba {user.display_name},\n\n"
                f"{total_label} toplam harcaman: {total_minor / 100:,.2f} TL\n\n"
                f"Kategori özeti:\n{breakdown}\n\n"
                "Accountant"
            ),
        )
        self._deliveries.mark_delivered(
            user.id,
            kind,
            reference_key,
            delivered_at,
        )
        return True
