"""Pose cache: render-once surfaces for parameterised procedural bodies.

``PoseCache.get(key, size, draw_cb)`` draws into a fresh SRCALPHA surface the
first time ``key`` is seen and returns the cached surface afterwards; the
oldest entries are evicted FIFO past ``cap`` (the legacy ``artpack.pose``
semantics, cap 512). One shared instance, ``POSES``, backs
``engine.assets.artpack.pose``; scenes may own private caches too.
"""
from __future__ import annotations

__all__ = ["PoseCache", "POSES", "POSE_CAP"]

POSE_CAP = 512


class PoseCache:
    def __init__(self, cap: int = POSE_CAP) -> None:
        self.cap = int(cap)
        self._surf: dict = {}
        self._order: list = []
        self.hits = 0
        self.misses = 0

    def get(self, key, size, draw_cb):
        surf = self._surf.get(key)
        if surf is None:
            import pygame
            surf = pygame.Surface(size, pygame.SRCALPHA)
            draw_cb(surf)
            self._surf[key] = surf
            self._order.append(key)
            self.misses += 1
            if len(self._order) > self.cap:
                self._surf.pop(self._order.pop(0), None)
        else:
            self.hits += 1
        return surf

    def clear(self) -> None:
        self._surf.clear()
        del self._order[:]

    def __len__(self) -> int:
        return len(self._surf)

    def __contains__(self, key) -> bool:
        return key in self._surf


POSES = PoseCache()
