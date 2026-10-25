"""Database engine, session factory and the FastAPI dependency."""

from __future__ import annotations

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import settings


class Base(DeclarativeBase):
    """Base class every ORM model inherits from."""


connect_args = {"check_same_thread": False} if settings.is_sqlite else {}

engine = create_engine(
    settings.database_url,
    connect_args=connect_args,
    pool_pre_ping=True,   # drop dead connections instead of erroring on use
    echo=False,
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency: one session per request, always closed."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def create_all() -> None:
    """Create any missing tables.

    Fine for development and for this project. A production system would use
    Alembic migrations instead, so schema changes are versioned and reversible.
    """
    from app import models  # noqa: F401  - registers the models on Base

    Base.metadata.create_all(bind=engine)
