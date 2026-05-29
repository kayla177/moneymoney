"""Shared types and helpers for bank email parsers.

Each bank gets its own parser (see rbc.py, scotia.py) that turns the raw email into a
`ParsedTransaction`. Parsers are deliberately defensive: if they cannot confidently
extract the amount, they return None and the email is left for manual review rather than
producing a wrong transaction.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Protocol


@dataclass
class ParsedTransaction:
    """The fields a parser extracts from one bank email."""

    amount: Decimal
    currency: str
    raw_merchant: str
    date: datetime
    source: str


@dataclass
class EmailMessage:
    """Minimal view of an email handed to a parser."""

    subject: str
    body: str
    sender: str
    date: datetime


class BankParser(Protocol):
    source: str

    def matches(self, email: EmailMessage) -> bool:
        """Return True if this parser recognizes the email as one of its alerts."""
        ...

    def parse(self, email: EmailMessage) -> ParsedTransaction | None:
        """Extract a transaction, or None if the email can't be confidently parsed."""
        ...


_AMOUNT_RE = re.compile(r"(?:CAD|USD|\$)?\s*([0-9][0-9,]*\.[0-9]{2})")


def parse_amount(text: str) -> Decimal | None:
    """Pull the first money-looking value (e.g. '$1,234.56') out of text."""
    match = _AMOUNT_RE.search(text)
    if not match:
        return None
    try:
        return Decimal(match.group(1).replace(",", ""))
    except InvalidOperation:
        return None
