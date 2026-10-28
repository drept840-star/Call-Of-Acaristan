"""Thin launcher — run with `python acaristan.py` from the repo root.

Game lives in src/app.py (runs on import). Keep CWD at repo root so
CWD-relative assets (menu_theme.mp3, assets/, save_data.json) resolve.
Pass `--launcher` (or run `python launcher.py`) to open the pre-game
KRAPNET Launcher & Auto-Updater window before starting the game.
"""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

if "--launcher" in sys.argv and os.environ.get("ACA_FROM_LAUNCHER") != "1":
    from launcher import run_launcher
    raise SystemExit(run_launcher(ROOT, demo_update=("--demo-update" in sys.argv)))

import app  # noqa: F401  (runs the game on import)
