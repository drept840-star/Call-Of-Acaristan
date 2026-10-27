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
from cutscenes import m6fx3d as _fx
from cutscenes import m6world3d as _w

GRASS = (78, 92, 54)
STUBBLE = (138, 122, 76)
FURROW = (104, 90, 58)
DIRT = (118, 96, 68)
TRACK = (134, 114, 84)
WOOD = (104, 78, 54)
WOOD_D = (66, 50, 38)
PLASTER = (178, 166, 142)
PLASTER_B = (88, 80, 72)
TILE = (126, 66, 50)
TILE_B = (52, 40, 36)
BARN = (112, 44, 38)
BARN_B = (78, 46, 42)
TRIM = (208, 198, 178)
ROOF_METAL = (84, 88, 96)
STONE = (132, 128, 120)
HAY = (196, 166, 84)
LEAF = (66, 96, 50)
LEAF2 = (84, 114, 58)
TRUNK = (74, 56, 42)
WIN = (28, 36, 48)
WIN_LIT = (255, 190, 110)
EMBER = (255, 120, 40)
TRACT = (66, 108, 72)
TRACT_D = (44, 76, 52)
RUB = (28, 28, 30)
HUB = (196, 160, 70)
METAL = (96, 100, 108)
RUST = (122, 70, 44)
HILL_N = (66, 78, 62)
HILL_F = (96, 104, 108)

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
    # The raid: a moonlit blue night lit enough to fight in.
    "raid": dict(
        fog=(24, 30, 46), fog_start=14.0, fog_end=120.0,
        light=dict(direction=(-0.3, 0.7, -0.4), ambient=0.46, diffuse=0.50,
                   sky=0.14, tint=(0.72, 0.80, 1.0)),
        sky_top=(8, 12, 26), sky_bot=(40, 48, 80), sodium=(60, 40, 28),
        stars=70),
    "burn": dict(
        fog=(26, 16, 16), fog_start=8.0, fog_end=96.0,
        light=dict(direction=(-0.3, 0.7, -0.4), ambient=0.30, diffuse=0.32,
                   sky=0.10, tint=(0.70, 0.70, 0.92)),
        sky_top=(8, 8, 16), sky_bot=(58, 28, 24), sodium=(120, 54, 24),
        stars=34),
}


def _v(col, k):
    return tuple(max(0, min(255, int(c + k))) for c in col)


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


def _fence(x0, z0, x1, z1, h=1.15, every=2.4, col=WOOD, gap=None):
    """Axis-aligned post-and-rail fence.  ``gap`` = (lo, hi) along the run."""
    m = Mesh()
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
    return [
        quad_xz(-100, -100, 100, 100, 0.0, GRASS, layer=0, seg=12,
                colfn=_vary(GRASS, 2)),
        quad_xz(-64, -12, -26, 34, 0.02, STUBBLE, layer=1, seg=6,
                colfn=_vary(STUBBLE, 2)),
        quad_xz(-20, -16, 20, 22, 0.02, DIRT, layer=1, seg=4,
                colfn=_vary(DIRT, 2)),
        quad_xz(-3.2, -100, 3.2, -16, 0.04, TRACK, layer=1, seg=8,
                colfn=_vary(TRACK, 2)),
        quad_xz(-7, -16, 7, -8, 0.04, TRACK, layer=1, seg=3,
                colfn=_vary(TRACK, 2)),
    ] + [quad_xz(x, -12, x + 0.9, 34, 0.05, FURROW, layer=1, seg=8)
         for x in range(-62, -26, 3)]


def hills():
    m = Mesh()
    n = 36
    for ring, (rad, base, col) in enumerate(((84.0, 7.0, HILL_N), (118.0, 14.0, HILL_F))):
        pts = []
        for i in range(n + 1):
            a = 2 * math.pi * i / n
            h = base + 3.5 * math.sin(a * 3 + ring) + 2.2 * math.sin(a * 7 + 1.3 * ring)
            pts.append((rad * math.cos(a), rad * math.sin(a), h))
        for i in range(n):
            (x0, z0, h0), (x1, z1, h1) = pts[i], pts[i + 1]
            m.face([(x0, -1, z0), (x1, -1, z1), (x1, h1, z1), (x0, h0, z0)],
                   col, 0, True)
    return m


def house(lit=False, burn=False):
    m = Mesh()
    W, D, H = 9.0, 6.0, 3.0
    wall = PLASTER_B if burn else PLASTER
    m.add(box(W, H, D, wall, center=(0, H / 2.0, 0)))
    roof = _gable_z(D, W, H, 1.9, TILE_B if burn else TILE, wall)
    m.add(roof, rot_y(90))
    m.add(box(0.7, 1.8, 0.7, STONE, center=(2.6, H + 1.2, 0.5)))
    zf = -D / 2.0 - 0.04
    for x in (-3.0, -0.8, 3.6):
        m.add(box(1.25, 1.15, 0.06, TRIM, center=(x, 1.75, zf)))
        m.add(box(0.95, 0.85, 0.08, WIN_LIT if lit else WIN,
                  center=(x, 1.75, zf - 0.02), emissive=lit))
    m.add(box(1.0, 2.1, 0.08, WOOD_D, center=(1.6, 1.05, zf)))
    m.add(box(5.0, 0.25, 1.6, WOOD, center=(1.0, 0.12, -D / 2.0 - 0.8)))
    for x in (-1.3, 3.3):
        m.add(box(0.14, 2.6, 0.14, WOOD, center=(x, 1.5, -D / 2.0 - 1.5)))
    m.face([(-1.6, 2.7, -D / 2.0 - 1.7), (3.6, 2.7, -D / 2.0 - 1.7),
            (3.6, 3.1, -D / 2.0), (-1.6, 3.1, -D / 2.0)], ROOF_METAL, 2, True)
    m.add(box(1.4, 0.12, 0.5, WOOD, center=(1.6, 0.04, -D / 2.0 - 1.85)))
    return m


def barn(burn=False):
    m = Mesh()
    W, D, H = 12.0, 10.0, 4.8
    side = BARN_B if burn else BARN
    m.add(box(W, H, D, side, center=(0, H / 2.0, 0)))
    zf = -D / 2.0 - 0.03
    if burn:
        m.add(box(5.0, 3.6, 0.1, EMBER, center=(0, 1.8, zf), emissive=True))
        m.add(box(1.6, 1.6, 0.1, EMBER, center=(0, H + 1.1, zf), emissive=True))
        m.add(_gable_z(W, D, H, 3.0, TILE_B, side, slopes=()))
    else:
        m.add(box(5.0, 3.6, 0.1, WOOD_D, center=(0, 1.8, zf)))
        for sx in (-1.25, 1.25):
            for ang in (40, -40):
                brace = Mesh()
                brace.add(box(0.14, 4.1, 0.05, TRIM, center=(0, 0, 0)), rot_z(ang))
                m.add(brace, t=(sx, 1.8, zf - 0.03))
        for x in (-2.6, 2.6):
            m.add(box(0.2, 3.7, 0.12, TRIM, center=(x, 1.85, zf - 0.02)))
        m.add(box(5.4, 0.2, 0.12, TRIM, center=(0, 3.7, zf - 0.02)))
        m.add(box(1.6, 1.6, 0.1, WOOD_D, center=(0, H + 1.1, zf)))
        m.add(box(1.9, 0.16, 0.12, TRIM, center=(0, H + 1.95, zf - 0.02)))
        m.add(_gable_z(W, D, H, 3.0, ROOF_METAL, side))
    return m


def hay(n=3):
    m = Mesh()
    for i in range(n):
        m.add(box(1.4, 0.7, 0.9, HAY, center=((i % 2) * 0.2, 0.35 + 0.7 * (i // 2), 0)))
    return m


def shed():
    m = Mesh()
    m.add(box(3.4, 2.4, 3.0, WOOD, center=(0, 1.2, 0)))
    m.face([(-1.9, 2.3, -1.7), (1.9, 2.3, -1.7), (1.9, 2.9, 1.7), (-1.9, 2.9, 1.7)],
           ROOF_METAL, 2, True)
    m.add(box(1.1, 1.9, 0.08, WOOD_D, center=(0.5, 0.95, -1.54)))
    for sx in (-0.4, 0.4):
        for sz in (-0.4, 0.4):
            m.add(box(0.12, 1.1, 0.12, WOOD_D, center=(3.4 + sx, 0.55, sz)))
    m.add(box(1.3, 0.8, 1.3, RUST, center=(3.4, 1.5, 0)))
    for i in range(3):
        m.add(box(0.5, 0.85, 0.5, _v(RUST, 14 * i - 14), center=(-2.5, 0.43, -0.6 + 0.65 * i)))
    return m


def well():
    m = Mesh()
    for sz in (-0.65, 0.65):
        m.add(box(1.7, 0.7, 0.35, STONE, center=(0, 0.35, sz)))
    for sx in (-0.65, 0.65):
        m.add(box(0.35, 0.7, 1.7, STONE, center=(sx, 0.35, 0)))
    m.add(box(0.9, 0.02, 0.9, (24, 34, 44), center=(0, 0.52, 0)))
    for sx in (-0.78, 0.78):
        m.add(box(0.12, 2.0, 0.12, WOOD, center=(sx, 1.35, 0)))
    m.add(box(1.8, 0.12, 0.12, WOOD, center=(0, 2.3, 0)))
    m.face([(-1.0, 2.3, -0.7), (1.0, 2.3, -0.7), (1.0, 2.8, 0), (-1.0, 2.8, 0)], ROOF_METAL, 2, True)
    m.face([(-1.0, 2.3, 0.7), (1.0, 2.3, 0.7), (1.0, 2.8, 0), (-1.0, 2.8, 0)], ROOF_METAL, 2, True)
    m.add(box(0.02, 0.9, 0.02, WOOD_D, center=(0, 1.85, 0)))
    m.add(box(0.24, 0.22, 0.24, WOOD_D, center=(0, 1.3, 0)))
    return m


def tree(seed=0):
    m = Mesh()
    s = 0.9 + 0.2 * ((seed * 37) % 7) / 7.0
    m.add(box(0.26, 1.7, 0.26, TRUNK, center=(0, 0.85, 0)))
    m.add(_bipyr(0, 2.3 * s, 0, 1.35 * s, 1.0 * s, 0.75 * s, LEAF))
    m.add(_bipyr(0.1, 3.1 * s, 0.05, 0.9 * s, 0.8 * s, 0.3 * s, LEAF2))
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


def build_static(r, look, park=None):
    """Everything that never moves, added through the static-scene bake.
    ``park`` = (x, z, rot_y degrees) overrides the tractor's default spot."""
    add = _w.add
    for q in ground():
        add(r, q)
    add(r, hills())
    lit = look != "dawn"
    burn = look == "burn"
    h = Mesh()
    h.add(house(lit=lit, burn=burn), t=(-12, 0, 10))
    add(r, h)
    b = Mesh()
    b.add(barn(burn=burn), t=(13, 0, 12))
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
    else:
        _w.night(r, buf, t, top=p["sky_top"], bot=p["sky_bot"], stars=p["stars"],
                 moon=False, sodium=p["sodium"], seed=seed)


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
    """Hard-edged flame sprite: red outer, orange middle, yellow core, embers."""
    def draw(s, sx, sy, scale, z):
        if scale < 0.4:
            return
        h = size_m * scale * (1.7 + 0.25 * math.sin(t * 0.011 + seed * 1.3)) * heat
        w = size_m * scale * 1.15
        for k, col in enumerate(((190, 52, 24), (244, 128, 32), (255, 214, 96))):
            fk = 1.0 - k * 0.27
            sway = math.sin(t * 0.009 + seed * 1.7 + k) * 0.14 * w
            pts = [(sx - w * 0.5 * fk, sy),
                   (sx - w * 0.30 * fk + sway * 0.5, sy - h * 0.55 * fk),
                   (sx + sway, sy - h * fk),
                   (sx + w * 0.30 * fk + sway * 0.5, sy - h * 0.55 * fk),
                   (sx + w * 0.5 * fk, sy)]
            pygame.draw.polygon(s, col, pts)
        for i in range(5):
            ph = ((t * 0.0006 + i * 0.21 + seed * 0.07) % 1.0)
            ex = sx + math.sin(i * 2.3 + seed) * w * 0.7 + math.sin(t * 0.004 + i) * 3
            ey = sy - h * (0.4 + ph * 1.4)
            if ph < 0.85:
                s.fill((255, 170, 70), (int(ex), int(ey), 2, 2))
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
            rad = max(2, int(size_m * scale * (0.5 + ph * 1.1)))
            ox = sx + math.sin(ph * 5 + seed + i) * size_m * scale * 0.5 + ph * size_m * scale * 0.9
            oy = sy - ph * size_m * scale * 4.6
            a = int(120 * (1.0 - ph))
            if a < 8:
                continue
            puff = pygame.Surface((rad * 2, rad * 2), pygame.SRCALPHA)
            pygame.draw.circle(puff, (18, 16, 18, a), (rad, rad), rad)
            s.blit(puff, (ox - rad, oy - rad))
    draw.bounds_m = (size_m * 2, size_m * 5)
    draw.bounds_cap_px = (140, 260)
    return draw


def fire(r, pos, t, seed=0, size=1.0, smoky=True):
    """Flame + halo + (optional) smoke column at a world point."""
    x, y, z = pos
    r.add_sprite((x, y, z), flame(t, seed, size), layer=_fx.FX_LAYER)
    r.add_sprite((x, y + size * 0.9, z),
                 _fx.glow((255, 150, 60), size * 3.2, t, flicker=0.12, seed=seed,
                          core=(255, 214, 140), intensity=0.9, max_px=80),
                 layer=_fx.FX_LAYER)
    if smoky:
        r.add_sprite((x, y + size * 2.0, z), smoke(t, seed, size * 0.9),
                     layer=_fx.FX_LAYER - 1)


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
