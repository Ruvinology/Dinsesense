# DineSense AI backend
#
# Built from the PROJECT ROOT, not from backend/, because the API imports the
# training code in ml/:
#     docker build -f backend/Dockerfile -t dinesense-api .

FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    TF_CPP_MIN_LOG_LEVEL=2

WORKDIR /srv

# System deps kept minimal - slim image plus what psycopg needs
RUN apt-get update && apt-get install -y --no-install-recommends \
        libpq5 curl \
    && rm -rf /var/lib/apt/lists/*

# Install dependencies first so Docker caches this layer across code changes
COPY backend/requirements.txt /srv/backend/requirements.txt
COPY requirements.txt /srv/requirements.txt
RUN pip install --no-cache-dir -r /srv/backend/requirements.txt \
    && pip install --no-cache-dir \
        "tensorflow-cpu>=2.16,<2.20" "scikit-learn>=1.4" "pandas>=2.1" "joblib>=1.3"

# Application code
COPY backend/ /srv/backend/
COPY ml/ /srv/ml/

# Run as a non-root user
RUN useradd --create-home --uid 1000 appuser && chown -R appuser:appuser /srv
USER appuser

WORKDIR /srv/backend
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=90s --retries=3 \
    CMD curl -fsS http://localhost:8000/health || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
