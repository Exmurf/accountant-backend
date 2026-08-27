"""GET and POST /api/v1/categories"""

import pytest
from fastapi.testclient import TestClient

from tests.api.conftest import Account

pytestmark = pytest.mark.api

NEW_CATEGORY = {"name": "Kahve", "kind": "EXPENSE", "color": "#8c7ab8"}


def test_a_new_account_already_has_categories_to_spend_against(
    client: TestClient,
    account: Account,
) -> None:
    response = client.get("/api/v1/categories")

    assert response.status_code == 200
    names = {item["name"] for item in response.json()}
    assert {"Yemek", "Maaş"} <= names
    assert all(item["is_default"] for item in response.json())


def test_the_list_can_be_narrowed_to_one_kind(
    client: TestClient,
    account: Account,
) -> None:
    response = client.get("/api/v1/categories", params={"kind": "INCOME"})

    assert {item["kind"] for item in response.json()} == {"INCOME"}


def test_a_created_category_is_marked_as_the_users_own(
    client: TestClient,
    account: Account,
) -> None:
    response = client.post("/api/v1/categories", json=NEW_CATEGORY)

    assert response.status_code == 201
    assert response.json()["name"] == "Kahve"
    assert response.json()["is_default"] is False


def test_a_created_category_shows_up_in_the_list(
    client: TestClient,
    account: Account,
) -> None:
    client.post("/api/v1/categories", json=NEW_CATEGORY)

    names = {item["name"] for item in client.get("/api/v1/categories").json()}
    assert "Kahve" in names


def test_the_same_category_cannot_be_created_twice(
    client: TestClient,
    account: Account,
) -> None:
    client.post("/api/v1/categories", json=NEW_CATEGORY)

    response = client.post("/api/v1/categories", json=NEW_CATEGORY)

    assert response.status_code == 409


def test_a_colour_that_is_not_a_hex_code_is_refused(
    client: TestClient,
    account: Account,
) -> None:
    response = client.post(
        "/api/v1/categories",
        json={**NEW_CATEGORY, "color": "mor"},
    )

    assert response.status_code == 422


def test_a_kind_outside_the_two_is_refused(
    client: TestClient,
    account: Account,
) -> None:
    response = client.post(
        "/api/v1/categories",
        json={**NEW_CATEGORY, "kind": "TRANSFER"},
    )

    assert response.status_code == 422


def test_another_accounts_category_is_not_visible(
    client: TestClient,
    other_client: TestClient,
    account: Account,
    other_account: Account,
) -> None:
    other_client.post("/api/v1/categories", json={**NEW_CATEGORY, "name": "Gizli"})

    names = {item["name"] for item in client.get("/api/v1/categories").json()}
    assert "Gizli" not in names
