"""Font registry and the glyph verdict (§6.13).

One home for the four bundled faces (R5) and for the exact loader the game has
always used: ``pygame.font.Font(path, size)`` when the file exists, else
``pygame.font.SysFont(family, size, bold)`` - a missing asset degrades to a
system face instead of crashing. ``core.config`` calls ``load_face`` for every
font it exposes, so there is a single font-loading path in the tree.

The TTF reader that backs the coverage check needs fontTools - a dev-only
dependency, not on the engine's import allowlist (boundary rule E1) - so it
lives in ``core.font_coverage``. This module keeps the faces table, the
Plex-only allowlist and the per-character verdict (``missing_glyphs``), which
are stdlib + pygame only. The smoke test's source scan owns the string-literal
walk.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pygame

__all__ = ["FACES", "PLEX_ONLY", "font_dir", "load_face", "missing_glyphs"]

# face key -> bundled filename (assets/fonts)
FACES = {
    "plex_regular": "IBMPlexMono-Regular.ttf",
    "plex_bold": "IBMPlexMono-Bold.ttf",
    "plex_semibold": "IBMPlexMono-SemiBold.ttf",
    "oswald": "Oswald.ttf",
}

# Characters that exist only in the Plex faces: arrows and the full block. Any
# string using them must be drawn with a Plex face, never Oswald.
PLEX_ONLY = frozenset({0x2190, 0x2191, 0x2192, 0x2193, 0x2588})

# src/engine/text/fonts.py -> repo root
_REPO = Path(__file__).resolve().parents[3]


def font_dir(root: str | Path | None = None) -> str:
    """``<base>/assets/fonts``; ``base`` is the frozen bundle when frozen, else the repo."""
    if root:
        base = Path(root)
    elif getattr(sys, "frozen", False):
        base = Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    else:
        base = _REPO
    return str(base / "assets" / "fonts")


def load_face(source: str, size: int, fallback_family: str = "Consolas", bold: bool = False,
              root: str | Path | None = None) -> pygame.font.Font:
    """Load a bundled face (a ``FACES`` key or a raw path), else the system fallback."""
    path = source if source in FACES else source
    if source in FACES:
        path = os.path.join(font_dir(root), FACES[source])
    try:
        if os.path.exists(path):
            return pygame.font.Font(path, size)
    except Exception:  # noqa: BLE001 - a broken face must not take the game down
        pass
    return pygame.font.SysFont(fallback_family, size, bold=bold)


def missing_glyphs(text: str, coverage: dict[str, set[int]] | None = None,
                   *, plex_only_ok: bool = True) -> dict[int, list[str]]:
    """``{codepoint: [faces lacking it]}`` for non-ASCII characters of ``text``.

    Returns ``{}`` when every character is covered, and also when no
    ``coverage`` map is passed: reading the TTFs needs fontTools and lives in
    ``core.font_coverage`` (dev/tools side), so without a map there is nothing
    to check against. With ``plex_only_ok`` (default) the Plex-only set is
    skipped - those characters are legitimate in Plex-drawn text.
    """
    cov = coverage
    if not cov:
        return {}
    out: dict[int, list[str]] = {}
    for ch in text:
        cp = ord(ch)
        if cp < 128:
            continue
        if plex_only_ok and cp in PLEX_ONLY:
            continue
        lacking = sorted(k for k, chars in cov.items() if cp not in chars)
        if lacking:
            out[cp] = lacking
    return out
