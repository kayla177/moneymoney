"""Tests for the screenshot-import pipeline (without hitting the OpenAI API).

Covers: JSON-mode response parsing, duplicate detection against existing transactions,
and the end-to-end ingest flow (dedup + auto-confirm + needs-review counting).
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

import pytest
from sqlmodel import select

from app import models
from app.image_extract import (
    ExtractedTransaction,
    ImageExtractError,
    _looks_like_duplicate,
    ingest_extracted,
    parse_response,
)


# ---- parse_response ----------------------------------------------------------


def test_parse_response_extracts_valid_transactions():
    raw = (
        '{"transactions": ['
        ' {"amount": "9.52", "date": "2026-05-30", "merchant": "UBER",'
        '  "category": "Transport", "subcategory": "Rideshare"},'
        ' {"amount": "1.50", "date": "2026-06-01", "merchant": "YIMING",'
        '  "category": null, "subcategory": null}'
        ']}'
    )
    result = parse_response(raw)
    assert len(result) == 2
    assert result[0].amount == Decimal("9.52")
    assert result[0].merchant == "UBER"
    assert result[0].category == "Transport"
    assert result[1].category is None


def test_parse_response_skips_malformed_items():
    # Mix of valid, broken-amount, missing-keys, and a final valid one.
    raw = (
        '{"transactions": ['
        ' {"amount": "9.52", "date": "2026-05-30", "merchant": "OK"},'
        ' {"amount": "bad", "date": "bad"},'
        ' {},'
        ' {"amount": "1.00", "date": "2026-01-01", "merchant": "X"}'
        ']}'
    )
    result = parse_response(raw)
    assert len(result) == 2
    assert {t.merchant for t in result} == {"OK", "X"}


def test_parse_response_empty_list():
    assert parse_response('{"transactions": []}') == []


def test_parse_response_no_transactions_key():
    # Defensive: model sometimes omits the key entirely.
    assert parse_response("{}") == []


def test_parse_response_non_json_raises():
    with pytest.raises(ImageExtractError):
        parse_response("definitely not json")


# ---- _looks_like_duplicate ---------------------------------------------------


def _make_txn(session, **kwargs) -> models.Transaction:
    defaults = dict(
        date=datetime(2026, 5, 30),
        amount=Decimal("9.52"),
        currency="CAD",
        raw_merchant="UBER CANADA",
        source="rbc",
        status=models.TransactionStatus.confirmed,
    )
    defaults.update(kwargs)
    txn = models.Transaction(**defaults)
    session.add(txn)
    session.commit()
    return txn


def _extract(amount, date, merchant, category=None, subcategory=None):
    return ExtractedTransaction(
        amount=Decimal(amount),
        date=date,
        merchant=merchant,
        category=category,
        subcategory=subcategory,
    )


def test_dedup_matches_same_amount_date_and_merchant(session):
    _make_txn(session)
    extract = _extract("9.52", datetime(2026, 5, 30), "UBER")  # merchant substring
    assert _looks_like_duplicate(session, extract) is True


def test_dedup_no_match_when_amount_differs(session):
    _make_txn(session)
    extract = _extract("9.53", datetime(2026, 5, 30), "UBER")  # penny off
    assert _looks_like_duplicate(session, extract) is False


def test_dedup_no_match_when_date_outside_window(session):
    _make_txn(session, date=datetime(2026, 5, 20))
    extract = _extract("9.52", datetime(2026, 5, 30), "UBER")  # 10 days away
    assert _looks_like_duplicate(session, extract) is False


def test_dedup_matches_within_3_day_window(session):
    _make_txn(session, date=datetime(2026, 5, 30))
    extract = _extract("9.52", datetime(2026, 6, 2), "UBER")  # 3 days later
    assert _looks_like_duplicate(session, extract) is True


def test_dedup_falls_back_to_amount_date_when_merchants_missing(session):
    # Scotia transactions have raw_merchant=''; we don't want a same-amount+date
    # extracted transaction to silently double-count, so the fallback says "duplicate".
    _make_txn(session, raw_merchant="")
    extract = _extract("9.52", datetime(2026, 5, 30), "")
    assert _looks_like_duplicate(session, extract) is True


def test_dedup_different_merchant_same_amount_date_is_not_a_dupe(session):
    # Same amount and date but clearly different merchants — could be a real coincidence.
    _make_txn(session, raw_merchant="UBER CANADA")
    extract = _extract("9.52", datetime(2026, 5, 30), "STARBUCKS")
    assert _looks_like_duplicate(session, extract) is False


# ---- ingest_extracted --------------------------------------------------------


def test_ingest_dedups_and_categorizes(session):
    # Existing UBER transaction so the dedup branch runs.
    _make_txn(session)

    extracted = [
        _extract("9.52", datetime(2026, 5, 30), "UBER"),  # duplicate of seed
        _extract(
            "5.00", datetime(2026, 5, 28), "STARBUCKS",
            category="Food", subcategory="Coffee",
        ),  # auto-confirm: matches a real category
        _extract("12.00", datetime(2026, 5, 27), "MYSTERY VENDOR"),  # no category -> review
    ]
    result = ingest_extracted(session, extracted)

    assert result.skipped_duplicates == 1
    assert result.imported == 1
    assert result.needs_review == 1

    # Confirm the auto-confirmed one was saved with the right category.
    starbucks = session.exec(
        select(models.Transaction).where(
            models.Transaction.raw_merchant == "STARBUCKS"
        )
    ).first()
    assert starbucks is not None
    assert starbucks.status == models.TransactionStatus.confirmed
    food = session.exec(
        select(models.Category).where(models.Category.name == "Food")
    ).one()
    assert starbucks.category_id == food.id


def test_ingest_ignores_unknown_category_falls_back_to_review(session):
    extracted = [
        _extract(
            "5.00", datetime(2026, 5, 28), "WEIRD VENDOR",
            category="Crypto", subcategory="Tokens",  # not in our seeded categories
        ),
    ]
    result = ingest_extracted(session, extracted)
    # Unknown category means no category resolved; goes to review.
    assert result.needs_review == 1
    assert result.imported == 0


def test_ingest_existing_merchant_rule_overrides_model_category(session):
    # Train a rule that says "MYSTERY" -> Food. The model claims Transport. The
    # rule should win because it represents the user's explicit decision.
    food = session.exec(
        select(models.Category).where(models.Category.name == "Food")
    ).one()
    transport = session.exec(
        select(models.Category).where(models.Category.name == "Transport")
    ).one()
    session.add(
        models.MerchantRule(pattern="MYSTERY", category_id=food.id)
    )
    session.commit()

    extracted = [
        _extract(
            "12.00", datetime(2026, 5, 27), "MYSTERY VENDOR",
            category="Transport", subcategory="Rideshare",
        ),
    ]
    result = ingest_extracted(session, extracted)
    assert result.imported == 1

    txn = session.exec(
        select(models.Transaction).where(
            models.Transaction.raw_merchant == "MYSTERY VENDOR"
        )
    ).one()
    # Rule wins: ends up tagged Food, not Transport.
    assert txn.category_id == food.id
    assert txn.category_id != transport.id
