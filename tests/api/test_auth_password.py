"""Changing a password, and getting back in after forgetting one."""

from urllib.parse import parse_qs, urlparse

import pytest
from fastapi.testclient import TestClient

from tests.api.conftest import Account, PASSWORD, sign_in
from tests.fakes import SentMail

pytestmark = pytest.mark.api

NEW_PASSWORD = "yeniparola456"


def token_from(mail: SentMail, parameter: str) -> str:
    query = parse_qs(urlparse(mail.message.action.url).query)
    return query[parameter][0]


def test_the_password_can_be_changed_from_inside_a_session(
    client: TestClient,
    account: Account,
) -> None:
    response = client.patch(
        "/api/v1/auth/me/password",
        json={"current_password": PASSWORD, "new_password": NEW_PASSWORD},
    )

    assert response.status_code == 200
    client.cookies.clear()
    assert sign_in(client, password=NEW_PASSWORD).status_code == 200


def test_the_old_password_stops_working(
    client: TestClient,
    account: Account,
) -> None:
    client.patch(
        "/api/v1/auth/me/password",
        json={"current_password": PASSWORD, "new_password": NEW_PASSWORD},
    )

    client.cookies.clear()
    assert sign_in(client, password=PASSWORD).status_code == 401


def test_the_session_that_made_the_change_keeps_working(
    client: TestClient,
    account: Account,
) -> None:
    """Every refresh token was just revoked, so this one needs replacing before
    the response goes out — otherwise changing a password would sign you out of
    the browser you did it in."""
    client.patch(
        "/api/v1/auth/me/password",
        json={"current_password": PASSWORD, "new_password": NEW_PASSWORD},
    )

    assert client.get("/api/v1/auth/me").status_code == 200
    assert client.post("/api/v1/auth/refresh").status_code == 200


def test_another_browser_is_signed_out(
    client: TestClient,
    other_client: TestClient,
    account: Account,
) -> None:
    """The usual reason to change a password is that somebody else knows it."""
    assert sign_in(other_client).status_code == 200

    client.patch(
        "/api/v1/auth/me/password",
        json={"current_password": PASSWORD, "new_password": NEW_PASSWORD},
    )

    assert other_client.post("/api/v1/auth/refresh").status_code == 401


def test_a_wrong_current_password_is_refused(
    client: TestClient,
    account: Account,
) -> None:
    response = client.patch(
        "/api/v1/auth/me/password",
        json={"current_password": "yanlisparola", "new_password": NEW_PASSWORD},
    )

    assert response.status_code == 422
    assert response.json()["data"]["detail"] == "Mevcut şifren hatalı."


def test_the_new_password_has_to_be_different(
    client: TestClient,
    account: Account,
) -> None:
    response = client.patch(
        "/api/v1/auth/me/password",
        json={"current_password": PASSWORD, "new_password": PASSWORD},
    )

    assert response.status_code == 422
    assert response.json()["data"]["detail"] == "Yeni şifren mevcut şifrenden farklı olmalı."


def test_guessing_the_current_password_is_rate_limited(
    client: TestClient,
    account: Account,
) -> None:
    """Reaching this endpoint already needs a session, so it is keyed by
    account rather than by address."""
    for _ in range(5):
        client.patch(
            "/api/v1/auth/me/password",
            json={"current_password": "yanlisparola", "new_password": NEW_PASSWORD},
        )

    locked = client.patch(
        "/api/v1/auth/me/password",
        json={"current_password": PASSWORD, "new_password": NEW_PASSWORD},
    )

    assert locked.status_code == 429


def test_asking_for_a_reset_link_says_the_same_thing_either_way(
    client: TestClient,
    account: Account,
    mail_enabled: None,
    outbox: list[SentMail],
) -> None:
    """Registered or not, the reply is identical — and so is the work done
    before it, since all of it happens after the response."""
    registered = client.post(
        "/api/v1/auth/password/forgot",
        json={"email": account.email},
    )
    unknown = client.post(
        "/api/v1/auth/password/forgot",
        json={"email": "kimse@mail.dev"},
    )

    assert registered.status_code == 202
    assert unknown.status_code == 202
    assert registered.json()["data"] == unknown.json()["data"]


def test_only_a_registered_address_actually_gets_a_mail(
    client: TestClient,
    mail_enabled: None,
    outbox: list[SentMail],
) -> None:
    client.post("/api/v1/auth/password/forgot", json={"email": "kimse@mail.dev"})

    assert outbox == []


def test_the_link_sets_a_new_password(
    client: TestClient,
    account: Account,
    mail_enabled: None,
    outbox: list[SentMail],
) -> None:
    client.post("/api/v1/auth/password/forgot", json={"email": account.email})
    token = token_from(outbox[-1], "reset_token")

    response = client.post(
        "/api/v1/auth/password/reset",
        json={"token": token, "new_password": NEW_PASSWORD},
    )

    assert response.status_code == 200
    client.cookies.clear()
    assert sign_in(client, password=NEW_PASSWORD).status_code == 200


def test_the_link_does_not_sign_anybody_in(
    client: TestClient,
    account: Account,
    mail_enabled: None,
    outbox: list[SentMail],
) -> None:
    """Whoever follows it has proved they hold the mailbox, not that they are
    sitting at a device the owner trusts."""
    client.cookies.clear()
    client.post("/api/v1/auth/password/forgot", json={"email": account.email})
    token = token_from(outbox[-1], "reset_token")

    client.post(
        "/api/v1/auth/password/reset",
        json={"token": token, "new_password": NEW_PASSWORD},
    )

    assert client.get("/api/v1/auth/me").status_code == 401


def test_the_link_works_only_once(
    client: TestClient,
    account: Account,
    mail_enabled: None,
    outbox: list[SentMail],
) -> None:
    client.post("/api/v1/auth/password/forgot", json={"email": account.email})
    token = token_from(outbox[-1], "reset_token")
    payload = {"token": token, "new_password": NEW_PASSWORD}

    client.post("/api/v1/auth/password/reset", json=payload)
    second = client.post("/api/v1/auth/password/reset", json=payload)

    assert second.status_code == 400


def test_a_made_up_link_is_refused(client: TestClient, account: Account) -> None:
    response = client.post(
        "/api/v1/auth/password/reset",
        json={"token": "a" * 40, "new_password": NEW_PASSWORD},
    )

    assert response.status_code == 400


def test_a_reset_ends_every_open_session(
    client: TestClient,
    other_client: TestClient,
    account: Account,
    mail_enabled: None,
    outbox: list[SentMail],
) -> None:
    assert sign_in(other_client).status_code == 200
    client.post("/api/v1/auth/password/forgot", json={"email": account.email})
    token = token_from(outbox[-1], "reset_token")

    client.post(
        "/api/v1/auth/password/reset",
        json={"token": token, "new_password": NEW_PASSWORD},
    )

    assert other_client.post("/api/v1/auth/refresh").status_code == 401
    assert other_client.get("/api/v1/auth/me").status_code == 401


def test_asking_for_too_many_links_is_refused(
    client: TestClient,
    account: Account,
    mail_enabled: None,
    outbox: list[SentMail],
) -> None:
    for _ in range(3):
        client.post("/api/v1/auth/password/forgot", json={"email": account.email})

    locked = client.post(
        "/api/v1/auth/password/forgot",
        json={"email": account.email},
    )

    assert locked.status_code == 429
