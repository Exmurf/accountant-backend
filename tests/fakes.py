"""In-memory stand-ins for the ports the application depends on.

Each one implements the same `Protocol` the SQLAlchemy adapter does, which is
why a use case cannot tell the difference. They exist for two reasons, and
speed is only the smaller one: the bigger is reach. A refused mail server, a
token that has already expired, a row that vanishes between two calls — these
are one line here and close to unreachable against the real thing.

They are deliberately simple. A fake with its own rules is a second
implementation to get wrong, and a test that passes against it proves nothing.
"""

from dataclasses import dataclass, replace
from datetime import date, datetime, time
from uuid import UUID, uuid4

from app.application.identity.errors import EmailAlreadyRegisteredError
from app.application.notifications.message import MailMessage
from app.domain.admin.models import AdminCategorySpending, UserFinanceTotals
from app.domain.identity.email_change import PendingEmailChange
from app.domain.identity.session import AccessTokenClaims
from app.domain.identity.user import User
from app.domain.ledger.budget import MonthlyBudget
from app.domain.ledger.models import (
    AccountBalance,
    Category,
    Transaction,
    TransactionKind,
)
from app.domain.ledger.subscription import Subscription
from app.domain.savings.models import MonthlySaving
from tests.factories import CREATED_AT, USER_PERMISSIONS, make_user


@dataclass(frozen=True, slots=True)
class SentMail:
    recipient: str
    subject: str
    message: MailMessage


class FakeMailSender:
    """Keeps what it was asked to send so a test can read it back."""

    def __init__(self, fails: bool = False) -> None:
        self.sent: list[SentMail] = []
        self._fails = fails

    def send(self, recipient: str, subject: str, message: MailMessage) -> None:
        if self._fails:
            raise ConnectionRefusedError("mail server refused the connection")
        self.sent.append(
            SentMail(recipient=recipient, subject=subject, message=message)
        )

    @property
    def last(self) -> SentMail:
        return self.sent[-1]


class FakePasswordHasher:
    """A hash you can read.

    Argon2 is slow by design — that is the whole point of it — and a suite that
    hashed for real would spend most of its time proving a library works.
    """

    def hash(self, password: str) -> str:
        return f"hashed:{password}"

    def verify(self, password: str, password_hash: str) -> bool:
        return password_hash == f"hashed:{password}"


class FakeAccessTokenService:
    def create(self, user_id: UUID) -> str:
        return f"access:{user_id}"

    def decode(self, token: str) -> AccessTokenClaims:
        return AccessTokenClaims(
            user_id=UUID(token.removeprefix("access:")),
            issued_at=CREATED_AT,
        )


class FakeRefreshTokenService:
    """Hands out a new token every call, so rotation is visible in a test."""

    def __init__(self) -> None:
        self._issued = 0

    def create(self) -> str:
        self._issued += 1
        return f"refresh-{self._issued}"

    def hash(self, token: str) -> str:
        return f"sha:{token}"


@dataclass
class _StoredRefreshToken:
    user_id: UUID
    expires_at: datetime
    revoked_at: datetime | None = None


class FakeRefreshTokenRepository:
    def __init__(self) -> None:
        self.tokens: dict[str, _StoredRefreshToken] = {}

    def add(self, user_id: UUID, token_hash: str, expires_at: datetime) -> None:
        self.tokens[token_hash] = _StoredRefreshToken(
            user_id=user_id,
            expires_at=expires_at,
        )

    def rotate(
        self,
        token_hash: str,
        replacement_hash: str,
        replacement_expires_at: datetime,
        now: datetime,
    ) -> UUID | None:
        stored = self.tokens.get(token_hash)
        if stored is None or stored.revoked_at is not None:
            return None
        if stored.expires_at <= now:
            return None

        stored.revoked_at = now
        self.tokens[replacement_hash] = _StoredRefreshToken(
            user_id=stored.user_id,
            expires_at=replacement_expires_at,
        )
        return stored.user_id

    def revoke(self, token_hash: str, now: datetime) -> None:
        stored = self.tokens.get(token_hash)
        if stored is not None:
            stored.revoked_at = now

    def revoke_all_for_user(self, user_id: UUID, now: datetime) -> None:
        for stored in self.tokens.values():
            if stored.user_id == user_id:
                stored.revoked_at = now

    def live_tokens_for(self, user_id: UUID) -> list[str]:
        return [
            token_hash
            for token_hash, stored in self.tokens.items()
            if stored.user_id == user_id and stored.revoked_at is None
        ]


class FakeUserRepository:
    """Stands in for the user table, including its unique index on email."""

    def __init__(self, users: list[User] | None = None) -> None:
        self.users: dict[UUID, User] = {user.id: user for user in (users or [])}

    def list_all(self) -> list[User]:
        return sorted(self.users.values(), key=lambda user: user.created_at)

    def list_active(self) -> list[User]:
        return [user for user in self.list_all() if user.is_active]

    def get_by_email(self, email: str) -> User | None:
        return next(
            (user for user in self.users.values() if user.email == email),
            None,
        )

    def get_by_id(self, user_id: UUID) -> User | None:
        return self.users.get(user_id)

    def add(self, email: str, display_name: str, password_hash: str) -> User:
        if self.get_by_email(email) is not None:
            raise EmailAlreadyRegisteredError
        user = make_user(
            id=uuid4(),
            email=email,
            display_name=display_name,
            password_hash=password_hash,
            permissions=USER_PERMISSIONS,
        )
        self.users[user.id] = user
        return user

    def update_settings(
        self,
        user_id: UUID,
        display_name: str,
        daily_summary_enabled: bool,
        daily_summary_time: time,
        budget_alerts_enabled: bool,
    ) -> User | None:
        user = self.users.get(user_id)
        if user is None:
            return None
        updated = replace(
            user,
            display_name=display_name,
            daily_summary_enabled=daily_summary_enabled,
            daily_summary_time=daily_summary_time,
            budget_alerts_enabled=budget_alerts_enabled,
        )
        self.users[user_id] = updated
        return updated

    def update_password(self, user_id: UUID, password_hash: str) -> User | None:
        user = self.users.get(user_id)
        if user is None:
            return None
        # Stamped exactly as the real repository does: it is what invalidates
        # access tokens minted before the change.
        updated = replace(
            user,
            password_hash=password_hash,
            password_changed_at=datetime.now(tz=user.created_at.tzinfo),
        )
        self.users[user_id] = updated
        return updated

    def update_email(self, user_id: UUID, email: str) -> User | None:
        user = self.users.get(user_id)
        if user is None:
            return None
        taken = self.get_by_email(email)
        if taken is not None and taken.id != user_id:
            raise EmailAlreadyRegisteredError
        updated = replace(user, email=email)
        self.users[user_id] = updated
        return updated

    def set_opening_balance(self, user_id: UUID, amount_minor: int) -> int | None:
        user = self.users.get(user_id)
        if user is None:
            return None
        self.users[user_id] = replace(user, opening_balance_minor=amount_minor)
        return amount_minor

    def set_savings_goal(self, user_id: UUID, amount_minor: int) -> int | None:
        user = self.users.get(user_id)
        if user is None:
            return None
        self.users[user_id] = replace(user, savings_goal_minor=amount_minor)
        return amount_minor

    def set_active(self, user_id: UUID, is_active: bool) -> User | None:
        user = self.users.get(user_id)
        if user is None:
            return None
        updated = replace(user, is_active=is_active)
        self.users[user_id] = updated
        return updated


@dataclass
class _StoredResetToken:
    user_id: UUID
    expires_at: datetime
    used_at: datetime | None = None


class FakePasswordResetTokenRepository:
    def __init__(self) -> None:
        self.tokens: dict[str, _StoredResetToken] = {}

    def replace_for_user(
        self,
        user_id: UUID,
        token_hash: str,
        expires_at: datetime,
        now: datetime,
    ) -> None:
        # One live link per account, as the real table enforces by spending
        # whatever was outstanding before writing the new row.
        for stored in self.tokens.values():
            if stored.user_id == user_id:
                stored.used_at = now
        self.tokens[token_hash] = _StoredResetToken(
            user_id=user_id,
            expires_at=expires_at,
        )

    def consume(self, token_hash: str, now: datetime) -> UUID | None:
        stored = self.tokens.get(token_hash)
        if stored is None or stored.used_at is not None:
            return None
        if stored.expires_at <= now:
            return None
        stored.used_at = now
        return stored.user_id


@dataclass
class _StoredEmailChange:
    user_id: UUID
    new_email: str
    expires_at: datetime
    used_at: datetime | None = None


class FakeEmailChangeTokenRepository:
    def __init__(self) -> None:
        self.tokens: dict[str, _StoredEmailChange] = {}

    def replace_for_user(
        self,
        user_id: UUID,
        new_email: str,
        token_hash: str,
        expires_at: datetime,
        now: datetime,
    ) -> None:
        for stored in self.tokens.values():
            if stored.user_id == user_id:
                stored.used_at = now
        self.tokens[token_hash] = _StoredEmailChange(
            user_id=user_id,
            new_email=new_email,
            expires_at=expires_at,
        )

    def consume(self, token_hash: str, now: datetime) -> PendingEmailChange | None:
        stored = self.tokens.get(token_hash)
        if stored is None or stored.used_at is not None:
            return None
        if stored.expires_at <= now:
            return None
        stored.used_at = now
        return PendingEmailChange(user_id=stored.user_id, new_email=stored.new_email)


class FakeCategoryRepository:
    def __init__(self, categories: list[Category] | None = None) -> None:
        self.categories: list[Category] = list(categories or [])

    def list_available(
        self,
        user_id: UUID,
        kind: TransactionKind | None = None,
    ) -> list[Category]:
        available = [
            category
            for category in self.categories
            if category.user_id in (None, user_id)
            and (kind is None or category.kind == kind)
        ]
        return sorted(available, key=lambda category: category.name)

    def get_available_by_id(
        self,
        user_id: UUID,
        category_id: UUID,
    ) -> Category | None:
        return next(
            (
                category
                for category in self.categories
                if category.id == category_id and category.user_id in (None, user_id)
            ),
            None,
        )

    def add(
        self,
        user_id: UUID,
        name: str,
        kind: TransactionKind,
        color: str,
    ) -> Category:
        category = Category(
            id=uuid4(),
            user_id=user_id,
            name=name,
            kind=kind,
            color=color,
        )
        self.categories.append(category)
        return category


class FakeTransactionRepository:
    def __init__(self, transactions: list[Transaction] | None = None) -> None:
        self.transactions: list[Transaction] = list(transactions or [])

    def get_balance(self, user_id: UUID, before: datetime) -> AccountBalance:
        counted = [
            item
            for item in self.transactions
            if item.user_id == user_id and item.occurred_at < before
        ]
        return AccountBalance(
            total_income_minor=sum(
                item.amount_minor
                for item in counted
                if item.kind == TransactionKind.INCOME
            ),
            total_expense_minor=sum(
                item.amount_minor
                for item in counted
                if item.kind == TransactionKind.EXPENSE
            ),
        )

    def list_for_user(
        self,
        user_id: UUID,
        start: datetime,
        end: datetime,
        category_id: UUID | None = None,
        kind: TransactionKind | None = None,
    ) -> list[Transaction]:
        matches = [
            item
            for item in self.transactions
            if item.user_id == user_id
            and start <= item.occurred_at < end
            and (category_id is None or item.category_id == category_id)
            and (kind is None or item.kind == kind)
        ]
        return sorted(matches, key=lambda item: item.occurred_at, reverse=True)

    def add(
        self,
        user_id: UUID,
        category: Category,
        kind: TransactionKind,
        amount_minor: int,
        description: str,
        occurred_at: datetime,
    ) -> Transaction:
        transaction = Transaction(
            id=uuid4(),
            user_id=user_id,
            category_id=category.id,
            category_name=category.name,
            category_color=category.color,
            kind=kind,
            amount_minor=amount_minor,
            description=description,
            occurred_at=occurred_at,
            created_at=CREATED_AT,
        )
        self.transactions.append(transaction)
        return transaction

    def update(
        self,
        user_id: UUID,
        transaction_id: UUID,
        category: Category,
        kind: TransactionKind,
        amount_minor: int,
        description: str,
        occurred_at: datetime,
    ) -> Transaction | None:
        for index, item in enumerate(self.transactions):
            if item.id == transaction_id and item.user_id == user_id:
                updated = replace(
                    item,
                    category_id=category.id,
                    category_name=category.name,
                    category_color=category.color,
                    kind=kind,
                    amount_minor=amount_minor,
                    description=description,
                    occurred_at=occurred_at,
                )
                self.transactions[index] = updated
                return updated
        return None

    def remove(self, user_id: UUID, transaction_id: UUID) -> bool:
        for index, item in enumerate(self.transactions):
            if item.id == transaction_id and item.user_id == user_id:
                del self.transactions[index]
                return True
        return False

    def add_subscription_charge(
        self,
        subscription: Subscription,
        charge_date: date,
        occurred_at: datetime,
    ) -> Transaction | None:
        already_charged = any(
            item.subscription_id == subscription.id
            and item.subscription_charge_date == charge_date
            for item in self.transactions
        )
        if already_charged:
            # The unique index says one charge per subscription per date, and
            # the catch-up walk relies on that to stay idempotent.
            return None

        transaction = Transaction(
            id=uuid4(),
            user_id=subscription.user_id,
            category_id=subscription.category_id,
            category_name=subscription.category_name,
            category_color=subscription.category_color,
            kind=subscription.kind,
            amount_minor=subscription.amount_minor,
            description=subscription.name,
            occurred_at=occurred_at,
            created_at=CREATED_AT,
            subscription_id=subscription.id,
            subscription_charge_date=charge_date,
        )
        self.transactions.append(transaction)
        return transaction


class FakeSubscriptionRepository:
    def __init__(self, subscriptions: list[Subscription] | None = None) -> None:
        self.subscriptions: list[Subscription] = list(subscriptions or [])

    def list_active(self, user_id: UUID) -> list[Subscription]:
        return [
            item
            for item in self.subscriptions
            if item.user_id == user_id and item.is_active
        ]

    def list_due(self, user_id: UUID, through_date: date) -> list[Subscription]:
        return [
            item
            for item in self.list_active(user_id)
            if item.next_charge_date <= through_date
        ]

    def add(
        self,
        user_id: UUID,
        category: Category,
        name: str,
        amount_minor: int,
        first_charge_date: date,
    ) -> Subscription:
        subscription = Subscription(
            id=uuid4(),
            user_id=user_id,
            category_id=category.id,
            category_name=category.name,
            category_color=category.color,
            kind=category.kind,
            name=name,
            amount_minor=amount_minor,
            billing_day=first_charge_date.day,
            next_charge_date=first_charge_date,
            is_active=True,
            created_at=CREATED_AT,
        )
        self.subscriptions.append(subscription)
        return subscription

    def update_next_charge(
        self,
        user_id: UUID,
        subscription_id: UUID,
        next_charge_date: date,
    ) -> None:
        for index, item in enumerate(self.subscriptions):
            if item.id == subscription_id and item.user_id == user_id:
                self.subscriptions[index] = replace(
                    item,
                    next_charge_date=next_charge_date,
                )
                return

    def update(
        self,
        user_id: UUID,
        subscription_id: UUID,
        category: Category,
        name: str,
        amount_minor: int,
        billing_day: int,
    ) -> Subscription | None:
        for index, item in enumerate(self.subscriptions):
            if (
                item.id == subscription_id
                and item.user_id == user_id
                and item.is_active
            ):
                updated = replace(
                    item,
                    category_id=category.id,
                    category_name=category.name,
                    category_color=category.color,
                    kind=category.kind,
                    name=name,
                    amount_minor=amount_minor,
                    billing_day=billing_day,
                )
                self.subscriptions[index] = updated
                return updated
        return None

    def deactivate(self, user_id: UUID, subscription_id: UUID) -> bool:
        for index, item in enumerate(self.subscriptions):
            if (
                item.id == subscription_id
                and item.user_id == user_id
                and item.is_active
            ):
                self.subscriptions[index] = replace(item, is_active=False)
                return True
        return False


class FakeBudgetRepository:
    def __init__(self, budgets: list[MonthlyBudget] | None = None) -> None:
        self.budgets: list[MonthlyBudget] = list(budgets or [])

    def list_for_user(self, user_id: UUID) -> list[MonthlyBudget]:
        return [item for item in self.budgets if item.user_id == user_id]

    def upsert(
        self,
        user_id: UUID,
        category: Category,
        limit_minor: int,
    ) -> MonthlyBudget:
        for index, item in enumerate(self.budgets):
            if item.user_id == user_id and item.category_id == category.id:
                updated = replace(item, limit_minor=limit_minor)
                self.budgets[index] = updated
                return updated

        budget = MonthlyBudget(
            id=uuid4(),
            user_id=user_id,
            category_id=category.id,
            category_name=category.name,
            category_color=category.color,
            limit_minor=limit_minor,
            created_at=CREATED_AT,
            updated_at=CREATED_AT,
        )
        self.budgets.append(budget)
        return budget

    def update(
        self,
        user_id: UUID,
        budget_id: UUID,
        category: Category,
        limit_minor: int,
    ) -> MonthlyBudget | None:
        for index, item in enumerate(self.budgets):
            if item.id == budget_id and item.user_id == user_id:
                updated = replace(
                    item,
                    category_id=category.id,
                    category_name=category.name,
                    category_color=category.color,
                    limit_minor=limit_minor,
                )
                self.budgets[index] = updated
                return updated
        return None

    def remove(self, user_id: UUID, category_id: UUID) -> bool:
        for index, item in enumerate(self.budgets):
            if item.user_id == user_id and item.category_id == category_id:
                del self.budgets[index]
                return True
        return False


class FakeSavingsRepository:
    def __init__(self, entries: list[MonthlySaving] | None = None) -> None:
        self.entries: list[MonthlySaving] = list(entries or [])

    def list_for_user(self, user_id: UUID) -> list[MonthlySaving]:
        return sorted(
            (item for item in self.entries if item.user_id == user_id),
            key=lambda item: (item.year, item.month),
        )

    def upsert_month(
        self,
        user_id: UUID,
        year: int,
        month: int,
        amount_minor: int,
    ) -> MonthlySaving:
        for index, item in enumerate(self.entries):
            if item.user_id == user_id and (item.year, item.month) == (year, month):
                updated = replace(item, amount_minor=amount_minor)
                self.entries[index] = updated
                return updated

        entry = MonthlySaving(
            id=uuid4(),
            user_id=user_id,
            year=year,
            month=month,
            amount_minor=amount_minor,
            created_at=CREATED_AT,
            updated_at=CREATED_AT,
        )
        self.entries.append(entry)
        return entry


class FakeCashFlowReader:
    """Income and expense per month, the one read the savings walk makes."""

    def __init__(
        self,
        totals: dict[tuple[int, int], tuple[int, int]] | None = None,
    ) -> None:
        self.totals = dict(totals or {})
        self.timezones_asked: list[str] = []

    def monthly_totals(
        self,
        user_id: UUID,
        timezone_name: str,
    ) -> dict[tuple[int, int], tuple[int, int]]:
        self.timezones_asked.append(timezone_name)
        return dict(self.totals)


class FakeAdminFinanceReader:
    def __init__(
        self,
        totals: dict[UUID, UserFinanceTotals] | None = None,
        transactions: list[Transaction] | None = None,
        spending: list[AdminCategorySpending] | None = None,
        subscriptions: list[Subscription] | None = None,
    ) -> None:
        self.totals = dict(totals or {})
        self.transactions = list(transactions or [])
        self.spending = list(spending or [])
        self.subscriptions = list(subscriptions or [])
        self.limits_asked: list[int] = []

    def get_totals(self, user_id: UUID, before: datetime) -> UserFinanceTotals:
        return self.totals.get(
            user_id,
            UserFinanceTotals(
                total_income_minor=0,
                total_expense_minor=0,
                transaction_count=0,
            ),
        )

    def list_recent_transactions(
        self,
        user_id: UUID,
        before: datetime,
        limit: int,
    ) -> list[Transaction]:
        self.limits_asked.append(limit)
        return [item for item in self.transactions if item.user_id == user_id][:limit]

    def list_category_spending(
        self,
        user_id: UUID,
        before: datetime,
    ) -> list[AdminCategorySpending]:
        return list(self.spending)

    def list_active_subscriptions(self, user_id: UUID) -> list[Subscription]:
        return [
            item
            for item in self.subscriptions
            if item.user_id == user_id and item.is_active
        ]


class FakeDeliveryRepository:
    """The record that stops the same notification going out twice."""

    def __init__(self) -> None:
        self.delivered: set[tuple[UUID, str, str]] = set()

    def was_delivered(self, user_id: UUID, kind: str, reference_key: str) -> bool:
        return (user_id, kind, reference_key) in self.delivered

    def mark_delivered(
        self,
        user_id: UUID,
        kind: str,
        reference_key: str,
        delivered_at: datetime,
    ) -> None:
        self.delivered.add((user_id, kind, reference_key))
