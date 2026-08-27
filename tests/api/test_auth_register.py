"""POST /api/v1/auth/register"""

import pytest
from fastapi.testclient import TestClient

from tests.api.conftest import PASSWORD, register

pytestmark = pytest.mark.api


def test_registering_returns_the_new_account(client: TestClient) -> None:
    response = register(client)

    assert response.status_code == 201
    body = response.json()
    assert body["email"] == "ahmet@mail.dev"
    assert body["display_name"] == "Ahmet"
    assert body["roles"] == ["USER"]
    assert sorted(body["permissions"]) == ["finance.read.self", "finance.write.self"]


def test_registering_opens_a_session(client: TestClient) -> None:
    register(client)

    assert "accountant_access" in client.cookies
    assert "accountant_refresh" in client.cookies
    # Proof the cookies work, not just that they exist.
    assert client.get("/api/v1/auth/me").status_code == 200


def test_the_response_never_carries_the_password(client: TestClient) -> None:
    response = register(client)

    assert "password" not in response.text
    assert "password_hash" not in response.json()


def test_the_second_registration_of_one_address_is_refused(
    client: TestClient,
) -> None:
    register(client)

    response = register(client)

    assert response.status_code == 409
    assert response.json()["detail"] == "Bu e-posta adresi zaten kayıtlı."


def test_a_short_password_is_refused_before_anything_is_written(
    client: TestClient,
) -> None:
    response = register(client, password="kisa")

    assert response.status_code == 422
    assert sign_in_fails(client)


def test_a_malformed_address_is_refused(client: TestClient) -> None:
    response = register(client, email="bu-bir-adres-degil")

    assert response.status_code == 422


def test_a_one_letter_display_name_is_refused(client: TestClient) -> None:
    response = register(client, display_name="A")

    assert response.status_code == 422


def sign_in_fails(client: TestClient) -> bool:
    return (
        client.post(
            "/api/v1/auth/login",
            json={"email": "ahmet@mail.dev", "password": PASSWORD},
        ).status_code
        == 401
    )
