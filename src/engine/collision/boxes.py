"""engine.collision.boxes - ray, segment and body queries against AABBs.

Boxes are ``(x0, y0, z0, x1, y1, z1)`` with ``x0 <= x1`` etc. A uniform XZ
bucket grid (``cell`` metres) keeps a query to the boxes near it; every query
returns the same answer a brute-force loop over all boxes would.
"""
from __future__ import annotations

import math
from typing import Iterable, Sequence

__all__ = ["BoxWorld", "ray_aabb"]

Box = Sequence[float]
Vec3 = Sequence[float]


def ray_aabb(o: Vec3, d: Vec3, lo: Vec3, hi: Vec3) -> float | None:
    """Slab test: distance along ``d`` to the first hit, 0 when ``o`` starts
    inside the box, None on a miss or a box wholly behind the ray."""
    tmin, tmax = 0.0, 1e9
    for i in range(3):
        if abs(d[i]) < 1e-9:
            if o[i] < lo[i] or o[i] > hi[i]:
                return None
            continue
        inv = 1.0 / d[i]
        t1 = (lo[i] - o[i]) * inv
        t2 = (hi[i] - o[i]) * inv
        if t1 > t2:
            t1, t2 = t2, t1
        if t1 > tmin:
            tmin = t1
        if t2 < tmax:
            tmax = t2
        if tmin > tmax:
            return None
    return tmin if tmax > 0.0 else None


class BoxWorld:
    def __init__(self, boxes: Iterable[Box], cell: float = 4.0) -> None:
        self.boxes: tuple[tuple[float, ...], ...] = tuple(tuple(map(float, b)) for b in boxes)
        self.cell = float(cell)
        self._grid: dict[tuple[int, int], list[int]] = {}
        for i, (x0, _y0, z0, x1, _y1, z1) in enumerate(self.boxes):
            for key in self._keys(x0, z0, x1, z1):
                self._grid.setdefault(key, []).append(i)

    def _keys(self, x0: float, z0: float, x1: float, z1: float):
        c = self.cell
        for gx in range(math.floor(x0 / c), math.floor(x1 / c) + 1):
            for gz in range(math.floor(z0 / c), math.floor(z1 / c) + 1):
                yield gx, gz

    def near(self, x0: float, z0: float, x1: float, z1: float) -> list[int]:
        """Indices of boxes whose buckets touch the XZ rectangle, ascending."""
        if x0 > x1:
            x0, x1 = x1, x0
        if z0 > z1:
            z0, z1 = z1, z0
        c = self.cell
        # a huge rectangle walks the bucket map instead of every empty cell
        if (x1 - x0) * (z1 - z0) > len(self._grid) * c * c:
            out = set()
            for (gx, gz), ids in self._grid.items():
                if gx * c <= x1 and (gx + 1) * c >= x0 and gz * c <= z1 and (gz + 1) * c >= z0:
                    out.update(ids)
            return sorted(out)
        out = set()
        for key in self._keys(x0, z0, x1, z1):
            ids = self._grid.get(key)
            if ids:
                out.update(ids)
        return sorted(out)

    def ray(self, o: Vec3, d: Vec3, tmax: float = 1e9) -> tuple[float, int] | None:
        """First hit along unit direction ``d`` within ``tmax``: (t, box index)."""
        ex, ez = o[0] + d[0] * tmax, o[2] + d[2] * tmax
        best = None
        for i in self.near(o[0], o[2], ex, ez):
            b = self.boxes[i]
            t = ray_aabb(o, d, b[:3], b[3:])
            if t is not None and t <= tmax and (best is None or t < best[0]):
                best = (t, i)
        return best

    def segment_blocked(self, a: Vec3, b: Vec3, slack: float = 0.2) -> bool:
        """True when a box stands between ``a`` and ``b``. A hit within
        ``slack`` of ``b`` does not count (the target leaning on the box)."""
        d = (b[0] - a[0], b[1] - a[1], b[2] - a[2])
        dist = math.sqrt(d[0] * d[0] + d[1] * d[1] + d[2] * d[2])
        if dist < 1e-6:
            return False
        u = (d[0] / dist, d[1] / dist, d[2] / dist)
        for i in self.near(a[0], a[2], b[0], b[2]):
            bx = self.boxes[i]
            t = ray_aabb(a, u, bx[:3], bx[3:])
            if t is not None and t < dist - slack:
                return True
        return False

    def body_hits(self, x: float, z: float, r: float, y0: float, y1: float) -> bool:
        """A vertical capsule-ish body (XZ square of half-size ``r`` between
        heights ``y0``..``y1``) overlaps a box."""
        for i in self.near(x - r, z - r, x + r, z + r):
            bx0, by0, bz0, bx1, by1, bz1 = self.boxes[i]
            if by1 <= y0 or by0 >= y1:
                continue
            if bx0 - r < x < bx1 + r and bz0 - r < z < bz1 + r:
                return True
        return False
