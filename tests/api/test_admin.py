"""The administration endpoints, and who is turned away from them."""

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from tests.api.conftest import (
    Account,
    FOOD_CATEGORY_ID,
    SALARY_CATEGORY_ID,
    today,
)

pytestmark = pytest.mark.api

FORBIDDEN = "Bu işlem için yetkiniz yok."


def test_an_ordinary_account_is_turned_away(
    client: TestClient,
    account: Account,
) -> None:
    """The permission comes from a role granted by hand at the database prompt.
    Nothing an ordinary session can do reaches it."""
    response = client.get("/api/v1/admin/users")

    assert response.status_code == 403
    assert response.json()["data"]["detail"] == FORBIDDEN


def test_an_ordinary_account_cannot_read_another_users_finances(
    client: TestClient,
    account: Account,
    other_account: Account,
) -> None:
    response = client.get(f"/api/v1/admin/users/{other_account.id}/finance")

    assert response.status_code == 403


def test_an_ordinary_account_cannot_change_anybodys_status(
    client: TestClient,
    account: Account,
    other_account: Account,
) -> None:
    response = client.patch(
        f"/api/v1/admin/users/{other_account.id}/status",
        json={"is_active": False},
    )

    assert response.status_code == 403


def test_an_administrator_sees_every_account(
    client: TestClient,
    other_client: TestClient,
    admin: Account,
    other_account: Account,
) -> None:
    response = client.get("/api/v1/admin/users")

    assert response.status_code == 200
    assert {item["email"] for item in response.json()["data"]} == {
        admin.email,
        other_account.email,
    }


def test_a_summary_adds_up_the_accounts_money(
    client: TestClient,
    admin: Account,
) -> None:
    client.post(
        "/api/v1/transactions",
        json={
            "category_id": SALARY_CATEGORY_ID,
            "kind": "INCOME",
            "amount": "1000.00",
            "description": "Maaş",
            "occurred_on": today().isoformat(),
        },
    )
    client.put("/api/v1/balance/opening", json={"amount": "250.00"})

    summary = next(
        item
        for item in client.get("/api/v1/admin/users").json()["data"]
        if item["email"] == admin.email
    )

    assert summary["total_income_minor"] == 100_000
    assert summary["transaction_count"] == 1
    assert summary["current_balance_minor"] == 125_000


def test_a_summary_never_carries_password_material(
    client: TestClient,
    admin: Account,
) -> None:
    response = client.get("/api/v1/admin/users")

    assert "password" not in response.text


def test_an_administrator_can_read_one_accounts_detail(
    client: TestClient,
    other_client: TestClient,
    admin: Account,
    other_account: Account,
) -> None:
    other_client.post(
        "/api/v1/transactions",
        json={
            "category_id": FOOD_CATEGORY_ID,
            "kind": "EXPENSE",
            "amount": "50.00",
            "description": "Öğle yemeği",
            "occurred_on": today().isoformat(),
        },
    )

    response = client.get(f"/api/v1/admin/users/{other_account.id}/finance")

    assert response.status_code == 200
    body = response.json()["data"]
    assert [item["description"] for item in body["recent_transactions"]] == [
        "Öğle yemeği"
    ]
    assert body["category_spending"][0]["total_expense_minor"] == 5_000


def test_asking_about_an_account_that_is_not_there_is_reported(
    client: TestClient,
    admin: Account,
) -> None:
    response = client.get(f"/api/v1/admin/users/{uuid4()}/finance")

    assert response.status_code == 404


def test_an_administrator_can_deactivate_somebody(
    client: TestClient,
    other_client: TestClient,
    admin: Account,
    other_account: Account,
) -> None:
    response = client.patch(
        f"/api/v1/admin/users/{other_account.id}/status",
        json={"is_active": False},
    )

    assert response.status_code == 200
    assert response.json()["data"]["is_active"] is False
    assert other_client.get("/api/v1/auth/me").status_code == 401


def test_a_deactivated_account_can_be_let_back_in(
    client: TestClient,
    other_client: TestClient,
    admin: Account,
    other_account: Account,
) -> None:
    client.patch(
        f"/api/v1/admin/users/{other_account.id}/status",
        json={"is_active": False},
    )

    client.patch(
        f"/api/v1/admin/users/{other_account.id}/status",
        json={"is_active": True},
    )

    assert other_client.get("/api/v1/auth/me").status_code == 200


def test_an_administrator_cannot_lock_themselves_out(
    client: TestClient,
    admin: Account,
) -> None:
    """The first ADMIN is granted by hand in the database. Losing the last one
    would mean going back there to get it back."""
    response = client.patch(
        f"/api/v1/admin/users/{admin.id}/status",
        json={"is_active": False},
    )

    assert response.status_code == 409
    assert client.get("/api/v1/auth/me").status_code == 200


def test_changing_the_status_of_an_unknown_account_is_reported(
    client: TestClient,
    admin: Account,
) -> None:
    response = client.patch(
        f"/api/v1/admin/users/{uuid4()}/status",
        json={"is_active": False},
    )

    assert response.status_code == 404
