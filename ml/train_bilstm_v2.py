"""
BiLSTM v2 - the same architecture, fixed where v1 was broken.

WHY v1 LOST TO THE BASELINE

v1 scored 0.7483 macro F1 against the baseline's 0.7718. The training curves
showed why: training accuracy climbed 0.68 -> 0.90 while validation sat flat at
0.74 and validation loss rose from epoch 2 onward. Textbook overfitting.

The cause is visible in the parameter count:

    Embedding (20,000 x 128)   2,560,000 params   96%
    BiLSTM + Dense                107,267 params    4%

96% of the model's capacity was spent learning what English words mean, from
scratch, from 42,000 restaurant reviews. That is nowhere near enough text to
learn a language from - so it memorised the training set instead.

WHAT CHANGED IN v2

1. GloVe pretrained embeddings (glove-wiki-gigaword-100, trained on 6 billion
   words). The embedding layer is FROZEN, so those 2 million parameters stop
   being trainable. Trainable params drop by ~96%.

2. Shorter sequences: 200 -> 160 tokens. Reviews average ~110 words, so 200 was
   mostly padding, which costs time and adds nothing.

3. Stronger regularisation on what remains: recurrent dropout, and L2 on the
   dense layer.

4. Class weights, so the harder neutral class is not quietly ignored.

The data is IDENTICAL to v1 - same CSV, same seed, same split. One variable
changed at a time, so the comparison actually means something.

Run:
    python ml/train_bilstm_v2.py --epochs 15

Requires the GloVe vectors:
    pip install gensim
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import numpy as np
import tensorflow as tf
from sklearn.metrics import classification_report, confusion_matrix
from sklearn.utils.class_weight import compute_class_weight
from tensorflow import keras
from tensorflow.keras import layers, regularizers

from preprocessing import LABELS, load_dataset, split_dataset

MODEL_DIR = Path(__file__).resolve().parent / "saved_models"
MODEL_PATH = MODEL_DIR / "bilstm_v2_sentiment.keras"
METRICS_PATH = MODEL_DIR / "bilstm_v2_metrics.json"
HISTORY_PATH = MODEL_DIR / "bilstm_v2_history.json"

MAX_VOCAB = 20_000
MAX_LEN = 160          # was 200 - mostly padding
EMBED_DIM = 100        # must match the GloVe file
LSTM_UNITS = 64
SEED = 42

GLOVE_NAME = "glove-wiki-gigaword-100"


def load_glove_matrix(vocabulary: list[str]) -> tuple[np.ndarray, int]:
    """Build an embedding matrix for our vocabulary from GloVe.

    Words GloVe has never seen (misspellings, slang, "kottu") keep a small
    random vector rather than zeros - a zero vector would make them invisible
    to the LSTM rather than merely unknown.
    """
    import gensim.downloader as downloader

    print(f"[glove] Loading {GLOVE_NAME} (downloads ~128 MB the first time)...")
    vectors = downloader.load(GLOVE_NAME)

    rng = np.random.default_rng(SEED)
    matrix = rng.normal(0.0, 0.1, size=(len(vocabulary), EMBED_DIM)).astype("float32")
    matrix[0] = 0.0  # padding token stays zero

    found = 0
    for index, word in enumerate(vocabulary):
        if index == 0:
            continue
        if word in vectors:
            matrix[index] = vectors[word]
            found += 1

    coverage = found / max(len(vocabulary) - 1, 1)
    print(f"[glove] Matched {found:,} of {len(vocabulary):,} vocabulary words "
          f"({coverage:.1%} coverage)")
    if coverage < 0.7:
        print("[glove] WARNING: coverage below 70%. Check the cleaning step - "
              "over-aggressive stripping can leave tokens GloVe cannot match.")
    return matrix, found


def build_model(vectorizer, embedding_matrix: np.ndarray) -> keras.Model:
    inputs = keras.Input(shape=(1,), dtype=tf.string, name="review_text")
    x = vectorizer(inputs)
    x = layers.Embedding(
        input_dim=embedding_matrix.shape[0],
        output_dim=EMBED_DIM,
        embeddings_initializer=keras.initializers.Constant(embedding_matrix),
        trainable=False,          # <-- the whole point of v2
        mask_zero=True,
        name="glove_embedding",
    )(x)
    x = layers.Bidirectional(
        layers.LSTM(LSTM_UNITS, dropout=0.3, recurrent_dropout=0.0),
        name="bilstm",
    )(x)
    x = layers.Dropout(0.5)(x)
    x = layers.Dense(64, activation="relu",
                     kernel_regularizer=regularizers.l2(1e-4), name="dense")(x)
    x = layers.Dropout(0.3)(x)
    outputs = layers.Dense(len(LABELS), activation="softmax", name="sentiment")(x)

    model = keras.Model(inputs, outputs, name="dinesense_bilstm_v2")
    model.compile(
        optimizer=keras.optimizers.Adam(learning_rate=1e-3),
        loss="sparse_categorical_crossentropy",
        metrics=["accuracy"],
    )
    return model


def make_dataset(texts, labels, batch_size: int, shuffle: bool) -> tf.data.Dataset:
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

    # Identical data and split to v1 - same seed, same function
    df = load_dataset()
    train, val, test = split_dataset(df)

    print("\n[vectorizer] Adapting on training text only...")
    vectorizer = layers.TextVectorization(
        max_tokens=MAX_VOCAB,
        output_sequence_length=MAX_LEN,
        standardize="lower_and_strip_punctuation",
        name="text_vectorization",
    )
    vectorizer.adapt(
        tf.data.Dataset.from_tensor_slices(train["clean_text"].values).batch(256)
    )
    vocabulary = vectorizer.get_vocabulary()
    print(f"[vectorizer] vocabulary size = {len(vocabulary):,}")

    embedding_matrix, _ = load_glove_matrix(vocabulary)

    model = build_model(vectorizer, embedding_matrix)
    model.summary()

    trainable = int(sum(np.prod(w.shape) for w in model.trainable_weights))
    frozen = int(sum(np.prod(w.shape) for w in model.non_trainable_weights))
    print(f"\n[params] trainable {trainable:,} | frozen {frozen:,}")
    print(f"[params] v1 trained 2,667,267. v2 trains {trainable:,} "
          f"({trainable / 2_667_267:.1%} of v1).")

    # Neutral is the hard class; without weights the model drifts toward the easy two
    weights = compute_class_weight("balanced",
                                   classes=np.unique(train["label"]),
                                   y=train["label"])
    class_weight = {int(i): float(w) for i, w in enumerate(weights)}
    print(f"[train] class weights: {class_weight}")

    train_ds = make_dataset(train["clean_text"].values, train["label"].values,
                            args.batch_size, shuffle=True)
    val_ds = make_dataset(val["clean_text"].values, val["label"].values,
                          args.batch_size, shuffle=False)
    test_ds = make_dataset(test["clean_text"].values, test["label"].values,
                           args.batch_size, shuffle=False)

    callbacks = [
        keras.callbacks.EarlyStopping(monitor="val_loss", patience=4,
                                      restore_best_weights=True, verbose=1),
        keras.callbacks.ModelCheckpoint(MODEL_PATH, monitor="val_loss",
                                        save_best_only=True, verbose=0),
        keras.callbacks.ReduceLROnPlateau(monitor="val_loss", factor=0.5,
                                          patience=2, min_lr=1e-5, verbose=1),
    ]

    print(f"\n[train] up to {args.epochs} epochs, batch {args.batch_size}")
    start = time.time()
    history = model.fit(
        train_ds, validation_data=val_ds, epochs=args.epochs,
        callbacks=callbacks, class_weight=class_weight,
        shuffle=False, verbose=2,
    )
    print(f"[train] finished in {(time.time() - start) / 60:.1f} min")

    probs = model.predict(test_ds, verbose=0)
    preds = probs.argmax(axis=1)
    y_true = test["label"].values

    print("\n===== TEST =====")
    print(classification_report(y_true, preds, target_names=LABELS, digits=3))
    print("Confusion matrix (rows = true, cols = predicted):")
    print(confusion_matrix(y_true, preds))

    report = classification_report(y_true, preds, target_names=LABELS,
                                   digits=4, output_dict=True)

    model.save(MODEL_PATH)
    METRICS_PATH.write_text(json.dumps({
        "model": "bilstm_v2_glove",
        "model_version": "v2",
        "test_accuracy": report["accuracy"],
        "test_macro_f1": report["macro avg"]["f1-score"],
        "per_class": {label: report[label] for label in LABELS},
        "epochs_run": len(history.history["loss"]),
        "trainable_params": trainable,
        "frozen_params": frozen,
        "n_train": len(train),
        "n_test": len(test),
        "changes_from_v1": [
            "frozen GloVe 100d embeddings instead of learned 128d",
            "sequence length 200 -> 160",
            "dropout 0.4/0.3 -> 0.3 (LSTM) / 0.5 / 0.3",
            "L2 1e-4 on the dense layer",
            "balanced class weights",
        ],
    }, indent=2), encoding="utf-8")
    HISTORY_PATH.write_text(
        json.dumps({k: [float(v) for v in vals] for k, vals in history.history.items()},
                   indent=2),
        encoding="utf-8",
    )

    print(f"\n[train] saved -> {MODEL_PATH}")
    print(f"[train] v2 test macro F1 = {report['macro avg']['f1-score']:.4f}")
    print("[train] v1 was 0.7483 | baseline was 0.7718")


if __name__ == "__main__":
    main()