"""Mission 7 farm: one shared 3D builder for the drop-off and finale films and
the raid scene.  Flat late-PS2 colours, hard edges, blocky forms.

Axes: x east, y up, z north.  Scenes are viewed from -z, so the yard faces the
camera.  Layout (metres, yard centre at the origin):

    house   (-12, 10)   ridge along x, porch on the yard side
    barn    ( 13, 12)   gable end and big doors face -z, hayloft above
    shed    (-11, -9)   fuel shed, tank on a stand
    well    (  1,  4)
    track   x -3..3, runs south from the yard mouth at z -16 to z -90
    orchard x 26..41, z -8..16 (east of the yard); the old orchard x 52..73
    field   x -64..-26, z -12..34 (stubble; the helicopter lands here)

Looks: "dawn" (cold mist), "night" (dark), "burn" (night, barn and house burning).
"""
import math
from functools import lru_cache

import pygame

from engine3d.core import Light, Mesh, box, prism, quad_xz, rot_x, rot_y, rot_z
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
PLASTER_N = (158, 136, 102)      # limewash at raid hour: warm daub, not grey
PLASTER_B = (88, 80, 72)        # burnt render (finale)
TILE = P.ROOF
TILE_B = (52, 40, 36)           # burnt tile
BARN = P.BARN
BARN_B = (78, 46, 42)           # burnt boards
TRIM = P.PLASTER
ROOF_METAL = P.GALV_D
STONE = P.STONE
HAY = P.HAY
LEAF = (74, 96, 58)             # canopy keeps a green read under the moon
LEAF2 = P.GRASS_HI
TRUNK = (96, 78, 58)            # moonlit bark: dark, but not a black pole
WIN = (28, 36, 48)
WIN_LIT = P.WINDOW
EMBER = (255, 120, 40)
TRACT = P.TRACTOR
TRACT_D = P.TRACTOR_D
RUB = P.INK
HUB = P.HAY_MID
METAL = P.GALV_D
RUST = P.RUST
HILL_N = (36, 46, 38)           # the near slope keeps its grass hue
HILL_F = (48, 58, 70)
SKYLINE = (22, 26, 32)          # unlit far windows
FAR_WALL = (136, 112, 82)      # far limewash reads as warm clay, not grey

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
    # albedos (HILL_N / HILL_F), not in a short fog.  A dark night blue, not
    # a grey: the far farms and village keep their plaster and tile hues.
    "raid": dict(
        fog=(22, 29, 46), fog_start=34.0, fog_end=250.0,
        light=dict(direction=(-0.42, 0.50, -0.72), ambient=0.36, diffuse=0.72,
                   sky=0.12, tint=(0.72, 0.83, 1.0)),
        sky_top=(6, 9, 18), sky_bot=(30, 40, 64), sodium=None,
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


def _bipyr(cx, cy, cz, r, up, dn, col, col2=None, n=6, moon=False):
    """Bipyramid.  ``moon``: side faces turned toward the raid moon get a +12 shade."""
    m = Mesh()
    ring = [(cx + r * math.cos(2 * math.pi * i / n),
             cy, cz + r * math.sin(2 * math.pi * i / n)) for i in range(n)]
    top, bot = (cx, cy + up, cz), (cx, cy - dn, cz)
    for i in range(n):
        a, b = ring[i], ring[(i + 1) % n]
        k = 0
        if moon:
            ang = 2 * math.pi * (i + 0.5) / n
            k = 12 if math.cos(ang) * -0.504 + math.sin(ang) * -0.864 > 0.2 else 0
        m.face([a, b, top], _v(col, k), 2, True)
        m.face([b, a, bot], _v(col2 or _v(col, -22), k), 2, True)
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
        quad_xz(-400, -400, 400, 400, 0.0, _t("grass", GRASS), layer=0, seg=40),
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
    """Faceted hills with a valley opening along the southern road.  World
    layer, not background: woods, farms and the village stand on these
    slopes and behind their crests, and only a depth test hides the parts
    inside the hill (a background hill let them show through and slide)."""
    m = Mesh()
    n = 60
    south = 1.5 * math.pi
    cut = math.radians(5.0)
    shoulder = math.radians(14.0)

    for ring, col in enumerate((_t("grass", HILL_N), _t("grass", HILL_F))):
        rad = HILL_RAD[ring]

        # Add exact vertices at the edges of the road opening.
        angles = [math.tau * i / n for i in range(n + 1)]
        angles.extend((south - cut, south + cut))
        angles.sort()

        rows = []
        for a in angles:
            da = abs((a - south + math.pi) % math.tau - math.pi)
            u = max(0.0, min(1.0, (da - cut) / (shoulder - cut)))
            u = u * u * (3.0 - 2.0 * u)

            h = _hill_h(a, ring) * u
            c, s = math.cos(a), math.sin(a)
            rows.append((
                ((rad - 9.0) * c, -0.5, (rad - 9.0) * s),
                ((rad - 4.0) * c, h * 0.43, (rad - 4.0) * s),
                (rad * c, h, rad * s),
                ((rad + 8.0) * c, -0.5, (rad + 8.0) * s),
            ))

        for i in range(len(angles) - 1):
            a = (angles[i] + angles[i + 1]) * 0.5
            da = abs((a - south + math.pi) % math.tau - math.pi)
            if da < cut:
                continue

            lo0, mid0, top0, back0 = rows[i]
            lo1, mid1, top1, back1 = rows[i + 1]
            shade = (((i * 73) ^ (i * 131 + ring * 17)) & 7) - 3

            m.face([lo0, lo1, mid1], _v(col, shade - 3), 2, True)
            m.face([lo0, mid1, mid0], _v(col, shade - 1), 2, True)
            m.face([mid0, mid1, top1], _v(col, shade + 1), 2, True)
            m.face([mid0, top1, top0], _v(col, shade + 3), 2, True)
            # Back slope: closes the crest so the woods on it stay rooted.
            m.face([top0, top1, back1, back0], _v(col, shade - 6), 2, True)

    return m


def house(lit=False, burn=False):
    m = Mesh()
    W, D, H = 9.0, 6.0, 3.0
    # At night the limewash is a shade down: full white under the moon read
    # brighter than the lit windows.
    wall = PLASTER_B if burn else _t("plaster", PLASTER_N if lit else PLASTER)
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
        # The pane stands proud of its frame: a full-box trim behind it would
        # hide the lit glass and the window read as a grey plaster square.
        m.add(box(0.95, 0.85, 0.06, WIN_LIT if lit else WIN,
                  center=(x, 1.75, zf - 0.06), emissive=lit))
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
                brace.add(box(0.14, 4.1, 0.05, _t("plank", P.WOOD_L),
                              center=(0, 0, 0)), rot_z(ang))
                m.add(brace, t=(sx, 1.8, zf - 0.03))
        for x in (-2.6, 2.6):
            m.add(box(0.2, 3.7, 0.12, _t("plank", P.WOOD_L), center=(x, 1.85, zf - 0.02)))
        m.add(box(5.4, 0.2, 0.12, _t("plank", P.WOOD_L), center=(0, 3.7, zf - 0.02)))
        m.add(box(1.6, 1.6, 0.1, door, center=(0, H + 1.1, zf)))
        m.add(box(1.9, 0.16, 0.12, _t("plank", P.WOOD_L),
                  center=(0, H + 1.95, zf - 0.02)))
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
    bark = _t("bark", TRUNK)
    m.add(contact(1.6))
    m.add(box(0.58, 0.14, 0.58, _v(bark, -22), center=(0, 0.07, 0)))
    m.add(box(0.30, 1.8, 0.30, bark, center=(0, 0.9, 0)))
    m.add(_bipyr(0, 2.3 * s, 0, 1.35 * s, 1.0 * s, 0.75 * s, _t("leaf", LEAF)))
    m.add(_bipyr(0.1, 3.1 * s, 0.05, 0.9 * s, 0.8 * s, 0.3 * s, _t("leaf", LEAF2)))
    return m


def contact(size, col=None):
    """A baked contact shadow at a tree's foot: without it a night canopy
    reads as a crown hanging over the field."""
    m = Mesh()
    m.add(quad_xz(-size / 2.0, -size / 2.0, size / 2.0, size / 2.0, 0.046,
                  col or _v(LEAF, -26), layer=1, seg=1))
    return m


def orchard():
    m = Mesh()
    bark = _t("bark", TRUNK)
    soil = _t("dirt", FURROW)
    root_soil = _v(soil, -8)
    furrow = _t("furrow", P.TRACK_D)
    leaf = _t("leaf", LEAF)
    i = 0

    for x in (26, 31, 36, 41):
        m.add(quad_xz(
            x - 1.35, -10, x + 1.35, 19, 0.028,
            soil, layer=1, seg=6))

        # Narrow worked edges make the planting rows read at a distance.
        for dx in (-1.0, 1.0):
            m.add(quad_xz(
                x + dx - 0.08, -10, x + dx + 0.08, 19, 0.033,
                furrow, layer=1, seg=3))

        for z in (-8, -2, 4, 10, 16):
            # Must remain identical to raid_world._orchard().
            tx = x + ((i * 13) % 5) * 0.2 - 0.4
            tz = z + ((i * 7) % 5) * 0.2 - 0.4
            s = 0.90 + 0.04 * ((i * 37) % 7)

            m.add(quad_xz(
                tx - 0.38, tz - 0.38, tx + 0.38, tz + 0.38, 0.036,
                root_soil, layer=1, seg=1))

            t = Mesh()
            t.add(contact(1.4))
            t.add(box(0.58, 0.14, 0.58, _v(bark, -22), center=(0, 0.07, 0)))
            t.add(box(0.30, 1.7, 0.30, bark, center=(0, 0.85, 0)))

            # Forked branches show beneath the pruned crowns.
            for side in (-1, 1):
                t.add(
                    box(0.10, 0.82, 0.10, bark),
                    rot_z(-side * 38),
                    t=(side * 0.25, 1.96, 0))

            crown = _v(leaf, (i % 5 - 2) * 5)
            t.add(_bipyr(
                0, 2.50, 0, 1.30 * s, 0.95 * s, 1.15,
                crown, n=6, moon=True))
            t.add(_bipyr(
                0.50 * s, 2.90, 0.12 * s,
                0.82 * s, 0.72 * s, 0.60,
                _v(crown, 8), n=5, moon=True))
            t.add(_bipyr(
                -0.47 * s, 2.75, -0.10 * s,
                0.75 * s, 0.64 * s, 0.55,
                _v(crown, -7), n=5, moon=True))

            # Fruit sits on the flat north and south faces of some crowns.
            if i % 3 == 0:
                for side in (-1, 1):
                    for fx in (-0.42, 0.42):
                        fruit = (180, 74, 40) if (i + side) % 2 else (196, 98, 45)
                        t.add(box(
                            0.12, 0.12, 0.12, fruit,
                            center=(fx * s, 2.50, side * 1.14 * s)))

            m.add(t, rot_y((i * 47) % 360), t=(tx, 0, tz))
            i += 1

    # East-west access lane and turning headland.
    m.add(quad_xz(
        18, -1.15, 48, 1.15, 0.055,
        _t("track", TRACK), layer=1, seg=8))
    m.add(quad_xz(
        43.7, -10, 46.5, 20, 0.038,
        _t("track", TRACK), layer=1, seg=6))

    return m


@lru_cache(maxsize=1)
def _tractor_asset():
    """(verts, faces) of the imported TractorM7.glb (tools/ae_import_tractor.py),
    or None when the mesh file is missing."""
    try:
        from game.render3d_bridge import load_mesh_asset
        return load_mesh_asset("tractor_m7")
    except (OSError, ValueError):
        return None


def tractor(lit=False):
    """Local forward = +x.  The authored asset; the procedural one if it is missing."""
    asset = _tractor_asset()
    if asset is None:
        return _tractor_blocks(lit)
    verts, faces = asset
    m = Mesh()
    m.verts = [tuple(v) for v in verts]
    m.faces = [(tuple(f[0]), WIN_LIT if lit and f[2] == 1 else tuple(f[1]),
                2, True, lit and f[2] > 0) for f in faces]
    return m


def _tractor_blocks(lit=False):
    """Local forward = +x.  Rear wheels at x -0.7, front at +1.0."""
    m = Mesh()

    def wheel(x, z, rad, wid):
        """Low-poly tyre with an integral tread, sidewall and recessed rim.

        Every side is built as non-overlapping concentric bands rather than
        stacking cylinders. This also keeps the software painter from drawing
        a hub through the tyre when viewed from an angle.
        """
        n = 16
        cy = rad * math.cos(math.pi / n) - 0.025
        angles = [math.tau * k / n + math.pi / n for k in range(n)]

        def ring(radius):
            return [(x + radius * math.cos(a), cy + radius * math.sin(a)) for a in angles]

        outer = ring(rad)
        shoulder = ring(rad * 0.86)
        bead = ring(rad * 0.51)
        rim = ring(rad * 0.42)
        hub = ring(rad * 0.18)
        z0, z1 = z - wid / 2, z + wid / 2

        # Integrated alternating tread strips: all are on the tyre surface,
        # rather than separate blocks sticking out of it.
        for k in range(n):
            j = (k + 1) % n
            for strip in range(3):
                za = z0 + wid * strip / 3.0
                zb = z0 + wid * (strip + 1) / 3.0
                shade = (12 if (k + strip) % 2 == 0 else 3)
                m.face([(outer[k][0], outer[k][1], za),
                        (outer[j][0], outer[j][1], za),
                        (outer[j][0], outer[j][1], zb),
                        (outer[k][0], outer[k][1], zb)], _v(RUB, shade), 2, True)

        # Each side is tiled edge-to-edge. A dark bead separates the rubber
        # from the metal rim, with a smaller, shaded centre cap.
        for side in (-1, 1):
            zz = z + side * wid / 2
            for k in range(n):
                j = (k + 1) % n
                for outside, inside, colour in (
                    (outer, shoulder, _v(RUB, 10 if k % 2 else 6)),
                    (shoulder, bead, _v(RUB, 4)),
                    (bead, rim, _v(RUB, -7)),
                    (rim, hub, _v(HUB, 6 if k % 2 else -4)),
                ):
                    m.face([(outside[k][0], outside[k][1], zz),
                            (outside[j][0], outside[j][1], zz),
                            (inside[j][0], inside[j][1], zz),
                            (inside[k][0], inside[k][1], zz)], colour, 2, True)
            m.face([(px, py, zz) for px, py in hub], _v(HUB, -18), 2, True)

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
    # Eight-sided steering rim, spokes and column, kept clear of the seat.
    steer_r = 0.23
    for k in range(8):
        a = math.tau * k / 8
        b = math.tau * (k + 1) / 8
        ax, az = 0.1 + steer_r * math.cos(a), steer_r * math.sin(a)
        bx, bz = 0.1 + steer_r * math.cos(b), steer_r * math.sin(b)
        dx, dz = bx - ax, bz - az
        m.add(box(math.hypot(dx, dz), 0.035, 0.035, RUB),
              rot_y(-math.degrees(math.atan2(dz, dx))),
              t=((ax + bx) / 2, 1.92, (az + bz) / 2))
    m.add(box(0.36, 0.03, 0.035, METAL, center=(0.1, 1.91, 0)))
    m.add(box(0.035, 0.03, 0.36, METAL, center=(0.1, 1.91, 0)))
    m.add(box(0.1, 0.9, 0.1, METAL, center=(1.0, 2.0, 0.22)))
    # Raised grille surround and horizontal cooling slats.
    m.add(box(0.045, 0.48, 0.48, RUB, center=(1.565, 1.30, 0)))
    for yy in (1.12, 1.21, 1.30, 1.39, 1.48):
        m.add(box(0.025, 0.025, 0.44, METAL, center=(1.60, yy, 0)))
    for sz in (-0.28, 0.28):
        m.add(box(0.10, 0.18, 0.22, RUB, center=(1.57, 1.44, sz)))
        m.add(box(0.035, 0.12, 0.16, WIN_LIT if lit else METAL,
                  center=(1.63, 1.44, sz), emissive=lit))
    # Hood seams, engine vents and steps add readable mechanical detail.
    for sz in (-0.36, 0.36):
        m.add(box(1.05, 0.05, 0.035, _v(TRACT, 16), center=(0.83, 1.69, sz)))
        for xx in (0.55, 0.70, 0.85, 1.00):
            m.add(box(0.065, 0.26, 0.025, TRACT_D, center=(xx, 1.28, sz)))
        m.add(box(0.48, 0.08, 0.30, METAL, center=(-0.42, 0.72, sz * 1.8)))
    m.add(box(0.17, 0.07, 0.17, RUB, center=(1.0, 2.48, 0.22)))
    m.add(box(0.22, 0.12, 0.32, METAL, center=(-1.28, 0.55, 0)))  # tow hitch
    # Mudguard lips, rear lamps and stamped panel lines.
    for side in (-1, 1):
        z = side * 0.82
        m.add(box(1.20, 0.045, 0.06, _v(TRACT, 14),
                  center=(-0.7, 1.615, z + side * 0.22)))
        m.add(box(0.055, 0.13, 0.18, (140, 52, 38),
                  center=(-1.36, 1.47, z)))
        # Angled braces support the rear mudguards above the large wheels.
        m.add(box(0.08, 0.37, 0.08, TRACT_D), rot_z(-24),
              t=(-0.35, 1.34, z - side * 0.16))
    # Distinct fuel cap, engine lower rails and rear drawbar.
    m.add(box(0.16, 0.06, 0.16, METAL, center=(0.48, 1.705, -0.12)))
    for z in (-0.37, 0.37):
        m.add(box(1.08, 0.08, 0.05, TRACT_D, center=(0.78, 0.98, z)))
    m.add(box(0.43, 0.08, 0.09, METAL, center=(-1.36, 0.51, 0)))
    # Gear lever rises beside the driver's seat.
    m.add(box(0.045, 0.45, 0.045, METAL), rot_z(12), t=(-0.30, 1.52, -0.25))
    m.add(box(0.09, 0.09, 0.09, RUB, center=(-0.34, 1.76, -0.25)))
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
    m.add(box(1.9, 0.16, 1.9, METAL, center=(0.0, 0.08, 0.0)))
    return m


def _farm_windpump():
    """An old four-vane windpump silhouette at the field boundary."""
    m = Mesh()
    metal = (106, 111, 101)
    m.add(box(0.22, 6.0, 0.22, metal, center=(0, 3.0, 0)))
    leg_l = box(0.13, 3.3, 0.13, WOOD_D)
    leg_r = box(0.13, 3.3, 0.13, WOOD_D)
    m.add(leg_l, rot_z(-24), t=(-0.72, 1.51, 0))
    m.add(leg_r, rot_z(24), t=(0.72, 1.51, 0))
    m.add(box(2.8, 0.13, 0.12, metal, center=(0, 5.65, -0.15)))
    m.add(box(0.12, 2.8, 0.12, metal, center=(0, 5.65, -0.15)))
    for ang in (45, -45):
        blade = box(2.2, 0.09, 0.10, (142, 145, 128))
        m.add(blade, rot_z(ang), t=(0, 5.65, -0.22))
    m.add(box(0.42, 0.42, 0.30, RUST, center=(0, 5.65, -0.34)))
    # Water trough beneath the pump catches a little of the warm practical light.
    m.add(box(1.5, 0.32, 0.72, WOOD_D, center=(1.2, 0.16, -0.2)))
    m.add(box(1.32, 0.06, 0.54, (42, 68, 70), center=(1.2, 0.33, -0.2)))
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
        m.add(tree(70 + i), t=(x, _ground_y(x, z), z))
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
# The line ends at the pass: a pole behind the third ridge would draw over it.
POLES = [(-5.5, -21.0 - 16.0 * i) for i in range(8)][::-1] + [(-18.5, -13.5)]
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


def _pole_y(z):
    """Ground under a pole: the farm plain, the valley floor, then the climb
    to the pass (the road's last face, ``road_dressing``)."""
    if z >= -128.0:
        return _valley_y(z)
    return 2.52 + (7.15 - 2.52) * min(1.0, (-128.0 - z) / 12.5)


def poles():
    m = Mesh()
    p = _pole()
    for x, z in POLES:
        m.add(p, t=(x, _pole_y(z), z))
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
VILLAGE_R = 79.0


def _village():
    """Far houses round the church: (x, z, base y, lit sides).  On the near
    hill ring's inner face, like the far farms: hills draw as background, so
    a house behind the crest would show whole, floating over it.  Each sits
    at the slope height under its front wall and digs into the hill behind."""
    out = []
    for i, (da, dr) in enumerate(((-0.34, -1.0), (-0.26, 0.5), (-0.18, -1.5), (0.11, 0.0),
                                  (0.18, -1.5), (0.25, 0.5), (0.32, -1.0), (0.40, 0.0))):
        a = _CHURCH_A + da
        rad = VILLAGE_R + dr
        out.append((rad * math.cos(a), rad * math.sin(a), _hill_y(a, rad - 2.0),
                    tuple(k for k in range(4) if (i * 5 + k * 3) % 7 < 3)))
    return out


def skyline(lit):
    """A village and its onion-domed church on the northern hillside: the
    farm's limewash and clay tile, a few lamplit windows."""
    m = Mesh()
    wall = _t("plaster", FAR_WALL)
    roof = _t("tile", _v(TILE, -18))
    win = WIN_LIT if lit else SKYLINE
    for x, z, y, sides in _village():
        g = Mesh()
        g.add(box(4.2, 2.8 + 2.0, 3.4, wall, center=(0, 0.4, 0)))
        g.add(box(4.3, 1.6, 3.5, _t("stone", P.STONE_D), center=(0, -0.55, 0)))
        g.add(_gable_z(3.4, 4.2, 2.8, 1.6, roof, wall), rot_y(90))
        m.add(g, t=(x, y, z))
        for k in sides:
            ox, oz = ((0, -1.74), (2.14, 0), (0, 1.74), (-2.14, 0))[k]
            w, d = (0.6, 0.06) if k % 2 == 0 else (0.06, 0.6)
            m.add(box(w, 0.6, d, win, center=(x + ox, y + 1.6, z + oz), emissive=lit))
    rad = VILLAGE_R + 3.0
    cx, cz = rad * math.cos(_CHURCH_A), rad * math.sin(_CHURCH_A)
    y = _hill_y(_CHURCH_A, rad - 3.0)
    dome = _t("tin", P.GALV_D)
    m.add(box(10.0, 6.0 + 3.0, 6.0, wall, center=(cx, y + 1.5, cz)))
    g = Mesh()
    g.add(_gable_z(6.0, 10.0, 6.0, 2.6, roof, wall), rot_y(90))
    m.add(g, t=(cx, y, cz))
    tx = cx + 6.4
    m.add(box(3.2, 13.0 + 3.0, 3.2, wall, center=(tx, y + 5.0, cz)))
    m.add(box(3.6, 0.4, 3.6, dome, center=(tx, y + 13.2, cz)))
    m.add(_bipyr(tx, y + 14.2, cz, 1.9, 2.3, 0.8, dome, _v(dome, -20), n=8))
    m.add(box(0.2, 2.4, 0.2, P.GALV, center=(tx, y + 17.6, cz)))
    m.add(box(1.0, 0.18, 0.18, P.GALV, center=(tx, y + 18.2, cz)))
    m.add(box(0.5, 1.2, 0.06, win, center=(tx, y + 9.5, cz - 1.63), emissive=lit))
    return m


def _shelter_tree(seed=0):
    """Taller windbreak trees; distinct from the small orchard trees."""
    m = Mesh()
    s = 0.90 + 0.09 * (seed % 5)
    bark = _t("bark", TRUNK)
    leaf = _t("leaf", _v(LEAF, (seed % 3 - 1) * 6))

    m.add(contact(1.9))
    m.add(box(0.72, 0.16, 0.72, _v(bark, -20), center=(0, 0.08, 0)))
    m.add(box(0.34, 3.2 * s, 0.34, bark,
              center=(0, 1.6 * s, 0)))

    if seed % 4 == 0:
        # Narrow poplar-like silhouette.
        # Lower cone runs down to the ground: the trunk is too dark to show at range.
        m.add(_bipyr(
            0, 4.7 * s, 0,
            1.05 * s, 3.0 * s, 4.7 * s,
            leaf, n=5))
    else:
        # Offset crowns avoid a repeated row of identical diamonds.
        m.add(_bipyr(
            -0.40 * s, 4.1 * s, 0,
            2.0 * s, 1.9 * s, 4.1 * s,
            leaf, n=6))
        m.add(_bipyr(
            0.70 * s, 5.0 * s, 0.25 * s,
            1.55 * s, 1.4 * s, 0.9 * s,
            _v(leaf, 8), n=5))
    return m


def _hedgerow(x0, z0, x1, z1, seed=0):
    """Faceted earth bank with an uneven, hard-edged hedge on top."""
    m = Mesh()
    dx, dz = x1 - x0, z1 - z0
    length = math.hypot(dx, dz)
    if length < 0.01:
        return m

    nx, nz = -dz / length, dx / length
    width, crest = 1.10, 0.42
    grass = _t("grass", GRASS)
    leaf = _t("leaf", _v(LEAF, (seed % 3 - 1) * 5))

    a0 = (x0 + nx * width, 0.025, z0 + nz * width)
    a1 = (x1 + nx * width, 0.025, z1 + nz * width)
    b0 = (x0 - nx * width, 0.025, z0 - nz * width)
    b1 = (x1 - nx * width, 0.025, z1 - nz * width)
    r0, r1 = (x0, crest, z0), (x1, crest, z1)

    m.face([a0, a1, r1, r0], grass, 2, True)
    m.face([r0, r1, b1, b0], _v(grass, -8), 2, True)
    m.face([b0, a0, r0], grass, 2, True)
    m.face([a1, b1, r1], grass, 2, True)

    n = max(2, int(length / 1.7))
    for i in range(n):
        u = (i + 0.5) / n
        h = (i * 37 + seed * 19) % 17
        sideways = (h % 5 - 2) * 0.09
        x = x0 + dx * u + nx * sideways
        z = z0 + dz * u + nz * sideways
        cy = 0.98 + 0.05 * (h % 3)

        m.add(_bipyr(
            x, cy, z,
            0.85 + 0.08 * (h % 4),
            0.72 + 0.10 * (h % 5),
            cy - 0.40,
            _v(leaf, (h % 3 - 1) * 5),
            n=5))
    return m


def outer_dressing():
    """Working landscape around the farm, clear of the main approaches."""
    m = Mesh()
    track = _t("track", TRACK)
    loam = _t("dirt", FURROW)
    stone = _t("stone", STONE)
    plank = _t("plank", WOOD)

    # --- North: a working lane between divided fields ---------------------

    # Continues through the existing north fence opening.
    m.add(quad_xz(
        -1.4, 22, 1.4, 70, 0.035,
        track, layer=1, seg=10))

    # Broad cultivated strips, rather than tiny ground-colour noise.
    # All are north of the helicopter field.
    for x in (-46, -41, -36, -31, 11, 16, 21):
        m.add(quad_xz(
            x, 40, x + 2.1, 56, 0.026,
            _t("furrow", P.TRACK_D), layer=1, seg=4))

    hedge_runs = (
        # Rear paddocks: retain the generous central approach.
        (-27, 36, -10, 36),
        (10, 36, 27, 36),
        (-58, 57, -11, 59),
        (11, 59, 58, 56),

        # Orchard boundary: leave the east approach open around z=0.
        (48, -17, 48, -5),
        (48, 5, 48, 25),

        # Roadside hedges, interrupted by field entrances.
        (-9.5, -80, -9.5, -61),
        (-9.5, -48, -9.5, -29),
        (9, -79, 9, -58),
    )
    for i, run in enumerate(hedge_runs):
        m.add(_hedgerow(*run, seed=20 + i))

    # Uneven groves, not another evenly spaced tree grid.
    tree_sites = (
        # Behind the farm.
        (-27, 39), (-24, 42), (-20, 38), (-16, 43), (-11, 40),
        (11, 41), (15, 38), (20, 43), (25, 40), (31, 44),

        # Beyond the orchard.
        (51, -13), (55, -10), (52, 12),
        (56, 17), (51, 27), (57, 29),

        # Along the valley road.
        (-13, -38), (-16, -43), (-12, -63), (-16, -68),
        (13, -50), (17, -54), (12, -73), (16, -78),
    )
    for i, (x, z) in enumerate(tree_sites):
        m.add(_shelter_tree(i), rot_y((i * 57) % 360),
              t=(x, _ground_y(x, z), z))

    # A modest equipment store gives the rear landscape a purpose.
    store = Mesh()
    boards = _t("plank", P.WOOD_GREY)
    store.add(box(5.0, 2.4, 3.6, boards, center=(0, 1.2, 0)))
    store.add(_gable_z(
        5.0, 3.6, 2.4, 0.9,
        _t("tin", ROOF_METAL), boards))
    store.add(box(
        1.5, 1.9, 0.08, _t("plank", WOOD_D),
        center=(0, 0.95, -1.84)))
    m.add(store, t=(32, 0, 34))

    m.add(hay(6), t=(-20, 0, 30))
    m.add(hay(4), t=(28, 0, 24.6))

    # Picking crates beyond the orchard's eastern turning headland.
    for i in range(4):
        m.add(box(
            0.75, 0.55, 0.65, _v(plank, (i % 3 - 1) * 8),
            center=(45.8 + 0.85 * (i % 2),
                    0.275,
                    13.0 + 0.85 * (i // 2))))

    # --- South: a used road with shoulders and drainage -------------------

    # Wheel ruts over the existing track surface.
    for x in (-1.10, 1.10):
        m.add(quad_xz(
            x - 0.25, -92, x + 0.25, -27, 0.052,
            _t("dirt", P.TRACK_D), layer=1, seg=12))

    # Broken grass growing between the ruts.
    for z in range(-87, -31, 9):
        m.add(quad_xz(
            -0.28, z, 0.28, z + 5, 0.055,
            _t("grass", GRASS), layer=1, seg=1))

    # Dark drainage strips sit outside the usable road.
    for x0, x1 in ((-5.5, -4.2), (4.2, 5.5)):
        m.add(quad_xz(
            x0, -82, x1, -29, 0.025,
            loam, layer=1, seg=9))

    # Culvert headwalls: masonry at the shoulders, not across the lane.
    for x in (-4.7, 4.7):
        m.add(box(
            1.1, 0.52, 1.9, stone,
            center=(x, 0.26, -36)))
        m.add(box(
            1.25, 0.12, 2.1, P.STONE_D,
            center=(x, 0.58, -36)))
        m.add(box(
            0.55, 0.24, 0.025, WOOD_D,
            center=(x, 0.22, -36.965)))

    # Sparse pale marker bands make the approach readable at night.
    for z in (-31, -46, -63, -77):
        m.add(box(
            0.15, 0.65, 0.15, WOOD_D,
            center=(4.0, 0.325, z)))
        m.add(box(
            0.20, 0.12, 0.20, TRIM,
            center=(4.0, 0.49, z)))

    return m


def _landscape_water_tower():
    """A distant, timber-framed landmark behind the western fields."""
    m = Mesh()
    wood = _t("plank", WOOD_D)
    tank = _t("plank", P.WOOD_GREY)
    tin = _t("tin", ROOF_METAL)

    for x in (-1.2, 1.2):
        for z in (-1.2, 1.2):
            m.add(box(0.18, 6.5, 0.18, wood, center=(x, 3.25, z)))

    m.add(box(3.5, 0.18, 3.5, wood, center=(0, 6.5, 0)))

    # Cross-bracing on all four sides.
    braces = Mesh()
    length = math.hypot(2.4, 4.8)
    angle = math.degrees(math.atan2(2.4, 4.8))
    for z in (-1.2, 1.2):
        for a in (-angle, angle):
            braces.add(
                box(0.11, length, 0.11, wood),
                rot_z(a), t=(0, 3.55, z))
    m.add(braces)
    m.add(braces, rot_y(90))

    n = 8
    ring = [
        (1.55 * math.cos(math.tau * i / n),
         1.55 * math.sin(math.tau * i / n))
        for i in range(n)
    ]
    for i in range(n):
        x0, z0 = ring[i]
        x1, z1 = ring[(i + 1) % n]

        m.face([
            (x0, 6.6, z0), (x1, 6.6, z1),
            (x1, 9.7, z1), (x0, 9.7, z0),
        ], _v(tank, 4 if i % 2 else -3), 2, True)

        m.face([
            (x0, 9.7, z0), (x1, 9.7, z1), (0, 10.7, 0),
        ], _v(tin, 5 if i % 2 else -5), 2, True)

        for y in (6.85, 9.45):
            m.face([
                (x0 * 1.01, y, z0 * 1.01),
                (x1 * 1.01, y, z1 * 1.01),
                (x1 * 1.01, y + 0.06, z1 * 1.01),
                (x0 * 1.01, y + 0.06, z0 * 1.01),
            ], METAL, 2, True)

    return m


def _landscape_hut(lit):
    """A small occupied field hut, visible between the windbreak trees."""
    m = Mesh()
    w, d, h = 4.4, 3.2, 2.2
    boards = _t("plank", P.WOOD_GREY)
    stone = _t("stone", P.STONE_D)

    m.add(box(w, h, d, boards, center=(0, h / 2.0, 0)))
    m.add(box(w + 0.1, 0.22, d + 0.1, stone, center=(0, 0.11, 0)))
    m.add(_gable_z(w, d, h, 0.9, _t("tin", ROOF_METAL), boards))
    m.add(box(0.35, 0.8, 0.35, stone, center=(1.3, 2.85, 0.3)))

    zf = -d / 2.0 - 0.03
    m.add(box(0.85, 1.8, 0.08, _t("plank", WOOD_D),
              center=(-0.9, 0.9, zf)))
    m.add(box(0.85, 0.7, 0.06, TRIM, center=(0.9, 1.3, zf)))
    m.add(box(0.65, 0.5, 0.06, WIN_LIT if lit else WIN,
              center=(0.9, 1.3, zf - 0.06), emissive=lit))
    return m


def landscape_dressing(look):
    """Static background depth, kept clear of the raid approaches and landing field."""
    m = Mesh()

    # Large, quiet colour shapes behind the farm. Existing furrows and the
    # north footpath sit slightly higher and remain visible.
    patches = (
        (-70, 35, -49, 56, "stubble", P.HAY_DD),
        (-48, 35, -28, 56, "grass", P.GRASS_DRY),
        (-24, 37, -4, 57, "grass", P.GRASS_DRY),
        (4, 37, 20, 57, "stubble", P.HAY_D),
        (26, 38, 44, 60, "stubble", P.HAY_DD),
        (45, 36, 64, 58, "grass", P.GRASS_DRY),
        (-55, 62, -8, 70, "stubble", P.HAY_DD),
        (8, 62, 54, 70, "grass", P.GRASS_D),
        (-70, -90, -15, -54, "grass", P.GRASS_DRY),
        (15, -90, 70, -54, "stubble", P.HAY_DD),
    )
    for x0, z0, x1, z1, name, col in patches:
        m.add(quad_xz(
            x0, z0, x1, z1, 0.020,
            _t(name, col), layer=1, seg=4))

    furrow = _t("furrow", P.TRACK_D)
    for x in (-67, -64, -61, -58, -55, -52):
        m.add(quad_xz(x, 37, x + 0.32, 54, 0.031,
                      furrow, layer=1, seg=2))
    for z in (40, 43, 46, 49, 52, 55, 58):
        m.add(quad_xz(27, z, 43, z + 0.32, 0.031,
                      furrow, layer=1, seg=2))

    # Continue the orchard access lane beyond the playable orchard.
    track = _t("track", TRACK)
    m.add(quad_xz(48, -1.15, 72, 1.15, 0.055,
                  track, layer=1, seg=4))
    for z in (-0.5, 0.5):
        m.add(quad_xz(21, z - 0.09, 72, z + 0.09, 0.060,
                      _t("dirt", P.TRACK_D), layer=1, seg=6))

    # Broken verge strips frame the truck road without narrowing it.
    for z0, z1 in ((-96, -86), (-80, -68), (-61, -50), (-43, -29)):
        for x0, x1 in ((-4.1, -3.3), (3.3, 4.1)):
            m.add(quad_xz(x0, z0, x1, z1, 0.020,
                          _t("grass", P.GRASS_DRY), layer=1, seg=3))

    # An uneven second windbreak gives the orchard and rear fields depth.
    sites = (
        (-66, 44), (-62, 52), (-57, 60), (-47, 62),
        (-39, 65), (-31, 66), (-22, 64), (-13, 65),
        (12, 65), (21, 66), (30, 65), (40, 62),
        (49, 59), (57, 52),
        (60, -23), (65, -16), (68, -10),
        (69, 10), (65, 17), (63, 24), (59, 33), (57, 40),
        (-16, -86), (-19, -80), (16, -87), (19, -81),
    )
    for i, (x, z) in enumerate(sites):
        m.add(_shelter_tree(200 + i * 7),
              rot_y((i * 61) % 360), t=(x, _ground_y(x, z), z))

    # Farm silhouettes between the foreground buildings and the village.
    m.add(_landscape_water_tower(), t=(-32, 0, 53))
    m.add(_landscape_hut(look != "dawn"), t=(-53, 0, 51))

    for i, (x, z) in enumerate((
            (-61, 41), (-52, 45), (-42, 51), (-17, 51),
            (18, 49), (38, 52), (58, 44))):
        m.add(hay(1), rot_y((i * 37) % 180), t=(x, 0, z))

    m.add(_fence(-45, 46, -35, 46, h=0.9, every=3.5, col=P.WOOD_GREY))
    m.add(_fence(30, 46, 42, 46, h=0.9, every=3.5, col=P.WOOD_GREY))

    # Roadside reflectors and an old direction board, outside the road width.
    for z in (-39, -55, -71, -87):
        m.add(box(0.15, 0.85, 0.15, WOOD_D, center=(-4.05, 0.425, z)))
        m.add(box(0.18, 0.13, 0.18, TRIM, center=(-4.05, 0.70, z)))

    sign_z = -49.0
    m.add(box(0.14, 2.05, 0.14, WOOD_D, center=(-6.1, 1.025, sign_z)))
    m.add(box(1.5, 0.42, 0.10, _t("plank", P.WOOD_GREY),
              center=(-6.1, 1.80, sign_z)))
    for side in (-1, 1):
        z = sign_z + side * 0.061
        m.add(box(0.90, 0.06, 0.012, TRIM, center=(-6.1, 1.85, z)))
        m.add(box(0.58, 0.05, 0.012, TRIM, center=(-6.1, 1.70, z)))

    m.add(_fence(-9.5, -98, -9.5, -84, h=1.05, every=4.0,
                 col=P.WOOD_GREY))
    m.add(_fence(9.0, -98, 9.0, -84, h=1.05, every=4.0,
                 col=P.WOOD_GREY))

    return m


# Backdrop albedos: dead crops, beehives and the furthest ridge.
STALK = (108, 98, 56)           # dead sunflower stalks, toward the dry grass
SEEDHEAD = (70, 58, 40)
HIVE = (112, 116, 104)
FAR_RIDGE = (34, 40, 50)        # third ridge: nearly the fog
CREST_N = (22, 28, 27)          # woods on the near crest (HILL_N, darker)
CREST_F = (34, 41, 47)

_SOUTH = 1.5 * math.pi


def _gap_u(a, cut=5.0, shoulder=14.0):
    """0 inside the southern road gap, 1 clear of its shoulders (as ``hills``)."""
    da = abs((a - _SOUTH + math.pi) % math.tau - math.pi)
    cut, shoulder = math.radians(cut), math.radians(shoulder)
    u = max(0.0, min(1.0, (da - cut) / (shoulder - cut)))
    return u * u * (3.0 - 2.0 * u)


@lru_cache(maxsize=2)
def _hill_surface_triangles(ring):
    """The same projected triangles as hills(), for accurate tree placement."""
    rad = HILL_RAD[ring]
    south, cut = 1.5 * math.pi, math.radians(5.0)
    angles = [math.tau * i / 60 for i in range(61)]
    angles.extend((south - cut, south + cut))
    angles.sort()
    rows = []
    for a in angles:
        h = _hill_h(a, ring) * _gap_u(a)
        c, s = math.cos(a), math.sin(a)
        rows.append(tuple((rr * c, yy, rr * s) for rr, yy in (
            (rad - 9.0, -0.5), (rad - 4.0, h * 0.43),
            (rad, h), (rad + 8.0, -0.5))))
    triangles = []
    for i in range(len(angles) - 1):
        a = (angles[i] + angles[i + 1]) * 0.5
        if abs((a - south + math.pi) % math.tau - math.pi) < cut:
            continue
        lo0, mid0, top0, back0 = rows[i]
        lo1, mid1, top1, back1 = rows[i + 1]
        triangles.extend(((lo0, lo1, mid1), (lo0, mid1, mid0),
                          (mid0, mid1, top1), (mid0, top1, top0),
                          (top0, top1, back1), (top0, back1, back0)))
    return triangles


def _hill_y(a, r, ring=0):
    """Sample the actual faceted hill mesh, not its ideal radial profile.

    The crest is a polygon, not a circle; the analytic profile can put a
    tree metres above the visible slope between vertices.
    """
    x, z = r * math.cos(a), r * math.sin(a)
    height = 0.0  # the flat field covers the buried parts of the hill
    for p, q, t in _hill_surface_triangles(ring):
        den = (q[2] - t[2]) * (p[0] - t[0]) + (t[0] - q[0]) * (p[2] - t[2])
        if abs(den) < 1e-10:
            continue
        u = ((q[2] - t[2]) * (x - t[0]) + (t[0] - q[0]) * (z - t[2])) / den
        v = ((t[2] - p[2]) * (x - t[0]) + (p[0] - t[0]) * (z - t[2])) / den
        w = 1.0 - u - v
        if min(u, v, w) >= -1e-8:
            height = max(height, u * p[1] + v * q[1] + w * t[1])
    return height


def _ground_y(x, z):
    """Place the trunk base just below the visible ground at its centre."""
    a, r = math.atan2(z, x), math.hypot(x, z)
    return max(_hill_y(a, r, ring) for ring in range(len(HILL_RAD))) - 0.08


def _old_tree(seed):
    """Gnarled old fruit tree: live, leaning, dead (bare fork) or a stump."""
    m = Mesh()
    kind = (seed * 7) % 11
    s = 1.15 + 0.07 * (seed % 5)
    bark = _t("bark", TRUNK)
    if kind == 0:
        m.add(box(0.55, 0.42, 0.55, bark, center=(0, 0.21, 0)))
        m.add(box(0.30, 0.30, 2.1, _t("bark", P.WOOD_GREY)), rot_y(30 + seed * 13),
              t=(0.9, 0.15, 0.4))
        return m
    m.add(box(0.44, 1.5 * s, 0.44, bark, center=(0, 0.75 * s, 0)))
    if kind in (1, 5):
        grey = _t("bark", P.WOOD_GREY)
        for k, (ang, ln) in enumerate(((34, 1.9), (-28, 2.3), (52, 1.4))):
            sn, cs = math.sin(math.radians(ang)), math.cos(math.radians(ang))
            b = Mesh()
            b.add(box(0.16, ln * s, 0.16, grey), rot_z(ang),
                  t=(-sn * ln * s / 2.0, (1.4 + cs * ln / 2.0) * s, 0))
            b.add(box(0.09, 0.9 * s, 0.09, grey), rot_z(-ang * 0.4),
                  t=(-sn * ln * s * 0.85, (1.4 + cs * ln * 0.85 + 0.4) * s, 0))
            m.add(b, rot_y(k * 125 + seed * 17))
        return m
    for side in (-1, 1):
        m.add(box(0.18, 1.3 * s, 0.18, bark), rot_z(-side * 32), t=(side * 0.34 * s, 1.85 * s, 0))
    crown = _t("leaf", _v(LEAF, (seed % 5 - 2) * 4 - 4))
    m.add(_bipyr(0.15 * s, 2.9 * s, 0, 1.75 * s, 1.0 * s, 0.85 * s, crown, n=6))
    m.add(_bipyr(0.85 * s, 3.25 * s, 0.35 * s, 1.05 * s, 0.85 * s, 0.55 * s,
                 _v(crown, 9), n=5))
    if kind in (2, 8):
        lean = Mesh()
        lean.add(m, rot_z(13 if seed % 2 else -11))
        return lean
    return m


# Existing beyond-orchard trees the old rows grow round.
_OLD_SKIP = ((51, -13), (55, -10), (52, 12), (56, 17), (51, 27), (57, 29), (60, -23),
             (65, -16), (68, -10), (69, 10), (65, 17), (63, 24), (59, 33), (57, 40),
             (48, 26), (51, 15), (50, -13))


def old_orchard():
    """The farm's old orchard east of the hedge: irregular rows of big gnarled
    trees, long grass, a stone wall, and the bee and picking clutter."""
    m = Mesh()
    mown = _t("grass", P.GRASS_D)
    rough = _t("grass", P.GRASS_DRY)
    plank = _t("plank", WOOD)
    i = 0
    for row, x in enumerate((53.0, 58.5, 64.0, 69.0)):
        m.add(quad_xz(x - 1.4, -27, x + 1.4, 36, 0.03, mown, layer=1, seg=6))
        m.add(quad_xz(x + 2.0, -27, x + 3.5, 36, 0.032, rough, layer=1, seg=6))
        for k in range(11):
            z = -25.0 + 5.8 * k + (row % 2) * 2.4
            if abs(z) < 3.0:
                continue
            h = (i * 37 + row * 11) % 13
            tx, tz = x + (h % 5 - 2) * 0.35, z + (h % 3 - 1) * 0.6
            i += 1
            if any(math.hypot(tx - ox, tz - oz) < 3.4 for ox, oz in _OLD_SKIP) or h == 6:
                continue
            m.add(_old_tree(i), rot_y((i * 53) % 360), t=(tx, _ground_y(tx, tz), tz))

    # Dry-stone wall along the far edge, a gap for the lane.
    stone = _t("stone", P.STONE_D)
    for k in range(36):
        z = -30.0 + 2.0 * k
        if abs(z + 1.0) < 2.0:
            continue
        hh = 0.78 + 0.07 * ((k * 5) % 4)
        y0 = _hill_y(math.atan2(z + 1.0, 73.0), math.hypot(73.0, z + 1.0)) - 0.2
        m.add(box(0.7, hh, 2.04, _v(stone, ((k * 3) % 5 - 2) * 4),
                  center=(73.0, y0 + hh / 2.0, z + 1.0)))
    for z in (-1.9, 1.9):
        m.add(box(0.8, 1.35, 0.8, _t("stone", STONE), center=(73.0, 0.67, z)))

    # Beehives on the headland, past the boundary hedge.
    for k, z in enumerate((18.5, 20.0, 21.6, 23.0)):
        x = 50.2 + 0.25 * (k % 2)
        m.add(box(0.62, 0.32, 0.52, WOOD_D, center=(x, 0.16, z)))
        m.add(box(0.5, 0.6, 0.44, _v(HIVE, (k % 3 - 1) * 8), center=(x, 0.62, z)))
        m.add(box(0.64, 0.08, 0.58, P.GALV_D, center=(x, 0.96, z)))
    # Picking crates stacked by the lane.
    for k, (dx, dy, dz) in enumerate(((0, 0, 0), (0.8, 0, 0.1), (0.4, 0.55, 0.05),
                                      (0, 0, 0.75), (0.1, 0.55, 0.7))):
        m.add(box(0.75, 0.55, 0.65, _v(plank, (k % 3 - 1) * 9),
                  center=(49.6 + dx, 0.275 + dy, -3.6 - dz)))
    # A ladder left against the nearest live tree.
    lad = Mesh()
    pale = _t("plank", P.WOOD_GREY)
    for sx in (-0.24, 0.24):
        lad.add(box(0.07, 3.2, 0.07, pale, center=(sx, 1.6, 0)))
    for y in (0.5, 1.1, 1.7, 2.3, 2.9):
        lad.add(box(0.5, 0.05, 0.05, pale, center=(0, y, 0)))
    lean = Mesh()
    lean.add(lad, rot_z(-17))
    m.add(lean, rot_y(90), t=(53.0, 0, -6.4))
    # A collapsed lean-to: back wall, one post standing, one down, roof slid off.
    m.add(box(3.2, 1.2, 0.14, _t("plank", P.WOOD_GREY), center=(51.6, 0.6, 7.4)))
    m.add(box(0.14, 1.5, 0.14, plank, center=(50.2, 0.75, 5.6)))
    m.add(box(0.14, 0.14, 1.6, plank), rot_y(35), t=(52.8, 0.07, 5.4))
    m.face([(50.0, 1.25, 7.3), (53.2, 1.0, 7.3), (53.4, 0.05, 5.2), (50.1, 0.55, 5.4)],
           _t("tin", ROOF_METAL), 2, True)
    return m


def _poplar(seed, h):
    m = Mesh()
    leaf = _t("leaf", _v(LEAF, (seed % 3 - 1) * 5 - 6))
    m.add(box(0.36, h * 0.3, 0.36, _t("bark", TRUNK), center=(0, h * 0.15, 0)))
    w = 1.25 + 0.12 * (seed % 4)
    m.add(_bipyr(0, h * 0.42, 0, w, h * 0.58, h * 0.24, leaf, n=5, moon=True))
    m.add(_bipyr(0.3, h * 0.66, 0.2, w * 0.7, h * 0.26, h * 0.2, _v(leaf, 8), n=4, moon=True))
    return m


def poplars():
    """A windbreak of tall poplars on the hill foot, east to north-east: the
    raid opens facing them, so they carry the eastern skyline."""
    m = Mesh()
    a, k = math.radians(-38.0), 0
    while a < math.radians(56.0):
        h = 11.0 + 1.2 * ((k * 5) % 7) + (2.5 if k % 9 == 4 else 0.0)
        r = 77.0 + 1.6 * ((k * 3) % 3)
        y = _hill_y(a, r) - 0.15  # root the trunk in the actual slope
        if k % 11 != 7:     # a gap where one has come down
            m.add(_poplar(k, h), rot_y((k * 71) % 360),
                  t=(r * math.cos(a), y, r * math.sin(a)))
        a += math.radians((2.6, 4.2, 3.4, 5.0, 2.9)[k % 5])
        k += 1
    return m


def crest_woods():
    """Blocky woods along both hill crests (sparse clumps near, denser far)
    and a third, faint ridge; the road valley stays open."""
    m = Mesh()
    church = (_CHURCH_A - 0.36, _CHURCH_A + 0.36)
    for ring, (step, rad, col, keep) in enumerate(((2.1, 83.2, CREST_N, 5),
                                                   (2.4, 117.0, CREST_F, 8))):
        n = int(360 / step)
        for i in range(n):
            a = math.radians(i * step + ((i * 13) % 5) * 0.3)
            if _gap_u(a, 5.0, 17.0) < 1.0 or (ring == 0 and church[0] < a < church[1]):
                continue
            # Woods in clumps with open crest between, ragged at their edges.
            if (i // 6 * 7) % 11 >= keep or (i * 5) % 7 == 0:
                continue
            # Far woods only where the far crest clears the near one.
            if ring and _hill_h(a, 1) / 118.0 < _hill_h(a, 0) / 84.0 + 0.012:
                continue
            h = (i * 29 + ring * 5) % 7
            x, z = rad * math.cos(a), rad * math.sin(a)
            y = _hill_y(a, rad, ring) - 0.15
            c = _v(col, (h % 3 - 1) * 2)
            tall = (3.2 if ring == 0 else 5.0) + 0.45 * h
            # Visible trunks connect the crowns to the surface; keep the
            # foliage above the root rather than piercing the hill face.
            trunk_h = tall * 0.38
            m.add(box(0.30, trunk_h, 0.30, _v(c, -4),
                      center=(x, y + trunk_h / 2.0, z)))
            if h % 3 == 0:
                m.add(_bipyr(x, y + trunk_h + tall * 0.22, z, 1.0 + 0.1 * h, tall * 0.8, tall * 0.3, c,
                             _v(c, -3), n=4, moon=True))
            else:
                m.add(_bipyr(x, y + trunk_h + tall * 0.30, z, 1.9 + 0.2 * h, tall * 0.5, tall * 0.4, c,
                             _v(c, -3), n=5, moon=True))
    # Third ridge, near the fog: a saddle where the road crosses.
    n, rad = 72, 140.0
    rows = []
    for i in range(n + 1):
        a = math.tau * i / n
        u = _gap_u(a, 7.0, 22.0)
        h = 7.0 + (19.0 + 4.0 * math.sin(2 * a + 0.7) + 2.5 * math.sin(5 * a + 2.1) - 7.0) * u
        c, s = math.cos(a), math.sin(a)
        rows.append((((rad - 13.0) * c, 2.4 * (1.0 - u) - u, (rad - 13.0) * s),
                     (rad * c, h, rad * s)))
    for i in range(n):
        (lo0, top0), (lo1, top1) = rows[i], rows[i + 1]
        shade = ((i * 73) & 3) - 1
        m.face([lo0, lo1, top1], _v(FAR_RIDGE, shade - 1), 0, True)
        m.face([lo0, top1, top0], _v(FAR_RIDGE, shade + 1), 0, True)
    return m


def _valley_y(z):
    u = max(0.0, min(1.0, (-100.0 - z) / 28.0))
    return 2.4 * u * u * (3.0 - 2.0 * u)


def _walnut(seed):
    m = Mesh()
    leaf = _t("leaf", _v(LEAF, (seed % 3 - 1) * 5 - 2))
    m.add(box(0.4, 2.3, 0.4, _t("bark", TRUNK), center=(0, 1.15, 0)))
    m.add(box(0.16, 1.4, 0.16, _t("bark", TRUNK)), rot_z(40), t=(-0.45, 2.4, 0))
    m.add(_bipyr(0.2, 3.5, 0, 2.5, 1.3, 1.0, leaf, n=6))
    m.add(_bipyr(-0.9, 3.9, 0.5, 1.5, 0.9, 0.5, _v(leaf, 8), n=5))
    return m


# Wayside shrine lamp and far farmstead windows (raid halos).
SHRINE_AT = (6.5, -44.5)
SHRINE_LAMP = (6.22, 1.74, -44.5)


def _farmsteads():
    """(x, y, z, window x, window z) for three far farms on the hills."""
    out = []
    # On the near ring's inner face: hills draw as background (layer 0), so
    # anything behind a crest would show through it.
    for deg, ring, r in ((-72.0, 0, 79.5), (250.0, 0, 79.0), (151.0, 0, 80.0)):
        a = math.radians(deg)
        x, z = r * math.cos(a), r * math.sin(a)
        if abs(x) > abs(z):
            wx, wz = x - math.copysign(2.04, x), z
        else:
            wx, wz = x, z - math.copysign(1.79, z)
        out.append((x, _hill_y(a, r, ring) - 0.3, z, wx, wz))
    return out


def road_dressing(lit):
    """The truck road's country: dead sunflowers and a ploughed field either
    side, a walnut line, the wayside shrine, a culvert plank bridge, a broken
    cart, and the road climbing the valley to the pass."""
    m = Mesh()
    # Valley floor beyond the ground plane, rising to the third ridge's saddle.
    grass = _t("grass", _v(P.GRASS_D, 12))
    track = _t("track", TRACK)
    zs = [-99.5 - 4.0 * k for k in range(8)]
    for z0, z1 in zip(zs[:-1], zs[1:]):
        y0, y1 = _valley_y(z0), _valley_y(z1)
        for x0 in range(-60, 60, 20):
            m.face([(x0, y0, z0), (x0 + 20, y0, z0), (x0 + 20, y1, z1), (x0, y1, z1)],
                   grass, 0, True)
        m.face([(-3.2, y0 + 0.06, z0), (3.2, y0 + 0.06, z0), (3.2, y1 + 0.06, z1),
                (-3.2, y1 + 0.06, z1)], track, 1, True)
    m.face([(-3.0, 2.52, zs[-1]), (3.0, 2.52, zs[-1]), (2.6, 7.15, -140.5),
            (-2.6, 7.15, -140.5)], track, 1, True)

    # Dead sunflowers on the east verge: thin stalks, heavy drooping heads.
    stalk = _t("grass", STALK, tint=True)
    disc = [(0.25 * math.cos(math.tau * k / 6), 0.25 * math.sin(math.tau * k / 6))
            for k in range(6)]
    for row in range(6):
        x = 7.2 + 1.9 * row
        for k in range(10):
            h = (row * 31 + k * 17) % 13
            if h in (4, 9):
                continue
            z = -46.5 + 1.7 * k + (row % 2) * 0.7
            tall = 1.85 + 0.06 * (h % 7)
            p = Mesh()
            p.face([(-0.05, 0, 0), (0.05, 0, 0), (0.04, tall, 0), (-0.04, tall, 0)], stalk, 2, True)
            p.face([(0, 0, -0.05), (0, 0, 0.05), (0, tall, 0.04), (0, tall, -0.04)], stalk, 2, True)
            p.face([(0, tall * 0.55, 0), (0.42, tall * 0.42, 0.05), (0.36, tall * 0.38, -0.08)],
                   _v(stalk, -10), 2, True)
            head = Mesh()
            head.add(prism(disc, 0.11, _v(SEEDHEAD, (h % 3 - 1) * 5), z0=-0.055),
                     rot_x(34 + 5 * (h % 4)))
            p.add(head, rot_y(90), t=(0.16, tall - 0.12, 0))
            m.add(p, rot_y((h * 41) % 360), t=(x + (h % 3 - 1) * 0.15, 0, z))
    m.add(_hedgerow(18.6, -48.5, 18.6, -28.5, seed=61))
    m.add(_hedgerow(7.0, -48.6, 18.0, -48.6, seed=62))

    # Ploughed field west of the tree line, its own hedge between.
    m.add(quad_xz(-34, -52, -19.5, -26, 0.024, _t("dirt", FURROW), layer=1, seg=6))
    furrow = _t("furrow", P.TRACK_D)
    for k in range(17):
        x = -33.6 + 0.85 * k
        m.add(quad_xz(x, -51.6, x + 0.38, -26.4, 0.034, furrow, layer=1, seg=4))
    m.add(_hedgerow(-18.6, -52.5, -18.6, -26.0, seed=63))

    # Walnut line down the east verge, south of the sunflowers.
    for k, z in enumerate((-62.0, -70.5, -79.0, -88.0, -96.5)):
        m.add(_walnut(k), rot_y((k * 83) % 360), t=(6.9 + 0.3 * (k % 2), 0, z))

    # Wayside shrine: post, niche, little tin roof, cross; a lamp for the road.
    sx, sz = SHRINE_AT
    grey = _t("plank", P.WOOD_GREY)
    m.add(box(0.16, 1.5, 0.16, WOOD_D, center=(sx, 0.75, sz)))
    m.add(box(0.46, 0.62, 0.62, grey, center=(sx, 1.78, sz)))
    m.add(box(0.03, 0.44, 0.42, P.INK, center=(sx - 0.235, 1.76, sz)))
    roof = Mesh()
    roof.add(_gable_z(0.62, 0.82, 0.0, 0.32, _t("tin", ROOF_METAL), grey, oh=0.12), rot_y(90))
    m.add(roof, t=(sx, 2.09, sz))
    m.add(box(0.06, 0.55, 0.06, WOOD_D, center=(sx, 2.66, sz)))
    m.add(box(0.06, 0.06, 0.32, WOOD_D, center=(sx, 2.76, sz)))
    m.add(box(0.1, 0.14, 0.1, P.LAMP_WARM if lit else P.GLASS, center=SHRINE_LAMP,
              emissive=lit))
    m.add(box(0.7, 0.12, 0.9, _t("stone", P.STONE_D), center=(sx, 0.06, sz)))

    # Plank bridges over both drains at the field entrances.
    for x0, x1, z in ((4.0, 5.7, -53.0), (-5.7, -4.0, -54.5)):
        cx = (x0 + x1) / 2.0
        m.add(box(x1 - x0, 0.12, 2.4, _t("plank", P.WOOD_GREY), center=(cx, 0.06, z)))
        for dz in (-1.15, 1.15):
            m.add(box(x1 - x0 + 0.3, 0.16, 0.16, _t("plank", WOOD_D), center=(cx, 0.2, z + dz)))
        out = x1 + 4.2 if x0 > 0 else x0 - 4.2
        m.add(quad_xz(min(x1, out), z - 1.1, max(x0, out), z + 1.1, 0.045,
                      _t("track", P.TRACK_D), layer=1, seg=2))

    # A broken cart in the west verge: bed down on one corner, a wheel off.
    cart = Mesh()
    cart.add(box(2.6, 0.18, 1.4, _t("plank", P.WOOD_GREY), center=(0, 0, 0)))
    for z in (-0.66, 0.66):
        cart.add(box(2.6, 0.4, 0.07, _t("plank", WOOD_D), center=(0, 0.28, z)))
    cart.add(box(1.6, 0.08, 0.08, WOOD_D, center=(1.9, -0.1, 0.3)))
    tilt = Mesh()
    tilt.add(cart, rot_z(12))
    m.add(tilt, rot_y(74), t=(-7.4, 0.36, -67.0))
    prof = [(0.48 * math.cos(math.pi / 8 + k * math.pi / 4),
             0.48 + 0.48 * math.sin(math.pi / 8 + k * math.pi / 4)) for k in range(8)]
    wheel = Mesh()
    wheel.add(prism(prof, 0.1, WOOD_D, z0=-0.05))
    m.add(wheel, rot_y(74), t=(-6.95, -0.04, -66.0))
    flat = Mesh()
    flat.add(prism(prof, 0.1, _v(WOOD_D, -8), z0=-0.05), rot_x(90))
    m.add(flat, rot_y(20), t=(-8.6, 0.05, -69.2))

    # Far farmsteads on the hills, a lamplit window each.
    roof_c = _t("tile", _v(TILE, -18))
    wall = _t("plaster", FAR_WALL)
    win = WIN_LIT if lit else SKYLINE
    for x, y, z, wx, wz in _farmsteads():
        m.add(box(4.0, 2.6, 3.4, wall, center=(x, y + 1.3, z)))
        g = Mesh()
        g.add(_gable_z(3.4, 4.0, 2.6, 1.4, roof_c, wall), rot_y(90))
        m.add(g, t=(x, y, z))
        # Stone footing dug into the slope: the house sits in the hill, not on it.
        m.add(box(4.3, 1.6, 3.7, _t("stone", P.STONE_D), center=(x, y - 0.55, z)))
        m.add(box(2.4, 1.6, 2.2, _v(wall, -6), center=(x + 2.9, y + 0.8, z + 0.8)))
        sideways = abs(wx - x) > 0.1
        m.add(box(0.08 if sideways else 0.62, 0.5, 0.62 if sideways else 0.08, win,
                  center=(wx, y + 1.5, wz), emissive=lit))
    return m


def build_static(r, look, park=None):
    """Everything that never moves, added through the static-scene bake.
    ``park`` = (x, z, rot_y degrees) overrides the tractor's default spot."""
    add = _w.add
    for q in ground():
        add(r, q)
    add(r, hills())
    add(r, field_dressing())
    add(r, outer_dressing())       # new
    add(r, landscape_dressing(look))
    lit = look != "dawn"
    burn = look == "burn"
    add(r, old_orchard())
    add(r, poplars())
    add(r, crest_woods())
    add(r, road_dressing(lit))
    add(r, skyline(lit))
    add(r, poles())
    add(r, yard_dressing())
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
           (118.0, 8.0, 28.0, 3), (158.0, 19.0, 16.0, 2),
           # Low broken bank over the south road and the eastern poplars.
           (178.0, 9.5, 42.0, 2), (-142.0, 10.0, 24.0, 2), (136.0, 9.0, 30.0, 2),
           (92.0, 11.0, 40.0, 2), (52.0, 9.5, 24.0, 2))
_CLOUD = (5, 6, 11)             # added to the sky behind: a thin lit veil
_CLOUD_RIM = (13, 14, 21)


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
        lit = abs(((az - maz + 180) % 360) - 180) < 60
        for k in range(rows):
            ww = int(cw * (1.0 - 0.3 * k))
            x0 = int(cx - ww / 2 + (k * 7 % 5 - 2) * px_deg)
            y0 = int(cy - (k + 1) * rh)
            # Each row splits into two pieces with a ragged gap: broken cloud.
            cut = int(ww * (0.35 + 0.1 * ((i + k) % 3)))
            for a, b in ((x0, x0 + cut - rh), (x0 + cut + rh, x0 + ww)):
                if b - a > 1:
                    buf.fill(_CLOUD, (a, y0, b - a, rh), special_flags=pygame.BLEND_ADD)
                    if lit:
                        buf.fill(_CLOUD_RIM, (a + 1, y0, b - a - 2, 1),
                                 special_flags=pygame.BLEND_ADD)


# The raid's practicals: barn yard lamp, porch bulb, and the house windows
# (front face, world coords).  Chimney smoke rises from the stone stack.
HOUSE_WINDOWS = ((-15.0, 1.75, 6.88), (-12.8, 1.75, 6.88), (-8.4, 1.75, 6.88))
CHIMNEY_TOP = (-9.4, 5.2, 10.5)

_POOL_CACHE = {}


def _pool_img(rx, ry, col, k):
    key = (rx, ry, tuple(col), k)
    img = _POOL_CACHE.get(key)
    if img is None:
        img = pygame.Surface((rx * 2 + 2, ry * 2 + 2))
        img.fill((0, 0, 0))
        n = 24
        for i in range(n, 0, -1):
            f = i / float(n)
            b = k * (0.10 + 0.90 * (1.0 - f) ** 2)
            c = tuple(min(255, int(ch * b)) for ch in col)
            pygame.draw.ellipse(img, c, (rx + 1 - rx * f, ry + 1 - ry * f,
                                         rx * 2 * f + 1, ry * 2 * f + 1))
        if len(_POOL_CACHE) > 160:
            _POOL_CACHE.clear()
        _POOL_CACHE[key] = img
    return img


def pool(col, radius_m, intensity=0.3, squash=0.5):
    """A lamp's pool on the ground: a flattened radial wash that reads as lit
    earth on both backends (GL pools do not exist on the software path)."""
    def draw(s, sx, sy, scale, z):
        rx = int(min(240, radius_m * scale))
        if rx < 3:
            return
        ry = max(2, int(min(160, rx * squash)))
        k = int(round(intensity * 24.0)) / 24.0
        if k <= 0.02:
            return
        img = _pool_img(rx, ry, col, k)
        s.blit(img, (int(sx) - img.get_width() // 2, int(sy) - img.get_height() // 2),
               special_flags=pygame.BLEND_ADD)
    draw.light = True
    draw.light_soft = True
    draw.bounds_m = (radius_m, radius_m * squash)
    draw.bounds_cap_px = (240, 160)
    return draw


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
        # Warm wash on the wall behind each bulb and a pool on the yard: the
        # practicals have to read as lighting the set, not as floating dots.
        r.add_sprite((PORCH_LAMP[0], PORCH_LAMP[1] - 0.35, PORCH_LAMP[2] + 0.22),
                     pool((255, 168, 92), 2.1, intensity=0.55, squash=0.8),
                     layer=_fx.FX_LAYER)
        r.add_sprite((BARN_LAMP[0], BARN_LAMP[1] - 0.3, BARN_LAMP[2] + 0.24),
                     pool((255, 170, 96), 1.6, intensity=0.45, squash=0.8),
                     layer=_fx.FX_LAYER)
        r.add_sprite((PORCH_LAMP[0], 0.05, PORCH_LAMP[2] - 1.3),
                     pool((255, 196, 132), 3.2, intensity=0.34, squash=0.5),
                     layer=_fx.FX_LAYER)
        r.add_sprite((BARN_LAMP[0] + 1.6, 0.05, BARN_LAMP[2] - 1.2),
                     pool((255, 192, 128), 3.4, intensity=0.28, squash=0.5),
                     layer=_fx.FX_LAYER)
        for i, pos in enumerate(HOUSE_WINDOWS):
            r.add_sprite((pos[0], pos[1], pos[2] - 0.05),
                         _fx.window_glow(P.WINDOW, 0.9, 0.85, intensity=0.36, t=t,
                                         flicker=0.03, seed=11 + i),
                         layer=_fx.FX_LAYER)
            r.add_sprite((pos[0], 0.05, pos[2] - 0.95),
                         pool((255, 206, 138), 1.5, intensity=0.20, squash=0.55),
                         layer=_fx.FX_LAYER)
        for i, (vx, vz, vy, sides) in enumerate(_village()):
            if sides:
                r.add_sprite((vx, vy + 1.9, vz), _fx.glow(P.WINDOW, 0.9, t, seed=30 + i,
                                                          intensity=0.55, max_px=6),
                             layer=_fx.FX_LAYER)
        for i, (_x, y, _z, wx, wz) in enumerate(_farmsteads()):
            r.add_sprite((wx, y + 1.5, wz), _fx.glow(P.WINDOW, 1.0, t, seed=50 + i,
                                                     intensity=0.6, max_px=6),
                         layer=_fx.FX_LAYER)
        r.add_sprite(SHRINE_LAMP, _fx.glow(P.LAMP_WARM, 0.8, t, flicker=0.12, seed=57,
                                           core=(255, 232, 196), intensity=0.7, max_px=10),
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
        y0, y1 = y + _pole_y(z0), y + _pole_y(z1)
        for sx in (-0.7, 0.7):
            _sag(r, (x0 + sx, y0, z0), (x1 + sx, y1, z1), col)
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
        {"pos": PORCH_LAMP, "range": 6.0, "color": P.LAMP_WARM,
         "hot": (255, 236, 206), "intensity": 1.7},
    ]
    # Window spill: a warm patch on the yard in front of each lit pane.
    pools += [{"pos": (x, y + 0.2, z - 0.9), "range": 2.6, "color": P.WINDOW,
               "hot": (255, 232, 180), "intensity": 1.1} for x, y, z in HOUSE_WINDOWS]
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
            rad = min(80, max(2, int(size_m * scale * (0.34 + ph * 0.76))))
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


def burn_fx(r, t, grow=1.0, layer=_fx.FX_LAYER):
    """The burning barn and house: flames, smoke, window glow.  ``grow`` 0..1
    scales the flames up from a young fire to a roaring one."""
    g = 0.55 + 0.45 * grow
    for i, (dx, dy, dz, sz) in enumerate(((-3.6, 5.0, 10.0, 2.3), (-0.5, 5.4, 12.0, 2.7),
                                          (2.8, 5.0, 14.0, 2.4), (-2.0, 1.2, 6.2, 1.8),
                                          (2.2, 1.5, 6.3, 1.5), (4.2, 5.1, 10.5, 2.0))):
        fire(r, (13 + dx, dy, dz), t, seed=i * 3, size=sz * g, smoky=i % 2 == 0, layer=layer)
    for i, (x, y, sz) in enumerate(((-14.2, 4.5, 1.7), (-9.6, 4.3, 1.4))):
        fire(r, (x, y, 10.0), t, seed=20 + i, size=sz * g, smoky=i == 0, layer=layer)
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
