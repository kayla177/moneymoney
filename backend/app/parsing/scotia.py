"""Scotiabank purchase-receipt email parser.

STATUS: stub. The real extraction logic will be written against a real Scotia receipt
email (TDD). Until then `matches` returns False so the poller ignores Scotia emails rather
than guessing. See app/parsing/base.py for the interface.
"""

from __future__ import annotations

from app.parsing.base import EmailMessage, ParsedTransaction


class ScotiaParser:
    source = "scotia"

    def matches(self, email: EmailMessage) -> bool:
        # TODO: recognize Scotia receipt emails by sender/subject once we have a real sample.
        return False

    def parse(self, email: EmailMessage) -> ParsedTransaction | None:
        # TODO: extract amount / merchant / date from the real Scotia receipt format.
        return None
