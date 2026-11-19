"""engine.collision.nav - 2D and multi-floor 3D A* navigation (RPE6 §6.9).

``GridNav`` samples ``walkable(x, z)`` at every cell centre once, at build time;
pass a test that already includes the body radius. ``height(x, z)`` (optional)
gives the floor under a cell: neighbours more than ``step`` apart in height are
not connected (a ledge, a platform edge too tall to climb).

``MultiFloorNav`` extends this to overlapping multi-storey geometry (galleries
over halls, stairs, gantry catwalks, bridges), explicit off-mesh ``NavLink``
edges (ladders, low-cover vaults, drops), and runtime dynamic obstacles
(parked or moving vehicles) without rebuilding the static grid.
"""
from __future__ import annotations

from dataclasses import dataclass
import heapq
import math
from typing import Callable, Sequence

__all__ = ["GridNav", "MultiFloorNav", "NavLink"]

_SQRT2 = math.sqrt(2.0)
_NBRS = ((1, 0, 1.0), (-1, 0, 1.0), (0, 1, 1.0), (0, -1, 1.0),
         (1, 1, _SQRT2), (1, -1, _SQRT2), (-1, 1, _SQRT2), (-1, -1, _SQRT2))


@dataclass(frozen=True)
class NavLink:
    """An explicit off-mesh transition (stair/ladder/vault/drop) between 3D nodes."""
    target: int
    cost: float
    kind: str = "link"


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


def _dedup_heights(hs: Sequence[float], merge: float = 0.05) -> tuple[float, ...]:
    if not hs:
        return ()
    vals = sorted(float(y) for y in hs)
    out = [vals[0]]
    for y in vals[1:]:
        if y - out[-1] > merge:
            out.append(y)
    return tuple(out)


def _as_vec3(p: Sequence[float]) -> tuple[float, float, float]:
    if len(p) == 2:
        return float(p[0]), 0.0, float(p[1])
    return float(p[0]), float(p[1]), float(p[2])


class MultiFloorNav:
    """Multi-layer 3D grid + off-mesh link A* with dynamic obstacle avoidance.

    ``layers_at(x, z)`` returns sorted walkable surface heights at ``(x, z)``
    (empty when blocked). If ``layers_at`` is omitted, falls back to single-layer
    ``walkable(x, z)`` + ``height(x, z)`` like ``GridNav``.
    """

    def __init__(self, bounds: Sequence[float], cell: float,
                 layers_at: Callable[[float, float], Sequence[float]] | None = None,
                 *, walkable: Callable[[float, float], bool] | None = None,
                 height: Callable[[float, float], float] | None = None,
                 step: float = 0.65, body_h: float = 1.8, max_nodes: int = 40000,
                 cache_size: int = 128) -> None:
        self.x0, self.x1, self.z0, self.z1 = (float(v) for v in bounds)
        self.cell = float(cell)
        self.cols = max(1, math.ceil((self.x1 - self.x0) / self.cell))
        self.rows = max(1, math.ceil((self.z1 - self.z0) / self.cell))
        self.step = float(step)
        self.body_h = float(body_h)
        self.max_nodes = int(max_nodes)
        self._cache_size = int(cache_size)
        self._cache: dict[tuple[int, int, int], list[int]] = {}
        self._pulled_cache: dict[tuple[int, int, int], list[tuple[tuple[float, float, float], bool]]] = {}
        self._nbr_cache: dict[int, tuple[tuple[int, float, bool, int, int], ...]] = {}
        self._blocked = bytearray()
        self._blocked_ver = -1

        self._cell_nodes: list[tuple[int, ...]] = [() for _ in range(self.cols * self.rows)]
        self._nodes: list[tuple[int, int, float]] = []     # (col, row, y)
        self._links: dict[int, list[NavLink]] = {}
        self._dyn_boxes: tuple[tuple[float, float, float, float, float, float], ...] = ()
        self._dyn_circles: tuple[tuple[float, float, float, float, float], ...] = ()
        self._dyn_ver = 0

        for r in range(self.rows):
            for c in range(self.cols):
                x, z = self.center(c, r)
                if layers_at is not None:
                    ys = _dedup_heights(layers_at(x, z))
                elif walkable is not None and walkable(x, z):
                    ys = (float(height(x, z)) if height is not None else 0.0,)
                else:
                    ys = ()
                if ys:
                    ids = []
                    for y in ys:
                        nid = len(self._nodes)
                        self._nodes.append((c, r, y))
                        ids.append(nid)
                    self._cell_nodes[r * self.cols + c] = tuple(ids)
        self._blocked = bytearray(len(self._nodes))

    def center(self, c: int, r: int) -> tuple[float, float]:
        return self.x0 + (c + 0.5) * self.cell, self.z0 + (r + 0.5) * self.cell

    def node_pos(self, nid: int) -> tuple[float, float, float]:
        c, r, y = self._nodes[nid]
        x, z = self.center(c, r)
        return x, y, z

    def cell_at(self, x: float, z: float) -> tuple[int, int] | None:
        c = math.floor((x - self.x0) / self.cell)
        r = math.floor((z - self.z0) / self.cell)
        if 0 <= c < self.cols and 0 <= r < self.rows:
            return c, r
        return None

    def set_dynamic_boxes(self, boxes: Sequence[Sequence[float]]) -> None:
        """Register runtime boxes ``(x0, y0, z0, x1, y1, z1)`` (e.g. doors, trucks)."""
        norm = tuple(tuple(float(v) for v in b) for b in boxes)
        if norm != self._dyn_boxes:
            self._dyn_boxes = norm
            self._dyn_ver += 1
            self._cache.clear()
            self._pulled_cache.clear()

    def set_dynamic_circles(self, circles: Sequence[Sequence[float]]) -> None:
        """Register runtime circles ``(x, y0, z, r, y1)``."""
        norm = tuple(tuple(float(v) for v in c) for c in circles)
        if norm != self._dyn_circles:
            self._dyn_circles = norm
            self._dyn_ver += 1
            self._cache.clear()
            self._pulled_cache.clear()

    def _point_blocked(self, x: float, y: float, z: float) -> bool:
        y1 = y + self.body_h
        for bx0, by0, bz0, bx1, by1, bz1 in self._dyn_boxes:
            if by1 > y + 0.25 and by0 < y1 and bx0 <= x <= bx1 and bz0 <= z <= bz1:
                return True
        for cx, cy0, cz, r, cy1 in self._dyn_circles:
            if cy1 > y + 0.25 and cy0 < y1 and (x - cx) ** 2 + (z - cz) ** 2 <= r * r:
                return True
        return False

    def _sync_blocked(self) -> None:
        blk = self._blocked
        blk[:] = b"\x00" * len(blk)
        if not self._dyn_boxes and not self._dyn_circles:
            self._blocked_ver = self._dyn_ver
            return
        cols, rows = self.cols, self.rows
        x0, z0, cell = self.x0, self.z0, self.cell
        inv_c = 1.0 / cell
        body_h = self.body_h
        nodes = self._nodes
        cell_nodes = self._cell_nodes
        for bx0, by0, bz0, bx1, by1, bz1 in self._dyn_boxes:
            c0 = max(0, math.floor((bx0 - x0) * inv_c) - 1)
            c1 = min(cols - 1, math.floor((bx1 - x0) * inv_c) + 1)
            r0 = max(0, math.floor((bz0 - z0) * inv_c) - 1)
            r1 = min(rows - 1, math.floor((bz1 - z0) * inv_c) + 1)
            for r in range(r0, r1 + 1):
                cz = z0 + (r + 0.5) * cell
                if not (bz0 <= cz <= bz1):
                    continue
                row_off = r * cols
                for c in range(c0, c1 + 1):
                    nids = cell_nodes[row_off + c]
                    if not nids:
                        continue
                    cx = x0 + (c + 0.5) * cell
                    if not (bx0 <= cx <= bx1):
                        continue
                    for nid in nids:
                        ny = nodes[nid][2]
                        if by1 > ny + 0.25 and by0 < ny + body_h:
                            blk[nid] = 1
        for cx_c, cy0, cz_c, rad, cy1 in self._dyn_circles:
            r2 = rad * rad
            c0 = max(0, math.floor((cx_c - rad - x0) * inv_c) - 1)
            c1 = min(cols - 1, math.floor((cx_c + rad - x0) * inv_c) + 1)
            r0 = max(0, math.floor((cz_c - rad - z0) * inv_c) - 1)
            r1 = min(rows - 1, math.floor((cz_c + rad - z0) * inv_c) + 1)
            for r in range(r0, r1 + 1):
                cz = z0 + (r + 0.5) * cell
                dz2 = (cz - cz_c) ** 2
                if dz2 > r2:
                    continue
                row_off = r * cols
                for c in range(c0, c1 + 1):
                    nids = cell_nodes[row_off + c]
                    if not nids:
                        continue
                    cx = x0 + (c + 0.5) * cell
                    if (cx - cx_c) ** 2 + dz2 > r2:
                        continue
                    for nid in nids:
                        ny = nodes[nid][2]
                        if cy1 > ny + 0.25 and cy0 < ny + body_h:
                            blk[nid] = 1
        self._blocked_ver = self._dyn_ver

    def _node_blocked(self, nid: int) -> bool:
        if not self._dyn_boxes and not self._dyn_circles:
            return False
        if self._blocked_ver != self._dyn_ver:
            self._sync_blocked()
        return bool(self._blocked[nid])

    def nearest(self, x: float, y: float, z: float, reach: int = 6) -> int | None:
        """Closest walkable node id weighted strongly by elevation match."""
        c0 = min(self.cols - 1, max(0, math.floor((x - self.x0) / self.cell)))
        r0 = min(self.rows - 1, max(0, math.floor((z - self.z0) / self.cell)))
        best: int | None = None
        best_d = math.inf
        for ring in range(reach + 1):
            for c in range(max(0, c0 - ring), min(self.cols, c0 + ring + 1)):
                rs = (range(max(0, r0 - ring), min(self.rows, r0 + ring + 1))
                      if abs(c - c0) == ring or ring == 0
                      else (r0 - ring, r0 + ring))
                for r in rs:
                    if not (0 <= r < self.rows):
                        continue
                    nids = self._cell_nodes[r * self.cols + c]
                    if not nids:
                        continue
                    cx, cz = self.center(c, r)
                    dxz = (cx - x) ** 2 + (cz - z) ** 2
                    for nid in nids:
                        if self._node_blocked(nid):
                            continue
                        ny = self._nodes[nid][2]
                        d = dxz + (2.5 * (ny - y)) ** 2
                        if d < best_d:
                            best, best_d = nid, d
            if best is not None and best_d <= (ring * self.cell) ** 2 + 0.35:
                return best
        return best

    def add_link(self, a: Sequence[float], b: Sequence[float], *,
                 cost: float | None = None, bidirectional: bool = True,
                 kind: str = "link") -> bool:
        """Connect nearest nodes to ``a`` and ``b`` with an off-mesh link."""
        ax, ay, az = _as_vec3(a)
        bx, by, bz = _as_vec3(b)
        na = self.nearest(ax, ay, az)
        nb = self.nearest(bx, by, bz)
        if na is None or nb is None or na == nb:
            return False
        pa = self.node_pos(na)
        pb = self.node_pos(nb)
        w = float(cost) if cost is not None else max(0.5, math.dist(pa, pb) / max(0.25, self.cell))
        self._links.setdefault(na, []).append(NavLink(nb, w, kind))
        if bidirectional:
            self._links.setdefault(nb, []).append(NavLink(na, w, kind))
        self._nbr_cache.pop(na, None)
        if bidirectional:
            self._nbr_cache.pop(nb, None)
        self._cache.clear()
        self._pulled_cache.clear()
        return True

    def _layer_step_raw(self, c: int, r: int, y: float) -> int | None:
        if not (0 <= c < self.cols and 0 <= r < self.rows):
            return None
        nids = self._cell_nodes[r * self.cols + c]
        if not nids:
            return None
        best_nid = None
        best_dy = self.step + 1e-6
        for nid in nids:
            dy = abs(self._nodes[nid][2] - y)
            if dy <= best_dy:
                best_dy = dy
                best_nid = nid
        return best_nid

    def _layer_step(self, c: int, r: int, y: float) -> int | None:
        """Pick node in ``(c, r)`` reachable within ``step`` from ``y``."""
        best_nid = self._layer_step_raw(c, r, y)
        if best_nid is None or self._node_blocked(best_nid):
            return None
        return best_nid

    def _static_neighbors(self, nid: int) -> tuple[tuple[int, float, bool, int, int], ...]:
        cached = self._nbr_cache.get(nid)
        if cached is not None:
            return cached
        c, r, y = self._nodes[nid]
        cols, rows, step = self.cols, self.rows, self.step
        items = []
        for dc, dr, w in _NBRS:
            nc, nr = c + dc, r + dr
            if not (0 <= nc < cols and 0 <= nr < rows):
                continue
            nids = self._cell_nodes[nr * cols + nc]
            if not nids:
                continue
            na = nb = -1
            if dc and dr:
                na_id = self._layer_step_raw(c + dc, r, y)
                nb_id = self._layer_step_raw(c, r + dr, y)
                if na_id is None or nb_id is None:
                    continue
                na, nb = na_id, nb_id
            for j in nids:
                ny = self._nodes[j][2]
                if abs(ny - y) > step:
                    continue
                if dc and dr:
                    if (abs(self._nodes[na][2] - ny) > step
                            or abs(self._nodes[nb][2] - ny) > step):
                        continue
                items.append((j, w + abs(ny - y) * 0.25, False, na, nb))
        for lnk in self._links.get(nid, ()):
            items.append((lnk.target, lnk.cost, True, -1, -1))
        res = tuple(items)
        self._nbr_cache[nid] = res
        return res

    def _neighbors(self, nid: int):
        if not self._dyn_boxes and not self._dyn_circles:
            for j, w, is_link, _na, _nb in self._static_neighbors(nid):
                yield j, w, is_link
            return
        if self._blocked_ver != self._dyn_ver:
            self._sync_blocked()
        blk = self._blocked
        for j, w, is_link, na, nb in self._static_neighbors(nid):
            if blk[j] or (na >= 0 and (blk[na] or blk[nb])):
                continue
            yield j, w, is_link

    def walk_clear(self, a: Sequence[float], b: Sequence[float]) -> bool:
        """True when a straight walk from 3D ``a`` to ``b`` stays on connected layers."""
        ax, ay, az = _as_vec3(a)
        bx, by, bz = _as_vec3(b)
        dist_xz = math.hypot(bx - ax, bz - az)
        n = max(1, math.ceil(dist_xz / (self.cell * 0.35)))
        cur_y = ay
        for k in range(n + 1):
            f = k / n
            sx = ax + (bx - ax) * f
            sy_exp = ay + (by - ay) * f
            sz = az + (bz - az) * f
            cr = self.cell_at(sx, sz)
            if cr is None:
                return False
            nid = self._layer_step(cr[0], cr[1], cur_y)
            if nid is None:
                return False
            ny = self._nodes[nid][2]
            if abs(ny - sy_exp) > max(self.step * 1.4, 0.85):
                return False
            if self._point_blocked(sx, ny, sz):
                return False
            cur_y = ny
        return abs(by - cur_y) <= max(self.step * 1.4, 0.85)

    def path(self, a: Sequence[float], b: Sequence[float]) -> list[tuple[float, float, float]]:
        """3D waypoints ``[(x, y, z), ...]`` from ``a`` toward ``b``, start excluded."""
        ax, ay, az = _as_vec3(a)
        bx, by, bz = _as_vec3(b)
        s = self.nearest(ax, ay, az)
        g = self.nearest(bx, by, bz)
        if s is None or g is None:
            return []
        key = (s, g, self._dyn_ver)
        nodes = self._cache.get(key)
        if nodes is None:
            nodes = self._astar(s, g)
            if len(self._cache) >= self._cache_size:
                self._cache.pop(next(iter(self._cache)))
            self._cache[key] = nodes
        if not nodes:
            return []
        if len(nodes) == 1:
            gx, gy, gz = self.node_pos(g)
            return [(bx, gy, bz)] if self.walk_clear((ax, ay, az), (bx, gy, bz)) else [(gx, gy, gz)]

        pulled = self._pulled_cache.get(key)
        if pulled is None:
            # Partition at off-mesh links so string-pulling never skips ladders/vaults/drops
            raw_pts: list[tuple[tuple[float, float, float], bool]] = []
            for idx, nid in enumerate(nodes):
                forced = False
                if idx > 0:
                    prev_id = nodes[idx - 1]
                    for lnk in self._links.get(prev_id, ()):
                        if lnk.target == nid:
                            forced = True
                            break
                raw_pts.append((self.node_pos(nid), forced))
            pulled = []
            here_c = raw_pts[0][0]
            i = 1
            while i < len(raw_pts):
                if raw_pts[i][1]:
                    here_c = raw_pts[i][0]
                    pulled.append((here_c, True))
                    i += 1
                    continue
                j = i
                while j + 1 < len(raw_pts) and not raw_pts[j + 1][1]:
                    j += 1
                best = i
                for k in range(j, i - 1, -1):
                    if self.walk_clear(here_c, raw_pts[k][0]):
                        best = k
                        break
                here_c = raw_pts[best][0]
                pulled.append((here_c, False))
                i = best + 1
            if len(self._pulled_cache) >= self._cache_size:
                self._pulled_cache.pop(next(iter(self._pulled_cache)))
            self._pulled_cache[key] = pulled

        pts = list(pulled)
        prev_end = pts[-2][0] if len(pts) >= 2 else self.node_pos(s)
        if not pts[-1][1] and self.walk_clear(prev_end, (bx, pts[-1][0][1], bz)):
            pts[-1] = ((bx, pts[-1][0][1], bz), False)

        out: list[tuple[float, float, float]] = []
        here = (ax, ay, az)
        i = 0
        while i < len(pts):
            if pts[i][1]:
                here = pts[i][0]
                out.append(here)
                i += 1
                continue
            j = i
            while j + 1 < len(pts) and not pts[j + 1][1]:
                j += 1
            best = i
            for k in range(j, i - 1, -1):
                if self.walk_clear(here, pts[k][0]):
                    best = k
                    break
            here = pts[best][0]
            out.append(here)
            i = best + 1
        return out

    def _astar(self, s: int, g: int) -> list[int]:
        gx, gy, gz = self.node_pos(g)
        inv_c = 1.0 / max(0.25, self.cell)

        def h(nid: int) -> float:
            px, py, pz = self.node_pos(nid)
            return math.hypot(px - gx, pz - gz) * inv_c + abs(py - gy) * inv_c * 0.5

        best = {s: 0.0}
        prev = {s: -1}
        heap = [(h(s), 0.0, s)]
        expanded = 0
        while heap:
            _f, cost, u = heapq.heappop(heap)
            if u == g:
                break
            if cost > best.get(u, math.inf):
                continue
            expanded += 1
            if expanded > self.max_nodes:
                return []
            for v, w, _is_link in self._neighbors(u):
                nc = cost + w
                if nc < best.get(v, math.inf):
                    best[v] = nc
                    prev[v] = u
                    heapq.heappush(heap, (nc + h(v), nc, v))
        if g not in prev:
            return []
        out = []
        cur = g
        while cur != -1:
            out.append(cur)
            cur = prev[cur]
        out.reverse()
        return out