"""Money entries and the balance they add up to."""

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from tests.api.conftest import (
    Account,
    FOOD_CATEGORY_ID,
    SALARY_CATEGORY_ID,
    day_range,
    today,
    wide_range,
)

pytestmark = pytest.mark.api


def expense(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "category_id": FOOD_CATEGORY_ID,
        "kind": "EXPENSE",
        "amount": "50.00",
        "description": "Öğle yemeği",
        "occurred_on": today().isoformat(),
    }
    payload.update(overrides)
    return payload


def income(**overrides: object) -> dict[str, object]:
    return expense(
        category_id=SALARY_CATEGORY_ID,
        kind="INCOME",
        amount="1000.00",
        description="Maaş",
        **overrides,
    )


def test_an_entry_comes_back_with_its_category(
    client: TestClient,
    account: Account,
) -> None:
    response = client.post("/api/v1/transactions", json=expense())

    assert response.status_code == 201
    body = response.json()["data"]
    assert body["amount_minor"] == 5_000
    assert body["category_name"] == "Yemek"
    assert body["description"] == "Öğle yemeği"


def test_an_amount_is_stored_to_the_kuruş(
    client: TestClient,
    account: Account,
) -> None:
    """Money is kept as whole minor units, so nothing here ever rounds."""
    response = client.post("/api/v1/transactions", json=expense(amount="12.34"))

    assert response.json()["data"]["amount_minor"] == 1_234


def test_the_description_is_trimmed(client: TestClient, account: Account) -> None:
    response = client.post(
        "/api/v1/transactions",
        json=expense(description="  Öğle yemeği  "),
    )

    assert response.json()["data"]["description"] == "Öğle yemeği"


def test_a_new_entry_shows_up_in_the_days_list(
    client: TestClient,
    account: Account,
) -> None:
    client.post("/api/v1/transactions", json=expense())

    listed = client.get("/api/v1/transactions", params=day_range())

    assert listed.status_code == 200
    assert [item["description"] for item in listed.json()["data"]] == ["Öğle yemeği"]


def test_the_list_can_be_narrowed_by_kind(
    client: TestClient,
    account: Account,
) -> None:
    client.post("/api/v1/transactions", json=expense())
    client.post("/api/v1/transactions", json=income())

    listed = client.get(
        "/api/v1/transactions",
        params={**day_range(), "kind": "INCOME"},
    )

    assert [item["description"] for item in listed.json()["data"]] == ["Maaş"]


def test_the_list_can_be_narrowed_by_category(
    client: TestClient,
    account: Account,
) -> None:
    client.post("/api/v1/transactions", json=expense())
    client.post("/api/v1/transactions", json=income())

    listed = client.get(
        "/api/v1/transactions",
        params={**day_range(), "category_id": SALARY_CATEGORY_ID},
    )

    assert [item["category_name"] for item in listed.json()["data"]] == ["Maaş"]


def test_a_range_without_a_timezone_is_refused(
    client: TestClient,
    account: Account,
) -> None:
    """Which day an entry belongs to depends on where the reader is, so a
    range that does not say is a question with no answer."""
    response = client.get(
        "/api/v1/transactions",
        params={"start": "2026-03-01T00:00:00", "end": "2026-03-02T00:00:00"},
    )

    assert response.status_code == 422


def test_a_range_that_ends_before_it_starts_is_refused(
    client: TestClient,
    account: Account,
) -> None:
    window = day_range()
    response = client.get(
        "/api/v1/transactions",
        params={"start": window["end"], "end": window["start"]},
    )

    assert response.status_code == 422


def test_an_unknown_category_is_refused(
    client: TestClient,
    account: Account,
) -> None:
    response = client.post(
        "/api/v1/transactions",
        json=expense(category_id=str(uuid4())),
    )

    assert response.status_code == 404


def test_income_cannot_be_filed_under_an_expense_category(
    client: TestClient,
    account: Account,
) -> None:
    response = client.post("/api/v1/transactions", json=expense(kind="INCOME"))

    assert response.status_code == 422
    assert response.json()["data"]["detail"] == "Kategori ile hareket türü uyuşmuyor."


@pytest.mark.parametrize("amount", ["0", "-10.00", "1.234"])
def test_an_amount_that_is_not_positive_money_is_refused(
    client: TestClient,
    account: Account,
    amount: str,
) -> None:
    response = client.post("/api/v1/transactions", json=expense(amount=amount))

    assert response.status_code == 422


def test_an_entry_can_be_edited(client: TestClient, account: Account) -> None:
    created = client.post("/api/v1/transactions", json=expense()).json()["data"]

    response = client.patch(
        f"/api/v1/transactions/{created['id']}",
        json=expense(amount="75.50", description="Akşam yemeği"),
    )

    assert response.status_code == 200
    assert response.json()["data"]["amount_minor"] == 7_550
    assert response.json()["data"]["description"] == "Akşam yemeği"


def test_editing_an_entry_that_is_not_there_is_reported(
    client: TestClient,
    account: Account,
) -> None:
    response = client.patch(f"/api/v1/transactions/{uuid4()}", json=expense())

    assert response.status_code == 404


def test_an_entry_can_be_deleted(client: TestClient, account: Account) -> None:
    created = client.post("/api/v1/transactions", json=expense()).json()["data"]

    response = client.delete(f"/api/v1/transactions/{created['id']}")

    assert response.status_code == 200
    assert client.get("/api/v1/transactions", params=day_range()).json()["data"] == []


def test_deleting_an_entry_that_is_not_there_is_reported(
    client: TestClient,
    account: Account,
) -> None:
    assert client.delete(f"/api/v1/transactions/{uuid4()}").status_code == 404


def test_one_account_cannot_see_anothers_entries(
    client: TestClient,
    other_client: TestClient,
    account: Account,
    other_account: Account,
) -> None:
    other_client.post("/api/v1/transactions", json=expense(description="Gizli"))

    listed = client.get("/api/v1/transactions", params=wide_range())

    assert listed.json()["data"] == []


def test_one_account_cannot_delete_anothers_entries(
    client: TestClient,
    other_client: TestClient,
    account: Account,
    other_account: Account,
) -> None:
    theirs = other_client.post("/api/v1/transactions", json=expense()).json()["data"]

    response = client.delete(f"/api/v1/transactions/{theirs['id']}")

    assert response.status_code == 404
    assert len(other_client.get("/api/v1/transactions", params=wide_range()).json()["data"]) == 1


def test_the_balance_starts_at_nothing(client: TestClient, account: Account) -> None:
    response = client.get("/api/v1/balance")

    assert response.status_code == 200
    assert response.json()["data"] == {
        "current_balance_minor": 0,
        "opening_balance_minor": 0,
        "total_income_minor": 0,
        "total_expense_minor": 0,
    }


def test_the_balance_is_income_less_expense(
    client: TestClient,
    account: Account,
) -> None:
    client.post("/api/v1/transactions", json=income())
    client.post("/api/v1/transactions", json=expense())

    body = client.get("/api/v1/balance").json()["data"]

    assert body["total_income_minor"] == 100_000
    assert body["total_expense_minor"] == 5_000
    assert body["current_balance_minor"] == 95_000


def test_the_opening_amount_is_added_to_the_balance(
    client: TestClient,
    account: Account,
) -> None:
    client.put("/api/v1/balance/opening", json={"amount": "250.00"})
    client.post("/api/v1/transactions", json=expense())

    body = client.get("/api/v1/balance").json()["data"]

    assert body["opening_balance_minor"] == 25_000
    assert body["current_balance_minor"] == 20_000


def test_the_opening_amount_may_be_negative(
    client: TestClient,
    account: Account,
) -> None:
    """Starting in the red is a real situation, not a typo."""
    response = client.put("/api/v1/balance/opening", json={"amount": "-100.00"})

    assert response.status_code == 200
    assert response.json()["data"]["current_balance_minor"] == -10_000


def test_deleting_an_entry_takes_it_back_out_of_the_balance(
    client: TestClient,
    account: Account,
) -> None:
    created = client.post("/api/v1/transactions", json=expense()).json()["data"]

    client.delete(f"/api/v1/transactions/{created['id']}")

    assert client.get("/api/v1/balance").json()["data"]["total_expense_minor"] == 0
