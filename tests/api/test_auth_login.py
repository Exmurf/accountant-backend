"""POST /api/v1/auth/login"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from tests.api.conftest import Account, PASSWORD, sign_in

pytestmark = pytest.mark.api


def test_the_right_password_opens_a_session(
    client: TestClient,
    account: Account,
) -> None:
    client.cookies.clear()

    response = sign_in(client)

    assert response.status_code == 200
    assert response.json()["data"]["email"] == account.email
    assert client.get("/api/v1/auth/me").status_code == 200


def test_the_address_may_be_typed_in_any_case(
    client: TestClient,
    account: Account,
) -> None:
    client.cookies.clear()

    response = sign_in(client, email="AHMET@Mail.DEV")

    assert response.status_code == 200


def test_a_wrong_password_is_refused(client: TestClient, account: Account) -> None:
    response = sign_in(client, password="yanlisparola")

    assert response.status_code == 401
    assert response.json()["data"]["detail"] == "E-posta veya şifre hatalı."


def test_an_unknown_address_is_refused_the_same_way(client: TestClient) -> None:
    """Word for word the same as a wrong password, so the reply cannot be read
    as an answer to whether an account exists here."""
    response = sign_in(client, email="kimse@mail.dev")

    assert response.status_code == 401
    assert response.json()["data"]["detail"] == "E-posta veya şifre hatalı."


def test_a_deactivated_account_is_told_it_is_deactivated(
    client: TestClient,
    db_session: Session,
    account: Account,
) -> None:
    db_session.execute(
        text("UPDATE users SET is_active = false WHERE id = :id"),
        {"id": account.id},
    )
    db_session.commit()

    response = sign_in(client)

    assert response.status_code == 403
    assert response.json()["data"]["detail"] == "Kullanıcı hesabı devre dışı."


def test_repeated_wrong_passwords_lock_the_address(
    client: TestClient,
    account: Account,
) -> None:
    for _ in range(5):
        assert sign_in(client, password="yanlisparola").status_code == 401

    locked = sign_in(client, password="yanlisparola")

    assert locked.status_code == 429
    assert "Retry-After" in locked.headers


def test_the_lock_holds_even_against_the_right_password(
    client: TestClient,
    account: Account,
) -> None:
    """Otherwise the limit would only slow down somebody who never guesses
    correctly, which is not who it is for."""
    for _ in range(5):
        sign_in(client, password="yanlisparola")

    assert sign_in(client, password=PASSWORD).status_code == 429


def test_signing_in_clears_the_addresss_own_budget(
    client: TestClient,
    account: Account,
) -> None:
    for _ in range(4):
        sign_in(client, password="yanlisparola")

    assert sign_in(client).status_code == 200

    for _ in range(4):
        assert sign_in(client, password="yanlisparola").status_code == 401
