"""Extract transactions from a statement screenshot using GPT-4o vision.

Backfilling tool: the user uploads a screenshot of a credit-card or bank statement and
we pull out every visible transaction, dedup against what's already captured (so emails
already ingested aren't double-counted), and insert the rest.

The OpenAI SDK is imported lazily so the rest of the app (and tests) don't depend on it
or on OPENAI_API_KEY being set. If the key is missing, the API route returns 503.
"""

from __future__ import annotations

import base64
import json
import logging
import os
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation

from sqlmodel import Session, select

from app import categorize, models
from app.models import TransactionStatus

logger = logging.getLogger("moneymoney.image_extract")

MODEL = "gpt-4o"
MAX_IMAGE_BYTES = 5 * 1024 * 1024  # 5 MB; GPT-4o's hard limit is ~20 MB but we cap earlier

_PROMPT_TEMPLATE = """\
You are a transaction extractor. The user has uploaded a screenshot of a bank or
credit-card statement.

Extract EVERY transaction visible. For each one, output:
- amount: decimal string, no currency symbol (e.g. "9.52")
- date: ISO YYYY-MM-DD. Use the transaction/purchase date, not the posted date if both
  are shown. If the year isn't visible anywhere on the image, assume {current_year}.
- merchant: the merchant name exactly as displayed
- category: one of [{category_names}], or null if you can't confidently tell
- subcategory: one of the subcategories listed under that category, or null

Categories and their subcategories:
{categories_listing}

IMPORTANT: skip credits, payments to the card, refunds, interest charges, and any
non-purchase line items. Only include outgoing purchases / debits.

Return STRICT JSON in this exact shape and nothing else:
{{
  "transactions": [
    {{"amount": "9.52", "date": "2026-05-30", "merchant": "UBER CANADA", "category": "Transport", "subcategory": "Rideshare"}}
  ]
}}

If the image contains no transactions, return {{"transactions": []}}.
"""


@dataclass
class ExtractedTransaction:
    """One transaction parsed from the model's response, pre-dedup, pre-categorize."""

    amount: Decimal
    date: datetime
    merchant: str
    category: str | None
    subcategory: str | None


@dataclass
class ImportResult:
    imported: int
    skipped_duplicates: int
    needs_review: int


class ImageExtractError(Exception):
    """User-surfaceable extraction failure: missing config, bad response, API error."""


def _build_prompt(session: Session) -> str:
    categories = session.exec(select(models.Category)).all()
    subs = session.exec(select(models.Subcategory)).all()
    by_cat: dict[int, list[str]] = {}
    for s in subs:
        by_cat.setdefault(s.category_id, []).append(s.name)
    listing = "\n".join(
        f"- {c.name}: {', '.join(by_cat.get(c.id, [])) or '(none)'}"
        for c in categories
    )
    return _PROMPT_TEMPLATE.format(
        current_year=datetime.now().year,
        category_names=", ".join(c.name for c in categories),
        categories_listing=listing,
    )


def extract_from_image(
    image_bytes: bytes, session: Session
) -> list[ExtractedTransaction]:
    """Send image to GPT-4o, return parsed transactions. Raises ImageExtractError."""
    if not os.environ.get("OPENAI_API_KEY"):
        raise ImageExtractError("OPENAI_API_KEY not configured on the server")

    if len(image_bytes) > MAX_IMAGE_BYTES:
        raise ImageExtractError(
            f"image too large: {len(image_bytes) // 1024} KB "
            f"exceeds limit of {MAX_IMAGE_BYTES // 1024} KB"
        )

    from openai import OpenAI  # lazy: only when we actually call the API

    client = OpenAI()
    encoded = base64.standard_b64encode(image_bytes).decode()
    prompt = _build_prompt(session)

    try:
        response = client.chat.completions.create(
            model=MODEL,
            response_format={"type": "json_object"},
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{encoded}"
                            },
                        },
                    ],
                }
            ],
        )
    except Exception as e:  # noqa: BLE001 — surface as a user-visible error
        raise ImageExtractError(f"OpenAI API error: {e}") from e

    raw = response.choices[0].message.content or "{}"
    return parse_response(raw)


def parse_response(raw_json: str) -> list[ExtractedTransaction]:
    """Parse JSON-mode reply. Silently skip malformed rows — the model can hallucinate."""
    try:
        data = json.loads(raw_json)
    except json.JSONDecodeError as e:
        raise ImageExtractError(f"model returned non-JSON: {e}") from e

    out: list[ExtractedTransaction] = []
    for item in data.get("transactions", []) or []:
        try:
            amount = Decimal(str(item["amount"]))
            date = datetime.fromisoformat(item["date"])
            merchant = (item.get("merchant") or "").strip()
        except (KeyError, InvalidOperation, ValueError, TypeError):
            continue
        out.append(
            ExtractedTransaction(
                amount=amount,
                date=date,
                merchant=merchant,
                category=item.get("category"),
                subcategory=item.get("subcategory"),
            )
        )
    return out


def _looks_like_duplicate(
    session: Session, extracted: ExtractedTransaction
) -> bool:
    """True if an existing transaction matches amount + nearby date + similar merchant.

    Same-amount + within ±3 days is the strongest signal; we add merchant similarity as
    extra confidence. Without merchant info on either side we fall back to amount+date
    alone (better to skip a duplicate than risk a double-count for a small statement).
    """
    window_lo = extracted.date - timedelta(days=3)
    window_hi = extracted.date + timedelta(days=3)
    candidates = session.exec(
        select(models.Transaction).where(
            models.Transaction.amount == extracted.amount,
            models.Transaction.date >= window_lo,
            models.Transaction.date <= window_hi,
        )
    ).all()
    if not candidates:
        return False
    merch = extracted.merchant.lower()
    for c in candidates:
        existing = (c.raw_merchant or "").lower()
        if merch and existing:
            if merch in existing or existing in merch:
                return True
            continue
        # If either side lacks a merchant, amount+date alone is strong enough.
        return True
    return False


def _resolve_category(
    session: Session, category_name: str | None, subcategory_name: str | None
) -> tuple[int | None, int | None]:
    """Map a Claude-suggested category/sub name to our DB ids, ignoring unknowns."""
    if not category_name:
        return None, None
    category = session.exec(
        select(models.Category).where(models.Category.name == category_name)
    ).first()
    if category is None:
        return None, None
    subcategory_id: int | None = None
    if subcategory_name:
        sub = session.exec(
            select(models.Subcategory).where(
                models.Subcategory.name == subcategory_name,
                models.Subcategory.category_id == category.id,
            )
        ).first()
        subcategory_id = sub.id if sub else None
    return category.id, subcategory_id


def ingest_extracted(
    session: Session, extracted: list[ExtractedTransaction]
) -> ImportResult:
    """Insert non-duplicate extracted transactions; learned merchant rules still win."""
    imported = 0
    skipped = 0
    needs_review = 0
    for e in extracted:
        if _looks_like_duplicate(session, e):
            skipped += 1
            continue
        category_id, subcategory_id = _resolve_category(
            session, e.category, e.subcategory
        )
        txn = models.Transaction(
            date=e.date,
            amount=e.amount,
            currency="CAD",
            raw_merchant=e.merchant,
            source="image",
            category_id=category_id,
            subcategory_id=subcategory_id,
        )
        if category_id is not None:
            # Model gave a category — auto-confirm. But a user-trained merchant rule
            # is more authoritative, so let it override.
            txn.status = TransactionStatus.confirmed
            session.add(txn)
            session.commit()
            session.refresh(txn)
            rule = categorize.find_matching_rule(session, txn.raw_merchant)
            if rule is not None:
                txn.category_id = rule.category_id
                txn.subcategory_id = rule.subcategory_id
                session.add(txn)
                session.commit()
            imported += 1
        else:
            session.add(txn)
            session.commit()
            session.refresh(txn)
            categorize.apply_categorization(session, txn)
            if txn.status == TransactionStatus.needs_review:
                needs_review += 1
            else:
                imported += 1
    return ImportResult(
        imported=imported, skipped_duplicates=skipped, needs_review=needs_review
    )
