"""Scaffold-level checks: the app boots, the DB seeds, the health endpoint responds."""

from __future__ import annotations

import os

# Use a throwaway DB file for tests so we never touch the real one.
os.environ["DATABASE_URL"] = "sqlite:///test_scaffold.db"

from fastapi.testclient import TestClient  # noqa: E402
from sqlmodel import select  # noqa: E402

from app import db, models  # noqa: E402
from app.main import app  # noqa: E402


def test_health_ok():
    with TestClient(app) as client:  # triggers lifespan -> init_db
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}


def test_categories_are_seeded():
    db.init_db()
    with db.get_session() as session:
        names = {c.name for c in session.exec(select(models.Category)).all()}
        assert {"Food", "Transport", "Bills"}.issubset(names)

        food = session.exec(
            select(models.Category).where(models.Category.name == "Food")
        ).one()
        sub_names = {
            s.name
            for s in session.exec(
                select(models.Subcategory).where(
                    models.Subcategory.category_id == food.id
                )
            ).all()
        }
        assert "Groceries" in sub_names


def test_seeding_is_idempotent():
    db.init_db()
    db.init_db()  # second call must not duplicate
    with db.get_session() as session:
        all_categories = session.exec(select(models.Category)).all()
        assert len(all_categories) == len(set(c.name for c in all_categories))
