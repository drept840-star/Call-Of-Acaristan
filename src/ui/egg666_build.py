"""egg666_build.py - geometry for the 3D "666" scare: the vault, the ritual
marks, the hanging lamp and the demon.

Everything is the engine's own boxes (the game's blocky character language,
made wrong) with pixel textures from assets/tex3d and plain colours.  Meshes
are packed once with ``GLRenderer.pack`` and moved per frame with numpy by
``egg666_3d``, so the scare costs one buffer upload, not a Python face loop.
Metres, left-handed: x right, y up, z forward; the demon faces -z (the lens).
"""
import math
import random

import numpy as np

from engine3d.core import Mesh, box, m_apply, m_mul, rot_x, rot_y, rot_z
from engine3d.gl import GLRenderer
from engine3d.rig import cbox
from engine3d.textures import tex

CIRCLE = (0.0, 3.6)            # ritual centre on the floor (x, z)
RING_R = 3.0
ROOT_Y = 1.31                  # pelvis height with both feet on the floor
HALL_X, HALL_Z0, HALL_Z1, HALL_H = 4.0, -2.8, 9.0, 4.4
LAMP_ANCHOR = (1.5, 4.4, 5.4)  # where the cable meets the ceiling
LAMP_LEN = 0.95
EMBER = (214, 40, 18)

_TEX = {}


def tx(name, like, density=None):
    """A tinted pixel texture (one Tex per distinct request)."""
    key = (name, like, density)
    t = _TEX.get(key)
    if t is None:
        t = _TEX[key] = tex(name, like=like, tint=True, density=density)
    return t


def rot(rx=0.0, ry=0.0, rz=0.0):
    """Local rotation, degrees: z first, then x, then y."""
    return m_mul(rot_y(ry), m_mul(rot_x(rx), rot_z(rz)))


def quad(pts, toward, col, layer=2, emissive=True):
    """One flat face wound so that its normal points along ``toward``."""
    a, b, c = pts[0], pts[1], pts[2]
    ux, uy, uz = b[0] - a[0], b[1] - a[1], b[2] - a[2]
    vx, vy, vz = c[0] - a[0], c[1] - a[1], c[2] - a[2]
    n = (uy * vz - uz * vy, uz * vx - ux * vz, ux * vy - uy * vx)
    if n[0] * toward[0] + n[1] * toward[1] + n[2] * toward[2] < 0:
        pts = pts[::-1]
    return Mesh().face(list(pts), col, layer, False, emissive)


# -- the vault ---------------------------------------------------------------
_SIX = (((1, 3),), ((0, 0),), ((0, 0),), ((0, 3),), ((0, 0), (4, 4)),
        ((0, 0), (4, 4)), ((1, 3),))          # a blocky 6, five cells by seven


def glyph_rects():
    """Rectangles (xa, xb, ya, yb) on the back wall: the inverted cross and
    three sixes, to be burned in."""
    rects = [(-0.11, 0.11, 0.35, 2.80), (-0.62, 0.62, 1.10, 1.32)]
    cell = 0.17
    for xc in (-1.5, 0.0, 1.5):
        x0, ytop = xc - 2.5 * cell, 4.15
        for r, runs in enumerate(_SIX):
            for c0, c1 in runs:
                yb = ytop - r * cell
                rects.append((x0 + c0 * cell, x0 + (c1 + 1) * cell, yb - cell, yb))
    return rects


def build_room():
    x, z0, z1, h = HALL_X, HALL_Z0, HALL_Z1, HALL_H
    depth, zc = z1 - z0 + 0.6, (z0 + z1) / 2.0
    floor = tx("concrete", (36, 34, 35))
    ceil = tx("concrete", (22, 22, 25))
    wall = tx("vault", (40, 42, 47))
    post = tx("vault", (30, 32, 36))
    beam = tx("steel", (38, 40, 45))
    plate = tx("scorch", (30, 22, 20), 64)
    steel = tx("steel", (72, 76, 84))
    door = tx("steel", (52, 55, 62))
    char = (20, 13, 11)
    only = lambda keep: tuple(s for s in ("front", "back", "left", "right", "top", "bottom") if s != keep)
    m = Mesh()
    m.add(box(2 * x + 0.6, 0.3, depth, floor, center=(0, -0.15, zc), layer=0, skip=only("top")))
    m.add(box(2 * x + 0.6, 0.3, depth, ceil, center=(0, h + 0.15, zc), skip=only("bottom")))
    m.add(box(0.3, h + 0.3, depth, wall, center=(-x - 0.15, (h + 0.3) / 2, zc), skip=only("right")))
    m.add(box(0.3, h + 0.3, depth, wall, center=(x + 0.15, (h + 0.3) / 2, zc), skip=only("left")))
    m.add(box(2 * x + 0.6, h + 0.3, 0.3, wall, center=(0, (h + 0.3) / 2, z1 + 0.15), skip=only("front")))
    for zp in (1.0, 4.2, 7.4):
        for side in (-1, 1):
            m.add(cbox(0.6, h, 0.55, post, center=(side * (x - 0.28), h / 2, zp), bevel=0.06))
    for zb in (0.2, 3.2, 6.2):
        m.add(box(2 * x, 0.34, 0.42, beam, center=(0, h - 0.17, zb)))
    # the plate the signs are burned into, and the signs' dark relief
    m.add(box(5.8, 3.9, 0.07, plate, center=(0, 2.25, z1 - 0.035), skip=only("front")))
    for xa, xb, ya, yb in glyph_rects():
        m.add(box(xb - xa, yb - ya, 0.05, char, center=((xa + xb) / 2, (ya + yb) / 2, z1 - 0.095),
                  skip=("front", "back")))
    # the safe: body on the left wall, black opening, door swung open
    m.add(cbox(0.9, 1.9, 1.5, steel, center=(-x + 0.45, 0.95, 7.2), bevel=0.04))
    m.add(quad([(-x + 0.905, 0.25, 6.65), (-x + 0.905, 1.65, 6.65), (-x + 0.905, 1.65, 7.75),
                (-x + 0.905, 0.25, 7.75)], (1, 0, 0), (4, 4, 5), 2, False))
    slab = box(0.14, 1.7, 1.24, door, center=(0.0, 0.0, 0.62))
    m.add(slab, m=rot(0.0, 72.0, 0.0), t=(-x + 0.97, 0.95, 6.5))
    return m


def build_marks(seed):
    """The ritual circle, inverted pentagram and rune ticks on the floor plus
    the glowing fronts of the signs on the wall.  -> (Mesh of emissive quads,
    phase per face, gain per face); egg666_3d pulses their colour per frame."""
    rg = random.Random(seed)
    cx, cz = CIRCLE
    m, phase, gain = Mesh(), [], []

    def put(pts, toward, layer, ph, g):
        m.add(quad(pts, toward, EMBER, layer))
        phase.append(ph)
        gain.append(g)

    y = 0.006

    def at(r, a):
        return (cx + r * math.cos(a), y, cz + r * math.sin(a))

    for r_mid, w, n, g in ((RING_R, 0.10, 72, 1.0), (RING_R - 0.30, 0.06, 72, 0.75),
                           (RING_R + 0.42, 0.035, 60, 0.5)):
        for i in range(n):
            if r_mid > RING_R and i % 3 == 2:
                continue                                  # the outer ring is broken
            a0, a1 = 2 * math.pi * i / n, 2 * math.pi * (i + 1) / n
            put([at(r_mid - w / 2, a0), at(r_mid + w / 2, a0), at(r_mid + w / 2, a1), at(r_mid - w / 2, a1)],
                (0, 1, 0), 1, (a0 + a1) / 2, g)
    for i in range(48):                                   # ticks between the rings
        if rg.random() < 0.3:
            continue
        a = 2 * math.pi * i / 48 + 0.03
        d = 0.011
        put([at(RING_R - 0.24, a - d), at(RING_R - 0.06, a - d), at(RING_R - 0.06, a + d), at(RING_R - 0.24, a + d)],
            (0, 1, 0), 1, a, 0.8)
    R = RING_R - 0.42                                     # one point towards the lens: inverted
    pts5 = [(cx + R * math.cos(math.radians(-90 + 72 * k)), cz + R * math.sin(math.radians(-90 + 72 * k)))
            for k in range(5)]
    for ia, ib in ((0, 2), (2, 4), (4, 1), (1, 3), (3, 0)):
        (ax, az), (bx, bz) = pts5[ia], pts5[ib]
        ln = math.hypot(bx - ax, bz - az)
        nx, nz = -(bz - az) / ln * 0.045, (bx - ax) / ln * 0.045
        for j in range(14):
            t0, t1 = j / 14.0, (j + 1) / 14.0
            p0 = (ax + (bx - ax) * t0, az + (bz - az) * t0)
            p1 = (ax + (bx - ax) * t1, az + (bz - az) * t1)
            put([(p0[0] + nx, y, p0[1] + nz), (p0[0] - nx, y, p0[1] - nz),
                 (p1[0] - nx, y, p1[1] - nz), (p1[0] + nx, y, p1[1] + nz)],
                (0, 1, 0), 1, math.atan2((p0[1] + p1[1]) / 2 - cz, (p0[0] + p1[0]) / 2 - cx), 1.0)
    zf = HALL_Z1 - 0.122                                  # just proud of the dark relief
    for xa, xb, ya, yb in glyph_rects():
        put([(xb, ya, zf), (xa, ya, zf), (xa, yb, zf), (xb, yb, zf)], (0, 0, -1), 2,
            0.8 * xa + 0.6 * ya, 0.85)
    return m, np.array(phase, dtype=np.float32), np.array(gain, dtype=np.float32)


def build_lamp():
    """-> (body, bulb) in lamp space: the anchor is the origin, the cable hangs down."""
    body, bulb = Mesh(), Mesh()
    body.add(box(0.016, LAMP_LEN, 0.016, (22, 22, 24), center=(0, -LAMP_LEN / 2, 0)))
    body.add(cbox(0.08, 0.11, 0.08, (34, 34, 38), center=(0, -LAMP_LEN - 0.055, 0), bevel=0.02))
    bulb.add(cbox(0.085, 0.10, 0.085, (255, 238, 190), center=(0, -LAMP_LEN - 0.16, 0), bevel=0.025,
                  emissive=True))
    return body, bulb


# -- the demon ---------------------------------------------------------------
# (name, parent, offset from the parent's joint, pose keys for rx, ry, rz)
_BODY = (
    ("pelvis", None, (0.0, 0.0, 0.0), (None, None, None)),
    ("spine", "pelvis", (0.0, 0.10, 0.0), ("lean_lo", None, "bend")),
    ("chest", "spine", (0.0, 0.46, 0.0), ("lean_hi", "twist", None)),
    ("neck1", "chest", (0.0, 0.50, 0.0), ("n1", None, "nz1")),
    ("neck2", "neck1", (0.0, 0.26, 0.0), ("n2", None, "nz2")),
    ("neck3", "neck2", (0.0, 0.26, 0.0), ("n3", None, "nz3")),
    ("head", "neck3", (0.0, 0.22, 0.0), ("h_rx", "h_ry", "h_rz")),
    ("jaw", "head", (0.0, 0.06, -0.06), ("jaw_rx", None, None)),
    ("uarmL", "chest", (-0.43, 0.42, 0.0), ("aL_rx", None, "aL_rz")),
    ("farmL", "uarmL", (0.0, -0.74, 0.0), ("eL", None, None)),
    ("handL", "farmL", (0.0, -0.78, 0.0), ("wL_rx", None, "wL_rz")),
    ("uarmR", "chest", (0.43, 0.42, 0.0), ("aR_rx", None, "aR_rz")),
    ("farmR", "uarmR", (0.0, -0.74, 0.0), ("eR", None, None)),
    ("handR", "farmR", (0.0, -0.78, 0.0), ("wR_rx", None, "wR_rz")),
    ("thighL", "pelvis", (-0.13, -0.04, 0.0), ("hip", None, None)),
    ("shinL", "thighL", (0.0, -0.62, 0.0), ("knee", None, None)),
    ("footL", "shinL", (0.0, -0.62, 0.0), ("ankle", None, None)),
    ("thighR", "pelvis", (0.13, -0.04, 0.0), ("hip", None, None)),
    ("shinR", "thighR", (0.0, -0.62, 0.0), ("knee", None, None)),
    ("footR", "shinR", (0.0, -0.62, 0.0), ("ankle", None, None)),
)
# Eye sockets in head space: pair 0 is the face, pair 1 the forehead, pair 2
# the cheeks; each eye is its own part so its glow can be dimmed on its own.
EYES = (((-0.072, 0.226, -0.232), 0.020, 0), ((0.080, 0.205, -0.232), 0.020, 0),
        ((-0.060, 0.312, -0.228), 0.014, 1), ((0.088, 0.322, -0.228), 0.014, 1),
        ((-0.100, 0.070, -0.228), 0.012, 2), ((0.110, 0.046, -0.228), 0.012, 2))
PAIR_CENTRE = ((0.004, 0.2155, -0.27), (0.014, 0.317, -0.26), (0.005, 0.058, -0.26))  # head space
PARTS = _BODY + tuple(("eye%d" % i, "head", e[0], (None, None, None)) for i, e in enumerate(EYES))
EYE_FIRST = len(_BODY)                  # part index of eye 0
EYE_PAIRS = tuple(e[2] for e in EYES)


def _horn(col, base, out, length, n, w0, c_out, c_fwd, tilt_z, tilt_x):
    """A tapering chain of boxes curling outward (out=+1 left, -1 right) and forward."""
    m, pos = Mesh(), base
    M = rot(tilt_x, 0.0, tilt_z * out)
    seg = length / n
    for i in range(n):
        w = max(0.022, w0 * (1.0 - 0.82 * i / n))
        m.add(cbox(w, seg * 1.08, w * 0.85, col, center=(0, seg * 0.5, 0), bevel=w * 0.25), m=M, t=pos)
        d = m_apply(M, (0.0, seg, 0.0))
        pos = (pos[0] + d[0], pos[1] + d[1], pos[2] + d[2])
        M = m_mul(M, rot(c_fwd, 0.0, c_out * out))
    return m


def _hand(skin, bone, flip):
    s = -1.0 if flip else 1.0
    m = Mesh()
    m.add(cbox(0.12, 0.17, 0.045, skin, center=(0, -0.085, 0), bevel=0.02))
    for i, (x, splay, ln) in enumerate(((-0.048, 12.0, 0.27), (-0.016, 3.0, 0.31),
                                        (0.016, -4.0, 0.30), (0.048, -14.0, 0.25))):
        R = rot(0.0, 0.0, splay * s)
        o = (x * s, -0.17, 0.0)
        m.add(cbox(0.024, ln * 0.55, 0.026, bone, center=(0, -ln * 0.275, 0), bevel=0.008), m=R, t=o)
        e = m_apply(R, (0.0, -ln * 0.55, 0.0))
        m.add(cbox(0.02, ln * 0.5, 0.022, bone, center=(0, -ln * 0.25, 0), bevel=0.006),
              m=m_mul(R, rot(20.0 + 9.0 * i, 0.0, 0.0)), t=(o[0] + e[0], o[1] + e[1], o[2] + e[2]))
    m.add(cbox(0.026, 0.18, 0.028, bone, center=(0, -0.09, 0), bevel=0.008),
          m=rot(-16.0, 0.0, 50.0 * s), t=(0.05 * s, -0.04, 0.0))
    return m


def build_demon():
    """-> meshes in PARTS order, each in its own joint space (origin at the joint)."""
    SK = tx("scorch", (40, 31, 31), 48)
    SK2 = tx("scorch", (30, 24, 25), 48)
    BN = tx("bone", (176, 166, 148), 64)
    BD = tx("bone", (124, 111, 95), 64)
    BLK, TOOTH = (3, 3, 4), (198, 190, 166)
    M = {}

    def part(name):
        M[name] = Mesh()
        return M[name]

    part("pelvis").add(cbox(0.36, 0.22, 0.22, SK, center=(0, 0.02, 0), bevel=0.04))
    part("spine").add(cbox(0.36, 0.52, 0.22, SK, center=(0, 0.26, 0), bevel=0.05))
    for i in range(4):
        M["spine"].add(box(0.04, 0.04, 0.04, BN, center=(0, 0.08 + 0.12 * i, 0.12)))
    c = part("chest")
    c.add(cbox(0.50, 0.50, 0.28, SK, center=(0, 0.25, 0), bevel=0.06))
    c.add(cbox(0.88, 0.12, 0.24, SK2, center=(0, 0.44, 0), bevel=0.03))
    c.add(box(0.03, 0.34, 0.03, BN, center=(0, 0.25, -0.152)))
    for i in range(4):
        c.add(box(0.40 - 0.03 * i, 0.024, 0.03, BN, center=(0, 0.10 + 0.09 * i, -0.152)))
    for k, w in (("neck1", 0.125), ("neck2", 0.11), ("neck3", 0.10)):
        n = part(k)
        n.add(cbox(w, 0.28, w, SK2, center=(0, 0.14, 0), bevel=0.02))
        n.add(box(0.05, 0.035, 0.05, BN, center=(0, 0.09, w / 2 + 0.012)))
        n.add(box(0.05, 0.035, 0.05, BN, center=(0, 0.20, w / 2 + 0.012)))

    h = part("head")
    h.add(cbox(0.30, 0.36, 0.32, BD, center=(0, 0.18, 0.0), bevel=0.03))
    h.add(cbox(0.25, 0.30, 0.30, BD, center=(0, 0.20, 0.22), bevel=0.03))     # skull too long
    h.add(box(0.28, 0.34, 0.05, BN, center=(0, 0.17, -0.185)))                   # mask plate
    h.add(cbox(0.33, 0.055, 0.09, BD, center=(0, 0.265, -0.20), bevel=0.02))      # brow ridge
    h.add(cbox(0.075, 0.05, 0.08, BN, center=(-0.125, 0.115, -0.195), bevel=0.015))
    h.add(cbox(0.07, 0.056, 0.08, BN, center=(0.128, 0.098, -0.195), bevel=0.015))
    for cx, cy, w, hh in ((-0.072, 0.226, 0.085, 0.066), (0.080, 0.205, 0.098, 0.082),
                          (-0.060, 0.312, 0.050, 0.036), (0.088, 0.322, 0.056, 0.040),
                          (-0.100, 0.070, 0.040, 0.030), (0.110, 0.046, 0.046, 0.034)):
        h.add(box(w, hh, 0.022, BLK, center=(cx, cy, -0.2155)))                  # sockets
    h.add(box(0.012, 0.055, 0.02, BLK, center=(-0.014, 0.125, -0.216)))          # nose slits
    h.add(box(0.012, 0.055, 0.02, BLK, center=(0.016, 0.122, -0.216)))
    h.add(box(0.016, 0.075, 0.03, BN, center=(0.0, 0.14, -0.225)))
    h.add(box(0.008, 0.15, 0.006, BLK, center=(0, 0, 0)), m=rot(0.0, 0.0, 25.0), t=(0.06, 0.26, -0.2125))
    h.add(box(0.008, 0.13, 0.006, BLK, center=(0, 0, 0)), m=rot(0.0, 0.0, -15.0), t=(-0.11, 0.17, -0.2125))
    h.add(cbox(0.22, 0.10, 0.20, BLK, center=(0, 0.01, -0.13), bevel=0.01))        # the dark mouth
    for i, (x, th) in enumerate(((-0.105, 0.05), (-0.07, 0.07), (-0.035, 0.04), (0.0, 0.075),
                                 (0.035, 0.05), (0.07, 0.065), (0.105, 0.04))):
        h.add(box(0.02, th, 0.02, TOOTH, center=(x, 0.02 - th / 2, -0.222)))
    h.add(_horn(BD, (-0.115, 0.33, 0.02), 1, 0.78, 6, 0.10, 13.0, -8.0, 32.0, -6.0))
    h.add(_horn(BD, (0.11, 0.335, 0.0), -1, 0.34, 3, 0.09, -6.0, 5.0, 24.0, 10.0))
    h.add(_horn(BN, (0.15, 0.22, 0.0), -1, 0.30, 3, 0.045, 22.0, -18.0, 70.0, -20.0))

    j = part("jaw")
    j.add(cbox(0.25, 0.07, 0.25, BD, center=(0, -0.02, -0.125), cols={"top": BLK}, bevel=0.02))
    j.add(cbox(0.15, 0.24, 0.10, BD, center=(0, -0.14, -0.225), bevel=0.02))      # hangs too low
    for x, th in ((-0.09, 0.05), (-0.054, 0.07), (-0.018, 0.045), (0.018, 0.08), (0.054, 0.05), (0.09, 0.065)):
        j.add(box(0.02, th, 0.02, TOOTH, center=(x, 0.015 + th / 2, -0.245)))
    for sx in (-0.11, 0.11):
        j.add(box(0.02, 0.05, 0.02, TOOTH, center=(sx, 0.04, -0.17)))

    for side, key in ((-1, "L"), (1, "R")):
        u = part("uarm" + key)
        u.add(cbox(0.13, 0.76, 0.13, SK, center=(0, -0.37, 0), bevel=0.03))
        f = part("farm" + key)
        f.add(cbox(0.10, 0.80, 0.10, SK, center=(0, -0.39, 0), bevel=0.025))
        f.add(cbox(0.04, 0.10, 0.04, BN, center=(0, 0.02, 0.085)))
        part("hand" + key).add(_hand(SK2, BD, side > 0))
        part("thigh" + key).add(cbox(0.17, 0.64, 0.18, SK, center=(0, -0.32, 0), bevel=0.04))
        part("shin" + key).add(cbox(0.13, 0.64, 0.14, SK, center=(0, -0.32, 0), bevel=0.03))
        part("foot" + key).add(cbox(0.14, 0.07, 0.38, SK2, center=(0, -0.035, -0.11), bevel=0.02))

    out = [M[p[0]] for p in _BODY]
    for e in EYES:
        out.append(Mesh().add(cbox(e[1], e[1], e[1], (255, 40, 22), center=(0, 0, 0), bevel=e[1] * 0.2,
                                   emissive=True)))
    return out


def pack_parts(meshes):
    """The whole figure packed once, at rest -> (rows, spans): float32 vertex
    rows and each part's [a, b) row range (so a part moves as one block)."""
    verts, faces, spans, a = [], [], [], 0
    for m in meshes:
        base, n = len(verts), 0
        verts.extend(m.verts)
        for idx, col, layer, ds, em in m.faces:
            faces.append((tuple(i + base for i in idx), col, layer, ds, None, em))
            n += 3 * (len(idx) - 2)
        spans.append((a, a + n))
        a += n
    return GLRenderer.pack(verts, faces), spans


def pack_mesh(m):
    """A static or per-frame-modulated mesh packed once -> float32 rows."""
    faces = [(f[0], f[1], f[2], f[3], None, f[4]) for f in m.faces]
    return GLRenderer.pack(m.verts, faces)
