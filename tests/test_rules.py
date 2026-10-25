"""
Tests for the rule-based parts of the pipeline (aspects, urgency, cleaning).

These need no trained model, so they run in seconds:

    python -m pytest tests/ -v

The urgency tests matter most. These rules are the escalation path for
food-safety complaints - if one silently stops matching, a real complaint gets
filed as routine.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "ml"))

import pytest

from predict import detect_urgency, extract_aspects
from preprocessing import clean_text


# --------------------------------------------------------------------------
# Cleaning
# --------------------------------------------------------------------------

def test_clean_lowercases_and_strips():
    assert clean_text("  The FOOD was Great!  ") == "the food was great!"


def test_clean_removes_urls():
    assert "http" not in clean_text("see http://example.com/menu for details")


def test_clean_keeps_negation():
    # "not" must survive - stripping it flips the meaning of the review
    assert "not" in clean_text("The food was not good at all.")


def test_clean_handles_non_string():
    assert clean_text(None) == ""


# --------------------------------------------------------------------------
# Urgency - the escalation path
# --------------------------------------------------------------------------

# Regression tests. Every one of these was filed as LOW urgency by the first
# version of the rules - a guest reported illness and nobody would have been
# told. If any of these ever goes back to low, the escalation path is broken.
@pytest.mark.parametrize("text", [
    "I felt dizzy after eating the food",
    "the food was bit salty and after eating that I became all sweaty and fainted",
    "My stomach was upset all night after the curry",
    "Felt nauseous after the prawns",
    "Had a rash on my arms after the meal",
    "I could not breathe after eating the sauce",
    "Got a fever the next day after the buffet",
    "My stomach was turning after the oysters",
])
def test_illness_symptoms_escalate(text):
    urgency, reason = detect_urgency(text)
    assert urgency == "high", f"illness report filed as {urgency}: {text}"
    assert reason in {"possible foodborne illness", "allergic reaction"}


@pytest.mark.parametrize("text", [
    "Lovely evening, the pasta was delicious",
    "Great steak, friendly staff, will return",
    "The queue was long but the food was worth it",
    "Decent food, nothing special",
])
def test_ordinary_reviews_do_not_escalate(text):
    """The escalation bias must not swallow every positive review."""
    urgency, _ = detect_urgency(text)
    assert urgency == "low", f"ordinary review escalated to {urgency}: {text}"


def test_symptom_without_eating_context_is_medium_not_high():
    """A headache from loud music is worth a look, not an emergency."""
    urgency, reason = detect_urgency("The loud music gave me a headache")
    assert urgency == "medium"
    assert reason == "guest reported feeling unwell"


@pytest.mark.parametrize("text,expected_reason", [
    ("I got food poisoning after eating here", "possible foodborne illness"),
    ("My son had an allergic reaction to the sauce", "allergic reaction"),
    ("There was a hair in my soup", "foreign object in food"),
    ("Found a piece of glass in my pasta", "foreign object in food"),
    ("They charged me twice for the same order", "billing or payment dispute"),
    ("The manager screamed at my wife", "staff conduct or safety incident"),
    ("The chicken came out raw", "serious food-safety hazard"),
    ("There were cockroaches on the wall", "major cleanliness hazard"),
])
def test_high_urgency(text, expected_reason):
    urgency, reason = detect_urgency(text)
    assert urgency == "high", f"expected high urgency for: {text}"
    assert reason == expected_reason


@pytest.mark.parametrize("text", [
    "Never coming back here again",
    "I asked for a refund and no one helped",
    "We waited over an hour for two starters",
])
def test_medium_urgency(text):
    urgency, _ = detect_urgency(text)
    assert urgency == "medium", f"expected medium urgency for: {text}"


@pytest.mark.parametrize("text", [
    "Lovely evening, the pasta was delicious",
    "Decent food, nothing special",
    "The music was a bit loud for my taste",
])
def test_low_urgency(text):
    urgency, _ = detect_urgency(text)
    assert urgency == "low", f"expected low urgency for: {text}"


# --------------------------------------------------------------------------
# Aspects
# --------------------------------------------------------------------------

def test_contrastive_review_splits_correctly():
    """The headline case: one review, two aspects, opposite sentiments."""
    aspects = {a.aspect: a.sentiment for a in
               extract_aspects("The food was excellent, but the service was extremely slow.")}
    assert aspects.get("food_quality") == "positive"
    assert aspects.get("service") == "negative"


def test_negation_flips_aspect_sentiment():
    aspects = {a.aspect: a.sentiment for a in
               extract_aspects("The food was not good.")}
    assert aspects.get("food_quality") == "negative"


def test_multiple_aspects_detected():
    aspects = {a.aspect for a in
               extract_aspects("Rude staff, dirty bathroom, and overpriced drinks.")}
    assert {"staff_behaviour", "cleanliness", "price"} <= aspects


def test_no_aspect_returns_empty():
    assert extract_aspects("Went here on Tuesday with my brother.") == []
