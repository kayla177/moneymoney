"""JSON API routes: categories, transactions, and monthly analysis.

The PWA talks only to these endpoints. Transactions are normally created by the poller,
but a manual-create endpoint exists too (handy for small RBC purchases that fall under the
email-alert threshold).
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from pydantic import BaseModel
from sqlalchemy import func
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
    # Rename a transaction (e.g. label a blank "(no merchant)" Scotia transfer).
    raw_merchant: str | None = None
    # When true, remember this merchant -> category mapping for next time.
    learn: bool = False


class CategoryCreate(BaseModel):
    name: str


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


@router.post("/categories", response_model=CategoryOut)
def create_category(payload: CategoryCreate, db: Session = Depends(get_db)):
    """Create a custom category by name. Idempotent: an existing category with the
    same name (case-insensitive) is returned instead of creating a duplicate."""
    name = payload.name.strip()
    if not name:
        raise HTTPException(status_code=422, detail="name must not be empty")

    existing = db.exec(
        select(models.Category).where(
            func.lower(models.Category.name) == name.lower()
        )
    ).first()
    if existing is not None:
        subs = db.exec(
            select(models.Subcategory).where(
                models.Subcategory.category_id == existing.id
            )
        ).all()
        return CategoryOut(
            id=existing.id,
            name=existing.name,
            subcategories=[SubcategoryOut(id=s.id, name=s.name) for s in subs],
        )

    category = models.Category(name=name)
    db.add(category)
    db.commit()
    db.refresh(category)
    return CategoryOut(id=category.id, name=category.name, subcategories=[])


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
    if payload.raw_merchant is not None:
        txn.raw_merchant = payload.raw_merchant

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


# ---- image import ------------------------------------------------------------


class ImportImageResponse(BaseModel):
    imported: int
    skipped_duplicates: int
    needs_review: int


@router.post("/transactions/from-image", response_model=ImportImageResponse)
async def import_from_image(
    image: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    """Pull transactions out of a statement screenshot via GPT-4o vision.

    Returns counts of newly-imported vs skipped (duplicate) vs review-queue. The actual
    transactions go into the same DB tables as poller-captured ones; check the Review
    tab for any that landed without a category.
    """
    from app import image_extract  # lazy: openai SDK only loaded for this endpoint

    image_bytes = await image.read()
    try:
        extracted = image_extract.extract_from_image(image_bytes, db)
    except image_extract.ImageExtractError as e:
        msg = str(e)
        # "not configured" is the operator's problem; everything else is a 502 upstream
        # failure (bad model output, OpenAI down, image too large, etc.).
        status = 503 if "not configured" in msg else 502
        raise HTTPException(status_code=status, detail=msg)

    result = image_extract.ingest_extracted(db, extracted)
    return ImportImageResponse(
        imported=result.imported,
        skipped_duplicates=result.skipped_duplicates,
        needs_review=result.needs_review,
    )


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
