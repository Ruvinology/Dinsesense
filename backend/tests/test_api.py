"""End-to-end API tests against a throwaway SQLite database.

    cd backend
    python -m pytest tests/ -v

Covers the paths that matter: login, authorisation boundaries, review analysis,
CSV upload, and the analytics aggregates. The authorisation tests are the
important ones - a manager reading another restaurant's dashboard is the kind
of bug that looks fine in manual testing.
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

# Point at a temporary database BEFORE app modules read the settings
_tmp_db = Path(tempfile.mkdtemp()) / "test.db"
os.environ["DATABASE_URL"] = f"sqlite:///{_tmp_db}"
os.environ["SECRET_KEY"] = "test-secret"

from app.database.session import SessionLocal, create_all  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Branch, Restaurant, User  # noqa: E402
from app.services import auth_service  # noqa: E402

PASSWORD = "testpass123"


@pytest.fixture(scope="module")
def client():
    create_all()
    db = SessionLocal()

    r1 = Restaurant(name="Spice Garden")
    r2 = Restaurant(name="Rival Cafe")
    db.add_all([r1, r2])
    db.commit()

    db.add(Branch(restaurant_id=r1.restaurant_id, branch_name="Colombo 03", city="Colombo"))
    db.add_all([
        User(name="Admin", email="admin@test.com",
             password_hash=auth_service.hash_password(PASSWORD), role="admin"),
        User(name="Manager One", email="m1@test.com",
             password_hash=auth_service.hash_password(PASSWORD),
             role="manager", restaurant_id=r1.restaurant_id),
        User(name="Manager Two", email="m2@test.com",
             password_hash=auth_service.hash_password(PASSWORD),
             role="manager", restaurant_id=r2.restaurant_id),
    ])
    db.commit()
    # Read the ids out BEFORE closing - once the session is gone these
    # instances are detached and touching an attribute raises.
    ids = (r1.restaurant_id, r2.restaurant_id)
    db.close()

    with TestClient(app) as c:
        c.restaurant_ids = ids  # type: ignore[attr-defined]
        yield c


def token(client, email: str) -> str:
    resp = client.post("/api/auth/login", json={"email": email, "password": PASSWORD})
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


def auth(client, email: str) -> dict:
    return {"Authorization": f"Bearer {token(client, email)}"}


# ---------------------------------------------------------------- meta

def test_health(client):
    body = client.get("/health").json()
    assert body["status"] == "ok"
    assert "model_ready" in body


# ---------------------------------------------------------------- auth

def test_login_success(client):
    body = client.post("/api/auth/login",
                       json={"email": "admin@test.com", "password": PASSWORD}).json()
    assert body["token_type"] == "bearer"
    assert body["expires_in"] > 0


def test_login_wrong_password(client):
    resp = client.post("/api/auth/login",
                       json={"email": "admin@test.com", "password": "wrong"})
    assert resp.status_code == 401


def test_login_unknown_email_gives_same_error(client):
    """Must not reveal whether an account exists."""
    resp = client.post("/api/auth/login",
                       json={"email": "nobody@test.com", "password": PASSWORD})
    assert resp.status_code == 401
    assert resp.json()["detail"] == "Incorrect email or password."


def test_me_requires_token(client):
    assert client.get("/api/auth/me").status_code == 401


def test_me_returns_user_without_password(client):
    body = client.get("/api/auth/me", headers=auth(client, "m1@test.com")).json()
    assert body["email"] == "m1@test.com"
    assert "password_hash" not in body


def test_garbage_token_rejected(client):
    resp = client.get("/api/auth/me", headers={"Authorization": "Bearer not.a.token"})
    assert resp.status_code == 401


# ---------------------------------------------------------------- authorisation

def test_manager_cannot_create_restaurant(client):
    resp = client.post("/api/restaurants", json={"name": "Sneaky"},
                       headers=auth(client, "m1@test.com"))
    assert resp.status_code == 403


def test_admin_can_create_restaurant(client):
    resp = client.post("/api/restaurants", json={"name": "New Place"},
                       headers=auth(client, "admin@test.com"))
    assert resp.status_code == 201


def test_manager_cannot_read_other_restaurant(client):
    _, r2 = client.restaurant_ids
    resp = client.get(f"/api/restaurants/{r2}", headers=auth(client, "m1@test.com"))
    assert resp.status_code == 403


def test_manager_analytics_scoped_to_own_restaurant(client):
    """Asking for someone else's restaurant must be refused, not silently served."""
    _, r2 = client.restaurant_ids
    resp = client.get(f"/api/analytics/summary?restaurant_id={r2}",
                      headers=auth(client, "m1@test.com"))
    assert resp.status_code == 403


# ---------------------------------------------------------------- reviews

def test_submit_review_returns_analysis(client):
    r1, _ = client.restaurant_ids
    resp = client.post("/api/reviews", json={
        "restaurant_id": r1,
        "review_text": "The food was excellent, but the service was extremely slow.",
        "star_rating": 3,
    })
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["prediction"]["sentiment"] in {"positive", "neutral", "negative"}
    assert 0.0 <= body["prediction"]["sentiment_confidence"] <= 1.0
    aspects = {a["aspect"] for a in body["aspects"]}
    assert "food_quality" in aspects


def test_food_safety_review_flagged_high_urgency(client):
    """The escalation path, end to end through the API."""
    r1, _ = client.restaurant_ids
    resp = client.post("/api/reviews", json={
        "restaurant_id": r1,
        "review_text": "I got food poisoning after eating here on Saturday.",
        "star_rating": 1,
    })
    assert resp.status_code == 201
    body = resp.json()
    assert body["prediction"]["urgency"] == "high"
    assert body["prediction"]["sentiment"] == "negative"
    assert any("senior management" in r for r in body["recommendations"])


def test_submit_review_unknown_restaurant(client):
    resp = client.post("/api/reviews",
                       json={"restaurant_id": 99999, "review_text": "Lovely food here"})
    assert resp.status_code == 404


def test_blank_review_rejected(client):
    r1, _ = client.restaurant_ids
    resp = client.post("/api/reviews",
                       json={"restaurant_id": r1, "review_text": "     "})
    assert resp.status_code == 422


def test_analyse_without_storing(client):
    resp = client.post("/api/reviews/analyse",
                       json={"review_text": "Rude staff and a dirty bathroom."})
    assert resp.status_code == 200
    body = resp.json()
    assert body["sentiment"] == "negative"
    assert body["recommendations"]


def test_list_reviews_requires_auth(client):
    assert client.get("/api/reviews").status_code == 401


def test_list_and_filter_reviews(client):
    headers = auth(client, "m1@test.com")
    assert client.get("/api/reviews", headers=headers).status_code == 200
    resp = client.get("/api/reviews?urgency=high", headers=headers)
    assert resp.status_code == 200
    assert all(r["prediction"]["urgency"] == "high" for r in resp.json())


def test_csv_batch_upload(client):
    r1, _ = client.restaurant_ids
    csv_bytes = (
        "review_text,star_rating,review_date\n"
        "The pasta was cold and the waiter ignored us,2,2024-03-01\n"
        "Wonderful evening great staff and lovely food,5,2024-03-02\n"
        ",5,2024-03-03\n"                       # blank text - should be skipped
        "Nice enough place nothing special,3,not-a-date\n"   # bad date - kept, date ignored
    ).encode()

    resp = client.post(
        f"/api/reviews/batch?restaurant_id={r1}",
        files={"file": ("reviews.csv", csv_bytes, "text/csv")},
        headers=auth(client, "m1@test.com"),
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["stored"] == 3
    assert any("skipped" in e for e in body["errors"])


def test_csv_missing_column_reports_clearly(client):
    r1, _ = client.restaurant_ids
    resp = client.post(
        f"/api/reviews/batch?restaurant_id={r1}",
        files={"file": ("bad.csv", b"comment,stars\nfoo,5\n", "text/csv")},
        headers=auth(client, "m1@test.com"),
    )
    assert resp.status_code == 200
    assert "review_text" in resp.json()["errors"][0]


def test_non_csv_rejected(client):
    r1, _ = client.restaurant_ids
    resp = client.post(
        f"/api/reviews/batch?restaurant_id={r1}",
        files={"file": ("notes.txt", b"hello", "text/plain")},
        headers=auth(client, "m1@test.com"),
    )
    assert resp.status_code == 400


# ---------------------------------------------------------------- analytics

def test_analytics_summary(client):
    body = client.get("/api/analytics/summary",
                      headers=auth(client, "m1@test.com")).json()
    assert body["total_reviews"] > 0
    assert set(body["sentiment"]) == {"positive", "neutral", "negative"}
    assert body["high_urgency_open"] >= 1


def test_analytics_aspects(client):
    body = client.get("/api/analytics/aspects",
                      headers=auth(client, "m1@test.com")).json()
    assert body
    for row in body:
        assert 0.0 <= row["negative_share"] <= 1.0
        assert row["total"] == row["positive"] + row["neutral"] + row["negative"]


def test_analytics_trends(client):
    body = client.get("/api/analytics/trends?days=365",
                      headers=auth(client, "m1@test.com")).json()
    for point in body:
        assert point["total"] == point["positive"] + point["neutral"] + point["negative"]


def test_alerts_only_high_urgency(client):
    body = client.get("/api/alerts", headers=auth(client, "m1@test.com")).json()
    assert body
    assert all(r["prediction"]["urgency"] == "high" for r in body)


def test_model_metrics_public(client):
    body = client.get("/api/model/metrics").json()
    # These are the registry keys in ml/predict.py - if that list changes, this
    # test should fail so the two stay in step.
    assert body["active_model"] in {"bilstm_v2", "bilstm_v1", "baseline", "none"}
