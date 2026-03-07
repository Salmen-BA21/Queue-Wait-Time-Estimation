"""Backend-local bootstrap for the FastAPI backend-for-frontend."""

from __future__ import annotations

import sys
from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from src.api.app import app  # noqa: E402


__all__ = ["app"]