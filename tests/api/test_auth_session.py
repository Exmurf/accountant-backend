"""GET /auth/me, POST /auth/refresh, POST /auth/logout"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from tests.api.conftest import Account, cleared_cookies, plant_cookie

pytestmark = pytest.mark.api


def test_me_describes_the_signed_in_account(
    client: TestClient,
    account: Account,
) -> None:
    response = client.get("/api/v1/auth/me")

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == str(account.id)
    assert body["email"] == account.email
    assert "password_hash" not in body


def test_me_without_a_session_is_refused(client: TestClient) -> None:
    response = client.get("/api/v1/auth/me")

    assert response.status_code == 401
    assert response.json()["detail"] == "Oturum açmanız gerekiyor."


def test_a_cookie_that_is_not_a_token_is_refused(client: TestClient) -> None:
    plant_cookie(client, "accountant_access", "bu-bir-jeton-degil")

    assert client.get("/api/v1/auth/me").status_code == 401


def test_refreshing_hands_out_a_new_pair(
    client: TestClient,
    account: Account,
) -> None:
    before = client.cookies["accountant_refresh"]

    response = client.post("/api/v1/auth/refresh")

    assert response.status_code == 200
    assert client.cookies["accountant_refresh"] != before
    assert client.get("/api/v1/auth/me").status_code == 200


def test_the_previous_refresh_token_stops_working(
    client: TestClient,
    account: Account,
) -> None:
    """Rotation is what limits the damage of a stolen token: the moment the
    real owner refreshes, the copy is spent."""
    stolen = client.cookies["accountant_refresh"]
    client.post("/api/v1/auth/refresh")

    plant_cookie(client, "accountant_refresh", stolen)
    response = client.post("/api/v1/auth/refresh")

    assert response.status_code == 401


def test_refreshing_without_a_cookie_is_refused(client: TestClient) -> None:
    response = client.post("/api/v1/auth/refresh")

    assert response.status_code == 401


def test_a_refused_refresh_tells_the_browser_to_drop_both_cookies(
    client: TestClient,
) -> None:
    """The browser is holding something that will never work again, so leaving
    it there would only produce the same failure on every later request."""
    plant_cookie(client, "accountant_refresh", "uydurma-bir-jeton")

    response = client.post("/api/v1/auth/refresh")

    assert response.status_code == 401
    assert cleared_cookies(response) == {"accountant_access", "accountant_refresh"}


def test_a_deactivated_account_cannot_refresh(
    client: TestClient,
    db_session: Session,
    account: Account,
) -> None:
    db_session.execute(
        text("UPDATE users SET is_active = false WHERE id = :id"),
        {"id": account.id},
    )
    db_session.commit()

    assert client.post("/api/v1/auth/refresh").status_code == 401


def test_signing_out_clears_the_cookies(
    client: TestClient,
    account: Account,
) -> None:
    response = client.post("/api/v1/auth/logout")

    assert response.status_code == 200
    assert client.cookies.get("accountant_access") is None
    assert client.cookies.get("accountant_refresh") is None


def test_signing_out_ends_the_session_on_the_server_too(
    client: TestClient,
    account: Account,
) -> None:
    """Clearing the cookie only settles the browser in front of us. The token
    itself has to be spent, or a copy of it would still work."""
    refresh_token = client.cookies["accountant_refresh"]

    client.post("/api/v1/auth/logout")

    plant_cookie(client, "accountant_refresh", refresh_token)
    assert client.post("/api/v1/auth/refresh").status_code == 401


def test_signing_out_without_a_session_is_still_a_success(
    client: TestClient,
) -> None:
    """There is nothing to report to somebody who is already leaving."""
    assert client.post("/api/v1/auth/logout").status_code == 200
