"""PATCH /api/v1/auth/me"""

import pytest
from fastapi.testclient import TestClient

from tests.api.conftest import Account

pytestmark = pytest.mark.api

SETTINGS = {
    "display_name": "Ahmet Faruk",
    "daily_summary_enabled": False,
    "daily_summary_time": "08:30:00",
    "budget_alerts_enabled": False,
}


def test_settings_are_saved_and_read_back(
    client: TestClient,
    account: Account,
) -> None:
    response = client.patch("/api/v1/auth/me", json=SETTINGS)

    assert response.status_code == 200
    assert response.json()["display_name"] == "Ahmet Faruk"
    assert response.json()["daily_summary_time"] == "08:30:00"
    assert client.get("/api/v1/auth/me").json()["budget_alerts_enabled"] is False


def test_the_display_name_is_trimmed(client: TestClient, account: Account) -> None:
    response = client.patch(
        "/api/v1/auth/me",
        json={**SETTINGS, "display_name": "  Ahmet Faruk  "},
    )

    assert response.json()["display_name"] == "Ahmet Faruk"


def test_a_one_letter_display_name_is_refused(
    client: TestClient,
    account: Account,
) -> None:
    response = client.patch("/api/v1/auth/me", json={**SETTINGS, "display_name": "A"})

    assert response.status_code == 422


def test_a_time_that_is_not_a_time_is_refused(
    client: TestClient,
    account: Account,
) -> None:
    response = client.patch(
        "/api/v1/auth/me",
        json={**SETTINGS, "daily_summary_time": "yirmi bir"},
    )

    assert response.status_code == 422


def test_settings_cannot_be_changed_without_a_session(client: TestClient) -> None:
    assert client.patch("/api/v1/auth/me", json=SETTINGS).status_code == 401
