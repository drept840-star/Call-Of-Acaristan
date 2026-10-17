"""engine.text - string tables, the font registry and text layout (§6.12/§6.13).

Phase 4 home for every player-facing string key (``T``), every font load
(``load_face``) and every measurement that keeps text inside its box
(``measure`` / ``wrap_lines`` / ``ellipsize`` / ``check_fit``). The
fontTools-backed TTF coverage reader is *not* here: engine code imports stdlib +
pygame only (boundary rule E1), so it lives in ``core.font_coverage``.

    from engine.text import T
    label = T("m1.hud.objective")          # "OBJECTIVE"
    heat = T("m5.hud.heat", n=3)           # formats {n}

English-only for now (R12): the architecture is ready for more languages, the
content is not translated.
"""
from __future__ import annotations

from .fonts import FACES, PLEX_ONLY, font_dir, load_face, missing_glyphs
from .layout import check_fit, draw_line, ellipsize, fits, measure, wrap_lines
from .strings import DEFAULT_TABLE, T, load_strings, marker, missing_keys, reset_strings, table

__all__ = [
    # strings (§6.13)
    "DEFAULT_TABLE", "T", "load_strings", "marker", "missing_keys", "reset_strings", "table",
    # fonts (§6.13)
    "FACES", "PLEX_ONLY", "font_dir", "load_face", "missing_glyphs",
    # layout (§6.12)
    "check_fit", "draw_line", "ellipsize", "fits", "measure", "wrap_lines",
]
