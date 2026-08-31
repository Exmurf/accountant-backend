"""The endpoint the container's health check calls."""

import pytest
from fastapi.testclient import TestClient

pytestmark = pytest.mark.api


def test_health_answers_without_a_session(client: TestClient) -> None:
    response = client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json()["data"] == {"status": "ok", "service": "accountant-api"}
