"""Monthly spending analysis.

Aggregates a month's transactions into the numbers the analysis screen shows: total,
count, breakdown by category, top subcategories and merchants, per-day trend, and a
comparison against the previous month. All money is kept as Decimal.
"""

from __future__ import annotations

from calendar import monthrange
from collections import defaultdict
from datetime import datetime
from decimal import Decimal

from sqlmodel import Session, select

from app import models


def _month_bounds(year: int, month: int) -> tuple[datetime, datetime]:
    start = datetime(year, month, 1)
    last_day = monthrange(year, month)[1]
    end = datetime(year, month, last_day, 23, 59, 59)
    return start, end


def _transactions_in_month(
    session: Session, year: int, month: int
) -> list[models.Transaction]:
    start, end = _month_bounds(year, month)
    return session.exec(
        select(models.Transaction).where(
            models.Transaction.date >= start, models.Transaction.date <= end
        )
    ).all()


def _month_total(session: Session, year: int, month: int) -> Decimal:
    return sum(
        (t.amount for t in _transactions_in_month(session, year, month)),
        Decimal("0"),
    )


def _category_names(session: Session) -> dict[int, str]:
    return {c.id: c.name for c in session.exec(select(models.Category)).all()}


def _subcategory_names(session: Session) -> dict[int, str]:
    return {s.id: s.name for s in session.exec(select(models.Subcategory)).all()}


def _ranked_totals(buckets: dict, key_name: str, limit: int | None = None) -> list[dict]:
    rows = [
        {key_name: name, "total": total}
        for name, total in sorted(
            buckets.items(), key=lambda kv: kv[1], reverse=True
        )
    ]
    return rows[:limit] if limit else rows


def monthly_summary(
    session: Session, year: int, month: int, top_n: int = 5
) -> dict:
    txns = _transactions_in_month(session, year, month)

    cat_names = _category_names(session)
    sub_names = _subcategory_names(session)

    by_category: dict[str, Decimal] = defaultdict(lambda: Decimal("0"))
    by_subcategory: dict[str, Decimal] = defaultdict(lambda: Decimal("0"))
    by_merchant: dict[str, Decimal] = defaultdict(lambda: Decimal("0"))
    by_day: dict[int, Decimal] = defaultdict(lambda: Decimal("0"))
    total = Decimal("0")

    for t in txns:
        total += t.amount
        by_day[t.date.day] += t.amount
        if t.raw_merchant:
            by_merchant[t.raw_merchant] += t.amount
        if t.category_id in cat_names:
            by_category[cat_names[t.category_id]] += t.amount
        if t.subcategory_id in sub_names:
            by_subcategory[sub_names[t.subcategory_id]] += t.amount

    prev_year, prev_month = (year - 1, 12) if month == 1 else (year, month - 1)
    previous_total = _month_total(session, prev_year, prev_month)

    return {
        "year": year,
        "month": month,
        "total": total,
        "transaction_count": len(txns),
        "by_category": _ranked_totals(by_category, "category"),
        "top_subcategories": _ranked_totals(by_subcategory, "subcategory", top_n),
        "top_merchants": _ranked_totals(by_merchant, "merchant", top_n),
        "by_day": [
            {"day": day, "total": by_day[day]} for day in sorted(by_day)
        ],
        "previous_month_total": previous_total,
        "delta_vs_previous": total - previous_total,
    }
