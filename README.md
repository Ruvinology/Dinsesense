# DineSense AI

A restaurant feedback intelligence platform: it ingests reviews, analyses them
with a deep-learning sentiment model plus aspect and urgency detection, and
surfaces the results as business actions on a manager dashboard.

**Status: ML pipeline, FastAPI backend and React dashboard all built and running
locally. Not yet deployed.**

---

## Current state

| Layer | Status |
|---|---|
| Data preparation (Yelp -> training CSV) | Done: 60,000 restaurant reviews, 20,000 per class |
| TF-IDF + Logistic Regression baseline | Trained |
| BiLSTM v1 (learned embeddings) | Trained - overfits |
| BiLSTM v2 (frozen GloVe) | Trained - no longer overfits, still below the baseline |
| DistilRoBERTa v3 (fine-tuned transformer) | Trained in Colab, **served by default** |
| Aspect identification | v1, keyword + clause rules |
| Urgency detection | v1, rule-based |
| Recommendation engine | v1, mapped from aspects |
| FastAPI backend | Built, with tests |
| Database | SQLite locally; PostgreSQL supported via `DATABASE_URL` |
| React dashboard | Built |
| Deployment | Not started (Docker files exist) |

---

## Model results

All models are scored on the same 8,996 held-out test reviews.

| Model | Accuracy | Macro F1 | Neutral F1 |
|---|---|---|---|
| TF-IDF + logistic regression (baseline) | 0.7715 | 0.7718 | 0.675 |
| BiLSTM v1 | 0.7518 | 0.7483 | 0.631 |
| BiLSTM v2 (frozen GloVe) | 0.7514 | 0.7544 | 0.666 |
| **DistilRoBERTa v3**, full precision | **0.8190** | **0.8207** | **0.744** |
| DistilRoBERTa v3, 8-bit ONNX (what the app serves) | 0.8168 | 0.8183 | 0.740 |

What happened, briefly:

- **BiLSTM v1 overfitted.** Its embedding layer alone had about 2.5 million
  weights for 42,000 training reviews. Training accuracy rose from 68% to 90%
  in four epochs while validation loss rose every epoch.
- **BiLSTM v2 swung the other way.** Freezing GloVe left about 93,000 trainable
  weights. Training and validation accuracy are level at about 74.5%, which is
  underfitting, and it still lost to the baseline.
- **The transformer won.** A pretrained model arrives knowing English, and it
  gives each word a vector that depends on its context, so "not bad" and "bad"
  are different before any training. The biggest gain is on the neutral class,
  where reviews mix praise and complaints and word order matters most.
- **Neutral is still the weakest class for every model.** The labels come from
  star ratings, and many 3-star reviews read as clearly positive or negative.

---

## Setup

```bash
python -m venv .venv
.venv\Scripts\activate            # Windows
pip install -r requirements.txt
pip install -r backend/requirements.txt
```

Serving the transformer needs only `onnxruntime` and `tokenizers` (both in
`requirements.txt`), not PyTorch. TensorFlow is only needed if you want to serve
or retrain the BiLSTMs.

TensorFlow on native Windows is CPU-only from 2.11 onwards. Training the BiLSTM
on 42,000 reviews takes a few minutes per epoch on a laptop CPU.

---

## Running the pipeline

Run these in order from the project root.

**1. Build the training set** - filters to restaurants and balances the classes:

```bash
python ml/prepare_data.py
```

Standard library only, so no installs are needed for this step. It reads the
JSON *straight out of the tar* rather than extracting it, so it needs almost no
extra disk. Writes `data/processed/restaurant_reviews.csv` (~45 MB at the
default 20,000 per class). Pass `--per-class 60000` for a bigger set, or
`--extract` if you also want the raw JSON files on disk (~6 GB).

**2. Train the baseline** - about a minute, and it gives you the number every
deep model has to beat:

```bash
python ml/train_baseline.py
```

**3. Train the BiLSTMs** (optional now; kept for the comparison):

```bash
python ml/train_bilstm.py --epochs 15
python ml/train_bilstm_v2.py --epochs 15
```

**4. Fine-tune the transformer in Google Colab.** Open
`notebooks/finetune_transformer_v3.ipynb` in Colab with a T4 GPU, upload
`data/processed/restaurant_reviews.csv` and `ml/preprocessing.py`, and run all
cells (about 20-40 minutes). It uses the same split as every other model.
Unzip the result so the files sit in `ml/saved_models/transformer_v3/`.

**5. Export it to 8-bit ONNX** so the app can serve it without PyTorch. The
exported `sentiment_int8.onnx` (83 MB) goes in `ml/saved_models/transformer_v3/`
beside `tokenizer.json` and `config.json`. The export needs PyTorch, so do it in
Colab or any machine that has it: export with `torch.onnx.export(...,
dynamo=True)`, then quantise with `onnxruntime.quantization.quantize_dynamic`.

**6. Rebuild the comparison table** shown on the admin page:

```bash
python ml/compare_models.py
```

**7. Try a single review end to end:**

```bash
python ml/predict.py "The food was excellent but the service was extremely slow."
```

`predict.py` serves the best model available (`transformer_v3` first). Set the
environment variable `DINESENSE_MODEL` to `baseline`, `bilstm_v1` or
`bilstm_v2` to force another one.

---

## Running the app

```bash
cd backend
python seed.py                    # demo restaurant, users and reviews (safe to re-run)
uvicorn app.main:app --reload     # API on http://127.0.0.1:8000, docs at /docs
```

```bash
cd frontend
npm install
npm run dev                       # http://localhost:5173
```

After switching models, re-analyse the reviews already in the database:

```bash
cd backend
python reanalyse.py               # preview what would change
python reanalyse.py --apply       # store the new predictions
```

Tests:

```bash
python -m pytest tests/           # urgency and aspect rules
cd backend && python -m pytest tests/
```

---

## Design notes worth knowing

**Labels come from star ratings.** 1-2 stars = negative, 3 = neutral, 4-5 =
positive. This is standard practice but it is a proxy, not ground truth - a
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
Aspects are the weakest part of the system and the obvious next target - a
multi-label classifier trained on a few thousand hand-labelled reviews.

**Each model carries its own tokenizer.** For the BiLSTMs, `TextVectorization`
is a layer inside the Keras model. For the transformer, `tokenizer.json` sits
beside the ONNX file and `predict.py` loads both together. Either way the
backend feeds raw strings and cannot drift out of sync with training.

**The transformer reads raw text.** The BiLSTMs read `clean_text()` output
(lowercased, punctuation stripped). The transformer was fine-tuned on the
original review text, because its tokenizer uses capitals, emoji and
punctuation, so `predict.py` only decodes HTML entities and collapses
whitespace before passing text to it.

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
│   ├── train_bilstm.py         # BiLSTM v1
│   ├── train_bilstm_v2.py      # BiLSTM v2, frozen GloVe
│   ├── evaluate.py             # baseline vs BiLSTM v1 confusion matrices
│   ├── compare_models.py       # all models -> model_comparison.json
│   ├── predict.py              # full inference: sentiment/aspects/urgency
│   └── saved_models/
│       └── transformer_v3/     # fine-tuned DistilRoBERTa (ONNX + tokenizer)
├── notebooks/
│   └── finetune_transformer_v3.ipynb   # Colab fine-tuning notebook
├── backend/                    # FastAPI + SQLAlchemy
├── frontend/                   # React + Vite + Tailwind
├── tests/
└── requirements.txt
```

---

## Data

Built on the [Yelp Open Dataset](https://www.yelp.com/dataset). Read its terms
before publishing anything derived from it - redistribution of the raw data is
not permitted, which is why `data/` is gitignored.
