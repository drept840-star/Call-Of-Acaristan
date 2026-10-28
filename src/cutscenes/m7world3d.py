"""Mission 7 farm: one shared 3D builder for the drop-off and finale films and
the raid scene.  Flat late-PS2 colours, hard edges, blocky forms.

Axes: x east, y up, z north.  Scenes are viewed from -z, so the yard faces the
camera.  Layout (metres, yard centre at the origin):

    house   (-12, 10)   ridge along x, porch on the yard side
    barn    ( 13, 12)   gable end and big doors face -z, hayloft above
    shed    (-11, -9)   fuel shed, tank on a stand
    well    (  1,  4)
    track   x -3..3, runs south from the yard mouth at z -16 to z -90
    orchard x 24..44, z -10..20 (east of the yard)
    field   x -64..-26, z -12..34 (stubble; the helicopter lands here)

Looks: "dawn" (cold mist), "night" (dark), "burn" (night, barn and house burning).
"""
import math

import pygame

from engine3d.core import Light, Mesh, box, prism, quad_xz, rot_y, rot_z
from engine3d.rig import POSES
from engine3d.textures import Tex, tex
from cutscenes import m6fx3d as _fx
from cutscenes import m6world3d as _w
from cutscenes import m7palette3d as P

# Albedos come off the 2D farm (``m7palette3d``); the night is the light's job.
GRASS = P.GRASS
STUBBLE = P.HAY_D
FURROW = P.LOAM
DIRT = P.DIRT
TRACK = P.TRACK
WOOD = P.WOOD_MID
WOOD_D = P.WOOD_D
PLASTER = P.PLASTER
PLASTER_B = (88, 80, 72)        # burnt render (finale)
TILE = P.ROOF
TILE_B = (52, 40, 36)           # burnt tile
BARN = P.BARN
BARN_B = (78, 46, 42)           # burnt boards
TRIM = P.PLASTER
ROOF_METAL = P.GALV_D
STONE = P.STONE
HAY = P.HAY
LEAF = P.GRASS_D
LEAF2 = P.GRASS
TRUNK = P.WOOD_D
WIN = (28, 36, 48)
WIN_LIT = P.WINDOW
EMBER = (255, 120, 40)
TRACT = P.TRACTOR
TRACT_D = P.TRACTOR_D
RUB = P.INK
HUB = P.HAY_MID
METAL = P.GALV_D
RUST = P.RUST
HILL_N = P.HILL_NEAR
HILL_F = P.HILL_FAR
SKYLINE = (22, 26, 32)          # far village and church: a silhouette albedo

# M7 textures (tools/tex3d_draw_m7.py): ground at 16 texels/m, the rest 32.
_GROUND_TEX = ("grass", "stubble", "furrow", "dirt", "track")


def _t(name, col, tint=False):
    """``col`` as the M7 texture ``name``.  Untinted, the texture brings its
    own hue at ``col``'s brightness; ``tint`` keeps ``col`` (painted faces)."""
    return tex("m7_" + name, like=col, tint=tint,
               density=16.0 if name in _GROUND_TEX else 32.0)


# Tractor placement keyed by "burning": parked in the yard, or turned toward the
# barn for the finale (rot_y(-90) faces +z; local forward is +x).
TRACTOR_AT = {False: (-16.0, -3.0), True: (2.0, -3.0)}
TRACTOR_YAW = {False: -90, True: -54}
# World position of the tractor seat in the burning look (Bodi sits here).
SEAT_BURN = (1.62, 1.51, -3.53)

LOOKS = {
    "dawn": dict(
        fog=(196, 178, 166), fog_start=9.0, fog_end=96.0,
        light=dict(direction=(0.72, 0.30, 0.42), ambient=0.50, diffuse=0.62,
                   sky=0.10, tint=(1.0, 0.84, 0.70)),
        sky_top=(92, 116, 152), sky_bot=(234, 186, 150), sodium=(96, 62, 38),
        stars=0),
    "night": dict(
        fog=(10, 13, 20), fog_start=10.0, fog_end=90.0,
        light=dict(direction=(-0.3, 0.7, -0.4), ambient=0.30, diffuse=0.34,
                   sky=0.10, tint=(0.66, 0.74, 1.0)),
        sky_top=(5, 8, 16), sky_bot=(20, 26, 44), sodium=(30, 20, 14),
        stars=60),
    # The raid: a moonlit night lit enough to fight in.  The moon is the key
    # (low in the south-west, behind the trucks' road), so the barn and house
    # fronts catch it and read as silhouettes against a lighter horizon.  The
    # sky's foot IS the fog colour: far geometry fades into the sky it stands
    # against instead of into a seam.  Aerial perspective lives in the far
    # albedos (HILL_N / HILL_F / SKYLINE), not in a short fog.
    "raid": dict(
        fog=(44, 52, 66), fog_start=18.0, fog_end=175.0,
        light=dict(direction=(-0.42, 0.50, -0.72), ambient=0.40, diffuse=0.66,
                   sky=0.12, tint=(0.70, 0.80, 0.98)),
        sky_top=(7, 10, 18), sky_bot=(44, 52, 66), sodium=None,
        stars=90, moon=(-150.0, 15.0)),
    "burn": dict(
        fog=(26, 16, 16), fog_start=8.0, fog_end=96.0,
        light=dict(direction=(-0.3, 0.7, -0.4), ambient=0.30, diffuse=0.32,
                   sky=0.10, tint=(0.70, 0.70, 0.92)),
        sky_top=(8, 8, 16), sky_bot=(58, 28, 24), sodium=(120, 54, 24),
        stars=34),
}


def _v(col, k):
    out = tuple(max(0, min(255, int(c + k))) for c in col)
    return col.with_rgb(out) if isinstance(col, Tex) else out


def _vary(base, amp):
    def f(i, j):
        h = (i * 73856093 ^ j * 19349663) & 0xFF
        return _v(base, (h % 9 - 4) * amp)
    return f


def _gable_z(w, d, y0, rise, roof, wall, oh=0.3, slopes=("l", "r")):
    """Gable roof, ridge along z, width w across x.  Gable-end triangles use
    ``wall``; they sit on the wall planes z = +-d/2."""
    m = Mesh()
    w2, d2 = w / 2.0, d / 2.0
    ex = w2 + oh
    ey = y0 - oh * rise / w2
    zf, zb = -d2 - oh * 0.6, d2 + oh * 0.6
    if "l" in slopes:
        m.face([(-ex, ey, zf), (-ex, ey, zb), (0, y0 + rise, zb), (0, y0 + rise, zf)],
               roof, 2, True)
    if "r" in slopes:
        m.face([(ex, ey, zf), (0, y0 + rise, zf), (0, y0 + rise, zb), (ex, ey, zb)],
               _v(roof, -10), 2, True)
    for z in (-d2, d2):
        m.face([(-w2, y0, z), (w2, y0, z), (0, y0 + rise, z)], wall, 2, True)
    return m


def _bipyr(cx, cy, cz, r, up, dn, col, col2=None, n=6):
    m = Mesh()
    ring = [(cx + r * math.cos(2 * math.pi * i / n),
             cy, cz + r * math.sin(2 * math.pi * i / n)) for i in range(n)]
    top, bot = (cx, cy + up, cz), (cx, cy - dn, cz)
    for i in range(n):
        a, b = ring[i], ring[(i + 1) % n]
        m.face([a, b, top], col, 2, True)
        m.face([b, a, bot], col2 or _v(col, -22), 2, True)
    return m


def _fence(x0, z0, x1, z1, h=1.15, every=2.4, col=None, gap=None):
    """Axis-aligned post-and-rail fence.  ``gap`` = (lo, hi) along the run."""
    m = Mesh()
    col = _t("plank", col or WOOD)
    along_x = abs(z1 - z0) < 1e-6
    length = abs(x1 - x0) if along_x else abs(z1 - z0)
    n = max(1, int(round(length / every)))
    pts = []
    for i in range(n + 1):
        t = i / float(n)
        pts.append((x0 + (x1 - x0) * t, z0 + (z1 - z0) * t))

    def in_gap(p):
        if not gap:
            return False
        v = p[0] if along_x else p[1]
        return gap[0] < v < gap[1]

    for p in pts:
        if not in_gap(p):
            m.add(box(0.14, h, 0.14, col, center=(p[0], h / 2.0, p[1])))
    for a, b in zip(pts[:-1], pts[1:]):
        if in_gap(a) or in_gap(b):
            continue
        cx, cz = (a[0] + b[0]) / 2.0, (a[1] + b[1]) / 2.0
        sx = abs(b[0] - a[0]) or 0.06
        sz = abs(b[1] - a[1]) or 0.06
        for yy in (h * 0.42, h * 0.86):
            m.add(box(sx, 0.07, sz, col, center=(cx, yy, cz)))
    return m


def ground():
    # One flat colour per surface (a per-face tint read as diagonal bands);
    # the pixel textures carry the variation.  Half the field is ploughed.
    return [
        quad_xz(-100, -100, 100, 100, 0.0, _t("grass", GRASS), layer=0, seg=40),
        quad_xz(-46, -12, -26, 34, 0.02, _t("stubble", STUBBLE), layer=1, seg=12),
        quad_xz(-64, -12, -46, 34, 0.02, _t("furrow", P.TRACK_D), layer=1, seg=12),
        quad_xz(-20, -16, 20, 22, 0.02, _t("dirt", DIRT), layer=1, seg=8),
        quad_xz(-3.2, -100, 3.2, -16, 0.04, _t("track", TRACK), layer=1, seg=16),
        quad_xz(-7, -16, 7, -8, 0.04, _t("track", TRACK), layer=1, seg=4),
    ]


HILL_RAD = (84.0, 118.0)


def _hill_h(a, ring=0):
    """Crest height of hill ring ``ring`` at angle ``a`` (x = cos, z = sin)."""
    return (7.0, 14.0)[ring] + 3.5 * math.sin(a * 3 + ring) + 2.2 * math.sin(a * 7 + 1.3 * ring)


def hills():
    m = Mesh()
    n = 60
    for ring, col in enumerate((HILL_N, HILL_F)):
        rad = HILL_RAD[ring]
        pts = []
        for i in range(n + 1):
            a = 2 * math.pi * i / n
            pts.append((rad * math.cos(a), rad * math.sin(a), _hill_h(a, ring)))
        for i in range(n):
            (x0, z0, h0), (x1, z1, h1) = pts[i], pts[i + 1]
            m.face([(x0, -1, z0), (x1, -1, z1), (x1, h1, z1), (x0, h0, z0)],
                   col, 0, True)
    return m


def house(lit=False, burn=False):
    m = Mesh()
    W, D, H = 9.0, 6.0, 3.0
    wall = PLASTER_B if burn else _t("plaster", PLASTER)
    plank = _t("plank", WOOD)
    m.add(box(W, H, D, wall, center=(0, H / 2.0, 0)))
    m.add(box(W + 0.08, 0.42, D + 0.08, _t("stone", P.STONE_D), center=(0, 0.21, 0)))
    roof = _gable_z(D, W, H, 1.9, TILE_B if burn else _t("tile", TILE), wall)
    m.add(roof, rot_y(90))
    m.add(box(0.7, 1.8, 0.7, _t("stone", STONE), center=(2.6, H + 1.2, 0.5)))
    m.add(box(0.86, 0.12, 0.86, P.STONE_D, center=(2.6, H + 2.16, 0.5)))
    zf = -D / 2.0 - 0.04
    shutter = _t("plank", P.TRACTOR_D, tint=True)
    for x in (-3.0, -0.8, 3.6):
        m.add(box(1.25, 1.15, 0.06, TRIM, center=(x, 1.75, zf)))
        m.add(box(0.95, 0.85, 0.08, WIN_LIT if lit else WIN,
                  center=(x, 1.75, zf - 0.02), emissive=lit))
        m.add(box(1.4, 0.08, 0.2, plank, center=(x, 1.13, zf - 0.08)))
        for sx in (-0.76, 0.76):
            m.add(box(0.26, 1.15, 0.05, shutter, center=(x + sx, 1.75, zf - 0.03)))
    m.add(box(1.0, 2.1, 0.08, _t("plank", WOOD_D), center=(1.6, 1.05, zf)))
    # Gutters along both eaves and a downpipe at the west corners.
    for sz in (-1.0, 1.0):
        m.add(box(W + 0.6, 0.12, 0.14, P.GALV_D, center=(0, 2.74, sz * 3.36)))
        m.add(box(0.1, 2.7, 0.1, P.GALV_D, center=(-4.55, 1.37, sz * 3.38)))
    m.add(box(5.0, 0.25, 1.6, plank, center=(1.0, 0.12, -D / 2.0 - 0.8)))
    for x in (-1.3, 3.3):
        m.add(box(0.14, 2.6, 0.14, plank, center=(x, 1.5, -D / 2.0 - 1.5)))
    # porch rail, open at the door steps
    for x0, x1 in ((-1.3, 0.9), (2.3, 3.3)):
        m.add(box(x1 - x0, 0.07, 0.07, plank, center=((x0 + x1) / 2.0, 0.95, -D / 2.0 - 1.5)))
        m.add(box(x1 - x0, 0.07, 0.07, plank, center=((x0 + x1) / 2.0, 0.55, -D / 2.0 - 1.5)))
    m.face([(-1.6, 2.7, -D / 2.0 - 1.7), (3.6, 2.7, -D / 2.0 - 1.7),
            (3.6, 3.1, -D / 2.0), (-1.6, 3.1, -D / 2.0)], _t("tin", ROOF_METAL), 2, True)
    m.add(box(1.4, 0.12, 0.5, plank, center=(1.6, 0.04, -D / 2.0 - 1.85)))
    m.add(box(1.4, 0.42, 0.38, plank, center=(-0.6, 0.45, -D / 2.0 - 0.35)))   # bench
    m.add(box(0.05, 0.3, 0.05, P.STEEL_D, center=(2.0, 2.84, -D / 2.0 - 0.4)))
    if lit:
        m.add(box(0.16, 0.14, 0.16, P.LAMP_WARM, center=(2.0, 2.63, -D / 2.0 - 0.4),
                  emissive=True))
    return m


# World position of the porch bulb and the barn's yard lamp (raid halos).
PORCH_LAMP = (-10.0, 2.63, 6.6)
BARN_LAMP = (9.0, 3.94, 6.37)


def barn(burn=False, lamp=False):
    m = Mesh()
    W, D, H = 12.0, 10.0, 4.8
    side = BARN_B if burn else _t("barnboard", BARN)
    door = _t("plank", WOOD_D)
    m.add(box(W, H, D, side, center=(0, H / 2.0, 0)))
    zf = -D / 2.0 - 0.03
    if burn:
        m.add(box(5.0, 3.6, 0.1, EMBER, center=(0, 1.8, zf), emissive=True))
        m.add(box(1.6, 1.6, 0.1, EMBER, center=(0, H + 1.1, zf), emissive=True))
        m.add(_gable_z(W, D, H, 3.0, TILE_B, side, slopes=()))
    else:
        m.add(box(5.0, 3.6, 0.1, door, center=(0, 1.8, zf)))
        for sx in (-1.25, 1.25):
            for ang in (40, -40):
                brace = Mesh()
                brace.add(box(0.14, 4.1, 0.05, TRIM, center=(0, 0, 0)), rot_z(ang))
                m.add(brace, t=(sx, 1.8, zf - 0.03))
        for x in (-2.6, 2.6):
            m.add(box(0.2, 3.7, 0.12, TRIM, center=(x, 1.85, zf - 0.02)))
        m.add(box(5.4, 0.2, 0.12, TRIM, center=(0, 3.7, zf - 0.02)))
        m.add(box(1.6, 1.6, 0.1, door, center=(0, H + 1.1, zf)))
        m.add(box(1.9, 0.16, 0.12, TRIM, center=(0, H + 1.95, zf - 0.02)))
        m.add(_gable_z(W, D, H, 3.0, _t("tin", P.GALV), side))
        if lamp:
            # Yard lamp on a bracket over the west door leaf: an enamel shade
            # and a bare bulb (its halo and shaft are sprites, ``raid_fx``).
            m.add(box(0.08, 0.08, 0.62, P.STEEL_D, center=(-4.0, 4.12, zf - 0.3)))
            m.add(box(0.52, 0.1, 0.52, P.STEEL_D, center=(-4.0, 4.06, zf - 0.6)))
            m.add(box(0.2, 0.12, 0.2, P.LAMP_WARM, center=(-4.0, 3.95, zf - 0.6),
                      emissive=True))
    return m


def hay(n=3):
    m = Mesh()
    col = _t("hay", HAY)
    for i in range(n):
        m.add(box(1.4, 0.7, 0.9, col, center=((i % 2) * 0.2, 0.35 + 0.7 * (i // 2), 0)))
    return m


def shed():
    m = Mesh()
    m.add(box(3.4, 2.4, 3.0, _t("plank", WOOD), center=(0, 1.2, 0)))
    m.face([(-1.9, 2.3, -1.7), (1.9, 2.3, -1.7), (1.9, 2.9, 1.7), (-1.9, 2.9, 1.7)],
           _t("tin", ROOF_METAL), 2, True)
    m.add(box(1.1, 1.9, 0.08, _t("plank", WOOD_D), center=(0.5, 0.95, -1.54)))
    for sx in (-0.4, 0.4):
        for sz in (-0.4, 0.4):
            m.add(box(0.12, 1.1, 0.12, _t("plank", WOOD_D), center=(3.4 + sx, 0.55, sz)))
    rust = tex("rust", like=RUST, tint=True)
    m.add(box(1.3, 0.8, 1.3, rust, center=(3.4, 1.5, 0)))
    for i in range(3):
        m.add(box(0.5, 0.85, 0.5, _v(rust, 14 * i - 14), center=(-2.5, 0.43, -0.6 + 0.65 * i)))
    return m


def well():
    m = Mesh()
    st = _t("stone", STONE)
    pl = _t("plank", WOOD)
    tin = _t("tin", ROOF_METAL)
    for sz in (-0.65, 0.65):
        m.add(box(1.7, 0.7, 0.35, st, center=(0, 0.35, sz)))
    for sx in (-0.65, 0.65):
        m.add(box(0.35, 0.7, 1.7, st, center=(sx, 0.35, 0)))
    m.add(box(0.9, 0.02, 0.9, (24, 34, 44), center=(0, 0.52, 0)))
    for sx in (-0.78, 0.78):
        m.add(box(0.12, 2.0, 0.12, pl, center=(sx, 1.35, 0)))
    m.add(box(1.8, 0.12, 0.12, pl, center=(0, 2.3, 0)))
    m.face([(-1.0, 2.3, -0.7), (1.0, 2.3, -0.7), (1.0, 2.8, 0), (-1.0, 2.8, 0)], tin, 2, True)
    m.face([(-1.0, 2.3, 0.7), (1.0, 2.3, 0.7), (1.0, 2.8, 0), (-1.0, 2.8, 0)], tin, 2, True)
    m.add(box(0.02, 0.9, 0.02, WOOD_D, center=(0, 1.85, 0)))
    m.add(box(0.24, 0.22, 0.24, WOOD_D, center=(0, 1.3, 0)))
    return m


def tree(seed=0):
    m = Mesh()
    s = 0.9 + 0.2 * ((seed * 37) % 7) / 7.0
    m.add(box(0.26, 1.7, 0.26, _t("bark", TRUNK), center=(0, 0.85, 0)))
    m.add(_bipyr(0, 2.3 * s, 0, 1.35 * s, 1.0 * s, 0.75 * s, _t("leaf", LEAF)))
    m.add(_bipyr(0.1, 3.1 * s, 0.05, 0.9 * s, 0.8 * s, 0.3 * s, _t("leaf", LEAF2)))
    return m


def orchard():
    m = Mesh()
    i = 0
    for x in (26, 31, 36, 41):
        for z in (-8, -2, 4, 10, 16):
            m.add(tree(i), t=(x + ((i * 13) % 5) * 0.2 - 0.4, 0, z + ((i * 7) % 5) * 0.2 - 0.4))
            i += 1
    return m


def tractor(lit=False):
    """Local forward = +x.  Rear wheels at x -0.7, front at +1.0."""
    m = Mesh()

    def wheel(x, z, rad, wid):
        prof = [(rad * math.cos(math.pi / 8 + k * math.pi / 4),
                 rad + rad * math.sin(math.pi / 8 + k * math.pi / 4)) for k in range(8)]
        m.add(prism(prof, wid, RUB, z0=z - wid / 2.0), t=(x, 0, 0))
        hp = [(0.45 * rad * math.cos(math.pi / 8 + k * math.pi / 4),
               rad + 0.45 * rad * math.sin(math.pi / 8 + k * math.pi / 4)) for k in range(8)]
        m.add(prism(hp, wid + 0.05, HUB, z0=z - (wid + 0.05) / 2.0), t=(x, 0, 0))

    for sz in (-0.78, 0.78):
        wheel(-0.7, sz, 0.75, 0.34)
    for sz in (-0.62, 0.62):
        wheel(1.0, sz, 0.42, 0.2)
    m.add(box(2.3, 0.5, 0.75, TRACT_D, center=(0.1, 0.85, 0)))
    m.add(box(1.3, 0.75, 0.7, TRACT, center=(0.85, 1.3, 0)))
    m.add(box(0.06, 0.6, 0.6, METAL, center=(1.52, 1.3, 0)))
    for sz in (-0.82, 0.82):
        m.add(box(1.3, 0.1, 0.5, TRACT_D, center=(-0.7, 1.55, sz)))
    m.add(box(0.5, 0.12, 0.5, RUB, center=(-0.65, 1.45, 0)))
    m.add(box(0.1, 0.5, 0.5, RUB, center=(-0.92, 1.72, 0)))
    m.add(box(0.06, 0.5, 0.06, METAL, center=(0.15, 1.65, 0)))
    m.add(box(0.4, 0.04, 0.4, RUB, center=(0.1, 1.9, 0)))
    m.add(box(0.1, 0.9, 0.1, METAL, center=(1.0, 2.0, 0.22)))
    for sz in (-0.28, 0.28):
        m.add(box(0.08, 0.14, 0.2, WIN_LIT if lit else METAL,
                  center=(1.56, 1.38, sz), emissive=lit))
    return m


def _farm_silo():
    """Small riveted grain silo, deliberately visible above the north field edge."""
    m = Mesh()
    n = 10
    ring = [(1.55 * math.cos(math.tau * i / n),
             1.55 * math.sin(math.tau * i / n)) for i in range(n)]
    for y0, y1, c0, c1 in ((0.0, 0.35, (95, 105, 106), (130, 137, 132)),
                           (0.35, 4.6, (108, 118, 116), (143, 148, 137)),
                           (4.6, 4.95, (86, 98, 99), (118, 124, 118))):
        for i in range(n):
            j = (i + 1) % n
            shade = -8 if i % 2 else 5
            m.face([(ring[i][0], y0, ring[i][1]), (ring[j][0], y0, ring[j][1]),
                    (ring[j][0], y1, ring[j][1]), (ring[i][0], y1, ring[i][1])],
                   _v(c0 if i % 2 else c1, shade), 2, True)
    for i in range(n):
        j = (i + 1) % n
        m.face([(ring[i][0], 4.95, ring[i][1]), (ring[j][0], 4.95, ring[j][1]),
                (0.0, 5.75, 0.0)], (112, 66, 46) if i % 2 else (138, 82, 52), 2, True)
    # Belt seams and the dark loading door make the faceted cylinder read as tin.
    for yy in (0.55, 2.45, 4.45):
        for i in range(n):
            j = (i + 1) % n
            m.face([(ring[i][0] * 1.012, yy, ring[i][1] * 1.012),
                    (ring[j][0] * 1.012, yy, ring[j][1] * 1.012),
                    (ring[j][0] * 1.012, yy + 0.055, ring[j][1] * 1.012),
                    (ring[i][0] * 1.012, yy + 0.055, ring[i][1] * 1.012)],
                   (72, 83, 84), 2, True)
    m.add(box(0.75, 1.55, 0.08, WOOD_D, center=(0.0, 0.78, -1.59)))
    m.add(box(1.9, 0.16, 1.9, METAL, center=(0.0, 0.18, 0.0)))
    return m


def _farm_windpump():
    """An old four-vane windpump silhouette at the field boundary."""
    m = Mesh()
    metal = (106, 111, 101)
    m.add(box(0.22, 6.0, 0.22, metal, center=(0, 3.0, 0)))
    leg_l = box(0.13, 3.3, 0.13, WOOD_D)
    leg_r = box(0.13, 3.3, 0.13, WOOD_D)
    m.add(leg_l, rot_z(-24), t=(-0.72, 1.65, 0))
    m.add(leg_r, rot_z(24), t=(0.72, 1.65, 0))
    m.add(box(2.8, 0.13, 0.12, metal, center=(0, 5.65, -0.15)))
    m.add(box(0.12, 2.8, 0.12, metal, center=(0, 5.65, -0.15)))
    for ang in (45, -45):
        blade = box(2.2, 0.09, 0.10, (142, 145, 128))
        m.add(blade, rot_z(ang), t=(0, 5.65, -0.22))
    m.add(box(0.42, 0.42, 0.30, RUST, center=(0, 5.65, -0.34)))
    # Water trough beneath the pump catches a little of the warm practical light.
    m.add(box(1.5, 0.32, 0.72, WOOD_D, center=(1.2, 0.22, -0.2)))
    m.add(box(1.32, 0.06, 0.54, (42, 68, 70), center=(1.2, 0.39, -0.2)))
    return m


def field_dressing():
    """Baked field edges, believable approaches and working-farm clutter.

    The open gaps line up with the three raid approaches: orchard (east), north
    footpath and the truck lane (south).  The helicopter pad stays unobstructed.
    """
    m = Mesh()
    # Two strong rural silhouettes behind the yard, clearly above the fence line.
    m.add(_farm_silo(), t=(23.5, 0.0, 29.0))
    m.add(_farm_windpump(), t=(-23.5, 0.0, 27.0))
    for i, (x, z) in enumerate(((-62, 29), (-53, 34), (-42, 37), (-32, 32),
                                 (-24, 29), (-70, 14), (-66, -5), (-52, -13),
                                 (-28, 39), (-20, 43), (-18, 31), (-12, 35),
                                 (-6, 33), (7, 35), (14, 32), (20, 39), (28, 43),
                                 (48, 26), (51, 15), (50, -13), (31, -23))):
        m.add(tree(70 + i), t=(x, 0, z))
    # A patchwork of distant pasture and crop strips gives the yard a real
    # agricultural horizon instead of a bare green plane.
    for x0, z0, x1, z1, name, col in (
            (-96, 34, -28, 62, "grass", P.GRASS_DRY), (-24, 34, 18, 68, "stubble", P.HAY_DD),
            (24, 26, 64, 64, "grass", P.GRASS_D), (-78, -48, -24, -20, "furrow", P.TRACK_D),
            (25, -45, 72, -20, "stubble", P.HAY_D)):
        m.add(quad_xz(x0, z0, x1, z1, 0.015, _t(name, col), layer=1, seg=8))
    # Orchard-side field boundary, with an unmistakable guarded approach gate.
    m.add(_fence(23, -15, 23, -4, h=1.05, every=2.5))
    m.add(_fence(23, 4, 23, 22, h=1.05, every=2.5))
    # North footpath boundary; keep the centre lane open for the sweep.
    m.add(_fence(-20, 23, -7, 23, h=1.05, every=2.6))
    m.add(_fence(7, 23, 20, 23, h=1.05, every=2.6))
    # South road has proper verges and gate piers, so trucks visibly enter from
    # beyond the farm rather than appearing out of the fog on an empty strip.
    m.add(_fence(-8.5, -26, -8.5, -18, h=0.95, every=2.5))
    m.add(_fence(8.5, -26, 8.5, -18, h=0.95, every=2.5))
    for gx, gz in ((-8, -26), (8, -26), (-7.2, 23), (7.2, 23), (23, -4), (23, 4)):
        m.add(box(0.52, 1.65, 0.52, _t("stone", STONE), center=(gx, 0.82, gz)))
        m.add(box(0.64, 0.16, 0.64, P.STONE_D, center=(gx, 1.72, gz)))
    # A low, weathered rail and reflector stones make each entrance readable at night.
    m.add(_fence(-6.8, -24.5, 6.8, -24.5, h=1.45, every=3.0, col=P.WOOD_GREY, gap=(-3.4, 3.4)))
    for x, z in ((-4.2, -23.8), (4.2, -23.8), (-5.0, 21.5), (5.0, 21.5),
                 (21.4, -1.8), (21.4, 1.8)):
        m.add(box(0.34, 0.42, 0.34, RUST, center=(x, 0.21, z)))
    m.add(_fence(-68, 27, -29, 27, h=0.95, every=3.0))
    m.add(_fence(-62, -9, -29, -9, h=0.85, every=3.0, gap=(12, 18)))
    for x, z in ((-57, 23), (-53, 24), (-34, 23), (-30, 20), (-60, -4)):
        m.add(hay(2), t=(x, 0, z))
    # An old field cart: bed, side rails and four dark wheels.
    m.add(box(2.8, 0.20, 1.5, _t("plank", WOOD_D), center=(-33, 0.65, 29)))
    for z in (28.25, 29.75):
        m.add(box(2.8, 0.45, 0.08, _t("plank", WOOD), center=(-33, 0.95, z)))
        for x in (-34, -32):
            m.add(box(0.5, 0.6, 0.20, RUB, center=(x, 0.32, z)))
    return m


# Telephone line: up the track's west verge from the valley, then across to a
# yard pole and a service wire into the house gable.  (x, z); tops at POLE_H.
POLES = [(-5.5, -21.0 - 16.0 * i) for i in range(10)][::-1] + [(-18.5, -13.5)]
HOUSE_DROP = (-16.55, 4.2, 10.0)
POLE_H = 7.6


def _pole():
    m = Mesh()
    m.add(box(0.24, POLE_H + 0.2, 0.24, _t("bark", P.WOOD_DARK),
              center=(0, (POLE_H + 0.2) / 2.0, 0)))
    m.add(box(1.6, 0.12, 0.12, _t("plank", P.WOOD_GREY), center=(0, POLE_H - 0.2, 0)))
    for sx in (-0.7, 0.7):
        m.add(box(0.08, 0.16, 0.08, P.GLASS, center=(sx, POLE_H - 0.06, 0)))
    return m


def poles():
    m = Mesh()
    p = _pole()
    for x, z in POLES:
        m.add(p, t=(x, 0.0, z))
    return m


def yard_dressing():
    """Working-farm clutter on the yard edges, clear of the raid's lanes
    (orchard gate east, north footpath, the track mouth) and the films'
    marks.  The solid pieces have matching boxes in ``raid_world.STATIC``."""
    m = Mesh()
    pl = _t("plank", WOOD)
    tin = _t("tin", ROOF_METAL)
    # Woodpile along the house's west gable under a tin lean-to: bark sides,
    # sawn ends (the stone pattern tinted to cut wood) at both ends.
    ends = _t("stone", P.WOOD_L, tint=True)
    m.add(box(1.0, 1.15, 3.6, _t("bark", P.WOOD_DUN), center=(-17.05, 0.575, 10.0),
              cols={"front": ends, "back": ends}))
    m.face([(-17.75, 1.45, 7.9), (-17.75, 1.45, 12.1), (-16.5, 1.85, 12.1),
            (-16.5, 1.85, 7.9)], tin, 2, True)
    for z in (8.0, 12.0):
        m.add(box(0.1, 1.45, 0.1, pl, center=(-17.7, 0.72, z)))
    # Crates stacked by the west fence.
    m.add(box(1.0, 1.0, 1.0, pl, center=(-18.0, 0.5, 3.2)))
    m.add(box(0.9, 0.9, 0.9, _v(pl, -12), center=(-18.05, 0.45, 4.25)))
    m.add(box(0.8, 0.8, 0.8, _v(pl, 8), center=(-17.95, 1.4, 3.3)))
    # Oil drums by the fuel shed: rusted, one in tractor green, one orange.
    for (x, z), col in zip(((-14.4, -12.6), (-13.75, -12.75), (-14.1, -13.3)),
                           (RUST, P.TRACTOR_D, P.GENERATOR)):
        d = tex("rust", like=col, tint=True)
        m.add(box(0.58, 0.9, 0.58, d, center=(x, 0.45, z)))
        for y in (0.3, 0.62):
            m.add(box(0.62, 0.05, 0.62, _v(d, -18), center=(x, y, z)))
    # Stock trough in the south-east corner.
    m.add(box(2.2, 0.55, 0.7, _t("plank", WOOD_D), center=(16.5, 0.275, -9.5)))
    m.add(box(2.0, 0.04, 0.5, P.WATER, center=(16.5, 0.5, -9.5)))
    # A tarped pile (feed sacks, tools) weighted with stones.
    tarp = (52, 74, 96)
    m.add(box(2.4, 0.7, 1.8, pl, center=(14.0, 0.35, -12.8)))
    t = Mesh()
    t.add(_gable_z(1.8, 2.4, 0.7, 0.45, tarp, _v(tarp, -12), oh=0.12), rot_y(90))
    m.add(t, t=(14.0, 0.0, -12.8))
    for x in (13.0, 15.0):
        m.add(box(0.26, 0.18, 0.26, P.STONE_D, center=(x, 0.86, -13.6)))
    return m


_CHURCH_A = math.atan2(96.0, -30.0)


def _village():
    """Far houses round the church: (x, z, base y, lit sides).  On the far
    side of the near hill ring, so their windows show over its crest."""
    out = []
    for i, (da, rad) in enumerate(((-0.20, 97.0), (-0.14, 101.0), (-0.08, 95.0),
                                   (0.07, 99.0), (0.12, 94.0), (0.17, 103.0),
                                   (0.24, 97.0), (0.30, 101.0))):
        a = _CHURCH_A + da
        out.append((rad * math.cos(a), rad * math.sin(a), _hill_h(a) - 0.6,
                    tuple(k for k in range(4) if (i * 5 + k * 3) % 7 < 3)))
    return out


def skyline(lit):
    """A village and its onion-domed church on the northern skyline: dark
    silhouettes with a few lamplit windows, beyond the near hills."""
    m = Mesh()
    roof = (8, 9, 12)
    win = WIN_LIT if lit else SKYLINE
    for x, z, y, sides in _village():
        m.add(box(5.0, 3.2, 4.0, SKYLINE, center=(x, y + 1.6, z)))
        g = Mesh()
        g.add(_gable_z(4.0, 5.0, 3.2, 1.8, roof, SKYLINE), rot_y(90))
        m.add(g, t=(x, y, z))
        for k in sides:
            ox, oz = ((0, -2.04), (2.54, 0), (0, 2.04), (-2.54, 0))[k]
            w, d = (0.7, 0.06) if k % 2 == 0 else (0.06, 0.7)
            m.add(box(w, 0.7, d, win, center=(x + ox, y + 1.9, z + oz), emissive=lit))
    cx, cz = 100.0 * math.cos(_CHURCH_A), 100.0 * math.sin(_CHURCH_A)
    y = _hill_h(_CHURCH_A) - 0.8
    m.add(box(10.0, 6.0, 6.0, SKYLINE, center=(cx, y + 3.0, cz)))
    g = Mesh()
    g.add(_gable_z(6.0, 10.0, 6.0, 2.6, roof, SKYLINE), rot_y(90))
    m.add(g, t=(cx, y, cz))
    tx = cx + 6.4
    m.add(box(3.2, 13.0, 3.2, SKYLINE, center=(tx, y + 6.5, cz)))
    m.add(box(3.6, 0.4, 3.6, roof, center=(tx, y + 13.2, cz)))
    m.add(_bipyr(tx, y + 14.2, cz, 1.9, 2.3, 0.8, roof, SKYLINE, n=8))
    m.add(box(0.2, 2.4, 0.2, roof, center=(tx, y + 17.6, cz)))
    m.add(box(1.0, 0.18, 0.18, roof, center=(tx, y + 18.2, cz)))
    m.add(box(0.5, 1.2, 0.06, win, center=(tx, y + 9.5, cz - 1.63), emissive=lit))
    return m


def mist_ring():
    """Ground mist lying in the valley: two hard-topped bands at the foot of
    the hills, pale against them, stepped like late-PS2 fog cards (no soft
    sprites).  Unlit; the distance fog blends them further."""
    m = Mesh()
    n = 72
    for k, (rad, h0, amp, col) in enumerate(((60.0, 0.9, 0.9, (64, 72, 86)),
                                             (72.0, 1.8, 1.5, (56, 64, 78)))):
        for i in range(n):
            a0, a1 = 2 * math.pi * i / n, 2 * math.pi * (i + 1) / n
            h = h0 + amp * (((i * 7919 + k * 31) % 13) / 12.0)
            x0, z0 = rad * math.cos(a0), rad * math.sin(a0)
            x1, z1 = rad * math.cos(a1), rad * math.sin(a1)
            m.face([(x0, -0.5, z0), (x1, -0.5, z1), (x1, h, z1), (x0, h, z0)],
                   col, 0, True, True)
    return m


def build_static(r, look, park=None):
    """Everything that never moves, added through the static-scene bake.
    ``park`` = (x, z, rot_y degrees) overrides the tractor's default spot."""
    add = _w.add
    for q in ground():
        add(r, q)
    add(r, hills())
    add(r, field_dressing())
    lit = look != "dawn"
    burn = look == "burn"
    add(r, skyline(lit))
    add(r, poles())
    add(r, yard_dressing())
    if look == "raid":
        add(r, mist_ring())
    h = Mesh()
    h.add(house(lit=lit, burn=burn), t=(-12, 0, 10))
    add(r, h)
    b = Mesh()
    b.add(barn(burn=burn, lamp=lit and not burn), t=(13, 0, 12))
    add(r, b)
    s = Mesh()
    s.add(shed(), t=(-11, 0, -9))
    add(r, s)
    w = Mesh()
    w.add(well(), t=(1, 0, 4))
    add(r, w)
    hb = Mesh()
    hb.add(hay(4), t=(5.8, 0, 6.0))
    hb.add(hay(3), t=(6.4, 0, 3.8))
    add(r, hb)
    add(r, orchard())
    f = Mesh()
    f.add(_fence(-20, -16, 20, -16, gap=(-3.4, 3.4)))
    f.add(_fence(-20, -16, -20, 22))
    f.add(_fence(20, -16, 20, 22, gap=(-3, 3)))
    f.add(_fence(-26, -12, -26, 34))
    add(r, f)
    tx, tz, ty = park or (TRACTOR_AT[burn][0], TRACTOR_AT[burn][1], TRACTOR_YAW[burn])
    t = Mesh()
    t.add(tractor(lit=lit), rot_y(ty), t=(tx, 0, tz))
    add(r, t)


def setup(r, look):
    p = LOOKS[look]
    r.fog, r.fog_start, r.fog_end = p["fog"], p["fog_start"], p["fog_end"]
    r.light = Light(**p["light"])


def sky(r, buf, t, look, seed=0):
    p = LOOKS[look]
    if look == "dawn":
        _fx.night_sky(r, buf, t, p["sky_top"], p["sky_bot"], stars=0, moon=False,
                      clouds=0, sodium=p["sodium"], mist=None, seed=seed)
    elif look == "raid":
        # No soft clouds or mist blobs: stars, a hard moon, hard cloud slabs.
        _fx.night_sky(r, buf, t, p["sky_top"], p["sky_bot"], stars=p["stars"], moon=False,
                      clouds=0, sodium=p["sodium"], mist=None, seed=seed)
        _raid_sky(r, buf, t, p["moon"])
    else:
        _w.night(r, buf, t, top=p["sky_top"], bot=p["sky_bot"], stars=p["stars"],
                 moon=False, sodium=p["sodium"], seed=seed)


# Broken cloud over the raid: (azimuth deg, elevation deg, width deg, rows).
# Each slab is a stack of hard rectangles, wider at the base, a pixel-art
# cloud rather than a soft band.  The ones near the moon get a lit top rim.
_CLOUDS = ((-170.0, 9.0, 26.0, 3), (-128.0, 17.0, 18.0, 2), (-96.0, 7.0, 30.0, 3),
           (-40.0, 12.0, 22.0, 2), (10.0, 6.5, 34.0, 3), (64.0, 15.0, 20.0, 2),
           (118.0, 8.0, 28.0, 3), (158.0, 19.0, 16.0, 2))
_CLOUD = (9, 10, 13)            # added to the sky behind: a thin lit veil
_CLOUD_RIM = (34, 36, 40)


def _ring_img(rad, col):
    key = ("m7ring", rad, col)
    img = _SKY_CACHE.get(key)
    if img is None:
        img = pygame.Surface((rad * 2 + 2, rad * 2 + 2))
        img.fill((0, 0, 0))
        pygame.draw.circle(img, col, (rad + 1, rad + 1), rad)
        _SKY_CACHE[key] = img
    return img


_SKY_CACHE = {}


def _raid_sky(r, buf, t, moon):
    w, h = buf.get_size()
    hy = int(r.horizon_y())
    if hy < 4:
        return
    yaw = math.degrees(math.atan2(r.fwd[0], r.fwd[2]))
    px_deg = w / max(1.0, r.fov)

    def at(az, el):
        return (w / 2 + ((az - yaw + 180) % 360 - 180) * px_deg, hy - el * px_deg)

    maz, mel = moon
    mx, my = at(maz, mel)
    rm = int(max(3, px_deg * 0.9))
    if -rm * 8 < mx < w + rm * 8:
        # Two hard halo rings, added, then the disc with a few maria pixels.
        for k, col in ((7, (10, 12, 18)), (4, (16, 19, 28))):
            img = _ring_img(rm * k, col)
            buf.blit(img, (int(mx) - rm * k - 1, int(my) - rm * k - 1),
                     special_flags=pygame.BLEND_ADD)
        pygame.draw.circle(buf, (222, 226, 214), (int(mx), int(my)), rm)
        for dx, dy in ((-0.35, -0.2), (0.15, 0.25), (0.3, -0.35), (-0.1, 0.45)):
            q = max(1, rm // 3)
            pygame.draw.rect(buf, (176, 182, 178),
                             (int(mx + dx * rm), int(my + dy * rm), q, q))
    drift = t * 0.00015
    for i, (az, el, wd, rows) in enumerate(_CLOUDS):
        cx, cy = at(az + drift * (1.0 + 0.2 * i), el)
        cw = wd * px_deg
        if cx + cw < 0 or cx - cw > w:
            continue
        rh = max(2, int(px_deg * 0.7))
        lit = abs(((az - maz + 180) % 360) - 180) < 40
        for k in range(rows):
            ww = int(cw * (1.0 - 0.3 * k))
            x0 = int(cx - ww / 2 + (k * 7 % 5 - 2) * px_deg)
            y0 = int(cy - (k + 1) * rh)
            # Each row splits into two pieces with a ragged gap: broken cloud.
            cut = int(ww * (0.35 + 0.1 * ((i + k) % 3)))
            for a, b in ((x0, x0 + cut - rh), (x0 + cut + rh, x0 + ww)):
                if b - a > 1:
                    buf.fill(_CLOUD, (a, y0, b - a, rh), special_flags=pygame.BLEND_ADD)
                    if lit and k == rows - 1 - (rows > 2):
                        buf.fill(_CLOUD_RIM, (a + 1, y0, b - a - 2, 1),
                                 special_flags=pygame.BLEND_ADD)


# The raid's practicals: barn yard lamp, porch bulb, and the house windows
# (front face, world coords).  Chimney smoke rises from the stone stack.
HOUSE_WINDOWS = ((-15.0, 1.75, 6.88), (-12.8, 1.75, 6.88), (-8.4, 1.75, 6.88))
CHIMNEY_TOP = (-9.4, 5.2, 10.5)


def raid_fx(r, t, lit=True):
    """Per-frame dressing for the raid look: hard halos, the barn lamp's shaft,
    chimney smoke, far village lights and the wires."""
    if lit:
        x, y, z = BARN_LAMP
        r.add_sprite((x, y - 0.1, z), _fx.glow(P.LAMP_WARM, 2.4, t, flicker=0.04, seed=3,
                                               core=(255, 240, 214), intensity=0.9),
                     layer=_fx.FX_LAYER)
        r.add_sprite((x, y - 0.2, z - 0.1), _fx.light_shaft(P.LAMP_WARM, 3.6, 0.5, 2.6, t,
                                                            seed=3, intensity=0.22,
                                                            tilt=0.03),
                     layer=_fx.FX_LAYER)
        r.add_sprite(PORCH_LAMP, _fx.glow(P.LAMP_WARM, 1.6, t, flicker=0.05, seed=5,
                                          core=(255, 240, 214), intensity=0.8),
                     layer=_fx.FX_LAYER)
        for i, pos in enumerate(HOUSE_WINDOWS):
            r.add_sprite((pos[0], pos[1], pos[2] - 0.05),
                         _fx.window_glow(P.WINDOW, 0.9, 0.85, intensity=0.42, t=t,
                                         flicker=0.03, seed=11 + i, rim=True),
                         layer=_fx.FX_LAYER)
        for i, (vx, vz, vy, sides) in enumerate(_village()):
            if sides:
                r.add_sprite((vx, vy + 1.9, vz), _fx.glow(P.WINDOW, 0.9, t, seed=30 + i,
                                                          intensity=0.55, max_px=6),
                             layer=_fx.FX_LAYER)
    cx, cy, cz = CHIMNEY_TOP
    for i in range(3):
        u = ((t * 0.00018) + i / 3.0) % 1.0
        r.add_sprite((cx + u * 1.6, cy + u * 3.2, cz + u * 0.6),
                     smoke(t, seed=40 + i, size_m=0.8 + u * 1.6), layer=_fx.FX_LAYER)
    wires(r)


def _sag(r, a, b, col, n=3, drop=0.45):
    prev = a
    for i in range(1, n + 1):
        u = i / float(n)
        p = (a[0] + (b[0] - a[0]) * u, a[1] + (b[1] - a[1]) * u - drop * 4 * u * (1 - u),
             a[2] + (b[2] - a[2]) * u)
        r.add_line3d(prev, p, col, 1, layer=2)
        prev = p


def wires(r):
    """Telephone wires pole to pole and down to the house.  Lines are
    per-frame (they never bake)."""
    col = (20, 22, 26)
    y = POLE_H - 0.02
    for (x0, z0), (x1, z1) in zip(POLES[:-1], POLES[1:]):
        for sx in (-0.7, 0.7):
            _sag(r, (x0 + sx, y, z0), (x1 + sx, y, z1), col)
    # Lines draw over the world on both backends (no depth test), so the
    # service wire is skipped where the house would hide it.
    ex, _ey, ez = r.cam
    if ez < 13.0 or ex < -16.5:
        x, z = POLES[-1]
        _sag(r, (x - 0.7, y, z), HOUSE_DROP, col, drop=0.6)


def raid_pools(extra=()):
    """Lamp pools for the raid (GL only; the software path ignores them)."""
    pools = [
        {"pos": BARN_LAMP, "range": 7.5, "color": P.LAMP_WARM,
         "hot": (255, 236, 206), "intensity": 1.6},
        {"pos": PORCH_LAMP, "range": 5.0, "color": P.LAMP_WARM,
         "hot": (255, 236, 206), "intensity": 1.2},
    ]
    return pools + list(extra)


_GRADE = {}


def grade_raid(surface):
    """The raid grade on the internal buffer, after the flush: moonlit
    blue-green shadows, warm lamplit highs, ordered dither onto the 2D ink.
    Modeled on the M6 train's ``_grade_play``; works on either renderer."""
    try:
        import numpy as np
    except ImportError:
        return
    lut = _GRADE.get("raid")
    if lut is None:
        x = np.arange(256, dtype=np.float32) / 255.0
        x = np.clip((x - 0.020) / 0.980, 0.0, 1.0)
        x = np.clip(0.45 + (x - 0.45) * 1.10, 0.0, 1.0)
        x = x ** 1.10
        sh, mid, hi = (1.0 - x) ** 2, 4.0 * x * (1.0 - x), x * x
        chan = [np.clip(v, 0.0, 1.0) for v in (
            x - 0.012 * sh + 0.004 * mid + 0.030 * hi,
            x + 0.006 * sh + 0.004 * mid + 0.010 * hi,
            x + 0.022 * sh - 0.006 * mid - 0.034 * hi)]
        lut = _GRADE["raid"] = _fx.dither_lut(_fx.ink(chan, np), np)
    _fx.apply_lut(surface, lut, np)


def stage(look, t, eye, tgt, fov, lights=(), hh=0.006, seed=0, size=None, park=None):
    """Common opening of every farm shot: look, lights, camera, sky, static bake.
    ``size`` = (w, h) picks another buffer than the film one; ``park`` moves the tractor."""
    r, buf = _w.rend(*size) if size else _w.rend()
    setup(r, look)
    r.set_lights(list(lights))
    _w.cam(r, t, eye, tgt, fov, hh=hh, seed=seed)
    sky(r, buf, t, look, seed)
    fresh = _w.static_scene(r, "m7:%s:%s" % (look, park))
    r.begin()
    ok = True
    try:
        if fresh:
            build_static(r, look, park)
    except Exception:
        ok = False
        raise
    finally:
        _w.static_end(r, ok)
    return r, buf


def finish(surface, r, buf, seed, tag, t):
    r.flush(buf)
    _w.present(surface, buf)
    _w.finish(surface, seed, tag, t=t)


def mist(r, t, seed=0, n=9, intensity=0.10):
    """Ground mist over the field and yard: low lit-haze sprites."""
    for i in range(n):
        x = -58 + (i * 37 % 61) + 0.0
        z = -6 + (i * 53 % 40)
        r.add_sprite((x, 0.7, z), _fx.haze((214, 196, 182), 8.0, t, seed=seed + i,
                                           intensity=intensity), layer=_fx.FX_LAYER)


def sun(r, t, pos=(96.0, 9.0, -14.0)):
    r.add_sprite(pos, _fx.glow((255, 196, 128), 26.0, t, intensity=0.85,
                               core=(255, 232, 190), max_px=110), layer=_fx.FX_LAYER)


def flame(t, seed=0, size_m=1.0, heat=1.0):
    """Layered, irregular tongues with a hot core and small ember flecks."""
    def draw(s, sx, sy, scale, z):
        if scale < 0.4:
            return
        pulse = 0.94 + 0.06 * math.sin(t * 0.011 + seed * 1.3)
        h = size_m * scale * 1.85 * pulse * heat
        w = size_m * scale * 1.12
        phase = t * 0.008 + seed * 1.7
        # Separate tongues break the old flat, perfectly symmetrical triangle.
        for i, (off, height, width, col) in enumerate((
                (-0.24, 0.68, 0.36, (176, 42, 24)), (0.22, 0.82, 0.34, (202, 58, 22)),
                (-0.06, 1.0, 0.54, (242, 105, 27)), (0.10, 0.70, 0.38, (255, 174, 48)),
                (0.02, 0.46, 0.22, (255, 226, 112)))):
            sway = math.sin(phase + i * 1.9) * w * 0.10
            bx = sx + off * w + sway
            bh = h * height
            bw = w * width
            pts = [(bx - bw, sy), (bx - bw * 0.72, sy - bh * 0.24),
                   (bx - bw * 0.44 + sway * 0.25, sy - bh * 0.55),
                   (bx + sway * 0.55, sy - bh), (bx + bw * 0.30, sy - bh * 0.64),
                   (bx + bw * 0.78, sy - bh * 0.27), (bx + bw, sy)]
            pygame.draw.polygon(s, col, pts)
        for i in range(7):
            ph = ((t * 0.00055 + i * 0.17 + seed * 0.07) % 1.0)
            ex = sx + math.sin(i * 2.3 + seed) * w * 0.58 + math.sin(t * 0.004 + i) * 3
            ey = sy - h * (0.35 + ph * 1.25)
            if ph < 0.82:
                r = 1 if scale < 7 else 2
                pygame.draw.circle(s, (255, 194, 92), (int(ex), int(ey)), r)
    draw.bounds_m = (size_m, size_m * 2.2)
    draw.bounds_cap_px = (90, 130)
    return draw


def smoke(t, seed=0, size_m=2.0):
    """A rising column of dark translucent puffs."""
    def draw(s, sx, sy, scale, z):
        if scale < 0.4:
            return
        for i in range(7):
            ph = ((t * 0.00022 + i / 7.0 + seed * 0.13) % 1.0)
            rad = max(2, int(size_m * scale * (0.34 + ph * 0.76)) )
            ox = sx + math.sin(ph * 5 + seed + i) * size_m * scale * 0.5 + ph * size_m * scale * 0.9
            oy = sy - ph * size_m * scale * 4.6
            a = int(78 * (1.0 - ph))
            if a < 8:
                continue
            puff = pygame.Surface((rad * 2, rad * 2), pygame.SRCALPHA)
            pygame.draw.circle(puff, (18, 16, 18, a), (rad, rad), rad)
            s.blit(puff, (ox - rad, oy - rad))
    draw.bounds_m = (size_m * 2, size_m * 5)
    draw.bounds_cap_px = (140, 260)
    return draw


def fire(r, pos, t, seed=0, size=1.0, smoky=True, layer=_fx.FX_LAYER):
    """Flame + halo + smoke. ``layer=2`` enables world-depth occlusion in gameplay."""
    x, y, z = pos
    r.add_sprite((x, y, z), flame(t, seed, size), layer=layer)
    r.add_sprite((x, y + size * 0.9, z),
                 _fx.glow((255, 150, 60), size * 2.0, t, flicker=0.12, seed=seed,
                          core=(255, 214, 140), intensity=0.72, max_px=70),
                 layer=layer)
    if smoky:
        r.add_sprite((x, y + size * 2.0, z), smoke(t, seed, size * 0.9),
                     layer=layer)


BARN_AT = (13.0, 12.0)


def burn_fx(r, t, grow=1.0):
    """The burning barn and house: flames, smoke, window glow.  ``grow`` 0..1
    scales the flames up from a young fire to a roaring one."""
    g = 0.55 + 0.45 * grow
    for i, (dx, dy, dz, sz) in enumerate(((-3.6, 5.0, 10.0, 2.3), (-0.5, 5.4, 12.0, 2.7),
                                          (2.8, 5.0, 14.0, 2.4), (-2.0, 1.2, 6.2, 1.8),
                                          (2.2, 1.5, 6.3, 1.5), (4.2, 5.1, 10.5, 2.0))):
        fire(r, (13 + dx, dy, dz), t, seed=i * 3, size=sz * g, smoky=i % 2 == 0)
    for i, (x, y, sz) in enumerate(((-14.2, 4.5, 1.7), (-9.6, 4.3, 1.4))):
        fire(r, (x, y, 10.0), t, seed=20 + i, size=sz * g, smoky=i == 0)
    for i, x in enumerate((-15.0, -12.8, -8.4)):
        r.add_sprite((x, 1.75, 6.9), _fx.window_glow((255, 150, 70), 1.2, 1.1, 0.8, t,
                                                     flicker=0.2, seed=i), layer=_fx.FX_LAYER)


def burn_lights(t=0, boost=0.0):
    f = 0.92 + 0.08 * math.sin(t * 0.013) + 0.05 * math.sin(t * 0.031 + 1.0) + boost
    return [
        {"pos": (13.0, 5.5, 8.0), "color": (255, 140, 60), "intensity": 1.1 * f, "range": 22.0},
        {"pos": (13.0, 3.0, 4.0), "color": (255, 120, 50), "intensity": 0.8 * f, "range": 14.0},
        {"pos": (-12.0, 2.0, 5.0), "color": (255, 150, 80), "intensity": 0.5 * f, "range": 9.0},
    ]


def burn_roof(r, fall):
    """The burnt barn roof, one slope of tile and the other bare rafters.
    ``fall`` 0..1 drops the ridge and the slope into the barn."""
    W, D, H, rise = 12.0, 10.0, 4.8, 3.0
    w2 = W / 2.0
    ex, ey = w2 + 0.3, H - 0.3 * rise / w2
    zf, zb = -D / 2.0 - 0.18, D / 2.0 + 0.18
    ry = H + rise - 4.5 * fall * fall
    rx = -0.9 * fall
    m = Mesh()
    m.face([(-ex, ey, zf), (-ex, ey, zb), (rx, ry, zb), (rx, ry, zf)], TILE_B, 2, True)
    for i in range(6):
        z = zf + (zb - zf) * (i + 0.5) / 6.0
        m.face([(rx, ry, z - 0.10), (rx, ry, z + 0.10), (ex, ey, z + 0.10), (ex, ey, z - 0.10)],
               (34, 24, 22), 2, True)
    h = Mesh()
    h.add(m, t=(BARN_AT[0], 0, BARN_AT[1]))
    _w.add(r, h)


def sparks(t, t0, seed=0, n=46, speed=7.0, life=2.6):
    """A burst of embers thrown up at ``t0`` (ms)."""
    def draw(s, sx, sy, scale, z):
        age = (t - t0) / 1000.0
        if age < 0.0 or age > life:
            return
        for i in range(n):
            h1 = ((i * 7919 + seed * 104729) % 1000) / 1000.0
            h2 = ((i * 6007 + seed * 7 + 311) % 997) / 997.0
            ang = (h1 - 0.5) * 2.2
            sp = speed * (0.45 + 0.8 * h2)
            x = sx + math.sin(ang) * sp * 0.7 * age * scale
            y = sy - (math.cos(ang) * sp * age - 3.2 * age * age) * scale
            fade = 1.0 - age / life
            px = 2 if fade > 0.35 else 1
            s.fill((255, int(140 + 90 * h2 * fade), int(40 + 60 * fade)), (int(x), int(y), px, px))
    draw.bounds_m = (40.0, 40.0)
    draw.bounds_cap_px = (500, 500)
    return draw


def mix(a, b, u):
    return tuple(x + (y - x) * u for x, y in zip(a, b))


def sit_pose(**kw):
    """Seated on a tractor seat: thighs forward, shins down, rifle across the knees."""
    p = dict(POSES["stand"])
    p.update(spine=8, head_p=10, lhip_p=88, rhip_p=88, lkn=90, rkn=90, lsh_p=40, lel=64,
             rsh_p=34, rel=70, rifle_p=84)
    p.update(kw)
    return p


def walk_pose(t, speed=1.0, tired=0.0):
    ph = t * 0.0062 * speed
    s, c = math.sin(ph), math.cos(ph)
    p = dict(POSES["stand"])
    p.update(lhip_p=26 * s, rhip_p=-26 * s, lkn=max(0.0, -s) * 38, rkn=max(0.0, s) * 38,
             lsh_p=-22 * s, rsh_p=22 * s, spine=4 + tired * 10, head_p=tired * 12,
             lift=abs(c) * 0.03)
    return p


def stand_pose(**kw):
    p = dict(POSES["stand"])
    p.update(kw)
    return p


def k(t, start, length):
    """Clamped smoothstep over [start, start+length] ms."""
    x = max(0.0, min(1.0, (t - start) / float(length)))
    return x * x * (3.0 - 2.0 * x)
