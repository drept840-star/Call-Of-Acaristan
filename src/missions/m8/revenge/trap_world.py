"""Mission 8 Revenge - blocking solids, 3D sight lines and interactive hazards
of the Route 12 set for the trap fight.

Static solids are read from Mission 2's grid, plus M8's wrecks, the burnt
tanker, the gantry legs, Bodi's tractor, Guard sandbag bunkers and a steel
watchtower platform in the north yard.  ``los3d`` checks 3D segment-against-box
clearance so elevated overwatch Guards on the gantry or watchtower see over low
barriers while tall booths and walls still break line of sight.  Dynamic prop
colliders (fuel drums, the floodlight fusebox, the mid-plaza supply crate) sit
in ``self.props`` so shotgun hits and explosions remove or swap them cleanly.
"""
import math

from engine.collision import BoxWorld, box_xz_h, slide_capsule
from missions.m7 import raid_world as RW

from . import set3d as S3

TS, OX, OZ = S3.TS, S3.OX, S3.OZ
BOUNDS = (OX + TS, OX + 69 * TS, OZ - 79 * TS, OZ - TS)    # inside M2's border wall
BODY_R = RW.BODY_R
BODY_TOP = RW.BODY_TOP
LOS_MIN_H = RW.LOS_MIN_H
LOW_COVER_R = 1.5
LOW_COVER_K = 0.35

CARS = [(xz, yaw) for xz, yaw, _burned in S3.CARS]
CAR_HALF = (0.9, 2.15)
CAR_H = 1.45

# Interactive plaza landmarks (nudged clear of STATIC walls on startup).
BARREL_SPOTS = (
    (-42.5, 11.5),   # Beat 1: wrecks apron cluster
    (-26.8, 52.0),   # Beat 2: north truck lane ambush drum
    (-22.5, 36.5),   # Beat 2/3: beside the burnt tanker
    (-2.5, 48.0),    # Beat 3: gantry stronghold approach
)
BARREL_R = 0.42
BARREL_H = 1.10

TOWER_WANT = (-20.0, 47.5)
TOWER_HALF = 1.15
TOWER_H = 2.60

FUSEBOX_WANT = (-47.0, 15.5)
SUPPLY_WANT = (-45.0, 13.5)
KIOSK_WANT = (-46.2, 15.8)
RADIO_AT = S3.tile(39, 36)            # Darius's field radio baked in set3d

FLOOD_POLES = (
    (-54.0, 12.0),
    (-35.0, 28.0),
    (-12.0, 44.0),
)
FLOOD_H = 4.6
FLOOD_R = 7.6


def _rot_box(x, z, yaw, hw, hd, h):
    a = math.radians(yaw)
    hx = abs(math.cos(a)) * hw + abs(math.sin(a)) * hd
    hz = abs(math.sin(a)) * hw + abs(math.cos(a)) * hd
    return (x - hx, z - hz, x + hx, z + hz, h)


def _px(x, y, x2, y2, h):
    k = TS / 64.0
    return (x * k + OX, OZ - y2 * k, x2 * k + OX, OZ - y * k, h)


def _static():
    from missions.m2 import draw as M2
    from missions.m2 import draw3d as M2D
    from missions.m2.meta import GARDEN_FOUNTAIN_RECT, GARDEN_HEDGE_RECTS, GARDEN_TREE_RECTS
    out = []
    for c0, r0, w, h, kind, _var in M2D._wall_boxes():
        if kind in ("border", "tower"):
            continue
        out.append((c0 * TS + OX, OZ - (r0 + h) * TS, (c0 + w) * TS + OX, OZ - r0 * TS,
                    M2D.WALL_H[kind]))
    for row in range(80):
        for col in range(70):
            if S3._glyph(col, row) == "B":
                out.append(_px(col * 64 + 4, row * 64 + 12, col * 64 + 60, row * 64 + 52, 0.82))
    for rc in GARDEN_HEDGE_RECTS:
        out.append(_px(rc.left, rc.top, rc.right, rc.bottom, 1.0))
    fr = GARDEN_FOUNTAIN_RECT
    out.append(_px(fr.left, fr.top, fr.right, fr.bottom, 0.6))
    for rc in GARDEN_TREE_RECTS:
        cx, cy = rc.center
        out.append(_px(cx - 8, cy - 8, cx + 8, cy + 8, 2.0))
    for kind, ptx, pty, arg in M2._M2_DRESSING_PROPS:
        if kind in ("crates", "barrels") and S3._glyph(ptx, pty) not in ("C", "B", "T", ""):
            x, z = S3.tile(ptx, pty)
            out.append((x - 0.6, z - 0.5, x + 0.9, z + 0.7, 0.8))
    for (x, z), yaw in CARS:
        out.append(_rot_box(x, z, yaw, CAR_HALF[0], CAR_HALF[1], CAR_H))
    (tx, tz), L, W = S3.TANKER
    out.append((tx - L * 0.48, tz - W * 0.45, tx + L * 0.48, tz + W * 0.45, 1.6))
    for lx, lz in S3.GANTRY_LEGS:
        out.append((lx - 0.4, lz - 0.2, lx + 0.4, lz + 0.2, S3.CATWALK_Y))
    tx, tz, tyaw = S3.TRUCK_AT
    out.append(_rot_box(tx, tz, tyaw, 1.15, 2.0, 2.3))
    for sx, sz, sln, sdp, syaw in S3.SANDBAGS:
        out.append(_rot_box(sx, sz, syaw, sln * 0.5, sdp * 0.5, 0.82))
    return out


STATIC = _static()
_STATIC_BW = BoxWorld(box_xz_h(b) for b in STATIC)


def _clear_point(x, z, r, extra=()):
    """Keep a prop placement outside STATIC boxes (and optional extra boxes)."""
    def ok(px, pz):
        for b in STATIC:
            if RW._hit(px, pz, r, b):
                return False
        for b in extra:
            if RW._hit(px, pz, r, b):
                return False
        return BOUNDS[0] + r <= px <= BOUNDS[1] - r and BOUNDS[2] + r <= pz <= BOUNDS[3] - r

    if ok(x, z):
        return x, z
    for rad in (0.8, 1.6, 2.5, 3.6):
        for i in range(12):
            ang = i * math.pi / 6.0
            nx, nz = x + math.cos(ang) * rad, z + math.sin(ang) * rad
            if ok(nx, nz):
                return nx, nz
    return x, z


TOWER_AT = _clear_point(TOWER_WANT[0], TOWER_WANT[1], TOWER_HALF + 0.25)
TOWER_BOX = (TOWER_AT[0] - TOWER_HALF, TOWER_AT[1] - TOWER_HALF,
             TOWER_AT[0] + TOWER_HALF, TOWER_AT[1] + TOWER_HALF, TOWER_H)
FUSEBOX_AT = _clear_point(FUSEBOX_WANT[0], FUSEBOX_WANT[1], 0.55, (TOWER_BOX,))
SUPPLY_AT = _clear_point(SUPPLY_WANT[0], SUPPLY_WANT[1], 0.70, (TOWER_BOX,))
KIOSK_AT = _clear_point(KIOSK_WANT[0], KIOSK_WANT[1], 0.75, (TOWER_BOX,))
BARREL_COORDS = tuple(_clear_point(bx, bz, BARREL_R + 0.15, (TOWER_BOX,))
                      for bx, bz in BARREL_SPOTS)


def guard_truck_at(x, z):
    """The Guard truck's collider, facing -z (it drives south at the plaza)."""
    return RW._shape("truck_m7").at(x, 0.0, z, 90.0)


def _seg_box3d(ax, ay, az, bx, by, bz, box_):
    """True when segment (a -> b) intersects the vertical box ``(x0, z0, x1, z1, h)``."""
    x0, z0, x1, z1, h = box_
    dx, dy, dz = bx - ax, by - ay, bz - az
    tmin, tmax = 0.02, 0.98
    for p0, dp, lo, hi in ((ax, dx, x0, x1), (ay, dy, 0.0, h), (az, dz, z0, z1)):
        if abs(dp) < 1e-8:
            if p0 < lo or p0 > hi:
                return False
        else:
            inv = 1.0 / dp
            t1, t2 = (lo - p0) * inv, (hi - p0) * inv
            if t1 > t2:
                t1, t2 = t2, t1
            tmin = max(tmin, t1)
            tmax = min(tmax, t2)
            if tmin > tmax:
                return False
    return tmin <= tmax


class World:
    def __init__(self):
        self.boxes = list(STATIC) + [TOWER_BOX]
        self.box_world = BoxWorld(box_xz_h(b) for b in self.boxes)
        self.meshes = []
        self.dyn = []
        self.props = []          # dynamic (x0, z0, x1, z1, h) for intact barrels/fusebox/crate
        self._dyn_box = {}
        self.pig_at = None       # raid code reads it; there is no pig on Route 12

    def dyn_boxes(self):
        out = []
        for i, m in enumerate(self.dyn):
            if m is None:
                continue
            c = self._dyn_box.get(i)
            if c is None or c[0] is not m:
                wb = m.world_box()
                c = self._dyn_box[i] = (m, (wb[0], wb[2], wb[3], wb[5], wb[4]))
            out.append(c[1])
        return out

    def blocked(self, x, z, r=BODY_R):
        for b in self.boxes:
            if RW._hit(x, z, r, b):
                return True
        for b in self.props:
            if b is not None and RW._hit(x, z, r, b):
                return True
        for b in self.dyn_boxes():
            if b[0] - r < x < b[2] + r and b[1] - r < z < b[3] + r:
                return True
        return False

    def move(self, x, z, dx, dz, r=BODY_R, clip=True):
        extra = [box_xz_h(b) for b in self.props if b is not None]
        for b in self.dyn_boxes():
            extra.append(box_xz_h(b))
        nx, _ny, nz, _hit = slide_capsule(
            x, 0.0, z, dx, dz, r, BODY_TOP,
            box_world=self.box_world, extra_boxes=extra,
            bounds=BOUNDS if clip else None,
        )
        return nx, nz

    def los(self, a, b, dyn=True):
        for box_ in self.boxes:
            if box_[4] >= LOS_MIN_H and RW.seg_box(a[0], a[1], b[0], b[1], box_):
                return False
        if dyn:
            for box_ in self.dyn_boxes():
                if RW.seg_box(a[0], a[1], b[0], b[1], box_):
                    return False
        return True

    def los3d(self, a, b, dyn=True):
        """3D line of sight ``(x, y, z) -> (x, y, z)`` respecting box heights."""
        ax, ay, az = a
        bx, by, bz = b
        for box_ in self.boxes:
            if box_[4] >= LOS_MIN_H and _seg_box3d(ax, ay, az, bx, by, bz, box_):
                return False
        if dyn:
            for box_ in self.dyn_boxes():
                if _seg_box3d(ax, ay, az, bx, by, bz, box_):
                    return False
        return True

    def ray_hit(self, o, d, limit=75.0):
        best = limit
        if d[1] < -1e-6:
            gy = -o[1] / d[1]
            if 0.0 < gy < best:
                best = gy
        for b in self.boxes:
            h = RW._ray_box(o, d, b)
            if h is not None and h < best:
                best = h
        for b in self.dyn_boxes():
            h = RW._ray_box(o, d, b)
            if h is not None and h < best:
                best = h
        return best

    def ray_hit_static(self, o, d, limit=75.0):
        """Ray cast against ground and static world boxes only (skips dyn trucks)."""
        best = limit
        if d[1] < -1e-6:
            gy = -o[1] / d[1]
            if 0.0 < gy < best:
                best = gy
        for b in self.boxes:
            h = RW._ray_box(o, d, b)
            if h is not None and h < best:
                best = h
        return best

    def surface_y(self, x, z):
        """Deck/platform height at ``(x, z)`` for elevated corpses."""
        if (S3.DECK_X[0] - 0.3 <= x <= S3.DECK_X[1] + 0.3
                and abs(z - S3.CATWALK_Z) <= S3.DECK_D * 0.55):
            return S3.CATWALK_Y
        if TOWER_BOX[0] <= x <= TOWER_BOX[2] and TOWER_BOX[1] <= z <= TOWER_BOX[3]:
            return TOWER_H
        return 0.0

    def ragdoll_boxes(self):
        """Elevated deck/guardrails, dynamic trucks, and props for ragdoll collisions."""
        x0, x1 = S3.DECK_X
        zc, hd = S3.CATWALK_Z, S3.DECK_D * 0.5
        y = S3.CATWALK_Y
        lx = S3.LADDER_X
        out = [
            (x0, y - 0.25, zc - hd, x1, y, zc + hd),
            (x0, y, zc + hd - 0.08, x1, y + 0.92, zc + hd + 0.08),
            (x0, y, zc - hd - 0.08, lx - 0.4, y + 0.92, zc - hd + 0.08),
            (lx + 0.4, y, zc - hd - 0.08, x1, y + 0.92, zc - hd + 0.08),
        ]
        for b in self.dyn_boxes():
            out.append(box_xz_h(b))
        for b in self.props:
            if b is not None:
                out.append(box_xz_h(b))
        return tuple(out)

    def low_cover(self, target, shooter):
        """True when a low box hugs ``target`` on the line from ``shooter`` (x, z)."""
        tx, tz = target
        for b in self.boxes:
            if b[4] >= LOS_MIN_H or b[4] < 0.5:
                continue
            cx = min(max(tx, b[0]), b[2])
            cz = min(max(tz, b[1]), b[3])
            if math.hypot(tx - cx, tz - cz) > LOW_COVER_R:
                continue
            if RW.seg_box(shooter[0], shooter[1], tx, tz, b):
                return True
        return False