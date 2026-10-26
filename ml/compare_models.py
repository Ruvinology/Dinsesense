"""
Rebuild ml/saved_models/model_comparison.json from every model's metrics file.

    python ml/compare_models.py

The admin page reads model_comparison.json to show the comparison table, so run
this after training or re-scoring any model. Keys match MODEL_REGISTRY in
predict.py, so the page can mark which model is serving. Every score is on the
same 8,996-review test set.

Note: ml/evaluate.py also writes model_comparison.json, but only for the
baseline and BiLSTM v1. Run this script afterwards to restore the full table.
"""

from __future__ import annotations

import json
from pathlib import Path

SAVED = Path(__file__).resolve().parent / "saved_models"

# (key shown on the admin page, metrics file, note)
SOURCES = [
    ("baseline", "baseline_metrics.json", "TF-IDF + logistic regression"),
    ("bilstm_v1", "bilstm_metrics.json", "BiLSTM, learned embeddings"),
    ("bilstm_v2", "bilstm_v2_metrics.json", "BiLSTM, frozen GloVe embeddings"),
    ("transformer_v3", "transformer_v3/onnx_int8_metrics.json",
     "DistilRoBERTa fine-tuned, 8-bit ONNX (the version the app serves)"),
    ("transformer_v3_fp32", "transformer_v3/transformer_v3_metrics.json",
     "DistilRoBERTa fine-tuned, full precision (Colab result)"),
]


def main() -> None:
    comparison: dict[str, dict] = {}
    for key, filename, note in SOURCES:
        path = SAVED / filename
        if not path.exists():
            print(f"[compare] skipped {key}: {filename} not found")
            continue
        metrics = json.loads(path.read_text(encoding="utf-8"))
        comparison[key] = {
            "accuracy": metrics["test_accuracy"],
            "macro_f1": metrics["test_macro_f1"],
            "note": note,
        }

    out = SAVED / "model_comparison.json"
    out.write_text(json.dumps(comparison, indent=2) + "\n", encoding="utf-8")
    print(f"[compare] wrote {out}")
    for key, scores in comparison.items():
        print(f"  {key:<22} accuracy {scores['accuracy']:.4f}   macro F1 {scores['macro_f1']:.4f}")


if __name__ == "__main__":
    main()
