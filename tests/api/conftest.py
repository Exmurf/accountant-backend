"""Helpers for the tests that go through HTTP.

An account is created the way a person creates one — by calling the register
endpoint — rather than by writing rows. It costs one real Argon2 hash per test,
and buys a starting state that cannot drift away from what the application
actually produces.
"""

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from uuid import UUID
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.main import app

PASSWORD = "parola123"

# Seeded by migration 0003 and shared by every account, so a test can spend
# against a category without creating one first.
FOOD_CATEGORY_ID = "20000000-0000-0000-0000-000000000001"
SALARY_CATEGORY_ID = "10000000-0000-0000-0000-000000000001"

# The application files an entry at midday in this zone and cuts the balance off
# at local midnight, so a test that wants its entry counted has to agree.
ISTANBUL = ZoneInfo("Europe/Istanbul")


def today() -> date:
    return datetime.now(ISTANBUL).date()


def tomorrow() -> date:
    return today() + timedelta(days=1)


def first_of_previous_month() -> date:
    first_of_this_month = today().replace(day=1)
    return (first_of_this_month - timedelta(days=1)).replace(day=1)


def day_range(day: date | None = None) -> dict[str, str]:
    """The `start` and `end` query pair covering one whole local day."""
    start = datetime.combine(day or today(), time.min, tzinfo=ISTANBUL)
    return {
        "start": start.isoformat(),
        "end": (start + timedelta(days=1)).isoformat(),
    }


def wide_range() -> dict[str, str]:
    """A window around today wide enough to hold anything a test creates."""
    start = datetime.combine(today(), time.min, tzinfo=ISTANBUL) - timedelta(days=400)
    return {
        "start": start.isoformat(),
        "end": (start + timedelta(days=800)).isoformat(),
    }


@dataclass(frozen=True, slots=True)
class Account:
    id: UUID
    email: str
    display_name: str
    password: str = PASSWORD


def register(
    client: TestClient,
    email: str = "ahmet@mail.dev",
    display_name: str = "Ahmet",
    password: str = PASSWORD,
):  # type: ignore[no-untyped-def]
    return client.post(
        "/api/v1/auth/register",
        json={"email": email, "display_name": display_name, "password": password},
    )


def sign_in(
    client: TestClient,
    email: str = "ahmet@mail.dev",
    password: str = PASSWORD,
):  # type: ignore[no-untyped-def]
    return client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )


def plant_cookie(client: TestClient, name: str, value: str) -> None:
    """Make this the only cookie the client will send.

    The jar is emptied first on purpose. A cookie added next to the one the
    server set is a second entry rather than a replacement — the two differ in
    the domain the jar files them under — and both would go out together, which
    is not a state any browser can be in.
    """
    client.cookies.clear()
    client.cookies.set(name, value)


def cleared_cookies(response) -> set[str]:  # type: ignore[no-untyped-def]
    """The cookie names a response tells the browser to drop."""
    return {
        header.split("=", 1)[0]
        for header in response.headers.get_list("set-cookie")
        if "Max-Age=0" in header
    }


@pytest.fixture
def account(client: TestClient) -> Account:
    """A registered user, with the client already holding its session."""
    response = register(client)
    assert response.status_code == 201, response.text
    body = response.json()
    return Account(
        id=UUID(body["id"]),
        email=body["email"],
        display_name=body["display_name"],
    )


@pytest.fixture
def other_client(client: TestClient) -> TestClient:
    """A second browser, for checking that one account cannot read another.

    It depends on `client` rather than on the session directly: the overrides
    that point the application at the test database and at a fresh rate limiter
    are installed by that fixture, and a client built without them would be
    talking to a different application than the first one. Only the cookie jar
    is separate.
    """
    return TestClient(app)


@pytest.fixture
def other_account(other_client: TestClient) -> Account:
    response = register(
        other_client,
        email="baskasi@mail.dev",
        display_name="Başkası",
    )
    assert response.status_code == 201, response.text
    body = response.json()
    return Account(
        id=UUID(body["id"]),
        email=body["email"],
        display_name=body["display_name"],
    )


@pytest.fixture
def admin(client: TestClient, db_session: Session, account: Account) -> Account:
    """The account, promoted the only way the application allows: by hand.

    There is no endpoint and no setting that grants ADMIN, which is deliberate,
    so the test does what an operator would do at the database prompt.
    """
    db_session.execute(
        text(
            "INSERT INTO user_roles (user_id, role_id) "
            "SELECT :user_id, id FROM roles WHERE name = 'ADMIN'"
        ),
        {"user_id": account.id},
    )
    db_session.commit()
    # The session already handed this user out once, so its loaded roles have
    # to be dropped or the next request would answer from the old copy.
    db_session.expire_all()
    return account
