"""Shared FastAPI dependencies: current user, role checks, restaurant scoping."""

from __future__ import annotations

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.models import User
from app.services import auth_service

bearer = HTTPBearer(auto_error=False)

CREDENTIALS_ERROR = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Not authenticated",
    headers={"WWW-Authenticate": "Bearer"},
)


def current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: Session = Depends(get_db),
) -> User:
    if credentials is None:
        raise CREDENTIALS_ERROR
    try:
        payload = auth_service.decode_token(credentials.credentials)
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired - please log in again.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.PyJWTError:
        raise CREDENTIALS_ERROR

    user = db.get(User, int(payload.get("sub", 0)))
    if user is None:
        raise CREDENTIALS_ERROR
    return user


def require_admin(user: User = Depends(current_user)) -> User:
    if user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This action requires an administrator account.",
        )
    return user


def scoped_restaurant_id(user: User, requested: int | None) -> int | None:
    """Work out which restaurant this user may query.

    An admin may ask for any restaurant, or for all of them (None). A manager is
    pinned to their own restaurant regardless of what they ask for - without
    this, any manager could read a competitor's dashboard by changing a query
    parameter.
    """
    if user.role == "admin":
        return requested
    if requested is not None and requested != user.restaurant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only view data for your own restaurant.",
        )
    return user.restaurant_id
