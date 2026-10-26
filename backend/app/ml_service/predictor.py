"""Bridge between FastAPI and the ML code in ml/.

The model is loaded once, lazily, on the first request that needs it, then held
in memory. Loading a Keras model takes several seconds, so doing it per request
would make the API unusable.

If no trained model is present the API still starts and every other endpoint
works - the analysis endpoints return 503 rather than the whole service failing
to boot. That matters in deployment: a missing model file should degrade one
feature, not take down the site.
"""

from __future__ import annotations

import json
import logging
import sys
import threading
from pathlib import Path
from typing import Any

from app.config import settings

logger = logging.getLogger(__name__)

_lock = threading.Lock()
_analyse_fn = None
_load_error: str | None = None


def _import_ml():
    """Import ml/predict.py, which lives outside the backend package."""
    ml_dir = str(settings.ml_dir)
    if ml_dir not in sys.path:
        sys.path.insert(0, ml_dir)
    from predict import analyse_review  # type: ignore
    return analyse_review


def get_analyser():
    """Return the analyse_review function, loading the model on first use."""
    global _analyse_fn, _load_error

    if _analyse_fn is not None:
        return _analyse_fn

    with _lock:
        if _analyse_fn is not None:
            return _analyse_fn
        try:
            logger.info("Loading sentiment model from %s ...", settings.ml_dir)
            _analyse_fn = _import_ml()
            logger.info("Model loaded.")
        except Exception as exc:  # noqa: BLE001 - surfaced to the caller as 503
            _load_error = str(exc)
            logger.error("Could not load the model: %s", exc)
            raise
    return _analyse_fn


def is_ready() -> bool:
    """True if a model can be loaded. Used by /health."""
    try:
        get_analyser()
        return True
    except Exception:  # noqa: BLE001
        return False


def load_error() -> str | None:
    return _load_error


def analyse(text: str) -> dict[str, Any]:
    """Run the full pipeline on one review and return a plain dict."""
    return get_analyser()(text).to_dict()


def active_model_name() -> str:
    """Which model would actually serve a request right now.

    Delegates to ml/predict.py so there is one source of truth - duplicating the
    selection logic here is how /health ends up confidently reporting a
    different model from the one answering requests.
    """
    try:
        _import_ml()  # ensures ml/ is on sys.path
        from predict import active_model_key  # type: ignore
        return active_model_key()
    except Exception:  # noqa: BLE001 - never let a status endpoint raise
        return "none"


def active_model_version() -> str:
    """Version label ("v3", "v2", ...) of the model that would serve right now.

    Delegates to ml/predict.py for the same reason as active_model_name().
    """
    try:
        _import_ml()
        from predict import active_model_version as _version  # type: ignore
        return _version()
    except Exception:  # noqa: BLE001 - never let a status endpoint raise
        return "none"


def read_metrics() -> dict[str, Any]:
    """Load whatever metrics files exist so the dashboard can show them."""
    out: dict[str, Any] = {}
    saved = settings.ml_dir / "saved_models"
    for key, filename in (
        ("baseline", "baseline_metrics.json"),
        ("bilstm", "bilstm_metrics.json"),
        ("bilstm_v2", "bilstm_v2_metrics.json"),
        ("transformer_v3", "transformer_v3/transformer_v3_metrics.json"),
        ("transformer_v3_int8", "transformer_v3/onnx_int8_metrics.json"),
        ("comparison", "model_comparison.json"),
        ("history", "bilstm_history.json"),
        ("history_bilstm_v2", "bilstm_v2_history.json"),
        ("history_transformer_v3", "transformer_v3/transformer_v3_history.json"),
    ):
        path = saved / filename
        if path.exists():
            try:
                out[key] = json.loads(path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                logger.warning("Malformed metrics file: %s", path)
    return out
