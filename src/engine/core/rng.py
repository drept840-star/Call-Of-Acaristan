"""Named, seeded random streams (R6, §6.1).

Each subsystem asks for its own stream (``rngs.stream("ai")``). Streams are
derived from one master seed plus the stream name via SHA-256, so adding a new
consumer never shifts another subsystem's sequence (BUGS B-002).
"""
from __future__ import annotations

import hashlib
import random

__all__ = ["LEGACY", "LEGACY_RNG", "RngStreams", "derive_seed"]

# The process-global ``random`` instance that the ``random.X`` module
# functions are bound to. Legacy game code calls it as the named "legacy"
# stream (``_rng_legacy.X``) so its seeding and sequence are unchanged (R2/R6);
# new code must use its own ``App.rng.stream(name)``.
LEGACY = "legacy"
LEGACY_RNG: random.Random = random._inst  # type: ignore[attr-defined]


def derive_seed(master: int, name: str) -> int:
    h = hashlib.sha256(f"{int(master)}:{name}".encode("utf-8")).digest()
    return int.from_bytes(h[:8], "big")


class RngStreams:
    def __init__(self, master_seed: int = 0) -> None:
        self.master_seed = int(master_seed)
        self._streams: dict[str, random.Random] = {}
        self._adopted: set[str] = set()

    def stream(self, name: str) -> random.Random:
        s = self._streams.get(name)
        if s is None:
            s = random.Random(derive_seed(self.master_seed, name))
            self._streams[name] = s
        return s

    def adopt(self, name: str, rnd: random.Random) -> random.Random:
        """Register an existing Random (legacy seeding kept for parity)."""
        self._streams[name] = rnd
        self._adopted.add(name)
        return rnd

    def reseed(self, master_seed: int) -> None:
        self.master_seed = int(master_seed)
        for name, s in self._streams.items():
            if name in self._adopted:   # adopted streams keep their legacy seeding
                continue
            s.seed(derive_seed(self.master_seed, name))

    def names(self) -> list[str]:
        return sorted(self._streams)

    def snapshot(self) -> dict:
        return {"master_seed": self.master_seed,
                "streams": {n: s.getstate() for n, s in self._streams.items()}}

    def restore(self, snap: dict) -> None:
        self.master_seed = int(snap["master_seed"])
        for n, st in snap["streams"].items():
            self.stream(n).setstate(st)
