"""Password hashing and JWT issuing/verification."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.models import User


def hash_password(plain: str) -> str:
    """bcrypt with a per-password salt. Never store or log the plain password."""
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except ValueError:
        # malformed hash in the database - treat as a failed login, not a crash
        return False


def create_access_token(user: User) -> tuple[str, int]:
    """Return (token, seconds_until_expiry)."""
    expires_in = settings.access_token_expire_minutes * 60
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user.user_id),
        "email": user.email,
        "role": user.role,
        "restaurant_id": user.restaurant_id,
        "iat": now,
        "exp": now + timedelta(seconds=expires_in),
    }
    token = jwt.encode(payload, settings.secret_key, algorithm=settings.algorithm)
    return token, expires_in


def decode_token(token: str) -> dict:
    """Raises jwt.PyJWTError if the token is invalid or expired."""
    return jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])


def authenticate(db: Session, email: str, password: str) -> User | None:
    user = db.scalar(select(User).where(User.email == email.lower()))
    if user is None:
        # Hash anyway so a missing account and a wrong password take about the
        # same time - otherwise the response time leaks which emails exist.
        verify_password(password, "$2b$12$" + "x" * 53)
        return None
    if not verify_password(password, user.password_hash):
        return None
    return user
