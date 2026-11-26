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
_BVH_LEAF = 12
_BVH_MAX_DEPTH = 24


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


def _tri_xz_dist2(px: float, pz: float, a, b, c) -> float:
    """Unrolled squared XZ distance from (px, pz) to triangle (a, b, c)."""
    ax, az = a[0], a[2]
    bx, bz = b[0], b[2]
    cx, cz = c[0], c[2]
    pos = neg = False
    best = math.inf
    for x0, z0, x1, z1 in ((ax, az, bx, bz), (bx, bz, cx, cz), (cx, cz, ax, az)):
        ex, ez = x1 - x0, z1 - z0
        cr = ex * (pz - z0) - ez * (px - x0)
        if cr > 0.0:
            pos = True
        elif cr < 0.0:
            neg = True
        ll = ex * ex + ez * ez
        t = 0.0 if ll < _EPS else min(1.0, max(0.0, ((px - x0) * ex + (pz - z0) * ez) / ll))
        dx, dz = x0 + ex * t - px, z0 + ez * t - pz
        d2 = dx * dx + dz * dz
        if d2 < best:
            best = d2
    if pos != neg:
        return 0.0
    return best


def _tri_xz_closest2(px: float, pz: float, a, b, c) -> tuple[float, float, float, bool]:
    """Unrolled (dist2, cx, cz, inside) from (px, pz) to triangle (a, b, c)."""
    ax, az = a[0], a[2]
    bx, bz = b[0], b[2]
    cx, cz = c[0], c[2]
    pos = neg = False
    best = math.inf
    bcx, bcz = px, pz
    for x0, z0, x1, z1 in ((ax, az, bx, bz), (bx, bz, cx, cz), (cx, cz, ax, az)):
        ex, ez = x1 - x0, z1 - z0
        cr = ex * (pz - z0) - ez * (px - x0)
        if cr > 0.0:
            pos = True
        elif cr < 0.0:
            neg = True
        ll = ex * ex + ez * ez
        t = 0.0 if ll < _EPS else min(1.0, max(0.0, ((px - x0) * ex + (pz - z0) * ez) / ll))
        qx, qz = x0 + ex * t, z0 + ez * t
        d2 = (qx - px) * (qx - px) + (qz - pz) * (qz - pz)
        if d2 < best:
            best, bcx, bcz = d2, qx, qz
    if pos != neg:
        return 0.0, bcx, bcz, True
    return best, bcx, bcz, False


def _build_bvh(tris: list[tuple]) -> tuple:
    """Build a flat 3D BVH over ``tris``.

    Internal node: ``(x0, y0, z0, x1, y1, z1, left_idx, right_idx)``
    Leaf node:     ``(x0, y0, z0, x1, y1, z1, -1, leaf_records_tuple)``
    Record: ``(a, b, c, e1, e2, xmin, ymin, zmin, xmax, ymax, zmax)``
    """
    n = len(tris)
    if n == 0:
        return ()
    recs = []
    cxs = [0.0] * n
    cys = [0.0] * n
    czs = [0.0] * n
    for i, (a, b, c) in enumerate(tris):
        ax, ay, az = a
        bx, by, bz = b
        cx, cy, cz = c
        xmin = ax if ax < bx else bx
        if cx < xmin:
            xmin = cx
        xmax = ax if ax > bx else bx
        if cx > xmax:
            xmax = cx
        ymin = ay if ay < by else by
        if cy < ymin:
            ymin = cy
        ymax = ay if ay > by else by
        if cy > ymax:
            ymax = cy
        zmin = az if az < bz else bz
        if cz < zmin:
            zmin = cz
        zmax = az if az > bz else bz
        if cz > zmax:
            zmax = cz
        recs.append((a, b, c, (bx - ax, by - ay, bz - az), (cx - ax, cy - ay, cz - az),
                     xmin, ymin, zmin, xmax, ymax, zmax))
        cxs[i] = (xmin + xmax) * 0.5
        cys[i] = (ymin + ymax) * 0.5
        czs[i] = (zmin + zmax) * 0.5

    nodes: list = []

    def build(ids: list[int], depth: int) -> int:
        r0 = recs[ids[0]]
        x0, y0, z0, x1, y1, z1 = r0[5], r0[6], r0[7], r0[8], r0[9], r0[10]
        cx0 = cx1 = cxs[ids[0]]
        cy0 = cy1 = cys[ids[0]]
        cz0 = cz1 = czs[ids[0]]
        for i in ids[1:]:
            rc = recs[i]
            if rc[5] < x0: x0 = rc[5]
            if rc[6] < y0: y0 = rc[6]
            if rc[7] < z0: z0 = rc[7]
            if rc[8] > x1: x1 = rc[8]
            if rc[9] > y1: y1 = rc[9]
            if rc[10] > z1: z1 = rc[10]
            vx, vy, vz = cxs[i], cys[i], czs[i]
            if vx < cx0: cx0 = vx
            elif vx > cx1: cx1 = vx
            if vy < cy0: cy0 = vy
            elif vy > cy1: cy1 = vy
            if vz < cz0: cz0 = vz
            elif vz > cz1: cz1 = vz
        idx = len(nodes)
        if len(ids) <= _BVH_LEAF:
            nodes.append((x0, y0, z0, x1, y1, z1, -1, tuple(recs[i] for i in ids)))
            return idx
        sx, sy, sz = cx1 - cx0, cy1 - cy0, cz1 - cz0
        if sx >= sy and sx >= sz:
            axis_c, span, mid_v = cxs, sx, (cx0 + cx1) * 0.5
        elif sy >= sz:
            axis_c, span, mid_v = cys, sy, (cy0 + cy1) * 0.5
        else:
            axis_c, span, mid_v = czs, sz, (cz0 + cz1) * 0.5
        if depth >= _BVH_MAX_DEPTH or span < 1e-6:
            if span >= 1e-6:
                ids.sort(key=axis_c.__getitem__)
            mid = len(ids) >> 1
            left_ids, right_ids = ids[:mid], ids[mid:]
        else:
            left_ids = [i for i in ids if axis_c[i] < mid_v]
            right_ids = [i for i in ids if axis_c[i] >= mid_v]
            if not left_ids or not right_ids:
                mid = len(ids) >> 1
                left_ids, right_ids = ids[:mid], ids[mid:]
        nodes.append(None)
        li = build(left_ids, depth + 1)
        ri = build(right_ids, depth + 1)
        nodes[idx] = (x0, y0, z0, x1, y1, z1, li, ri)
        return idx

    build(list(range(n)), 0)
    return tuple(nodes)


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
        self._bvh = _build_bvh(self.tris)
        if self._bvh:
            r0 = self._bvh[0]
            self.lo = (r0[0], r0[1], r0[2])
            self.hi = (r0[3], r0[4], r0[5])
        else:
            self.lo = (0.0, 0.0, 0.0)
            self.hi = (0.0, 0.0, 0.0)

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
        self._wbox: tuple[float, ...] | None = None

    def _to_local(self, p):
        dx, dy, dz = p[0] - self.pos[0], p[1] - self.pos[1], p[2] - self.pos[2]
        # inverse of rot_y: local = Ry(-rot) * (world - pos)
        return (self._c * dx - self._s * dz, dy, self._s * dx + self._c * dz)

    def _dir_to_local(self, d):
        return (self._c * d[0] - self._s * d[2], d[1], self._s * d[0] + self._c * d[2])

    def world_box(self) -> tuple[float, ...]:
        """World AABB (x0, y0, z0, x1, y1, z1) of the placed mesh."""
        if self._wbox is not None:
            return self._wbox
        lo, hi = self.shape.lo, self.shape.hi
        xs, zs = [], []
        for x in (lo[0], hi[0]):
            for z in (lo[2], hi[2]):
                xs.append(self._c * x + self._s * z + self.pos[0])
                zs.append(-self._s * x + self._c * z + self.pos[2])
        self._wbox = (min(xs), lo[1] + self.pos[1], min(zs), max(xs), hi[1] + self.pos[1], max(zs))
        return self._wbox

    def ray(self, o: Vec3, d: Vec3, tmax: float = 1e9) -> float | None:
        """Distance along unit direction ``d`` to the first triangle within ``tmax``."""
        bvh = self.shape._bvh
        if not bvh:
            return None
        ox, oy, oz = self._to_local(o)
        dx, dy, dz = self._dir_to_local(d)
        idx = (1.0 / dx) if (dx > _EPS or dx < -_EPS) else None
        idy = (1.0 / dy) if (dy > _EPS or dy < -_EPS) else None
        idz = (1.0 / dz) if (dz > _EPS or dz < -_EPS) else None

        def hit_box(x0, y0, z0, x1, y1, z1, limit):
            if idx is None:
                if ox < x0 - 1e-7 or ox > x1 + 1e-7:
                    return None
                t0, t1 = 0.0, limit
            else:
                ta = (x0 - ox) * idx
                tb = (x1 - ox) * idx
                if ta > tb:
                    ta, tb = tb, ta
                t0 = ta if ta > 0.0 else 0.0
                t1 = tb if tb < limit else limit
                if t0 > t1 + 1e-7:
                    return None
            if idy is None:
                if oy < y0 - 1e-7 or oy > y1 + 1e-7:
                    return None
            else:
                ta = (y0 - oy) * idy
                tb = (y1 - oy) * idy
                if ta > tb:
                    ta, tb = tb, ta
                if ta > t0:
                    t0 = ta
                if tb < t1:
                    t1 = tb
                if t0 > t1 + 1e-7:
                    return None
            if idz is None:
                if oz < z0 - 1e-7 or oz > z1 + 1e-7:
                    return None
            else:
                ta = (z0 - oz) * idz
                tb = (z1 - oz) * idz
                if ta > tb:
                    ta, tb = tb, ta
                if ta > t0:
                    t0 = ta
                if tb < t1:
                    t1 = tb
                if t0 > t1 + 1e-7:
                    return None
            return t0

        root = bvh[0]
        t_root = hit_box(root[0], root[1], root[2], root[3], root[4], root[5], tmax)
        if t_root is None:
            return None
        best = None
        cur_max = tmax
        stack = [(t_root, 0)]
        while stack:
            t_ent, ni = stack.pop()
            if t_ent > cur_max + 1e-7:
                continue
            node = bvh[ni]
            li = node[6]
            if li < 0:
                for a, _b, _c, e1, e2, _x0, _y0, _z0, _x1, _y1, _z1 in node[7]:
                    e1x, e1y, e1z = e1
                    e2x, e2y, e2z = e2
                    px = dy * e2z - dz * e2y
                    py = dz * e2x - dx * e2z
                    pz = dx * e2y - dy * e2x
                    det = e1x * px + e1y * py + e1z * pz
                    if -_EPS < det < _EPS:
                        continue
                    inv = 1.0 / det
                    sx = ox - a[0]
                    sy = oy - a[1]
                    sz = oz - a[2]
                    u = (sx * px + sy * py + sz * pz) * inv
                    if u < 0.0 or u > 1.0:
                        continue
                    qx = sy * e1z - sz * e1y
                    qy = sz * e1x - sx * e1z
                    qz = sx * e1y - sy * e1x
                    v = (dx * qx + dy * qy + dz * qz) * inv
                    if v < 0.0 or u + v > 1.0:
                        continue
                    t = (e2x * qx + e2y * qy + e2z * qz) * inv
                    if 0.0 <= t <= cur_max and (best is None or t < best):
                        best = t
                        cur_max = t
            else:
                ri = node[7]
                ln = bvh[li]
                rn = bvh[ri]
                tl = hit_box(ln[0], ln[1], ln[2], ln[3], ln[4], ln[5], cur_max)
                tr = hit_box(rn[0], rn[1], rn[2], rn[3], rn[4], rn[5], cur_max)
                if tl is not None and tr is not None:
                    if tl <= tr:
                        stack.append((tr, ri))
                        stack.append((tl, li))
                    else:
                        stack.append((tl, li))
                        stack.append((tr, ri))
                elif tl is not None:
                    stack.append((tl, li))
                elif tr is not None:
                    stack.append((tr, ri))
        return best

    def body_hits(self, x: float, z: float, r: float, y0: float, y1: float) -> bool:
        """A vertical body (XZ circle of radius ``r``, heights ``y0``..``y1``) touches the mesh."""
        bvh = self.shape._bvh
        if not bvh:
            return False
        lx = self._to_local((x, y0, z))
        cx, cz = lx[0], lx[2]
        ly0 = y0 - self.pos[1]
        ly1 = y1 - self.pos[1]
        qx0, qx1 = cx - r, cx + r
        qz0, qz1 = cz - r, cz + r
        r2 = r * r
        stack = [0]
        while stack:
            node = bvh[stack.pop()]
            if (qx1 < node[0] or qx0 > node[3] or qz1 < node[2] or qz0 > node[5]
                    or ly1 < node[1] or ly0 > node[4]):
                continue
            li = node[6]
            if li < 0:
                for a, b, c, _e1, _e2, tx0, ty0, tz0, tx1, ty1, tz1 in node[7]:
                    if qx1 < tx0 or qx0 > tx1 or qz1 < tz0 or qz0 > tz1 or ly1 < ty0 or ly0 > ty1:
                        continue
                    if ty0 >= ly0 and ty1 <= ly1:
                        if _tri_xz_dist2(cx, cz, a, b, c) <= r2:
                            return True
                    else:
                        band = (a, b, c)
                        if ty0 < ly0:
                            band = _clip(band, 1, 1.0, ly0)
                        if band and ty1 > ly1:
                            band = _clip(band, 1, -1.0, ly1)
                        if len(band) >= 3 and _xz_dist2(cx, cz, band) <= r2:
                            return True
            else:
                stack.append(li)
                stack.append(node[7])
        return False

    def capsule_contacts(self, x: float, z: float, r: float, y0: float, y1: float) -> list[tuple[float, float, float]]:
        """Return world-space ``[(nx, nz, depth), ...]`` against mesh triangles."""
        bvh = self.shape._bvh
        if not bvh:
            return []
        lx = self._to_local((x, y0, z))
        cx, cz = lx[0], lx[2]
        ly0 = y0 - self.pos[1]
        ly1 = y1 - self.pos[1]
        qx0, qx1 = cx - r, cx + r
        qz0, qz1 = cz - r, cz + r
        r2 = r * r
        out: list[tuple[float, float, float]] = []
        stack = [0]
        while stack:
            node = bvh[stack.pop()]
            if (qx1 < node[0] or qx0 > node[3] or qz1 < node[2] or qz0 > node[5]
                    or ly1 < node[1] or ly0 > node[4]):
                continue
            li = node[6]
            if li < 0:
                for a, b, c, _e1, _e2, tx0, ty0, tz0, tx1, ty1, tz1 in node[7]:
                    if qx1 < tx0 or qx0 > tx1 or qz1 < tz0 or qz0 > tz1 or ly1 < ty0 or ly0 > ty1:
                        continue
                    if ty0 >= ly0 and ty1 <= ly1:
                        d2, px_c, pz_c, inside = _tri_xz_closest2(cx, cz, a, b, c)
                    else:
                        band = (a, b, c)
                        if ty0 < ly0:
                            band = _clip(band, 1, 1.0, ly0)
                        if band and ty1 > ly1:
                            band = _clip(band, 1, -1.0, ly1)
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
            else:
                stack.append(li)
                stack.append(node[7])
        return out