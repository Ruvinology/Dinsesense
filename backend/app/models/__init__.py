"""SQLAlchemy ORM models for DineSense AI.

Schema shape follows the project spec. The important design decision is that
`predictions` is a separate table from `reviews`: a review is a fact the
customer gave us and never changes, while a prediction is this model version's
opinion about it. Keeping them apart means you can re-analyse the whole history
with a better model later without touching or losing the original reviews.
"""

from __future__ import annotations

from datetime import date, datetime, timezone

from sqlalchemy import (
    Date, DateTime, Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.session import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Restaurant(Base):
    __tablename__ = "restaurants"

    restaurant_id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    branches: Mapped[list["Branch"]] = relationship(
        back_populates="restaurant", cascade="all, delete-orphan"
    )
    users: Mapped[list["User"]] = relationship(back_populates="restaurant")
    reviews: Mapped[list["Review"]] = relationship(back_populates="restaurant")


class Branch(Base):
    __tablename__ = "branches"

    branch_id: Mapped[int] = mapped_column(primary_key=True)
    restaurant_id: Mapped[int] = mapped_column(
        ForeignKey("restaurants.restaurant_id", ondelete="CASCADE"), index=True
    )
    branch_name: Mapped[str] = mapped_column(String(200), nullable=False)
    city: Mapped[str | None] = mapped_column(String(120))
    address: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    restaurant: Mapped[Restaurant] = relationship(back_populates="branches")
    reviews: Mapped[list["Review"]] = relationship(back_populates="branch")

    __table_args__ = (
        UniqueConstraint("restaurant_id", "branch_name", name="uq_branch_per_restaurant"),
    )


class User(Base):
    __tablename__ = "users"

    user_id: Mapped[int] = mapped_column(primary_key=True)
    restaurant_id: Mapped[int | None] = mapped_column(
        ForeignKey("restaurants.restaurant_id", ondelete="SET NULL"), index=True
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    # "admin" sees everything; "manager" is scoped to their own restaurant
    role: Mapped[str] = mapped_column(String(20), default="manager", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    restaurant: Mapped[Restaurant | None] = relationship(back_populates="users")


class Review(Base):
    __tablename__ = "reviews"

    review_id: Mapped[int] = mapped_column(primary_key=True)
    restaurant_id: Mapped[int] = mapped_column(
        ForeignKey("restaurants.restaurant_id", ondelete="CASCADE"), index=True
    )
    branch_id: Mapped[int | None] = mapped_column(
        ForeignKey("branches.branch_id", ondelete="SET NULL"), index=True
    )
    review_text: Mapped[str] = mapped_column(Text, nullable=False)
    star_rating: Mapped[int | None] = mapped_column(Integer)
    # where it came from: "web", "csv_upload", "yelp", "google", ...
    source: Mapped[str] = mapped_column(String(40), default="web")
    review_date: Mapped[date | None] = mapped_column(Date)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, index=True
    )

    restaurant: Mapped[Restaurant] = relationship(back_populates="reviews")
    branch: Mapped[Branch | None] = relationship(back_populates="reviews")
    predictions: Mapped[list["Prediction"]] = relationship(
        back_populates="review", cascade="all, delete-orphan",
        order_by="Prediction.predicted_at.desc()",
    )
    aspects: Mapped[list["ReviewAspect"]] = relationship(
        back_populates="review", cascade="all, delete-orphan"
    )

    @property
    def latest_prediction(self) -> "Prediction | None":
        return self.predictions[0] if self.predictions else None


class Prediction(Base):
    __tablename__ = "predictions"

    prediction_id: Mapped[int] = mapped_column(primary_key=True)
    review_id: Mapped[int] = mapped_column(
        ForeignKey("reviews.review_id", ondelete="CASCADE"), index=True
    )
    sentiment: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    sentiment_confidence: Mapped[float] = mapped_column(Float, nullable=False)
    urgency: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    urgency_reason: Mapped[str | None] = mapped_column(String(120))
    model_version: Mapped[str] = mapped_column(String(40), nullable=False)
    predicted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    review: Mapped[Review] = relationship(back_populates="predictions")

    __table_args__ = (
        Index("ix_predictions_urgency_date", "urgency", "predicted_at"),
    )


class ReviewAspect(Base):
    __tablename__ = "review_aspects"

    review_aspect_id: Mapped[int] = mapped_column(primary_key=True)
    review_id: Mapped[int] = mapped_column(
        ForeignKey("reviews.review_id", ondelete="CASCADE"), index=True
    )
    aspect: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    aspect_sentiment: Mapped[str] = mapped_column(String(20), nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)

    review: Mapped[Review] = relationship(back_populates="aspects")


__all__ = ["Restaurant", "Branch", "User", "Review", "Prediction", "ReviewAspect"]
