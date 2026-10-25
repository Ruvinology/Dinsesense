"""Create demo data so the dashboard has something to show.

    cd backend
    python seed.py

Creates an admin, a manager, one restaurant with three branches, and a set of
reviews that exercise every sentiment, aspect and urgency path. Safe to re-run:
it skips anything that already exists.
"""

from __future__ import annotations

import random
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from sqlalchemy import select  # noqa: E402

from app.database.session import SessionLocal, create_all  # noqa: E402
from app.models import Branch, Restaurant, User  # noqa: E402
from app.schemas import ReviewCreate  # noqa: E402
from app.services import auth_service, review_service  # noqa: E402

ADMIN_EMAIL = "admin@dinesense.ai"
MANAGER_EMAIL = "manager@dinesense.ai"
DEMO_PASSWORD = "dinesense123"

SAMPLE_REVIEWS = [
    ("The food was excellent, but the service was extremely slow.", 3),
    ("Absolutely wonderful evening. The pasta was delicious and the staff were lovely.", 5),
    ("Found a piece of glass in my pasta and the manager just shrugged.", 1),
    ("Waited over an hour and the chicken came out raw. Never again.", 1),
    ("Decent food, fair prices, nothing that blew me away.", 3),
    ("The delivery driver was rude and the packaging leaked everywhere.", 2),
    ("Best burger in town. Fast service, generous portions, will be back.", 5),
    ("Overpriced for what you get. Tiny portions and the drinks cost more than the food.", 2),
    ("Cozy atmosphere and great music, though it got very noisy after eight.", 4),
    ("I got food poisoning after eating here on Saturday.", 1),
    ("Staff were friendly and the restroom was spotless. Impressed.", 5),
    ("They charged me twice for the same meal and nobody would help.", 1),
    ("Food came out cold. Sent it back and the replacement was worse.", 2),
    ("Lovely little cafe. The coffee is good and the cakes are fresh.", 5),
    ("Service was fine but the table next to us waited 40 minutes for drinks.", 3),
    ("Portions are generous and the price is reasonable for the area.", 4),
    ("Dirty tables, sticky menus, and a fly in my drink.", 1),
    ("Quick lunch stop, sandwiches were fresh, no complaints.", 4),
]


def main() -> None:
    create_all()
    db = SessionLocal()
    random.seed(7)

    try:
        restaurant = db.scalar(select(Restaurant).where(Restaurant.name == "Spice Garden"))
        if restaurant is None:
            restaurant = Restaurant(
                name="Spice Garden",
                description="Demo restaurant group used to populate the dashboard.",
            )
            db.add(restaurant)
            db.commit()
            db.refresh(restaurant)
            print(f"Created restaurant: {restaurant.name}")

        branch_specs = [
            ("Colombo 03", "Colombo", "42 Galle Road, Colombo 03"),
            ("Kandy City", "Kandy", "18 Peradeniya Road, Kandy"),
            ("Galle Fort", "Galle", "7 Church Street, Galle"),
        ]
        branches = []
        for name, city, address in branch_specs:
            branch = db.scalar(
                select(Branch).where(
                    Branch.restaurant_id == restaurant.restaurant_id,
                    Branch.branch_name == name,
                )
            )
            if branch is None:
                branch = Branch(restaurant_id=restaurant.restaurant_id,
                                branch_name=name, city=city, address=address)
                db.add(branch)
                db.commit()
                db.refresh(branch)
                print(f"Created branch: {name}")
            branches.append(branch)

        for email, name, role in (
            (ADMIN_EMAIL, "Demo Admin", "admin"),
            (MANAGER_EMAIL, "Demo Manager", "manager"),
        ):
            if db.scalar(select(User).where(User.email == email)) is None:
                db.add(User(
                    name=name, email=email,
                    password_hash=auth_service.hash_password(DEMO_PASSWORD),
                    role=role,
                    restaurant_id=None if role == "admin" else restaurant.restaurant_id,
                ))
                db.commit()
                print(f"Created {role}: {email}")

        from app.models import Review
        existing = db.scalar(select(Review).where(Review.source == "seed"))
        if existing is not None:
            print("Reviews already seeded - skipping. Delete dinesense.db to start over.")
            return

        print(f"\nAnalysing and storing {len(SAMPLE_REVIEWS)} reviews "
              "(the model loads on the first one, so this takes a moment)...")

        for i, (text, stars) in enumerate(SAMPLE_REVIEWS):
            payload = ReviewCreate(
                restaurant_id=restaurant.restaurant_id,
                branch_id=random.choice(branches).branch_id,
                review_text=text,
                star_rating=stars,
                source="seed",
                review_date=date.today() - timedelta(days=random.randrange(0, 60)),
            )
            review, _ = review_service.analyse_and_store(db, payload)
            pred = review.latest_prediction
            print(f"  {i + 1:2}. {pred.sentiment:<8} {pred.urgency:<6} {text[:52]}...")

        print("\nSeed complete.")
        print(f"  Admin   : {ADMIN_EMAIL} / {DEMO_PASSWORD}")
        print(f"  Manager : {MANAGER_EMAIL} / {DEMO_PASSWORD}")
        print("\nStart the API with:  uvicorn app.main:app --reload")

    finally:
        db.close()


if __name__ == "__main__":
    main()
