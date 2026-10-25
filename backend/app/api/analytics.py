"""Dashboard analytics, alerts and model metrics."""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import current_user, scoped_restaurant_id
from app.database.session import get_db
from app.ml_service import predictor
from app.models import User
from app.schemas import (
    AnalyticsSummary, AspectPerformance, ModelMetrics, ReviewOut, TrendPoint,
)
from app.services import analytics_service

router = APIRouter(tags=["analytics"])


@router.get("/analytics/summary", response_model=AnalyticsSummary)
def analytics_summary(
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
    restaurant_id: int | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
) -> AnalyticsSummary:
    scoped = scoped_restaurant_id(user, restaurant_id)
    return AnalyticsSummary(**analytics_service.summary(db, scoped, start_date, end_date))


@router.get("/analytics/trends", response_model=list[TrendPoint])
def analytics_trends(
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
    restaurant_id: int | None = None,
    days: int = Query(90, ge=1, le=730),
) -> list[TrendPoint]:
    scoped = scoped_restaurant_id(user, restaurant_id)
    return [TrendPoint(**p) for p in analytics_service.trends(db, scoped, days)]


@router.get("/analytics/aspects", response_model=list[AspectPerformance])
def analytics_aspects(
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
    restaurant_id: int | None = None,
) -> list[AspectPerformance]:
    scoped = scoped_restaurant_id(user, restaurant_id)
    return [AspectPerformance(**a) for a in analytics_service.aspect_performance(db, scoped)]


@router.get("/analytics/branches")
def analytics_branches(
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
    restaurant_id: int | None = None,
) -> list[dict]:
    scoped = scoped_restaurant_id(user, restaurant_id)
    return analytics_service.branch_performance(db, scoped)


@router.get("/alerts", response_model=list[ReviewOut])
def alerts(
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
    restaurant_id: int | None = None,
    limit: int = Query(50, ge=1, le=200),
) -> list[ReviewOut]:
    """High-urgency complaints, newest first. The dashboard's headline feed."""
    from app.api.reviews import _to_out

    scoped = scoped_restaurant_id(user, restaurant_id)
    reviews = analytics_service.high_urgency_alerts(db, scoped, limit)
    return [_to_out(r) for r in reviews]


@router.get("/model/metrics", response_model=ModelMetrics)
def model_metrics() -> ModelMetrics:
    """What model is serving, and how well it scored. Public - no secrets here."""
    metrics = predictor.read_metrics()
    return ModelMetrics(
        active_model=predictor.active_model_name(),
        model_version="v1",
        metrics={k: v for k, v in metrics.items() if k != "comparison"},
        comparison=metrics.get("comparison"),
    )
