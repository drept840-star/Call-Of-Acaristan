"""Mission 8 Duty - the estate's solids, stacked floors and 3D sight lines.

Boxes are (x0, z0, x1, z1, y0, y1).  Floors are (x0, z0, x1, z1, ya, yb):
flat when ya == yb, a ramp rising from z0 to z1 otherwise.  A body stands on
the highest floor under it that is no more than a step above its feet, so the
hall and the gallery over it are both walkable."""
import math

from engine3d import clamp
from engine.collision import BoxWorld, MultiFloorNav, box_xz_yy, slide_capsule
from missions.m7 import raid_world as RW
from missions.m8.revenge import trap_world as TW

from . import mansion_set as MS

BOUNDS = (-33.2, 33.2, -47.0, 56.4)
BODY_R = RW.BODY_R
BODY_TOP = RW.BODY_TOP
LOS_MIN_H = RW.LOS_MIN_H
STEP = 0.6
GF, FF = MS.GF, MS.FF
X_IN = MS.HX - MS.WALL
Z_IN = MS.HZ - MS.WALL
SLAB_Y0 = FF - MS.SLAB


def _floors():
    s0, s1 = MS.STAIR_Z0, MS.STAIR_Z1
    out = [
        (-3.7, -4.1, 3.7, -2.7, 0.0, GF),                  # portico steps
        (-3.7, -2.7, 3.7, 0.0, GF, GF),                    # portico porch
        (-MS.HX, 0.0, MS.HX, MS.HZ, GF, GF),               # ground floor
        (-MS.STAIR_X, s0, MS.STAIR_X, s1, GF, FF),         # grand staircase
        (-X_IN, 0.5, -MS.HALL_X, MS.BACK_Z, FF, FF),       # west gallery
        (MS.HALL_X, 0.5, X_IN, MS.BACK_Z, FF, FF),         # east gallery
        (-X_IN, MS.BACK_Z, X_IN, Z_IN, FF, FF),            # landing and rooms
        (-1.5, Z_IN - 0.1, 1.5, MS.TERRACE[1] + 0.2, FF, FF),  # terrace doorway
        (MS.TERRACE[0], MS.TERRACE[1], MS.TERRACE[2], MS.TERRACE[3], FF, FF),
    ]
    for bx, bz in MS.BALCONIES:
        out.append((bx - 1.5, bz - 0.9, bx + 1.5, 0.0, FF, FF))
    return out


FLOORS = _floors()


def _b(x0, z0, x1, z1, y0, y1):
    return (min(x0, x1), min(z0, z1), max(x0, x1), max(z0, z1), y0, y1)


def _rot(x, z, yaw, hw, hd, y0, y1):
    b = TW._rot_box(x, z, yaw, hw, hd, y1)
    return (b[0], b[1], b[2], b[3], y0, y1)


def _static():
    W = MS.WALL
    hx, hz = MS.HX, MS.HZ
    out = []
    # estate walls and gate
    gz = MS.GATE_Z
    for s in (-1, 1):
        out.append(_b(s * 2.7, gz - 0.5, s * 3.7, gz + 0.5, 0.0, 3.4))
        out.append(_b(s * 3.7, gz - 0.25, s * 33.7, gz + 0.25, 0.0, 1.1))
        out.append(_b(s * 33.55, gz, s * 34.05, 57.0, 0.0, 1.1))
    out.append(_b(-34.0, 56.75, 34.0, 57.25, 0.0, 1.1))
    # hedges, lamp posts, poplar trunks, fountain
    for s in (-1, 1):
        out.append(_b(s * 3.1, gz + 1.0, s * 3.7, gz + 7.0, 0.0, 1.4))
        out.append(_b(s * 3.1, gz + 10.0, s * 3.7, -18.0, 0.0, 1.4))
        out.append(_b(s * 15.2, -16.0, s * 15.8, -1.0, 0.0, 1.4))
        for k in range(5):
            z = gz + 3.0 + k * 5.5
            out.append(_b(s * 8.0 - 0.3, z - 0.3, s * 8.0 + 0.3, z + 0.3, 0.0, 6.0))
    for x, z in MS.LAMPS:
        out.append(_b(x - 0.15, z - 0.15, x + 0.15, z + 0.15, 0.0, 3.4))
    fx, _, fz = MS.FOUNTAIN_AT
    out.append(_b(fx - 2.5, fz - 2.5, fx + 2.5, fz + 2.5, 0.0, 0.75))
    out.append(_b(fx - 0.4, fz - 0.4, fx + 0.4, fz + 0.4, 0.0, 3.1))
    # portico columns and its roof (a perch for riflemen)
    for dx in (-2.7, -0.9, 0.9, 2.7):
        out.append(_b(dx - 0.25, -2.45, dx + 0.25, -1.95, 0.0, 5.9))
    out.append(_b(-3.3, -2.6, 3.3, 0.2, 5.85, 6.45))
    # wings
    for s in (-1, 1):
        out.append(_b(s * 13.0, 2.3, s * 21.2, 9.7, 0.0, 6.2))
    # house shell: front (doorway x +-1.2), sides, back (terrace doors x +-1.5)
    for s in (-1, 1):
        out.append(_b(s * 1.2, -0.05, s * hx, W, 0.0, 9.0))
        out.append(_b(s * (hx - W), 0.0, s * hx, hz, 0.0, 9.0))
        out.append(_b(s * 1.5, hz - W, s * hx, hz + 0.05, 0.0, 9.0))
    out.append(_b(-1.2, -0.05, 1.2, W, GF + 3.4, 9.0))
    out.append(_b(-1.5, hz - W, 1.5, hz, 0.0, FF))
    out.append(_b(-1.5, hz - W, 1.5, hz, FF + 2.6, 9.0))
    out.append(_b(-X_IN, 0.5, X_IN, Z_IN, MS.CEIL, MS.CEIL + 0.3))      # ceiling
    out.append(_b(-hx - 0.2, -0.2, hx + 0.2, hz + 0.2, -0.1, GF - 0.02))  # plinth (bullets only)
    # hall columns, gallery slabs and rails
    for cx, cz in MS.COLUMNS:
        out.append(_b(cx - 0.35, cz - 0.35, cx + 0.35, cz + 0.35, GF, MS.CEIL))
    for s in (-1, 1):
        out.append(_b(s * MS.HALL_X, 0.5, s * X_IN, MS.BACK_Z, SLAB_Y0, FF))
        out.append(_b(s * (MS.HALL_X - 0.15), 0.5, s * (MS.HALL_X + 0.15), MS.BACK_Z, FF, FF + 1.0))
        out.append(_b(s * MS.HALL_X, MS.BACK_Z - 0.15, s * (MS.STAIR_X + 0.2), MS.BACK_Z + 0.15, FF, FF + 1.0))
    # staircase sides
    for s in (-1, 1):
        out.append(_b(s * MS.STAIR_X, MS.STAIR_Z0, s * (MS.STAIR_X + 0.4), MS.STAIR_Z1, GF, FF + 1.0))
    # ground floor back wall (doorways x 5..7 each side) and the room dividers
    bz = MS.BACK_Z
    for x0, x1 in ((-X_IN, -7.0), (-5.0, 5.0), (7.0, X_IN)):
        out.append(_b(x0, bz - W / 2, x1, bz + W / 2, GF, SLAB_Y0))
    for x0, x1 in ((-7.0, -5.0), (5.0, 7.0)):
        out.append(_b(x0, bz - W / 2, x1, bz + W / 2, GF + 2.8, SLAB_Y0))
    for s in (-1, 1):
        out.append(_b(s * 3.25, bz, s * 3.75, Z_IN, GF, SLAB_Y0))
    out.append(_b(-X_IN, bz, X_IN, Z_IN, SLAB_Y0, FF))                  # first floor slab
    # first floor: wall to the rooms (doors: armoury, study, bedroom), room walls
    rz = MS.ROOMS_Z
    for x0, x1 in ((-X_IN, -9.0), (-7.5, -1.2), (1.2, 7.5), (9.0, X_IN)):
        out.append(_b(x0, rz - W / 2, x1, rz + W / 2, FF, MS.CEIL))
    for x0, x1 in ((-9.0, -7.5), (-1.2, 1.2), (7.5, 9.0)):
        out.append(_b(x0, rz - W / 2, x1, rz + W / 2, FF + 2.8, MS.CEIL))
    for s in (-1, 1):
        out.append(_b(s * 3.75, rz, s * 4.25, Z_IN, FF, MS.CEIL))
    # security room: racks, desks
    for z in (28.0, 31.0, 34.0):
        out.append(_b(-12.45, z - 0.55, -11.55, z + 0.55, GF, GF + 2.2))
    out.append(_b(-10.9, 34.1, -6.1, 35.1, GF, GF + 0.78))
    out.append(_b(-11.35, 27.7, -10.45, 30.3, GF, GF + 0.78))
    # dining room table
    out.append(_b(7.3, 28.0, 9.1, 34.0, GF, GF + 0.9))
    # armoury lockers, study desk and shelves, bed
    for z in (30.4, 32.4, 34.4):
        out.append(_b(-12.4, z - 0.8, -11.8, z + 0.8, FF, FF + 2.2))
    dx, _, dz = MS.DESK_AT
    out.append(_b(dx - 1.35, dz - 0.53, dx + 1.35, dz + 0.53, FF, FF + 0.9))
    for s in (-1, 1):
        out.append(_b(s * 3.3, 29.0, s * 3.8, 35.4, FF, FF + 3.0))
    out.append(_b(8.4, 32.2, 10.8, 35.1, FF, FF + 0.7))
    # terrace: the solid block under it, balustrade, cover
    x0, z0, x1, z1 = MS.TERRACE
    out.append(_b(x0, z0, x1, z1, 0.0, FF))
    for s in (-1, 1):
        out.append(_b(s * 8.85, z0, s * 9.15, z1, FF, FF + 1.0))
        bx, bzz = MS.BALCONIES[0 if s < 0 else 1]
        out.append(_b(bx - 1.5, bzz - 0.95, bx + 1.5, bzz - 0.65, FF, FF + 1.0))
        out.append(_b(bx - 1.5, bzz - 0.9, bx + 1.5, 0.0, FF - 0.3, FF))
    out.append(_b(x0, z1 - 0.15, x1, z1 + 0.15, FF, FF + 1.0))
    for x, z, w, d, h in MS.TERRACE_COVER:
        out.append(_b(x - w / 2, z - d / 2, x + w / 2, z + d / 2, FF, FF + h))
    # crates
    for cx, cy, cz, cyaw in MS.CRATE_SPOTS:
        out.append(_rot(cx, cz, cyaw, 0.44, 0.26, cy, cy + 0.5))
    return out


STATIC = _static()
_STATIC_TUPLE = tuple(STATIC)
_LOS_STATIC = tuple(b for b in STATIC if not (0.4 < b[5] - b[4] < LOS_MIN_H))
_COVER_STATIC = tuple(b for b in STATIC if 0.5 <= b[5] - b[4] < LOS_MIN_H)
_STATIC_BW = BoxWorld(box_xz_yy(b) for b in STATIC)
_LOS_STATIC_BW = BoxWorld(box_xz_yy(b) for b in _LOS_STATIC)
_MANSION_NAV = None

_CELL = 8.0
_GRID = {}
_GLOBAL_STATIC = []
for _bx in STATIC:
    _ix0, _ix1 = int(math.floor(_bx[0] / _CELL)), int(math.floor(_bx[2] / _CELL))
    _iz0, _iz1 = int(math.floor(_bx[1] / _CELL)), int(math.floor(_bx[3] / _CELL))
    if (_ix1 - _ix0 + 1) * (_iz1 - _iz0 + 1) > 12:
        _GLOBAL_STATIC.append(_bx)
    else:
        for _ix in range(_ix0, _ix1 + 1):
            for _iz in range(_iz0, _iz1 + 1):
                _GRID.setdefault((_ix, _iz), []).append(_bx)
_GRID = {_k: tuple(_v) for _k, _v in _GRID.items()}
_GLOBAL_STATIC = tuple(_GLOBAL_STATIC)


def car_box(x, z, yaw):
    return _rot(x, z, yaw, 0.95, 2.2, 0.0, 1.5)


def _ray_box(o, d, b):
    lo, hi = 0.0, 1e9
    for a, dd, mn, mx in ((o[0], d[0], b[0], b[2]), (o[1], d[1], b[4], b[5]), (o[2], d[2], b[1], b[3])):
        if abs(dd) < 1e-9:
            if a < mn or a > mx:
                return None
            continue
        t0, t1 = (mn - a) / dd, (mx - a) / dd
        if t0 > t1:
            t0, t1 = t1, t0
        lo, hi = max(lo, t0), min(hi, t1)
        if lo > hi:
            return None
    return lo


class World:
    def __init__(self):
        self.boxes = list(STATIC)
        self.box_world = _STATIC_BW
        self.front_door_box = _b(-1.2, 0.05, 1.2, 0.45, GF, GF + 3.4)
        self.study_door_box = _b(-1.2, MS.ROOMS_Z - 0.2, 1.2, MS.ROOMS_Z + 0.2, FF, FF + 2.8)
        self.terrace_door_box = _b(-1.5, MS.HZ - MS.WALL, 1.5, MS.HZ, FF, FF + 2.6)
        hx, hy, hz = MS.HELIPAD_AT
        # parked VIP helicopter (yaw 90): cabin nose +x, tail boom -x, stub wings with pods
        self.heli_boxes = [_b(hx - 2.2, hz - 1.3, hx + 6.1, hz + 1.3, FF, FF + 2.6),
                           _b(hx - 6.2, hz - 0.45, hx - 2.2, hz + 0.45, FF, FF + 2.4),
                           _b(hx + 0.8, hz - 3.6, hx + 3.0, hz + 3.6, FF + 0.9, FF + 1.4)]
        self.front_open = False
        self.study_open = False
        self.terrace_open = False
        self.heli_parked = True
        self.cars = []                      # boxes of the staff cars (wrecks stay solid)
        self.cur_y = 0.0                    # the player's feet, the default height hint
        self._cache_sig = None
        self._dyn_boxes = ()
        self._dyn_box_aabbs = ()
        self._all_boxes = _STATIC_TUPLE
        self._los_boxes = _LOS_STATIC
        self._cover_boxes = _COVER_STATIC
        self._custom_boxes = False

    def _sync_cache(self):
        sig = (self.front_open, self.study_open, self.terrace_open, self.heli_parked, tuple(self.cars))
        if sig == self._cache_sig and len(self.boxes) == len(STATIC):
            return
        self._cache_sig = sig
        dyn = list(self.cars)
        if not self.front_open:
            dyn.append(self.front_door_box)
        if not self.study_open:
            dyn.append(self.study_door_box)
        if not self.terrace_open:
            dyn.append(self.terrace_door_box)
        if self.heli_parked:
            dyn.extend(self.heli_boxes)
        self._dyn_boxes = tuple(dyn)
        self._dyn_box_aabbs = tuple(box_xz_yy(b) for b in self._dyn_boxes)
        if len(self.boxes) == len(STATIC):
            self._all_boxes = _STATIC_TUPLE + self._dyn_boxes
            self._los_boxes = _LOS_STATIC + tuple(b for b in dyn if not (0.4 < b[5] - b[4] < LOS_MIN_H))
            self._cover_boxes = _COVER_STATIC + tuple(b for b in dyn if 0.5 <= b[5] - b[4] < LOS_MIN_H)
            self._custom_boxes = False
        else:
            all_b = tuple(self.boxes) + self._dyn_boxes
            self._all_boxes = all_b
            self._los_boxes = tuple(b for b in all_b if not (0.4 < b[5] - b[4] < LOS_MIN_H))
            self._cover_boxes = tuple(b for b in all_b if 0.5 <= b[5] - b[4] < LOS_MIN_H)
            self._custom_boxes = True

    def _active(self):
        self._sync_cache()
        return list(self._all_boxes)

    def ragdoll_boxes(self):
        """Staff cars, closed doors, and parked helicopter for ragdoll collisions."""
        self._sync_cache()
        return self._dyn_box_aabbs

    def nav(self):
        """Shared multi-floor 3D navmesh over ground floor, stairs, galleries, and terrace."""
        global _MANSION_NAV
        if _MANSION_NAV is None:
            def layers_at(x, z):
                ys = [0.0]
                if -13.0 <= x <= 13.0 and -4.1 <= z <= 52.0:
                    for x0, z0, x1, z1, ya, yb in FLOORS:
                        if x0 <= x <= x1 and z0 <= z <= z1:
                            fy = ya if ya == yb else ya + (yb - ya) * clamp((z - z0) / (z1 - z0), 0.0, 1.0)
                            ys.append(fy)
                ok = []
                for fy in sorted(set(round(v, 3) for v in ys)):
                    if not _STATIC_BW.body_hits(x, z, BODY_R + 0.04, fy + 0.35, fy + BODY_TOP):
                        ok.append(fy)
                return ok

            _MANSION_NAV = MultiFloorNav(BOUNDS, 0.75, layers_at, step=STEP, body_h=BODY_TOP)
        self._sync_cache()
        _MANSION_NAV.set_dynamic_boxes(self._dyn_box_aabbs)
        return _MANSION_NAV

    def surface_y(self, x, z, y=None):
        """Highest floor under (x, z) no more than a step above ``y``."""
        if z < -4.1 or z > 52.0 or x < -13.0 or x > 13.0:
            return 0.0
        lim = (99.0 if y is None else y) + STEP
        best = 0.0
        for x0, z0, x1, z1, ya, yb in FLOORS:
            if x0 <= x <= x1 and z0 <= z <= z1:
                fy = ya if ya == yb else ya + (yb - ya) * clamp((z - z0) / (z1 - z0), 0.0, 1.0)
                if best < fy <= lim:
                    best = fy
        return best

    def blocked(self, x, z, r=BODY_R, y=None):
        sy = self.surface_y(x, z, self.cur_y if y is None else y)
        y_lo = sy + 0.35
        y_hi = sy + BODY_TOP
        self._sync_cache()
        if self._custom_boxes:
            for b in self._all_boxes:
                if b[5] > y_lo and b[4] < y_hi and RW._hit(x, z, r, b):
                    return True
            return False
        for b in _GLOBAL_STATIC:
            if b[5] > y_lo and b[4] < y_hi and RW._hit(x, z, r, b):
                return True
        for b in self._dyn_boxes:
            if b[5] > y_lo and b[4] < y_hi and RW._hit(x, z, r, b):
                return True
        ix0, ix1 = int(math.floor((x - r) / _CELL)), int(math.floor((x + r) / _CELL))
        iz0, iz1 = int(math.floor((z - r) / _CELL)), int(math.floor((z + r) / _CELL))
        if ix0 == ix1 and iz0 == iz1:
            for b in _GRID.get((ix0, iz0), ()):
                if b[5] > y_lo and b[4] < y_hi and RW._hit(x, z, r, b):
                    return True
        else:
            for ix in range(ix0, ix1 + 1):
                for iz in range(iz0, iz1 + 1):
                    for b in _GRID.get((ix, iz), ()):
                        if b[5] > y_lo and b[4] < y_hi and RW._hit(x, z, r, b):
                            return True
        return False

    def move(self, x, z, dx, dz, r=BODY_R, clip=True, y=None):
        y = self.cur_y if y is None else y
        self._sync_cache()
        bw = _STATIC_BW if not self._custom_boxes else BoxWorld(box_xz_yy(b) for b in self.boxes)
        extra = self._dyn_box_aabbs
        nx, _ny, nz, _hit = slide_capsule(
            x, y, z, dx, dz, r, BODY_TOP,
            box_world=bw, extra_boxes=extra, step_h=STEP,
            floor_fn=self.surface_y, bounds=BOUNDS if clip else None,
        )
        # Keep the open gallery/terrace drop guard so actors do not step off >1 m ledges
        if self.surface_y(nx, nz, y) <= y - 1.0:
            if self.surface_y(nx, z, y) > y - 1.0 and not self.blocked(nx, z, r, y):
                return nx, z
            if self.surface_y(x, nz, y) > y - 1.0 and not self.blocked(x, nz, r, y):
                return x, nz
            return x, z
        return nx, nz

    def los(self, a, b, dyn=True):
        ay = self.surface_y(a[0], a[1], self.cur_y) + 1.25
        by = self.surface_y(b[0], b[1], self.cur_y) + 1.25
        return self.los3d((a[0], ay, a[1]), (b[0], by, b[1]), dyn=dyn)

    def los3d(self, a, b, dyn=True):
        self._sync_cache()
        if not self._custom_boxes:
            if _LOS_STATIC_BW.segment_blocked(a, b, slack=0.0):
                return False
            ax, ay, az = a
            bx, by, bz = b
            rx0, rx1 = (ax, bx) if ax <= bx else (bx, ax)
            ry0, ry1 = (ay, by) if ay <= by else (by, ay)
            rz0, rz1 = (az, bz) if az <= bz else (bz, az)
            d = (bx - ax, by - ay, bz - az)
            for box_ in self._dyn_boxes:
                if 0.4 < box_[5] - box_[4] < LOS_MIN_H:
                    continue
                if box_[2] < rx0 or box_[0] > rx1 or box_[3] < rz0 or box_[1] > rz1 or box_[5] < ry0 or box_[4] > ry1:
                    continue
                h = _ray_box(a, d, box_)
                if h is not None and h < 1.0:
                    return False
            return True
        ax, ay, az = a
        bx, by, bz = b
        rx0, rx1 = (ax, bx) if ax <= bx else (bx, ax)
        ry0, ry1 = (ay, by) if ay <= by else (by, ay)
        rz0, rz1 = (az, bz) if az <= bz else (bz, az)
        d = (bx - ax, by - ay, bz - az)
        for box_ in self._los_boxes:
            if (box_[2] < rx0 or box_[0] > rx1 or
                box_[3] < rz0 or box_[1] > rz1 or
                box_[5] < ry0 or box_[4] > ry1):
                continue
            h = _ray_box(a, d, box_)
            if h is not None and h < 1.0:
                return False
        return True

    def ray_hit(self, o, d, limit=75.0):
        best = limit
        ox, oy, oz = o
        dx, dy, dz = d
        if dy < -1e-6:
            gy = -oy / dy
            if 0.0 < gy < best:
                best = gy
        self._sync_cache()
        if not self._custom_boxes and best <= 12.0:
            hit = _STATIC_BW.ray(o, d, best)
            if hit is not None and 1e-4 < hit[0] < best:
                best = hit[0]
            for bx0, bz0, bx1, bz1, by0, by1 in self._dyn_boxes:
                h = _ray_box(o, d, (bx0, bz0, bx1, bz1, by0, by1))
                if h is not None and 1e-4 < h < best:
                    best = h
            return best
        rx_min = ox if dx >= 0.0 else ox + dx * best
        rx_max = ox + dx * best if dx >= 0.0 else ox
        ry_min = oy if dy >= 0.0 else oy + dy * best
        ry_max = oy + dy * best if dy >= 0.0 else oy
        rz_min = oz if dz >= 0.0 else oz + dz * best
        rz_max = oz + dz * best if dz >= 0.0 else oz
        small_x, small_y, small_z = abs(dx) < 1e-9, abs(dy) < 1e-9, abs(dz) < 1e-9
        idx = 0.0 if small_x else 1.0 / dx
        idy = 0.0 if small_y else 1.0 / dy
        idz = 0.0 if small_z else 1.0 / dz
        for bx0, bz0, bx1, bz1, by0, by1 in self._all_boxes:
            if (bx1 < rx_min or bx0 > rx_max or
                bz1 < rz_min or bz0 > rz_max or
                by1 < ry_min or by0 > ry_max):
                continue
            lo, hi = 0.0, best
            if small_x:
                if ox < bx0 or ox > bx1:
                    continue
            else:
                t0, t1 = (bx0 - ox) * idx, (bx1 - ox) * idx
                if t0 > t1:
                    t0, t1 = t1, t0
                if t0 > lo: lo = t0
                if t1 < hi: hi = t1
                if lo > hi:
                    continue
            if small_y:
                if oy < by0 or oy > by1:
                    continue
            else:
                t0, t1 = (by0 - oy) * idy, (by1 - oy) * idy
                if t0 > t1:
                    t0, t1 = t1, t0
                if t0 > lo: lo = t0
                if t1 < hi: hi = t1
                if lo > hi:
                    continue
            if small_z:
                if oz < bz0 or oz > bz1:
                    continue
            else:
                t0, t1 = (bz0 - oz) * idz, (bz1 - oz) * idz
                if t0 > t1:
                    t0, t1 = t1, t0
                if t0 > lo: lo = t0
                if t1 < hi: hi = t1
                if lo > hi:
                    continue
            if 1e-4 < lo < best:
                best = lo
                rx_min = ox if dx >= 0.0 else ox + dx * best
                rx_max = ox + dx * best if dx >= 0.0 else ox
                ry_min = oy if dy >= 0.0 else oy + dy * best
                ry_max = oy + dy * best if dy >= 0.0 else oy
                rz_min = oz if dz >= 0.0 else oz + dz * best
                rz_max = oz + dz * best if dz >= 0.0 else oz
        return best

    def low_cover(self, target, shooter):
        self._sync_cache()
        tx, tz = target
        for b in self._cover_boxes:
            cx = min(max(tx, b[0]), b[2])
            cz = min(max(tz, b[1]), b[3])
            if math.hypot(tx - cx, tz - cz) > 1.5:
                continue
            if RW.seg_box(shooter[0], shooter[1], tx, tz, b):
                return True
        return False