"""Aggregate queries behind the dashboard.

All of these do the counting in SQL rather than pulling rows into Python. With
a few hundred reviews it makes no difference; at fifty thousand it is the
difference between a dashboard that loads and one that times out.
"""

from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy import Select, and_, case, func, select
from sqlalchemy.orm import Session

from app.models import Branch, Prediction, Review, ReviewAspect


def _scoped(stmt: Select, restaurant_id: int | None,
            start: date | None, end: date | None) -> Select:
    """Apply the filters every dashboard query shares."""
    if restaurant_id is not None:
        stmt = stmt.where(Review.restaurant_id == restaurant_id)
    if start is not None:
        stmt = stmt.where(Review.review_date >= start)
    if end is not None:
        stmt = stmt.where(Review.review_date <= end)
    return stmt


def summary(db: Session, restaurant_id: int | None = None,
            start: date | None = None, end: date | None = None) -> dict:
    total = db.scalar(_scoped(select(func.count(Review.review_id)), restaurant_id, start, end)) or 0

    sentiment_rows = db.execute(
        _scoped(
            select(Prediction.sentiment, func.count())
            .join(Review, Review.review_id == Prediction.review_id),
            restaurant_id, start, end,
        ).group_by(Prediction.sentiment)
    ).all()
    sentiment = {"positive": 0, "neutral": 0, "negative": 0}
    for label, count in sentiment_rows:
        sentiment[label] = count

    avg_stars = db.scalar(
        _scoped(select(func.avg(Review.star_rating)), restaurant_id, start, end)
        .where(Review.star_rating.isnot(None))
    )

    high_urgency = db.scalar(
        _scoped(
            select(func.count())
            .select_from(Prediction)
            .join(Review, Review.review_id == Prediction.review_id),
            restaurant_id, start, end,
        ).where(Prediction.urgency == "high")
    ) or 0

    complaints = db.execute(
        _scoped(
            select(ReviewAspect.aspect, func.count().label("n"))
            .join(Review, Review.review_id == ReviewAspect.review_id),
            restaurant_id, start, end,
        )
        .where(ReviewAspect.aspect_sentiment == "negative")
        .group_by(ReviewAspect.aspect)
        .order_by(func.count().desc())
        .limit(5)
    ).all()

    return {
        "total_reviews": total,
        "analysed_reviews": sum(sentiment.values()),
        "sentiment": sentiment,
        "average_star_rating": round(float(avg_stars), 2) if avg_stars is not None else None,
        "high_urgency_open": high_urgency,
        "top_complaint_aspects": [{"aspect": a, "count": n} for a, n in complaints],
    }


def trends(db: Session, restaurant_id: int | None = None, days: int = 90) -> list[dict]:
    """Daily sentiment counts over the last `days` days."""
    start = date.today() - timedelta(days=days)

    rows = db.execute(
        _scoped(
            select(
                Review.review_date,
                func.sum(case((Prediction.sentiment == "positive", 1), else_=0)),
                func.sum(case((Prediction.sentiment == "neutral", 1), else_=0)),
                func.sum(case((Prediction.sentiment == "negative", 1), else_=0)),
                func.count(),
            ).join(Prediction, Prediction.review_id == Review.review_id),
            restaurant_id, start, None,
        )
        .group_by(Review.review_date)
        .order_by(Review.review_date)
    ).all()

    return [
        {"period": str(day), "positive": int(p or 0), "neutral": int(n or 0),
         "negative": int(neg or 0), "total": int(t or 0)}
        for day, p, n, neg, t in rows
    ]


def aspect_performance(db: Session, restaurant_id: int | None = None) -> list[dict]:
    rows = db.execute(
        _scoped(
            select(
                ReviewAspect.aspect,
                func.sum(case((ReviewAspect.aspect_sentiment == "positive", 1), else_=0)),
                func.sum(case((ReviewAspect.aspect_sentiment == "neutral", 1), else_=0)),
                func.sum(case((ReviewAspect.aspect_sentiment == "negative", 1), else_=0)),
                func.count(),
            ).join(Review, Review.review_id == ReviewAspect.review_id),
            restaurant_id, None, None,
        )
        .group_by(ReviewAspect.aspect)
        .order_by(func.count().desc())
    ).all()

    out = []
    for aspect, pos, neu, neg, total in rows:
        pos, neu, neg, total = int(pos or 0), int(neu or 0), int(neg or 0), int(total or 0)
        out.append({
            "aspect": aspect, "positive": pos, "neutral": neu, "negative": neg,
            "total": total,
            "negative_share": round(neg / total, 3) if total else 0.0,
        })
    return out


def branch_performance(db: Session, restaurant_id: int | None = None) -> list[dict]:
    """Best and worst branches by share of negative reviews."""
    rows = db.execute(
        _scoped(
            select(
                Branch.branch_id, Branch.branch_name, Branch.city,
                func.sum(case((Prediction.sentiment == "negative", 1), else_=0)),
                func.count(),
            )
            .select_from(Branch)
            .join(Review, Review.branch_id == Branch.branch_id)
            .join(Prediction, Prediction.review_id == Review.review_id),
            restaurant_id, None, None,
        )
        .group_by(Branch.branch_id, Branch.branch_name, Branch.city)
        .order_by(func.count().desc())
    ).all()

    return [
        {
            "branch_id": bid, "branch_name": name, "city": city,
            "negative": int(neg or 0), "total": int(total or 0),
            "negative_share": round(int(neg or 0) / int(total), 3) if total else 0.0,
        }
        for bid, name, city, neg, total in rows
    ]


def high_urgency_alerts(db: Session, restaurant_id: int | None = None,
                        limit: int = 50) -> list[Review]:
    stmt = (
        select(Review)
        .join(Prediction, Prediction.review_id == Review.review_id)
        .where(Prediction.urgency == "high")
        .order_by(Review.created_at.desc())
        .limit(limit)
    )
    if restaurant_id is not None:
        stmt = stmt.where(Review.restaurant_id == restaurant_id)
    return list(db.scalars(stmt).unique())
