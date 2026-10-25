"""
Inference for DineSense AI: sentiment + aspects + urgency + recommendation.

This is the module the FastAPI backend will import. It loads the trained model
once and reuses it.

    python ml/predict.py "The food was excellent but the service was very slow."

Honest labelling of what is what:
  - sentiment  : learned (BiLSTM, or the baseline as fallback)
  - aspects    : keyword-matched, with sentiment scored from the surrounding
                 clause. Transparent and debuggable, but NOT a trained model.
                 Version 2 should replace this with a multi-label classifier.
  - urgency    : rule-based, deliberately. For food-safety complaints a
                 predictable rule beats a model that is occasionally confident
                 and wrong.
"""

from __future__ import annotations

import os
import re
import sys
from dataclasses import asdict, dataclass, field
from functools import lru_cache
from pathlib import Path

from preprocessing import ID_TO_LABEL, clean_text

MODEL_DIR = Path(__file__).resolve().parent / "saved_models"

# Every model the app knows how to serve, in preference order. The first one
# whose file exists wins, unless DINESENSE_MODEL names one explicitly.
#
#   key            file                            kind        test macro F1
#   bilstm_v2      bilstm_v2_sentiment.keras       keras       0.7544
#   bilstm_v1      bilstm_sentiment.keras          keras       0.7483
#   baseline       baseline_tfidf_logreg.joblib    sklearn     0.7718
#
# NOTE FOR THE REPORT: the baseline scores HIGHEST. bilstm_v2 is served by
# default because this is a deep-learning project and the deep model is the
# subject of the work - not because it is the most accurate. Setting
# DINESENSE_MODEL=baseline switches to the better-scoring model.
MODEL_REGISTRY = [
    {"key": "bilstm_v2", "file": "bilstm_v2_sentiment.keras", "kind": "keras", "version": "v2"},
    {"key": "bilstm_v1", "file": "bilstm_sentiment.keras", "kind": "keras", "version": "v1"},
    {"key": "baseline", "file": "baseline_tfidf_logreg.joblib", "kind": "sklearn",
     "version": "baseline"},
]

BASELINE_PATH = MODEL_DIR / "baseline_tfidf_logreg.joblib"

MODEL_VERSION = "v1"  # overwritten at load time by the model actually selected

# --------------------------------------------------------------------------
# Aspect vocabulary
# --------------------------------------------------------------------------

ASPECT_KEYWORDS: dict[str, list[str]] = {
    "food_quality": ["food", "dish", "meal", "taste", "tasty", "flavour", "flavor",
                     "cooked", "undercooked", "overcooked", "fresh", "stale", "bland",
                     "delicious", "seasoned", "raw", "burnt", "soggy"],
    "service": ["service", "served", "waiter", "waitress", "server", "attentive",
                "ignored", "order was", "took our order", "refill"],
    "staff_behaviour": ["staff", "rude", "friendly", "polite", "manager", "hostess",
                        "welcoming", "attitude", "unprofessional", "helpful"],
    "waiting_time": ["wait", "waited", "waiting", "slow", "quick", "fast", "minutes",
                     "took forever", "prompt", "delay", "queue", "line"],
    "price": ["price", "pricey", "expensive", "cheap", "value", "overpriced",
              "affordable", "cost", "worth the money", "bill", "charged"],
    "portion_size": ["portion", "serving size", "small plate", "huge plate",
                     "generous", "tiny", "left hungry", "filling"],
    "cleanliness": ["clean", "dirty", "filthy", "hygiene", "sticky", "restroom",
                    "bathroom", "sanitary", "smell", "roach", "fly", "flies"],
    "ambience": ["ambience", "ambiance", "atmosphere", "decor", "music", "loud",
                 "noisy", "cozy", "lighting", "seating", "vibe", "crowded"],
    "delivery": ["delivery", "delivered", "driver", "uber eats", "doordash",
                 "grubhub", "takeout", "take-out", "arrived cold"],
    "packaging": ["packaging", "packed", "container", "box", "leaked", "spilled",
                  "wrapped", "bag"],
}

POSITIVE_CUES = {"excellent", "great", "good", "amazing", "delicious", "friendly",
                 "fast", "quick", "clean", "fresh", "perfect", "love", "loved",
                 "best", "generous", "worth", "attentive", "cozy", "polite",
                 "wonderful", "tasty", "reasonable", "affordable", "prompt",
                 "fair", "lovely", "spotless", "helpful", "nice", "solid"}
NEGATIVE_CUES = {"bad", "terrible", "awful", "slow", "rude", "dirty", "cold",
                 "bland", "expensive", "overpriced", "worst", "disgusting",
                 "horrible", "stale", "soggy", "burnt", "filthy", "tiny", "noisy",
                 "ignored", "unprofessional", "raw", "undercooked", "never again"}
NEGATORS = {"not", "no", "never", "nothing", "isn't", "wasn't", "aren't", "weren't",
            "don't", "didn't", "doesn't", "can't", "won't"}

# --------------------------------------------------------------------------
# Urgency rules
# --------------------------------------------------------------------------

# --- foodborne illness -------------------------------------------------
# Two tiers, because symptom words differ in how ambiguous they are.
#
# UNAMBIGUOUS: these mean illness wherever they appear in a restaurant review.
# A guest does not write "I fainted" about anything trivial.
UNAMBIGUOUS_ILLNESS = (
    r"food poison|food-poison|poisoned|"
    r"threw up|throwing up|vomit|puked?|"
    r"diarrh(o)?ea|dysentery|"
    r"e\.? ?coli|salmonella|norovirus|listeria|"
    r"faint(ed|ing)?|passed out|blacked out|collapsed|"
    r"(went|taken|rushed|admitted) to (the )?(hospital|a&e|er|emergency)|"
    r"stomach pump|food safety complaint"
)

# AMBIGUOUS: real symptoms, but they can describe something harmless
# ("the music made me dizzy"). These only escalate when the review also
# mentions eating - see _mentions_eating below.
AMBIGUOUS_SYMPTOMS = (
    r"\b(dizzy|dizziness|light[- ]?headed|"
    r"nausea|nauseous|nauseated|queasy|"
    r"sick|ill|unwell|"
    r"stomach ?ache|stomach[^.!?]{0,12}(pain|cramp|upset|bug|turning)|"
    r"cramps?|bloated|threw ?up|food ?poisoning|"
    r"sweaty|sweating|clammy|chills|shivering|fever|feverish|temperature|"
    r"headache|migraine|"
    r"rash|hives|itchy|swollen|swelling|"
    r"(cannot|could ?n.t|can.t) breathe|throat (closed|closing|tight))\b"
)

# Does the review actually involve consuming something here?
EATING_CONTEXT = (
    r"\b(ate|eating|eaten|drank|drinking|drunk|swallow\w*|"
    r"food|meal|dish|dishes|dinner|lunch|breakfast|brunch|"
    r"chicken|beef|pork|fish|seafood|prawns?|shrimps?|sushi|salads?|rice|curr(y|ies)|"
    r"burgers?|pizzas?|pastas?|soups?|sauces?|desserts?|drinks?|cocktails?|juice|water|"
    r"oysters?|mussels?|eggs?|meat|noodles?|sandwich(es)?|wraps?|steaks?|"
    r"restaurant|takeaway|takeout|delivery|buffet|starters?|mains?|course)\b"
)


def _mentions_eating(text: str) -> bool:
    return re.search(EATING_CONTEXT, text) is not None


HIGH_URGENCY_PATTERNS = [
    (UNAMBIGUOUS_ILLNESS, "possible foodborne illness"),
    (r"allerg\w+|anaphyla|epipen|peanut|gluten.{0,20}(sick|react)", "allergic reaction"),
    (r"foreign object|"
     r"\b(hair|glass|plastic|metal|insect|bug|roach|cockroach|worm|maggot|nail|screw|staple)\b"
     r"[^.!?]{0,40}\b(in|inside|on)\b[^.!?]{0,25}\b(my|the|our)\b",
     "foreign object in food"),
    (r"charged (me )?twice|double charged|overcharg|fraud|stole|stolen|unauthori[sz]ed charge",
     "billing or payment dispute"),
    (r"harass|assault|threaten|racist|racism|discriminat|grope|scream(ed)? at",
     "staff conduct or safety incident"),
    (r"\braw\b[^.!?]{0,25}\b(chicken|pork|meat|burger|fish|egg)\b|"
     r"\b(chicken|pork|meat|burger|fish|egg)\b[^.!?]{0,25}\b(raw|undercooked|pink inside)\b|"
     r"undercooked|mold|mould|expired|rotten|spoiled|still frozen inside",
     "serious food-safety hazard"),
    (r"cockroach|rat\b|rats\b|mice|infestation|sewage", "major cleanliness hazard"),
]

MEDIUM_URGENCY_PATTERNS = [
    (r"never (coming|going) back|never again|worst .{0,20}(ever|experience)", "customer loss risk"),
    (r"refund|complaint|complained|manager (did|would) ?n[o']t|no one (helped|cared)",
     "unresolved complaint"),
    (r"waited (over |more than )?(\d{2,}|an hour|two hours)", "severe wait time"),
    (r"report(ing)? (this|you) to|health (department|inspector)|review board", "escalation threat"),
]

RECOMMENDATIONS = {
    "waiting_time": "Review staffing levels and the order-to-table workflow for this shift.",
    "food_quality": "Notify kitchen management and check the affected dishes against spec.",
    "price": "Review pricing and portion value against local competitors.",
    "delivery": "Review packaging and the delivery partner's handover process.",
    "packaging": "Review packaging materials and sealing for transit.",
    "cleanliness": "Schedule a deep clean and a same-day hygiene inspection.",
    "staff_behaviour": "Flag for the branch manager; consider a service-conduct refresher.",
    "service": "Review floor coverage and check-in cadence with the service team.",
    "portion_size": "Audit portion weights against the standard recipe card.",
    "ambience": "Review noise levels, lighting and seating layout at peak hours.",
}
ESCALATION = "Escalate to senior management immediately and contact the customer directly."


# --------------------------------------------------------------------------
# Result types
# --------------------------------------------------------------------------

@dataclass
class AspectResult:
    aspect: str
    sentiment: str
    confidence: float


@dataclass
class PredictionResult:
    sentiment: str
    confidence: float
    urgency: str
    urgency_reason: str | None
    aspects: list[AspectResult] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)
    model_version: str = MODEL_VERSION

    def to_dict(self) -> dict:
        return asdict(self)


# --------------------------------------------------------------------------
# Model loading
# --------------------------------------------------------------------------

def _select_entry() -> dict:
    """Decide which model to serve.

    DINESENSE_MODEL wins if set and that model's file exists. Otherwise the
    first entry in MODEL_REGISTRY whose file is present. Raises if none are.
    """
    requested = os.environ.get("DINESENSE_MODEL", "").strip().lower()

    if requested:
        match = next((e for e in MODEL_REGISTRY if e["key"] == requested), None)
        if match is None:
            valid = ", ".join(e["key"] for e in MODEL_REGISTRY)
            raise ValueError(
                f"DINESENSE_MODEL='{requested}' is not a known model. Choose one of: {valid}"
            )
        if not (MODEL_DIR / match["file"]).exists():
            raise FileNotFoundError(
                f"DINESENSE_MODEL='{requested}' was requested but "
                f"{MODEL_DIR / match['file']} does not exist. Train it first, or unset "
                "the variable to use whichever model is available."
            )
        return match

    for entry in MODEL_REGISTRY:
        if (MODEL_DIR / entry["file"]).exists():
            return entry

    raise FileNotFoundError(
        "No trained model found in "
        f"{MODEL_DIR}. Run `python ml/train_baseline.py` (fast) or "
        "`python ml/train_bilstm_v2.py` first."
    )


@lru_cache(maxsize=1)
def _load_model():
    """Load the selected model once and keep it in memory."""
    global MODEL_VERSION

    entry = _select_entry()
    path = MODEL_DIR / entry["file"]
    MODEL_VERSION = entry["version"]

    if entry["kind"] == "keras":
        from tensorflow import keras
        model = keras.models.load_model(path)
    else:
        import joblib
        model = joblib.load(path)

    print(f"[predict] Serving '{entry['key']}' from {path.name}")
    return (entry["kind"], entry["key"], model)


def active_model_key() -> str:
    """Which model is serving. Safe to call before anything is loaded."""
    try:
        return _select_entry()["key"]
    except (FileNotFoundError, ValueError):
        return "none"


def predict_sentiment(text: str) -> tuple[str, float]:
    kind, _key, model = _load_model()
    cleaned = clean_text(text)
    if kind == "keras":
        import tensorflow as tf
        probs = model.predict(tf.constant([cleaned], dtype=tf.string), verbose=0)[0]
        idx = int(probs.argmax())
        return ID_TO_LABEL[idx], float(probs[idx])
    probs = model.predict_proba([cleaned])[0]
    idx = int(probs.argmax())
    return ID_TO_LABEL[idx], float(probs[idx])


# --------------------------------------------------------------------------
# Aspects
# --------------------------------------------------------------------------

def _clause_sentiment(clause: str) -> tuple[str, float]:
    """Score a clause by counting cue words, respecting simple negation."""
    tokens = clause.split()
    score = 0
    hits = 0
    for i, token in enumerate(tokens):
        word = token.strip(".,!?")
        polarity = 1 if word in POSITIVE_CUES else (-1 if word in NEGATIVE_CUES else 0)
        if polarity == 0:
            continue
        hits += 1
        window = {t.strip(".,!?") for t in tokens[max(0, i - 3):i]}
        if window & NEGATORS:
            polarity *= -1
        score += polarity

    if hits == 0:
        return "neutral", 0.34
    confidence = min(0.5 + 0.15 * abs(score), 0.95)
    if score > 0:
        return "positive", confidence
    if score < 0:
        return "negative", confidence
    return "neutral", 0.4


def extract_aspects(text: str) -> list[AspectResult]:
    cleaned = clean_text(text)
    # split on punctuation and contrastive conjunctions - "good food but slow service"
    clauses = re.split(r"[.!?;,]| but | however | although | though | while ", cleaned)
    clauses = [c.strip() for c in clauses if c.strip()]

    found: dict[str, AspectResult] = {}
    for clause in clauses:
        for aspect, keywords in ASPECT_KEYWORDS.items():
            if not any(kw in clause for kw in keywords):
                continue
            sentiment, confidence = _clause_sentiment(clause)
            existing = found.get(aspect)
            # keep the most confident, and prefer a non-neutral read
            if existing is None or (
                (sentiment != "neutral" and existing.sentiment == "neutral")
                or confidence > existing.confidence
            ):
                found[aspect] = AspectResult(aspect, sentiment, round(confidence, 3))

    return sorted(found.values(), key=lambda a: -a.confidence)


# --------------------------------------------------------------------------
# Urgency
# --------------------------------------------------------------------------

def detect_urgency(text: str) -> tuple[str, str | None]:
    """Classify how fast a human needs to see this review.

    Deliberately biased toward escalating. A false positive costs a manager
    thirty seconds of reading; a false negative means a guest reported illness
    and nobody was told. Those errors are not equally bad, so the rules do not
    treat them as if they were.
    """
    lowered = clean_text(text)

    for pattern, reason in HIGH_URGENCY_PATTERNS:
        if re.search(pattern, lowered):
            return "high", reason

    # Ambiguous symptoms escalate only alongside a mention of eating or drinking,
    # so "the loud music gave me a headache" stays routine while "I had the
    # prawns and got a headache" does not.
    if re.search(AMBIGUOUS_SYMPTOMS, lowered) and _mentions_eating(lowered):
        return "high", "possible foodborne illness"

    for pattern, reason in MEDIUM_URGENCY_PATTERNS:
        if re.search(pattern, lowered):
            return "medium", reason

    # A symptom with no eating context is still worth a human eye, just not an
    # emergency - this is the case the first version silently filed as routine.
    if re.search(AMBIGUOUS_SYMPTOMS, lowered):
        return "medium", "guest reported feeling unwell"

    return "low", None


# --------------------------------------------------------------------------
# Recommendations
# --------------------------------------------------------------------------

def recommend(aspects: list[AspectResult], urgency: str, sentiment: str) -> list[str]:
    actions: list[str] = []
    if urgency == "high":
        actions.append(ESCALATION)
    for aspect in aspects:
        if aspect.sentiment == "negative" and aspect.aspect in RECOMMENDATIONS:
            actions.append(RECOMMENDATIONS[aspect.aspect])
    if not actions and sentiment == "negative":
        actions.append("Negative review with no clear aspect - read it manually and follow up.")
    if not actions and sentiment == "positive":
        actions.append("No action needed. Consider sharing this with the team.")
    return actions


# --------------------------------------------------------------------------

def analyse_review(text: str) -> PredictionResult:
    """Full pipeline for one review."""
    sentiment, confidence = predict_sentiment(text)
    aspects = extract_aspects(text)
    urgency, reason = detect_urgency(text)

    # A food-safety hit outranks whatever the sentiment model thinks.
    if urgency == "high" and sentiment != "negative":
        sentiment = "negative"

    return PredictionResult(
        sentiment=sentiment,
        confidence=round(confidence, 4),
        urgency=urgency,
        urgency_reason=reason,
        aspects=aspects,
        recommendations=recommend(aspects, urgency, sentiment),
    )


if __name__ == "__main__":
    import json

    samples = sys.argv[1:] or [
        "The food was excellent, but the service was extremely slow.",
        "Found a piece of glass in my pasta and the manager just shrugged.",
        "Cozy little place, fair prices, and the staff were lovely.",
        "Waited over an hour and the chicken came out raw. Never again.",
    ]
    for sample in samples:
        print("\n" + "=" * 70)
        print(sample)
        print(json.dumps(analyse_review(sample).to_dict(), indent=2))
