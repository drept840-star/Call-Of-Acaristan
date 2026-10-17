"""Low-poly trailer props built from engine3d boxes/prisms (y up, metres)."""
import math
import random

from engine3d import Mesh, box, m_apply, m_mul, prism, quad_xz, rot_x, rot_y, rot_z


def rbox(w, h, d, col, c, rx=0.0, ry=0.0, rz=0.0, emissive=False, cols=None):
    m = Mesh()
    m.add(box(w, h, d, col, emissive=emissive, cols=cols), m=m_mul(rot_y(ry), m_mul(rot_x(rx), rot_z(rz))), t=c)
    return m


def merge(*ms):
    out = Mesh()
    for m in ms:
        out.add(m)
    return out


def transformed(mesh, m, t):
    return Mesh().add(mesh, m=m, t=t)


def dyn_faces(mesh, m=None, t=(0.0, 0.0, 0.0), layer=None):
    """Mesh -> (world verts, faces) for Renderer.add_dynamic."""
    if m is None:
        verts = [(x + t[0], y + t[1], z + t[2]) for x, y, z in mesh.verts]
    else:
        verts = []
        for v in mesh.verts:
            q = m_apply(m, v)
            verts.append((q[0] + t[0], q[1] + t[1], q[2] + t[2]))
    faces = [(idx, col, ly if layer is None else layer, ds, None, em) for idx, col, ly, ds, em in mesh.faces]
    return verts, faces


# ── ocean ───────────────────────────────────────────────────────────────
class Ocean:
    """Faceted animated water grid (dynamic mesh)."""
    def __init__(self, x0=-160, x1=160, z0=-10, z1=330, nx=36, nz=38, col=(18, 30, 44)):
        self.xs = [x0 + (x1 - x0) * i / nx for i in range(nx + 1)]
        self.zs = [z0 + (z1 - z0) * (j / nz) ** 1.6 for j in range(nz + 1)]
        self.col = col
        rng = random.Random(4)
        self.var = [[rng.uniform(0.85, 1.12) for _ in range(nx)] for _ in range(nz)]

    def faces(self, t, amp=0.55):
        verts = []
        nx = len(self.xs)
        for z in self.zs:
            for x in self.xs:
                y = (amp * math.sin(x * 0.11 + t * 0.9 + z * 0.05) + amp * 0.6 * math.sin(z * 0.17 - t * 1.3)
                     + amp * 0.3 * math.sin((x + z) * 0.31 + t * 2.1))
                verts.append((x, y, z))
        faces = []
        for j in range(len(self.zs) - 1):
            for i in range(nx - 1):
                a = j * nx + i
                k = self.var[j][i]
                c = tuple(int(v * k) for v in self.col)
                faces.append(((a, a + nx, a + nx + 1), c, 0, False, None, False))
                faces.append(((a, a + nx + 1, a + 1), c, 0, False, None, False))
        return verts, faces


def oil_platform(seed=1, flare=True):
    """-> (mesh, flare_tip, light_points)"""
    rng = random.Random(seed)
    steel, rust, dark = (58, 54, 50), (72, 52, 40), (30, 30, 32)
    parts = []
    for sx in (-9, 9):
        for sz in (-7, 7):
            parts.append(box(1.6, 22, 1.6, steel, center=(sx, 6, sz)))
    parts.append(box(23, 0.6, 17, steel, center=(0, 12.3, 0)))
    parts.append(box(24, 2.2, 18, dark, center=(0, 14, 0)))
    parts.append(box(22, 0.4, 16, rust, center=(0, 16.2, 0)))
    for i in range(4):
        parts.append(rbox(0.5, 15, 0.5, steel, (-9 + 18 * (i % 2), 6, 0), rx=48 * (1 if i < 2 else -1)))
    lights = []
    for _ in range(5):
        w, h, d = rng.uniform(3, 7), rng.uniform(2.5, 6), rng.uniform(3, 7)
        x, z = rng.uniform(-7, 7), rng.uniform(-5, 5)
        parts.append(box(w, h, d, rust if rng.random() < .5 else steel, center=(x, 16.4 + h / 2, z)))
        lights.append((x + w / 2 + 0.05, 16.8 + rng.uniform(0.5, h - 0.5), z))
    # derrick: tapered lattice tower
    for k in range(6):
        y = 18 + k * 4.2
        s = 4.2 - k * 0.55
        for sx in (-1, 1):
            for sz in (-1, 1):
                parts.append(box(0.4, 4.3, 0.4, steel, center=(sx * s / 2, y + 2.1, sz * s / 2)))
        parts.append(box(s + 0.4, 0.3, s + 0.4, steel, center=(0, y + 4.2, 0)))
    parts.append(box(1.2, 2, 1.2, rust, center=(0, 44, 0)))
    lights.append((0, 45.4, 0))
    # crane
    parts.append(box(1.4, 6, 1.4, rust, center=(8, 19, 6)))
    parts.append(rbox(0.7, 0.7, 18, rust, (8, 23, -1.5), rx=-14))
    tip = None
    if flare:
        parts.append(rbox(0.9, 0.9, 26, steel, (-14, 22, -2), ry=-70, rx=-22))
        a = math.radians(-70)
        L = 13
        el = math.radians(22)
        tip = (-14 + math.sin(a) * L * math.cos(el), 22 + L * math.sin(el) + 0.6,
               -2 + math.cos(a) * L * math.cos(el))
    for x, y, z in lights:
        parts.append(box(0.5, 0.5, 0.5, (255, 214, 140), center=(x, y, z), emissive=True))
    return merge(*parts), tip, lights


# ── Route 12 ────────────────────────────────────────────────────────────
def road(z0=-40, z1=160, w=8.0):
    asph = (34, 34, 36)
    m = Mesh()
    m.add(quad_xz(-w / 2, z0, w / 2, z1, 0.0, asph, seg=8,
                  colfn=lambda i, j: (34, 34, 36) if (i * 7 + j * 3) % 5 else (40, 39, 40)))
    m.add(quad_xz(-w / 2 - 14, z0, -w / 2, z1, -0.05, (40, 36, 30), seg=10,
                  colfn=lambda i, j: (40, 36, 30) if (i + j) % 3 else (46, 41, 33)))
    m.add(quad_xz(w / 2, z0, w / 2 + 14, z1, -0.05, (40, 36, 30), seg=10,
                  colfn=lambda i, j: (40, 36, 30) if (i + j) % 3 else (46, 41, 33)))
    z = z0
    while z < z1:
        m.add(box(0.14, 0.01, 2.2, (178, 150, 60), center=(0, 0.005, z)))
        z += 5.0
    for sx in (-1, 1):
        for zz in range(int(z0), int(z1), 4):
            m.add(box(0.12, 0.7, 0.12, (90, 92, 96), center=(sx * (w / 2 + 0.6), 0.35, zz)))
        m.add(box(0.06, 0.25, z1 - z0, (120, 124, 130), center=(sx * (w / 2 + 0.6), 0.62, (z0 + z1) / 2)))
    return m


def burnt_van():
    char, ash, rim = (24, 22, 21), (44, 40, 37), (60, 50, 44)
    return merge(
        box(2.1, 1.7, 5.0, char, center=(0, 1.35, 0), cols={"top": ash}),
        box(2.0, 0.9, 1.4, ash, center=(0, 1.0, 2.9)),
        box(1.6, 0.7, 0.05, (10, 10, 12), center=(0, 1.75, 3.52)),
        box(2.12, 0.18, 5.0, rim, center=(0, 0.55, 0)),
        *[box(0.3, 0.7, 0.7, (14, 14, 14), center=(sx * 1.0, 0.35, sz)) for sx in (-1, 1) for sz in (-1.6, 1.8)],
    )


def streetlamp(h=7.5):
    pole = (60, 62, 66)
    return merge(box(0.18, h, 0.18, pole, center=(0, h / 2, 0)),
                 box(1.8, 0.14, 0.18, pole, center=(0.8, h, 0)),
                 box(0.6, 0.16, 0.34, (255, 170, 70), center=(1.5, h - 0.12, 0), emissive=True)), (1.5, h - 0.3, 0)


def construction_site():
    conc, steel = (88, 86, 82), (120, 70, 30)
    parts = [box(14, 0.4, 10, conc, center=(0, 0.2, 0))]
    for lvl in range(3):
        y = 0.4 + lvl * 3.2
        for sx in (-6, -2, 2, 6):
            for sz in (-4, 4):
                parts.append(box(0.5, 3.2, 0.5, conc, center=(sx, y + 1.6, sz)))
        parts.append(box(14, 0.3, 10, conc, center=(0, y + 3.2, 0)))
    parts.append(box(0.8, 26, 0.8, steel, center=(10, 13, 2)))
    parts.append(box(22, 0.8, 0.8, steel, center=(4, 26, 2)))
    parts.append(box(0.06, 8, 0.06, (40, 40, 40), center=(-4, 22, 2)))
    return merge(*parts)


# ── capital ─────────────────────────────────────────────────────────────
def apartment_block(w, h, d, seed, facing=1, lit=0.35, col=(56, 56, 60), axis="x"):
    """Block centred at origin, ground at y=0. Windows on the +/-x face
    (axis="x", facing=+1/-1) or on the +/-z face (axis="z")."""
    rng = random.Random(seed)
    parts = [box(w, h, d, col, center=(0, h / 2, 0))]
    span = d if axis == "x" else w
    rows = int(h / 3.0)
    cols = int(span / 3.0)
    for r_ in range(rows):
        for c_ in range(cols):
            u = -span / 2 + 1.5 + c_ * 3.0
            y = 1.8 + r_ * 3.0
            on = rng.random() < lit
            col_w = rng.choice([(214, 178, 110), (196, 168, 120), (150, 170, 190), (230, 200, 140)]) if on else (22, 25, 30)
            if axis == "x":
                parts.append(box(0.06, 1.3, 1.3, col_w, center=(facing * (w / 2 + 0.03), y, u), emissive=on))
            else:
                parts.append(box(1.3, 1.3, 0.06, col_w, center=(u, y, facing * (d / 2 + 0.03)), emissive=on))
    return merge(*parts)


def tank(col=(58, 62, 54)):
    dark = (26, 27, 26)
    hull = prism([(-1.6, 0.5), (1.6, 0.5), (1.6, 1.5), (-1.6, 1.5)], 6.2, col, z0=-3.1)
    m = merge(
        hull,
        rbox(3.2, 0.5, 1.4, col, (0, 1.2, 3.35), rx=-30),
        box(0.8, 1.05, 6.6, dark, center=(-1.75, 0.6, 0)),
        box(0.8, 1.05, 6.6, dark, center=(1.75, 0.6, 0)),
        box(2.3, 0.75, 2.8, col, center=(0, 1.9, -0.3)),
        box(1.2, 0.3, 1.0, col, center=(0.5, 2.4, -0.6)),
        box(0.22, 0.22, 4.4, dark, center=(0, 1.95, 3.2)),
        box(0.34, 0.34, 0.5, dark, center=(0, 1.95, 1.3)),
        box(0.3, 0.2, 0.1, (255, 236, 190), center=(-1.2, 1.25, 3.13), emissive=True),
        box(0.3, 0.2, 0.1, (255, 236, 190), center=(1.2, 1.25, 3.13), emissive=True),
    )
    return m, [(-1.2, 1.25, 3.25), (1.2, 1.25, 3.25)]


def barrier(length=4.0):
    parts = []
    n = 8
    for i in range(n):
        c = (200, 40, 36) if i % 2 == 0 else (222, 220, 210)
        parts.append(box(length / n, 0.18, 0.18, c, center=(-length / 2 + (i + .5) * length / n, 1.0, 0)))
    parts.append(box(0.3, 1.1, 0.3, (60, 60, 64), center=(-length / 2, 0.55, 0)))
    parts.append(box(0.3, 1.1, 0.3, (60, 60, 64), center=(length / 2, 0.55, 0)))
    return merge(*parts)


def sandbags(n=5):
    parts = []
    for i in range(n):
        for row in range(2):
            parts.append(box(0.7, 0.3, 0.45, (92, 84, 64) if (i + row) % 2 else (84, 76, 58),
                             center=(i * 0.68 + row * 0.34, 0.15 + row * 0.3, 0)))
    return merge(*parts)


def skyline(seed, x0=-120, x1=120, z=160, lit=0.25, hmin=12, hmax=55):
    """Row of blocks along x at depth z, windows facing -z (toward the camera)."""
    rng = random.Random(seed)
    parts = []
    x = x0
    while x < x1:
        w = rng.uniform(8, 18)
        h = rng.uniform(hmin, hmax)
        d = rng.uniform(8, 16)
        blk = apartment_block(w, h, d, rng.randrange(9999), facing=-1, lit=lit, col=(40, 41, 46), axis="z")
        parts.append(transformed(blk, rot_y(0), (x + w / 2, 0, z + rng.uniform(-10, 20))))
        x += w + rng.uniform(1, 6)
    return merge(*parts)


# ── train ───────────────────────────────────────────────────────────────
def train_car(length=16.0, seats=True):
    wall, panel, floor, seat = (70, 76, 70), (52, 58, 54), (40, 38, 36), (58, 82, 70)
    hw = 1.45
    parts = [quad_xz(-hw, -length / 2, hw, length / 2, 0.0, floor, seg=2,
                     colfn=lambda i, j: floor if (i + j) % 2 else (46, 43, 40))]
    parts.append(box(2 * hw + 0.4, 0.1, length, (86, 90, 84), center=(0, 2.45, 0)))
    for sx in (-1, 1):
        x = sx * (hw + 0.05)
        parts.append(box(0.1, 0.95, length, panel, center=(x, 0.475, 0)))
        parts.append(box(0.1, 0.55, length, wall, center=(x, 2.15, 0)))
        z = -length / 2
        while z < length / 2:
            parts.append(box(0.12, 0.95, 0.4, wall, center=(x, 1.42, z)))
            z += 2.0
    for zz in (range(-6, 8, 2) if seats else ()):
        for sx in (-1, 1):
            parts.append(box(1.0, 0.45, 0.55, seat, center=(sx * 0.85, 0.42, zz)))
            parts.append(box(1.0, 0.75, 0.14, seat, center=(sx * 0.85, 1.0, zz - 0.3 if zz % 4 else zz + 0.3)))
    parts.append(box(0.06, 0.04, length, (240, 246, 230), center=(0, 2.39, 0), emissive=True))
    return merge(*parts)


# ── hangar + gunship ────────────────────────────────────────────────────
def hangar():
    conc, wall, truss = (62, 63, 66), (44, 46, 50), (70, 72, 76)
    parts = [quad_xz(-22, -18, 22, 26, 0.0, conc, seg=4,
                     colfn=lambda i, j: conc if (i + j) % 2 else (58, 59, 62))]
    for sx in (-1, 1):
        parts.append(box(0.5, 14, 44, wall, center=(sx * 22, 7, 4)))
    parts.append(box(44, 14, 0.5, wall, center=(0, 7, 26)))
    parts.append(box(44, 0.5, 44, (30, 31, 34), center=(0, 14, 4)))
    for z in range(-14, 26, 6):
        parts.append(box(44, 0.5, 0.4, truss, center=(0, 13.2, z)))
    for x in range(-16, 18, 8):
        parts.append(box(6, 0.12, 0.6, (240, 240, 226), center=(x, 13.0, 4), emissive=True))
    # yellow floor markings
    for z in range(-10, 20, 3):
        parts.append(box(0.25, 0.01, 1.6, (180, 150, 40), center=(-7, 0.01, z)))
        parts.append(box(0.25, 0.01, 1.6, (180, 150, 40), center=(7, 0.01, z)))
    return merge(*parts)


def gunship_body(col=(30, 31, 35)):
    red = (150, 30, 30)
    glass = (40, 66, 76)
    m = merge(
        box(1.7, 1.6, 4.4, col, center=(0, 1.75, 0)),
        prism([(-0.85, 0.95), (0.85, 0.95), (0.6, 2.2), (-0.6, 2.2)], 1.6, col, z0=2.2),
        rbox(1.3, 0.9, 1.4, glass, (0, 2.15, 2.85), rx=28, emissive=True),
        box(1.72, 0.12, 4.4, red, center=(0, 1.45, 0)),
        box(0.55, 0.55, 5.6, col, center=(0, 2.2, -4.9)),
        rbox(0.12, 1.6, 1.0, col, (0, 2.9, -7.4), rx=-20),
        box(3.6, 0.12, 0.8, col, center=(0, 1.6, 0.3)),
        box(0.4, 0.4, 1.4, (40, 40, 44), center=(-1.6, 1.35, 0.4)),
        box(0.4, 0.4, 1.4, (40, 40, 44), center=(1.6, 1.35, 0.4)),
        box(0.7, 0.5, 0.9, col, center=(0, 2.75, 0.2)),
        box(0.1, 0.1, 4.2, (50, 50, 54), center=(-0.8, 0.12, 0.3)),
        box(0.1, 0.1, 4.2, (50, 50, 54), center=(0.8, 0.12, 0.3)),
        *[box(0.08, 0.8, 0.08, (50, 50, 54), center=(sx * 0.8, 0.55, sz)) for sx in (-1, 1) for sz in (-1, 1.5)],
        box(0.3, 0.25, 0.3, (30, 30, 30), center=(0, 0.85, 3.2)),
    )
    return m


def rotor_faces(hub, ang, radius=6.0, n=4, col=(22, 22, 24), t=(0, 0, 0), blur=0.0):
    out_v, out_f = [], []
    for i in range(n):
        a = ang + i * 360.0 / n
        blade = box(0.32, 0.05, radius, col, center=(0, 0, radius / 2))
        m = rot_y(a)
        v, f = dyn_faces(blade, m, (hub[0] + t[0], hub[1] + t[1], hub[2] + t[2]))
        base = len(out_v)
        out_v += v
        out_f += [(tuple(k + base for k in idx), c, l, ds, n_, em) for idx, c, l, ds, n_, em in f]
    return out_v, out_f


# ── mansion ─────────────────────────────────────────────────────────────
def mansion_facade(seed=5):
    rng = random.Random(seed)
    stone, trim, roof = (150, 140, 124), (176, 168, 150), (54, 46, 44)
    parts = [box(40, 14, 2, stone, center=(0, 7, 0)), box(42, 1, 3, trim, center=(0, 14.3, 0)),
             prism([(-21, 14.8), (21, 14.8), (0, 19)], 3, roof, z0=-1.5)]
    for x in range(-16, 18, 4):
        for y in (3.5, 9.5):
            if abs(x) < 3 and y < 5:
                continue
            on = rng.random() < 0.6
            parts.append(box(1.6, 2.6, 0.1, (226, 186, 120) if on else (30, 30, 36),
                             center=(x, y, -1.03), emissive=on))
            parts.append(box(2.0, 0.25, 0.3, trim, center=(x, y - 1.45, -1.1)))
    for x in (-3.2, 3.2, -6, 6):
        parts.append(box(0.9, 8, 0.9, trim, center=(x, 4, -2.2)))
    parts.append(box(14, 0.8, 4, trim, center=(0, 8.4, -2.4)))
    parts.append(box(16, 0.5, 6, (120, 112, 100), center=(0, 0.25, -3.5)))
    return merge(*parts)


def door_leaf(col=(60, 36, 24)):
    return merge(box(1.2, 3.0, 0.15, col, center=(0, 1.5, 0)),
                 box(0.12, 0.12, 0.05, (200, 170, 90), center=(0.45, 1.5, -0.1)))


def notebook(open_=False):
    cover, page = (20, 20, 22), (218, 210, 188)
    if not open_:
        return merge(box(0.21, 0.025, 0.29, cover, center=(0, 0.0125, 0)),
                     box(0.2, 0.018, 0.28, page, center=(0.004, 0.012, 0)))
    return merge(box(0.42, 0.012, 0.29, cover, center=(0, 0.006, 0)),
                 box(0.2, 0.01, 0.28, page, center=(-0.105, 0.016, 0)),
                 box(0.2, 0.01, 0.28, page, center=(0.105, 0.016, 0)))
