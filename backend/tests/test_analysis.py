"""Tests for monthly spending analysis aggregation."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlmodel import select

from app import analysis, models


def _cat(session, name):
    return session.exec(
        select(models.Category).where(models.Category.name == name)
    ).one().id


def _add(session, *, day, amount, merchant, category_id, month=5):
    session.add(
        models.Transaction(
            date=datetime(2026, month, day, 10, 0),
            amount=Decimal(str(amount)),
            raw_merchant=merchant,
            source="rbc",
            category_id=category_id,
        )
    )


def _seed_month(session):
    food = _cat(session, "Food")
    transport = _cat(session, "Transport")
    _add(session, day=2, amount="20.00", merchant="LOBLAWS", category_id=food)
    _add(session, day=2, amount="5.50", merchant="TIM HORTONS", category_id=food)
    _add(session, day=15, amount="30.00", merchant="LOBLAWS", category_id=food)
    _add(session, day=15, amount="12.00", merchant="TTC", category_id=transport)
    # A transaction in the previous month, for the comparison.
    _add(session, day=10, amount="100.00", merchant="OLD", category_id=food, month=4)
    session.commit()
    return food, transport


def test_total_and_count(session):
    _seed_month(session)
    summary = analysis.monthly_summary(session, 2026, 5)
    assert summary["total"] == Decimal("67.50")
    assert summary["transaction_count"] == 4


def test_breakdown_by_category(session):
    food, transport = _seed_month(session)
    summary = analysis.monthly_summary(session, 2026, 5)
    by_cat = {row["category"]: row["total"] for row in summary["by_category"]}
    assert by_cat["Food"] == Decimal("55.50")
    assert by_cat["Transport"] == Decimal("12.00")


def test_top_merchants(session):
    _seed_month(session)
    summary = analysis.monthly_summary(session, 2026, 5)
    top = summary["top_merchants"]
    assert top[0]["merchant"] == "LOBLAWS"
    assert top[0]["total"] == Decimal("50.00")


def test_vs_previous_month(session):
    _seed_month(session)
    summary = analysis.monthly_summary(session, 2026, 5)
    assert summary["previous_month_total"] == Decimal("100.00")
    assert summary["delta_vs_previous"] == Decimal("-32.50")


def test_by_day(session):
    _seed_month(session)
    summary = analysis.monthly_summary(session, 2026, 5)
    by_day = {row["day"]: row["total"] for row in summary["by_day"]}
    assert by_day[2] == Decimal("25.50")
    assert by_day[15] == Decimal("42.00")


def test_empty_month_is_zeroed(session):
    summary = analysis.monthly_summary(session, 2026, 5)
    assert summary["total"] == Decimal("0")
    assert summary["transaction_count"] == 0
    assert summary["by_category"] == []
