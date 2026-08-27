"""Monthly spending limits."""

from uuid import uuid4

import pytest

from app.application.ledger.budgets import (
    ListMonthlyBudgets,
    RemoveMonthlyBudget,
    SetMonthlyBudget,
    UpdateMonthlyBudget,
)
from app.application.ledger.errors import (
    BudgetNotFoundError,
    CategoryKindMismatchError,
    CategoryNotFoundError,
)
from app.domain.ledger.models import TransactionKind
from tests.factories import make_budget, make_category, make_user
from tests.fakes import FakeBudgetRepository, FakeCategoryRepository


def test_setting_a_limit_records_it_against_the_category() -> None:
    user = make_user()
    food = make_category(name="Yemek", kind=TransactionKind.EXPENSE)
    budgets = FakeBudgetRepository()

    budget = SetMonthlyBudget(FakeCategoryRepository([food]), budgets).execute(
        user_id=user.id,
        category_id=food.id,
        limit_minor=150_000,
    )

    assert budget.category_name == "Yemek"
    assert budget.limit_minor == 150_000


def test_setting_a_limit_twice_replaces_it_rather_than_adding_one() -> None:
    user = make_user()
    food = make_category(kind=TransactionKind.EXPENSE)
    categories = FakeCategoryRepository([food])
    budgets = FakeBudgetRepository()
    use_case = SetMonthlyBudget(categories, budgets)

    use_case.execute(user_id=user.id, category_id=food.id, limit_minor=150_000)
    use_case.execute(user_id=user.id, category_id=food.id, limit_minor=90_000)

    assert [item.limit_minor for item in budgets.list_for_user(user.id)] == [90_000]


def test_an_income_category_cannot_carry_a_limit() -> None:
    """A limit is a ceiling on spending, and there is nothing to cap about
    money coming in."""
    salary = make_category(kind=TransactionKind.INCOME)

    with pytest.raises(CategoryKindMismatchError):
        SetMonthlyBudget(
            FakeCategoryRepository([salary]),
            FakeBudgetRepository(),
        ).execute(user_id=make_user().id, category_id=salary.id, limit_minor=1_000)


def test_an_unknown_category_cannot_carry_a_limit() -> None:
    with pytest.raises(CategoryNotFoundError):
        SetMonthlyBudget(
            FakeCategoryRepository(),
            FakeBudgetRepository(),
        ).execute(user_id=make_user().id, category_id=uuid4(), limit_minor=1_000)


def test_listing_returns_only_the_users_limits() -> None:
    user = make_user()
    budgets = FakeBudgetRepository(
        [make_budget(user_id=user.id), make_budget(user_id=uuid4())]
    )

    listed = ListMonthlyBudgets(budgets).execute(user.id)

    assert [item.user_id for item in listed] == [user.id]


def test_removing_a_limit_that_is_not_there_is_reported() -> None:
    with pytest.raises(BudgetNotFoundError):
        RemoveMonthlyBudget(FakeBudgetRepository()).execute(
            make_user().id,
            uuid4(),
        )


def test_removing_takes_the_limit_away() -> None:
    user = make_user()
    budget = make_budget(user_id=user.id)
    budgets = FakeBudgetRepository([budget])

    RemoveMonthlyBudget(budgets).execute(user.id, budget.category_id)

    assert budgets.list_for_user(user.id) == []


def test_editing_can_move_a_limit_to_another_category() -> None:
    user = make_user()
    food = make_category(name="Yemek", kind=TransactionKind.EXPENSE)
    transport = make_category(name="Ulaşım", kind=TransactionKind.EXPENSE)
    budget = make_budget(user_id=user.id, category_id=food.id)
    budgets = FakeBudgetRepository([budget])

    updated = UpdateMonthlyBudget(
        FakeCategoryRepository([food, transport]),
        budgets,
    ).execute(
        user_id=user.id,
        budget_id=budget.id,
        category_id=transport.id,
        limit_minor=60_000,
    )

    assert updated.category_name == "Ulaşım"
    assert updated.limit_minor == 60_000


def test_editing_a_limit_that_belongs_to_someone_else_is_refused() -> None:
    food = make_category(kind=TransactionKind.EXPENSE)
    theirs = make_budget(user_id=uuid4(), category_id=food.id)
    budgets = FakeBudgetRepository([theirs])

    with pytest.raises(BudgetNotFoundError):
        UpdateMonthlyBudget(FakeCategoryRepository([food]), budgets).execute(
            user_id=make_user().id,
            budget_id=theirs.id,
            category_id=food.id,
            limit_minor=1,
        )
