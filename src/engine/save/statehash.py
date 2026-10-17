"""save.statehash - stable world hashing for determinism checks (RPE6 §6.17).

``statehash(world)`` canonically serialises a world dump (nested
dicts/lists of primitives, as produced by the component dump) and
returns its sha256.  Floats are quantised to 1e-4 before hashing: the
simulation is deterministic, but a hash that flips on the 9th decimal of
a benign float (e.g. a reordered summation) would report divergences
that are not gameplay differences.  1e-4 is far below one pixel at game
scale (positions are in pixels/metres), so real divergence still trips.
Dict keys are sorted; tuples and lists are equivalent; sets are sorted
by their canonical form.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any

__all__ = ["QUANTUM", "canonical", "statehash"]

QUANTUM = 1e-4


def canonical(value: Any):
    """The hash-stable form of ``value`` (floats quantised, keys sorted)."""
    if isinstance(value, bool) or value is None or isinstance(value, (int, str)):
        return value
    if isinstance(value, float):
        return round(value / QUANTUM)
    if isinstance(value, dict):
        return {str(k): canonical(value[k]) for k in sorted(value, key=str)}
    if isinstance(value, (list, tuple)):
        return [canonical(v) for v in value]
    if isinstance(value, (set, frozenset)):
        return sorted((canonical(v) for v in value), key=repr)
    return repr(value)


def statehash(world: Any) -> str:
    """sha256 hex of the canonical world dump."""
    blob = json.dumps(canonical(world), sort_keys=True, ensure_ascii=True,
                      separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()
