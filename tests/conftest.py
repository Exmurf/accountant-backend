"""Fixtures shared by the whole suite.

The environment is set at import time, before anything under `app` is imported.
That order is not a style choice: `app.infrastructure.database.session` builds
its engine while it is being imported, and `get_settings` caches its answer for
the life of the process, so by the time a fixture runs it is already too late to
change either one.
"""

import os
from collections.abc import Iterator
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

ROOT = Path(__file__).resolve().parents[1]

# Matches the development stack. Overridden by DATABASE_URL inside the
# container, where PostgreSQL answers to a different host name.
FALLBACK_DATABASE_URL = (
    "postgresql+psycopg://accountant:accountant_dev_password"
    "@localhost:5432/accountant"
)


def _resolve_test_database_url() -> str:
    """A database of its own, named after the one the application uses."""
    explicit = os.environ.get("TEST_DATABASE_URL")
    if explicit:
        return explicit
    url = make_url(os.environ.get("DATABASE_URL") or FALLBACK_DATABASE_URL)
    return url.set(database=f"{url.database}_test").render_as_string(
        hide_password=False
    )


TEST_DATABASE_URL = _resolve_test_database_url()

# Every API test empties every table, so pointing the suite at a database that
# holds real money records would destroy them. The suffix is the guard, and it
# is checked before anything can connect.
if not (make_url(TEST_DATABASE_URL).database or "").endswith("_test"):
    raise RuntimeError(
        f"Refusing to run: {make_url(TEST_DATABASE_URL).database!r} is not a "
        "test database. Name it with a _test suffix or set TEST_DATABASE_URL."
    )

os.environ["DATABASE_URL"] = TEST_DATABASE_URL
os.environ["JWT_SECRET_KEY"] = "test-only-secret-not-used-anywhere-else"
os.environ["WEB_ORIGIN"] = "http://localhost:3000"
os.environ["COOKIE_SECURE"] = "false"
os.environ["APP_TIMEZONE"] = "Europe/Istanbul"
os.environ["TRUSTED_PROXY_IPS"] = ""
# No cache, so a stale entry can never be mistaken for a wrong query.
os.environ["REDIS_URL"] = ""
# Emptied deliberately: the developer's own .env carries a working Gmail app
# password, and nothing in a test run may be able to reach a real mailbox.
os.environ["MAIL_USERNAME"] = ""
os.environ["MAIL_APP_PASSWORD"] = ""
os.environ["RATE_LIMIT_ENABLED"] = "true"

# Imported below the environment on purpose; see the module docstring.
from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.core.config import get_settings  # noqa: E402
from app.infrastructure.database.session import (  # noqa: E402
    engine,
    get_database_session,
    session_factory,
)
from app.infrastructure.mail.smtp import SmtpMailSender  # noqa: E402
from app.infrastructure.security.rate_limit import InMemoryRateLimiter  # noqa: E402
from app.main import app  # noqa: E402
from app.presentation.dependencies.rate_limit import get_rate_limiter  # noqa: E402

from tests.fakes import SentMail  # noqa: E402

# Emptied between tests, children before parents. `TRUNCATE ... CASCADE` would
# be shorter but would also take the seeded default categories with it, since
# they hang off the same nullable column that a user's own categories do.
TABLES_TO_EMPTY = (
    "notification_deliveries",
    "monthly_savings",
    "monthly_budgets",
    "transactions",
    "subscriptions",
    "email_change_tokens",
    "password_reset_tokens",
    "refresh_tokens",
    "user_roles",
)


def _create_database_if_missing() -> None:
    url = make_url(TEST_DATABASE_URL)
    admin = create_engine(
        url.set(database="postgres"),
        isolation_level="AUTOCOMMIT",
    )
    try:
        with admin.connect() as connection:
            exists = connection.scalar(
                text("SELECT 1 FROM pg_database WHERE datname = :name"),
                {"name": url.database},
            )
            if not exists:
                # The name comes from configuration, never from a test, and
                # quoting it keeps a hyphenated database name working.
                connection.execute(text(f'CREATE DATABASE "{url.database}"'))
    finally:
        admin.dispose()


def _empty_tables() -> None:
    with engine.begin() as connection:
        for table in TABLES_TO_EMPTY:
            connection.execute(text(f"DELETE FROM {table}"))
        connection.execute(text("DELETE FROM categories WHERE user_id IS NOT NULL"))
        connection.execute(text("DELETE FROM users"))


@pytest.fixture(scope="session")
def database() -> None:
    """The schema, built the same way production builds it.

    Running the migrations rather than `create_all` means the tests exercise the
    tables the application will actually meet, seed rows included: without the
    roles that 0001 inserts, registering a user raises instead of working.
    """
    _create_database_if_missing()
    config = Config(str(ROOT / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", TEST_DATABASE_URL)
    command.upgrade(config, "head")


@pytest.fixture
def db_session(database: None) -> Iterator[Session]:
    """One session shared by the test and the request it makes.

    Sharing it is what lets a test read back what an endpoint wrote without
    caring when the repository committed.
    """
    _empty_tables()
    session = session_factory()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def limiter() -> InMemoryRateLimiter:
    """A window of its own per test.

    The application holds one limiter for the life of the process. Reusing it
    here would let a test that spends the register quota fail the next test that
    happens to register a user.
    """
    return InMemoryRateLimiter()


@pytest.fixture
def client(
    db_session: Session,
    limiter: InMemoryRateLimiter,
) -> Iterator[TestClient]:
    app.dependency_overrides[get_database_session] = lambda: db_session
    app.dependency_overrides[get_rate_limiter] = lambda: limiter
    # Deliberately not entered as a context manager: that would run the
    # lifespan, and the lifespan starts the subscription and notification
    # schedulers, which would then post charges under every test in the file.
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


@pytest.fixture
def outbox(monkeypatch: pytest.MonkeyPatch) -> list[SentMail]:
    """Every mail the application tries to send, captured instead of sent.

    Patched on the class rather than at each import site, so it covers the
    senders built inside background tasks too.
    """
    sent: list[SentMail] = []

    def record(_self: SmtpMailSender, recipient: str, subject: str, message) -> None:  # type: ignore[no-untyped-def]
        sent.append(SentMail(recipient=recipient, subject=subject, message=message))

    monkeypatch.setattr(SmtpMailSender, "send", record)
    return sent


@pytest.fixture
def mail_enabled(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Turn the mail-dependent flows on for one test.

    Nothing leaves the process even so: `outbox` is what stops the send, and
    every test that uses this fixture asks for it too.
    """
    monkeypatch.setenv("MAIL_USERNAME", "accountant@mail.dev")
    monkeypatch.setenv("MAIL_APP_PASSWORD", "not-a-real-password")
    get_settings.cache_clear()
    try:
        yield
    finally:
        get_settings.cache_clear()
