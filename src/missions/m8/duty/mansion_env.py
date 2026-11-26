"""Mission 8 Duty - Outer grounds, approach road, woodland, rolling foothills
and distant capital skyline surrounding Retardovici's estate (``mansion_set``).

Kept outside playable ``mansion_world.BOUNDS`` (except flat ``layer=1`` garden
walkways inside the lawns) and clear of ``flight3d``'s 48 m estate orbit and
``m8dutyfilms`` cameras.
"""
import math

from cutscenes import m6fx3d as _fx
from cutscenes import m7world3d as W7
from engine3d import Mesh, box, disc_xz, quad_xz
from engine3d.core import m_mul, rot_x, rot_y
from engine3d.textures import tex
from missions.m8.revenge import epilogue3d as E

_ORBIT_CX, _ORBIT_CZ = 0.0, 12.0

OUTER_LAMPS = (
    (-4.6, -58.0), (4.6, -58.0),
    (-4.6, -76.0), (4.6, -76.0),
    (-4.6, -104.0), (4.6, -104.0),
    (-4.6, -128.0), (4.6, -128.0),
    (-4.6, -156.0), (4.6, -156.0),
    (-36.0, -87.4), (-14.0, -87.4), (14.0, -87.4), (36.0, -87.4),
    (-64.0, -87.4), (64.0, -87.4),
)

_FLOOD_POLES = ((-22.0, 63.5), (22.0, 63.5))
_MAST_AT = (-42.0, 0.0, -182.0)
_TOWER_AT = (88.0, 148.0)
_SUB_BEACON = (24.6, 4.15, -108.6)
_SUB_GANTRY_H = 5.2

_POLES_NS = tuple((6.4, z) for z in (-54.0, -70.0, -85.5, -97.6, -116.0, -138.0, -162.0))
_POLES_W = tuple((x, -97.6) for x in (-12.0, -28.0, -44.0, -60.0, -76.0, -92.0))
_POLES_E = tuple((x, -97.6) for x in (16.0, 28.0, 44.0, 60.0, 76.0, 92.0))
_WIRE_COL = (28, 30, 36)


def hill_y(x, z):
    """Height (m) of the basin hills surrounding the estate (0 on the flat floor)."""
    r = math.hypot(x - _ORBIT_CX, z - _ORBIT_CZ)
    if r <= 108.0:
        return 0.0
    valley_u = 1.0
    if z < -60.0:
        half_w = 80.0 + (-60.0 - z) * 0.45
        excess = abs(x) - half_w
        if excess <= 0.0:
            return 0.0
        valley_u = min(1.0, excess / 45.0)
        valley_u = valley_u * valley_u * (3.0 - 2.0 * valley_u)
    if r < 175.0:
        u = (r - 108.0) / (175.0 - 108.0)
        radial = u * u * (3.0 - 2.0 * u)
    else:
        u = min(1.0, (r - 175.0) / (285.0 - 175.0))
        radial = 1.0 - 0.15 * u
    theta = math.atan2(x - _ORBIT_CX, z - _ORBIT_CZ)
    ridge = (
        16.0
        + 6.5 * math.cos(theta)
        + 4.5 * math.sin(2.0 * theta + 0.5)
        + 3.0 * math.cos(3.0 * theta - 0.7)
        + 2.0 * math.sin(5.0 * theta + 1.1)
    )
    return max(0.0, radial * ridge * valley_u)


def _conifer(m, x, y, z, h, spread, bark, leaf_a, leaf_b):
    sink = 0.15 if y > 0.1 else 0.0
    th = h * 0.36
    m.add(box(0.32, th, 0.32, bark, center=(x, y + th * 0.5 - sink, z)))
    for frac_y, frac_h, frac_w, col in (
        (0.46, 0.40, 1.00, leaf_a),
        (0.76, 0.34, 0.62, leaf_b),
    ):
        w = spread * frac_w
        m.add(box(w, h * frac_h, w, col, center=(x, y + h * frac_y, z)))


def _broadleaf(m, x, y, z, h, spread, bark, leaf_a, leaf_b):
    sink = 0.10 if y > 0.1 else 0.0
    th = h * 0.46
    m.add(box(0.28, th, 0.28, bark, center=(x, y + th * 0.5 - sink, z)))
    m.add(box(spread, h * 0.42, spread * 0.92, leaf_a, center=(x, y + h * 0.62, z)))
    m.add(box(spread * 0.68, h * 0.28, spread * 0.68, leaf_b,
              center=(x + spread * 0.14, y + h * 0.84, z - spread * 0.10)))


def _bush(m, x, y, z, w, h, d, leaf_a, leaf_b):
    m.add(box(w, h, d, leaf_a, center=(x, y + h * 0.45, z)))
    m.add(box(w * 0.68, h * 0.72, d * 0.72, leaf_b,
              center=(x + w * 0.22, y + h * 0.55, z - d * 0.14)))
    m.add(box(w * 0.56, h * 0.58, d * 0.62, leaf_a,
              center=(x - w * 0.24, y + h * 0.38, z + d * 0.16)))


def build_yard_detail(m):
    """Flat ``layer=1`` paths, lawn parterres and tree mulch inside the walls."""
    parterre = W7._t("grass", (42, 58, 36))
    flagstone = tex("ashlar", like=(102, 98, 92), tint=True)
    mulch = tex("m7_dirt", like=(54, 46, 36), density=12.0, tint=True)

    for s in (-1, 1):
        m.add(quad_xz(min(s * 10.5, s * 31.5), -40.5, max(s * 10.5, s * 31.5), -19.5,
                      0.014, parterre, layer=1, seg=10.5))
        m.add(quad_xz(min(s * 17.2, s * 31.5), 39.2, max(s * 17.2, s * 31.5), 54.5,
                      0.014, parterre, layer=1, seg=7.0))
        m.add(quad_xz(min(s * 14.0, s * 25.4), -12.4, max(s * 14.0, s * 25.4), -10.6,
                      0.024, flagstone, layer=1, seg=2.0))
        m.add(quad_xz(min(s * 23.6, s * 25.4), -10.6, max(s * 23.6, s * 25.4), 38.4,
                      0.024, flagstone, layer=1, seg=4.0))
        m.add(quad_xz(min(s * 9.2, s * 23.6), 36.8, max(s * 9.2, s * 23.6), 38.4,
                      0.024, flagstone, layer=1, seg=2.0))
        for k in range(4):
            m.add(disc_xz(s * (27.0 + 3.0 * (k % 2)), -12.0 + 14.0 * k, 1.35, 0.018, mulch, n=10))
        for k in range(3):
            m.add(disc_xz(s * 26.5, 40.5 + k * 6.0, 1.15, 0.018, mulch, n=10))


def _plain(m):
    # Match mansion_set._grounds base grass colour so (-80..80, -70..90) has no seam.
    outer_grass = W7._t("grass", (52, 68, 44))
    meadow = W7._t("grass", (40, 54, 36))
    stubble = tex("m7_stubble", like=(52, 56, 38), density=10.0, tint=True)
    furrow = tex("m7_furrow", like=(40, 44, 34), density=10.0, tint=True)

    for x0, z0, x1, z1 in (
        (-380.0, -380.0, 380.0, -70.0),
        (-380.0, 90.0, 380.0, 380.0),
        (-380.0, -70.0, -80.0, 90.0),
        (80.0, -70.0, 380.0, 90.0),
    ):
        m.add(quad_xz(x0, z0, x1, z1, 0.0, outer_grass, layer=0, seg=65.0))

    m.add(quad_xz(-82.0, -56.0, -39.8, 56.0, 0.014, meadow, layer=1, seg=20.0))
    m.add(quad_xz(47.2, -56.0, 82.0, 56.0, 0.014, meadow, layer=1, seg=20.0))
    m.add(quad_xz(-58.0, 64.0, 58.0, 100.0, 0.014, meadow, layer=1, seg=20.0))
    m.add(quad_xz(-76.0, -245.0, -8.0, -96.6, 0.014, stubble, layer=1, seg=25.0))
    m.add(quad_xz(8.0, -245.0, 76.0, -96.6, 0.014, furrow, layer=1, seg=25.0))


def _power_pole(m, x, z, yaw=0.0):
    hy = hill_y(x, z)
    wood = W7._t("plank", (76, 56, 38))
    insul = (212, 214, 208)
    p = Mesh()
    p.add(box(0.22, 7.6, 0.22, wood, center=(0.0, 3.65, 0.0)))
    p.add(box(1.55, 0.14, 0.14, wood, center=(0.0, 7.05, 0.0)))
    p.add(box(0.08, 0.75, 0.08, wood, center=(-0.38, 6.72, 0.0)))
    p.add(box(0.08, 0.75, 0.08, wood, center=(0.38, 6.72, 0.0)))
    for ox in (-0.56, 0.0, 0.56):
        p.add(box(0.10, 0.16, 0.10, insul, center=(ox, 7.18, 0.0)))
    m.add(p, rot_y(yaw), (x, hy, z))


def _wire_seg(m, a, b, thick=0.055):
    dx, dy, dz = b[0] - a[0], b[1] - a[1], b[2] - a[2]
    L = math.sqrt(dx * dx + dy * dy + dz * dz)
    if L < 1e-4:
        return
    yaw = math.degrees(math.atan2(dx, dz))
    pitch = -math.degrees(math.atan2(dy, math.hypot(dx, dz)))
    center = ((a[0] + b[0]) * 0.5, (a[1] + b[1]) * 0.5, (a[2] + b[2]) * 0.5)
    m.add(box(thick, thick, L, _WIRE_COL), m_mul(rot_y(yaw), rot_x(pitch)), center)


def _wire_span(m, a, b, sag=0.35):
    mid = ((a[0] + b[0]) * 0.5, (a[1] + b[1]) * 0.5 - sag, (a[2] + b[2]) * 0.5)
    _wire_seg(m, a, mid)
    _wire_seg(m, mid, b)


def _build_power_wires(m):
    h_top = 7.18
    for i in range(len(_POLES_NS) - 1):
        (x0, z0), (x1, z1) = _POLES_NS[i], _POLES_NS[i + 1]
        for ox in (-0.56, 0.56):
            _wire_span(m, (x0 + ox, hill_y(x0, z0) + h_top, z0), (x1 + ox, hill_y(x1, z1) + h_top, z1))
    for line in ((_POLES_NS[3],) + _POLES_E, (_POLES_NS[3],) + _POLES_W):
        for i in range(len(line) - 1):
            (x0, z0), (x1, z1) = line[i], line[i + 1]
            for oz in (-0.56, 0.56):
                _wire_span(m, (x0, hill_y(x0, z0) + h_top, z0 + oz), (x1, hill_y(x1, z1) + h_top, z1 + oz))
    for ox in (-0.56, 0.56):
        _wire_span(m, (28.0, h_top, -97.6 + ox), (29.5 + ox * 1.4, _SUB_GANTRY_H + 0.14, -102.5), sag=0.18)


def _roads(m):
    dirt = tex("m7_dirt", like=(68, 60, 48), density=12.0, tint=True)
    asphalt = tex("pavement", like=(44, 46, 52), density=24.0, tint=True)
    shoulder = tex("ashlar", like=(78, 76, 72), tint=True)
    fence_col = W7._t("plank", (68, 54, 40))

    m.add(quad_xz(-39.4, -44.0, -35.6, 62.6, 0.022, dirt, layer=1, seg=8.0))
    m.add(quad_xz(35.6, -44.0, 39.4, 62.6, 0.022, dirt, layer=1, seg=8.0))
    m.add(quad_xz(-35.6, 58.8, 35.6, 62.6, 0.022, dirt, layer=1, seg=8.0))
    m.add(quad_xz(39.6, -25.0, 47.0, -6.0, 0.024, dirt, layer=1, seg=4.0))
    m.add(quad_xz(-13.0, -58.5, -4.4, -50.5, 0.024, dirt, layer=1, seg=4.0))
    # Country lane pull-offs: farmstead, village cottages, substation apron and road-end drives
    m.add(quad_xz(-54.0, -109.0, -48.0, -96.4, 0.024, dirt, layer=1, seg=4.0))
    m.add(quad_xz(-33.0, -87.6, -29.0, -81.5, 0.024, dirt, layer=1, seg=4.0))
    m.add(quad_xz(24.0, -101.2, 32.0, -96.4, 0.024, shoulder, layer=1, seg=4.0))
    m.add(quad_xz(52.0, -103.5, 56.0, -96.4, 0.024, dirt, layer=1, seg=4.0))
    m.add(quad_xz(66.0, -87.6, 70.0, -81.5, 0.024, dirt, layer=1, seg=4.0))
    m.add(quad_xz(-98.0, -94.6, -94.0, -89.4, 0.024, dirt, layer=1, seg=2.0))
    m.add(quad_xz(94.0, -94.6, 98.0, -89.4, 0.024, dirt, layer=1, seg=2.0))

    m.add(quad_xz(-3.2, -48.6, 3.2, -47.02, 0.030, shoulder, layer=1, seg=2.0))
    m.add(quad_xz(-3.2, -265.0, 3.2, -48.6, 0.030, asphalt, layer=1, seg=12.0))
    m.add(quad_xz(-94.0, -95.2, -3.2, -88.8, 0.030, asphalt, layer=1, seg=12.0))
    m.add(quad_xz(3.2, -95.2, 94.0, -88.8, 0.030, asphalt, layer=1, seg=12.0))

    for s in (-1, 1):
        x0, x1 = (s * 3.2, s * 4.4) if s > 0 else (-4.4, -3.2)
        m.add(quad_xz(x0, -88.8, x1, -47.02, 0.024, shoulder, layer=1, seg=8.0))
        m.add(quad_xz(x0, -265.0, x1, -95.2, 0.024, shoulder, layer=1, seg=16.0))
    for side_z0, side_z1 in ((-96.4, -95.2), (-88.8, -87.6)):
        m.add(quad_xz(-94.0, side_z0, -4.4, side_z1, 0.024, shoulder, layer=1, seg=12.0))
        m.add(quad_xz(4.4, side_z0, 94.0, side_z1, 0.024, shoulder, layer=1, seg=12.0))

    stripe = (176, 174, 166)
    for z in range(-256, -50, 8):
        if -96 <= z <= -88:
            continue
        m.add(box(0.14, 0.012, 3.0, stripe, center=(0.0, 0.038, float(z))))
    for x in range(-90, 92, 8):
        if -5 <= x <= 5:
            continue
        m.add(box(3.0, 0.012, 0.14, stripe, center=(float(x), 0.038, -92.0)))

    for s in (-1, 1):
        m.add(W7._fence(s * 5.4, -86.5, s * 5.4, -50.5, h=0.95, every=2.6, col=fence_col))
        m.add(W7._fence(-84.0, -87.5, -7.0, -87.5, h=0.95, every=3.0, col=fence_col, gap=(-33.5, -28.5)))
        m.add(W7._fence(7.0, -87.5, 84.0, -87.5, h=0.95, every=3.0, col=fence_col, gap=(65.5, 70.5)))
    for x, z in OUTER_LAMPS:
        E._lamp_post(m, x, z)
    for x, z in _POLES_NS:
        _power_pole(m, x, z, yaw=0.0)
    for x, z in _POLES_W + _POLES_E:
        _power_pole(m, x, z, yaw=90.0)
    _build_power_wires(m)


def _bus_stop(m, x, z):
    concrete = tex("concrete", like=(112, 110, 104), density=12.0, tint=True)
    trim = (76, 78, 82)
    wood = W7._t("plank", (92, 62, 38))
    s = Mesh()
    s.add(box(5.2, 0.14, 3.2, concrete, center=(0.0, 0.05, 0.4)))
    s.add(box(4.6, 2.45, 0.18, concrete, center=(0.0, 1.32, -1.0)))
    s.add(box(0.18, 2.45, 2.1, concrete, center=(-2.21, 1.32, 0.05)))
    s.add(box(0.18, 2.45, 2.1, concrete, center=(2.21, 1.32, 0.05)))
    s.add(box(5.0, 0.18, 2.6, concrete, center=(0.0, 2.62, 0.18)))
    s.add(box(5.1, 0.10, 0.12, trim, center=(0.0, 2.60, 1.46)))
    # Wooden bench inside
    s.add(box(2.8, 0.08, 0.48, wood, center=(0.0, 0.50, -0.58)))
    s.add(box(2.8, 0.24, 0.06, wood, center=(0.0, 0.80, -0.84)))
    for lx in (-1.1, 1.1):
        s.add(box(0.10, 0.42, 0.42, trim, center=(lx, 0.28, -0.58)))
    # Faded poster on the back wall + roadside stop sign
    s.add(box(0.72, 0.96, 0.03, (176, 168, 144), center=(-0.6, 1.56, -0.89)))
    s.add(box(0.60, 0.18, 0.02, (132, 54, 48), center=(-0.6, 1.88, -0.87)))
    s.add(box(0.56, 0.48, 0.02, (124, 118, 102), center=(-0.6, 1.48, -0.87)))
    s.add(box(0.07, 2.55, 0.07, trim, center=(2.65, 1.28, 1.25)))
    s.add(box(0.42, 0.48, 0.05, (206, 178, 72), center=(2.65, 2.38, 1.25)))
    s.add(box(0.30, 0.24, 0.02, (36, 68, 118), center=(2.65, 2.40, 1.28)))
    m.add(s, t=(x, hill_y(x, z), z))


def _cottage(m, x, z, yaw=0.0, w=6.8, d=5.2, h=2.9, plaster_col=(192, 184, 166)):
    hy = hill_y(x, z)
    stone = tex("ashlar", like=(138, 134, 124), tint=True)
    plaster = tex("stucco", like=plaster_col, tint=True)
    tile = W7._t("tile", (122, 60, 48))
    wood = W7._t("plank", (74, 44, 28))
    warm = (238, 206, 140)
    c = Mesh()
    sink = 0.25 if hy > 0.1 else 0.0
    c.add(box(w + 0.4, 0.35 + sink, d + 0.4, stone, center=(0.0, 0.175 - sink * 0.5, 0.0)))
    c.add(box(w, h, d, plaster, center=(0.0, 0.35 + h * 0.5, 0.0)))
    c.add(W7._gable_z(d + 0.4, w + 0.4, 0.0, 1.6, tile, plaster, oh=0.28),
          rot_y(90.0), (0.0, 0.35 + h, 0.0))
    c.add(box(0.62, 1.45, 0.62, stone, center=(-w * 0.24, 0.35 + h + 0.95, d * 0.16)))
    # Front door (+z) and warm lit windows
    c.add(box(1.0, 2.05, 0.08, wood, center=(0.0, 1.38, d * 0.5 + 0.02)))
    c.add(box(1.9, 0.16, 1.0, tile, center=(0.0, 2.62, d * 0.5 + 0.45)))
    for sx in (-w * 0.28, w * 0.28):
        c.add(box(1.05, 1.05, 0.08, warm, center=(sx, 1.75, d * 0.5 + 0.02), emissive=True))
        c.add(box(1.05, 1.05, 0.08, warm, center=(sx, 1.75, -d * 0.5 - 0.02), emissive=True))
    for s in (-1, 1):
        c.add(box(0.08, 1.05, 1.1, warm, center=(s * (w * 0.5 + 0.02), 1.75, 0.0), emissive=True))
    m.add(c, rot_y(yaw), (x, hy, z))


def _substation(m, x, z):
    hy = hill_y(x, z)
    pad = tex("concrete", like=(96, 96, 92), density=12.0, tint=True)
    wall = tex("stucco", like=(128, 126, 118), tint=True)
    stone = tex("ashlar", like=(130, 126, 118), tint=True)
    steel = (56, 62, 60)
    dark = (36, 40, 44)
    insul = (212, 212, 206)
    s = Mesh()
    s.add(box(14.0, 0.12, 12.0, pad, center=(0.0, 0.06, 0.0)))
    # Perimeter security fence (open service gate on +z facing the east road)
    fx, fz = 6.9, 5.9
    for px in (-6.9, -4.6, -2.3, 2.3, 4.6, 6.9):
        s.add(box(0.10, 2.15, 0.10, dark, center=(px, 1.12, fz)))
        s.add(box(0.10, 2.15, 0.10, dark, center=(px, 1.12, -fz)))
    s.add(box(0.10, 2.15, 0.10, dark, center=(0.0, 1.12, -fz)))
    for pz in (-3.0, 0.0, 3.0):
        s.add(box(0.10, 2.15, 0.10, dark, center=(-fx, 1.12, pz)))
        s.add(box(0.10, 2.15, 0.10, dark, center=(fx, 1.12, pz)))
    for ry in (0.45, 1.25, 2.05):
        s.add(box(13.8, 0.06, 0.06, dark, center=(0.0, ry, -fz)))
        s.add(box(4.6, 0.06, 0.06, dark, center=(-4.6, ry, fz)))
        s.add(box(4.6, 0.06, 0.06, dark, center=(4.6, ry, fz)))
        s.add(box(0.06, 0.06, 11.8, dark, center=(-fx, ry, 0.0)))
        s.add(box(0.06, 0.06, 11.8, dark, center=(fx, ry, 0.0)))
    for gx in (-2.0, 2.0):
        s.add(box(0.08, 1.9, 2.1, dark, center=(gx, 1.05, fz - 1.0)))
    # Generator / control house with roof mast & red warning beacon
    s.add(box(5.0, 0.30, 5.2, stone, center=(-3.4, 0.25, -1.6)))
    s.add(box(4.7, 3.10, 4.8, wall, center=(-3.4, 1.95, -1.6)))
    s.add(box(5.1, 0.28, 5.2, (52, 54, 58), center=(-3.4, 3.58, -1.6)))
    s.add(box(1.8, 2.2, 0.08, dark, center=(-3.4, 1.45, 0.82)))
    s.add(box(0.08, 0.95, 1.2, (206, 226, 168), center=(-1.02, 2.15, -1.6), emissive=True))
    s.add(box(0.08, 0.55, 1.1, dark, center=(-1.02, 1.15, -3.0)))
    s.add(box(0.10, 0.55, 0.10, dark, center=(-3.4, 3.88, -1.6)))
    s.add(box(0.24, 0.24, 0.24, (230, 52, 42), center=(-3.4, 4.18, -1.6), emissive=True))
    # Two heavy oil-cooled transformers with cooling fins and ceramic bushings
    for tz in (-2.9, 1.1):
        s.add(box(2.5, 2.0, 2.2, steel, center=(2.8, 1.12, tz)))
        for fy in (-0.8, 0.0, 0.8):
            s.add(box(2.9, 1.5, 0.16, dark, center=(2.8, 1.08, tz + fy)))
        s.add(box(1.6, 0.55, 0.60, (82, 88, 86), center=(2.8, 2.40, tz)))
        for bx in (-0.7, 0.0, 0.7):
            s.add(box(0.14, 0.75, 0.14, insul, center=(2.8 + bx, 2.48, tz + 0.65)))
    # Steel H-frame gantry catching the overhead feeder
    for gx in (-0.5, 3.5):
        s.add(box(0.22, _SUB_GANTRY_H, 0.22, dark, center=(gx, _SUB_GANTRY_H * 0.5 + 0.1, 4.5)))
    s.add(box(4.6, 0.22, 0.22, dark, center=(1.5, _SUB_GANTRY_H - 0.1, 4.5)))
    for ix in (0.4, 1.5, 2.6):
        s.add(box(0.12, 0.28, 0.12, insul, center=(ix, _SUB_GANTRY_H + 0.14, 4.5)))
    m.add(s, t=(x, hy, z))


def _structures(m, car_fn):
    stone = tex("ashlar", like=(150, 146, 136), tint=True)
    plaster = tex("stucco", like=(198, 190, 170), tint=True)
    tile = W7._t("tile", (122, 60, 48))
    trim = tex("stucco", like=(226, 222, 210), tint=True)
    wood = W7._t("plank", (74, 44, 28))
    warm_glass = (238, 206, 140)

    # Gatehouse outside west wall (-7.8, -49.2)
    gx, gz = -7.8, -49.2
    m.add(box(3.8, 0.30, 3.0, stone, center=(gx, 0.15, gz)))
    m.add(box(3.5, 2.70, 2.7, plaster, center=(gx, 1.65, gz)))
    m.add(W7._gable_z(3.1, 3.9, 0.0, 1.1, tile, plaster, oh=0.25), rot_y(90.0), (gx, 3.0, gz))
    m.add(box(0.08, 1.1, 1.2, warm_glass, center=(gx + 1.77, 1.8, gz), emissive=True))
    m.add(box(1.1, 1.1, 0.08, warm_glass, center=(gx, 1.8, gz + 1.37), emissive=True))
    m.add(box(0.22, 1.25, 0.22, (42, 44, 48), center=(-4.1, 0.625, -47.6)))
    m.add(box(0.08, 2.60, 0.08, (206, 48, 42), center=(-4.1, 2.25, -47.6)))

    # West caretaker cottage (-52, 34) and glasshouse (-52, 20)
    wx, wz = -52.0, 34.0
    m.add(box(7.4, 0.35, 5.8, stone, center=(wx, 0.175, wz)))
    m.add(box(7.0, 3.00, 5.4, plaster, center=(wx, 1.85, wz)))
    m.add(W7._gable_z(5.8, 7.4, 0.0, 1.6, tile, plaster, oh=0.3), rot_y(90.0), (wx, 3.35, wz))
    m.add(box(0.65, 1.4, 0.65, stone, center=(wx - 1.8, 4.4, wz + 0.8)))
    for dz in (-1.2, 1.2):
        m.add(box(0.08, 1.2, 1.0, warm_glass, center=(wx + 3.52, 1.9, wz + dz), emissive=True))

    ghx, ghz = -52.0, 20.0
    m.add(box(4.6, 0.60, 7.0, stone, center=(ghx, 0.30, ghz)))
    m.add(box(4.2, 2.00, 6.6, (58, 92, 108), center=(ghx, 1.60, ghz), emissive=True))
    m.add(box(4.5, 0.16, 6.9, (38, 44, 46), center=(ghx, 2.68, ghz)))
    for z in (17.2, 20.0, 22.8):
        m.add(box(4.36, 2.1, 0.10, (38, 44, 46), center=(ghx, 1.65, z)))

    # East Guard barracks (52, -16) and garden pavilion (45.5, 28)
    bx, bz = 52.0, -16.0
    m.add(box(8.4, 0.40, 12.6, stone, center=(bx, 0.20, bz)))
    m.add(box(8.0, 3.40, 12.0, plaster, center=(bx, 2.10, bz)))
    m.add(W7._gable_z(8.4, 12.6, 0.0, 1.8, tile, plaster, oh=0.35), t=(bx, 3.80, bz))
    for dz in (-4.0, -1.4, 1.4, 4.0):
        m.add(box(0.08, 1.3, 1.1, warm_glass, center=(bx - 4.02, 2.2, bz + dz), emissive=True))
    m.add(W7._hedgerow(40.0, 23.0, 40.0, 33.0, seed=41))

    px, pz = 45.5, 28.0
    m.add(box(4.6, 0.30, 4.6, stone, center=(px, 0.15, pz)))
    for sx in (-1.8, 1.8):
        for sz in (-1.8, 1.8):
            m.add(box(0.28, 2.6, 0.28, trim, center=(px + sx, 1.60, pz + sz)))
    m.add(box(4.8, 0.24, 4.8, trim, center=(px, 2.98, pz)))
    m.add(box(4.2, 0.65, 4.2, tile, center=(px, 3.42, pz)))
    m.add(box(2.4, 0.60, 2.4, tile, center=(px, 3.98, pz)))
    m.add(box(0.28, 0.32, 0.28, warm_glass, center=(px, 2.65, pz), emissive=True))

    # North service pump house (-18, 64.5) and floodlight poles (+-22, 63.5)
    m.add(box(4.4, 2.6, 3.6, stone, center=(-18.0, 1.3, 64.5)))
    m.add(box(4.8, 0.3, 4.0, (54, 58, 62), center=(-18.0, 2.75, 64.5)))
    for fx, fz in _FLOOD_POLES:
        m.add(box(0.24, 6.2, 0.24, wood, center=(fx, 3.1, fz)))
        m.add(box(1.5, 0.16, 0.16, (48, 50, 54), center=(fx, 6.0, fz)))
        m.add(box(0.45, 0.24, 0.22, (236, 224, 188), center=(fx - 0.45, 5.92, fz - 0.16), emissive=True))
        m.add(box(0.45, 0.24, 0.22, (236, 224, 188), center=(fx + 0.45, 5.92, fz - 0.16), emissive=True))

    # West road: concrete bus stop, village cottage, small farmstead, road-end house
    fence_col = W7._t("plank", (68, 54, 40))
    _bus_stop(m, -20.0, -98.4)
    _cottage(m, -31.0, -79.0, yaw=180.0, w=6.4, d=5.0, plaster_col=(186, 178, 160))
    _cottage(m, -45.0, -108.5, yaw=12.0, w=6.8, d=5.2, plaster_col=(196, 188, 170))
    m.add(W7.barn(), rot_y(-82.0), (-63.0, 0.0, -116.0))
    m.add(W7.shed(), rot_y(8.0), (-57.0, 0.0, -104.5))
    m.add(W7.hay(3), rot_y(25.0), (-66.0, 0.0, -106.5))
    m.add(W7.hay(2), rot_y(-35.0), (-52.5, 0.0, -120.5))
    m.add(W7._fence(-69.0, -99.8, -38.0, -99.8, h=1.05, every=2.4, col=fence_col, gap=(-54.5, -48.5)))
    m.add(W7._fence(-69.0, -123.0, -69.0, -99.8, h=1.05, every=2.6, col=fence_col))
    m.add(W7._fence(-38.0, -123.0, -38.0, -99.8, h=1.05, every=2.6, col=fence_col))
    _cottage(m, -99.5, -92.0, yaw=90.0, w=6.6, d=5.2, plaster_col=(188, 180, 164))
    m.add(W7.shed(), rot_y(90.0), (-102.0, hill_y(-102.0, -83.5), -83.5))

    # East road: electrical substation, village cottages, road-end house
    _substation(m, 28.0, -107.0)
    _cottage(m, 54.0, -107.0, yaw=0.0, w=6.6, d=5.2, plaster_col=(194, 186, 168))
    m.add(W7._fence(44.0, -99.8, 63.0, -99.8, h=1.0, every=2.4, col=fence_col, gap=(51.5, 56.5)))
    m.add(W7._fence(44.0, -114.0, 44.0, -99.8, h=1.0, every=2.6, col=fence_col))
    m.add(W7._fence(63.0, -114.0, 63.0, -99.8, h=1.0, every=2.6, col=fence_col))
    m.add(box(3.4, 2.2, 2.8, W7._t("plank", (74, 52, 34)), center=(58.5, 1.1, -112.0)))
    _cottage(m, 68.0, -79.0, yaw=180.0, w=6.4, d=5.0, plaster_col=(184, 178, 162))
    _cottage(m, 99.5, -92.0, yaw=-90.0, w=6.8, d=5.2, plaster_col=(190, 182, 166))
    m.add(W7.hay(2), rot_y(18.0), (96.0, hill_y(96.0, -83.0), -83.0))

    if car_fn is not None:
        m.add(car_fn((28, 32, 42), False), rot_y(16.0), (-9.5, 0.02, -54.5))
        m.add(car_fn((28, 32, 42), False), rot_y(90.0), (42.5, 0.02, -19.5))
        m.add(car_fn((24, 26, 30), False), rot_y(92.0), (42.5, 0.02, -12.0))


def _trees(m):
    bark = tex("m7_bark", like=(68, 50, 38), density=14.0, tint=True)
    leaf_a = tex("m7_leaf", like=(30, 48, 30), density=12.0, tint=True)
    leaf_b = tex("m7_leaf", like=(40, 60, 36), density=12.0, tint=True)
    pine_a = tex("m7_leaf", like=(24, 40, 28), density=12.0, tint=True)
    pine_b = tex("m7_leaf", like=(32, 50, 32), density=12.0, tint=True)

    # West orchard (kept <= 4.1 m under flight3d climb)
    for ix in range(2):
        for iz in range(4):
            _broadleaf(m, -53.0 + ix * 7.5, 0.0, -28.0 + iz * 10.5, 4.1, 2.4, bark, leaf_a, leaf_b)

    # Roadside trees outside the gate (south of approach_aerial)
    for s in (-1, 1):
        for k, kz in enumerate((-66.0, -78.0, -104.0, -118.0, -134.0)):
            px = s * (9.5 + (k * 3) % 7)
            if k % 2 == 0:
                m.add(W7.tree(30 + k + (s > 0) * 7), t=(px, 0.0, kz))
            else:
                _broadleaf(m, px, 0.0, kz, 7.2 + (k % 3), 3.4, bark, leaf_a, leaf_b)

    # Clusters of trees and bushes lining both country lanes
    lane_groves = (
        # West road verges (north and south)
        (-11.5, -83.0, 7.2, 3.2, 0), (-14.5, -81.0, 6.4, 2.8, 1),
        (-44.0, -82.5, 7.8, 3.6, 1), (-48.5, -81.0, 6.8, 3.0, 2),
        (-74.0, -82.5, 8.2, 3.8, 0), (-79.5, -80.5, 7.2, 3.2, 1),
        (-33.5, -101.5, 7.4, 3.4, 1), (-36.5, -103.5, 6.2, 2.8, 0),
        (-76.0, -101.8, 7.8, 3.6, 0), (-82.0, -103.5, 7.0, 3.2, 2),
        # East road verges (north and south)
        (18.5, -82.5, 7.4, 3.3, 1), (22.5, -80.8, 6.4, 2.8, 0),
        (45.0, -82.5, 8.0, 3.6, 0), (50.0, -81.0, 6.8, 3.0, 2),
        (80.0, -82.5, 7.8, 3.5, 1), (84.5, -80.5, 6.8, 3.1, 0),
        (18.0, -102.0, 6.8, 3.0, 1), (39.0, -102.0, 7.4, 3.4, 0),
        (72.0, -101.8, 7.8, 3.5, 1), (79.0, -103.2, 7.0, 3.2, 2),
    )
    for idx, (tx, tz, h, sp, kind) in enumerate(lane_groves):
        hy = hill_y(tx, tz)
        if kind == 0:
            _broadleaf(m, tx, hy, tz, h, sp, bark, leaf_a, leaf_b)
        elif kind == 1:
            _conifer(m, tx, hy, tz, h + 1.0, sp, bark, pine_a, pine_b)
        else:
            m.add(W7.tree(70 + idx), t=(tx, hy, tz))

    for bx, bz, bw, bh, bd in (
        (-13.0, -85.0, 2.4, 1.3, 1.8), (-24.5, -84.8, 2.8, 1.4, 1.9), (-41.5, -85.2, 2.6, 1.3, 1.8),
        (-59.5, -85.0, 3.0, 1.5, 2.0), (-72.0, -85.2, 2.6, 1.4, 1.8), (-85.0, -85.0, 3.0, 1.5, 2.0),
        (-25.5, -99.8, 2.2, 1.2, 1.6), (-35.0, -99.8, 2.6, 1.3, 1.7), (-74.0, -99.6, 2.8, 1.4, 1.8),
        (19.0, -85.0, 2.4, 1.3, 1.8), (32.0, -84.8, 2.8, 1.4, 1.9), (48.0, -85.2, 2.6, 1.3, 1.8),
        (77.0, -85.0, 3.0, 1.5, 2.0), (19.0, -99.6, 2.2, 1.2, 1.6), (40.5, -99.8, 2.5, 1.3, 1.8),
        (70.0, -99.8, 2.6, 1.4, 1.8), (83.0, -99.6, 2.8, 1.4, 1.9),
    ):
        _bush(m, bx, hill_y(bx, bz), bz, bw, bh, bd, leaf_a, leaf_b)

    # Horseshoe groves behind the west and east road-end houses
    for sign in (-1, 1):
        for i, (dx, dz, h) in enumerate((
            (105.0, -99.0, 9.5), (108.0, -93.0, 10.2), (106.0, -86.0, 9.0),
            (98.0, -102.0, 8.2), (96.0, -82.0, 8.4), (112.0, -97.0, 10.6),
            (111.0, -88.0, 9.8),
        )):
            tx = sign * dx
            hy = hill_y(tx, dz)
            if i % 2 == 0:
                _conifer(m, tx, hy, dz, h, 3.8, bark, pine_a, pine_b)
            else:
                _broadleaf(m, tx, hy, dz, h - 1.2, 4.0, bark, leaf_a, leaf_b)

    # Outer woodland ring (r = 68..104 m from (0, 12), clear of flight3d 48 m orbit and south road)
    for i in range(34):
        ang = math.tau * i / 34.0 + 0.08 * math.sin(i * 2.1)
        r = 68.0 + ((i * 19) % 34)
        x = _ORBIT_CX + r * math.sin(ang)
        z = _ORBIT_CZ + r * math.cos(ang)
        if z < -54.0 and abs(x) < 40.0:
            continue
        if abs(z + 92.0) < 9.0:
            continue
        if i % 5 == 0:
            m.add(W7._poplar(50 + i, 10.5 + (i % 3)), t=(x, 0.0, z))
        elif i % 2 == 0:
            _conifer(m, x, 0.0, z, 9.2 + (i % 4) * 1.1, 3.6 + (i % 3) * 0.4, bark, pine_a, pine_b)
        else:
            _broadleaf(m, x, 0.0, z, 8.2 + (i % 3) * 1.0, 4.0 + (i % 2) * 0.6, bark, leaf_a, leaf_b)

    # Hillside ridge conifers grounded on the slopes
    for i in range(28):
        ang = math.tau * i / 28.0 + 0.11 * math.cos(i * 1.7)
        r = 120.0 + ((i * 23) % 54)
        x = _ORBIT_CX + r * math.sin(ang)
        z = _ORBIT_CZ + r * math.cos(ang)
        hy = hill_y(x, z)
        if hy < 1.0:
            continue
        _conifer(m, x, hy, z, 8.6 + (i % 4) * 1.2, 3.8 + (i % 3) * 0.5, bark, pine_a, pine_b)


def _hills(m):
    radii = (108.0, 138.0, 175.0, 225.0, 285.0)
    sectors = 36
    low_hill = W7._t("grass", (34, 48, 32))
    mid_hill = W7._t("grass", (28, 40, 29))
    high_hill = W7._t("grass", (24, 34, 26))

    for ri in range(len(radii) - 1):
        r0, r1 = radii[ri], radii[ri + 1]
        for si in range(sectors):
            t0 = math.tau * si / sectors
            t1 = math.tau * (si + 1) / sectors
            p00 = (_ORBIT_CX + r0 * math.sin(t0), 0.0, _ORBIT_CZ + r0 * math.cos(t0))
            p10 = (_ORBIT_CX + r1 * math.sin(t0), 0.0, _ORBIT_CZ + r1 * math.cos(t0))
            p11 = (_ORBIT_CX + r1 * math.sin(t1), 0.0, _ORBIT_CZ + r1 * math.cos(t1))
            p01 = (_ORBIT_CX + r0 * math.sin(t1), 0.0, _ORBIT_CZ + r0 * math.cos(t1))
            p00 = (p00[0], hill_y(p00[0], p00[2]), p00[2])
            p10 = (p10[0], hill_y(p10[0], p10[2]), p10[2])
            p11 = (p11[0], hill_y(p11[0], p11[2]), p11[2])
            p01 = (p01[0], hill_y(p01[0], p01[2]), p01[2])
            peak = max(p00[1], p10[1], p11[1], p01[1])
            if peak <= 0.01:
                continue
            col = low_hill if peak < 9.0 else (mid_hill if peak < 18.0 else high_hill)
            m.face([p00, p10, p11], col, layer=2, double=False)
            m.face([p00, p11, p01], col, layer=2, double=False)


def _skyline(m):
    # Distant capital blocs down the southern valley (z = -172..-222)
    bloc_a = (26, 30, 38)
    bloc_b = (32, 36, 44)
    lit = (232, 186, 112)
    blocs = (
        (-78, -196, 14, 22, 12), (-58, -184, 16, 26, 10), (-26, -192, 18, 20, 12),
        (-10, -210, 22, 28, 14), (18, -188, 16, 24, 11), (42, -198, 20, 26, 12),
        (68, -186, 15, 19, 10), (88, -206, 18, 22, 12), (-92, -214, 16, 18, 12),
        (12, -172, 12, 14, 9), (-22, -174, 12, 15, 9), (56, -214, 22, 24, 12),
    )
    for i, (bx, bz, w, h, d) in enumerate(blocs):
        col = bloc_a if i % 2 == 0 else bloc_b
        m.add(box(w, h, d, col, center=(float(bx), h * 0.5, float(bz))))
        for row in range(3, int(h) - 2, 4):
            for k in (-0.28, 0.22):
                m.add(box(w * 0.24, 0.55, 0.2, lit,
                          center=(float(bx) + w * k, float(row), float(bz) + d * 0.5 + 0.06),
                          emissive=True))

    # Distant southern radio mast (links to FlightScene "THE RADIO MAST")
    mx, _, mz = _MAST_AT
    m.add(box(1.8, 38.0, 1.8, (46, 50, 56), center=(mx, 19.0, mz)))
    m.add(box(3.4, 0.5, 3.4, (74, 78, 84), center=(mx, 28.0, mz)))
    m.add(box(0.7, 0.7, 0.7, (255, 64, 52), center=(mx, 38.4, mz), emissive=True))

    # North-east hilltop watchtower behind the estate
    tx, tz = _TOWER_AT
    ty = hill_y(tx, tz)
    m.add(box(3.2, 8.5, 3.2, (46, 38, 30), center=(tx, ty + 4.1, tz)))
    m.add(box(4.2, 2.2, 4.2, (36, 40, 44), center=(tx, ty + 9.4, tz)))
    m.add(box(3.8, 0.9, 0.12, (238, 206, 140), center=(tx, ty + 9.4, tz - 2.12), emissive=True))
    m.add(box(4.8, 0.7, 4.8, (54, 42, 36), center=(tx, ty + 10.8, tz)))
    m.add(box(0.5, 0.5, 0.5, (255, 64, 52), center=(tx, ty + 11.4, tz), emissive=True))

    # 360-deg aerial horizon skirt (dark distant forest + dim capital skyline glow ring)
    n_seg = 40
    r_inner = 186.0
    r_outer = 216.0
    forest_dark = (14, 20, 17)
    ridge_dark = (18, 24, 30)
    amber_glow = (142, 98, 52)
    for i in range(n_seg):
        a0 = math.tau * i / n_seg
        a1 = math.tau * (i + 1) / n_seg
        am = 0.5 * (a0 + a1)
        x0, z0 = _ORBIT_CX + math.sin(a0) * r_inner, _ORBIT_CZ + math.cos(a0) * r_inner
        x1, z1 = _ORBIT_CX + math.sin(a1) * r_inner, _ORBIT_CZ + math.cos(a1) * r_inner
        h0 = hill_y(x0, z0) + 14.0 + 5.0 * math.sin(i * 1.9)
        h1 = hill_y(x1, z1) + 14.0 + 5.0 * math.sin((i + 1) * 1.9)
        # Continuous dark forest silhouette wall facing inward
        m.face([(x0, -2.0, z0), (x1, -2.0, z1), (x1, h1, z1), (x0, h0, z0)],
               forest_dark, layer=2, double=True)
        # Outer mountain / capital skyline ring
        ox0, oz0 = _ORBIT_CX + math.sin(a0) * r_outer, _ORBIT_CZ + math.cos(a0) * r_outer
        ox1, oz1 = _ORBIT_CX + math.sin(a1) * r_outer, _ORBIT_CZ + math.cos(a1) * r_outer
        oh0 = h0 + 11.0 + 7.0 * math.cos(i * 1.3)
        oh1 = h1 + 11.0 + 7.0 * math.cos((i + 1) * 1.3)
        m.face([(ox0, -2.0, oz0), (ox1, -2.0, oz1), (ox1, oh1, oz1), (ox0, oh0, oz0)],
               ridge_dark, layer=2, double=True)
        # Southern / flanking capital skyline blocs & dim sodium horizon glow bands
        if math.cos(am) < 0.25:
             xm = _ORBIT_CX + math.sin(am) * (r_inner + 8.0)
             zm = _ORBIT_CZ + math.cos(am) * (r_inner + 8.0)
             yaw_seg = math.degrees(am)
             bh = 18.0 + (i * 7 % 16)
             bw = 16.0 + (i * 5 % 10)
             m.add(box(bw, bh, 8.0, bloc_a if i % 2 == 0 else bloc_b),
                   rot_y(yaw_seg), (xm, bh * 0.5, zm))
             m.add(box(bw * 0.72, 0.85, 0.25, amber_glow, emissive=True),
                   rot_y(yaw_seg), (xm, 6.0 + (i % 3) * 3.5, zm - math.cos(am) * 4.2))


def build_surroundings(m, car_fn=None):
    """Build the countryside, approach road, outbuildings, woods, hills and horizon."""
    _plain(m)
    _roads(m)
    _structures(m, car_fn)
    _trees(m)
    _hills(m)
    _skyline(m)


def bake_surroundings(r, car_fn=None):
    """Bake the outer countryside as separate cullable ``Obj`` batches."""
    for fn in (_plain, _roads, lambda m: _structures(m, car_fn), _trees, _hills, _skyline):
        m = Mesh()
        fn(m)
        if m.faces:
            r.bake(m)


def outer_pools():
    """Warm ground light pools for the outer road, gatehouse and annexes (<= 8 pools)."""
    warm = (255, 206, 142)
    return [
        {"pos": (-7.8, 2.4, -47.2), "range": 6.5, "color": warm, "intensity": 0.65},
        {"pos": (-4.6, E.LAMP_H + 0.3, -58.0), "range": 6.5, "color": warm, "intensity": 0.65},
        {"pos": (4.6, E.LAMP_H + 0.3, -58.0), "range": 6.5, "color": warm, "intensity": 0.65},
        {"pos": (-4.6, E.LAMP_H + 0.3, -76.0), "range": 6.5, "color": warm, "intensity": 0.55},
        {"pos": (4.6, E.LAMP_H + 0.3, -76.0), "range": 6.5, "color": warm, "intensity": 0.55},
        {"pos": (46.5, 2.6, -16.0), "range": 7.5, "color": warm, "intensity": 0.60},
        {"pos": (45.5, 2.8, 28.0), "range": 6.0, "color": warm, "intensity": 0.55},
        {"pos": (-48.0, 2.4, 34.0), "range": 6.5, "color": warm, "intensity": 0.55},
    ]


def draw_fx(r, tm):
    """Dynamic glow halos on outer lamps/floods and distant aviation beacons."""
    for x, z in OUTER_LAMPS[:4]:
        r.add_sprite((x, E.LAMP_H + 0.28, z),
                     _fx.glow((255, 214, 150), 0.9, int(tm), flicker=0.05, seed=int(abs(x) * 3 + abs(z))),
                     layer=_fx.FX_LAYER)
    for fx, fz in _FLOOD_POLES:
        r.add_sprite((fx, 5.9, fz - 0.2),
                     _fx.glow((236, 224, 188), 1.3, int(tm), intensity=0.55, max_px=48),
                     layer=_fx.FX_LAYER)
    mx, _, mz = _MAST_AT
    r.add_sprite((mx, 38.6, mz),
                 _fx.beacon((255, 64, 52), 0.45, int(tm), period_ms=1600.0, phase=0.0),
                 layer=_fx.FX_LAYER)
    tx, tz = _TOWER_AT
    r.add_sprite((tx, hill_y(tx, tz) + 11.5, tz),
                 _fx.beacon((255, 64, 52), 0.38, int(tm), period_ms=1400.0, phase=600.0),
                 layer=_fx.FX_LAYER)
    r.add_sprite(_SUB_BEACON,
                 _fx.beacon((255, 58, 44), 0.34, int(tm), period_ms=1200.0, phase=250.0),
                 layer=_fx.FX_LAYER)
