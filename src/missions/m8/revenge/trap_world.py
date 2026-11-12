"""Mission 8 Revenge - blocking solids of the Route 12 set for the trap fight.

Boxes are ``(x0, z0, x1, z1, h)`` read off Mission 2's own map, the same grid
``set3d`` bakes: the booths, the control building and the hut (``C``), the
jersey barriers on their 2D collision rects (``B``), the garden hedges and
fountain, the yard dressing, plus M8's wrecks, the burnt tanker, the gantry
legs and Bodi's truck.  The World API matches ``missions.m7.raid_world.World``
(blocked / move / los / ray_hit, a ``dyn`` list for the Guard truck) so the
raid's camera, movement and pellet code run on it unchanged.  Lower solids
(the jersey barriers, hedges, wrecks) block bodies but not bullets;
``low_cover`` turns them into cover.
"""
import math

from missions.m7 import raid_world as RW

from . import set3d as S3

TS, OX, OZ = S3.TS, S3.OX, S3.OZ
BOUNDS = (OX + TS, OX + 69 * TS, OZ - 79 * TS, OZ - TS)    # inside M2's border wall
BODY_R = RW.BODY_R
BODY_TOP = RW.BODY_TOP
LOS_MIN_H = RW.LOS_MIN_H
LOW_COVER_R = 1.5           # a low box this close to a target, on the line of fire
LOW_COVER_K = 0.35          # cuts a Guard's hit chance to this share

CARS = [(xz, yaw) for xz, yaw, _burned in S3.CARS]
CAR_HALF = (0.9, 2.15)
CAR_H = 1.45


def _rot_box(x, z, yaw, hw, hd, h):
    a = math.radians(yaw)
    hx = abs(math.cos(a)) * hw + abs(math.sin(a)) * hd
    hz = abs(math.sin(a)) * hw + abs(math.cos(a)) * hd
    return (x - hx, z - hz, x + hx, z + hz, h)


def _px(x, y, x2, y2, h):
    """An M2 sim-pixel rect (x, y)-(x2, y2) as a box of height h."""
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
    out.append(_rot_box(tx, tz, tyaw, 0.98, 2.42, 1.9))
    return out


STATIC = _static()


def guard_truck_at(x, z):
    """The Guard truck's collider, facing -z (it drives south at the plaza)."""
    return RW._shape("truck_m7").at(x, 0.0, z, 90.0)


class World:
    def __init__(self):
        self.boxes = list(STATIC)
        self.meshes = []
        self.dyn = []
        self._dyn_box = {}
        self.pig_at = None      # raid code reads it; there is no pig on Route 12

    def dyn_boxes(self):
        """The parked trucks as (x0, z0, x1, z1, h) boxes. The truck stands square
        in its lane, and its triangle test costs ms a call (sight lines run it
        dozens of times a frame), so walkers, sight and bullets use the box."""
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
        for b in self.dyn_boxes():
            if b[0] - r < x < b[2] + r and b[1] - r < z < b[3] + r:
                return True
        return False

    def move(self, x, z, dx, dz, r=BODY_R, clip=True):
        nx, nz = x + dx, z + dz
        if clip:
            nx = min(max(nx, BOUNDS[0]), BOUNDS[1])
            nz = min(max(nz, BOUNDS[2]), BOUNDS[3])
        if not self.blocked(nx, z, r):
            x = nx
        if not self.blocked(x, nz, r):
            z = nz
        return x, z

    def los(self, a, b, dyn=True):
        for box_ in self.boxes:
            if box_[4] >= LOS_MIN_H and RW.seg_box(a[0], a[1], b[0], b[1], box_):
                return False
        if dyn:
            for box_ in self.dyn_boxes():
                if RW.seg_box(a[0], a[1], b[0], b[1], box_):
                    return False
        return True

    def ray_hit(self, o, d, limit=60.0):
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
