"""Pydantic schemas: the validated shapes that cross the API boundary.

Request models validate what comes in; response models control what goes out.
Note that no response model ever contains `password_hash` - that is the point of
keeping them separate from the ORM models.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

Sentiment = Literal["positive", "neutral", "negative"]
Urgency = Literal["low", "medium", "high"]
Role = Literal["manager", "admin"]


# ---------------------------------------------------------------- auth

class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1)


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class UserCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    email: EmailStr
    password: str = Field(min_length=8, description="At least 8 characters.")
    role: Role = "manager"
    restaurant_id: int | None = None


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: int
    name: str
    email: EmailStr
    role: Role
    restaurant_id: int | None
    created_at: datetime


# ---------------------------------------------------------------- restaurants

class RestaurantCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str | None = None


class RestaurantOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    restaurant_id: int
    name: str
    description: str | None
    created_at: datetime


class BranchCreate(BaseModel):
    branch_name: str = Field(min_length=1, max_length=200)
    city: str | None = None
    address: str | None = None


class BranchOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    branch_id: int
    restaurant_id: int
    branch_name: str
    city: str | None
    address: str | None


# ---------------------------------------------------------------- reviews

class ReviewCreate(BaseModel):
    restaurant_id: int
    branch_id: int | None = None
    review_text: str = Field(min_length=5, max_length=10_000)
    star_rating: int | None = Field(default=None, ge=1, le=5)
    source: str = "web"
    review_date: date | None = None

    @field_validator("review_text")
    @classmethod
    def not_just_whitespace(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("review_text cannot be blank")
        return v.strip()


class AspectOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    aspect: str
    aspect_sentiment: Sentiment
    confidence: float


class PredictionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    sentiment: Sentiment
    sentiment_confidence: float
    urgency: Urgency
    urgency_reason: str | None
    model_version: str
    predicted_at: datetime


class ReviewOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    review_id: int
    restaurant_id: int
    branch_id: int | None
    review_text: str
    star_rating: int | None
    source: str
    review_date: date | None
    created_at: datetime
    prediction: PredictionOut | None = None
    aspects: list[AspectOut] = []
    recommendations: list[str] = []


class AnalyseRequest(BaseModel):
    """Analyse text without storing it - for the 'try a review' page."""
    review_text: str = Field(min_length=5, max_length=10_000)


class AnalyseResponse(BaseModel):
    sentiment: Sentiment
    confidence: float
    urgency: Urgency
    urgency_reason: str | None
    aspects: list[dict]
    recommendations: list[str]
    model_version: str


class BatchUploadResult(BaseModel):
    received: int
    stored: int
    skipped: int
    errors: list[str] = []


# ---------------------------------------------------------------- analytics

class SentimentCounts(BaseModel):
    positive: int = 0
    neutral: int = 0
    negative: int = 0


class AnalyticsSummary(BaseModel):
    total_reviews: int
    analysed_reviews: int
    sentiment: SentimentCounts
    average_star_rating: float | None
    high_urgency_open: int
    top_complaint_aspects: list[dict]


class TrendPoint(BaseModel):
    period: str
    positive: int
    neutral: int
    negative: int
    total: int


class AspectPerformance(BaseModel):
    aspect: str
    positive: int
    neutral: int
    negative: int
    total: int
    negative_share: float


class ModelMetrics(BaseModel):
    active_model: str
    model_version: str
    metrics: dict
    comparison: dict | None = None
