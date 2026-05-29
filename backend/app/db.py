"""Database engine, session helper, and one-time initialization/seeding."""

from __future__ import annotations

import os

from sqlmodel import Session, SQLModel, create_engine, select

from app import models

# Default categories seeded on first run. Each entry is (category, [subcategories]).
# Editable later via the API; this is just a sensible starting point.
DEFAULT_CATEGORIES: dict[str, list[str]] = {
    "Food": ["Restaurants", "Groceries", "Coffee", "Delivery"],
    "Transport": ["Transit", "Rideshare", "Gas", "Parking"],
    "Shopping": ["Clothing", "Electronics", "Household", "Other"],
    "Bills": ["Phone", "Internet", "Utilities", "Subscriptions"],
    "Entertainment": ["Streaming", "Events", "Games", "Hobbies"],
    "Health": ["Pharmacy", "Fitness", "Medical"],
    "Other": ["Uncategorized"],
}

DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///moneymoney.db")

engine = create_engine(DATABASE_URL, echo=False)


def get_session() -> Session:
    return Session(engine)


def init_db() -> None:
    """Create tables and seed default categories if the table is empty."""
    SQLModel.metadata.create_all(engine)
    with get_session() as session:
        existing = session.exec(select(models.Category)).first()
        if existing is None:
            _seed_categories(session)
            session.commit()


def _seed_categories(session: Session) -> None:
    for category_name, subcategory_names in DEFAULT_CATEGORIES.items():
        category = models.Category(name=category_name)
        session.add(category)
        session.flush()  # assigns category.id
        for sub_name in subcategory_names:
            session.add(
                models.Subcategory(name=sub_name, category_id=category.id)
            )
