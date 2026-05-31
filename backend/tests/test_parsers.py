"""Parser tests, written against real (sanitized) sample emails.

These lock in the formats we've actually seen:
- Scotia Interac Debit alert: amount + time, no merchant, no date in body.
- RBC Interac e-Transfer (outgoing): amount, date, recipient name, message.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from pathlib import Path

from app.parsing.base import EmailMessage
from app.parsing.etransfer import EtransferParser
from app.parsing.registry import parse_email
from app.parsing.scotia import ScotiaParser

FIXTURES = Path(__file__).parent / "fixtures"


def _load(name: str) -> str:
    return (FIXTURES / name).read_text()


def _scotia_email(received: datetime) -> EmailMessage:
    return EmailMessage(
        subject="Scotiabank InfoAlert",
        body=_load("scotia_debit.txt"),
        sender="InfoAlerts@scotiabank.com",
        date=received,
    )


def _etransfer_email() -> EmailMessage:
    return EmailMessage(
        subject="INTERAC e-Transfer: Your transfer was deposited",
        body=_load("rbc_etransfer_sent.txt"),
        sender="notify@payments.interac.ca",
        date=datetime(2026, 5, 28, 14, 0),
    )


# ---- Scotia debit ------------------------------------------------------------


def test_scotia_matches_its_own_email():
    assert ScotiaParser().matches(_scotia_email(datetime(2026, 5, 20)))


def test_scotia_does_not_match_etransfer():
    assert not ScotiaParser().matches(_etransfer_email())


def test_scotia_parses_amount_and_uses_email_date():
    received = datetime(2026, 5, 20, 18, 12)
    result = ScotiaParser().parse(_scotia_email(received))
    assert result is not None
    assert result.amount == Decimal("60.04")
    assert result.currency == "CAD"
    assert result.raw_merchant == ""  # Scotia alerts carry no merchant
    assert result.date == received  # body has no date, fall back to email date
    assert result.source == "scotia"


# ---- RBC e-transfer ----------------------------------------------------------


def test_etransfer_matches_its_own_email():
    assert EtransferParser().matches(_etransfer_email())


def test_etransfer_does_not_match_scotia():
    assert not EtransferParser().matches(_scotia_email(datetime(2026, 5, 20)))


def test_etransfer_parses_amount_date_recipient_and_message():
    result = EtransferParser().parse(_etransfer_email())
    assert result is not None
    assert result.amount == Decimal("1200.00")
    assert result.currency == "CAD"
    assert result.raw_merchant == "JANE DOE"  # recipient becomes the "merchant"
    assert result.date == datetime(2026, 5, 28)
    assert result.note == "Rent for June 2026 (123 Example Ave, Unit 1, A1A1A1)"
    assert result.source == "etransfer"


# ---- registry routing --------------------------------------------------------


def test_registry_routes_each_email_to_the_right_parser():
    scotia = parse_email(_scotia_email(datetime(2026, 5, 20)))
    assert scotia is not None and scotia.source == "scotia"

    etransfer = parse_email(_etransfer_email())
    assert etransfer is not None and etransfer.source == "etransfer"
