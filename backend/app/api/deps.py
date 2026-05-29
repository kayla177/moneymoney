"""FastAPI dependencies. `get_db` yields a session against the app's engine and is
overridden in tests to point at an isolated database."""

from __future__ import annotations

from collections.abc import Iterator

from sqlmodel import Session

from app.db import engine


def get_db() -> Iterator[Session]:
    with Session(engine) as session:
        yield session
