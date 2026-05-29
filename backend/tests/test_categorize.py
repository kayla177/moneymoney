"""Tests for the categorization engine (merchant rules + learn-on-correct)."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlmodel import select

from app import categorize, models
from app.models import TransactionStatus


def _category_id(session, name: str) -> int:
    return session.exec(
        select(models.Category).where(models.Category.name == name)
    ).one().id


def _subcategory_id(session, name: str) -> int:
    return session.exec(
        select(models.Subcategory).where(models.Subcategory.name == name)
    ).first().id


def _make_txn(session, raw_merchant: str) -> models.Transaction:
    txn = models.Transaction(
        date=datetime(2026, 5, 1, 12, 0),
        amount=Decimal("12.50"),
        raw_merchant=raw_merchant,
        source="rbc",
    )
    session.add(txn)
    session.commit()
    session.refresh(txn)
    return txn


def test_unknown_merchant_goes_to_review(session):
    txn = _make_txn(session, "MYSTERY SHOP 123")
    categorize.apply_categorization(session, txn)
    assert txn.status == TransactionStatus.needs_review
    assert txn.category_id is None


def test_matching_rule_auto_categorizes(session):
    food = _category_id(session, "Food")
    groceries = _subcategory_id(session, "Groceries")
    session.add(
        models.MerchantRule(
            pattern="LOBLAWS", category_id=food, subcategory_id=groceries
        )
    )
    session.commit()

    txn = _make_txn(session, "LOBLAWS #1234 TORONTO ON")
    categorize.apply_categorization(session, txn)

    assert txn.status == TransactionStatus.auto
    assert txn.category_id == food
    assert txn.subcategory_id == groceries


def test_matching_is_case_insensitive(session):
    food = _category_id(session, "Food")
    session.add(models.MerchantRule(pattern="tim hortons", category_id=food))
    session.commit()

    txn = _make_txn(session, "TIM HORTONS #42")
    categorize.apply_categorization(session, txn)
    assert txn.category_id == food


def test_most_specific_rule_wins(session):
    food = _category_id(session, "Food")
    shopping = _category_id(session, "Shopping")
    # A generic and a more specific pattern both match "WALMART SUPERCENTRE".
    session.add(models.MerchantRule(pattern="WALMART", category_id=shopping))
    session.add(
        models.MerchantRule(pattern="WALMART SUPERCENTRE", category_id=food)
    )
    session.commit()

    txn = _make_txn(session, "WALMART SUPERCENTRE #99")
    categorize.apply_categorization(session, txn)
    assert txn.category_id == food  # longer (more specific) pattern wins


def test_learn_rule_then_auto_categorizes_next_time(session):
    food = _category_id(session, "Food")
    restaurants = _subcategory_id(session, "Restaurants")

    # User corrects an unknown transaction and we learn a rule from it.
    txn = _make_txn(session, "SUSHI PLACE 88")
    categorize.learn_rule(
        session,
        raw_merchant=txn.raw_merchant,
        category_id=food,
        subcategory_id=restaurants,
    )

    # The next identical merchant should now auto-categorize.
    next_txn = _make_txn(session, "SUSHI PLACE 88")
    categorize.apply_categorization(session, next_txn)
    assert next_txn.status == TransactionStatus.auto
    assert next_txn.category_id == food
    assert next_txn.subcategory_id == restaurants
