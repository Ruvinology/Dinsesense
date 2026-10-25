"""Restaurant and branch management."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import current_user, require_admin
from app.database.session import get_db
from app.models import Branch, Restaurant, User
from app.schemas import BranchCreate, BranchOut, RestaurantCreate, RestaurantOut

router = APIRouter(prefix="/restaurants", tags=["restaurants"])


@router.get("", response_model=list[RestaurantOut])
def list_restaurants(db: Session = Depends(get_db),
                     user: User = Depends(current_user)) -> list[Restaurant]:
    stmt = select(Restaurant).order_by(Restaurant.name)
    if user.role != "admin" and user.restaurant_id is not None:
        stmt = stmt.where(Restaurant.restaurant_id == user.restaurant_id)
    return list(db.scalars(stmt))


@router.post("", response_model=RestaurantOut, status_code=status.HTTP_201_CREATED,
             dependencies=[Depends(require_admin)])
def create_restaurant(payload: RestaurantCreate,
                      db: Session = Depends(get_db)) -> Restaurant:
    restaurant = Restaurant(name=payload.name, description=payload.description)
    db.add(restaurant)
    db.commit()
    db.refresh(restaurant)
    return restaurant


@router.get("/{restaurant_id}", response_model=RestaurantOut)
def get_restaurant(restaurant_id: int, db: Session = Depends(get_db),
                   user: User = Depends(current_user)) -> Restaurant:
    if user.role != "admin" and user.restaurant_id != restaurant_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN,
                            "You can only view your own restaurant.")
    restaurant = db.get(Restaurant, restaurant_id)
    if restaurant is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Restaurant not found.")
    return restaurant


@router.get("/{restaurant_id}/branches", response_model=list[BranchOut])
def list_branches(restaurant_id: int, db: Session = Depends(get_db),
                  user: User = Depends(current_user)) -> list[Branch]:
    if user.role != "admin" and user.restaurant_id != restaurant_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN,
                            "You can only view your own restaurant.")
    return list(db.scalars(
        select(Branch).where(Branch.restaurant_id == restaurant_id)
        .order_by(Branch.branch_name)
    ))


@router.post("/{restaurant_id}/branches", response_model=BranchOut,
             status_code=status.HTTP_201_CREATED, dependencies=[Depends(require_admin)])
def create_branch(restaurant_id: int, payload: BranchCreate,
                  db: Session = Depends(get_db)) -> Branch:
    if db.get(Restaurant, restaurant_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Restaurant not found.")

    branch = Branch(
        restaurant_id=restaurant_id,
        branch_name=payload.branch_name,
        city=payload.city,
        address=payload.address,
    )
    db.add(branch)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"This restaurant already has a branch called '{payload.branch_name}'.",
        )
    db.refresh(branch)
    return branch
