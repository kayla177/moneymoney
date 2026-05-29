"""Shared pytest fixtures.

Each test gets an isolated in-memory SQLite database seeded with the default categories,
so tests never touch the real DB and don't interfere with each other.
"""

from __future__ import annotations

import pytest
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from app import db, models  # noqa: F401  (import registers tables)


@pytest.fixture
def session() -> Session:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        db._seed_categories(s)
        s.commit()
        yield s
