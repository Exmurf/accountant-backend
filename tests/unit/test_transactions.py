"""Balance, and the money entries it is computed from."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from app.application.ledger.errors import (
    CategoryKindMismatchError,
    CategoryNotFoundError,
    TransactionNotFoundError,
)
from app.application.ledger.transactions import (
    CreateTransaction,
    DeleteTransaction,
    GetAccountBalance,
    ListTransactions,
    SetOpeningBalance,
    UpdateTransaction,
)
from app.domain.ledger.models import TransactionKind
from tests.factories import make_category, make_transaction, make_user
from tests.fakes import (
    FakeCategoryRepository,
    FakeTransactionRepository,
    FakeUserRepository,
)

TOMORROW = datetime(2026, 3, 2, tzinfo=UTC)
YESTERDAY = datetime(2026, 2, 28, tzinfo=UTC)


def test_balance_is_the_opening_amount_plus_income_less_expense() -> None:
    user = make_user(opening_balance_minor=100_000)
    transactions = FakeTransactionRepository(
        [
            make_transaction(
                user_id=user.id,
                kind=TransactionKind.INCOME,
                amount_minor=250_000,
                occurred_at=YESTERDAY,
            ),
            make_transaction(
                user_id=user.id,
                kind=TransactionKind.EXPENSE,
                amount_minor=40_000,
                occurred_at=YESTERDAY,
            ),
        ]
    )

    balance = GetAccountBalance(transactions).execute(user, TOMORROW)

    assert balance.total_income_minor == 250_000
    assert balance.total_expense_minor == 40_000
    assert balance.current_balance_minor == 310_000


def test_balance_ignores_entries_dated_after_the_cutoff() -> None:
    """The cutoff is what keeps a charge dated next month out of today's
    number."""
    user = make_user()
    transactions = FakeTransactionRepository(
        [
            make_transaction(
                user_id=user.id,
                kind=TransactionKind.EXPENSE,
                amount_minor=9_000,
                occurred_at=datetime(2026, 4, 1, tzinfo=UTC),
            )
        ]
    )

    balance = GetAccountBalance(transactions).execute(user, TOMORROW)

    assert balance.total_expense_minor == 0


def test_balance_counts_only_the_owner_of_the_account() -> None:
    user = make_user()
    transactions = FakeTransactionRepository(
        [
            make_transaction(
                user_id=uuid4(),
                kind=TransactionKind.INCOME,
                amount_minor=500_000,
                occurred_at=YESTERDAY,
            )
        ]
    )

    balance = GetAccountBalance(transactions).execute(user, TOMORROW)

    assert balance.total_income_minor == 0


def test_setting_the_opening_amount_returns_the_recomputed_balance() -> None:
    user = make_user()
    users = FakeUserRepository([user])
    transactions = FakeTransactionRepository(
        [
            make_transaction(
                user_id=user.id,
                kind=TransactionKind.EXPENSE,
                amount_minor=30_000,
                occurred_at=YESTERDAY,
            )
        ]
    )

    balance = SetOpeningBalance(users, transactions).execute(
        user_id=user.id,
        amount_minor=200_000,
        before=TOMORROW,
    )

    assert balance.opening_balance_minor == 200_000
    assert balance.current_balance_minor == 170_000


def test_a_negative_opening_amount_is_allowed() -> None:
    """Starting in the red is a real situation, and the endpoint's schema is
    the only place that would refuse it."""
    user = make_user()
    users = FakeUserRepository([user])

    balance = SetOpeningBalance(users, FakeTransactionRepository()).execute(
        user_id=user.id,
        amount_minor=-50_000,
        before=TOMORROW,
    )

    assert balance.current_balance_minor == -50_000


def test_listing_passes_the_filters_through() -> None:
    user = make_user()
    food = make_category(name="Yemek", kind=TransactionKind.EXPENSE)
    salary = make_category(name="Maaş", kind=TransactionKind.INCOME)
    transactions = FakeTransactionRepository(
        [
            make_transaction(user_id=user.id, category=food, occurred_at=YESTERDAY),
            make_transaction(user_id=user.id, category=salary, occurred_at=YESTERDAY),
        ]
    )

    only_food = ListTransactions(transactions).execute(
        user.id,
        datetime(2026, 2, 1, tzinfo=UTC),
        TOMORROW,
        category_id=food.id,
    )

    assert [item.category_name for item in only_food] == ["Yemek"]


def create_transaction(
    categories: FakeCategoryRepository,
    transactions: FakeTransactionRepository,
    user_id,  # type: ignore[no-untyped-def]
    **overrides,  # type: ignore[no-untyped-def]
):
    payload = {
        "category_id": categories.categories[0].id,
        "kind": TransactionKind.EXPENSE,
        "amount_minor": 5_000,
        "description": "Öğle yemeği",
        "occurred_at": YESTERDAY,
    }
    payload.update(overrides)
    return CreateTransaction(categories, transactions).execute(
        user_id=user_id,
        **payload,
    )


def test_a_new_entry_takes_the_name_and_colour_of_its_category() -> None:
    user = make_user()
    food = make_category(name="Yemek", color="#ec8c5a")
    categories = FakeCategoryRepository([food])
    transactions = FakeTransactionRepository()

    created = create_transaction(categories, transactions, user.id)

    assert created.category_name == "Yemek"
    assert created.category_color == "#ec8c5a"


def test_the_description_is_trimmed() -> None:
    user = make_user()
    categories = FakeCategoryRepository([make_category()])

    created = create_transaction(
        categories,
        FakeTransactionRepository(),
        user.id,
        description="  Öğle yemeği  ",
    )

    assert created.description == "Öğle yemeği"


def test_an_unknown_category_is_refused() -> None:
    user = make_user()

    with pytest.raises(CategoryNotFoundError):
        create_transaction(
            FakeCategoryRepository([make_category()]),
            FakeTransactionRepository(),
            user.id,
            category_id=uuid4(),
        )


def test_another_users_category_cannot_be_spent_against() -> None:
    user = make_user()
    someone_elses = make_category(user_id=uuid4(), name="Gizli")

    with pytest.raises(CategoryNotFoundError):
        create_transaction(
            FakeCategoryRepository([someone_elses]),
            FakeTransactionRepository(),
            user.id,
            category_id=someone_elses.id,
        )


def test_income_cannot_be_filed_under_an_expense_category() -> None:
    user = make_user()
    food = make_category(kind=TransactionKind.EXPENSE)

    with pytest.raises(CategoryKindMismatchError):
        create_transaction(
            FakeCategoryRepository([food]),
            FakeTransactionRepository(),
            user.id,
            kind=TransactionKind.INCOME,
        )


def test_editing_replaces_every_field_it_was_given() -> None:
    user = make_user()
    food = make_category(name="Yemek", kind=TransactionKind.EXPENSE)
    transport = make_category(name="Ulaşım", kind=TransactionKind.EXPENSE)
    existing = make_transaction(user_id=user.id, category=food, amount_minor=5_000)
    transactions = FakeTransactionRepository([existing])

    updated = UpdateTransaction(
        FakeCategoryRepository([food, transport]),
        transactions,
    ).execute(
        user_id=user.id,
        transaction_id=existing.id,
        category_id=transport.id,
        kind=TransactionKind.EXPENSE,
        amount_minor=7_500,
        description="  Otobüs  ",
        occurred_at=YESTERDAY,
    )

    assert updated.category_name == "Ulaşım"
    assert updated.amount_minor == 7_500
    assert updated.description == "Otobüs"


def test_editing_an_entry_that_belongs_to_someone_else_is_refused() -> None:
    food = make_category()
    theirs = make_transaction(user_id=uuid4(), category=food)
    transactions = FakeTransactionRepository([theirs])

    with pytest.raises(TransactionNotFoundError):
        UpdateTransaction(FakeCategoryRepository([food]), transactions).execute(
            user_id=make_user().id,
            transaction_id=theirs.id,
            category_id=food.id,
            kind=food.kind,
            amount_minor=1,
            description="Ele geçirme",
            occurred_at=YESTERDAY,
        )


def test_deleting_removes_the_entry() -> None:
    user = make_user()
    existing = make_transaction(user_id=user.id)
    transactions = FakeTransactionRepository([existing])

    DeleteTransaction(transactions).execute(user.id, existing.id)

    assert transactions.transactions == []


def test_deleting_someone_elses_entry_is_refused() -> None:
    theirs = make_transaction(user_id=uuid4())
    transactions = FakeTransactionRepository([theirs])

    with pytest.raises(TransactionNotFoundError):
        DeleteTransaction(transactions).execute(make_user().id, theirs.id)

    assert transactions.transactions == [theirs]
