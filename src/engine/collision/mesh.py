"""engine.collision.mesh - exact hitboxes from a mesh's own triangles.

``MeshCollider`` holds one mesh in local space (built once per asset).
``Placement`` puts it at ``(x, y, z)`` with a yaw in ``rot_y`` degrees, the same
convention the renderer uses, and answers rays and body overlaps against the
triangles themselves. A body only collides where the model is solid.

Queries transform into local space, so one collider serves every copy of a
moving prop (a truck rebuilt per frame costs a few multiplies, not a new grid).
"""
from __future__ import annotations

import math
from typing import Iterable, Sequence

__all__ = ["MeshCollider", "Placement"]

Vec3 = Sequence[float]
_EPS = 1e-9


def _sub(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def _dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _ray_tri(o, d, tri, tmax):
    """Moller-Trumbore, both faces: distance along ``d`` or None."""
    a, b, c = tri
    e1, e2 = _sub(b, a), _sub(c, a)
    p = _cross(d, e2)
    det = _dot(e1, p)
    if abs(det) < _EPS:
        return None
    inv = 1.0 / det
    s = _sub(o, a)
    u = _dot(s, p) * inv
    if u < 0.0 or u > 1.0:
        return None
    q = _cross(s, e1)
    v = _dot(d, q) * inv
    if v < 0.0 or u + v > 1.0:
        return None
    t = _dot(e2, q) * inv
    return t if 0.0 <= t <= tmax else None


def _clip(poly, axis, sign, value):
    """Sutherland-Hodgman: keep the part of ``poly`` where sign*(p[axis]-value) >= 0."""
    out = []
    n = len(poly)
    for i in range(n):
        p, q = poly[i], poly[(i + 1) % n]
        dp = sign * (p[axis] - value)
        dq = sign * (q[axis] - value)
        if dp >= 0.0:
            out.append(p)
        if (dp >= 0.0) != (dq >= 0.0):
            k = dp / (dp - dq)
            out.append(tuple(p[j] + (q[j] - p[j]) * k for j in range(3)))
    return out


def _xz_dist2(px, pz, poly):
    """Squared XZ distance from (px, pz) to a convex polygon (0 inside)."""
    n = len(poly)
    best = math.inf
    pos = neg = False
    for i in range(n):
        ax, az = poly[i][0], poly[i][2]
        bx, bz = poly[(i + 1) % n][0], poly[(i + 1) % n][2]
        ex, ez = bx - ax, bz - az
        cr = ex * (pz - az) - ez * (px - ax)
        if cr > 0.0:
            pos = True
        elif cr < 0.0:
            neg = True
        ll = ex * ex + ez * ez
        t = 0.0 if ll < _EPS else min(1.0, max(0.0, ((px - ax) * ex + (pz - az) * ez) / ll))
        dx, dz = ax + ex * t - px, az + ez * t - pz
        best = min(best, dx * dx + dz * dz)
    if pos != neg:  # strictly one side of every edge: inside a non-degenerate polygon
        return 0.0
    return best


class MeshCollider:
    """Triangles of one mesh in local space, bucketed on an XZ grid."""

    def __init__(self, verts: Iterable[Vec3], faces: Iterable[Sequence[int]], cell: float = 2.0) -> None:
        pts = [tuple(float(c) for c in v) for v in verts]
        self.tris: list[tuple] = []
        for idx in faces:  # polygons fan out into triangles
            for k in range(1, len(idx) - 1):
                self.tris.append((pts[idx[0]], pts[idx[k]], pts[idx[k + 1]]))
        self.cell = float(cell)
        self._grid: dict[tuple[int, int], list[int]] = {}
        for i, tri in enumerate(self.tris):
            xs = [p[0] for p in tri]
            zs = [p[2] for p in tri]
            for key in self._keys(min(xs), min(zs), max(xs), max(zs)):
                self._grid.setdefault(key, []).append(i)
        self.lo = tuple(min(p[j] for tri in self.tris for p in tri) for j in range(3))
        self.hi = tuple(max(p[j] for tri in self.tris for p in tri) for j in range(3))

    def _keys(self, x0, z0, x1, z1):
        c = self.cell
        for gx in range(math.floor(x0 / c), math.floor(x1 / c) + 1):
            for gz in range(math.floor(z0 / c), math.floor(z1 / c) + 1):
                yield gx, gz

    def candidates(self, x0, z0, x1, z1) -> set[int]:
        out: set[int] = set()
        for key in self._keys(min(x0, x1), min(z0, z1), max(x0, x1), max(z0, z1)):
            ids = self._grid.get(key)
            if ids:
                out.update(ids)
        return out

    def at(self, x: float, y: float, z: float, rot_deg: float = 0.0) -> "Placement":
        return Placement(self, x, y, z, rot_deg)


class Placement:
    """A ``MeshCollider`` at a world pose: rot_y(rot_deg), then translated."""

    def __init__(self, shape: MeshCollider, x: float, y: float, z: float, rot_deg: float = 0.0) -> None:
        self.shape = shape
        self.pos = (float(x), float(y), float(z))
        c = math.cos(math.radians(rot_deg))
        s = math.sin(math.radians(rot_deg))
        self._c, self._s = c, s

    def _to_local(self, p):
        dx, dy, dz = p[0] - self.pos[0], p[1] - self.pos[1], p[2] - self.pos[2]
        # inverse of rot_y: local = Ry(-rot) * (world - pos)
        return (self._c * dx - self._s * dz, dy, self._s * dx + self._c * dz)

    def _dir_to_local(self, d):
        return (self._c * d[0] - self._s * d[2], d[1], self._s * d[0] + self._c * d[2])

    def world_box(self) -> tuple[float, ...]:
        """World AABB (x0, y0, z0, x1, y1, z1) of the placed mesh."""
        lo, hi = self.shape.lo, self.shape.hi
        xs, zs = [], []
        for x in (lo[0], hi[0]):
            for z in (lo[2], hi[2]):
                xs.append(self._c * x + self._s * z + self.pos[0])
                zs.append(-self._s * x + self._c * z + self.pos[2])
        return (min(xs), lo[1] + self.pos[1], min(zs), max(xs), hi[1] + self.pos[1], max(zs))

    def ray(self, o: Vec3, d: Vec3, tmax: float = 1e9) -> float | None:
        """Distance along unit direction ``d`` to the first triangle within ``tmax``."""
        lo = self._to_local(o)
        ld = self._dir_to_local(d)
        end = (lo[0] + ld[0] * tmax, lo[2] + ld[2] * tmax)
        best = None
        for i in self.shape.candidates(lo[0], lo[2], end[0], end[1]):
            t = _ray_tri(lo, ld, self.shape.tris[i], tmax if best is None else best)
            if t is not None and (best is None or t < best):
                best = t
        return best

    def body_hits(self, x: float, z: float, r: float, y0: float, y1: float) -> bool:
        """A vertical body (XZ circle of radius ``r``, heights ``y0``..``y1``) touches the mesh."""
        lx = self._to_local((x, y0, z))
        cx, cz = lx[0], lx[2]
        for i in self.shape.candidates(cx - r, cz - r, cx + r, cz + r):
            tri = self.shape.tris[i]
            # the triangle's part inside the height band, in local space
            band = _clip(_clip(list(tri), 1, 1.0, y0 - self.pos[1]), 1, -1.0, y1 - self.pos[1])
            if len(band) >= 3 and _xz_dist2(cx, cz, band) <= r * r:
                return True
        return False
