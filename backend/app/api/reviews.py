"""Review submission, retrieval and batch upload."""

from __future__ import annotations

from datetime import date

from fastapi import (
    APIRouter, Depends, File, HTTPException, Query, UploadFile, status,
)
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.api.deps import current_user, scoped_restaurant_id
from app.config import settings
from app.database.session import get_db
from app.ml_service import predictor
from app.models import Prediction, Restaurant, Review, ReviewAspect, User
from app.schemas import (
    AnalyseRequest, AnalyseResponse, BatchUploadResult, ReviewCreate, ReviewOut,
)
from app.services import review_service

router = APIRouter(prefix="/reviews", tags=["reviews"])

MODEL_UNAVAILABLE = HTTPException(
    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
    detail="The sentiment model is not available. Train it with "
           "`python ml/train_bilstm.py` (or train_baseline.py) and restart the API.",
)


def _to_out(review: Review, recommendations: list[str] | None = None) -> ReviewOut:
    out = ReviewOut.model_validate(review)
    latest = review.latest_prediction
    if latest is not None:
        from app.schemas import PredictionOut
        out.prediction = PredictionOut.model_validate(latest)
    from app.schemas import AspectOut
    out.aspects = [AspectOut.model_validate(a) for a in review.aspects]
    out.recommendations = recommendations or []
    return out


@router.post("", response_model=ReviewOut, status_code=status.HTTP_201_CREATED)
def submit_review(payload: ReviewCreate, db: Session = Depends(get_db)) -> ReviewOut:
    """Submit a review and analyse it. Public - customers are not logged in."""
    if db.get(Restaurant, payload.restaurant_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Restaurant not found.")
    try:
        review, recommendations = review_service.analyse_and_store(db, payload)
    except FileNotFoundError:
        raise MODEL_UNAVAILABLE
    return _to_out(review, recommendations)


@router.post("/analyse", response_model=AnalyseResponse)
def analyse_only(payload: AnalyseRequest) -> AnalyseResponse:
    """Analyse text without storing it - powers the 'try a review' page."""
    try:
        result = predictor.analyse(payload.review_text)
    except FileNotFoundError:
        raise MODEL_UNAVAILABLE
    return AnalyseResponse(**result)


@router.get("", response_model=list[ReviewOut])
def list_reviews(
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
    restaurant_id: int | None = None,
    branch_id: int | None = None,
    sentiment: str | None = Query(None, pattern="^(positive|neutral|negative)$"),
    urgency: str | None = Query(None, pattern="^(low|medium|high)$"),
    search: str | None = Query(None, min_length=2, max_length=100),
    start_date: date | None = None,
    end_date: date | None = None,
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
) -> list[ReviewOut]:
    scoped = scoped_restaurant_id(user, restaurant_id)

    stmt = (
        select(Review)
        .options(selectinload(Review.predictions), selectinload(Review.aspects))
        .order_by(Review.created_at.desc())
    )
    if scoped is not None:
        stmt = stmt.where(Review.restaurant_id == scoped)
    if branch_id is not None:
        stmt = stmt.where(Review.branch_id == branch_id)
    if start_date is not None:
        stmt = stmt.where(Review.review_date >= start_date)
    if end_date is not None:
        stmt = stmt.where(Review.review_date <= end_date)
    if search:
        stmt = stmt.where(Review.review_text.ilike(f"%{search}%"))
    if sentiment or urgency:
        stmt = stmt.join(Prediction, Prediction.review_id == Review.review_id)
        if sentiment:
            stmt = stmt.where(Prediction.sentiment == sentiment)
        if urgency:
            stmt = stmt.where(Prediction.urgency == urgency)

    reviews = db.scalars(stmt.limit(limit).offset(offset)).unique()
    return [_to_out(r) for r in reviews]


@router.get("/{review_id}", response_model=ReviewOut)
def get_review(review_id: int, db: Session = Depends(get_db),
               user: User = Depends(current_user)) -> ReviewOut:
    review = db.get(Review, review_id)
    if review is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Review not found.")
    if user.role != "admin" and review.restaurant_id != user.restaurant_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN,
                            "You can only view your own restaurant's reviews.")
    return _to_out(review)


@router.post("/batch", response_model=BatchUploadResult)
async def upload_batch(
    restaurant_id: int,
    file: UploadFile = File(...),
    branch_id: int | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> BatchUploadResult:
    """Upload a CSV of reviews and analyse each one.

    Required column: review_text. Optional: star_rating, review_date, branch_id.
    """
    scoped_restaurant_id(user, restaurant_id)
    if db.get(Restaurant, restaurant_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Restaurant not found.")

    if not (file.filename or "").lower().endswith(".csv"):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Please upload a .csv file.")

    content = await file.read()
    rows, errors = review_service.parse_csv(content, settings.max_batch_rows)
    if not rows:
        return BatchUploadResult(received=0, stored=0, skipped=0, errors=errors)

    stored = 0
    for i, row in enumerate(rows, start=1):
        payload = ReviewCreate(
            restaurant_id=restaurant_id,
            branch_id=row.get("branch_id", branch_id),
            review_text=row["review_text"],
            star_rating=row.get("star_rating"),
            source="csv_upload",
            review_date=row.get("review_date"),
        )
        try:
            review_service.analyse_and_store(db, payload)
            stored += 1
        except FileNotFoundError:
            raise MODEL_UNAVAILABLE
        except Exception as exc:  # noqa: BLE001
            db.rollback()
            errors.append(f"Row {i}: {exc}")

    return BatchUploadResult(
        received=len(rows), stored=stored, skipped=len(rows) - stored, errors=errors[:50],
    )
