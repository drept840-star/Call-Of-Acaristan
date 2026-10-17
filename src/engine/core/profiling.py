"""Scoped timers (§6.22). Uses perf_counter: profiling only, never simulation."""
from __future__ import annotations

import time
from contextlib import contextmanager

__all__ = ["Profiler"]


class Profiler:
    def __init__(self) -> None:
        self._s: dict[str, list[float]] = {}

    @contextmanager
    def scope(self, name: str):
        t0 = time.perf_counter()
        try:
            yield
        finally:
            self._s.setdefault(name, []).append((time.perf_counter() - t0) * 1000.0)

    def stats(self) -> dict[str, dict[str, float]]:
        out = {}
        for k, v in self._s.items():
            sv = sorted(v)
            out[k] = {"n": len(sv), "avg_ms": sum(sv) / len(sv), "p99_ms": sv[min(len(sv) - 1, int(len(sv) * 0.99))],
                      "max_ms": sv[-1]}
        return out

    def reset(self) -> None:
        self._s.clear()
