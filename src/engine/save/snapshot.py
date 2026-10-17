"""save.snapshot - the ae.save/1 snapshot model (RPE6 §6.17, Phase 9).

A snapshot is plain JSON data with a versioned schema::

    {"schema": "ae.save/1", "id": "m5.checkpoint.print",
     "frame": 12345, "mission": "m5",
     "vars": {...},                      # mission vars and flags (host-declared)
     "world": {...},                     # component dump (see statehash)
     "rng": {"legacy": [...]},           # named-stream states, host-encoded
     "clock": {"frame": 12345}}

The kernel validates and canonically serialises; capturing and applying
a snapshot against the live game is the host's side of the protocol
(it owns STATE, the world and the streams).  ``validate`` returns
human-readable problems; ``dumps``/``loads`` round-trip byte-stably.
"""
from __future__ import annotations

import json
from typing import Any

__all__ = ["SCHEMA", "SaveError", "validate", "dumps", "loads", "from_dict"]

SCHEMA = "ae.save/1"
_TOP = {"schema", "id", "frame", "mission", "vars", "world", "rng", "clock", "metadata"}


class SaveError(ValueError):
    """A snapshot is malformed or fails validation."""


def validate(data: Any) -> list[str]:
    out: list[str] = []
    if not isinstance(data, dict):
        return ["snapshot is not a JSON object"]
    for k in data:
        if k not in _TOP:
            out.append(f"unknown top-level key {k!r}")
    if data.get("schema") != SCHEMA:
        out.append(f"schema is {data.get('schema')!r}, expected {SCHEMA!r}")
    if not isinstance(data.get("id"), str) or not data["id"]:
        out.append("id missing")
    if not isinstance(data.get("mission"), str) or not data["mission"]:
        out.append("mission missing")
    frame = data.get("frame")
    if not isinstance(frame, int) or isinstance(frame, bool) or frame < 0:
        out.append("frame must be a non-negative int")
    for key in ("vars", "world", "rng", "clock"):
        if key in data and not isinstance(data[key], dict):
            out.append(f"{key} must be an object")
    try:
        json.dumps(data)
    except (TypeError, ValueError) as e:
        out.append(f"snapshot is not JSON-serialisable: {e}")
    return out


def from_dict(data: dict, source: str = "") -> dict:
    problems = validate(data)
    if problems:
        raise SaveError(f"{source or 'snapshot'}: " + "; ".join(problems))
    return data


def dumps(data: dict) -> str:
    """Canonical serialisation (sorted keys; stable across runs)."""
    from_dict(data)
    return json.dumps(data, sort_keys=True, ensure_ascii=True, indent=1) + "\n"


def loads(text: str, source: str = "<string>") -> dict:
    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        raise SaveError(f"{source}: invalid JSON: {e}") from e
    return from_dict(data, source)
