"""Recurring charges over HTTP."""

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from tests.api.conftest import (
    Account,
    FOOD_CATEGORY_ID,
    day_range,
    today,
    tomorrow,
    wide_range,
)

pytestmark = pytest.mark.api

SUBSCRIPTION_CATEGORY_ID = "20000000-0000-0000-0000-000000000003"


def subscription(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "category_id": SUBSCRIPTION_CATEGORY_ID,
        "name": "Müzik servisi",
        "amount": "60.00",
        "first_charge_date": today().isoformat(),
    }
    payload.update(overrides)
    return payload


def test_a_subscription_bills_on_the_day_it_starts(
    client: TestClient,
    account: Account,
) -> None:
    response = client.post("/api/v1/subscriptions", json=subscription())

    assert response.status_code == 201
    body = response.json()["data"]
    assert body["amount_minor"] == 6_000
    assert body["billing_day"] == today().day
    assert body["next_charge_date"] == today().isoformat()


def test_the_name_is_trimmed(client: TestClient, account: Account) -> None:
    response = client.post(
        "/api/v1/subscriptions",
        json=subscription(name="  Müzik servisi  "),
    )

    assert response.json()["data"]["name"] == "Müzik servisi"


def test_a_new_subscription_shows_up_in_the_list(
    client: TestClient,
    account: Account,
) -> None:
    client.post("/api/v1/subscriptions", json=subscription())

    listed = client.get("/api/v1/subscriptions")

    assert [item["name"] for item in listed.json()["data"]] == ["Müzik servisi"]


def test_an_unknown_category_is_refused(
    client: TestClient,
    account: Account,
) -> None:
    response = client.post(
        "/api/v1/subscriptions",
        json=subscription(category_id=str(uuid4())),
    )

    assert response.status_code == 404


def test_a_subscription_can_be_edited(client: TestClient, account: Account) -> None:
    created = client.post("/api/v1/subscriptions", json=subscription()).json()["data"]

    response = client.patch(
        f"/api/v1/subscriptions/{created['id']}",
        json={
            "category_id": FOOD_CATEGORY_ID,
            "name": "Yemek kutusu",
            "amount": "120.00",
            "billing_day": 5,
        },
    )

    assert response.status_code == 200
    assert response.json()["data"]["name"] == "Yemek kutusu"
    assert response.json()["data"]["amount_minor"] == 12_000
    assert response.json()["data"]["billing_day"] == 5


@pytest.mark.parametrize("billing_day", [0, 32])
def test_a_billing_day_outside_the_month_is_refused(
    client: TestClient,
    account: Account,
    billing_day: int,
) -> None:
    created = client.post("/api/v1/subscriptions", json=subscription()).json()["data"]

    response = client.patch(
        f"/api/v1/subscriptions/{created['id']}",
        json={
            "category_id": SUBSCRIPTION_CATEGORY_ID,
            "name": "Müzik servisi",
            "amount": "60.00",
            "billing_day": billing_day,
        },
    )

    assert response.status_code == 422


def test_editing_a_subscription_that_is_not_there_is_reported(
    client: TestClient,
    account: Account,
) -> None:
    response = client.patch(
        f"/api/v1/subscriptions/{uuid4()}",
        json={
            "category_id": SUBSCRIPTION_CATEGORY_ID,
            "name": "Müzik servisi",
            "amount": "60.00",
            "billing_day": 5,
        },
    )

    assert response.status_code == 404


def test_a_subscription_can_be_cancelled(
    client: TestClient,
    account: Account,
) -> None:
    created = client.post("/api/v1/subscriptions", json=subscription()).json()["data"]

    response = client.delete(f"/api/v1/subscriptions/{created['id']}")

    assert response.status_code == 200
    assert client.get("/api/v1/subscriptions").json()["data"] == []


def test_cancelling_one_that_is_not_there_is_reported(
    client: TestClient,
    account: Account,
) -> None:
    assert client.delete(f"/api/v1/subscriptions/{uuid4()}").status_code == 404


def test_a_due_charge_becomes_a_real_entry(
    client: TestClient,
    account: Account,
) -> None:
    client.post("/api/v1/subscriptions", json=subscription())

    posted = client.post("/api/v1/subscriptions/process-due")

    assert posted.status_code == 200
    assert [item["description"] for item in posted.json()["data"]] == ["Müzik servisi"]
    assert client.get("/api/v1/balance").json()["data"]["total_expense_minor"] == 6_000


def test_the_posted_charge_carries_its_date(
    client: TestClient,
    account: Account,
) -> None:
    client.post("/api/v1/subscriptions", json=subscription())

    posted = client.post("/api/v1/subscriptions/process-due").json()["data"]

    assert posted[0]["subscription_charge_date"] == today().isoformat()


def test_running_it_again_posts_nothing(
    client: TestClient,
    account: Account,
) -> None:
    """The hourly scheduler and this endpoint both reach the same code, so
    posting twice has to be impossible rather than unlikely."""
    client.post("/api/v1/subscriptions", json=subscription())
    client.post("/api/v1/subscriptions/process-due")

    second = client.post("/api/v1/subscriptions/process-due")

    assert second.json()["data"] == []
    assert len(client.get("/api/v1/transactions", params=day_range()).json()["data"]) == 1


def test_a_subscription_that_is_not_due_posts_nothing(
    client: TestClient,
    account: Account,
) -> None:
    client.post(
        "/api/v1/subscriptions",
        json=subscription(first_charge_date=tomorrow().isoformat()),
    )

    assert client.post("/api/v1/subscriptions/process-due").json()["data"] == []


def test_a_cancelled_subscription_stops_being_charged(
    client: TestClient,
    account: Account,
) -> None:
    created = client.post("/api/v1/subscriptions", json=subscription()).json()["data"]
    client.delete(f"/api/v1/subscriptions/{created['id']}")

    assert client.post("/api/v1/subscriptions/process-due").json()["data"] == []


def test_one_account_cannot_see_anothers_subscriptions(
    client: TestClient,
    other_client: TestClient,
    account: Account,
    other_account: Account,
) -> None:
    other_client.post("/api/v1/subscriptions", json=subscription(name="Gizli"))

    assert client.get("/api/v1/subscriptions").json()["data"] == []


def test_one_account_cannot_cancel_anothers_subscription(
    client: TestClient,
    other_client: TestClient,
    account: Account,
    other_account: Account,
) -> None:
    theirs = other_client.post("/api/v1/subscriptions", json=subscription()).json()["data"]

    response = client.delete(f"/api/v1/subscriptions/{theirs['id']}")

    assert response.status_code == 404
    assert len(other_client.get("/api/v1/subscriptions").json()["data"]) == 1


def test_processing_charges_only_the_account_that_asked(
    client: TestClient,
    other_client: TestClient,
    account: Account,
    other_account: Account,
) -> None:
    other_client.post("/api/v1/subscriptions", json=subscription())

    assert client.post("/api/v1/subscriptions/process-due").json()["data"] == []
    assert other_client.get("/api/v1/transactions", params=wide_range()).json()["data"] == []
