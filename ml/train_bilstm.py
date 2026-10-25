"""
BiLSTM sentiment model - the architecture from the DineSense spec.

    Input -> TextVectorization(20k vocab, 200 tokens)
          -> Embedding(128)
          -> Bidirectional LSTM(64)
          -> Dropout(0.4)
          -> Dense(64, relu)
          -> Dropout(0.3)
          -> Dense(3, softmax)

Run:
    python ml/train_bilstm.py                 # default 15 epochs, batch 64
    python ml/train_bilstm.py --epochs 8      # quicker pass while iterating

The TextVectorization layer is saved *inside* the model, so serving code never
has to reproduce the tokenizer - you feed it raw strings.
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import numpy as np
import tensorflow as tf
from sklearn.metrics import classification_report, confusion_matrix
from tensorflow import keras
from tensorflow.keras import layers

from preprocessing import LABELS, load_dataset, split_dataset

MODEL_DIR = Path(__file__).resolve().parent / "saved_models"
MODEL_PATH = MODEL_DIR / "bilstm_sentiment.keras"
METRICS_PATH = MODEL_DIR / "bilstm_metrics.json"
HISTORY_PATH = MODEL_DIR / "bilstm_history.json"

MAX_VOCAB = 20_000
MAX_LEN = 200
EMBED_DIM = 128
LSTM_UNITS = 64
SEED = 42


def build_model(vectorizer: layers.TextVectorization) -> keras.Model:
    inputs = keras.Input(shape=(1,), dtype=tf.string, name="review_text")
    x = vectorizer(inputs)
    x = layers.Embedding(
        input_dim=MAX_VOCAB,
        output_dim=EMBED_DIM,
        mask_zero=True,          # let the LSTM ignore padding
        name="embedding",
    )(x)
    x = layers.Bidirectional(layers.LSTM(LSTM_UNITS), name="bilstm")(x)
    x = layers.Dropout(0.4)(x)
    x = layers.Dense(64, activation="relu", name="dense")(x)
    x = layers.Dropout(0.3)(x)
    outputs = layers.Dense(len(LABELS), activation="softmax", name="sentiment")(x)

    model = keras.Model(inputs, outputs, name="dinesense_bilstm")
    model.compile(
        optimizer=keras.optimizers.Adam(learning_rate=1e-3),
        loss="sparse_categorical_crossentropy",
        metrics=["accuracy"],
    )
    return model


def make_dataset(texts, labels, batch_size: int, shuffle: bool) -> tf.data.Dataset:
    # pandas gives object dtype for strings; Keras needs tf.string
    text_tensor = tf.constant(list(texts), dtype=tf.string)
    label_tensor = tf.constant(np.asarray(labels, dtype="int32"))
    ds = tf.data.Dataset.from_tensor_slices((text_tensor, label_tensor))
    if shuffle:
        ds = ds.shuffle(buffer_size=min(len(texts), 50_000), seed=SEED)
    return ds.batch(batch_size).prefetch(tf.data.AUTOTUNE)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--epochs", type=int, default=15)
    parser.add_argument("--batch-size", type=int, default=64)
    args = parser.parse_args()

    keras.utils.set_random_seed(SEED)
    MODEL_DIR.mkdir(parents=True, exist_ok=True)

    gpus = tf.config.list_physical_devices("GPU")
    print(f"[tf] TensorFlow {tf.__version__} | GPUs visible: {len(gpus)}")
    if not gpus:
        print("[tf] Running on CPU. Expect roughly 5-15 min per epoch at 120k reviews.")

    df = load_dataset()
    train, val, test = split_dataset(df)

    # --- fit the tokenizer on TRAIN ONLY (fitting on val/test leaks vocabulary)
    print("\n[vectorizer] Adapting on training text...")
    vectorizer = layers.TextVectorization(
        max_tokens=MAX_VOCAB,
        output_sequence_length=MAX_LEN,
        standardize="lower_and_strip_punctuation",
        name="text_vectorization",
    )
    vectorizer.adapt(
        tf.data.Dataset.from_tensor_slices(train["clean_text"].values).batch(256)
    )
    print(f"[vectorizer] vocabulary size = {len(vectorizer.get_vocabulary()):,}")

    model = build_model(vectorizer)
    model.summary()

    train_ds = make_dataset(train["clean_text"].values, train["label"].values,
                            args.batch_size, shuffle=True)
    val_ds = make_dataset(val["clean_text"].values, val["label"].values,
                          args.batch_size, shuffle=False)
    test_ds = make_dataset(test["clean_text"].values, test["label"].values,
                           args.batch_size, shuffle=False)

    callbacks = [
        keras.callbacks.EarlyStopping(
            monitor="val_loss", patience=3, restore_best_weights=True, verbose=1
        ),
        keras.callbacks.ModelCheckpoint(
            MODEL_PATH, monitor="val_loss", save_best_only=True, verbose=1
        ),
        keras.callbacks.ReduceLROnPlateau(
            monitor="val_loss", factor=0.5, patience=1, min_lr=1e-5, verbose=1
        ),
    ]

    print(f"\n[train] Starting: up to {args.epochs} epochs, batch size {args.batch_size}")
    start = time.time()
    history = model.fit(
        train_ds, validation_data=val_ds, epochs=args.epochs,
        callbacks=callbacks,
        shuffle=False,   # the tf.data pipeline already shuffles
        verbose=2,       # one line per epoch instead of a progress bar
    )
    print(f"[train] Finished in {(time.time() - start) / 60:.1f} min")

    # --- evaluate on the held-out test set
    probs = model.predict(test_ds, verbose=0)
    preds = probs.argmax(axis=1)
    y_true = test["label"].values

    print("\n===== TEST =====")
    print(classification_report(y_true, preds, target_names=LABELS, digits=3))
    print("Confusion matrix (rows = true, cols = predicted):")
    print(confusion_matrix(y_true, preds))

    report = classification_report(
        y_true, preds, target_names=LABELS, digits=4, output_dict=True
    )

    model.save(MODEL_PATH)
    METRICS_PATH.write_text(json.dumps({
        "model": "bilstm_sentiment",
        "model_version": "v1",
        "test_accuracy": report["accuracy"],
        "test_macro_f1": report["macro avg"]["f1-score"],
        "per_class": {label: report[label] for label in LABELS},
        "epochs_run": len(history.history["loss"]),
        "n_train": len(train),
        "n_test": len(test),
    }, indent=2), encoding="utf-8")
    HISTORY_PATH.write_text(
        json.dumps({k: [float(v) for v in vals] for k, vals in history.history.items()}, indent=2),
        encoding="utf-8",
    )

    print(f"\n[train] Saved model   -> {MODEL_PATH}")
    print(f"[train] Saved metrics -> {METRICS_PATH}")
    print(f"[train] Test macro F1 = {report['macro avg']['f1-score']:.4f}")
    print("[train] Compare this against baseline_metrics.json. If it is not clearly "
          "higher, the BiLSTM is not worth its cost - say so in your report.")


if __name__ == "__main__":
    main()
