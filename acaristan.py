
"""Thin launcher — run with `python acaristan.py` from the repo root.

Game lives in src/app.py (runs on import). Keep CWD at repo root so
CWD-relative assets (menu_theme.mp3, assets/, save_data.json) resolve.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

import app  # noqa: F401  (runs the game on import)
