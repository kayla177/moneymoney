"""Tests for the email-ingest logic (dedupe + parse + categorize), using a fake parser."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlmodel import select

from app import models, poller
from app.models import TransactionStatus
from app.parsing.base import EmailMessage, ParsedTransaction


class FakeParser:
    """Recognizes any email whose subject contains 'PURCHASE' and pulls a fixed result."""

    source = "rbc"

    def matches(self, email: EmailMessage) -> bool:
        return "PURCHASE" in email.subject.upper()

    def parse(self, email: EmailMessage) -> ParsedTransaction | None:
        return ParsedTransaction(
            amount=Decimal("18.75"),
            currency="CAD",
            raw_merchant="LOBLAWS #1234",
            date=datetime(2026, 5, 20, 9, 30),
            source="rbc",
        )


def _email(subject="A PURCHASE was made"):
    return EmailMessage(
        subject=subject, body="...", sender="alerts@rbc.com", date=datetime(2026, 5, 20)
    )


def test_ingest_creates_transaction(session):
    txn = poller.ingest_email(session, _email(), "uid-1", [FakeParser()])
    assert txn is not None
    assert txn.amount == Decimal("18.75")
    assert txn.raw_merchant == "LOBLAWS #1234"
    assert txn.source == "rbc"


def test_ingest_is_deduped(session):
    first = poller.ingest_email(session, _email(), "uid-1", [FakeParser()])
    second = poller.ingest_email(session, _email(), "uid-1", [FakeParser()])
    assert first is not None
    assert second is None  # same uid -> skipped
    count = len(session.exec(select(models.Transaction)).all())
    assert count == 1


def test_ingest_applies_categorization(session):
    # Seed a rule so the ingested transaction auto-categorizes.
    food = session.exec(
        select(models.Category).where(models.Category.name == "Food")
    ).one()
    session.add(models.MerchantRule(pattern="LOBLAWS", category_id=food.id))
    session.commit()

    txn = poller.ingest_email(session, _email(), "uid-1", [FakeParser()])
    assert txn.status == TransactionStatus.auto
    assert txn.category_id == food.id


def test_unrecognized_email_creates_nothing_but_is_marked_processed(session):
    txn = poller.ingest_email(
        session, _email(subject="Your monthly statement"), "uid-9", [FakeParser()]
    )
    assert txn is None
    assert len(session.exec(select(models.Transaction)).all()) == 0
    # Marked processed so we don't re-examine it forever.
    processed = session.exec(select(models.ProcessedEmail)).all()
    assert any(p.email_uid == "uid-9" for p in processed)
