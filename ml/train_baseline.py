"""
TF-IDF + Logistic Regression baseline.

This exists to keep the deep-learning claim honest. If the BiLSTM cannot beat
this, the BiLSTM is not earning its complexity - and on 3-class sentiment with
plenty of data, this baseline is genuinely strong. Expect ~0.78-0.83 macro F1.

    python ml/train_baseline.py
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import joblib
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import classification_report, confusion_matrix
from sklearn.pipeline import Pipeline

from preprocessing import LABELS, load_dataset, split_dataset

MODEL_DIR = Path(__file__).resolve().parent / "saved_models"
MODEL_PATH = MODEL_DIR / "baseline_tfidf_logreg.joblib"
METRICS_PATH = MODEL_DIR / "baseline_metrics.json"


def build_pipeline() -> Pipeline:
    return Pipeline([
        ("tfidf", TfidfVectorizer(
            max_features=50_000,
            ngram_range=(1, 2),   # bigrams catch "not good", "never again"
            min_df=3,
            sublinear_tf=True,
        )),
        ("clf", LogisticRegression(
            max_iter=1000,
            C=4.0,
            class_weight="balanced",
            n_jobs=-1,
        )),
    ])


def main() -> None:
    MODEL_DIR.mkdir(parents=True, exist_ok=True)

    df = load_dataset()
    train, val, test = split_dataset(df)

    pipeline = build_pipeline()

    print("\n[baseline] Fitting TF-IDF + Logistic Regression...")
    start = time.time()
    pipeline.fit(train["clean_text"], train["label"])
    print(f"[baseline] Trained in {time.time() - start:.1f}s")

    for name, split in (("validation", val), ("test", test)):
        preds = pipeline.predict(split["clean_text"])
        print(f"\n===== {name.upper()} =====")
        print(classification_report(split["label"], preds, target_names=LABELS, digits=3))
        print("Confusion matrix (rows = true, cols = predicted):")
        print(confusion_matrix(split["label"], preds))

    test_preds = pipeline.predict(test["clean_text"])
    report = classification_report(
        test["label"], test_preds, target_names=LABELS, digits=4, output_dict=True
    )

    joblib.dump(pipeline, MODEL_PATH)
    METRICS_PATH.write_text(json.dumps({
        "model": "tfidf_logreg_baseline",
        "test_accuracy": report["accuracy"],
        "test_macro_f1": report["macro avg"]["f1-score"],
        "per_class": {label: report[label] for label in LABELS},
        "n_train": len(train),
        "n_test": len(test),
    }, indent=2), encoding="utf-8")

    print(f"\n[baseline] Saved model  -> {MODEL_PATH}")
    print(f"[baseline] Saved metrics -> {METRICS_PATH}")
    print(f"[baseline] Test macro F1 = {report['macro avg']['f1-score']:.4f}  "
          f"(this is the number the BiLSTM must beat)")


if __name__ == "__main__":
    main()
