"""Database models for MoneyMoney.

The schema captures four ideas:
- `Category` / `Subcategory`: the fixed-but-editable buckets used for analysis.
- `Transaction`: one purchase, parsed from a bank email (or entered manually).
- `MerchantRule`: maps a merchant text pattern to a category/subcategory. This powers
  auto-categorization and grows as the user corrects transactions.
- `ProcessedEmail`: remembers which emails we've already ingested so a transaction is
  never recorded twice.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import Enum

from sqlalchemy import Column, Numeric
from sqlmodel import Field, SQLModel


class TransactionStatus(str, Enum):
    """Where a transaction sits in the review lifecycle."""

    auto = "auto"  # categorized automatically by a merchant rule
    needs_review = "needs_review"  # parsed, but no confident category yet
    confirmed = "confirmed"  # the user has reviewed/corrected it


class Category(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(index=True, unique=True)


class Subcategory(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(index=True)
    category_id: int = Field(foreign_key="category.id", index=True)


class MerchantRule(SQLModel, table=True):
    """If `pattern` is found in a transaction's raw_merchant, apply this category."""

    id: int | None = Field(default=None, primary_key=True)
    pattern: str = Field(index=True)  # matched case-insensitively as a substring
    category_id: int = Field(foreign_key="category.id")
    subcategory_id: int | None = Field(default=None, foreign_key="subcategory.id")
    created_at: datetime = Field(default_factory=datetime.utcnow)


class Transaction(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    date: datetime = Field(index=True)
    amount: Decimal = Field(sa_column=Column(Numeric(12, 2)))
    currency: str = Field(default="CAD")
    raw_merchant: str = Field(default="")
    source: str = Field(index=True)  # "rbc" | "scotia"
    category_id: int | None = Field(default=None, foreign_key="category.id")
    subcategory_id: int | None = Field(default=None, foreign_key="subcategory.id")
    note: str | None = Field(default=None)
    status: TransactionStatus = Field(default=TransactionStatus.needs_review, index=True)
    raw_email_id: str | None = Field(default=None)
    created_at: datetime = Field(default_factory=datetime.utcnow)


class ProcessedEmail(SQLModel, table=True):
    """One row per ingested email, keyed by a stable per-mailbox identifier."""

    id: int | None = Field(default=None, primary_key=True)
    email_uid: str = Field(index=True, unique=True)
    processed_at: datetime = Field(default_factory=datetime.utcnow)
