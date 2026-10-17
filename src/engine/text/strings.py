"""String tables (§6.13): keys -> English, ``T()`` with fallbacks.

English-only for now (R12): the architecture is ready for more languages and
nothing is translated. Keys are dotted ids (``"m5.caption.notice"``) and the
table lives in the content tree: ``src/game/content/strings/en.json``.

A missing key is never silent: ``T()`` returns a visible marker built from the
key and warns once on the ``text`` log channel, and ``missing_keys()`` feeds the
validator (``tools/ae_text_check.py``) and the unit tests. The master prompt
writes the dev marker as the U+27E6/U+27E7 brackets; the bundled faces have no
glyph for those (and the smoke glyph check would rightly flag them), so the
marker renders as ``[[key]]`` - same meaning, drawable everywhere.

Formatting: ``T("m5.heat", heat=3)`` fills ``"{heat}"`` placeholders. Every string
is run through ``str.format`` (standard rules: a literal brace is written
``{{`` / ``}}``), so a template with a missing or malformed field shows the
marker and warns once instead of raising - a content typo can never crash a
frame.
"""
from __future__ import annotations

import json
from pathlib import Path

from engine.core.log import get_log

__all__ = ["DEFAULT_TABLE", "T", "load_strings", "marker", "missing_keys", "reset_strings", "table"]

# game/content/strings/en.json, relative to src/ (this file is src/engine/text/strings.py).
DEFAULT_TABLE = (Path(__file__).resolve().parents[2] / "game" / "content" / "strings" / "en.json")

_TABLE: dict[str, str] = {}
_MISSING: set[str] = set()
_LOADED = False


def marker(key: str) -> str:
    """The visible stand-in for a missing key (``[[key]]``; see module docstring)."""
    return f"[[{key}]]"


def load_strings(path: str | Path | None = None) -> int:
    """(Re)load the table; returns the number of keys. A missing file is an empty table."""
    global _LOADED
    p = Path(path) if path else DEFAULT_TABLE
    _TABLE.clear()
    if p.exists():
        data = json.loads(p.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError(f"string table {p} must be a JSON object of key -> string")
        for k, v in data.items():
            _TABLE[str(k)] = str(v)
    _LOADED = True
    return len(_TABLE)


def table() -> dict[str, str]:
    """The live table (lazily loaded from the shipped path on first use)."""
    if not _LOADED:
        load_strings()
    return _TABLE


def reset_strings() -> None:
    """Test hook: forget table, keys and the loaded flag."""
    global _LOADED
    _TABLE.clear()
    _MISSING.clear()
    _LOADED = False


def missing_keys() -> tuple[str, ...]:
    """Keys looked up since the last reset that were not in the table (sorted)."""
    return tuple(sorted(_MISSING))


def T(key: str, *, default: str | None = None, **fmt: object) -> str:
    """Translate ``key``; ``default`` covers a missing key, ``**fmt`` fills ``{placeholders}``."""
    text = table().get(key)
    if text is None:
        _MISSING.add(key)
        get_log().warn_once("text", f"missing:{key}", f"missing string key {key!r} - showing the marker")
        text = default if default is not None else marker(key)
    try:
        text = text.format(**fmt)
    except (KeyError, IndexError, ValueError):
        get_log().warn_once("text", f"fmt:{key}", f"string {key!r} failed to format with {sorted(fmt)}")
        text = marker(key)
    return text
