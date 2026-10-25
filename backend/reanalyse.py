"""
Re-run the analysis over reviews already in the database.

Use this after changing the model or the urgency rules - existing reviews keep
whatever verdict they were given when they arrived, so a rule fix does not
reach them until you re-analyse.

    cd backend
    python reanalyse.py                 # show what would change, change nothing
    python reanalyse.py --apply         # write the new predictions
    python reanalyse.py --apply --only-urgency-changed

This is the payoff from keeping `predictions` in its own table: the guest's
words are never touched, and every re-analysis adds a new prediction row rather
than overwriting history. You can always see what the old model said.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from sqlalchemy import select  # noqa: E402
from sqlalchemy.orm import selectinload  # noqa: E402

from app.database.session import SessionLocal, create_all  # noqa: E402
from app.ml_service import predictor  # noqa: E402
from app.models import Prediction, Review, ReviewAspect  # noqa: E402

ARROW = "->"


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Re-analyse stored reviews with the current model and rules.")
    parser.add_argument("--apply", action="store_true",
                        help="Actually write the new predictions (default is a dry run).")
    parser.add_argument("--only-urgency-changed", action="store_true",
                        help="Only report/write rows whose urgency changed.")
    parser.add_argument("--limit", type=int, default=None,
                        help="Process at most this many reviews.")
    args = parser.parse_args()

    create_all()
    db = SessionLocal()

    try:
        stmt = (
            select(Review)
            .options(selectinload(Review.predictions), selectinload(Review.aspects))
            .order_by(Review.review_id)
        )
        if args.limit:
            stmt = stmt.limit(args.limit)
        reviews = list(db.scalars(stmt).unique())

        if not reviews:
            print("No reviews in the database.")
            return

        print(f"Active model: {predictor.active_model_name()}")
        print(f"Re-analysing {len(reviews)} reviews "
              f"({'APPLYING CHANGES' if args.apply else 'dry run - nothing will be written'})\n")

        changed_urgency = 0
        changed_sentiment = 0
        written = 0

        for review in reviews:
            old = review.latest_prediction
            try:
                result = predictor.analyse(review.review_text)
            except Exception as exc:  # noqa: BLE001
                print(f"  #{review.review_id}: FAILED - {exc}")
                continue

            old_urgency = old.urgency if old else None
            old_sentiment = old.sentiment if old else None
            urgency_moved = old_urgency != result["urgency"]
            sentiment_moved = old_sentiment != result["sentiment"]

            if urgency_moved:
                changed_urgency += 1
            if sentiment_moved:
                changed_sentiment += 1

            if args.only_urgency_changed and not urgency_moved:
                continue

            if urgency_moved or sentiment_moved:
                bits = []
                if urgency_moved:
                    bits.append(f"urgency {old_urgency} {ARROW} {result['urgency']}")
                if sentiment_moved:
                    bits.append(f"sentiment {old_sentiment} {ARROW} {result['sentiment']}")
                print(f"  #{review.review_id}: {' | '.join(bits)}")
                print(f"      {review.review_text[:90]}")
                if result.get("urgency_reason"):
                    print(f"      reason: {result['urgency_reason']}")

            if not args.apply:
                continue

            # New prediction row - the old one stays as history.
            db.add(Prediction(
                review_id=review.review_id,
                sentiment=result["sentiment"],
                sentiment_confidence=result["confidence"],
                urgency=result["urgency"],
                urgency_reason=result.get("urgency_reason"),
                model_version=result.get("model_version", "v1"),
            ))

            # Aspects are a current view, not history - replace them.
            for aspect in review.aspects:
                db.delete(aspect)
            for aspect in result.get("aspects", []):
                db.add(ReviewAspect(
                    review_id=review.review_id,
                    aspect=aspect["aspect"],
                    aspect_sentiment=aspect["sentiment"],
                    confidence=aspect["confidence"],
                ))
            written += 1

        if args.apply:
            db.commit()

        print(f"\n{len(reviews)} reviews checked")
        print(f"  urgency changed   : {changed_urgency}")
        print(f"  sentiment changed : {changed_sentiment}")
        if args.apply:
            print(f"  predictions written: {written}")
        else:
            print("\nDry run - nothing was written. Re-run with --apply to save.")

    finally:
        db.close()


if __name__ == "__main__":
    main()
