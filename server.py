"""Vercel entry point for the DineSense API.

Vercel looks for a FastAPI instance named `app` in server.py at the project
root. The real application lives in backend/app/main.py and imports its own
modules as `app.*`, so backend/ goes on the import path first. Deploying from
the repo root (rather than from backend/) keeps ml/ - the model and predict.py -
inside the deployment.

Locally nothing changes: run `uvicorn app.main:app --reload` from backend/.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "backend"))

from app.main import app  # noqa: E402,F401  - Vercel serves this
