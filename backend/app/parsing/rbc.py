"""RBC purchase-alert email parser.

STATUS: stub. The real extraction logic will be written against a real RBC alert email
(TDD) — in particular we need to confirm whether the alert names the merchant or only the
amount. Until then `matches` returns False so the poller simply ignores RBC emails rather
than guessing. See app/parsing/base.py for the interface.
"""

from __future__ import annotations

from app.parsing.base import EmailMessage, ParsedTransaction


class RbcParser:
    source = "rbc"

    def matches(self, email: EmailMessage) -> bool:
        # TODO: recognize RBC alert emails by sender/subject once we have a real sample.
        return False

    def parse(self, email: EmailMessage) -> ParsedTransaction | None:
        # TODO: extract amount / merchant / date from the real RBC alert format.
        return None
