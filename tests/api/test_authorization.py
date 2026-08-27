"""Every route, checked against the list of the ones that may be reached
without a session.

The point of the first test is completeness rather than behaviour: adding an
endpoint and forgetting to think about who may call it will fail here, because
the new route belongs to neither list.
"""

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.main import app
from tests.api.conftest import FOOD_CATEGORY_ID, day_range, today

pytestmark = pytest.mark.api

SOME_ID = str(uuid4())

# Reachable with no session at all, each for its own reason: the two ways in,
# the two halves of forgetting a password, the link that lands in a mailbox
# nobody is signed in on, leaving, and the container's health check.
PUBLIC = {
    ("POST", "/api/v1/auth/register"),
    ("POST", "/api/v1/auth/login"),
    ("POST", "/api/v1/auth/password/forgot"),
    ("POST", "/api/v1/auth/password/reset"),
    ("POST", "/api/v1/auth/email/confirm"),
    ("POST", "/api/v1/auth/logout"),
    ("GET", "/api/v1/health"),
}

TRANSACTION_BODY = {
    "category_id": FOOD_CATEGORY_ID,
    "kind": "EXPENSE",
    "amount": "50.00",
    "description": "Öğle yemeği",
    "occurred_on": today().isoformat(),
}

# Route template -> a request that actually reaches it.
GUARDED: dict[tuple[str, str], tuple[str, dict | None]] = {
    ("GET", "/api/v1/admin/users"): ("/api/v1/admin/users", None),
    ("GET", "/api/v1/admin/users/{user_id}/finance"): (
        f"/api/v1/admin/users/{SOME_ID}/finance",
        None,
    ),
    ("PATCH", "/api/v1/admin/users/{user_id}/status"): (
        f"/api/v1/admin/users/{SOME_ID}/status",
        {"is_active": False},
    ),
    ("POST", "/api/v1/auth/refresh"): ("/api/v1/auth/refresh", None),
    ("GET", "/api/v1/auth/me"): ("/api/v1/auth/me", None),
    ("PATCH", "/api/v1/auth/me"): (
        "/api/v1/auth/me",
        {
            "display_name": "Ahmet",
            "daily_summary_enabled": True,
            "daily_summary_time": "21:00:00",
            "budget_alerts_enabled": True,
        },
    ),
    ("PATCH", "/api/v1/auth/me/password"): (
        "/api/v1/auth/me/password",
        {"current_password": "parola123", "new_password": "yeniparola456"},
    ),
    ("POST", "/api/v1/auth/email/change"): (
        "/api/v1/auth/email/change",
        {"new_email": "yeni@mail.dev", "current_password": "parola123"},
    ),
    ("GET", "/api/v1/balance"): ("/api/v1/balance", None),
    ("PUT", "/api/v1/balance/opening"): (
        "/api/v1/balance/opening",
        {"amount": "100.00"},
    ),
    ("GET", "/api/v1/budgets"): ("/api/v1/budgets", None),
    ("PUT", "/api/v1/budgets/{category_id}"): (
        f"/api/v1/budgets/{FOOD_CATEGORY_ID}",
        {"limit": "1500.00"},
    ),
    ("PATCH", "/api/v1/budgets/{budget_id}"): (
        f"/api/v1/budgets/{SOME_ID}",
        {"limit": "1500.00", "category_id": FOOD_CATEGORY_ID},
    ),
    ("DELETE", "/api/v1/budgets/{category_id}"): (
        f"/api/v1/budgets/{FOOD_CATEGORY_ID}",
        None,
    ),
    ("GET", "/api/v1/categories"): ("/api/v1/categories", None),
    ("POST", "/api/v1/categories"): (
        "/api/v1/categories",
        {"name": "Kahve", "kind": "EXPENSE", "color": "#8c7ab8"},
    ),
    ("GET", "/api/v1/transactions"): (
        "/api/v1/transactions?" + "&".join(f"{k}={v}" for k, v in day_range().items()),
        None,
    ),
    ("POST", "/api/v1/transactions"): ("/api/v1/transactions", TRANSACTION_BODY),
    ("PATCH", "/api/v1/transactions/{transaction_id}"): (
        f"/api/v1/transactions/{SOME_ID}",
        TRANSACTION_BODY,
    ),
    ("DELETE", "/api/v1/transactions/{transaction_id}"): (
        f"/api/v1/transactions/{SOME_ID}",
        None,
    ),
    ("GET", "/api/v1/subscriptions"): ("/api/v1/subscriptions", None),
    ("POST", "/api/v1/subscriptions"): (
        "/api/v1/subscriptions",
        {
            "category_id": FOOD_CATEGORY_ID,
            "name": "Müzik servisi",
            "amount": "60.00",
            "first_charge_date": today().isoformat(),
        },
    ),
    ("PATCH", "/api/v1/subscriptions/{subscription_id}"): (
        f"/api/v1/subscriptions/{SOME_ID}",
        {
            "category_id": FOOD_CATEGORY_ID,
            "name": "Müzik servisi",
            "amount": "60.00",
            "billing_day": 5,
        },
    ),
    ("DELETE", "/api/v1/subscriptions/{subscription_id}"): (
        f"/api/v1/subscriptions/{SOME_ID}",
        None,
    ),
    ("POST", "/api/v1/subscriptions/process-due"): (
        "/api/v1/subscriptions/process-due",
        None,
    ),
    ("POST", "/api/v1/savings/process-month-end"): (
        "/api/v1/savings/process-month-end",
        None,
    ),
    ("PUT", "/api/v1/savings/goal"): ("/api/v1/savings/goal", {"goal": "5000.00"}),
}


def declared_routes() -> set[tuple[str, str]]:
    """Every route the application publishes.

    Read from the OpenAPI description rather than by walking `app.routes`:
    included routers are not flattened into that list, and the shape of what is
    there has changed between FastAPI versions.
    """
    return {
        (method.upper(), path)
        for path, operations in app.openapi()["paths"].items()
        for method in operations
    }


def test_every_route_is_accounted_for() -> None:
    """Neither list may drift from the application.

    A new endpoint that appears in neither is not an oversight to catch in
    review; it is a failing test.
    """
    assert declared_routes() == PUBLIC | set(GUARDED)


@pytest.mark.parametrize(
    ("method", "template"),
    sorted(GUARDED),
    ids=lambda value: value if isinstance(value, str) else str(value),
)
def test_a_guarded_route_refuses_a_caller_with_no_session(
    client: TestClient,
    method: str,
    template: str,
) -> None:
    url, body = GUARDED[(method, template)]

    response = client.request(method, url, json=body)

    assert response.status_code == 401, f"{method} {template} -> {response.status_code}"


@pytest.mark.parametrize(
    ("method", "template"),
    sorted(key for key in GUARDED if key[1].startswith("/api/v1/admin")),
    ids=lambda value: value if isinstance(value, str) else str(value),
)
def test_an_administration_route_refuses_an_ordinary_session(
    client: TestClient,
    account,  # type: ignore[no-untyped-def]
    method: str,
    template: str,
) -> None:
    url, body = GUARDED[(method, template)]

    response = client.request(method, url, json=body)

    assert response.status_code == 403
