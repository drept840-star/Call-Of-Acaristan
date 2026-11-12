"""Mission 8 Revenge - Route 12 in 3D, shared by the trap fight, the kill and
the meet.

The layout is Mission 2's own map: ``missions.m2.world.MISSION2_MAP`` and the
2.5D set ``missions.m2.draw3d`` builds on it (booths, the control building and
security hut, the jersey barriers, the garden, the lamps, the yard dressing),
baked here with M8's pre-dawn light.  ``trap_world`` reads its solids from the
same grid.  The map border wall gives way to farmland, the burnt tanker still
lies where it blew in M2, the squad's cars are wrecks on the apron, and the sign
gantry by the control building stands at catwalk height with a ladder at its
east end.  Bodi's farm truck is parked in the south approach where M2 began.
``frame`` sets the camera, light and sky and opens the frame; callers add
actors and effects, then ``present``.

Axes: x east, y up, z north.  An M2 tile (col, row) sits at ``tile(col, row)``;
the M2 gantry deck centres on x 3.6, z 57.1.
"""
import math
import random

from engine3d import Mesh, box, prism, quad_xz, disc_xz, m_mul, rot_z, M_IDENT
from engine3d.core import Light, rot_y
from engine3d.textures import tex
from cutscenes import m7world3d as W7
from cutscenes import m7palette3d as P
from missions.m2 import sniper3d_set as SET

RES = (640, 448)                       # internal buffer; x1.5625 to the 1000x700 canvas
FOG = (112, 100, 108)
FOG_START, FOG_END = 30.0, 300.0
LIGHT = dict(direction=(-0.55, 0.40, 0.66), ambient=0.46, diffuse=0.60, sky=0.12,
             tint=(0.94, 0.84, 0.92))
SKY_TOP, SKY_BOT, SODIUM = (26, 32, 54), (156, 120, 112), (120, 78, 50)
DUSK_CLOUDS = dict(key="dusk", hor=SKY_BOT, sun=LIGHT["direction"],
                   rim=((118, 92, 96), (184, 126, 108)), body=(84, 76, 96))

TS = 1.6                               # metres per M2 tile (game.topdown3d.K * TILE_SIZE)
OX, OZ = -90.0, 100.3                  # M2 2.5D world (topdown3d.to3) -> this set
MAP_X0, MAP_X1 = OX, OX + 70 * TS      # the M2 map, border included
MAP_Z0, MAP_Z1 = OZ - 80 * TS, OZ


def tile(col, row):
    """Centre (x, z) of M2 tile (col, row)."""
    return (col + 0.5) * TS + OX, OZ - (row + 0.5) * TS


TRUCK_AT = (-76.0, -21.0, 8.0)        # x, z, yaw: Bodi's farm truck, where M2's squad set off
ROAD_X = (-80.5, -71.5)                # the approach road south out of the map
CATWALK_Y = 6.76                       # top of the catwalk grating
CATWALK_Z = 57.1                       # deck centre: M2 rows 26-27
DECK_X = (-2.0, 9.2)                   # M2 cols 55-61
DECK_D = 1.4
GANTRY_LEGS = (tile(56, 27), tile(59, 27))
GANTRY_Z = GANTRY_LEGS[0][1]
VASILE_AT = (3.6, CATWALK_Y, CATWALK_Z - 0.1)
LADDER_X = 8.7                         # hung off the deck's south edge, east end
LADDER_Z = CATWALK_Z - DECK_D / 2.0 - 0.15
TANKER = (tile(45, 37), 8.0, 3.0)      # (x, z), length, width: M2's tanker footprint, burnt out
# (x, z), yaw, burned: the squad's cars, left on the apron (trap_world.CARS)
CARS = [((-50.0, 2.0), 18, True), ((-40.0, 10.0), -24, True), ((-46.0, 20.0), 70, True),
        ((-30.0, 22.0), 8, False), ((-40.0, 31.0), -12, True), ((-44.0, 41.0), 30, True),
        ((-66.0, -6.0), 4, False), ((-58.0, -18.0), -6, True)]

ASPHALT = (50, 52, 56)
ASPHALT_B = (46, 48, 52)
LOT = (92, 94, 92)
YARD = (84, 82, 76)
STEEL = (78, 84, 90)
STEEL_D = (52, 56, 62)
SIGN_G = (38, 55, 52)

_cache = {}


def _t(name, col, tint=True):
    return tex(name, like=col, tint=tint)


def farm_truck():
    """Bodi's farm truck: faded blue cab, a timber flatbed, local forward +z."""
    m = _cache.get("truck")
    if m is not None:
        return m
    m = Mesh()
    paint = _t("steel", (70, 92, 112))
    trim, wood = (26, 26, 28), W7._t("plank", (108, 82, 54))
    m.add(box(1.9, 0.5, 4.8, (52, 54, 58), center=(0, 0.55, 0)))           # chassis
    m.add(box(1.9, 0.62, 1.6, paint, center=(0, 1.05, 1.55), seg=1.0))     # hood
    m.add(box(1.9, 1.05, 1.25, paint, center=(0, 1.38, 0.25), seg=1.0))    # cab
    m.add(box(1.92, 0.44, 1.0, (30, 40, 50), center=(0, 1.62, 0.3), skip=("top", "bottom")))
    m.add(box(1.4, 0.42, 1.27, (30, 40, 50), center=(0, 1.62, 0.25), skip=("left", "right", "top", "bottom")))
    m.add(box(1.96, 0.08, 1.3, paint, center=(0, 1.94, 0.25)))             # roof
    m.add(box(2.0, 0.1, 2.3, wood, center=(0, 0.85, -1.55), seg=1.0))      # bed
    for sx in (-0.98, 0.98):
        m.add(box(0.06, 0.42, 2.3, wood, center=(sx, 1.11, -1.55)))
        m.add(box(0.34, 0.08, 0.9, trim, center=(sx * 1.0, 0.76, 1.5)))    # wheel arches
    m.add(box(2.0, 0.42, 0.06, wood, center=(0, 1.11, -2.7)))
    m.add(box(1.7, 0.4, 0.04, _t("metal_rib", (120, 122, 114)), center=(0, 1.1, 2.36)))  # grille
    m.add(box(2.02, 0.16, 0.12, trim, center=(0, 0.62, 2.38)))            # bumper
    for sx in (-0.62, 0.62):
        m.add(box(0.3, 0.14, 0.03, (232, 222, 180), center=(sx, 1.12, 2.4), emissive=True))
        m.add(box(0.16, 0.1, 0.03, (190, 30, 26), center=(sx * 1.3, 0.8, -2.75), emissive=True))
    for wx in (-0.92, 0.92):
        for wz in (1.5, -1.6):
            m.add(box(0.28, 0.72, 0.72, trim, center=(wx, 0.36, wz)))
            m.add(box(0.3, 0.3, 0.3, (120, 118, 110), center=(wx, 0.36, wz)))
    m.add(box(0.9, 0.5, 0.6, _t("rust", (90, 84, 70)), center=(0.4, 1.15, -2.0)))   # jerrycans
    _cache["truck"] = m
    return m


def _wreck(col, burned):
    """A ``car_m2`` wreck at the box car's size (trap_world's 0.9 x 2.15 half box)."""
    try:
        from missions.m8.revenge import chase_set as CS
        return CS._asset("car_m2", 1.45, col, 0.62 if burned else 0.0, emissive=False)
    except (OSError, ValueError, ImportError):
        return SET.car(col, burned)


class _Shift:
    """Renderer stand-in for M2's 2.5D builders: what they add in M2 world
    space is baked into ours, moved by (OX, OZ)."""

    def __init__(self, r):
        self.r = r

    def bake(self, m):
        self.r.bake(Mesh().add(m, t=(OX, 0.0, OZ)))

    def add_dynamic(self, verts, faces, bias=0.0):
        self.bake(Mesh(list(verts), [(f[0], f[1], f[2], f[3], f[5]) for f in faces]))


def _glyph(col, row):
    from missions.m2.world import MISSION2_MAP
    if 0 <= row < len(MISSION2_MAP) and 0 <= col < len(MISSION2_MAP[row]):
        return MISSION2_MAP[row][col]
    return ""


def _floor(r):
    """One ground tile per M2 tile: asphalt, verge grass, the ditch, the
    service yard and the control building's lot."""
    from missions.m2 import draw3d as M2D
    looks = {".": ("pavement", ASPHALT), "g": ("grass", W7._v(W7.GRASS, -26)),
             "d": ("dirt", W7._v(P.TRACK_D, -30)), "s": ("concrete", YARD), "O": ("concrete", LOT),
             "X": ("concrete", LOT)}
    m = Mesh()
    for row in range(80):
        for col in range(70):
            g = _glyph(col, row)
            if g == "C":
                g = "g" if row in (0, 79) or col in (0, 69) else "O"
            if M2D._GARDEN.collidepoint(col, row) and row <= 6:
                g = "g"
            name, base = looks.get(g, ("pavement", ASPHALT))
            k = 1.0 + (((col * 73856093) ^ (row * 19349663)) % 9 - 4) * 0.012
            col3 = tuple(max(0, min(255, int(c * k))) for c in base)
            x0, z1 = col * TS + OX, OZ - row * TS
            face = W7._t("grass", col3) if name == "grass" else _t(name, col3, tint=name != "concrete")
            m.add(quad_xz(x0, z1 - TS, x0 + TS, z1, 0.0, face, layer=0))
    r.bake(m)


def _m2_set(r):
    """M2's 2.5D dressing on its own tiles: paint, barriers, garden, yard
    clutter, lamps, then the walls (booths, control building, hut)."""
    from missions.m1 import draw3d as M1D
    from missions.m2 import draw as M2
    from missions.m2 import draw3d as M2D
    sh = _Shift(r)
    T = M2D.T
    M2D._paint(sh)
    for row in range(80):
        for col in range(70):
            if _glyph(col, row) == "B":
                M2D._barrier(sh, col, row)
    M2D._garden(sh)
    for kind, ptx, pty, arg in M2._M2_DRESSING_PROPS:
        if _glyph(ptx, pty) in ("C", "B", "T", ""):
            continue
        x2, y2 = ptx * T + T / 2.0, pty * T + T / 2.0
        if kind in ("crates", "barrels", "coil"):
            M1D._dressing(sh, kind, x2, y2, arg)
        else:
            x, _, z = M2D._tc(ptx, pty)
            sh.bake(M2D._cart_mesh(kind, x, z))
    for col, row in M2D._POSTS:
        M2D._street_lamp(sh, col, row)
    for col, row in M2D._FLOODS:
        col3 = (255, 230, 180) if row == 34 else (220, 230, 255)
        M1D._lamp_fixture(sh, "fl_m2", col * T + T / 2.0, row * T + T / 2.0 + 0.9 / M2D.K, col3)
    for c0, r0, w, h, kind, _var in M2D._wall_boxes():
        if kind in ("border", "tower"):
            continue
        x, _, z = M2D.to3((c0 + w / 2.0) * T, (r0 + h / 2.0) * T)
        sh.bake(Mesh().add(M2D._wall_mesh(kind, w * TS, h * TS, M2D.WALL_H[kind]), t=(x, 0.0, z)))
        if kind == "facade":
            for tc in range(c0, c0 + w):
                for tr in range(r0, r0 + h):
                    M2D._facade_window(sh, tc, tr)
    rx, rz = tile(39, 36)                        # Darius's field radio, never picked up
    rad = Mesh()
    rad.add(box(0.42, 0.26, 0.24, (54, 62, 46), center=(rx, 0.13, rz)))
    rad.add(box(0.02, 0.6, 0.02, (16, 16, 16), center=(rx + 0.15, 0.55, rz - 0.05)))
    r.bake(rad)


def _gantry(r):
    """M2's sign gantry by the control building (legs on cols 56 and 59, the
    deck across cols 55-61), raised to catwalk height, signs under the deck."""
    steel, steel_d = _t("steel", STEEL), _t("steel", STEEL_D)
    y, (x0, x1), zc, d = CATWALK_Y, DECK_X, CATWALK_Z, DECK_D
    g = Mesh()
    for lx, lz in GANTRY_LEGS:
        for dx in (-0.25, 0.25):
            g.add(box(0.16, y, 0.16, steel, center=(lx + dx, y / 2.0, lz), seg=2.2))
        for k in range(1, 6):
            g.add(box(0.56, 0.06, 0.06, steel_d, center=(lx, y * k / 6.0, lz)))
        g.add(box(0.9, 0.2, 0.9, _t("concrete", (104, 100, 92), tint=False), center=(lx, 0.1, lz)))
        g.add(box(0.12, 0.12, d, steel_d, center=(lx, y - 0.2, zc)))
    g.add(box(x1 - x0, 0.3, 0.3, steel, center=((x0 + x1) / 2.0, y - 0.25, GANTRY_Z), seg=2.5))
    g.add(box(x1 - x0, 0.08, d, _t("metal_rib", (60, 64, 70)), center=((x0 + x1) / 2.0, y - 0.04, zc),
              seg=3.0))
    gap = (LADDER_X - 0.4, LADDER_X + 0.4)     # the south rail opens onto the ladder
    for dz in (-d / 2.0, d / 2.0):
        runs = ((x0, gap[0]), (gap[1], x1)) if dz < 0 else ((x0, x1),)
        for a, b in runs:
            g.add(box(b - a, 0.05, 0.05, steel_d, center=((a + b) / 2.0, y + 1.0, zc + dz), seg=3.0))
            g.add(box(b - a, 0.04, 0.04, steel_d, center=((a + b) / 2.0, y + 0.5, zc + dz), seg=3.0))
        n = 8
        for i in range(n):
            px = x0 + i * (x1 - x0) / (n - 1)
            if dz < 0 and gap[0] - 0.1 < px < gap[1] + 0.1:
                px = gap[0] if px < LADDER_X else gap[1]
            g.add(box(0.05, 1.0, 0.05, steel_d, center=(px, y + 0.5, zc + dz)))
        if dz < 0:
            g.add(box(0.05, 1.0, 0.05, steel_d, center=(gap[1], y + 0.5, zc + dz)))
    for sx in (tile(56, 26)[0] + 0.96, tile(59, 26)[0] + 1.28):
        g.add(box(2.6, 1.0, 0.08, SIGN_G, center=(sx, y - 0.9, zc - d / 2.0 - 0.05)))
        for i, w in enumerate((1.8, 1.1)):
            g.add(box(w, 0.14, 0.01, (220, 226, 220), center=(sx, y - 0.7 - i * 0.36, zc - d / 2.0 - 0.095)))
    r.bake(g)


def _tanker():
    """M2's burnt-out tanker, years on: chassis, split shell, ribs."""
    _xz, L, W = TANKER
    m = Mesh()
    black, rust = (24, 21, 19), (60, 34, 24)
    m.add(box(L * 0.95, 0.35, W * 0.8, black, center=(0.0, 0.45, 0.0)))
    m.add(box(L * 0.16, 1.1, W * 0.9, (34, 28, 24), center=(-L * 0.4, 0.95, 0.0)))
    for side in (-1, 1):
        m.add(box(L * 0.66, 0.6, 0.12, _t("rust", rust), center=(L * 0.1, 0.95, side * W * 0.42)))
    for i in range(8):
        x = -L * 0.22 + i * (L * 0.66) / 7.0
        h = 0.8 + (i * 5 % 7) * 0.12
        for side in (-1, 1):
            m.add(box(0.1, h, 0.1, rust if i % 3 else black, center=(x, 0.6 + h / 2.0, side * W * 0.36)))
        m.add(box(0.1, 0.1, W * 0.72, black, center=(x, 0.6 + h, 0.0)))
    return m


def _wrecks(r):
    rng = random.Random(1212)
    pal = [(112, 40, 36), (60, 74, 92), (140, 132, 112)]
    scorch = tex("scorch", like=(30, 28, 28), tint=True)
    for (cx, cz), yaw, burned in CARS:
        col = rng.choice(pal)
        if burned:
            r.bake(quad_xz(cx - 1.8, cz - 2.4, cx + 1.8, cz + 2.4, 0.015, scorch, layer=1, seg=4.8))
        r.bake(_wreck(col, burned), rot_y(yaw), (cx, 0.0, cz))
    (tx, tz), L, W = TANKER
    r.bake(quad_xz(tx - L * 0.8, tz - W * 1.4, tx + L * 0.8, tz + W * 1.4, 0.015, scorch, layer=1, seg=4.0))
    r.bake(_tanker(), M_IDENT, (tx, 0.0, tz))
    deb = Mesh()
    for _ in range(60):
        x, z = rng.uniform(-60, -12), rng.uniform(-4, 44)
        if _glyph(int((x - OX) / TS), int((OZ - z) / TS)) not in (".", "d"):
            continue
        s = rng.uniform(0.08, 0.3)
        deb.add(box(s, s * 0.5, s * 1.2, rng.choice([(40, 40, 40), (90, 80, 60), (120, 118, 110)]),
                    center=(x, s * 0.25, z)), rot_y(rng.uniform(0, 90)))
    r.bake(deb)


def _off_map(x0, z0, x1, z1, pad=3.0):
    """True when the rectangle clears the M2 map and the approach road."""
    if x1 > MAP_X0 - pad and x0 < MAP_X1 + pad and z1 > MAP_Z0 - pad and z0 < MAP_Z1 + pad:
        return False
    return not (x1 > ROAD_X[0] - pad and x0 < ROAD_X[1] + pad and z0 < MAP_Z0)


def _country(r):
    """The approach road south, the Guard track north, fields, hedges,
    poplars, a farm, the power line and the town past the map edge."""
    rng = random.Random(1213)
    m = Mesh()
    m.add(quad_xz(-320.0, -200.0, 320.0, 360.0, -0.06, W7._t("grass", W7._v(W7.GRASS, -26)),
                  layer=0, seg=40.0))
    m.add(quad_xz(ROAD_X[0], -260.0, ROAD_X[1], MAP_Z0, -0.01, _t("pavement", ASPHALT), layer=0, seg=8.0))
    for ex in (ROAD_X[0] + 0.3, ROAD_X[1] - 0.3):
        m.add(quad_xz(ex - 0.08, -260.0, ex + 0.08, MAP_Z0, 0.0, (196, 160, 52), layer=1, seg=12.0))
    cx = (ROAD_X[0] + ROAD_X[1]) / 2.0
    z = -258.0
    while z < MAP_Z0 - 3.0:
        m.add(quad_xz(cx - 0.07, z, cx + 0.07, z + 3.0, 0.0, (196, 196, 186), layer=1))
        z += 9.0
    m.add(quad_xz(-32.0, MAP_Z1, -27.2, 340.0, -0.02, W7._t("dirt", P.TRACK_D), layer=0, seg=12.0))
    kinds = (("stubble", W7._v(W7.STUBBLE, -34)), ("furrow", W7._v(P.TRACK_D, -24)),
             ("grass", W7._v(W7.GRASS, -34)))
    z = -190.0
    while z < 340.0:
        z1 = z + rng.uniform(45.0, 85.0)
        x = -300.0
        while x < 300.0:
            x1 = x + rng.uniform(30.0, 70.0)
            if rng.random() < 0.8 and _off_map(x, z, x1, z1, 1.0) and not (x < -27.2 and x1 > -32.0 and z1 > MAP_Z1):
                name, col = kinds[rng.randrange(3)]
                m.add(quad_xz(x + 0.5, z + 0.5, x1 - 0.5, z1 - 0.5, -0.045, W7._t(name, col), layer=0, seg=24.0))
            x = x1
        roll = rng.random()
        for side, xa in ((-1, MAP_X0 - 4.0), (1, MAP_X1 + 4.0)):
            if roll < 0.45:
                xb = xa + side * rng.uniform(60.0, 150.0)
                m.add(W7._hedgerow(min(xa, xb), z, max(xa, xb), z, seed=int(z) % 41))
            elif roll < 0.7:
                xp, k = xa, 0
                while abs(xp - xa) < 80.0:
                    m.add(W7._poplar(k, 10.0 + (k * 5) % 7), t=(xp, 0.0, z))
                    xp += side * rng.uniform(6.0, 8.0)
                    k += 1
        z = z1
    for k in range(40):
        maker = (W7.tree, W7._shelter_tree, W7._walnut)[k % 3]
        x, z = rng.uniform(-200.0, 140.0), rng.uniform(-170.0, 260.0)
        if _off_map(x - 3, z - 3, x + 3, z + 3) and not (-36.0 < x < -23.0 and z > MAP_Z1):
            m.add(maker(k), rot_y(rng.uniform(0, 360)), (x, 0.0, z))
    m.add(W7.house_ruin(), rot_y(-90), (-130.0, 0.0, -10.0))     # Bodi's farm, burned in M7
    m.add(W7.barn_ruin(), rot_y(-90), (-140.0, 0.0, 14.0))
    m.add(W7._farm_silo(), t=(-126.0, 0.0, 28.0))
    m.add(W7.shed(), rot_y(-90), (-126.0, 0.0, -28.0))
    m.add(quad_xz(-126.0, -12.0, -92.0, -8.0, -0.03, W7._t("dirt", P.TRACK_D), layer=1, seg=4.0))
    m.add(W7._landscape_water_tower(), t=(58.0, 0.0, 86.0))
    m.add(W7._landscape_hut(True), rot_y(90), (46.0, 0.0, -40.0))
    for z in range(-180, 340, 46):              # power line east
        m.add(W7._pole(), t=(34.0, 0.0, float(z)))
    r.bake(m)
    hills = Mesh()
    for i in range(16):
        hills.add(W7._bipyr(-330.0 + i * 40.0, 0.0, 360.0 + rng.uniform(-20, 20), rng.uniform(50, 80),
                            rng.uniform(22, 42), 1.0, W7._v(W7.HILL_F, -20), n=7))
    for side in (-1, 1):
        for i in range(10):
            hills.add(W7._bipyr(side * rng.uniform(250, 300) - 30.0, 0.0, -160.0 + i * 55.0,
                                rng.uniform(50, 80), rng.uniform(16, 34), 1.0, W7._v(W7.HILL_F, -24), n=7))
    hills.add(W7._bipyr(-40.0, 0.0, -240.0, 160.0, 26.0, 1.0, W7._v(W7.HILL_F, -24), n=9))
    r.bake(hills)
    sk = Mesh()                                  # the town north of the plaza, lit windows
    for i in range(46):
        x = -260 + i * 10 + rng.uniform(-3, 3)
        z = 225 + rng.uniform(0, 60)
        h = rng.uniform(8, 26) if abs(x + 30) > 40 else rng.uniform(14, 40)
        w = rng.uniform(6, 14)
        c = rng.randint(54, 66)
        sk.add(box(w, h, w, _t("concrete", (c, c + 2, c + 10)), center=(x, h / 2, z), skip=("bottom",)))
        for _ in range(rng.randint(2, 8)):
            wy = rng.uniform(2, h - 2)
            wx = x + rng.uniform(-w / 2 + 1, w / 2 - 1)
            sk.add(box(0.9, 0.7, 0.1, (210, 172, 100), center=(wx, wy, z - w / 2 - 0.06), emissive=True))
    r.bake(sk)


def _clear_of(x, z, rad):
    """True when a prop of radius ``rad`` at (x, z) misses the map, the road,
    the Guard track, the farms and the landmarks."""
    if not _off_map(x - rad, z - rad, x + rad, z + rad, 2.0):
        return False
    if -37.0 < x < -22.0 and z > MAP_Z1 - 2.0:
        return False
    for (cx, cz), keep in (((-132.0, 2.0), 26.0), ((76.0, 18.0), 22.0), ((-84.0, 150.0), 20.0),
                           ((58.0, 86.0), 8.0), ((46.0, -40.0), 7.0)):
        if math.hypot(x - cx, z - cz) < keep + rad:
            return False
    return abs(x - 34.0) > rad + 2.5


def _fill(r):
    """Close the empty country: a hedge round the map, copses and tree belts
    in the middle distance, two more farms, bales and road fences."""
    rng = random.Random(4417)
    m = Mesh()
    # the hedge round the M2 map, open for the approach road and the Guard track
    e = 2.5
    x0, x1, z0, z1 = MAP_X0 - e, MAP_X1 + e, MAP_Z0 - e, MAP_Z1 + e
    for a, b in ((x0, ROAD_X[0] - 1.0), (ROAD_X[1] + 1.0, x1)):
        m.add(W7._hedgerow(a, z0, b, z0, seed=3))
    for a, b in ((x0, -33.0), (-26.2, x1)):
        m.add(W7._hedgerow(a, z1, b, z1, seed=5))
    for x in (x0, x1):
        m.add(W7._hedgerow(x, z0, x, z1, seed=7 if x < 0 else 9))
    # post-and-rail along the approach road
    for x in (ROAD_X[0] - 1.5, ROAD_X[1] + 1.5):
        m.add(W7._fence(x, -200.0, x, MAP_Z0 - 4.0, gap=(-120.0, -112.0) if x < -76 else (-60.0, -52.0)))
    makers = (W7.tree, W7._shelter_tree, W7._walnut)
    # copses in the middle distance
    n = 0
    for k in range(60):
        if n >= 22:
            break
        cx, cz = rng.uniform(-230.0, 170.0), rng.uniform(-170.0, 230.0)
        if not _clear_of(cx, cz, 10.0):
            continue
        n += 1
        for i in range(rng.randint(6, 11)):
            x, z = cx + rng.uniform(-9.0, 9.0), cz + rng.uniform(-9.0, 9.0)
            m.add(makers[(k + i) % 3](k * 13 + i), rot_y(rng.uniform(0, 360)), (x, 0.0, z))
    # tree belts that close the horizon on three sides
    belts = ([(x, -150.0 + rng.uniform(-4, 4)) for x in range(-240, 200, 7)] +
             [(-215.0 + rng.uniform(-4, 4), z) for z in range(-140, 220, 7)] +
             [(165.0 + rng.uniform(-4, 4), z) for z in range(-140, 220, 7)])
    for i, (x, z) in enumerate(belts):
        if _clear_of(x, z, 3.0) and rng.random() < 0.85:
            m.add(makers[i % 3](i), rot_y(rng.uniform(0, 360)), (x, 0.0, z))
    # stray trees along the field edges near the map
    for k in range(70):
        x, z = rng.uniform(-150.0, 100.0), rng.uniform(-120.0, 200.0)
        if _clear_of(x, z, 3.0):
            m.add(makers[k % 3](200 + k), rot_y(rng.uniform(0, 360)), (x, 0.0, z))
    # a farm east of the power line and one north-west, off the Guard track
    m.add(W7.house(lit=True), rot_y(180), (76.0, 0.0, 12.0))
    m.add(W7.barn(), rot_y(90), (88.0, 0.0, 26.0))
    m.add(W7._farm_silo(), t=(70.0, 0.0, 30.0))
    m.add(W7.shed(), rot_y(0), (64.0, 0.0, 14.0))
    m.add(W7._fence(58.0, 0.0, 96.0, 0.0, gap=(72.0, 78.0)))
    m.add(quad_xz(36.0, 2.0, 74.0, 6.0, -0.03, W7._t("dirt", P.TRACK_D), layer=1, seg=4.0))
    m.add(W7.barn(), rot_y(0), (-84.0, 0.0, 156.0))
    m.add(W7.shed(), rot_y(90), (-96.0, 0.0, 144.0))
    m.add(W7._farm_windpump(), t=(-72.0, 0.0, 140.0))
    m.add(quad_xz(-72.0, 146.0, -32.0, 150.0, -0.03, W7._t("dirt", P.TRACK_D), layer=1, seg=4.0))
    # bales left in the stubble
    for x, z in ((-112.0, -60.0), (-150.0, 60.0), (52.0, -80.0), (96.0, 60.0), (-60.0, 130.0),
                 (20.0, 140.0), (-120.0, 100.0), (64.0, 130.0)):
        if _clear_of(x, z, 3.0):
            m.add(W7.hay(rng.randint(2, 4)), rot_y(rng.uniform(0, 360)), (x, 0.0, z))
    r.bake(m)


def renderer():
    """(renderer, None, 0), built and baked on first use."""
    got = _cache.get("r")
    if got is not None:
        return got
    from engine3d import Renderer  # lazy: the caller owns renderer import errors
    r = Renderer(RES[0], RES[1], fog=FOG, fog_start=FOG_START, fog_end=FOG_END)
    r.light = Light(**LIGHT)
    _floor(r)
    _m2_set(r)
    _gantry(r)
    _wrecks(r)
    _country(r)
    _fill(r)
    x, z, yaw = TRUCK_AT
    r.bake(farm_truck(), rot_y(yaw), (x, 0.0, z))
    r.bake(_ladder())
    _cache["r"] = (r, None, 0)
    return _cache["r"]


def _ladder():
    m = Mesh()
    col = _t("steel", (60, 64, 70))
    for sx in (-0.22, 0.22):
        m.add(box(0.05, CATWALK_Y + 1.0, 0.05, col,
                  center=(LADDER_X + sx, (CATWALK_Y + 1.0) / 2.0, LADDER_Z)))
    y = 0.3
    while y < CATWALK_Y + 0.6:
        m.add(box(0.44, 0.04, 0.04, col, center=(LADDER_X, y, LADDER_Z)))
        y += 0.32
    return m


def frame(eye, tgt, fov, lights=(), t=0, size=None):
    """Open a frame on the set from ``eye`` toward ``tgt``; returns the renderer.
    ``size`` is the films' letterbox buffer; play frames go back to ``RES``."""
    r = renderer()[0]
    r.resize(*(size or RES))
    r.set_camera(eye, tgt, fov, 0.0)
    r.fog, r.fog_start, r.fog_end = FOG, FOG_START, FOG_END
    r.light = Light(**LIGHT)
    try:
        r.set_lights(list(lights))
    except Exception:
        pass
    from cutscenes import m5fx3d as _sky  # lazy: numpy stack
    _sky.night_sky(r, r.surface, t, SKY_TOP, SKY_BOT, stars=36, moon=False, clouds=0,
                   sodium=SODIUM, mist=None, seed=8)
    from . import chase_set as _cs        # hard stratus streaks, not soft ellipse bands
    _cs.stratus(r, r.surface, t, DUSK_CLOUDS)
    r.begin()
    r.add_static()
    return r


def present(r, surface):
    """Flush the frame and upscale it crisp onto the canvas."""
    from cutscenes import m6fx3d as _fx  # lazy: numpy stack
    surf = r.surface
    r.flush(surf)
    try:
        _fx.grade_cine(surf)
    except Exception:
        pass
    _fx.present_crisp(surf, surface)
