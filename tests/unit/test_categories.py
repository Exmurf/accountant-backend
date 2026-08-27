"""Categories: the shared defaults and a user's own."""

from uuid import uuid4

from app.application.ledger.categories import CreateCategory, ListCategories
from app.domain.ledger.models import TransactionKind
from tests.factories import make_category, make_user
from tests.fakes import FakeCategoryRepository


def test_listing_shows_the_defaults_and_the_users_own() -> None:
    user = make_user()
    categories = FakeCategoryRepository(
        [
            make_category(user_id=None, name="Yemek"),
            make_category(user_id=user.id, name="Kahve"),
            make_category(user_id=uuid4(), name="Başkasının"),
        ]
    )

    listed = ListCategories(categories).execute(user.id)

    assert [item.name for item in listed] == ["Kahve", "Yemek"]


def test_listing_can_be_narrowed_to_one_kind() -> None:
    user = make_user()
    categories = FakeCategoryRepository(
        [
            make_category(name="Yemek", kind=TransactionKind.EXPENSE),
            make_category(name="Maaş", kind=TransactionKind.INCOME),
        ]
    )

    income_only = ListCategories(categories).execute(
        user.id,
        TransactionKind.INCOME,
    )

    assert [item.name for item in income_only] == ["Maaş"]


def test_a_new_category_belongs_to_the_user_who_made_it() -> None:
    user = make_user()
    categories = FakeCategoryRepository()

    created = CreateCategory(categories).execute(
        user_id=user.id,
        name="Kahve",
        kind=TransactionKind.EXPENSE,
        color="#8c7ab8",
    )

    assert created.user_id == user.id


def test_the_name_is_trimmed() -> None:
    categories = FakeCategoryRepository()

    created = CreateCategory(categories).execute(
        user_id=make_user().id,
        name="  Kahve  ",
        kind=TransactionKind.EXPENSE,
        color="#8c7ab8",
    )

    assert created.name == "Kahve"
