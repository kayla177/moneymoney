"""JSON API routes: categories, transactions, and monthly analysis.

The PWA talks only to these endpoints. Transactions are normally created by the poller,
but a manual-create endpoint exists too (handy for small RBC purchases that fall under the
email-alert threshold).
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlmodel import Session, select

from app import analysis, categorize, models
from app.api.deps import get_db
from app.models import TransactionStatus

router = APIRouter(prefix="/api")


# ---- response/request shapes -------------------------------------------------


class SubcategoryOut(BaseModel):
    id: int
    name: str


class CategoryOut(BaseModel):
    id: int
    name: str
    subcategories: list[SubcategoryOut]


class TransactionCreate(BaseModel):
    date: datetime
    amount: Decimal
    raw_merchant: str = ""
    source: str = "manual"
    currency: str = "CAD"
    category_id: int | None = None
    subcategory_id: int | None = None
    note: str | None = None


class TransactionUpdate(BaseModel):
    category_id: int | None = None
    subcategory_id: int | None = None
    note: str | None = None
    # When true, remember this merchant -> category mapping for next time.
    learn: bool = False


# ---- categories --------------------------------------------------------------


@router.get("/categories", response_model=list[CategoryOut])
def list_categories(db: Session = Depends(get_db)):
    categories = db.exec(select(models.Category)).all()
    subs = db.exec(select(models.Subcategory)).all()
    by_cat: dict[int, list[SubcategoryOut]] = {}
    for s in subs:
        by_cat.setdefault(s.category_id, []).append(
            SubcategoryOut(id=s.id, name=s.name)
        )
    return [
        CategoryOut(id=c.id, name=c.name, subcategories=by_cat.get(c.id, []))
        for c in categories
    ]


# ---- transactions ------------------------------------------------------------


@router.get("/transactions", response_model=list[models.Transaction])
def list_transactions(
    db: Session = Depends(get_db),
    month: str | None = Query(default=None, description="Filter by month, YYYY-MM"),
    status: TransactionStatus | None = None,
):
    stmt = select(models.Transaction)
    if month:
        year, mon = _parse_month(month)
        from app.analysis import _month_bounds

        start, end = _month_bounds(year, mon)
        stmt = stmt.where(
            models.Transaction.date >= start, models.Transaction.date <= end
        )
    if status:
        stmt = stmt.where(models.Transaction.status == status)
    stmt = stmt.order_by(models.Transaction.date.desc())
    return db.exec(stmt).all()


@router.post("/transactions", response_model=models.Transaction)
def create_transaction(payload: TransactionCreate, db: Session = Depends(get_db)):
    txn = models.Transaction(
        date=payload.date,
        amount=payload.amount,
        currency=payload.currency,
        raw_merchant=payload.raw_merchant,
        source=payload.source,
        category_id=payload.category_id,
        subcategory_id=payload.subcategory_id,
        note=payload.note,
    )
    if payload.category_id is not None:
        txn.status = TransactionStatus.confirmed
        db.add(txn)
        db.commit()
        db.refresh(txn)
    else:
        db.add(txn)
        db.commit()
        db.refresh(txn)
        categorize.apply_categorization(db, txn)
    return txn


@router.patch("/transactions/{txn_id}", response_model=models.Transaction)
def update_transaction(
    txn_id: int, payload: TransactionUpdate, db: Session = Depends(get_db)
):
    txn = db.get(models.Transaction, txn_id)
    if txn is None:
        raise HTTPException(status_code=404, detail="Transaction not found")

    if payload.category_id is not None:
        txn.category_id = payload.category_id
        txn.subcategory_id = payload.subcategory_id
        txn.status = TransactionStatus.confirmed
    if payload.note is not None:
        txn.note = payload.note

    db.add(txn)
    db.commit()
    db.refresh(txn)

    if payload.learn and payload.category_id is not None and txn.raw_merchant:
        categorize.learn_rule(
            db,
            raw_merchant=txn.raw_merchant,
            category_id=payload.category_id,
            subcategory_id=payload.subcategory_id,
        )
    return txn


# ---- analysis ----------------------------------------------------------------


@router.get("/analysis")
def monthly_analysis(
    db: Session = Depends(get_db),
    month: str = Query(description="Month to analyze, YYYY-MM"),
):
    year, mon = _parse_month(month)
    return analysis.monthly_summary(db, year, mon)


def _parse_month(month: str) -> tuple[int, int]:
    try:
        year_str, month_str = month.split("-")
        return int(year_str), int(month_str)
    except (ValueError, AttributeError):
        raise HTTPException(
            status_code=422, detail="month must be in YYYY-MM format"
        )
