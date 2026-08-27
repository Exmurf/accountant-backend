"""Ready-made domain objects.

Every field has a defensible default so a test can name only what it is about.
A test that reads `make_user(is_active=False)` says what it is testing in its
first line; the same test spelled out over fourteen keyword arguments does not.
"""

from datetime import UTC, date, datetime, time
from uuid import UUID, uuid4

from app.domain.identity.user import User
from app.domain.ledger.budget import MonthlyBudget
from app.domain.ledger.models import Category, Transaction, TransactionKind
from app.domain.ledger.subscription import Subscription
from app.domain.savings.models import MonthlySaving

# Fixed so a failure message reads the same on every run.
CREATED_AT = datetime(2026, 1, 1, 9, 0, tzinfo=UTC)

USER_PERMISSIONS = frozenset({"finance.read.self", "finance.write.self"})
ADMIN_PERMISSIONS = USER_PERMISSIONS | frozenset(
    {"finance.read.any", "users.read", "users.manage"}
)


def make_user(**overrides: object) -> User:
    defaults: dict[str, object] = {
        "id": uuid4(),
        "email": "ahmet@mail.dev",
        "display_name": "Ahmet",
        "password_hash": "hashed:parola123",
        "is_active": True,
        "opening_balance_minor": 0,
        "savings_goal_minor": 0,
        "daily_summary_enabled": True,
        "daily_summary_time": time(21, 0),
        "budget_alerts_enabled": True,
        "roles": frozenset({"USER"}),
        "permissions": USER_PERMISSIONS,
        "created_at": CREATED_AT,
        "password_changed_at": None,
    }
    return User(**{**defaults, **overrides})  # type: ignore[arg-type]


def make_category(**overrides: object) -> Category:
    defaults: dict[str, object] = {
        "id": uuid4(),
        "user_id": None,
        "name": "Yemek",
        "kind": TransactionKind.EXPENSE,
        "color": "#ec8c5a",
    }
    return Category(**{**defaults, **overrides})  # type: ignore[arg-type]


def make_transaction(**overrides: object) -> Transaction:
    category = overrides.pop("category", None)
    if isinstance(category, Category):
        overrides.setdefault("category_id", category.id)
        overrides.setdefault("category_name", category.name)
        overrides.setdefault("category_color", category.color)
        overrides.setdefault("kind", category.kind)
    defaults: dict[str, object] = {
        "id": uuid4(),
        "user_id": uuid4(),
        "category_id": uuid4(),
        "category_name": "Yemek",
        "category_color": "#ec8c5a",
        "kind": TransactionKind.EXPENSE,
        "amount_minor": 5000,
        "description": "Öğle yemeği",
        "occurred_at": CREATED_AT,
        "created_at": CREATED_AT,
        "subscription_id": None,
        "subscription_charge_date": None,
    }
    return Transaction(**{**defaults, **overrides})  # type: ignore[arg-type]


def make_subscription(**overrides: object) -> Subscription:
    defaults: dict[str, object] = {
        "id": uuid4(),
        "user_id": uuid4(),
        "category_id": uuid4(),
        "category_name": "Abonelik",
        "category_color": "#7a6ff0",
        "kind": TransactionKind.EXPENSE,
        "name": "Müzik servisi",
        "amount_minor": 6000,
        "billing_day": 15,
        "next_charge_date": date(2026, 2, 15),
        "is_active": True,
        "created_at": CREATED_AT,
    }
    return Subscription(**{**defaults, **overrides})  # type: ignore[arg-type]


def make_budget(**overrides: object) -> MonthlyBudget:
    defaults: dict[str, object] = {
        "id": uuid4(),
        "user_id": uuid4(),
        "category_id": uuid4(),
        "category_name": "Yemek",
        "category_color": "#ec8c5a",
        "limit_minor": 100_000,
        "created_at": CREATED_AT,
        "updated_at": CREATED_AT,
    }
    return MonthlyBudget(**{**defaults, **overrides})  # type: ignore[arg-type]


def make_saving(**overrides: object) -> MonthlySaving:
    defaults: dict[str, object] = {
        "id": uuid4(),
        "user_id": uuid4(),
        "year": 2026,
        "month": 1,
        "amount_minor": 25_000,
        "created_at": CREATED_AT,
        "updated_at": CREATED_AT,
    }
    return MonthlySaving(**{**defaults, **overrides})  # type: ignore[arg-type]


def uuid_from(value: int) -> UUID:
    """A readable UUID for tests that need to sort or compare them."""
    return UUID(int=value)
