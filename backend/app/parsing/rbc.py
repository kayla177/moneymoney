"""RBC Royal Bank credit-card purchase-alert parser.

Real sample (sanitized) in tests/fixtures/rbc_credit.txt. The alert restates each field
in a structured table after a narrative paragraph:

    Purchase Amount:        $39.37
    Transaction Date:        May 30, 2026
    Transaction Description: CA WONDERLAND FOODS

We extract from the structured labels (more reliable than the narrative). The narrative
itself also names the merchant ("towards CA WONDERLAND FOODS") but only the table form is
guaranteed to be a single line, so we use that.
"""

from __future__ import annotations

import re
from datetime import datetime

from app.parsing.base import EmailMessage, ParsedTransaction, parse_amount

_AMOUNT_RE = re.compile(r"Purchase Amount:\s*([^\n]+)", re.IGNORECASE)
_DATE_RE = re.compile(r"Transaction Date:\s*([^\n]+)", re.IGNORECASE)
_MERCHANT_RE = re.compile(r"Transaction Description:\s*([^\n]+)", re.IGNORECASE)


class RbcParser:
    source = "rbc"

    def matches(self, email: EmailMessage) -> bool:
        text = f"{email.subject}\n{email.body}".lower()
        return "rbc royal bank credit card" in text

    def parse(self, email: EmailMessage) -> ParsedTransaction | None:
        amount_match = _AMOUNT_RE.search(email.body)
        amount = parse_amount(amount_match.group(1)) if amount_match else None
        if amount is None:
            return None  # defensive: no confident amount -> leave for manual review

        merchant_match = _MERCHANT_RE.search(email.body)
        merchant = merchant_match.group(1).strip() if merchant_match else ""

        return ParsedTransaction(
            amount=amount,
            currency="CAD",
            raw_merchant=merchant,
            date=self._parse_date(email),
            source=self.source,
        )

    @staticmethod
    def _parse_date(email: EmailMessage) -> datetime:
        match = _DATE_RE.search(email.body)
        if match:
            try:
                return datetime.strptime(match.group(1).strip(), "%B %d, %Y")
            except ValueError:
                pass
        return email.date
