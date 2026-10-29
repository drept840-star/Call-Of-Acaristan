"""Mission 7 raid world: collision boxes, line of sight, the barn fire and the props.

The static farm comes from ``cutscenes.m7world3d``; this module holds the blocking
boxes that match it, the fire that spreads in front of the barn, and the meshes
for the raid's trucks and dog (the films borrow both: the convoy lights far
up the valley in the raid-in, and the orchard vanguard).

Axes: x east, y up, z north.  Yaw 0 faces +z and turns clockwise seen from above.
"""
import math
import os
import random

from engine3d.core import Mesh, box, rot_y
from cutscenes import m6fx3d as _fx
from cutscenes import m7world3d as F

BOUNDS = (-19.4, 44.0, -27.0, 21.5)     # player and allies: x0, x1, z0, z1
BODY_R = 0.32
LOS_MIN_H = 1.15                        # lower boxes do not stop bullets

# Tractor parked across the track mouth (prep "block the track").
TRACTOR_BLOCK = (-0.3, -15.0, 0)
TRACTOR_YAW_BOX = {0: (-1.7, 2.3, -1.3, 1.3), -90: (-1.3, 1.3, -1.7, 2.3)}

LOFT_AT = (13.0, 4.7, 6.45)             # Bodi's ledge below the hayloft door
BODI_GROUND = (8.2, 2.2)
WELL_PIN = (1.0, 2.5)
TANK_AT = (-7.6, 1.5, -9.0)
GATE_EAST = (20.0, 0.0)
MOUTH = (0.0, -17.0)


def _orchard():
    out, i = [], 0
    for x in (26, 31, 36, 41):
        for z in (-8, -2, 4, 10, 16):
            tx = x + ((i * 13) % 5) * 0.2 - 0.4
            tz = z + ((i * 7) % 5) * 0.2 - 0.4
            out.append((tx - 0.2, tz - 0.2, tx + 0.2, tz + 0.2, 2.0))
            i += 1
    return out


# x0, z0, x1, z1, height
STATIC = [
    (-16.5, 7.0, -7.5, 13.0, 3.2),      # house
    (7.0, 7.0, 19.0, 17.0, 4.8),        # barn
    (-12.7, -10.5, -9.3, -7.5, 2.4),    # fuel shed
    (-8.25, -9.65, -6.95, -8.35, 2.2),  # fuel tank (the stand is open)
    (-13.75, -9.85, -13.25, -8.05, 0.85),
    (0.15, 3.15, 1.85, 4.85, 0.7),      # well wall
    (5.1, 5.55, 6.7, 6.45, 1.4),        # hay bales
    (5.7, 3.35, 7.3, 4.25, 1.4),
    (-20.15, -16.15, -3.4, -15.85, 0.9),    # fence, south
    (3.4, -16.15, 20.15, -15.85, 0.9),
    (-20.15, -16.0, -19.85, 22.0, 0.9),     # fence, west
    (19.85, -16.0, 20.15, -3.0, 0.9),       # fence, east
    (19.85, 3.0, 20.15, 22.0, 0.9),
    (-17.6, 8.1, -16.5, 11.9, 1.2),     # woodpile on the house's west gable
    (-18.55, 2.65, -17.55, 4.75, 1.8),  # crate stack
    (-14.75, -13.65, -13.4, -12.25, 0.95),  # oil drums
    (15.4, -9.85, 17.6, -9.15, 0.6),    # stock trough
    (12.8, -13.7, 15.2, -11.9, 1.1),    # tarped pile
    (-18.7, -13.7, -18.3, -13.3, 8.0),  # telephone poles
    (-5.7, -21.2, -5.3, -20.8, 8.0),
] + _orchard()


def tractor_box(x, z, yaw):
    x0, x1, z0, z1 = TRACTOR_YAW_BOX[yaw]
    return (x + x0, z + z0, x + x1, z + z1, 1.9)


def seg_box(ax, az, bx, bz, box_):
    """True when the segment a-b crosses the XZ rectangle (slab test)."""
    x0, z0, x1, z1 = box_[:4]
    dx, dz = bx - ax, bz - az
    lo, hi = 0.0, 1.0
    for a, d, mn, mx in ((ax, dx, x0, x1), (az, dz, z0, z1)):
        if abs(d) < 1e-9:
            if a < mn or a > mx:
                return False
            continue
        t0, t1 = (mn - a) / d, (mx - a) / d
        if t0 > t1:
            t0, t1 = t1, t0
        lo, hi = max(lo, t0), min(hi, t1)
        if lo > hi:
            return False
    return True


class World:
    """Blocking boxes for one raid: the static farm plus the vehicles."""

    def __init__(self, tractor_blocks):
        self.boxes = list(STATIC)
        self.tractor = None
        if tractor_blocks:
            self.tractor = TRACTOR_BLOCK
            self.boxes.append(tractor_box(*TRACTOR_BLOCK))
        else:
            self.boxes.append(tractor_box(-16.0, -3.0, -90))
        self.dyn = []

    def blocked(self, x, z, r=BODY_R):
        for b in self.boxes:
            if _hit(x, z, r, b):
                return True
        for b in self.dyn:
            if _hit(x, z, r, b):
                return True
        return False

    def move(self, x, z, dx, dz, r=BODY_R, clip=True):
        """Axis-separated slide; returns the new (x, z)."""
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
        """Open line between two (x, z) points at chest height."""
        for box_ in self.boxes:
            if box_[4] >= LOS_MIN_H and seg_box(a[0], a[1], b[0], b[1], box_):
                return False
        if dyn:
            for box_ in self.dyn:
                if seg_box(a[0], a[1], b[0], b[1], box_):
                    return False
        return True

    def ray_hit(self, o, d, limit=60.0):
        """Distance along the ray (3D origin, unit direction) to the nearest box top
        or side, ground included; used to stop bullets and tracers."""
        best = limit
        if d[1] < -1e-6:
            gy = -o[1] / d[1]
            if 0.0 < gy < best:
                best = gy
        for b in self.boxes + self.dyn:
            h = _ray_box(o, d, b)
            if h is not None and h < best:
                best = h
        return best


def _hit(x, z, r, b):
    cx = min(max(x, b[0]), b[2])
    cz = min(max(z, b[1]), b[3])
    return (x - cx) ** 2 + (z - cz) ** 2 < r * r


def _ray_box(o, d, b):
    lo, hi = 0.0, 1e9
    for a, dd, mn, mx in ((o[0], d[0], b[0], b[2]), (o[1], d[1], 0.0, b[4]),
                          (o[2], d[2], b[1], b[3])):
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
    return lo if lo > 0.0 else None


# --- fire in front of the barn -------------------------------------------------

FIRE_COLS = tuple(range(4, 19, 2))
FIRE_ROWS = (4, 6)
FIRE_MAX = 11
FIRE_DPS = 16.0


class Fire:
    """A few cells of burning ground in front of the barn that creep toward the yard."""

    def __init__(self):
        self.rng = random.Random(31)
        self.cells = {}
        self.next_spread = 0.0
        self.lit = False
        self.t0 = 0.0

    def ignite(self, now):
        self.lit = True
        self.t0 = now
        self.next_spread = now + 2.6
        for i in (5, 6):
            self.cells[(i, 1)] = now

    def update(self, now):
        if not self.lit or now < self.next_spread or len(self.cells) >= FIRE_MAX:
            return
        self.next_spread = now + 2.6 + self.rng.random() * 1.4
        i, j = self.rng.choice(list(self.cells))
        di, dj = self.rng.choice(((1, 0), (-1, 0), (0, 1), (0, -1)))
        ni, nj = i + di, j + dj
        if 0 <= ni < len(FIRE_COLS) and 0 <= nj < len(FIRE_ROWS) and (ni, nj) not in self.cells:
            self.cells[(ni, nj)] = now

    def burning(self, x, z, r=1.25):
        for (i, j) in self.cells:
            if (x - FIRE_COLS[i]) ** 2 + (z - FIRE_ROWS[j]) ** 2 < r * r:
                return True
        return False

    def grow(self, now):
        return min(1.0, (now - self.t0) / 20.0) if self.lit else 0.0

    def draw(self, r, t, now):
        if not self.lit:
            return
        for n, ((i, j), t0) in enumerate(self.cells.items()):
            size = min(1.0, 0.35 + (now - t0) / 4.0) * (1.1 + 0.2 * (n % 3))
            F.fire(r, (FIRE_COLS[i], 0.05, FIRE_ROWS[j]), t, seed=n * 5 + 2, size=size,
                   smoky=n % 3 == 0, layer=2)
        g = self.grow(now)
        for n, (dx, dy, dz, sz) in enumerate(((-3.6, 4.7, 10.0, 1.05), (-0.5, 4.9, 12.0, 1.2),
                                              (2.8, 4.7, 14.0, 1.0), (4.2, 4.8, 10.5, 0.95),
                                              (-2.0, 1.4, 6.9, 0.85), (2.2, 1.6, 6.9, 0.8))):
            # Keep the barn tongues just in front of its south facade. The
            # raid's world-depth layer then lets Bodi/Alex/guards correctly
            # occlude the flames when they cross in front of them.
            F.fire(r, (13.0 + dx, dy, 6.35), t, seed=40 + n * 3,
                   size=sz * (0.45 + 0.55 * g), smoky=n % 2 == 0, layer=2)

    def lights(self, t, now):
        if not self.lit:
            return []
        g = self.grow(now)
        out = F.burn_lights(t)[:2]
        for ln in out:
            ln["intensity"] *= 0.4 + 0.6 * g
        return out


# --- props ---------------------------------------------------------------------

OLIVE = (62, 74, 54)
OLIVE_D = (42, 50, 38)
CANVAS = (88, 92, 66)
GLASS = (30, 40, 52)


_TRUCK = []


def truck():
    """Guard cargo truck from assets/3D/IPA-army-truck.glb (tools/ae_import_truck.py),
    local forward +x, 6.1 long and 2.5 wide, bed floor at 1.29.  Falls back to
    the block truck when the asset is missing."""
    if not _TRUCK:
        try:
            from game.render3d_bridge import load_mesh_asset
            verts, faces = load_mesh_asset("truck_m7")
        except (OSError, ValueError):
            return _truck_blocks()
        m = Mesh()
        m.verts = [tuple(v) for v in verts]
        m.faces = [(tuple(f[0]), tuple(f[1]), 2, True, f[2] > 0) for f in faces]
        _TRUCK.append(m)
    return _TRUCK[0]


def _truck_blocks():
    """Olive cargo truck, local forward +x, 5.4 long and 2.3 wide."""
    m = Mesh()
    # Continuous wheels: the sidewall and rim are tiled together so neither
    # the software renderer nor GL has overlapping, protruding hub pieces.
    def wheel(x, z):
        n, rad, wid, cy = 12, 0.48, 0.30, 0.48 * math.cos(math.pi / 12) - 0.02
        angles = [math.tau * k / n + math.pi / n for k in range(n)]
        def ring(r):
            return [(x + r * math.cos(a), cy + r * math.sin(a)) for a in angles]
        outer, shoulder, bead, rim, hub = (ring(rad * f) for f in (1, 0.85, 0.52, 0.43, 0.18))
        for k in range(n):
            j = (k + 1) % n
            for band in range(3):
                za, zb = z - wid / 2 + wid * band / 3, z - wid / 2 + wid * (band + 1) / 3
                m.face([(outer[k][0], outer[k][1], za), (outer[j][0], outer[j][1], za),
                        (outer[j][0], outer[j][1], zb), (outer[k][0], outer[k][1], zb)],
                       F._v(F.RUB, 10 if (k + band) % 2 else 3), 2, True)
        for side in (-1, 1):
            zz = z + side * wid / 2
            for k in range(n):
                j = (k + 1) % n
                for out, inside, col in ((outer, shoulder, F._v(F.RUB, 8)),
                                          (shoulder, bead, F.RUB),
                                          (bead, rim, F._v(F.RUB, -6)),
                                          (rim, hub, F._v(OLIVE, 10 if k % 2 else -3))):
                    m.face([(out[k][0], out[k][1], zz), (out[j][0], out[j][1], zz),
                            (inside[j][0], inside[j][1], zz), (inside[k][0], inside[k][1], zz)],
                           col, 2, True)
            m.face([(px, py, zz) for px, py in hub], OLIVE_D, 2, True)
    for x in (-1.6, 1.55):
        for z in (-1.05, 1.05):
            wheel(x, z)
    m.add(box(5.2, 0.45, 2.0, OLIVE_D, center=(0, 0.95, 0)))
    m.add(box(1.7, 1.4, 2.2, OLIVE, center=(1.75, 1.85, 0)))
    m.add(box(0.06, 0.6, 1.8, GLASS, center=(2.62, 2.15, 0)))
    m.add(box(3.2, 0.14, 2.3, OLIVE_D, center=(-0.85, 1.25, 0)))
    for sz in (-1.12, 1.12):
        m.add(box(3.2, 0.62, 0.1, OLIVE, center=(-0.85, 1.62, sz)))
    m.add(box(0.1, 0.62, 2.3, OLIVE, center=(-2.4, 1.62, 0)))
    m.add(box(0.1, 0.62, 2.3, OLIVE, center=(0.72, 1.62, 0)))
    m.add(box(0.2, 0.3, 2.2, F.RUB, center=(2.75, 0.75, 0)))
    for sz in (-0.7, 0.7):
        m.add(box(0.12, 0.22, 0.52, F.RUB, center=(2.72, 1.36, sz)))
        m.add(box(0.10, 0.18, 0.44, (255, 238, 198), center=(2.79, 1.36, sz),
                  emissive=True))
    # Cab roof, split windscreen, doors and mirrors.  Keep the cargo bed
    # open: the raid and films stage passengers and the gunner inside it.
    m.add(box(1.82, 0.12, 2.24, OLIVE_D, center=(1.75, 2.60, 0)))
    m.add(box(0.07, 0.64, 0.075, OLIVE_D, center=(2.66, 2.15, 0)))
    for side in (-1, 1):
        z = side * 1.115
        m.add(box(1.05, 0.58, 0.035, GLASS, center=(1.65, 2.19, z)))
        m.add(box(0.06, 0.70, 0.045, OLIVE_D, center=(1.65, 2.17, z * 1.01)))
        m.add(box(0.66, 0.035, 0.035, OLIVE_D, center=(1.65, 1.82, z * 1.01)))
        m.add(box(0.19, 0.045, 0.045, F.HUB, center=(1.28, 1.72, z * 1.02)))
        m.add(box(0.35, 0.05, 0.05, OLIVE_D, center=(2.14, 2.20, side * 1.22)))
        m.add(box(0.10, 0.26, 0.12, GLASS, center=(2.29, 2.20, side * 1.22)))
        # Cargo side stakes and horizontal plank seams.
        for xx in (-2.25, -1.5, -0.75, 0.0, 0.55):
            m.add(box(0.065, 0.65, 0.06, OLIVE_D, center=(xx, 1.62, side * 1.18)))
        m.add(box(3.12, 0.035, 0.035, OLIVE_D, center=(-0.85, 1.62, side * 1.18)))
        m.add(box(0.84, 0.12, 0.40, OLIVE_D, center=(1.55, 1.05, side * 0.99)))
        m.add(box(0.20, 0.13, 0.22, (140, 43, 30), center=(-2.48, 1.23, side * 0.86)))
    # Radiator grille and guard, inside the existing front bumper envelope.
    m.add(box(0.045, 0.52, 0.92, OLIVE_D, center=(2.64, 1.53, 0)))
    for z in (-0.36, -0.24, -0.12, 0, 0.12, 0.24, 0.36):
        m.add(box(0.035, 0.46, 0.035, F.HUB, center=(2.67, 1.53, z)))
    # Open cargo box: narrow top rails, inner bench ledges and tailgate braces.
    for side in (-1, 1):
        z = side * 1.12
        m.add(box(3.2, 0.055, 0.12, F._v(OLIVE, 12), center=(-0.85, 1.96, z)))
        m.add(box(2.75, 0.075, 0.23, F.WOOD_D, center=(-0.85, 1.47, side * 0.88)))
        m.add(box(0.36, 0.08, 0.30, OLIVE_D, center=(0.95, 0.77, side * 1.02)))
        # Fender lips span the wheel without cutting into the wheel mesh.
        for xx in (-1.6, 1.55):
            m.add(box(1.0, 0.09, 0.32, OLIVE_D, center=(xx, 1.05, side * 1.02)))
        m.add(box(0.10, 0.24, 0.19, (110, 42, 31), center=(-2.49, 1.42, side * 0.86)))
        m.add(box(0.38, 0.05, 0.045, F.HUB, center=(0.99, 1.70, side * 1.135)))
    for z in (-0.82, 0.0, 0.82):
        m.add(box(0.05, 0.58, 0.07, OLIVE_D, center=(-2.46, 1.63, z)))
    m.add(box(0.055, 0.04, 2.18, OLIVE_D, center=(-2.46, 1.64, 0)))
    # Windscreen wipers and a small protective bar across the grille.
    for z in (-0.45, 0.45):
        m.add(box(0.035, 0.035, 0.64, OLIVE_D, center=(2.665, 1.92, z)))
    m.add(box(0.06, 0.06, 1.05, OLIVE_D, center=(2.70, 1.30, 0)))
    # Tail hitch stays within the body footprint and doesn't affect collision.
    m.add(box(0.18, 0.13, 0.30, F.RUB, center=(-2.50, 0.75, 0)))
    return m


_DOG = {}
_RIG = []
DOG_RUN_M = 2.7       # metres per Run cycle (0.42 s at the raid dog's 6.4 m/s)


def _dog_rig():
    """Parts and baked clips of assets/3D/dawg.glb (tools/ae_import_dog.py)."""
    if not _RIG:
        import json
        from game.render3d_bridge import MESHES_DIR
        with open(os.path.join(MESHES_DIR, "dog_m7.rig.json"), encoding="utf-8") as fh:
            _RIG.append(json.load(fh))
    return _RIG[0]


def dog_clip_s(clip):
    """Length in seconds of one of the dog's clips: Idle, Run, Bite, Death."""
    return _dog_rig()["clips"][clip]["dur"]


def dog(clip="Idle", t=0.0):
    """Guard dog ``t`` seconds into ``clip``, local forward +x.  Idle, Run and
    Bite loop; Death holds its last frame."""
    rig = _dog_rig()
    c = rig["clips"][clip]
    n = len(c["frames"])
    if c["loop"]:
        f = int(t / c["dur"] * n) % n
    else:
        f = min(n - 1, max(0, int(round(t / c["dur"] * (n - 1)))))
    m = _DOG.get((clip, f))
    if m is None:
        m = Mesh()
        for part, x in zip(rig["parts"], c["frames"][f]):
            base = len(m.verts)
            m.verts.extend((x[0] * a + x[1] * b + x[2] * d + x[3],
                            x[4] * a + x[5] * b + x[6] * d + x[7],
                            x[8] * a + x[9] * b + x[10] * d + x[11]) for a, b, d in part["verts"])
            m.faces.extend((tuple(i + base for i in idx), tuple(col), 2, True, em)
                           for idx, col, em in part["faces"])
        _DOG[(clip, f)] = m
    return m


def placed(mesh, x, y, z, yaw_deg):
    """A mesh with local forward +x set down facing the world yaw (0 = +z)."""
    w = Mesh()
    w.add(mesh, rot_y(yaw_deg - 90.0), t=(x, y, z))
    return w


def ledge():
    """The plank balcony Bodi stands on in front of the hayloft door."""
    m = Mesh()
    m.add(box(2.2, 0.14, 1.2, F.WOOD, center=(LOFT_AT[0], LOFT_AT[1] - 0.07, LOFT_AT[2])))
    for sx in (-0.9, 0.9):
        m.add(box(0.1, 0.3, 0.95, F.WOOD_D, center=(LOFT_AT[0] + sx, LOFT_AT[1] - 0.2,
                                                    LOFT_AT[2] + 0.15)))
    m.add(box(2.2, 0.06, 0.06, F.WOOD, center=(LOFT_AT[0], LOFT_AT[1] + 0.9, LOFT_AT[2] - 0.55)))
    for sx in (-1.05, 1.05):
        m.add(box(0.06, 0.9, 0.06, F.WOOD_D, center=(LOFT_AT[0] + sx, LOFT_AT[1] + 0.45,
                                                      LOFT_AT[2] - 0.55)))
    return m


def tank_glow(t, armed):
    """Faint amber lamp on the rigged tank so the player can find it in the dark."""
    return _fx.glow((255, 150, 60), 0.9, t, intensity=0.55 if armed else 0.0, max_px=36)
