"""Hot reload for development (§6.5): poll the files behind loaded assets and
call ``AssetRegistry.reload`` when one changes.

Stdlib only (no watchdog dependency): ``AssetWatcher.poll()`` compares mtimes
and is meant to be called from the host loop every ~500 ms (``interval_ms``);
``AssetWatcher.run_once()`` is the same thing without the throttle (tests).
Reloads re-import the sprite module, drop the asset's cache entries and emit
``AssetReloaded`` on the registry's bus; live scenes re-``get`` next frame.
"""
from __future__ import annotations

import os

from .registry import AssetRegistry

__all__ = ["AssetWatcher"]


class AssetWatcher:
    def __init__(self, registry: AssetRegistry, *, interval_ms: int = 500) -> None:
        self.registry = registry
        self.interval_ms = int(interval_ms)
        self._files: dict[str, list[str]] = {}
        self._mtimes: dict[str, float] = {}
        self._last_poll = -10 ** 9
        self.reloads = 0
        self.rescan()

    def rescan(self) -> int:
        """(Re)collect the watched file list from the registry; returns file count."""
        self._files = self.registry.watched_files()
        n = 0
        for files in self._files.values():
            for f in files:
                n += 1
                self._mtimes.setdefault(f, self._mtime(f))
        return n

    @staticmethod
    def _mtime(path: str) -> float:
        try:
            return os.stat(path).st_mtime
        except OSError:
            return -1.0

    def run_once(self) -> list[str]:
        """Check every watched file now; reload changed assets; return their ids."""
        changed_files = {}
        for f in {f for files in self._files.values() for f in files}:
            mt = self._mtime(f)
            if mt != self._mtimes.get(f):
                self._mtimes[f] = mt
                changed_files[f] = mt
        if not changed_files:
            return []
        hit = []
        for aid, files in self._files.items():
            why = [os.path.basename(f) for f in files if f in changed_files]
            if why:
                self.registry.reload(aid, "changed: " + ", ".join(why))
                self.reloads += 1
                hit.append(aid)
        return hit

    def poll(self, now_ms: int) -> list[str]:
        """Throttled ``run_once`` for host loops (``now_ms`` from the engine clock)."""
        if now_ms - self._last_poll < self.interval_ms:
            return []
        self._last_poll = now_ms
        return self.run_once()
