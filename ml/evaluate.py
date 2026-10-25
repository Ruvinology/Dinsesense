"""
Side-by-side evaluation of the baseline and the BiLSTM.

    python ml/evaluate.py

Writes confusion-matrix images and a comparison table into ml/saved_models/.
Run after both training scripts.
"""

from __future__ import annotations

import json
from pathlib import Path

import joblib
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import seaborn as sns
from sklearn.metrics import classification_report, confusion_matrix

from preprocessing import LABELS, load_dataset, split_dataset

MODEL_DIR = Path(__file__).resolve().parent / "saved_models"
BASELINE_PATH = MODEL_DIR / "baseline_tfidf_logreg.joblib"
BILSTM_PATH = MODEL_DIR / "bilstm_sentiment.keras"
COMPARISON_PATH = MODEL_DIR / "model_comparison.json"


def plot_confusion(y_true, y_pred, title: str, outfile: Path) -> None:
    cm = confusion_matrix(y_true, y_pred)
    cm_pct = cm.astype(float) / cm.sum(axis=1, keepdims=True) * 100

    fig, ax = plt.subplots(figsize=(5.5, 4.5))
    sns.heatmap(
        cm_pct, annot=np.array([[f"{c}\n{p:.1f}%" for c, p in zip(rc, rp)]
                                for rc, rp in zip(cm, cm_pct)]),
        fmt="", cmap="Blues", cbar=False,
        xticklabels=LABELS, yticklabels=LABELS, ax=ax,
    )
    ax.set_xlabel("Predicted")
    ax.set_ylabel("True")
    ax.set_title(title)
    fig.tight_layout()
    fig.savefig(outfile, dpi=150)
    plt.close(fig)
    print(f"[eval] Wrote {outfile}")


def plot_history(outfile: Path) -> None:
    history_path = MODEL_DIR / "bilstm_history.json"
    if not history_path.exists():
        return
    history = json.loads(history_path.read_text(encoding="utf-8"))
    epochs = range(1, len(history["loss"]) + 1)

    fig, axes = plt.subplots(1, 2, figsize=(10, 4))
    axes[0].plot(epochs, history["loss"], label="train")
    axes[0].plot(epochs, history["val_loss"], label="validation")
    axes[0].set_title("Loss"); axes[0].set_xlabel("Epoch"); axes[0].legend()
    axes[1].plot(epochs, history["accuracy"], label="train")
    axes[1].plot(epochs, history["val_accuracy"], label="validation")
    axes[1].set_title("Accuracy"); axes[1].set_xlabel("Epoch"); axes[1].legend()
    fig.tight_layout()
    fig.savefig(outfile, dpi=150)
    plt.close(fig)
    print(f"[eval] Wrote {outfile}")
    print("[eval] If the two loss curves separate widely, you are overfitting - "
          "shorten training or raise dropout.")


def main() -> None:
    df = load_dataset()
    _, _, test = split_dataset(df)
    y_true = test["label"].values
    results = {}

    if BASELINE_PATH.exists():
        pipeline = joblib.load(BASELINE_PATH)
        preds = pipeline.predict(test["clean_text"])
        report = classification_report(y_true, preds, target_names=LABELS,
                                       digits=4, output_dict=True)
        results["baseline_tfidf_logreg"] = {
            "accuracy": report["accuracy"],
            "macro_f1": report["macro avg"]["f1-score"],
        }
        plot_confusion(y_true, preds, "TF-IDF + Logistic Regression",
                       MODEL_DIR / "confusion_baseline.png")
    else:
        print(f"[eval] Baseline not found at {BASELINE_PATH} - skipping.")

    if BILSTM_PATH.exists():
        from tensorflow import keras
        model = keras.models.load_model(BILSTM_PATH)
        # Keras needs tf.string, not a numpy object/unicode array
        import tensorflow as tf
        texts = tf.data.Dataset.from_tensor_slices(
            tf.constant(test["clean_text"].tolist(), dtype=tf.string)
        ).batch(128)
        probs = model.predict(texts, verbose=0)
        preds = probs.argmax(axis=1)
        report = classification_report(y_true, preds, target_names=LABELS,
                                       digits=4, output_dict=True)
        results["bilstm"] = {
            "accuracy": report["accuracy"],
            "macro_f1": report["macro avg"]["f1-score"],
        }
        plot_confusion(y_true, preds, "BiLSTM", MODEL_DIR / "confusion_bilstm.png")
        plot_history(MODEL_DIR / "training_history.png")
    else:
        print(f"[eval] BiLSTM not found at {BILSTM_PATH} - skipping.")

    if results:
        COMPARISON_PATH.write_text(json.dumps(results, indent=2), encoding="utf-8")
        print("\n===== COMPARISON =====")
        print(f"{'model':<28}{'accuracy':>10}{'macro F1':>12}")
        for name, scores in results.items():
            print(f"{name:<28}{scores['accuracy']:>10.4f}{scores['macro_f1']:>12.4f}")

        if len(results) == 2:
            gain = results["bilstm"]["macro_f1"] - results["baseline_tfidf_logreg"]["macro_f1"]
            print(f"\nBiLSTM gain over baseline: {gain:+.4f} macro F1")
            if gain < 0.01:
                print("That is within noise. Report it honestly - a null result that you "
                      "measured properly is a stronger portfolio piece than an unverified claim.")


if __name__ == "__main__":
    main()
