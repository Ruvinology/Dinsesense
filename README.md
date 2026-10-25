# DineSense AI

A restaurant feedback intelligence platform: it ingests reviews, analyses them
with a deep-learning sentiment model plus aspect and urgency detection, and
surfaces the results as business actions on a manager dashboard.

**Status: ML core built. Backend, database and frontend not started yet.**

---

## Current state

| Layer | Status |
|---|---|
| Data preparation (Yelp -> training CSV) | Built, not yet run |
| TF-IDF + Logistic Regression baseline | Built, not yet trained |
| BiLSTM sentiment model | Built, not yet trained |
| Evaluation and model comparison | Built |
| Aspect identification | v1, keyword + clause rules |
| Urgency detection | v1, rule-based |
| Recommendation engine | v1, mapped from aspects |
| FastAPI backend | Not started |
| PostgreSQL schema | Not started |
| React dashboard | Not started |

---

## Setup

```bash
conda create -n dinesense python=3.11 -y
conda activate dinesense
pip install -r requirements.txt
```

TensorFlow on native Windows is CPU-only from 2.11 onwards. Training the BiLSTM
on ~120k reviews will take roughly 5-15 minutes per epoch on a laptop CPU. If
that is too slow, either drop `--per-class` to 20000 when preparing data, or run
the training on Colab / your university Linux box.

---

## Running the pipeline

Run these in order from the project root.

**1. Build the training set** — filters to restaurants and balances the classes:

```bash
python ml/prepare_data.py
```

Standard library only, so no installs are needed for this step. It reads the
JSON *straight out of the tar* rather than extracting it, so it needs almost no
extra disk. Writes `data/processed/restaurant_reviews.csv` (~45 MB at the
default 20,000 per class). Pass `--per-class 60000` for a bigger set, or
`--extract` if you also want the raw JSON files on disk (~6 GB).

**2. Train the baseline** — do this first, it takes about a minute and gives you
the number the BiLSTM has to beat:

```bash
python ml/train_baseline.py
```

**3. Train the BiLSTM:**

```bash
python ml/train_bilstm.py --epochs 15
```

**4. Compare them:**

```bash
python ml/evaluate.py
```

**5. Try a single review end to end:**

```bash
python ml/predict.py "The food was excellent but the service was extremely slow."
```

---

## Design notes worth knowing

**Labels come from star ratings.** 1-2 stars = negative, 3 = neutral, 4-5 =
positive. This is standard practice but it is a proxy, not ground truth — a
3-star review is often a positive review from a picky reviewer. The neutral
class will be your weakest and that is expected, not a bug in your code.

**The classes are balanced by capping.** Yelp skews heavily positive. Capping
each class at the same count avoids a model that scores 70% accuracy by
predicting "positive" for everything. It also means your reported accuracy is
not directly comparable to papers that train on the natural distribution.

**Aspects and urgency are rules, not models.** They are labelled as such in the
code and should be labelled as such in your report. Urgency is rule-based on
purpose: for a food-poisoning complaint, a predictable rule that always fires
beats a classifier that is 94% accurate and silent the other 6% of the time.
Aspects are the weakest part of the system and the obvious v2 target — a
multi-label classifier trained on a few thousand hand-labelled reviews.

**The tokenizer is inside the saved model.** `TextVectorization` is a layer of
the Keras model, so the backend feeds it raw strings and cannot drift out of
sync with training.

---

## Project layout

```
DineSense/
├── data/
│   ├── raw/                    # extracted Yelp JSON (gitignored)
│   └── processed/              # restaurant_reviews.csv (gitignored)
├── ml/
│   ├── prepare_data.py         # Yelp tar -> balanced training CSV
│   ├── preprocessing.py        # cleaning, loading, splitting
│   ├── train_baseline.py       # TF-IDF + LogReg
│   ├── train_bilstm.py         # the spec's BiLSTM
│   ├── evaluate.py             # comparison + confusion matrices
│   ├── predict.py              # full inference: sentiment/aspects/urgency
│   └── saved_models/
├── notebooks/
├── backend/                    # FastAPI (not started)
├── frontend/                   # React + Vite (not started)
├── tests/
└── requirements.txt
```

---

## Data

Built on the [Yelp Open Dataset](https://www.yelp.com/dataset). Read its terms
before publishing anything derived from it — redistribution of the raw data is
not permitted, which is why `data/` is gitignored.
