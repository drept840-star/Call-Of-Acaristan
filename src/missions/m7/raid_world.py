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

from engine3d.core import Mesh, box, m_apply, rot_x, rot_y
from engine.collision import MeshCollider
from cutscenes import m6fx3d as _fx
from cutscenes import m6world3d as _w
from cutscenes import m7world3d as F

BOUNDS = (-19.4, 44.0, -27.0, 21.5)     # player and allies: x0, x1, z0, z1
BODY_R = 0.32
BODY_TOP = 1.9                          # a body blocks anything under this height
LOS_MIN_H = 1.15                        # lower solids do not stop bullets

# Tractor parked across the track mouth (prep "block the track"): x, z, yaw.
TRACTOR_BLOCK = (-0.3, -15.0, 0)
MOTORCYCLE_AT = (16.75, -6.4, 100.0)    # x, z, yaw: next to the pig

LOFT_AT = (13.0, 4.7, 6.45)             # Bodi's ledge below the hayloft door
BODI_GROUND = (8.2, 2.2)
WELL_PIN = (1.0, 1.9)                   # Alex's hips, under the fallen crossbeam
WELL_AT = (1.0, 4.0)
WELL_HINGE = (0.0, 0.7, -0.55)          # the roof tips south about the south wall's top
WELL_DOWN = 112.0                       # degrees the fallen frame lies at, beam across Alex
WELL_LIFT_AT = (2.3, 1.85)              # Biribel's spot at the beam's east end
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
    (4.32, 5.5, 7.28, 6.55, 1.42),      # hay bales, hay(4) at (5.8, 6)
    (4.93, 3.3, 7.87, 4.27, 1.42),      # hay bales, hay(3) at (6.4, 3.8)
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


_SHAPES = {}


def _shape(ref):
    """Collider of an imported mesh, built once from its triangles."""
    if ref not in _SHAPES:
        from game.render3d_bridge import load_mesh_asset
        verts, faces = load_mesh_asset(ref)
        _SHAPES[ref] = MeshCollider(verts, [f[0] for f in faces])
    return _SHAPES[ref]


def tractor_at(x, z, yaw):
    """Tractor asset at (x, z), local forward +x turned by ``yaw`` (as the renderer does)."""
    return _shape("tractor_m7").at(x, 0.0, z, yaw)


_MOTO = []


def motorcycle_at(x, z, yaw):
    """Scrambler at (x, z) turned by ``yaw`` as build_static draws it."""
    if not _MOTO:
        m = F.motorcycle()
        _MOTO.append(MeshCollider(m.verts, [f[0] for f in m.faces]))
    return _MOTO[0].at(x, 0.0, z, yaw)


def truck_at(x, z):
    """Truck asset at (x, z) facing +z, as ``put(..., yaw 0)`` draws it."""
    return _shape("truck_m7").at(x, 0.0, z, -90.0)


def _mesh_sight(m, a, b):
    """True when the chest-height sight line from a to b (x, z) meets the mesh."""
    dx, dz = b[0] - a[0], b[1] - a[1]
    dist = math.hypot(dx, dz)
    if dist < 1e-9:
        return False
    return m.ray((a[0], LOS_MIN_H, a[1]), (dx / dist, 0.0, dz / dist), dist) is not None


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
    """Blocking solids for one raid: the static farm boxes, the tractor and the trucks."""

    def __init__(self, tractor_blocks):
        self.boxes = list(STATIC)
        self.tractor = None
        if tractor_blocks:
            self.tractor = TRACTOR_BLOCK
            tractor = tractor_at(*TRACTOR_BLOCK)
        else:
            tractor = tractor_at(-16.0, -3.0, -90)
        self.meshes = [tractor, motorcycle_at(*MOTORCYCLE_AT)]
        self.dyn = []          # placed truck colliders, kept current by raid_brain
        self.pig_at = None     # the pig's (x, z) while it is on the farm

    def blocked(self, x, z, r=BODY_R):
        if self.pig_at is not None:
            dx, dz = x - self.pig_at[0], z - self.pig_at[1]
            if dx * dx + dz * dz < (r + 0.45) ** 2:
                return True
        for b in self.boxes:
            if _hit(x, z, r, b):
                return True
        for m in self.meshes + self.dyn:
            if m.body_hits(x, z, r, 0.0, BODY_TOP):
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
        for m in self.meshes + (self.dyn if dyn else []):
            if _mesh_sight(m, a, b):
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
        if self.pig_at is not None:
            px, pz = self.pig_at
            h = _ray_box(o, d, (px - 0.4, pz - 0.4, px + 0.4, pz + 0.4, 0.55))
            if h is not None and h < best:
                best = h
        for b in self.boxes:
            h = _ray_box(o, d, b)
            if h is not None and h < best:
                best = h
        for m in self.meshes + self.dyn:
            h = m.ray(o, d, best)
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
        # x, base y, size, wall face z: the door (x 10.5-15.5) stands 0.08 m
        # proud of the wall at z=7.0, so flames in the doorway sit on it.
        sources = (
            (9.8,  1.0, 0.75, 7.0),
            (11.0, 0.1, 0.90, 6.92),
            (13.0, 0.1, 1.05, 6.92),
            (15.0, 0.1, 0.85, 6.92),
            (16.2, 1.0, 0.70, 7.0),
            (13.0, 4.5, 0.75, 7.0),  # hayloft opening
        )
        for n, (x, y, size, wall_z) in enumerate(sources):
            F.wall_fire(
                r, x, y, wall_z, t, seed=40 + n * 3,
                size=size * (0.45 + 0.55 * g),
                smoky=n % 3 == 0, layer=2)

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


_ROWS = {}


def put(r, mesh, x, y, z, yaw_deg):
    """``_w.add(r, placed(...))`` without the per-frame copy and re-pack.

    The truck and the dog frames are thousands of faces; copying them through
    ``Mesh.add`` and packing them in Python cost ~20 ms each per frame.  GL packs
    each mesh once and only turns and moves the packed rows; the software
    backend still places a copy."""
    if not hasattr(r, "add_packed"):
        _w.add(r, placed(mesh, x, y, z, yaw_deg))
        return
    import numpy as np
    ent = _ROWS.get(id(mesh))
    if ent is None or ent[0] is not mesh:
        faces = [(f[0], f[1], f[2], f[3], None, f[4]) for f in mesh.faces]
        ent = _ROWS[id(mesh)] = [mesh, r.pack(mesh.verts, faces), None, None]
    rows = ent[1]
    if rows is None:
        return
    if ent[2] != yaw_deg:       # the trucks never turn: keep the turned rows
        rt = np.array(rot_y(yaw_deg - 90.0), dtype=np.float32).reshape(3, 3).T
        turned = rows.copy()
        np.matmul(rows[:, 0:3], rt, out=turned[:, 0:3])
        np.matmul(rows[:, 6:9], rt, out=turned[:, 6:9])
        ent[2], ent[3] = yaw_deg, turned
    out = ent[3].copy()
    out[:, 0] += x
    out[:, 1] += y
    out[:, 2] += z
    r.add_packed(out)


G = 9.8


class WellWreck:
    """The well's roof frame coming down on Alex.

    Upright until ``topple``; then a body hinged on the south wall that gravity
    swings over (angle ``th`` from upright), bouncing where the beam lands across
    Alex.  The tin roof tears off when it touches the ground and goes on as a free
    rigid sheet (six Verlet points held by all their pair lengths); the bucket
    swings on its rope from the beam.  ``update`` takes ``lift`` 0..1 while Biribel
    heaves the beam, None otherwise.  Impacts land in ``events`` for the sound."""

    STEP = 1.0 / 240.0
    SWING = 7.0                 # g over the frame's pendulum length, 1/s^2
    KICK = 1.3                  # rad/s it starts toppling with
    REST = math.radians(WELL_DOWN)
    ROPE = 1.0

    def __init__(self):
        self.th = 0.0
        self.om = 0.0
        self.live = False
        self.landed = False
        self.tin = None
        self.bob = None
        self.events = []
        self._acc = 0.0
        self._tin_down = False
        self._frame = None

    def topple(self):
        if not self.live:
            self.live, self.om = True, self.KICK

    def at(self, v, th=None):
        """World position of a point given in the well's frame, tipped ``th``."""
        m = rot_x(-math.degrees(self.th if th is None else th))
        q = m_apply(m, (v[0] - WELL_HINGE[0], v[1] - WELL_HINGE[1], v[2] - WELL_HINGE[2]))
        return (WELL_AT[0] + WELL_HINGE[0] + q[0], WELL_HINGE[1] + q[1],
                WELL_AT[1] + WELL_HINGE[2] + q[2])

    def boxes(self):
        """Blocking boxes of the frame lying across Alex: two posts and the beam."""
        bz = self.at((0.0, 2.3, 0.0), self.REST)[2]
        hz = WELL_AT[1] - 0.85
        x0 = WELL_AT[0]
        return [(x0 - 0.84, bz - 0.1, x0 - 0.72, hz, 0.5), (x0 + 0.72, bz - 0.1, x0 + 0.84, hz, 0.5),
                (x0 - 0.9, bz - 0.1, x0 + 0.9, bz + 0.1, 0.7)]

    def update(self, dt, lift=None):
        if not self.live:
            return
        self._acc = min(self._acc + dt, 0.1)
        while self._acc >= self.STEP:
            self._acc -= self.STEP
            self._step(self.STEP, lift)

    def _step(self, h, lift):
        th0 = self.th
        if lift is not None and self.landed:
            tgt = self.REST - math.radians(24.0) * lift
            acc = 90.0 * (tgt - self.th) - 16.0 * self.om
        else:
            acc = self.SWING * math.sin(self.th)
        self.om += acc * h
        self.th += self.om * h
        if self.tin is None and min(self.at(v)[1] for v in _TIN_PTS) < 0.02:
            self._tear(th0)
        if self.th >= self.REST:
            if self.tin is None:
                self._tear(th0)
            self.th = self.REST
            if self.om > 0.8:
                self.events.append(("frame", self.om))
                self.om *= -0.28
            else:
                self.om = 0.0
            self.landed = True
        self._step_tin(h)
        self._step_bob(h)

    def _tear(self, th0):
        """Free the tin: its points now, and a step back for their velocity,
        with a little sideways drift and roll so it does not land square."""
        self.tin = []
        for v in _TIN_PTS:
            p, q = self.at(v), self.at(v, th0)
            self.tin.append([p, (q[0] + 0.5 * self.STEP, q[1] - 0.4 * self.STEP * v[0], q[2])])

    def _step_tin(self, h):
        if self.tin is None:
            return
        g = G * h * h
        for pt in self.tin:
            p, q = pt
            pt[0], pt[1] = (2 * p[0] - q[0], 2 * p[1] - q[1] - g, 2 * p[2] - q[2]), p
        for _ in range(3):
            for i, j, d in _TIN_LINKS:
                a, b = self.tin[i][0], self.tin[j][0]
                dx, dy, dz = b[0] - a[0], b[1] - a[1], b[2] - a[2]
                ln = math.sqrt(dx * dx + dy * dy + dz * dz) or 1e-6
                k = (ln - d) / ln * 0.5
                self.tin[i][0] = (a[0] + dx * k, a[1] + dy * k, a[2] + dz * k)
                self.tin[j][0] = (b[0] - dx * k, b[1] - dy * k, b[2] - dz * k)
        hit = 0.0
        for pt in self.tin:
            p, q = pt
            if p[1] < 0.0:
                vy = (p[1] - q[1]) / h
                hit = max(hit, -vy)
                # bounce a little, scrape along the dirt
                pt[0] = (p[0], 0.0, p[2])
                pt[1] = (p[0] - (p[0] - q[0]) * 0.55, -0.25 * (p[1] - q[1]), p[2] - (p[2] - q[2]) * 0.55)
        if hit > 1.5 and not self._tin_down:
            self.events.append(("tin", hit))
        self._tin_down = hit > 0.0

    def _step_bob(self, h):
        top = self.at((0.0, 2.3, 0.0))
        if self.bob is None:
            b = (top[0], top[1] - self.ROPE, top[2])
            self.bob = [b, b]
        p, q = self.bob
        n = (p[0] + (p[0] - q[0]) * 0.998, p[1] + (p[1] - q[1]) * 0.998 - G * h * h,
             p[2] + (p[2] - q[2]) * 0.998)
        dx, dy, dz = n[0] - top[0], n[1] - top[1], n[2] - top[2]
        ln = math.sqrt(dx * dx + dy * dy + dz * dz) or 1e-6
        if ln > self.ROPE:
            k = self.ROPE / ln
            n = (top[0] + dx * k, top[1] + dy * k, top[2] + dz * k)
        if n[1] < 0.11:
            n = (n[0], 0.11, n[2])
            p = (n[0] - (n[0] - p[0]) * 0.6, 0.11, n[2] - (n[2] - p[2]) * 0.6)
        self.bob = [n, p]

    def draw(self, r):
        if self._frame is None:
            m = Mesh()
            m.add(F.well_frame(), t=(-WELL_HINGE[0], -WELL_HINGE[1], -WELL_HINGE[2]))
            self._frame = m
            _COL.update(tin=F._t("tin", F.ROOF_METAL))
        w = Mesh()
        w.add(self._frame, rot_x(-math.degrees(self.th)),
              t=(WELL_AT[0] + WELL_HINGE[0], WELL_HINGE[1], WELL_AT[1] + WELL_HINGE[2]))
        pts = [pt[0] for pt in self.tin] if self.tin else [self.at(v) for v in _TIN_PTS]
        for quad in _TIN_QUADS:
            w.face([pts[i] for i in quad], _COL["tin"], 2, True)
        top = self.at((0.0, 2.3, 0.0))
        bob = self.bob[0] if self.bob else (top[0], top[1] - self.ROPE, top[2])
        w.face([(top[0] - 0.012, top[1], top[2]), (top[0] + 0.012, top[1], top[2]),
                (bob[0] + 0.012, bob[1] + 0.11, bob[2]), (bob[0] - 0.012, bob[1] + 0.11, bob[2])],
               F.WOOD_D, 2, True)
        w.add(F.well_bucket(), t=bob)
        _w.add(r, w)


_COL = {}
_TIN_PTS = ((-1, 2.3, -0.7), (1, 2.3, -0.7), (1, 2.8, 0), (-1, 2.8, 0), (-1, 2.3, 0.7), (1, 2.3, 0.7))
_TIN_QUADS = ((0, 1, 2, 3), (4, 5, 2, 3))
_TIN_LINKS = tuple((i, j, math.dist(_TIN_PTS[i], _TIN_PTS[j]))
                   for i in range(6) for j in range(i + 1, 6))


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