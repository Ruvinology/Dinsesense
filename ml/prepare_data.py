"""
Step 1 of the DineSense AI pipeline.

Turns the raw Yelp Open Dataset tar into a restaurant-only, sentiment-labelled
CSV that the rest of the pipeline trains on.

    python ml/prepare_data.py                     # default 20,000 per class
    python ml/prepare_data.py --per-class 60000   # bigger set, slower training

Uses the Python standard library only - no pandas, no installs needed.

By default it STREAMS the JSON straight out of the tar, so it never writes the
5 GB review.json to disk. Pass --extract if you would rather have the raw JSON
files on disk (needs ~6 GB free).

Input   D:\\DineSense\\Yelp-JSON\\Yelp JSON\\yelp_dataset.tar
Output  D:\\DineSense\\data\\processed\\restaurant_reviews.csv
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import sys
import tarfile
import time
from collections import Counter
from pathlib import Path

# --------------------------------------------------------------------------
# Configuration
# --------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"
OUTPUT_CSV = PROCESSED_DIR / "restaurant_reviews.csv"

TAR_CANDIDATES = [
    PROJECT_ROOT / "Yelp-JSON" / "Yelp JSON" / "yelp_dataset.tar",
    DATA_DIR / "Yelp-JSON" / "Yelp JSON" / "yelp_dataset.tar",
    DATA_DIR / "yelp_dataset.tar",
]

BUSINESS_NAME = "yelp_academic_dataset_business.json"
REVIEW_NAME = "yelp_academic_dataset_review.json"

# Categories that count as "a place where you eat".
FOOD_CATEGORIES = {
    "Restaurants", "Food", "Cafes", "Coffee & Tea", "Bakeries", "Fast Food",
    "Pizza", "Burgers", "Sandwiches", "Breakfast & Brunch", "Bars", "Desserts",
    "Ice Cream & Frozen Yogurt", "Juice Bars & Smoothies", "Diners",
    "Food Trucks", "Delis", "Seafood", "Steakhouses", "Sushi Bars", "Buffets",
    "Caterers",
}

# star rating -> sentiment label.  1,2 -> negative | 3 -> neutral | 4,5 -> positive
STAR_TO_SENTIMENT = {1: "negative", 2: "negative", 3: "neutral",
                     4: "positive", 5: "positive"}

DEFAULT_PER_CLASS = 20_000
MIN_CHARS = 20
MAX_CHARS = 5_000


# --------------------------------------------------------------------------
# Locating things inside the tar
# --------------------------------------------------------------------------

def find_tar() -> Path:
    for candidate in TAR_CANDIDATES:
        if candidate.exists():
            return candidate
    sys.exit(
        "ERROR: yelp_dataset.tar not found. Looked in:\n  "
        + "\n  ".join(str(c) for c in TAR_CANDIDATES)
    )


def open_member(tar_path: Path, filename: str):
    """Return a text-mode line iterator over one file inside the tar."""
    tar = tarfile.open(tar_path, "r")
    for member in tar:
        if Path(member.name).name == filename:
            raw = tar.extractfile(member)
            if raw is None:
                break
            return tar, io.TextIOWrapper(raw, encoding="utf-8", errors="replace")
    tar.close()
    sys.exit(f"ERROR: {filename} not found inside {tar_path.name}")


def extract_to_disk(tar_path: Path, dest: Path) -> None:
    """Optional: write the two JSON files out to data/raw/ (needs ~6 GB)."""
    dest.mkdir(parents=True, exist_ok=True)
    wanted = {BUSINESS_NAME, REVIEW_NAME}
    with tarfile.open(tar_path, "r") as tar:
        for member in tar:
            name = Path(member.name).name
            if name not in wanted:
                continue
            target = dest / name
            if target.exists():
                print(f"[extract] {name} already present - skipping.")
                continue
            print(f"[extract] Writing {name} ({member.size / 1e9:.2f} GB)...")
            source = tar.extractfile(member)
            if source is None:
                continue
            with open(target, "wb") as out:
                while chunk := source.read(8 * 1024 * 1024):
                    out.write(chunk)
            print(f"[extract] Done -> {target}")


# --------------------------------------------------------------------------
# Pass 1: which businesses are places to eat
# --------------------------------------------------------------------------

def load_restaurant_ids(tar_path: Path) -> dict[str, dict]:
    print(f"[business] Reading {BUSINESS_NAME} from the tar...")
    tar, stream = open_member(tar_path, BUSINESS_NAME)
    restaurants: dict[str, dict] = {}
    total = 0
    try:
        for line in stream:
            total += 1
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            raw_categories = row.get("categories") or ""
            categories = {c.strip() for c in raw_categories.split(",") if c.strip()}
            if not categories & FOOD_CATEGORIES:
                continue
            restaurants[row["business_id"]] = {
                "name": row.get("name", ""),
                "city": row.get("city", ""),
                "state": row.get("state", ""),
            }
    finally:
        stream.close()
        tar.close()

    print(f"[business] {len(restaurants):,} food businesses out of {total:,} total.")
    if not restaurants:
        sys.exit("ERROR: no food businesses matched. Check FOOD_CATEGORIES.")
    return restaurants


# --------------------------------------------------------------------------
# Pass 2: stream reviews, keep a balanced sample
# --------------------------------------------------------------------------

def build_csv(tar_path: Path, restaurants: dict[str, dict],
              output_csv: Path, per_class: int) -> None:
    output_csv.parent.mkdir(parents=True, exist_ok=True)
    target_total = per_class * 3
    kept: Counter[str] = Counter()
    seen = 0
    start = time.time()

    print(f"[reviews] Streaming {REVIEW_NAME} (~5 GB). Target {per_class:,} per class.")
    print("[reviews] This takes roughly 5-15 minutes. Progress every 500k reviews.\n")

    tar, stream = open_member(tar_path, REVIEW_NAME)
    try:
        with open(output_csv, "w", encoding="utf-8", newline="") as out:
            writer = csv.writer(out)
            writer.writerow([
                "review_id", "business_id", "business_name", "city", "state",
                "star_rating", "sentiment", "review_date", "review_text",
            ])

            for line in stream:
                seen += 1
                if seen % 500_000 == 0:
                    rate = seen / max(time.time() - start, 1)
                    print(f"[reviews] {seen:,} scanned | kept {sum(kept.values()):,} "
                          f"{dict(kept)} | {rate:,.0f}/s")

                if sum(kept.values()) >= target_total:
                    print("[reviews] All three classes full - stopping early.")
                    break

                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    continue

                business = restaurants.get(row.get("business_id"))
                if business is None:
                    continue

                try:
                    stars = int(float(row.get("stars", 0)))
                except (TypeError, ValueError):
                    continue

                sentiment = STAR_TO_SENTIMENT.get(stars)
                if sentiment is None or kept[sentiment] >= per_class:
                    continue

                text = (row.get("text") or "").replace("\r", " ").replace("\n", " ").strip()
                if not (MIN_CHARS <= len(text) <= MAX_CHARS):
                    continue

                kept[sentiment] += 1
                writer.writerow([
                    row.get("review_id", ""),
                    row.get("business_id", ""),
                    business["name"],
                    business["city"],
                    business["state"],
                    stars,
                    sentiment,
                    (row.get("date") or "")[:10],
                    text,
                ])
    finally:
        stream.close()
        tar.close()

    size_mb = output_csv.stat().st_size / 1e6
    print(f"\n[reviews] Done in {(time.time() - start) / 60:.1f} min.")
    print(f"[reviews] Scanned {seen:,} | kept {sum(kept.values()):,} {dict(kept)}")
    print(f"[reviews] Wrote {output_csv}  ({size_mb:.0f} MB)")

    if kept and min(kept.values()) < per_class:
        short = [c for c, n in kept.items() if n < per_class]
        print(f"[reviews] NOTE: these classes did not fill up: {short}. "
              "Neutral (3 stars) is genuinely rarer on Yelp - that is expected.")


# --------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build the DineSense training CSV from the Yelp dataset tar.")
    parser.add_argument("--per-class", type=int, default=DEFAULT_PER_CLASS,
                        help=f"Reviews to keep per sentiment class (default {DEFAULT_PER_CLASS}).")
    parser.add_argument("--extract", action="store_true",
                        help="Also write the raw JSON files to data/raw/ (needs ~6 GB free).")
    args = parser.parse_args()

    RAW_DIR.mkdir(parents=True, exist_ok=True)
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

    tar_path = find_tar()
    print(f"[tar] Using {tar_path}\n")

    if args.extract:
        extract_to_disk(tar_path, RAW_DIR)

    restaurants = load_restaurant_ids(tar_path)
    build_csv(tar_path, restaurants, OUTPUT_CSV, args.per_class)

    print("\nNext: send me data/processed/restaurant_reviews.csv and I will train the models.")


if __name__ == "__main__":
    main()
