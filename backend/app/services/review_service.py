"""Storing a review and its analysis together, in one transaction."""

from __future__ import annotations

import csv
import io
from datetime import date, datetime

from sqlalchemy.orm import Session

from app.ml_service import predictor
from app.models import Prediction, Review, ReviewAspect
from app.schemas import ReviewCreate


def analyse_and_store(db: Session, payload: ReviewCreate) -> tuple[Review, list[str]]:
    """Create the review, run the model, persist prediction and aspects.

    Returns (review, recommendations). Recommendations are derived, not stored -
    they follow from the aspects, so persisting them would be duplicated state
    that goes stale the moment the recommendation rules change.
    """
    result = predictor.analyse(payload.review_text)

    review = Review(
        restaurant_id=payload.restaurant_id,
        branch_id=payload.branch_id,
        review_text=payload.review_text,
        star_rating=payload.star_rating,
        source=payload.source,
        review_date=payload.review_date or date.today(),
    )
    db.add(review)
    db.flush()  # assigns review_id without committing yet

    db.add(Prediction(
        review_id=review.review_id,
        sentiment=result["sentiment"],
        sentiment_confidence=result["confidence"],
        urgency=result["urgency"],
        urgency_reason=result.get("urgency_reason"),
        model_version=result.get("model_version", "v1"),
    ))

    for aspect in result.get("aspects", []):
        db.add(ReviewAspect(
            review_id=review.review_id,
            aspect=aspect["aspect"],
            aspect_sentiment=aspect["sentiment"],
            confidence=aspect["confidence"],
        ))

    db.commit()
    db.refresh(review)
    return review, result.get("recommendations", [])


def parse_csv(content: bytes, max_rows: int) -> tuple[list[dict], list[str]]:
    """Parse an uploaded CSV into review dicts.

    Expected columns: review_text (required), star_rating, review_date,
    branch_id. Extra columns are ignored. Returns (rows, errors) - a bad row is
    skipped and reported rather than failing the whole upload, because a single
    malformed line in a 3,000-row export should not cost the user the upload.
    """
    errors: list[str] = []
    rows: list[dict] = []

    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError:
        try:
            text = content.decode("latin-1")
        except Exception:  # noqa: BLE001
            return [], ["File is not valid UTF-8 or Latin-1 text."]

    reader = csv.DictReader(io.StringIO(text))
    if reader.fieldnames is None or "review_text" not in reader.fieldnames:
        return [], ["CSV must have a 'review_text' column. "
                    f"Found: {reader.fieldnames}"]

    for line_no, raw in enumerate(reader, start=2):
        if len(rows) >= max_rows:
            errors.append(f"Stopped at {max_rows} rows - the rest of the file was ignored.")
            break

        text_value = (raw.get("review_text") or "").strip()
        if len(text_value) < 5:
            errors.append(f"Line {line_no}: review_text missing or too short - skipped.")
            continue

        row: dict = {"review_text": text_value, "source": "csv_upload"}

        stars = (raw.get("star_rating") or "").strip()
        if stars:
            try:
                value = int(float(stars))
                row["star_rating"] = value if 1 <= value <= 5 else None
                if row["star_rating"] is None:
                    errors.append(f"Line {line_no}: star_rating {stars} out of range - ignored.")
            except ValueError:
                errors.append(f"Line {line_no}: star_rating '{stars}' is not a number - ignored.")

        raw_date = (raw.get("review_date") or "").strip()
        if raw_date:
            parsed = None
            for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%Y/%m/%d"):
                try:
                    parsed = datetime.strptime(raw_date[:10], fmt).date()
                    break
                except ValueError:
                    continue
            if parsed:
                row["review_date"] = parsed
            else:
                errors.append(f"Line {line_no}: unreadable date '{raw_date}' - ignored.")

        branch = (raw.get("branch_id") or "").strip()
        if branch:
            try:
                row["branch_id"] = int(branch)
            except ValueError:
                errors.append(f"Line {line_no}: branch_id '{branch}' is not a number - ignored.")

        rows.append(row)

    return rows, errors
