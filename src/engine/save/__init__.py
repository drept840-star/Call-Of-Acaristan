"""engine.save - snapshots and determinism hashing (RPE6 §6.17, Phase 9).

``ae.save/1`` snapshots (mission vars, component world dump, named RNG
stream states, clock frame) with canonical serialisation, plus
``statehash`` for replay determinism checks.  The host captures/applies
snapshots against the live game; this package validates and hashes only.
"""
from __future__ import annotations

from .snapshot import SCHEMA, SaveError, dumps, from_dict, loads, validate
from .statehash import QUANTUM, canonical, statehash

__all__ = ["QUANTUM", "SCHEMA", "SaveError", "canonical", "dumps", "from_dict", "loads", "statehash", "validate"]
