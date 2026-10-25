"""DineSense AI - FastAPI application entry point.

Run it:
    cd backend
    uvicorn app.main:app --reload

Then open http://127.0.0.1:8000/docs for the interactive API documentation.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import analytics, auth, restaurants, reviews
from app.config import settings
from app.database.session import create_all
from app.ml_service import predictor

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("dinesense")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting %s", settings.app_name)
    create_all()
    logger.info("Database ready: %s",
                "SQLite (development)" if settings.is_sqlite else "PostgreSQL")

    if settings.secret_is_default:
        logger.warning(
            "SECRET_KEY is still the development default. Anyone with this "
            "value can forge a login token. Set SECRET_KEY in backend/.env "
            "before deploying: python -c \"import secrets; "
            "print(secrets.token_urlsafe(48))\""
        )

    # Warm the model at startup so the first real request is not slow. A failure
    # here is logged but does not stop the API - every non-analysis endpoint
    # still works, and /health reports the problem.
    try:
        predictor.get_analyser()
        logger.info("Sentiment model loaded: %s", predictor.active_model_name())
    except Exception as exc:  # noqa: BLE001
        logger.warning("No sentiment model loaded (%s). "
                       "Analysis endpoints will return 503.", exc)

    yield
    logger.info("Shutting down.")


app = FastAPI(
    title=settings.app_name,
    description="Restaurant feedback intelligence: sentiment, aspects, urgency "
                "and recommended actions.",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix=settings.api_prefix)
app.include_router(restaurants.router, prefix=settings.api_prefix)
app.include_router(reviews.router, prefix=settings.api_prefix)
app.include_router(analytics.router, prefix=settings.api_prefix)


@app.get("/", tags=["meta"])
def root() -> dict:
    return {
        "service": settings.app_name,
        "docs": "/docs",
        "health": "/health",
    }


@app.get("/health", tags=["meta"])
def health() -> dict:
    """Liveness plus whether the model is actually usable."""
    model_ready = predictor.is_ready()
    return {
        "status": "ok",
        "database": "sqlite" if settings.is_sqlite else "postgresql",
        "model_ready": model_ready,
        "active_model": predictor.active_model_name(),
        "model_error": None if model_ready else predictor.load_error(),
    }
