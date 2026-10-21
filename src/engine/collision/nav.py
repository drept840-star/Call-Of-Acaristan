"""engine.collision.nav - A* on a walkability grid (RPE6 §6.9 ``GridGraph``).

The grid samples ``walkable(x, z)`` at every cell centre once, at build time;
pass a test that already includes the body radius. ``height(x, z)`` (optional)
gives the floor under a cell: neighbours more than ``step`` apart in height are
not connected (a ledge, a platform edge too tall to climb).

``path(a, b)`` is 8-connected A* with no corner cutting and an octile
heuristic, then string-pulled: each waypoint is the farthest one still
reachable in a straight line, so agents walk diagonals instead of stairs.
"""
from __future__ import annotations

import heapq
import math
from typing import Callable, Sequence

__all__ = ["GridNav"]

_SQRT2 = math.sqrt(2.0)
_NBRS = ((1, 0, 1.0), (-1, 0, 1.0), (0, 1, 1.0), (0, -1, 1.0),
         (1, 1, _SQRT2), (1, -1, _SQRT2), (-1, 1, _SQRT2), (-1, -1, _SQRT2))


class GridNav:
    def __init__(self, bounds: Sequence[float], cell: float,
                 walkable: Callable[[float, float], bool],
                 height: Callable[[float, float], float] | None = None,
                 step: float = math.inf, max_nodes: int = 40000,
                 cache_size: int = 64) -> None:
        self.x0, self.x1, self.z0, self.z1 = (float(v) for v in bounds)
        self.cell = float(cell)
        self.cols = max(1, math.ceil((self.x1 - self.x0) / self.cell))
        self.rows = max(1, math.ceil((self.z1 - self.z0) / self.cell))
        self.step = float(step)
        self.max_nodes = int(max_nodes)
        self._height_fn = height
        self._walk = bytearray(self.cols * self.rows)
        self._h = [0.0] * (self.cols * self.rows)
        for r in range(self.rows):
            for c in range(self.cols):
                x, z = self.center(c, r)
                i = r * self.cols + c
                self._walk[i] = 1 if walkable(x, z) else 0
                if height is not None:
                    self._h[i] = float(height(x, z))
        self._cache: dict[tuple[int, int], list[tuple[float, float, float]]] = {}
        self._cache_size = int(cache_size)

    # ── cells ─────────────────────────────────────────────────────────
    def center(self, c: int, r: int) -> tuple[float, float]:
        return self.x0 + (c + 0.5) * self.cell, self.z0 + (r + 0.5) * self.cell

    def cell_at(self, x: float, z: float) -> tuple[int, int] | None:
        c = math.floor((x - self.x0) / self.cell)
        r = math.floor((z - self.z0) / self.cell)
        if 0 <= c < self.cols and 0 <= r < self.rows:
            return c, r
        return None

    def _ok(self, c: int, r: int) -> bool:
        return 0 <= c < self.cols and 0 <= r < self.rows and self._walk[r * self.cols + c] == 1

    def is_walkable(self, x: float, z: float) -> bool:
        cr = self.cell_at(x, z)
        return cr is not None and self._ok(*cr)

    def floor(self, x: float, z: float) -> float:
        if self._height_fn is not None:
            return float(self._height_fn(x, z))
        return 0.0

    def nearest(self, x: float, z: float, reach: int = 6) -> tuple[int, int] | None:
        """The walkable cell closest to (x, z) within ``reach`` cells."""
        c0 = min(self.cols - 1, max(0, math.floor((x - self.x0) / self.cell)))
        r0 = min(self.rows - 1, max(0, math.floor((z - self.z0) / self.cell)))
        if self._ok(c0, r0):
            return c0, r0
        best, best_d = None, math.inf
        for ring in range(1, reach + 1):
            for c in range(c0 - ring, c0 + ring + 1):
                for r in (r0 - ring, r0 + ring) if abs(c - c0) < ring else range(r0 - ring, r0 + ring + 1):
                    if self._ok(c, r):
                        cx, cz = self.center(c, r)
                        d = (cx - x) ** 2 + (cz - z) ** 2
                        if d < best_d:
                            best, best_d = (c, r), d
            if best is not None:
                return best
        return None

    def _link(self, i: int, j: int) -> bool:
        return abs(self._h[i] - self._h[j]) <= self.step

    # ── queries ───────────────────────────────────────────────────────
    def walk_clear(self, a: Sequence[float], b: Sequence[float]) -> bool:
        """Every point of the straight walk from ``a`` to ``b`` (x, _, z) is on
        walkable cells with no step taller than ``step``."""
        ax, az, bx, bz = a[0], a[-1], b[0], b[-1]
        n = max(1, math.ceil(math.hypot(bx - ax, bz - az) / (self.cell * 0.35)))
        prev = None
        for k in range(n + 1):
            f = k / n
            cr = self.cell_at(ax + (bx - ax) * f, az + (bz - az) * f)
            if cr is None or not self._ok(*cr):
                return False
            i = cr[1] * self.cols + cr[0]
            if prev is not None and i != prev and not self._link(prev, i):
                return False
            prev = i
        return True

    def path(self, a: Sequence[float], b: Sequence[float]) -> list[tuple[float, float, float]]:
        """Waypoints (x, floor, z) from ``a`` toward ``b``, start excluded.
        The last point is ``b`` itself when ``b`` is walkable, else the centre
        of the nearest walkable cell. Empty when no route exists."""
        s = self.nearest(a[0], a[-1])
        g = self.nearest(b[0], b[-1])
        if s is None or g is None:
            return []
        key = (s[1] * self.cols + s[0], g[1] * self.cols + g[0])
        cells = self._cache.get(key)
        if cells is None:
            cells = self._astar(s, g)
            if len(self._cache) >= self._cache_size:
                self._cache.pop(next(iter(self._cache)))
            self._cache[key] = cells
        if not cells and s != g:
            return []
        goal = (b[0], b[-1]) if self.is_walkable(b[0], b[-1]) else self.center(*g)
        pts = [self.center(c, r) for c, r in cells[1:-1]] + [goal]
        out, here = [], (a[0], a[-1])
        i = 0
        while i < len(pts):
            j = len(pts) - 1
            while j > i and not self.walk_clear(here, pts[j]):
                j -= 1
            here = pts[j]
            out.append((here[0], self.floor(*here), here[1]))
            i = j + 1
        return out

    def _astar(self, s: tuple[int, int], g: tuple[int, int]) -> list[tuple[int, int]]:
        cols = self.cols
        si, gi = s[1] * cols + s[0], g[1] * cols + g[0]
        gx, gz = g

        def h(c: int, r: int) -> float:
            dx, dz = abs(c - gx), abs(r - gz)
            return (dx + dz) + (_SQRT2 - 2.0) * min(dx, dz)

        best = {si: 0.0}
        prev = {si: -1}
        heap = [(h(*s), 0.0, si)]
        expanded = 0
        while heap:
            _f, cost, i = heapq.heappop(heap)
            if i == gi:
                break
            if cost > best.get(i, math.inf):
                continue
            expanded += 1
            if expanded > self.max_nodes:
                return []
            c, r = i % cols, i // cols
            for dc, dr, w in _NBRS:
                nc, nr = c + dc, r + dr
                if not self._ok(nc, nr):
                    continue
                j = nr * cols + nc
                if not self._link(i, j):
                    continue
                if dc and dr and not (self._ok(c + dc, r) and self._ok(c, r + dr)):
                    continue            # no corner cutting
                nc_cost = cost + w
                if nc_cost < best.get(j, math.inf):
                    best[j] = nc_cost
                    prev[j] = i
                    heapq.heappush(heap, (nc_cost + h(nc, nr), nc_cost, j))
        if gi not in prev:
            return []
        out = []
        i = gi
        while i != -1:
            out.append((i % cols, i // cols))
            i = prev[i]
        out.reverse()
        return out
