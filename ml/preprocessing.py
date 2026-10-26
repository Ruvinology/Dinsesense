"""
Shared text cleaning and data loading for DineSense AI.

Deliberately light-touch. The BiLSTM learns from word order and its own
embeddings, so aggressive stemming or stop-word removal usually *hurts* it -
"not good" becomes "good" if you strip negations. We only normalise noise that
carries no sentiment: URLs, emails, HTML entities, repeated characters.
"""

from __future__ import annotations

import html
import re
from pathlib import Path
from typing import TYPE_CHECKING

# pandas and scikit-learn are imported inside the functions that need them.
# The deployed API only uses clean_text() and the label maps, so it doesn't
# have to install or load either library.
if TYPE_CHECKING:
    import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
PROCESSED_CSV = PROJECT_ROOT / "data" / "processed" / "restaurant_reviews.csv"

# Fixed label order - the model's output index maps to this list. Do not reorder.
LABELS = ["negative", "neutral", "positive"]
LABEL_TO_ID = {label: i for i, label in enumerate(LABELS)}
ID_TO_LABEL = {i: label for label, i in LABEL_TO_ID.items()}

RANDOM_SEED = 42

_URL = re.compile(r"https?://\S+|www\.\S+")
_EMAIL = re.compile(r"\S+@\S+\.\S+")
_REPEAT = re.compile(r"(.)\1{3,}")          # "sooooo" -> "sooo"
_WHITESPACE = re.compile(r"\s+")
_KEEP = re.compile(r"[^a-z0-9\s'!?.,$%-]")  # keep '!' and '?' - they carry tone


def clean_text(text: str) -> str:
    """Normalise a single review. Returns lowercase text with noise stripped."""
    if not isinstance(text, str):
        return ""
    text = html.unescape(text).lower()
    text = _URL.sub(" url ", text)
    text = _EMAIL.sub(" email ", text)
    text = _REPEAT.sub(r"\1\1\1", text)
    text = _KEEP.sub(" ", text)
    text = _WHITESPACE.sub(" ", text)
    return text.strip()


def load_dataset(csv_path: Path | str = PROCESSED_CSV) -> pd.DataFrame:
    """Load the prepared CSV, clean the text, drop empties and duplicates."""
    import pandas as pd

    csv_path = Path(csv_path)
    if not csv_path.exists():
        raise FileNotFoundError(
            f"{csv_path} not found. Run `python ml/prepare_data.py` first."
        )

    df = pd.read_csv(csv_path)
    df = df.dropna(subset=["review_text", "sentiment"])
    df["clean_text"] = df["review_text"].map(clean_text)
    df = df[df["clean_text"].str.split().str.len() >= 3]
    df = df.drop_duplicates(subset=["clean_text"])
    df["label"] = df["sentiment"].map(LABEL_TO_ID)
    df = df.dropna(subset=["label"])
    df["label"] = df["label"].astype(int)

    print(f"[data] {len(df):,} usable reviews")
    print(f"[data] class balance:\n{df['sentiment'].value_counts()}")
    return df.reset_index(drop=True)


def split_dataset(df: pd.DataFrame, test_size: float = 0.15, val_size: float = 0.15):
    """Stratified train/validation/test split. Returns three DataFrames."""
    from sklearn.model_selection import train_test_split

    train_val, test = train_test_split(
        df, test_size=test_size, stratify=df["label"], random_state=RANDOM_SEED
    )
    # val_size is a fraction of the *original* set, so rescale it
    val_fraction = val_size / (1.0 - test_size)
    train, val = train_test_split(
        train_val, test_size=val_fraction, stratify=train_val["label"],
        random_state=RANDOM_SEED,
    )
    print(f"[data] train={len(train):,}  val={len(val):,}  test={len(test):,}")
    return (
        train.reset_index(drop=True),
        val.reset_index(drop=True),
        test.reset_index(drop=True),
    )


if __name__ == "__main__":
    frame = load_dataset()
    split_dataset(frame)
    print("\nSample cleaned text:")
    for sample in frame["clean_text"].head(3):
        print(" -", sample[:160])
