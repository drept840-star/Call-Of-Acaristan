"""Shared test setup: put ``src`` on sys.path and keep SDL headless.

Engine unit tests must not open a window or touch audio (R7, R9). Setting the
dummy drivers *before* pygame is imported makes that true even for the boot
and crash-report tests, which do call ``pygame.init()``.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

__all__ = ["ROOT", "SRC"]
