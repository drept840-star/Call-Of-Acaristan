"""game.timelines - cutscene shot-list access (RPE6 Phase 8).

Cutscene sequencing lives as ``ae.timeline/1`` data under
``src/game/content/timelines/<id>.timeline.json`` (validated by
``engine.timeline``) and is converted back into the legacy shot dicts
``app.CutscenePlayer`` consumes.  The JSON-native lists under the known
tuple keys (``lighting``, ``cues``, ``dialogue_events``) are restored to
tuples recursively, so the converted dicts compare equal - and behave
equal - to the legacy tables.

``ACA_TL_SRC=legacy`` returns the caller's legacy list untouched, the
strangler fallback (tables stay in code until a later phase deletes them
deliberately).
"""
from __future__ import annotations

import os

import json

from engine.timeline import from_dict, load_timeline

__all__ = ["TIMELINES_DIR", "use_legacy", "timeline", "shots", "save_timeline"]

TIMELINES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "content", "timelines")

_TUPLE_KEYS = {"lighting", "cues", "dialogue_events"}

_cache: dict = {}


def use_legacy() -> bool:
    return os.environ.get("ACA_TL_SRC", "").strip().lower() == "legacy"


def timeline(timeline_id: str):
    """Load (and cache) one ``ae.timeline/1`` document by id."""
    if timeline_id not in _cache:
        _cache[timeline_id] = load_timeline(os.path.join(TIMELINES_DIR, f"{timeline_id}.timeline.json"))
    return _cache[timeline_id]


def save_timeline(timeline_id: str, data: dict) -> str:
    """Write an edited ``ae.timeline/1`` document back to its data file.

    RPE6 Phase 10 (§6.20 editors write data files only): validates first,
    writes in the same canonical shape as `tools/ae_timeline_edit.py`,
    and drops the cached parse so the next `timeline()` re-reads it.
    """
    from_dict(data, source=f"{timeline_id}.timeline.json")   # raises on problems
    path = os.path.join(TIMELINES_DIR, f"{timeline_id}.timeline.json")
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(data, indent=1, ensure_ascii=False) + "\n")
    _cache.pop(timeline_id, None)
    return path


def _retuple(v):
    if isinstance(v, list):
        return tuple(_retuple(x) for x in v)
    return v


def shots(timeline_id: str, legacy_shots):
    """Legacy shot dicts for ``timeline_id`` (fresh dicts; legacy mode: identity)."""
    if use_legacy():
        return legacy_shots
    out = []
    for raw in timeline(timeline_id).shots:
        shot = {}
        for k, v in raw.items():
            shot[k] = _retuple(v) if k in _TUPLE_KEYS else v
        out.append(shot)
    return out
