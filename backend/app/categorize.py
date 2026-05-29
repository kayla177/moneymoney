"""Auto-categorization: map a transaction's merchant to a category via merchant rules.

A rule matches if its `pattern` appears (case-insensitively) anywhere in the transaction's
`raw_merchant`. When several rules match, the longest pattern wins, since a longer match is
more specific (e.g. "WALMART SUPERCENTRE" beats "WALMART"). No match means the transaction
is left for manual review rather than guessed at.

`learn_rule` is the flip side: when the user categorizes an unknown transaction, we record
a rule so the same merchant is handled automatically next time.
"""

from __future__ import annotations

from sqlmodel import Session, select

from app import models
from app.models import TransactionStatus


def find_matching_rule(
    session: Session, raw_merchant: str
) -> models.MerchantRule | None:
    merchant = raw_merchant.lower()
    rules = session.exec(select(models.MerchantRule)).all()
    matches = [r for r in rules if r.pattern.lower() in merchant]
    if not matches:
        return None
    return max(matches, key=lambda r: len(r.pattern))


def apply_categorization(session: Session, txn: models.Transaction) -> None:
    """Set the transaction's category/status based on merchant rules, then persist."""
    rule = find_matching_rule(session, txn.raw_merchant)
    if rule is None:
        txn.status = TransactionStatus.needs_review
    else:
        txn.category_id = rule.category_id
        txn.subcategory_id = rule.subcategory_id
        txn.status = TransactionStatus.auto
    session.add(txn)
    session.commit()
    session.refresh(txn)


def learn_rule(
    session: Session,
    raw_merchant: str,
    category_id: int,
    subcategory_id: int | None = None,
) -> models.MerchantRule:
    """Create a merchant rule from a user's correction so it sticks next time.

    Uses the full merchant string as the pattern, which is conservative: only the same
    merchant matches, so we never over-generalize a single correction.
    """
    rule = models.MerchantRule(
        pattern=raw_merchant.strip(),
        category_id=category_id,
        subcategory_id=subcategory_id,
    )
    session.add(rule)
    session.commit()
    session.refresh(rule)
    return rule
