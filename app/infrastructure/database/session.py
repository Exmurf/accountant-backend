from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings

# Imported for the side effect of attaching the cache listeners: a session
# created anywhere has to be watched, not only the ones a route builds.
import app.infrastructure.database.events  # noqa: E402,F401  isort:skip

settings = get_settings()

engine = create_engine(settings.database_url, pool_pre_ping=True)
session_factory = sessionmaker(
    bind=engine,
    autoflush=False,
    expire_on_commit=False,
    class_=Session,
)


def get_database_session() -> Generator[Session, None, None]:
    session = session_factory()
    try:
        yield session
    finally:
        session.close()
