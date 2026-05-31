"""Email poller: fetch new bank emails, turn them into categorized transactions.

Two layers:
- `ingest_email` is pure and testable: dedupe by email uid, parse, categorize, persist.
- `poll_once` / `start_scheduler` handle the live IMAP connection and scheduling. These
  need real credentials and aren't unit-tested.

We poll because iOS can't reliably read email in the background; this runs on the always-on
backend instead.
"""

from __future__ import annotations

import logging
import os

from sqlmodel import Session, select

from app import categorize, models
from app.db import engine
from app.parsing.base import EmailMessage
from app.parsing.registry import parse_email

logger = logging.getLogger("moneymoney.poller")


def ingest_email(
    session: Session, email: EmailMessage, email_uid: str, parsers=None
) -> models.Transaction | None:
    """Process one email exactly once. Returns the created transaction, or None.

    None means either we've already seen this uid, or no parser produced a transaction
    (e.g. a newsletter). Either way the uid is recorded so we don't re-examine it.
    """
    already = session.exec(
        select(models.ProcessedEmail).where(
            models.ProcessedEmail.email_uid == email_uid
        )
    ).first()
    if already is not None:
        return None

    parsed = parse_email(email, parsers)

    session.add(models.ProcessedEmail(email_uid=email_uid))
    session.commit()

    if parsed is None:
        return None

    txn = models.Transaction(
        date=parsed.date,
        amount=parsed.amount,
        currency=parsed.currency,
        raw_merchant=parsed.raw_merchant,
        source=parsed.source,
        note=parsed.note,
        raw_email_id=email_uid,
    )
    session.add(txn)
    session.commit()
    session.refresh(txn)

    categorize.apply_categorization(session, txn)
    return txn


def poll_once() -> int:
    """Connect to Gmail over IMAP, ingest unseen emails, return how many transactions made.

    Requires GMAIL_ADDRESS / GMAIL_APP_PASSWORD env vars. Imported lazily so the rest of
    the app (and tests) don't require imap-tools or credentials.
    """
    from imap_tools import AND, MailBox

    host = os.environ.get("GMAIL_IMAP_HOST", "imap.gmail.com")
    address = os.environ["GMAIL_ADDRESS"]
    password = os.environ["GMAIL_APP_PASSWORD"]

    created = 0
    with MailBox(host).login(address, password) as mailbox:
        # Fetch unseen messages; mark them seen so each is handled once.
        for msg in mailbox.fetch(AND(seen=False), mark_seen=True):
            email = EmailMessage(
                subject=msg.subject or "",
                body=msg.text or msg.html or "",
                sender=msg.from_ or "",
                date=msg.date,
            )
            with Session(engine) as session:
                # uid is stable within a mailbox; combine with date for safety.
                uid = f"{msg.uid}-{msg.date.isoformat() if msg.date else ''}"
                txn = ingest_email(session, email, uid)
                if txn is not None:
                    created += 1
    if created:
        logger.info("Ingested %d new transaction(s)", created)
    return created


def start_scheduler() -> None:
    """Run `poll_once` on a fixed interval (default 60s) via APScheduler."""
    from apscheduler.schedulers.background import BackgroundScheduler

    interval = int(os.environ.get("POLL_INTERVAL_SECONDS", "60"))
    scheduler = BackgroundScheduler()
    scheduler.add_job(_safe_poll, "interval", seconds=interval, id="poll")
    scheduler.start()
    logger.info("Poller scheduled every %ds", interval)


def _safe_poll() -> None:
    try:
        poll_once()
    except Exception:  # never let a transient IMAP/parse error kill the scheduler
        logger.exception("poll_once failed")
