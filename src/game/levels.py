"""game.levels - level-data access for the missions (RPE6 §6.16, Phase 7).

One place decides where a mission grid comes from:

- default: ``src/game/content/levels/<id>.level.json`` (engine.level) - the data
  the exporter produced from the legacy generators and the validator keeps equal;
- ``ACA_LEVEL_SRC=legacy``: the mission's own generator output (fallback while a
  flip is being proven; the check tool fails CI if the two ever diverge, so the
  fallback can never silently become a second truth).

``grid(level_id, legacy_grid)`` is called by mission map modules at import: it
returns a ``list[str]`` and never anything else (the runtime map contract). The
legacy object itself is returned under ``ACA_LEVEL_SRC=legacy`` (identity and
marker-rebinding behaviour of the generating module are untouched).
"""
from __future__ import annotations

import os

from engine.level import load_level

__all__ = ["LEVELS_DIR", "use_legacy", "grid", "level"]

_here = os.path.dirname(os.path.abspath(__file__))
LEVELS_DIR = os.path.join(_here, "content", "levels")
_cache: dict[str, object] = {}


def use_legacy() -> bool:
    return os.environ.get("ACA_LEVEL_SRC", "").strip().lower() == "legacy"


def level(level_id: str):
    """The parsed ``Level`` (cached), or ``None`` when no data file exists."""
    if level_id not in _cache:
        path = os.path.join(LEVELS_DIR, level_id + ".level.json")
        _cache[level_id] = load_level(path) if os.path.exists(path) else None
    return _cache[level_id]


def grid(level_id: str, legacy_grid):
    """Level grid for ``level_id``: data by default, ``legacy_grid`` under ACA_LEVEL_SRC=legacy."""
    if use_legacy():
        return legacy_grid
    lvl = level(level_id)
    if lvl is None:
        return legacy_grid
    return lvl.grid("floor")
