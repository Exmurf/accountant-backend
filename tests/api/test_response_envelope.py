"""The response contract shared by every route under /api/v1."""

import pytest
from fastapi.testclient import TestClient
from httpx import Response

pytestmark = pytest.mark.api


def assert_envelope(response: Response, *, status: bool):
    body = response.json()
    assert set(body) == {"status", "data"}
    assert body["status"] is status
    return body["data"]


def test_a_successful_response_uses_the_shared_envelope(
    client: TestClient,
) -> None:
    response = client.get("/api/v1/health")

    assert response.status_code == 200
    assert assert_envelope(response, status=True) == {
        "status": "ok",
        "service": "accountant-api",
    }


def test_an_authentication_error_uses_the_shared_envelope(
    client: TestClient,
) -> None:
    response = client.get("/api/v1/auth/me")

    assert response.status_code == 401
    assert assert_envelope(response, status=False) == {
        "detail": "Oturum açmanız gerekiyor."
    }


def test_a_validation_error_uses_the_shared_envelope(
    client: TestClient,
) -> None:
    response = client.post("/api/v1/auth/register", json={})

    assert response.status_code == 422
    data = assert_envelope(response, status=False)
    assert isinstance(data["detail"], list)


def test_an_unknown_api_route_uses_the_shared_envelope(
    client: TestClient,
) -> None:
    response = client.get("/api/v1/does-not-exist")

    assert response.status_code == 404
    assert assert_envelope(response, status=False) == {"detail": "Not Found"}
