"""Font glyph coverage - the fontTools half of §6.13 (dev/audit only).

``engine.text`` owns the registry (``FACES`` / ``font_dir`` / ``load_face``) and
the per-character verdict (``missing_glyphs``), all of it stdlib + pygame.
Reading the TTFs needs fontTools, which is a dev-only dependency and not on the
engine's import allowlist (boundary rule E1), so the reader lives here on the
game/tools side.

    from core import font_coverage as FC
    if FC.coverage_supported():
        cov = FC.glyph_coverage()
        bad = FC.missing_glyphs(text, cov)      # {codepoint: [faces lacking it]}

Without fontTools ``coverage_supported()`` is False and ``glyph_coverage()``
returns ``{}``; callers treat that as "cannot check" and skip.
"""
from __future__ import annotations

import os
from pathlib import Path

from engine.text import FACES, font_dir
from engine.text import missing_glyphs as _missing_glyphs

__all__ = ["coverage_supported", "glyph_coverage", "missing_glyphs"]


def coverage_supported() -> bool:
    """True when fontTools is importable (dev machines and tools; false in slim builds)."""
    try:
        import fontTools.ttLib  # noqa: F401
    except ImportError:
        return False
    return True


def glyph_coverage(root: str | Path | None = None) -> dict[str, set[int]]:
    """``{face: set of codepoints}`` for every bundled face that exists; ``{}`` without fontTools."""
    try:
        from fontTools.ttLib import TTFont
    except ImportError:
        return {}
    cov: dict[str, set[int]] = {}
    for key, fname in FACES.items():
        path = os.path.join(font_dir(root), fname)
        if not os.path.exists(path):
            continue
        font = TTFont(path, fontNumber=0, lazy=True)
        chars: set[int] = set()
        for table in font["cmap"].tables:
            chars |= set(table.cmap.keys())
        cov[key] = chars
    return cov


def missing_glyphs(text: str, coverage: dict[str, set[int]] | None = None,
                   *, plex_only_ok: bool = True) -> dict[int, list[str]]:
    """The engine verdict (``engine.text.missing_glyphs``) with the TTF read supplied."""
    return _missing_glyphs(text, coverage if coverage is not None else glyph_coverage(),
                           plex_only_ok=plex_only_ok)
