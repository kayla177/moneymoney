"""Interac e-Transfer parser (outgoing transfers, e.g. rent).

Real sample (sanitized) in tests/fixtures/rbc_etransfer_sent.txt. These are sent by Interac
"on behalf of RBC Royal Bank" and confirm money the user sent was deposited — i.e. money
out. We only match outgoing transfers (incoming money isn't spending).

We extract amount, date, the recipient (used as the merchant so a landlord can be
categorized once and remembered), and the transfer message (kept as the note).
"""

from __future__ import annotations

import re
from datetime import datetime

from app.parsing.base import EmailMessage, ParsedTransaction, parse_amount

_RECIPIENT_RE = re.compile(r"sent to\s+\S+?\(([^)]+)\)", re.IGNORECASE)
_DATE_RE = re.compile(r"([A-Z][a-z]+ \d{1,2}, \d{4})")
_CURRENCY_RE = re.compile(r"\((CAD|USD)\)")
_MESSAGE_RE = re.compile(r"Message:\s*(?:\n\s*)*([^\n]+)", re.IGNORECASE)


class EtransferParser:
    source = "etransfer"

    def matches(self, email: EmailMessage) -> bool:
        text = f"{email.subject}\n{email.body}".lower()
        is_etransfer = "interac" in text and "e-transfer" in text
        # Outgoing only: the user sent money (not received).
        is_outgoing = "you sent to" in text or "your transfer to" in text
        return is_etransfer and is_outgoing

    def parse(self, email: EmailMessage) -> ParsedTransaction | None:
        amount = parse_amount(email.body)
        if amount is None:
            return None

        currency_match = _CURRENCY_RE.search(email.body)
        currency = currency_match.group(1) if currency_match else "CAD"

        recipient_match = _RECIPIENT_RE.search(email.body)
        recipient = recipient_match.group(1).strip() if recipient_match else ""

        message_match = _MESSAGE_RE.search(email.body)
        note = message_match.group(1).strip() if message_match else None

        return ParsedTransaction(
            amount=amount,
            currency=currency,
            raw_merchant=recipient,
            date=self._parse_date(email),
            source=self.source,
            note=note,
        )

    @staticmethod
    def _parse_date(email: EmailMessage) -> datetime:
        match = _DATE_RE.search(email.body)
        if match:
            try:
                return datetime.strptime(match.group(1), "%B %d, %Y")
            except ValueError:
                pass
        return email.date
