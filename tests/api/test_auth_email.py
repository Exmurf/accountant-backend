"""POST /auth/email/change and POST /auth/email/confirm"""

import pytest
from fastapi.testclient import TestClient

from tests.api.conftest import Account, PASSWORD, register, sign_in
from tests.api.test_auth_password import token_from
from tests.fakes import SentMail

pytestmark = pytest.mark.api

NEW_EMAIL = "yeni@mail.dev"


def ask_to_move(
    client: TestClient,
    new_email: str = NEW_EMAIL,
    current_password: str = PASSWORD,
):  # type: ignore[no-untyped-def]
    return client.post(
        "/api/v1/auth/email/change",
        json={"new_email": new_email, "current_password": current_password},
    )


def confirmation_for(outbox: list[SentMail], recipient: str) -> SentMail:
    return next(mail for mail in outbox if mail.recipient == recipient)


def test_without_a_configured_sender_the_flow_is_closed(
    client: TestClient,
    account: Account,
) -> None:
    """The whole thing turns on a link arriving somewhere, so there is nothing
    useful to do here without a sender."""
    response = ask_to_move(client)

    assert response.status_code == 503


def test_asking_sends_the_link_to_the_address_being_claimed(
    client: TestClient,
    account: Account,
    mail_enabled: None,
    outbox: list[SentMail],
) -> None:
    response = ask_to_move(client)

    assert response.status_code == 202
    confirmation = confirmation_for(outbox, NEW_EMAIL)
    assert confirmation.message.action is not None


def test_the_old_address_is_warned_but_given_no_link(
    client: TestClient,
    account: Account,
    mail_enabled: None,
    outbox: list[SentMail],
) -> None:
    ask_to_move(client)

    warning = confirmation_for(outbox, account.email)
    assert warning.message.action is None
    assert NEW_EMAIL in " ".join(warning.message.paragraphs)


def test_nothing_changes_until_the_link_is_followed(
    client: TestClient,
    account: Account,
    mail_enabled: None,
    outbox: list[SentMail],
) -> None:
    ask_to_move(client)

    assert client.get("/api/v1/auth/me").json()["data"]["email"] == account.email


def test_following_the_link_moves_the_account(
    client: TestClient,
    account: Account,
    mail_enabled: None,
    outbox: list[SentMail],
) -> None:
    ask_to_move(client)
    token = token_from(confirmation_for(outbox, NEW_EMAIL), "email_token")

    response = client.post("/api/v1/auth/email/confirm", json={"token": token})

    assert response.status_code == 200
    assert response.json()["data"]["email"] == NEW_EMAIL


def test_after_moving_the_new_address_is_the_one_that_signs_in(
    client: TestClient,
    account: Account,
    mail_enabled: None,
    outbox: list[SentMail],
) -> None:
    ask_to_move(client)
    token = token_from(confirmation_for(outbox, NEW_EMAIL), "email_token")
    client.post("/api/v1/auth/email/confirm", json={"token": token})

    client.cookies.clear()
    assert sign_in(client, email=NEW_EMAIL).status_code == 200
    assert sign_in(client, email=account.email).status_code == 401


def test_the_session_survives_the_move(
    client: TestClient,
    account: Account,
    mail_enabled: None,
    outbox: list[SentMail],
) -> None:
    """The password was proved when the change was asked for, so there is
    nothing here to suggest the account is in the wrong hands."""
    ask_to_move(client)
    token = token_from(confirmation_for(outbox, NEW_EMAIL), "email_token")

    client.post("/api/v1/auth/email/confirm", json={"token": token})

    assert client.get("/api/v1/auth/me").status_code == 200


def test_the_link_works_only_once(
    client: TestClient,
    account: Account,
    mail_enabled: None,
    outbox: list[SentMail],
) -> None:
    ask_to_move(client)
    token = token_from(confirmation_for(outbox, NEW_EMAIL), "email_token")

    client.post("/api/v1/auth/email/confirm", json={"token": token})
    second = client.post("/api/v1/auth/email/confirm", json={"token": token})

    assert second.status_code == 400


def test_a_made_up_link_is_refused(client: TestClient, account: Account) -> None:
    response = client.post("/api/v1/auth/email/confirm", json={"token": "a" * 40})

    assert response.status_code == 400


def test_a_wrong_password_stops_the_request(
    client: TestClient,
    account: Account,
    mail_enabled: None,
    outbox: list[SentMail],
) -> None:
    """A session cookie is not enough. Mail is the recovery channel, so letting
    a stolen session repoint it would make the takeover permanent."""
    response = ask_to_move(client, current_password="yanlisparola")

    assert response.status_code == 422
    assert outbox == []


def test_moving_to_the_current_address_is_refused(
    client: TestClient,
    account: Account,
    mail_enabled: None,
    outbox: list[SentMail],
) -> None:
    response = ask_to_move(client, new_email=account.email)

    assert response.status_code == 422
    assert response.json()["data"]["detail"] == "Bu zaten mevcut e-posta adresin."


def test_an_address_no_mail_can_reach_is_refused(
    client: TestClient,
    account: Account,
    mail_enabled: None,
    outbox: list[SentMail],
) -> None:
    response = ask_to_move(client, new_email="yeni@example.com")

    assert response.status_code == 422
    assert outbox == []


def test_an_address_another_account_holds_is_refused(
    client: TestClient,
    other_client: TestClient,
    account: Account,
    mail_enabled: None,
    outbox: list[SentMail],
) -> None:
    register(other_client, email=NEW_EMAIL, display_name="Başkası")

    response = ask_to_move(client)

    assert response.status_code == 409


def test_an_address_taken_while_the_mail_sat_unread_is_refused(
    client: TestClient,
    other_client: TestClient,
    account: Account,
    mail_enabled: None,
    outbox: list[SentMail],
) -> None:
    """It was free when the link went out. The only thing that settles it is
    the state at the moment of the write."""
    ask_to_move(client)
    token = token_from(confirmation_for(outbox, NEW_EMAIL), "email_token")
    register(other_client, email=NEW_EMAIL, display_name="Başkası")

    response = client.post("/api/v1/auth/email/confirm", json={"token": token})

    assert response.status_code == 409


def test_asking_too_often_is_refused(
    client: TestClient,
    account: Account,
    mail_enabled: None,
    outbox: list[SentMail],
) -> None:
    for index in range(3):
        ask_to_move(client, new_email=f"yeni{index}@mail.dev")

    locked = ask_to_move(client, new_email="yeni9@mail.dev")

    assert locked.status_code == 429
