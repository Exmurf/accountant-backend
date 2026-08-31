"""Monthly spending limits over HTTP."""

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from tests.api.conftest import (
    Account,
    FOOD_CATEGORY_ID,
    SALARY_CATEGORY_ID,
)

pytestmark = pytest.mark.api

TRANSPORT_CATEGORY_ID = "20000000-0000-0000-0000-000000000005"


def test_a_limit_can_be_set_on_an_expense_category(
    client: TestClient,
    account: Account,
) -> None:
    response = client.put(
        f"/api/v1/budgets/{FOOD_CATEGORY_ID}",
        json={"limit": "1500.00"},
    )

    assert response.status_code == 200
    assert response.json()["data"]["limit_minor"] == 150_000
    assert response.json()["data"]["category_name"] == "Yemek"


def test_setting_the_limit_again_replaces_it(
    client: TestClient,
    account: Account,
) -> None:
    client.put(f"/api/v1/budgets/{FOOD_CATEGORY_ID}", json={"limit": "1500.00"})

    client.put(f"/api/v1/budgets/{FOOD_CATEGORY_ID}", json={"limit": "900.00"})

    listed = client.get("/api/v1/budgets").json()["data"]
    assert [item["limit_minor"] for item in listed] == [90_000]


def test_an_income_category_cannot_carry_a_limit(
    client: TestClient,
    account: Account,
) -> None:
    response = client.put(
        f"/api/v1/budgets/{SALARY_CATEGORY_ID}",
        json={"limit": "1500.00"},
    )

    assert response.status_code == 422


def test_an_unknown_category_cannot_carry_a_limit(
    client: TestClient,
    account: Account,
) -> None:
    response = client.put(f"/api/v1/budgets/{uuid4()}", json={"limit": "1500.00"})

    assert response.status_code == 404


@pytest.mark.parametrize("limit", ["0", "-5.00"])
def test_a_limit_has_to_be_a_positive_amount(
    client: TestClient,
    account: Account,
    limit: str,
) -> None:
    response = client.put(
        f"/api/v1/budgets/{FOOD_CATEGORY_ID}",
        json={"limit": limit},
    )

    assert response.status_code == 422


def test_the_list_is_empty_until_a_limit_is_set(
    client: TestClient,
    account: Account,
) -> None:
    assert client.get("/api/v1/budgets").json()["data"] == []


def test_a_limit_can_be_moved_to_another_category(
    client: TestClient,
    account: Account,
) -> None:
    budget = client.put(
        f"/api/v1/budgets/{FOOD_CATEGORY_ID}",
        json={"limit": "1500.00"},
    ).json()["data"]

    response = client.patch(
        f"/api/v1/budgets/{budget['id']}",
        json={"limit": "600.00", "category_id": TRANSPORT_CATEGORY_ID},
    )

    assert response.status_code == 200
    assert response.json()["data"]["category_name"] == "Ulaşım"
    assert response.json()["data"]["limit_minor"] == 60_000


def test_two_limits_cannot_land_on_one_category(
    client: TestClient,
    account: Account,
) -> None:
    client.put(f"/api/v1/budgets/{FOOD_CATEGORY_ID}", json={"limit": "1500.00"})
    transport = client.put(
        f"/api/v1/budgets/{TRANSPORT_CATEGORY_ID}",
        json={"limit": "600.00"},
    ).json()["data"]

    response = client.patch(
        f"/api/v1/budgets/{transport['id']}",
        json={"limit": "600.00", "category_id": FOOD_CATEGORY_ID},
    )

    assert response.status_code == 409


def test_editing_a_limit_that_is_not_there_is_reported(
    client: TestClient,
    account: Account,
) -> None:
    response = client.patch(
        f"/api/v1/budgets/{uuid4()}",
        json={"limit": "600.00", "category_id": FOOD_CATEGORY_ID},
    )

    assert response.status_code == 404


def test_a_limit_can_be_removed(client: TestClient, account: Account) -> None:
    client.put(f"/api/v1/budgets/{FOOD_CATEGORY_ID}", json={"limit": "1500.00"})

    response = client.delete(f"/api/v1/budgets/{FOOD_CATEGORY_ID}")

    assert response.status_code == 200
    assert client.get("/api/v1/budgets").json()["data"] == []


def test_removing_a_limit_that_is_not_there_is_reported(
    client: TestClient,
    account: Account,
) -> None:
    assert client.delete(f"/api/v1/budgets/{FOOD_CATEGORY_ID}").status_code == 404


def test_one_account_cannot_see_anothers_limits(
    client: TestClient,
    other_client: TestClient,
    account: Account,
    other_account: Account,
) -> None:
    other_client.put(f"/api/v1/budgets/{FOOD_CATEGORY_ID}", json={"limit": "1500.00"})

    assert client.get("/api/v1/budgets").json()["data"] == []


def test_one_account_cannot_remove_anothers_limits(
    client: TestClient,
    other_client: TestClient,
    account: Account,
    other_account: Account,
) -> None:
    other_client.put(f"/api/v1/budgets/{FOOD_CATEGORY_ID}", json={"limit": "1500.00"})

    response = client.delete(f"/api/v1/budgets/{FOOD_CATEGORY_ID}")

    assert response.status_code == 404
    assert len(other_client.get("/api/v1/budgets").json()["data"]) == 1
