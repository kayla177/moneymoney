"""Scotiabank Interac Debit alert parser.

Real sample (sanitized) in tests/fixtures/scotia_debit.txt:

    "Your ScotiaCard was used for an Interac Debit transaction of $60.04 at 6:12 pm ET."

These alerts give us the amount and a time, but no merchant and no date in the body, so we
use the email's received date. With no merchant, these transactions land in the review
queue for a one-tap category (nothing to auto-categorize on).
"""

from __future__ import annotations

from app.parsing.base import EmailMessage, ParsedTransaction, parse_amount


class ScotiaParser:
    source = "scotia"

    def matches(self, email: EmailMessage) -> bool:
        text = f"{email.subject}\n{email.body}".lower()
        return "scotiacard was used" in text or (
            "scotiabank" in text and "transaction of" in text
        )

    def parse(self, email: EmailMessage) -> ParsedTransaction | None:
        amount = parse_amount(email.body)
        if amount is None:
            return None  # defensive: no confident amount -> leave for manual review
        return ParsedTransaction(
            amount=amount,
            currency="CAD",
            raw_merchant="",  # Scotia debit alerts don't include the merchant
            date=email.date,  # no date in body; use when the email arrived
            source=self.source,
        )
