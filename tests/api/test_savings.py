"""POST /savings/process-month-end and PUT /savings/goal"""

import pytest
from fastapi.testclient import TestClient

from tests.api.conftest import (
    Account,
    FOOD_CATEGORY_ID,
    SALARY_CATEGORY_ID,
    first_of_previous_month,
    today,
)

pytestmark = pytest.mark.api


def entry(kind: str, amount: str, on_day: str) -> dict[str, str]:
    return {
        "category_id": SALARY_CATEGORY_ID if kind == "INCOME" else FOOD_CATEGORY_ID,
        "kind": kind,
        "amount": amount,
        "description": "Maaş" if kind == "INCOME" else "Market",
        "occurred_on": on_day,
    }


def test_a_new_account_has_nothing_saved_yet(
    client: TestClient,
    account: Account,
) -> None:
    response = client.post("/api/v1/savings/process-month-end")

    assert response.status_code == 200
    assert response.json()["data"] == {
        "total_saved_minor": 0,
        "current_month_projection_minor": 0,
        "goal_minor": 0,
        "entries": [],
    }


def test_a_finished_month_is_closed_and_kept(
    client: TestClient,
    account: Account,
) -> None:
    last_month = first_of_previous_month()
    client.post(
        "/api/v1/transactions",
        json=entry("INCOME", "1000.00", last_month.isoformat()),
    )

    body = client.post("/api/v1/savings/process-month-end").json()["data"]

    assert body["total_saved_minor"] == 100_000
    assert [(item["year"], item["month"]) for item in body["entries"]] == [
        (last_month.year, last_month.month)
    ]


def test_the_month_in_progress_is_only_a_projection(
    client: TestClient,
    account: Account,
) -> None:
    """It is not over yet, so writing it down would make a figure that still
    moves look like a settled one."""
    client.post(
        "/api/v1/transactions",
        json=entry("INCOME", "500.00", today().isoformat()),
    )

    body = client.post("/api/v1/savings/process-month-end").json()["data"]

    assert body["current_month_projection_minor"] == 50_000
    assert body["entries"] == []


def test_savings_never_fall_below_nothing(
    client: TestClient,
    account: Account,
) -> None:
    """There is no owing the piggy bank. A month that spent more than it
    earned can empty what was put aside, and no further."""
    last_month = first_of_previous_month()
    client.post(
        "/api/v1/transactions",
        json=entry("EXPENSE", "800.00", last_month.isoformat()),
    )

    body = client.post("/api/v1/savings/process-month-end").json()["data"]

    assert body["total_saved_minor"] == 0


def test_running_it_twice_does_not_double_the_total(
    client: TestClient,
    account: Account,
) -> None:
    """The savings screen calls this on every visit."""
    client.post(
        "/api/v1/transactions",
        json=entry("INCOME", "1000.00", first_of_previous_month().isoformat()),
    )
    client.post("/api/v1/savings/process-month-end")

    body = client.post("/api/v1/savings/process-month-end").json()["data"]

    assert body["total_saved_minor"] == 100_000
    assert len(body["entries"]) == 1


def test_the_goal_is_stored_and_read_back(
    client: TestClient,
    account: Account,
) -> None:
    response = client.put("/api/v1/savings/goal", json={"goal": "5000.00"})

    assert response.status_code == 200
    assert response.json()["data"]["goal_minor"] == 500_000
    assert client.post("/api/v1/savings/process-month-end").json()["data"]["goal_minor"] == 500_000


def test_a_goal_of_nothing_clears_it(client: TestClient, account: Account) -> None:
    client.put("/api/v1/savings/goal", json={"goal": "5000.00"})

    response = client.put("/api/v1/savings/goal", json={"goal": "0"})

    assert response.json()["data"]["goal_minor"] == 0


def test_a_negative_goal_is_refused(client: TestClient, account: Account) -> None:
    assert client.put("/api/v1/savings/goal", json={"goal": "-1.00"}).status_code == 422


def test_one_account_does_not_see_anothers_savings(
    client: TestClient,
    other_client: TestClient,
    account: Account,
    other_account: Account,
) -> None:
    other_client.post(
        "/api/v1/transactions",
        json=entry("INCOME", "1000.00", first_of_previous_month().isoformat()),
    )
    other_client.post("/api/v1/savings/process-month-end")

    body = client.post("/api/v1/savings/process-month-end").json()["data"]

    assert body["total_saved_minor"] == 0
