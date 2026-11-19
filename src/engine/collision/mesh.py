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


def _ray_aabb_span(ox, oy, oz, dx, dy, dz, lo, hi, tmax):
    """Clip ray (o, d, [0, tmax]) against local AABB [lo, hi] -> (t0, t1) | None."""
    t0, t1 = 0.0, tmax
    for oi, di, mn, mx in ((ox, dx, lo[0], hi[0]),
                           (oy, dy, lo[1], hi[1]),
                           (oz, dz, lo[2], hi[2])):
        if -_EPS < di < _EPS:
            if oi < mn or oi > mx:
                return None
        else:
            inv = 1.0 / di
            ta = (mn - oi) * inv
            tb = (mx - oi) * inv
            if ta > tb:
                ta, tb = tb, ta
            if ta > t0:
                t0 = ta
            if tb < t1:
                t1 = tb
            if t0 > t1:
                return None
    return t0, t1


def _ray_tri_fast(ox, oy, oz, dx, dy, dz, item, tmax, rymin, rymax):
    """Moller-Trumbore against precomputed (a, e1, e2, y_min, y_max)."""
    a, e1, e2, tymin, tymax = item
    if tymax < rymin or tymin > rymax:
        return None
    e1x, e1y, e1z = e1
    e2x, e2y, e2z = e2
    px = dy * e2z - dz * e2y
    py = dz * e2x - dx * e2z
    pz = dx * e2y - dy * e2x
    det = e1x * px + e1y * py + e1z * pz
    if -_EPS < det < _EPS:
        return None
    inv = 1.0 / det
    sx = ox - a[0]
    sy = oy - a[1]
    sz = oz - a[2]
    u = (sx * px + sy * py + sz * pz) * inv
    if u < 0.0 or u > 1.0:
        return None
    qx = sy * e1z - sz * e1y
    qy = sz * e1x - sx * e1z
    qz = sx * e1y - sy * e1x
    v = (dx * qx + dy * qy + dz * qz) * inv
    if v < 0.0 or u + v > 1.0:
        return None
    t = (e2x * qx + e2y * qy + e2z * qz) * inv
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


def _xz_closest2(px: float, pz: float, poly) -> tuple[float, float, float, bool]:
    """Return ``(dist2, cx, cz, inside)`` from ``(px, pz)`` to convex ``poly``."""
    n = len(poly)
    best = math.inf
    bcx, bcz = px, pz
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
        cx, cz = ax + ex * t, az + ez * t
        d2 = (cx - px) * (cx - px) + (cz - pz) * (cz - pz)
        if d2 < best:
            best, bcx, bcz = d2, cx, cz
    if pos != neg:
        return 0.0, bcx, bcz, True
    return best, bcx, bcz, False


class MeshCollider:
    """Triangles of one mesh in local space, bucketed on an XZ grid."""

    def __init__(self, verts: Iterable[Vec3], faces: Iterable[Sequence[int]], cell: float = 2.0) -> None:
        pts = [tuple(float(c) for c in v) for v in verts]
        self.tris: list[tuple] = []
        for idx in faces:  # polygons fan out into triangles
            for k in range(1, len(idx) - 1):
                self.tris.append((pts[idx[0]], pts[idx[k]], pts[idx[k + 1]]))
        self._tri_data = [
            (a, _sub(b, a), _sub(c, a), min(a[1], b[1], c[1]), max(a[1], b[1], c[1]))
            for a, b, c in self.tris
        ]
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

    def _span_candidates(self, x0, z0, x1, z1):
        c = self.cell
        gx0 = math.floor((x0 if x0 < x1 else x1) / c)
        gx1 = math.floor((x1 if x0 < x1 else x0) / c)
        gz0 = math.floor((z0 if z0 < z1 else z1) / c)
        gz1 = math.floor((z1 if z0 < z1 else z0) / c)
        if gx0 == gx1 and gz0 == gz1:
            return self._grid.get((gx0, gz0), ())
        out: set[int] = set()
        grid = self._grid
        for gx in range(gx0, gx1 + 1):
            for gz in range(gz0, gz1 + 1):
                ids = grid.get((gx, gz))
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
        ox, oy, oz = self._to_local(o)
        dx, dy, dz = self._dir_to_local(d)
        shape = self.shape
        span = _ray_aabb_span(ox, oy, oz, dx, dy, dz, shape.lo, shape.hi, tmax)
        if span is None:
            return None
        t0, t1 = span
        y0 = oy + dy * t0
        y1 = oy + dy * t1
        rymin, rymax = (y0 - 1e-6, y1 + 1e-6) if y0 <= y1 else (y1 - 1e-6, y0 + 1e-6)
        x0, x1 = ox + dx * t0, ox + dx * t1
        z0, z1 = oz + dz * t0, oz + dz * t1
        tri_data = shape._tri_data
        best = None
        cur_max = min(tmax, t1 + 1e-6)
        for i in shape._span_candidates(
            min(x0, x1) - 1e-6, min(z0, z1) - 1e-6, max(x0, x1) + 1e-6, max(z0, z1) + 1e-6
        ):
            t = _ray_tri_fast(ox, oy, oz, dx, dy, dz, tri_data[i], cur_max, rymin, rymax)
            if t is not None and (best is None or t < best):
                best = t
                if t < cur_max:
                    cur_max = t
        return best

    def body_hits(self, x: float, z: float, r: float, y0: float, y1: float) -> bool:
        """A vertical body (XZ circle of radius ``r``, heights ``y0``..``y1``) touches the mesh."""
        lx = self._to_local((x, y0, z))
        cx, cz = lx[0], lx[2]
        shape = self.shape
        s_lo, s_hi = shape.lo, shape.hi
        ly0 = y0 - self.pos[1]
        ly1 = y1 - self.pos[1]
        if (cx + r < s_lo[0] or cx - r > s_hi[0] or cz + r < s_lo[2] or cz - r > s_hi[2]
                or ly1 < s_lo[1] or ly0 > s_hi[1]):
            return False
        tris = shape.tris
        tri_data = shape._tri_data
        for i in shape._span_candidates(cx - r, cz - r, cx + r, cz + r):
            item = tri_data[i]
            if item[4] < ly0 or item[3] > ly1:
                continue
            tri = tris[i]
            # the triangle's part inside the height band, in local space
            band = _clip(_clip(list(tri), 1, 1.0, ly0), 1, -1.0, ly1)
            if len(band) >= 3 and _xz_dist2(cx, cz, band) <= r * r:
                return True
        return False

    def capsule_contacts(self, x: float, z: float, r: float, y0: float, y1: float) -> list[tuple[float, float, float]]:
        """Return world-space ``[(nx, nz, depth), ...]`` against mesh triangles."""
        lx = self._to_local((x, y0, z))
        cx, cz = lx[0], lx[2]
        shape = self.shape
        s_lo, s_hi = shape.lo, shape.hi
        ly0 = y0 - self.pos[1]
        ly1 = y1 - self.pos[1]
        if (cx + r < s_lo[0] or cx - r > s_hi[0] or cz + r < s_lo[2] or cz - r > s_hi[2]
                or ly1 < s_lo[1] or ly0 > s_hi[1]):
            return []
        tris = shape.tris
        tri_data = shape._tri_data
        r2 = r * r
        out: list[tuple[float, float, float]] = []
        for i in shape._span_candidates(cx - r, cz - r, cx + r, cz + r):
            item = tri_data[i]
            if item[4] < ly0 or item[3] > ly1:
                continue
            band = _clip(_clip(list(tris[i]), 1, 1.0, ly0), 1, -1.0, ly1)
            if len(band) < 3:
                continue
            d2, px_c, pz_c, inside = _xz_closest2(cx, cz, band)
            if d2 >= r2:
                continue
            dx = (px_c - cx) if inside else (cx - px_c)
            dz = (pz_c - cz) if inside else (cz - pz_c)
            d = math.hypot(dx, dz)
            if d < 1e-9:
                continue
            nx_l, nz_l = dx / d, dz / d
            pen = (r + d) if inside else (r - d)
            out.append((self._c * nx_l + self._s * nz_l, -self._s * nx_l + self._c * nz_l, pen))
        return out