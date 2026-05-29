"""Parser registry: holds the known bank parsers and tries each against an email.

To add a bank, implement the BankParser protocol (see base.py) and add it to PARSERS.
"""

from __future__ import annotations

from app.parsing.base import BankParser, EmailMessage, ParsedTransaction
from app.parsing.rbc import RbcParser
from app.parsing.scotia import ScotiaParser

PARSERS: list[BankParser] = [RbcParser(), ScotiaParser()]


def parse_email(
    email: EmailMessage, parsers: list[BankParser] | None = None
) -> ParsedTransaction | None:
    """Return the first confident parse from any parser that recognizes the email."""
    for parser in parsers if parsers is not None else PARSERS:
        if parser.matches(email):
            result = parser.parse(email)
            if result is not None:
                return result
    return None
