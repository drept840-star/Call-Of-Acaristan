"""Mission 8 Duty - Retardovici's estate, the same house the Revenge funeral
films (``epilogue3d.funeral``): plastered walls on a stone plinth, a tile
gable roof, two wings, a four-column portico, lit windows, a gravel drive
between hedges, poplars and lamp posts, open iron gates.  Here the house has
an inside to fight through.

Shared by the Approach film, the Mansion fight, the Liftoff film and the
first section of Last Flight.  Axes: +x east, +y up, +z north; the front
facade stands on z = 0, the gate at z = -43.

Areas (all floors are listed in ``mansion_world.FLOORS``):
- The Gates & Drive (z -43..-17): hedged gravel drive, lamp posts, poplars.
- The Forecourt (z -17..0): fountain, staff cars that burn, front balconies.
- The Grand Hall (ground floor, y 0.8): double height, eight columns, two
  chandeliers that can be shot down, side galleries above.
- Security room (west, behind the hall) and the dining room (east).
- The Gallery (first floor, y 5.2): side galleries, landing, armoury,
  Retardovici's study.
- The Helipad terrace (y 5.2, z 36..52) behind the study, where his VIP
  helicopter waits.
"""
import math

from cutscenes import m6fx3d as _fx
from cutscenes import m7world3d as W7
from engine3d import Mesh, box, disc_xz, quad_xz
from engine3d.core import Light, m_apply, m_mul, rot_x, rot_y, rot_z, v_add
from engine3d.textures import tex
from game import scenery3d as SC
from missions.m8.revenge import epilogue3d as E

from . import mansion_env as ENV

RES = (640, 448)
LOOK = W7.LOOKS["night"]
FOG = LOOK["fog"]
FOG_START, FOG_END = 36.0, 235.0

GF = 0.8                     # ground floor, on the plinth
FF = 5.2                     # first floor and terrace
UPPER_Y = FF
SLAB = 0.3
CEIL = 8.8
HX = 13.0                    # house half-width (outer face)
HZ = 36.0                    # back wall
WALL = 0.5
HALL_X = 8.0                 # hall half-width; galleries beyond
STAIR_X = 3.0
STAIR_Z0, STAIR_Z1 = 18.0, 26.0
STAIR_HW = STAIR_X
BACK_Z = 26.0                # hall back wall (ground) / landing edge (first)
ROOMS_Z = 28.5               # first-floor wall between landing and rooms
TERRACE = (-9.0, 36.0, 9.0, 52.0)
GATE_Z = -43.0

HELIPAD_AT = (0.0, FF, 45.0)
HELI_YAW = 90.0
FOUNTAIN_AT = (0.0, 0.0, -9.0)
FRONT_DOOR_AT = (0.0, GF, 0.25)
STUDY_DOOR_AT = (0.0, FF, ROOMS_Z)
TERRACE_DOOR_AT = (0.0, FF, HZ)
DESK_AT = (0.0, FF, 33.0)
SERVER_ROOM_CENTER = (-8.5, GF, 31.0)
ANDREI_AT = (-7.6, GF, 31.2)
ANDREI_RACK_AT = (-11.6, GF, 31.0)
ARMOURY_AT = (-9.0, FF, 32.5)

COLUMNS = tuple((sx * HALL_X, z) for sx in (-1, 1) for z in (4.0, 10.0, 16.0, 22.0))
CHANDELIERS = ((0.0, 7.4, 8.0), (0.0, 7.4, 15.5))
BALCONIES = ((-8.4, -0.9), (8.4, -0.9))
LAMPS = tuple((s * 3.4, z) for z in (-34.0, -28.0, -22.0) for s in (-1, 1))
# (x, z, yaw, paint) - the staff cars in the forecourt, they burn when shot
CARS = ((-6.4, -13.6, 24.0, (28, 32, 42)), (6.2, -14.4, -30.0, (24, 26, 30)),
        (-11.5, -4.6, 90.0, (40, 22, 24)), (11.8, -5.2, 270.0, (28, 32, 42)))
# (x, y, z, yaw) ammo and medical crates, [E] to take
CRATE_SPOTS = ((2.2, 0.0, -40.0, 12.0), (-4.2, 0.0, -2.8, 0.0), (-11.6, GF, 24.6, 90.0),
               (11.4, GF, 33.6, 0.0), (-11.8, FF, 30.0, 90.0), (-6.8, FF, 33.8, 0.0),
               (7.0, FF, 38.2, 20.0))
MONEY_PALLETS = ((-12.0, GF, 34.6), (0.95, FF + 0.9, 33.05), (10.8, FF, 34.6))
# terrace cover: (x, z, w, d, h)
TERRACE_COVER = ((-5.6, 40.2, 1.6, 1.0, 1.1), (5.4, 41.0, 1.0, 1.8, 1.1),
                 (-6.0, 49.0, 1.8, 1.0, 1.1), (5.8, 48.6, 1.6, 1.0, 1.1),
                 (-2.6, 38.8, 1.2, 0.8, 0.9), (2.8, 38.6, 1.2, 0.8, 0.9))
WORKSTATIONS = (
    ((-10.2, GF + 0.78, 34.65), 180.0, "pc_zarya", "monitor_crt"),
    ((-10.95, GF + 0.78, 28.9), 90.0, "pc_tall", "monitor_lcd"),
    ((-6.8, GF + 0.78, 34.65), 180.0, "pc_zarya", "monitor_crt"),
)

_cache = {}
_prop_cache = {}
_LIGHT_CACHE = {}
_POOL_CACHE = {}

STONE = (156, 152, 142)
PLASTER = (198, 190, 170)
TRIM = (226, 222, 210)
GOLD = E.GOLD
NAVY = E.NAVY
RED = E.RED
CARPET = (118, 28, 32)


def _mesh_asset(ref, fallback_fn, scale=1.0, yaw=0.0):
    key = (ref, scale, yaw)
    if key in _prop_cache:
        return _prop_cache[key]
    m = None
    try:
        loaded = SC.prop(ref)
        if loaded is None:
            from game.render3d_bridge import load_mesh_asset
            verts, faces = load_mesh_asset(ref)
            loaded = Mesh()
            loaded.verts = [tuple(float(c) for c in v) for v in verts]
            loaded.faces = [(tuple(f[0]), tuple(f[1]), 2, True, False) for f in faces]
        if loaded is not None and loaded.verts:
            m = Mesh()
            R = rot_y(yaw)
            m.verts = [m_apply(R, (v[0] * scale, v[1] * scale, v[2] * scale)) for v in loaded.verts]
            m.faces = list(loaded.faces)
    except Exception:
        m = None
    if m is None:
        m = fallback_fn()
    _prop_cache[key] = m
    return m


def _fallback_money():
    m = Mesh()
    m.add(box(0.18, 0.09, 0.09, (118, 120, 108), center=(0.0, 0.045, 0.0)))
    m.add(box(0.05, 0.094, 0.094, (148, 102, 54), center=(0.0, 0.047, 0.0)))
    return m


def _fallback_crate():
    m = Mesh()
    m.add(box(0.84, 0.46, 0.50, (76, 86, 58), center=(0.0, 0.23, 0.0)))
    m.add(box(0.88, 0.06, 0.54, (54, 62, 42), center=(0.0, 0.44, 0.0)))
    return m


def _fallback_pistol():
    m = Mesh()
    m.add(box(0.03, 0.09, 0.10, (32, 34, 38), center=(0.0, -0.04, 0.0)))
    m.add(box(0.03, 0.04, 0.22, (44, 48, 54), center=(0.0, 0.02, 0.07)))
    return m


def _fallback_pig():
    m = Mesh()
    m.add(box(0.45, 0.28, 0.72, (164, 96, 62), center=(0.0, 0.18, 0.0)))
    return m


def money_bundle(count=4, detail=True):
    """A neat stack of ``moneystack`` bricks for desks and pallets."""
    unit = _mesh_asset("moneystack", _fallback_money) if detail else _fallback_money()
    m = Mesh()
    for i in range(count):
        row = i // 2
        col = i % 2
        m.add(unit, rot_y((i * 19) % 35 - 17), (col * 0.20 - 0.10, row * 0.088, (i % 3 - 1) * 0.05))
    return m


def ammo_crate_mesh():
    return _mesh_asset("ammo_crate", _fallback_crate)


def crate_lid_angle(open_u):
    """Two-stage hinged lid angle (deg): latch pop, swing up, backstop settle."""
    if open_u <= 0.0:
        return 0.0
    if open_u >= 1.0:
        return 100.0
    if open_u < 0.18:
        t = open_u / 0.18
        return 14.0 * t * t * (3.0 - 2.0 * t)
    if open_u < 0.72:
        q = (open_u - 0.18) / 0.54
        return 14.0 + 92.0 * (1.0 - (1.0 - q) ** 2.4)
    q = (open_u - 0.72) / 0.28
    return 100.0 + 6.0 * math.cos(q * math.pi * 1.5) * (1.0 - q)


def _crate_parts():
    got = _prop_cache.get("crate_parts")
    if got is not None:
        return got
    src = ammo_crate_mesh()
    hinge_y, hinge_z = 0.3955, 0.236
    base = Mesh()
    lid = Mesh()
    for idx, col, layer, dbl, em in src.faces:
        pts = [src.verts[i] for i in idx]
        ys = [p[1] for p in pts]
        if all(abs(y - 0.395541) < 0.002 for y in ys):
            continue
        if min(ys) >= 0.394:
            lid.face([(p[0], p[1] - hinge_y, p[2] - hinge_z) for p in pts], col, layer, dbl, em)
        else:
            base.face([(p[0], min(p[1], hinge_y), p[2]) for p in pts], col, layer, dbl, em)
    # hollowed tray inside the base + solid underside on the hinged lid
    base.add(box(0.62, 0.02, 0.36, (78, 58, 38), center=(0.0, 0.28, 0.0)))
    for sx in (-0.325, 0.325):
        base.add(box(0.03, 0.115, 0.40, (96, 74, 48), center=(sx, 0.3375, 0.0)))
    for sz in (-0.194, 0.194):
        base.add(box(0.68, 0.115, 0.025, (96, 74, 48), center=(0.0, 0.3375, sz)))
    lid.add(box(0.68, 0.016, 0.42, (74, 56, 38), center=(0.0, 0.012, -hinge_z)))
    for sx in (-0.21, 0.21):
        lid.add(box(0.05, 0.018, 0.36, (52, 38, 26), center=(sx, 0.004, -hinge_z)))
        lid.add(box(0.05, 0.03, 0.018, (48, 50, 54), center=(sx, 0.0, -hinge_z * 2.02)))
    contents = Mesh()
    # readable olive ammo tins, brass/red 12GA shells and a medkit inside the tray
    for ox, oz in ((-0.18, -0.05), (-0.18, 0.07)):
        contents.add(box(0.18, 0.09, 0.09, (84, 102, 64), center=(ox, 0.335, oz)))
        contents.add(box(0.186, 0.018, 0.094, (206, 174, 72), center=(ox, 0.36, oz)))
    for k in range(3):
        contents.add(box(0.032, 0.032, 0.075, (198, 44, 38), center=(0.0 + k * 0.045, 0.306, 0.08)))
        contents.add(box(0.034, 0.034, 0.02, (216, 184, 78), center=(0.0 + k * 0.045, 0.306, 0.118)))
    contents.add(box(0.18, 0.08, 0.13, (202, 42, 46), center=(0.16, 0.33, -0.04)))
    contents.add(box(0.03, 0.012, 0.07, (238, 234, 222), center=(0.16, 0.372, -0.04)))
    contents.add(box(0.07, 0.012, 0.03, (238, 234, 222), center=(0.16, 0.372, -0.04)))
    got = _prop_cache["crate_parts"] = (base, lid, contents, (0.0, hinge_y, hinge_z))
    return got


def pistol_mesh():
    """Andrei's sidearm (an enemy prop; Biribel never carries it)."""
    return _fallback_pistol()


def car_mesh(paint, burned=False):
    key = ("car", paint, burned)
    m = _prop_cache.get(key)
    if m is None:
        try:
            from missions.m8.revenge import chase_set as CS
            m = CS._asset("car_m2", 1.45, paint, 1.0 if burned else 0.0, emissive=False)
        except Exception:
            m = None
        if m is None:
            col = (30, 26, 24) if burned else paint
            m = Mesh()
            m.add(box(1.8, 0.8, 4.2, col, center=(0.0, 0.55, 0.0)))
            m.add(box(1.6, 0.6, 2.2, col, center=(0.0, 1.25, -0.2)))
        _prop_cache[key] = m
    return m


def chandelier_mesh():
    m = _prop_cache.get("chandelier")
    if m is None:
        m = Mesh()
        m.add(box(0.06, 1.2, 0.06, GOLD, center=(0.0, 0.75, 0.0)))
        m.add(box(0.5, 0.18, 0.5, GOLD, center=(0.0, 0.1, 0.0)))
        for i in range(10):
            a = math.tau * i / 10.0
            x, z = math.cos(a) * 0.95, math.sin(a) * 0.95
            m.add(box(0.12, 0.08, 0.12, GOLD, center=(x, 0.0, z)))
            m.add(box(0.05, 0.16, 0.05, (250, 238, 200), center=(x, 0.12, z), emissive=True))
            m.add(box(0.06, 0.26, 0.06, (214, 226, 236), center=(x * 0.82, -0.22, z * 0.82)))
        for i in range(6):
            a = math.tau * i / 6.0
            m.add(box(0.9, 0.05, 0.05, GOLD, center=(math.cos(a) * 0.48, 0.02, math.sin(a) * 0.48)))
        m.add(box(0.14, 0.5, 0.14, (220, 230, 240), center=(0.0, -0.32, 0.0)))
        _prop_cache["chandelier"] = m
    return m


# --- building blocks --------------------------------------------------------------

def _window(m, x, y, z, face=-1):
    """``epilogue3d._window`` on a facade facing -z (face=-1) or +z (face=1)."""
    s = -face
    m.add(box(1.5, 2.1, 0.08, TRIM, center=(x, y, z)))
    m.add(box(1.2, 1.8, 0.04, (238, 206, 140), center=(x, y, z - 0.05 * s), emissive=True))
    m.add(box(1.2, 0.05, 0.02, (60, 50, 40), center=(x, y, z - 0.08 * s)))
    m.add(box(0.05, 1.8, 0.02, (60, 50, 40), center=(x, y, z - 0.08 * s)))
    for k in (-1, 1):
        m.add(box(0.5, 1.9, 0.05, (52, 66, 54), center=(x + k * 1.0, y, z - 0.04 * s)))
    m.add(box(1.7, 0.12, 0.2, TRIM, center=(x, y - 1.1, z - 0.08 * s)))


def _window_x(m, x, y, z, face):
    """A window on a side wall facing +x (face=1) or -x (face=-1)."""
    m.add(box(0.08, 2.1, 1.5, TRIM, center=(x, y, z)))
    m.add(box(0.04, 1.8, 1.2, (238, 206, 140), center=(x + 0.05 * face, y, z), emissive=True))
    m.add(box(0.02, 0.05, 1.2, (60, 50, 40), center=(x + 0.08 * face, y, z)))
    for k in (-1, 1):
        m.add(box(0.05, 1.9, 0.5, (52, 66, 54), center=(x + 0.04 * face, y, z + k * 1.0)))
    m.add(box(0.2, 0.12, 1.7, TRIM, center=(x + 0.08 * face, y - 1.1, z)))


def _inner_window(m, x, y, z, face):
    """Night glass seen from inside, with red drapes: face=+1 looks into +z."""
    m.add(box(1.3, 2.0, 0.04, (40, 56, 88), center=(x, y, z + 0.03 * face), emissive=True))
    m.add(box(1.3, 0.05, 0.02, (30, 26, 24), center=(x, y, z + 0.06 * face)))
    for k in (-1, 1):
        m.add(box(0.42, 2.5, 0.08, (124, 26, 30), center=(x + k * 0.86, y + 0.1, z + 0.08 * face)))
    m.add(box(2.2, 0.2, 0.12, GOLD, center=(x, y + 1.35, z + 0.08 * face)))


def _sec_inner_window(m, x, y, z, face):
    """Dark recessed interior trim for security room windows on the north wall."""
    m.add(box(1.56, 2.16, 0.08, (32, 34, 38), center=(x, y, z + 0.02 * face)))
    m.add(box(1.30, 1.90, 0.04, (24, 36, 56), center=(x, y, z + 0.05 * face), emissive=True))
    for by in (-0.55, 0.0, 0.55):
        m.add(box(1.30, 0.05, 0.03, (46, 50, 56), center=(x, y + by, z + 0.07 * face)))
    m.add(box(0.05, 1.90, 0.03, (46, 50, 56), center=(x, y, z + 0.07 * face)))


def _sec_inner_window_x(m, x, y, z, face):
    """Dark recessed interior trim for security room windows on the west wall."""
    wm = Mesh()
    _sec_inner_window(wm, 0.0, 0.0, 0.0, 1)
    m.add(wm, rot_y(90.0 if face > 0 else -90.0), (x, y, z))


def _portrait(m, x, y, z, face, w=1.3, h=1.7, paint=(70, 52, 40)):
    """A gilt-framed portrait on a wall facing +z (face=1) or -z (face=-1)."""
    m.add(box(w + 0.16, h + 0.16, 0.06, GOLD, center=(x, y, z + 0.03 * face)))
    m.add(box(w, h, 0.03, paint, center=(x, y, z + 0.07 * face)))
    m.add(box(w * 0.42, h * 0.36, 0.02, (186, 150, 120), center=(x, y + h * 0.18, z + 0.09 * face)))
    m.add(box(w * 0.7, h * 0.36, 0.02, (36, 40, 56), center=(x, y - h * 0.2, z + 0.09 * face)))


def _banner(m, x, y, z, face):
    """The national banner: navy over red with a gold star."""
    m.add(box(1.4, 3.0, 0.04, NAVY, center=(x, y, z + 0.04 * face)))
    m.add(box(1.4, 1.0, 0.04, RED, center=(x, y - 1.0, z + 0.06 * face)))
    m.add(box(0.36, 0.36, 0.02, GOLD, center=(x, y + 0.6, z + 0.08 * face)))
    m.add(box(1.7, 0.1, 0.1, GOLD, center=(x, y + 1.55, z + 0.04 * face)))


def _lamp_post(m, x, z):
    E._lamp_post(m, x, z)


def _balustrade(m, x0, z0, x1, z1, y, col=TRIM):
    """Posts and a rail from (x0,z0) to (x1,z1) on floor height ``y``."""
    dx, dz = x1 - x0, z1 - z0
    n = max(1, int(math.hypot(dx, dz) / 0.45))
    for i in range(n + 1):
        u = i / n
        m.add(box(0.14, 0.82, 0.14, col, center=(x0 + dx * u, y + 0.41, z0 + dz * u)))
    cx, cz = (x0 + x1) / 2.0, (z0 + z1) / 2.0
    w = abs(dx) + 0.3 if abs(dx) > abs(dz) else 0.3
    d = abs(dz) + 0.3 if abs(dz) >= abs(dx) else 0.3
    m.add(box(w, 0.14, d, col, center=(cx, y + 0.9, cz)))
    m.add(box(w, 0.1, d, col, center=(cx, y + 0.06, cz)))


def _checker(m, x0, z0, x1, z1, y, a, b, cell=2.0, layer=1):
    nx, nz = int(round((x1 - x0) / cell)), int(round((z1 - z0) / cell))
    for ix in range(nx):
        for iz in range(nz):
            col = a if (ix + iz) % 2 == 0 else b
            m.add(quad_xz(x0 + ix * cell, z0 + iz * cell, x0 + (ix + 1) * cell,
                          z0 + (iz + 1) * cell, y, col, layer=layer))


# --- the grounds -------------------------------------------------------------------

def _grounds_estate(m):
    stone = W7._t("stone", STONE)
    gravel = W7._t("gravel", (92, 90, 86), tint=True)
    kerb = W7._t("stone", (112, 108, 102))
    m.add(quad_xz(-80, -70, 80, 90, 0.0, W7._t("grass", (52, 68, 44)), layer=0, seg=40.0))
    m.add(quad_xz(-2.4, GATE_Z - 4.0, 2.4, -16.5, 0.03, gravel, layer=1, seg=4.0))
    m.add(quad_xz(-14.0, -16.5, 14.0, 0.0, 0.03, gravel, layer=1, seg=4.0))
    # low stone kerbs framing the gravel drive and forecourt against the grass
    for s in (-1, 1):
        m.add(quad_xz(min(s * 2.35, s * 2.55), GATE_Z - 4.0, max(s * 2.35, s * 2.55), -16.5, 0.036, kerb, layer=1, seg=4.0))
        m.add(quad_xz(min(s * 2.35, s * 14.15), -16.65, max(s * 2.35, s * 14.15), -16.45, 0.036, kerb, layer=1, seg=4.0))
        kx0, kx1 = min(s * 13.95, s * 14.15), max(s * 13.95, s * 14.15)
        m.add(quad_xz(kx0, -16.65, kx1, -12.4, 0.036, kerb, layer=1, seg=4.0))
        m.add(quad_xz(kx0, -10.6, kx1, 0.0, 0.036, kerb, layer=1, seg=4.0))
    # fountain
    fx, _, fz = FOUNTAIN_AT
    m.add(disc_xz(fx, fz, 3.0, 0.05, stone, n=16))
    m.add(box(5.0, 0.7, 5.0, stone, center=(fx, 0.35, fz)))
    m.add(box(4.4, 0.1, 4.4, (38, 74, 96), center=(fx, 0.66, fz)))
    m.add(box(0.8, 1.9, 0.8, W7._t("plaster", TRIM), center=(fx, 1.15, fz)))
    m.add(box(2.0, 0.2, 2.0, stone, center=(fx, 2.1, fz)))
    m.add(box(0.5, 0.9, 0.5, TRIM, center=(fx, 2.65, fz)))
    # hedges, poplars, trees, lamps (the funeral grounds' plan)
    for s in (-1, 1):
        m.add(W7._hedgerow(s * 3.4, GATE_Z + 1.0, s * 3.4, GATE_Z + 7.0, seed=3 + s))
        m.add(W7._hedgerow(s * 3.4, GATE_Z + 10.0, s * 3.4, -18.0, seed=5 + s))
        m.add(W7._hedgerow(s * 15.5, -16.0, s * 15.5, -1.0, seed=7 + s))
        for k in range(5):
            m.add(W7._poplar(k * 3 + (s > 0), 10.0 + (k * 7) % 3), t=(s * 8.0, 0.0, GATE_Z + 3.0 + k * 5.5))
        for k in range(4):
            m.add(W7.tree(k + (s > 0) * 5), t=(s * (27.0 + 3.0 * (k % 2)), 0.0, -12.0 + 14.0 * k))
        for k in range(3):
            m.add(W7._poplar(20 + k + (s > 0) * 3, 11.0), t=(s * 15.0, 0.0, 40.0 + k * 6.0))
    for x, z in LAMPS:
        _lamp_post(m, x, z)
    # gate piers, open iron gates, the low wall
    gz = GATE_Z
    for s in (-1, 1):
        m.add(box(1.0, 3.0, 1.0, stone, center=(s * 3.2, 1.5, gz)))
        m.add(box(1.2, 0.3, 1.2, stone, center=(s * 3.2, 3.15, gz)))
        m.add(box(0.6, 0.5, 0.6, GOLD, center=(s * 3.2, 3.55, gz)))
        m.add(box(30.0, 1.1, 0.5, stone, center=(s * 18.7, 0.55, gz)))
        leaf = Mesh()
        for k in range(8):
            leaf.add(box(0.05, 2.3, 0.05, (24, 24, 26), center=(0.15 + k * 0.33, 1.15, 0.0)))
        for y in (0.3, 2.2):
            leaf.add(box(2.7, 0.08, 0.06, (24, 24, 26), center=(1.35, y, 0.0)))
        m.add(leaf, rot_y(-70 if s < 0 else -110), (s * 2.7, 0.0, gz))
        # estate wall down the sides
        m.add(box(0.5, 1.1, 100.0, stone, center=(s * 33.8, 0.55, 7.0)))
    m.add(box(68.0, 1.1, 0.5, stone, center=(0.0, 0.55, 57.0)))
    ENV.build_yard_detail(m)


def _grounds(m):
    _grounds_estate(m)
    ENV.build_surroundings(m, car_fn=car_mesh)


# --- the house -----------------------------------------------------------------------

def _shell(m):
    stone = W7._t("stone", STONE)
    plaster = W7._t("plaster", PLASTER)
    tile = W7._t("tile", (122, 60, 48))
    trim = W7._t("plaster", TRIM)
    mz = HZ / 2.0
    gf_top = GF + 0.01
    # plinth, walls (front split for the doorway), string course, cornice
    # no top face: the box layer would paint over the layer-1 hall floor
    m.add(box(2 * HX + 0.4, gf_top, HZ + 0.4, stone, center=(0.0, gf_top / 2.0, mz), skip=("top",)))
    # cap only the 0.2 m exterior plinth ledge outside the walls (leaves hall floor intact)
    m.add(quad_xz(-HX - 0.2, -0.2, HX + 0.2, 0.0, gf_top, stone, layer=2, seg=2.0))
    m.add(quad_xz(-HX - 0.2, HZ, HX + 0.2, HZ + 0.2, gf_top, stone, layer=2, seg=2.0))
    m.add(quad_xz(-HX - 0.2, 0.0, -HX, HZ, gf_top, stone, layer=2, seg=2.0))
    m.add(quad_xz(HX, 0.0, HX + 0.2, HZ, gf_top, stone, layer=2, seg=2.0))
    wall_h = CEIL - gf_top
    wall_cy = (CEIL + gf_top) / 2.0
    for s in (-1, 1):
        m.add(box(HX - 1.2, wall_h, WALL, plaster, center=(s * (HX + 1.2) / 2.0, wall_cy, WALL / 2)))
        m.add(box(WALL, wall_h, HZ, plaster, center=(s * (HX - WALL / 2), wall_cy, mz)))
        m.add(box(HX - 1.5, wall_h, WALL, plaster, center=(s * (HX + 1.5) / 2.0, wall_cy, HZ - WALL / 2)))
    m.add(box(2.4, 5.0, WALL, plaster, center=(0.0, 6.3, WALL / 2)))
    m.add(box(3.0, 1.0, WALL, plaster, center=(0.0, 8.3, HZ - WALL / 2)))
    m.add(box(3.0, FF - gf_top, WALL, plaster, center=(0.0, (FF + gf_top) / 2.0, HZ - WALL / 2)))
    # string course: a band round the outside, not a slab through the hall
    for zc in (0.0, HZ):
        m.add(box(2 * HX + 0.3, 0.22, 0.3, stone, center=(0.0, 4.6, zc)))
    for s in (-1, 1):
        m.add(box(0.3, 0.22, HZ + 0.3, stone, center=(s * HX, 4.6, mz)))
    m.add(box(2 * HX + 0.6, 0.4, HZ + 0.6, stone, center=(0.0, 8.9, mz)))
    m.add(W7._gable_z(HZ + 0.6, 2 * HX + 0.2, 0.0, 5.0, tile, plaster, oh=0.4), rot_y(90), (0.0, 9.1, mz))
    for dx in (-8.0, 8.0):
        for dz in (8.0, 28.0):
            m.add(box(0.9, 4.2, 0.9, plaster, center=(dx, 13.0, dz)))
            m.add(box(1.1, 0.2, 1.1, stone, center=(dx, 15.15, dz)))
    # the wings
    for s in (-1, 1):
        wx = s * 17.0
        m.add(box(8.2, GF, 7.4, stone, center=(s * 17.1, GF / 2.0, 6.0)))
        m.add(box(8.0, 5.2, 7.0, plaster, center=(wx, 3.4, 6.0)))
        m.add(box(8.4, 0.3, 7.4, stone, center=(wx, 6.1, 6.0)))
        m.add(W7._gable_z(7.4, 8.4, 0.0, 2.2, tile, plaster, oh=0.3), rot_y(90), (wx, 6.25, 6.0))
        for i in range(3):
            _window(m, wx - 2.6 + i * 2.6, 2.6, 2.48)
    # front windows (9 columns, two floors) and the lit door surround
    for i in range(9):
        x = -11.2 + i * 2.8
        for y in (2.6, 6.6):
            if abs(x) > 1.0 or y > 5.0:
                _window(m, x, y, -0.02)
    for s in (-1, 1):
        m.add(box(0.3, 3.8, 0.16, (60, 40, 30), center=(s * 1.35, GF + 1.9, -0.06)))
    m.add(box(3.0, 0.3, 0.16, (60, 40, 30), center=(0.0, GF + 3.65, -0.06)))
    # side and back windows
    for s in (-1, 1):
        for z in (14.0, 18.5, 23.0, 27.5, 32.0):
            for y in (2.6, 6.6):
                _window_x(m, s * (HX + 0.02), y, z, s)
        for x in (10.8, -10.8):
            for y in (2.6, 6.6):
                _window(m, x, y, HZ + 0.02, 1)
    # portico: steps, four columns, entablature, pediment; balconies either side
    # porch slab at floor height carries the columns; steps run down in front of it
    m.add(box(7.4, GF - 0.03, 2.7, stone, center=(0.0, (GF + 0.03) / 2.0, -1.35)))
    for k in range(4):
        z0 = -4.1 + k * 0.35
        h_step = (k + 1) * 0.2 - 0.03
        m.add(box(7.4, h_step, -2.7 - z0, stone, center=(0.0, 0.03 + h_step / 2.0, (z0 - 2.7) / 2)))
    for dx in (-2.7, -0.9, 0.9, 2.7):
        m.add(box(0.5, 0.25, 0.5, stone, center=(dx, 0.92, -2.2)))
        m.add(box(0.36, 4.6, 0.36, trim, center=(dx, 3.35, -2.2)))
        m.add(box(0.5, 0.22, 0.5, stone, center=(dx, 5.75, -2.2)))
    m.add(box(6.6, 0.6, 2.8, trim, center=(0.0, 6.15, -1.2)))
    m.add(W7._gable_z(6.8, 3.0, 0.0, 1.4, tile, trim, oh=0.2), t=(0.0, 6.45, -1.2))
    for bx, bz in BALCONIES:
        m.add(box(3.0, 0.3, 1.8, stone, center=(bx, FF - 0.15, bz)))
        for k in range(3):
            m.add(box(0.2, 0.6, 0.2, stone, center=(bx - 1.0 + k, FF - 0.6, -0.2)))
        _balustrade(m, bx - 1.4, bz - 0.8, bx + 1.4, bz - 0.8, FF)
        for s in (-1, 1):
            _balustrade(m, bx + s * 1.4, bz - 0.8, bx + s * 1.4, 0.0, FF)


def _interior_hall(m):
    stone = W7._t("stone", STONE)
    plaster = W7._t("plaster", (214, 204, 182))
    wood = W7._t("plank", (74, 44, 28))
    dark = W7._t("plank", (52, 30, 20))
    # smooth tinted slab: m7 cobbles smeared into crawling streaks at grazing angles
    marble_a = tex("concrete", like=(196, 190, 178), tint=True)
    marble_b = tex("concrete", like=(88, 84, 80), tint=True)
    ix0, ix1, iz0, iz1 = -HX + WALL, HX - WALL, WALL, HZ - WALL
    # ground floor marble, carpet runner to the stairs
    # Leave [-12.5, -3.75] x [25.75, 35.5] for the security room's own concrete slab.
    _checker(m, -12.0, 0.5, 12.0, 24.5, GF + 0.01, marble_a, marble_b, layer=2)
    m.add(quad_xz(ix0, iz0, -12.0, 24.5, GF + 0.01, marble_b, layer=2, seg=2.0))
    m.add(quad_xz(12.0, iz0, ix1, 24.5, GF + 0.01, marble_b, layer=2, seg=2.0))
    m.add(quad_xz(ix0, 24.5, ix1, 25.75, GF + 0.01, marble_b, layer=2, seg=2.0))
    _checker(m, -2.0, 26.5, 12.0, 34.5, GF + 0.01, marble_a, marble_b, layer=2)
    m.add(quad_xz(-3.25, 25.75, -2.0, 34.5, GF + 0.01, marble_b, layer=2, seg=2.0))
    m.add(quad_xz(-2.0, 25.75, 12.0, 26.5, GF + 0.01, marble_b, layer=2, seg=2.0))
    m.add(quad_xz(12.0, 25.75, ix1, 34.5, GF + 0.01, marble_b, layer=2, seg=2.0))
    m.add(quad_xz(-3.25, 34.5, ix1, iz1, GF + 0.01, marble_b, layer=2, seg=2.0))
    m.add(quad_xz(-1.3, -0.1, 1.3, 0.55, GF + 0.012, marble_b, layer=2))  # front door threshold
    m.add(quad_xz(-1.6, 0.6, 1.6, STAIR_Z0, GF + 0.03, CARPET, layer=2))
    m.add(quad_xz(-1.9, 0.6, -1.6, STAIR_Z0, GF + 0.03, GOLD, layer=2))
    m.add(quad_xz(1.6, 0.6, 1.9, STAIR_Z0, GF + 0.03, GOLD, layer=2))
    gf_top = GF + 0.01
    # wainscot round the hall, ceiling with gold coffers
    for s in (-1, 1):
        m.add(box(0.02, CEIL - gf_top, iz1 - iz0, plaster, center=(s * (ix1 - 0.01), (CEIL + gf_top) / 2,
                                                                   (iz0 + iz1) / 2)))
        m.add(box(0.06, 2.0 - gf_top, iz1 - iz0, dark, center=(s * (ix1 - 0.03), (2.0 + gf_top) / 2, (iz0 + iz1) / 2)))
        m.add(box(0.08, 0.08, iz1 - iz0, GOLD, center=(s * (ix1 - 0.04), GF + 1.22, (iz0 + iz1) / 2)))
    for s in (-1, 1):  # front wainscot, split round the doorway
        m.add(box(ix1 - 1.2, 2.0 - gf_top, 0.06, dark, center=(s * (ix1 + 1.2) / 2, (2.0 + gf_top) / 2, iz0 + 0.03)))
    m.add(box(ix1 - ix0, 0.25, iz1 - iz0, plaster, center=(0.0, CEIL + 0.12, (iz0 + iz1) / 2)))
    for z in (2.0, 8.0, 14.0, 20.0):
        m.add(box(2 * HALL_X, 0.12, 0.2, GOLD, center=(0.0, CEIL - 0.02, z + 3.0)))
    for x in (-4.0, 0.0, 4.0):
        m.add(box(0.2, 0.12, BACK_Z, GOLD, center=(x, CEIL - 0.02, BACK_Z / 2)))
    # inside of the front wall: windows, drapes, banners by the door
    for i in range(9):
        x = -11.2 + i * 2.8
        if abs(x) > 1.0:
            _inner_window(m, x, 2.9, WALL + 0.01, 1)
        _inner_window(m, x, 7.0, WALL + 0.01, 1)
    for s in (-1, 1):
        _banner(m, s * 2.2, 3.6, WALL + 0.01, 1)
    # hall columns and the side galleries they carry
    for cx, cz in COLUMNS:
        m.add(box(0.9, 0.4 - 0.01, 0.9, stone, center=(cx, (GF + 0.4 + gf_top) / 2.0, cz)))
        m.add(box(0.7, CEIL - gf_top, 0.7, W7._t("plaster", TRIM), center=(cx, (CEIL + gf_top) / 2, cz)))
        m.add(box(0.9, 0.3, 0.9, GOLD, center=(cx, CEIL - 0.2, cz)))
    for s in (-1, 1):
        gx = s * (HALL_X + ix1) / 2.0
        gw = ix1 - HALL_X
        m.add(box(gw + 0.3, SLAB, BACK_Z - WALL, wood, center=(gx, FF - SLAB / 2, (BACK_Z + WALL) / 2)))
        m.add(box(0.3, 0.4, BACK_Z - WALL, GOLD, center=(s * (HALL_X + 0.1), FF - 0.45, (BACK_Z + WALL) / 2)))
        m.add(quad_xz(min(s * HALL_X, s * ix1), WALL, max(s * HALL_X, s * ix1), BACK_Z, FF + 0.01,
                      CARPET, layer=2))
        _balustrade(m, s * HALL_X, WALL + 0.2, s * HALL_X, BACK_Z, FF)
        side = Mesh()  # side-wall portrait: build facing +z, turn flat onto the wall
        _portrait(side, 0.0, 0.0, 0.0, 1, w=1.2, h=1.6)
        for z in (7.0, 13.0, 19.0):
            m.add(side, rot_y(-90.0 * s), (s * (ix1 - 0.02), GF + 2.6, z))
    # ground-floor back wall with two doorways, the rooms behind it
    for x0, x1 in ((ix0, -7.0), (-5.0, 5.0), (7.0, ix1)):
        m.add(box(x1 - x0, FF - SLAB - gf_top, WALL, plaster, center=((x0 + x1) / 2, (FF - SLAB + gf_top) / 2, BACK_Z)))
    for x in (-6.0, 6.0):
        m.add(box(2.0, 0.4, WALL, GOLD, center=(x, GF + 3.0, BACK_Z)))
        m.add(box(2.0, FF - SLAB - (GF + 3.2), WALL, plaster, center=(x, (FF - SLAB + GF + 3.2) / 2, BACK_Z)))
    _portrait(m, -2.6, GF + 2.3, BACK_Z - WALL / 2, -1, w=1.0, h=1.4)
    _portrait(m, 2.6, GF + 2.3, BACK_Z - WALL / 2, -1, w=1.0, h=1.4)
    for s in (-1, 1):
        m.add(box(WALL, FF - SLAB - gf_top, iz1 - BACK_Z, plaster, center=(s * 3.5, (FF - SLAB + gf_top) / 2,
                                                                         (BACK_Z + iz1) / 2)))
    # first floor slab over the back rooms, landing carpet
    m.add(box(ix1 - ix0, SLAB, iz1 - BACK_Z, wood, center=(0.0, FF - SLAB / 2, (BACK_Z + iz1) / 2)))
    m.add(quad_xz(ix0, BACK_Z, ix1, ROOMS_Z, FF + 0.01, CARPET, layer=2))
    for x0, x1 in ((-HALL_X, -STAIR_X - 0.2), (STAIR_X + 0.2, HALL_X)):
        _balustrade(m, x0, BACK_Z, x1, BACK_Z, FF)
    # grand staircase
    n = 22
    dz = (STAIR_Z1 - STAIR_Z0) / n
    dy = (FF - GF) / n
    for i in range(n):
        sz = STAIR_Z0 + (i + 0.5) * dz
        sy = GF + (i + 0.5) * dy
        m.add(box(2 * STAIR_X, sy - gf_top + dy * 0.5, dz + 0.02, marble_a if i % 2 else marble_b,
                  center=(0.0, (sy + dy * 0.5 + gf_top) / 2, sz)))
        m.add(box(3.4, 0.02, dz + 0.02, CARPET, center=(0.0, sy + dy * 0.5 + 0.012, sz)))
    for s in (-1, 1):
        x = s * (STAIR_X + 0.2)
        steps = 10
        for k in range(steps + 1):
            u = k / steps
            z = STAIR_Z0 + (STAIR_Z1 - STAIR_Z0) * u
            y = GF + (FF - GF) * u
            m.add(box(0.16, 0.9, 0.16, TRIM, center=(x, y + 0.45, z)))
        L = math.hypot(STAIR_Z1 - STAIR_Z0, FF - GF)
        ang = math.degrees(math.atan2(FF - GF, STAIR_Z1 - STAIR_Z0))
        from engine3d.core import rot_x
        rail = box(0.24, 0.16, L, GOLD)
        m.add(rail, rot_x(-ang), (x, (GF + FF) / 2 + 0.95, (STAIR_Z0 + STAIR_Z1) / 2))
        m.add(box(0.4, 1.4 - 0.01, 0.4, stone, center=(x, (GF + 1.4 + gf_top) / 2.0, STAIR_Z0)))
        m.add(box(0.5, 0.2, 0.5, GOLD, center=(x, GF + 1.5, STAIR_Z0)))
    # landing wall to the rooms, doors for armoury / study / bedroom
    for x0, x1 in ((ix0, -9.0), (-7.5, -1.2), (1.2, 7.5), (9.0, ix1)):
        m.add(box(x1 - x0, CEIL - FF, WALL, plaster, center=((x0 + x1) / 2, (CEIL + FF) / 2, ROOMS_Z)))
    for x0, x1 in ((-9.0, -7.5), (-1.2, 1.2), (7.5, 9.0)):
        m.add(box(x1 - x0, CEIL - FF - 2.8, WALL, plaster, center=((x0 + x1) / 2, (CEIL + FF + 2.8) / 2, ROOMS_Z)))
    m.add(box(3.0, 0.5, 0.1, GOLD, center=(0.0, FF + 3.0, ROOMS_Z - 0.3)))
    _banner(m, -4.6, FF + 2.0, ROOMS_Z - WALL / 2, -1)
    _banner(m, 4.6, FF + 2.0, ROOMS_Z - WALL / 2, -1)
    for s in (-1, 1):
        m.add(box(WALL, CEIL - FF, iz1 - ROOMS_Z, plaster, center=(s * 4.0, (CEIL + FF) / 2,
                                                                (ROOMS_Z + iz1) / 2)))
    m.add(quad_xz(-4.0, ROOMS_Z, 4.0, iz1, FF + 0.012, (96, 22, 26), layer=2))


def _interior(m):
    _interior_hall(m)
    for room_fn in (_security_room, _dining_room, _armoury, _study, _bedroom):
        room_fn(m)


def _server_rack_mesh(damaged=False, include_leds=False):
    """Modular 2U/4U tactical server rack centered at (0,0,0), y=0..2.2, facing +x."""
    key = ("server_rack", bool(damaged), bool(include_leds))
    got = _prop_cache.get(key)
    if got is not None:
        return got
    m = Mesh()
    steel = tex("steel", like=(44, 48, 54), tint=True)
    dark = (22, 24, 28)
    blade_col = (34, 38, 44)
    # corner uprights + top/bottom chassis rails
    for sx in (-0.41, 0.41):
        for sz in (-0.51, 0.51):
            m.add(box(0.08, 2.20, 0.08, steel, center=(sx, 1.10, sz)))
    for sy in (0.04, 2.16):
        m.add(box(0.88, 0.08, 1.08, steel, center=(0.0, sy, 0.0)))
    # recessed cabinet body (leaves open front bay if damaged)
    if damaged:
        m.add(box(0.68, 2.04, 0.94, dark, center=(-0.09, 1.10, 0.0)))
        for sz in (-0.45, 0.45):
            m.add(box(0.80, 2.04, 0.04, (30, 32, 38), center=(-0.03, 1.10, sz)))
        # internal copper busbars & coils exposed in the lower/mid bay
        for sz in (-0.18, 0.18):
            m.add(box(0.06, 1.18, 0.06, (178, 102, 46), center=(0.24, 1.05, sz)))
        for k in range(4):
            m.add(box(0.08, 0.10, 0.52, (92, 54, 34), center=(0.21, 0.68 + k * 0.24, 0.0)))
        # severed sparking wire stubs
        for wy, wz, ang in ((0.82, -0.10, -24.0), (1.16, 0.14, 18.0), (1.42, -0.06, 28.0)):
            m.add(box(0.24, 0.024, 0.024, (28, 30, 34)), rot_y(ang), (0.34, wy, wz))
    else:
        m.add(box(0.78, 2.04, 0.94, dark, center=(-0.04, 1.10, 0.0)))
    # perforated dark-grille vent strips on side walls
    for sy in (0.36, 0.74, 1.44, 1.82):
        for sz in (-0.48, 0.48):
            m.add(box(0.56, 0.12, 0.02, (16, 18, 22), center=(-0.04, sy, sz)))
    # top exhaust fan housings
    for fz in (-0.24, 0.24):
        m.add(box(0.46, 0.08, 0.42, steel, center=(-0.04, 2.24, fz)))
        m.add(box(0.34, 0.02, 0.30, (14, 16, 20), center=(-0.04, 2.285, fz)))
        m.add(box(0.10, 0.03, 0.10, (54, 58, 64), center=(-0.04, 2.29, fz)))
    # front bay: intact blades + tape drive, or popped crooked bay door
    door = Mesh() if damaged else m
    dx_off = -0.36 if damaged else 0.0
    dz_off = 0.46 if damaged else 0.0
    # top 4U tape-drive reel module
    door.add(box(0.06, 0.38, 0.88, blade_col, center=(0.38 + dx_off, 1.86, 0.0 + dz_off)))
    for rz_reel in (-0.22, 0.22):
        door.add(box(0.03, 0.24, 0.24, (18, 20, 24), center=(0.415 + dx_off, 1.86, rz_reel + dz_off)))
        door.add(box(0.035, 0.08, 0.08, (88, 92, 100), center=(0.42 + dx_off, 1.86, rz_reel + dz_off)))
    # 2U server blades separated by dark seams with pull handles
    for b_idx in range(6):
        by = 0.30 + b_idx * 0.22
        door.add(box(0.06, 0.19, 0.88, blade_col, center=(0.38 + dx_off, by, 0.0 + dz_off)))
        door.add(box(0.02, 0.02, 0.88, (12, 14, 16), center=(0.405 + dx_off, by - 0.10, 0.0 + dz_off)))
        for hz in (-0.36, 0.36):
            door.add(box(0.035, 0.11, 0.025, (78, 84, 92), center=(0.42 + dx_off, by, hz + dz_off)))
    # perforated lower front intake grille
    door.add(box(0.05, 0.14, 0.86, (16, 18, 22), center=(0.385 + dx_off, 0.13, 0.0 + dz_off)))
    if damaged:
        # swing popped door out from the front-left upright (0.36, 0.0, -0.46)
        m.add(door, m_mul(rot_y(-30.0), rot_x(3.5)), (0.36, -0.02, -0.46))
    if include_leds:
        m.add(_rack_leds_mesh("normal_a"))
    _prop_cache[key] = m
    return m


def _rack_leds_mesh(mode="normal_a"):
    """Cached LED / overloaded busbar overlay for a server rack."""
    got = _prop_cache.get(("rack_leds", mode))
    if got is not None:
        return got
    m = Mesh()
    if mode in ("normal_a", "normal_b"):
        alt = (mode == "normal_b")
        for b_idx in range(6):
            by = 0.30 + b_idx * 0.22
            for k, lz in enumerate((-0.24, -0.14, -0.04, 0.08)):
                on = ((b_idx + k + int(alt)) % 3) != 0
                col = (58, 214, 118) if k < 3 else (232, 162, 52)
                if on:
                    m.add(box(0.02, 0.028, 0.032, col, center=(0.415, by + 0.03, lz), emissive=True))
        m.add(box(0.02, 0.03, 0.04, (58, 214, 118), center=(0.42, 1.98, 0.0), emissive=True))
    elif mode.startswith("surge"):
        step = int(mode.rsplit("_", 1)[1])
        # violent overloaded copper busbars + coils + frantic cyan/red/white LEDs
        for sz in (-0.18, 0.18):
            m.add(box(0.068, 1.18, 0.068, (255, 168, 72) if step != 1 else (190, 240, 255),
                      center=(0.24, 1.05, sz), emissive=True))
        for k in range(4):
            m.add(box(0.088, 0.08, 0.50, (255, 120, 44), center=(0.21, 0.68 + k * 0.24, 0.0), emissive=True))
        for b_idx in range(5):
            by = 0.45 + b_idx * 0.26
            col = ((235, 252, 255), (80, 195, 255), (242, 68, 52))[(b_idx + step) % 3]
            m.add(box(0.03, 0.035, 0.06, col, center=(0.30, by, -0.28 + 0.14 * (b_idx % 3)), emissive=True))
    elif mode == "ember":
        # LEDs dead after breaker pop; faint dying red/ember glow on shorted busbar & coils
        for sz in (-0.18, 0.18):
            m.add(box(0.064, 0.56, 0.064, (148, 38, 22), center=(0.24, 0.92, sz), emissive=True))
        for k in range(3):
            m.add(box(0.084, 0.06, 0.44, (132, 34, 18), center=(0.21, 0.68 + k * 0.24, 0.0), emissive=True))
    _prop_cache[("rack_leds", mode)] = m
    return m


def _office_desk(m, cx, cz, w, d, top_col, leg_col):
    """Tactical office desk spanning [GF, GF+0.78] with steel legs & modesty panel."""
    m.add(box(w, 0.06, d, top_col, center=(cx, GF + 0.75, cz)))
    m.add(box(w - 0.08, 0.05, d - 0.08, leg_col, center=(cx, GF + 0.695, cz)))
    if w >= d:
        for lx in (cx - w / 2 + 0.14, cx, cx + w / 2 - 0.14):
            m.add(box(0.08, 0.668, d - 0.14, leg_col, center=(lx, GF + 0.346, cz)))
        m.add(box(w - 0.28, 0.44, 0.04, (32, 34, 38), center=(cx, GF + 0.46, cz + d / 2 - 0.12)))
    else:
        for lz in (cz - d / 2 + 0.14, cz + d / 2 - 0.14):
            m.add(box(w - 0.14, 0.668, 0.08, leg_col, center=(cx, GF + 0.346, lz)))
        m.add(box(0.04, 0.44, d - 0.28, (32, 34, 38), center=(cx - w / 2 + 0.12, GF + 0.46, cz)))


def _security_room(m):
    wood = W7._t("plank", (74, 44, 28))
    m.add(quad_xz(-12.5, BACK_Z - 0.25, -3.75, HZ - WALL, GF + 0.012,
                  tex("concrete", like=(72, 76, 80), tint=True), layer=2, seg=2.0))
    m.add(box(2.0, 0.012, 0.50, (54, 58, 62), center=(-6.0, GF + 0.016, BACK_Z)))
    # baseboard skirting so wall-to-floor seams read crisply
    skirt = (28, 30, 34)
    m.add(box(8.75, 0.078, 0.04, skirt, center=(-8.125, GF + 0.051, HZ - WALL - 0.02)))
    m.add(box(0.04, 0.078, 9.25, skirt, center=(-12.48, GF + 0.051, 30.875)))
    m.add(box(0.04, 0.078, 9.25, skirt, center=(-3.77, GF + 0.051, 30.875)))
    # static end server racks (z=31.0 middle rack is drawn dynamically)
    for rz in (28.0, 34.0):
        m.add(_server_rack_mesh(damaged=False, include_leds=True), t=(-12.0, GF, rz))
    # overhead cable tray & wall power conduit linking all 3 racks and monitor bank
    tray_col = (42, 46, 52)
    m.add(box(0.38, 0.06, 7.6, tray_col, center=(-12.0, GF + 2.38, 31.1)))
    for rz in (28.0, 31.0, 34.0):
        m.add(box(0.10, 0.18, 0.10, (28, 30, 34), center=(-12.0, GF + 2.29, rz)))
    m.add(box(2.2, 0.08, 0.10, tray_col, center=(-10.9, GF + 2.94, HZ - WALL - 0.06)))
    m.add(box(0.08, 0.65, 0.08, tray_col, center=(-10.35, GF + 2.62, HZ - WALL - 0.06)))
    # thick floor power cables snaking from rack bases toward desks
    cable_col = (24, 26, 30)
    m.add(box(0.95, 0.035, 0.07, cable_col, center=(-11.15, GF + 0.035, 28.4)))
    m.add(box(0.07, 0.035, 1.35, cable_col, center=(-10.95, GF + 0.035, 34.1)))
    m.add(box(1.10, 0.035, 0.07, cable_col, center=(-11.10, GF + 0.035, 34.5)))
    # desks (north desk widened so all 3 workstations fit inside with clean margin)
    _office_desk(m, -8.5, 34.6, 4.8, 1.0, wood, (38, 42, 46))
    _office_desk(m, -10.9, 29.0, 0.9, 2.6, wood, (38, 42, 46))
    # interior trim for north & west exterior windows
    _sec_inner_window(m, -10.8, 2.6, HZ - WALL - 0.01, -1)
    for wz in (27.5, 32.0):
        _sec_inner_window_x(m, -HX + WALL + 0.01, 2.6, wz, 1)
    for pos, yaw, pc, mon in WORKSTATIONS:
        ws = SC.workstation(pc, mon, live=True)
        if ws is not None:
            m.add(ws, rot_y(yaw), pos)
    for i in range(6):
        m.add(box(0.62, 0.46, 0.04, (12, 14, 18), center=(-9.8 + (i % 3) * 0.7, GF + 2.0 + (i // 3) * 0.52,
                                                          HZ - WALL - 0.05)))
    for mx, my, mz in MONEY_PALLETS[:1]:
        m.add(money_bundle(8, detail=False), rot_y(15.0), (mx, my, mz))


def _dining_room(m):
    wood = W7._t("plank", (74, 44, 28))
    m.add(box(1.8, 0.84, 6.0, wood, center=(8.2, GF + 0.43, 31.0)))
    m.add(box(1.86, 0.05, 6.06, (226, 222, 212), center=(8.2, GF + 0.86, 31.0)))
    m.add(_mesh_asset("pig", _fallback_pig, scale=0.45), rot_y(90), (8.2, GF + 0.88, 31.0))
    for dz in (-2.2, -1.1, 1.1, 2.2):
        for s in (-1, 1):
            x = 8.2 + s * 1.3
            m.add(box(0.5, 0.06, 0.5, (60, 30, 24), center=(x, GF + 0.48, 31.0 + dz)))
            m.add(box(0.06, 0.8, 0.5, (60, 30, 24), center=(x + s * 0.24, GF + 0.86, 31.0 + dz)))
    for z in (29.0, 33.0):
        m.add(box(0.3, 1.2, 0.3, GOLD, center=(8.2, GF + 1.5, z)))
    _portrait(m, 8.2, GF + 2.4, HZ - WALL - 0.01, -1, w=2.2, h=1.6, paint=(46, 56, 40))


def _armoury(m):
    steel = (52, 56, 58)
    m.add(quad_xz(-12.5, ROOMS_Z + 0.25, -4.25, HZ - WALL, FF + 0.012, W7._t("concrete", (54, 56, 58)), layer=2))
    for z in (30.4, 32.4, 34.4):
        m.add(box(0.6, 2.2, 1.6, steel, center=(-12.1, FF + 1.1, z)))
        for k in range(4):
            m.add(box(0.08, 1.0, 0.08, (24, 26, 28), center=(-11.75, FF + 1.4, z - 0.6 + k * 0.4)))


def _study(m):
    wood = W7._t("plank", (74, 44, 28))
    dark = (40, 24, 18)
    dx, dy, dz = DESK_AT
    # bookshelves along both walls
    for s in (-1, 1):
        x = s * 3.55
        m.add(box(0.5, 3.0, 6.4, dark, center=(x, FF + 1.5, 32.2)))
        for k in range(5):
            y = FF + 0.4 + k * 0.58
            for j in range(10):
                col = ((120, 40, 34), (44, 58, 92), (86, 74, 40), (30, 60, 44))[(j + k) % 4]
                m.add(box(0.3, 0.42, 0.5, col, center=(x - s * 0.08, y + 0.21, 29.4 + j * 0.6)))
    m.add(box(2.7, 0.86, 1.05, wood, center=(dx, dy + 0.43, dz)))
    m.add(box(2.8, 0.05, 1.12, (98, 58, 36), center=(dx, dy + 0.88, dz)))
    ws = SC.workstation("pc_tall", "monitor_lcd", live=False)
    if ws is not None:
        m.add(ws, rot_y(0.0), (dx - 0.75, dy + 0.90, dz - 0.12))
    m.add(E.telephone_base_mesh(), rot_y(24.0), (dx + 0.45, dy + 0.90, dz - 0.18))
    m.add(E.telephone_handset_mesh(), rot_y(204.0), (dx + 0.45, dy + 0.99, dz - 0.19))
    m.add(box(0.7, 0.1, 0.62, (36, 28, 28), center=(dx, dy + 0.5, dz + 0.9)))
    m.add(box(0.7, 1.1, 0.12, (36, 28, 28), center=(dx, dy + 1.0, dz + 1.2)))
    for mx, my, mz in MONEY_PALLETS[1:2]:
        m.add(money_bundle(6, detail=False), rot_y(15.0), (mx, my, mz))
    # the President's portrait over the terrace doors, banners either side
    _portrait(m, 0.0, FF + 3.1, HZ - WALL - 0.01, -1, w=1.8, h=1.0, paint=(80, 56, 40))
    for s in (-1, 1):
        _banner(m, s * 2.4, FF + 2.2, HZ - WALL - 0.01, -1)


def _bedroom(m):
    m.add(box(2.4, 0.6, 2.8, (120, 26, 30), center=(9.6, FF + 0.3, 33.6)))
    m.add(box(2.6, 1.4, 0.2, (60, 34, 24), center=(9.6, FF + 0.7, 35.0)))
    for mx, my, mz in MONEY_PALLETS[2:]:
        m.add(money_bundle(10, detail=False), rot_y(-10.0), (mx, my, mz))
        m.add(money_bundle(10, detail=False), rot_y(20.0), (mx - 0.6, my, mz - 0.4))


def _terrace(m):
    stone = W7._t("stone", STONE)
    x0, z0, x1, z1 = TERRACE
    m.add(box(x1 - x0, FF, z1 - z0, stone, center=((x0 + x1) / 2, FF / 2, (z0 + z1) / 2), skip=("top",)))
    for k in range(5):
        x = x0 + 1.8 + k * 3.6
        m.add(box(2.2, 3.2, 0.1, (22, 24, 28), center=(x, 1.6, z1 + 0.02)))
    _checker(m, x0, z0, x1, z1, FF + 0.01, W7._t("stone", (176, 170, 158)), W7._t("stone", (138, 132, 122)), layer=2)
    hx, hy, hz = HELIPAD_AT
    tarmac = tex("pavement", like=(60, 64, 68), density=24.0, tint=True)
    m.add(disc_xz(hx, hz, 5.2, FF + 0.02, tarmac, n=20, layer=2))
    m.add(disc_xz(hx, hz, 4.8, FF + 0.025, (226, 220, 206), n=20, layer=2))
    m.add(disc_xz(hx, hz, 4.5, FF + 0.03, tarmac, n=20, layer=2))
    m.add(box(0.5, 0.02, 3.6, (226, 220, 206), center=(hx - 1.2, FF + 0.04, hz)))
    m.add(box(0.5, 0.02, 3.6, (226, 220, 206), center=(hx + 1.2, FF + 0.04, hz)))
    m.add(box(1.9, 0.02, 0.5, (226, 220, 206), center=(hx, FF + 0.04, hz)))
    _balustrade(m, x0, z0 + 0.2, x0, z1, FF)
    _balustrade(m, x1, z0 + 0.2, x1, z1, FF)
    _balustrade(m, x0, z1, x1, z1, FF)
    for x, z, w, d, h in TERRACE_COVER:
        m.add(box(w, h - 0.25, d, (150, 144, 132), center=(x, FF + (h - 0.25) / 2, z)))
        m.add(box(w + 0.1, 0.08, d + 0.1, (176, 170, 158), center=(x, FF + h - 0.25, z)))
        m.add(box(w - 0.1, 0.3, d - 0.1, (52, 76, 46), center=(x, FF + h - 0.1, z)))
    for s in (-1, 1):
        for z in (40.0, 48.0):
            m.add(box(0.3, 1.6, 0.3, (30, 30, 32), center=(s * 8.6, FF + 0.8, z)))
            m.add(box(0.36, 0.3, 0.36, (255, 226, 160), center=(s * 8.6, FF + 1.75, z), emissive=True))


def _build(r):
    # Bake shell, hall, each interior room, terrace, then grounds separately so
    # Early-Z order stays intact while off-screen rooms and surroundings cull.
    for fn in (
        _shell, _interior_hall,
        _security_room, _dining_room, _armoury, _study, _bedroom,
        _terrace, _grounds_estate,
    ):
        m = Mesh()
        fn(m)
        if m.faces:
            r.bake(m)
    ENV.bake_surroundings(r, car_fn=car_mesh)


# --- lights ------------------------------------------------------------------------------

def house_lights(chandeliers_up=(True, True), sec_light=1.0, near=None):
    """Point lights for the per-frame meshes (the strongest eight win)."""
    key = tuple(bool(u) for u in chandeliers_up)
    got = _LIGHT_CACHE.get(key)
    if got is None:
        out = [{"pos": (0.0, 3.2, -3.0), "color": (255, 214, 150), "intensity": 0.85, "range": 12.0},
               {"pos": (0.0, 3.0, 30.0), "color": (255, 206, 146), "intensity": 0.5, "range": 10.0},
               {"pos": (-8.5, GF + 2.4, 31.0), "color": (128, 224, 172), "intensity": 0.6, "range": 8.0},
               {"pos": (0.0, FF + 2.4, 32.5), "color": (255, 206, 146), "intensity": 0.75, "range": 8.0},
               {"pos": (0.0, FF + 3.0, 44.0), "color": (255, 196, 128), "intensity": 0.7, "range": 14.0}]
        for up, (x, y, z) in zip(key, CHANDELIERS):
            if up:
                out.append({"pos": (x, y - 0.6, z), "color": (255, 214, 152), "intensity": 0.95, "range": 13.0})
        for x, z in LAMPS[-2:]:
            out.append({"pos": (x, E.LAMP_H + 0.3, z), "color": (255, 214, 150), "intensity": 0.6, "range": 9.0})
        got = _LIGHT_CACHE[key] = tuple(out)
    out = list(got)
    if sec_light != 1.0:
        sl = dict(out[2])
        sl["intensity"] = max(0.0, sl["intensity"] * float(sec_light))
        if sec_light > 1.2:
            sl["color"] = (170, 240, 255)
            sl["range"] = 10.5
        out[2] = sl
    if near is not None and len(out) > 6:
        nx, ny, nz = near
        def _lscore(L):
            p = L["pos"]
            d2 = (p[0] - nx) ** 2 + (p[1] - ny) ** 2 + (p[2] - nz) ** 2
            rng = max(1.0, float(L.get("range", 8.0)))
            return d2 / max(0.1, rng * rng * float(L.get("intensity", 1.0)))
        out.sort(key=_lscore)
        out = out[:6]
    return out


def pools(chandeliers_up=(True, True), sec_light=1.0, near=None):
    """Lamp pools on the baked set (GL only): lamps, porch, rooms, terrace."""
    key = tuple(bool(u) for u in chandeliers_up)
    got = _POOL_CACHE.get(key)
    if got is None:
        warm = (255, 210, 150)
        out = [{"pos": (x, E.LAMP_H + 0.3, z), "range": 6.5, "color": warm, "intensity": 0.75} for x, z in LAMPS]
        out += [{"pos": (0.0, 5.6, -1.4), "range": 7.0, "color": warm, "intensity": 0.8},
                {"pos": (0.0, 3.2, -9.0), "range": 6.0, "color": (150, 190, 230), "intensity": 0.35},
                {"pos": (-8.5, GF + 3.6, 31.0), "range": 6.0, "color": (110, 220, 160), "intensity": 0.6},
                {"pos": (8.2, GF + 3.6, 31.0), "range": 6.0, "color": warm, "intensity": 0.7},
                {"pos": (-8.5, FF + 3.4, 32.0), "range": 5.5, "color": (210, 220, 230), "intensity": 0.55},
                {"pos": (0.0, FF + 3.4, 32.4), "range": 6.0, "color": warm, "intensity": 0.8},
                {"pos": (8.6, FF + 3.4, 32.4), "range": 5.5, "color": (255, 170, 140), "intensity": 0.6},
                {"pos": (0.0, FF + 3.4, 27.2), "range": 9.0, "color": warm, "intensity": 0.55}]
        for s in (-1, 1):
            out.append({"pos": (s * 10.4, FF + 3.4, 12.0), "range": 9.0, "color": warm, "intensity": 0.45})
            for z in (40.0, 48.0):
                out.append({"pos": (s * 8.6, FF + 2.2, z), "range": 6.0, "color": warm, "intensity": 0.7})
        for up, (x, y, z) in zip(key, CHANDELIERS):
            if up:
                out.append({"pos": (x, y, z), "range": 13.0, "color": warm, "intensity": 0.95})
        out += ENV.outer_pools()
        got = _POOL_CACHE[key] = tuple(out)
    out = list(got)
    if sec_light != 1.0:
        sp = dict(out[len(LAMPS) + 2])
        sp["intensity"] = max(0.0, sp["intensity"] * float(sec_light))
        if sec_light > 1.2:
            sp["color"] = (160, 236, 255)
        out[len(LAMPS) + 2] = sp
    if near is not None and len(out) > 10:
        nx, _ny, nz = near
        kept = []
        for P in out:
            p = P["pos"]
            lim = float(P.get("range", 6.0)) + 28.0
            if (p[0] - nx) ** 2 + (p[2] - nz) ** 2 <= lim * lim:
                kept.append(P)
        kept.sort(key=lambda P: ((P["pos"][0] - nx) ** 2 + (P["pos"][2] - nz) ** 2)
                  / max(1.0, float(P.get("range", 6.0)) ** 2 * float(P.get("intensity", 1.0))))
        out = kept[:10]
    return out


def renderer():
    got = _cache.get("r")
    if got is not None:
        return got
    from engine3d import Renderer
    r = Renderer(RES[0], RES[1], fog=FOG, fog_start=FOG_START, fog_end=FOG_END)
    r.light = Light(**dict(LOOK["light"], ambient=0.38, diffuse=0.42, tint=(0.76, 0.82, 1.0)))
    _build(r)
    _cache["r"] = (r, None, 0)
    return _cache["r"]


def _dyn(r, mesh, rot, pos):
    verts = [tuple(m_apply(rot, v)[i] + pos[i] for i in range(3)) for v in mesh.verts]
    r.add_dynamic(verts, [(f[0], f[1], f[2], f[3], None, f[4]) for f in mesh.faces])


def _put_resident(r, key, build_fn, rot, pos):
    if hasattr(r, "add_resident"):
        res = _cache.setdefault("res", {})
        rk = (id(r), key)
        if rk in res:
            arr = res[rk]
        else:
            mesh = build_fn()
            if mesh is None or not mesh.verts:
                arr = res[rk] = None
            else:
                verts = [tuple(m_apply(rot, v)[i] + pos[i] for i in range(3)) for v in mesh.verts]
                faces = [(f[0], f[1], f[2], f[3], None, f[4]) for f in mesh.faces]
                arr = res[rk] = r.pack(verts, faces)
        if arr is not None:
            r.add_resident(arr)
        return
    sw = _cache.setdefault("res_sw", {})
    if key in sw:
        pair = sw[key]
    else:
        mesh = build_fn()
        if mesh is None or not mesh.verts:
            pair = sw[key] = None
        else:
            verts = [tuple(m_apply(rot, v)[i] + pos[i] for i in range(3)) for v in mesh.verts]
            faces = [(f[0], f[1], f[2], f[3], None, f[4]) for f in mesh.faces]
            pair = sw[key] = (verts, faces)
    if pair is not None:
        r.add_dynamic(pair[0], pair[1])


def _put_packed_yaw(r, key, build_fn, pos, yaw_deg):
    if hasattr(r, "add_packed"):
        pk = _cache.setdefault("pack", {})
        rk = (id(r), key)
        rows = pk.get(rk)
        if rows is None:
            mesh = build_fn()
            rows = pk[rk] = r.pack(mesh.verts, [(f[0], f[1], f[2], f[3], None, f[4]) for f in mesh.faces])
        if rows is None:
            return
        import numpy as np
        a = math.radians(yaw_deg)
        cy, sy = math.cos(a), math.sin(a)
        rt = np.array(((cy, 0.0, -sy), (0.0, 1.0, 0.0), (sy, 0.0, cy)), dtype=rows.dtype)
        out = rows.copy()
        out[:, 0:3] = rows[:, 0:3] @ rt
        out[:, 0:3] += np.asarray(pos, dtype=rows.dtype)
        out[:, 6:9] = rows[:, 6:9] @ rt
        r.add_packed(out)
        return
    _dyn(r, build_fn(), rot_y(yaw_deg), pos)


_SURGE_COLS = ((130, 245, 255), (240, 252, 255), (72, 175, 255))


def _wall_monitors_mesh(cams_alive, surge=0):
    m = Mesh()
    if surge > 0:
        for i in range(6):
            c = _SURGE_COLS[(i + surge) % len(_SURGE_COLS)]
            m.add(box(0.56, 0.4, 0.02, c,
                      center=(-9.8 + (i % 3) * 0.7, GF + 2.0 + (i // 3) * 0.52, HZ - WALL - 0.08),
                      emissive=True))
        return m
    scr_col = (54, 188, 118) if cams_alive else (10, 12, 14)
    for i in range(6):
        m.add(box(0.56, 0.4, 0.02, scr_col,
                  center=(-9.8 + (i % 3) * 0.7, GF + 2.0 + (i // 3) * 0.52, HZ - WALL - 0.08),
                  emissive=bool(cams_alive)))
    return m


def _front_doors_mesh(front_open):
    m = Mesh()
    door = (58, 38, 26)
    if not front_open:
        for s in (-1, 1):
            m.add(box(1.2, 3.4, 0.14, door, center=(s * 0.6, GF + 1.7, 0.25)))
    else:
        for s in (-1, 1):
            m.add(box(1.2, 3.4, 0.14, door), rot_y(-80.0 * s), (s * 1.15, GF + 1.7, 0.7))
    return m


def _terrace_doors_mesh(terrace_open):
    m = Mesh()
    glass = (60, 80, 120)
    if not terrace_open:
        for s in (-1, 1):
            m.add(box(1.4, 2.6, 0.08, glass, center=(s * 0.72, FF + 1.3, HZ - WALL / 2), emissive=True))
    else:
        for s in (-1, 1):
            m.add(box(1.4, 2.6, 0.08, glass, emissive=True), rot_y(-80.0 * s), (s * 1.4, FF + 1.3, HZ + 0.4))
    return m


def draw_dynamic_props(r, tm, cams_alive=True, front_open=False, study_open=False,
                       terrace_open=False, chandeliers=None, cars=None, crates=None,
                       rack_state=None, monitor_surge=0):
    """Per-frame screens, doors, chandeliers, cars and the glows.

    ``chandeliers``: list of (x, y, z) or None per chandelier (None = fallen
    and drawn by the scene); ``cars``: list of (x, z, yaw, paint, burned);
    ``crates``: list of (open_u, loot_u) per ``CRATE_SPOTS`` entry (``loot_u < 0`` hides loot)."""
    base_m, lid_m, loot_m, hinge = _crate_parts()
    surge = int(monitor_surge)
    if surge > 0 or cams_alive:
        for idx, (pos, yaw, pc, mon) in enumerate(WORKSTATIONS):
            if surge > 0:
                scr_col = _SURGE_COLS[(idx + surge) % len(_SURGE_COLS)]
                key_ws = ("ws_surge", idx, surge % 3)
            else:
                scr_col = (54, 188, 118)
                key_ws = ("ws", pos, pc, mon, True)
            _put_resident(r, key_ws,
                          lambda pc=pc, mon=mon, col=scr_col: SC.workstation_display(pc, mon, col),
                          rot_y(yaw), pos)
    _put_resident(r, ("wall_mons", bool(cams_alive), surge),
                  lambda ca=bool(cams_alive), sg=surge: _wall_monitors_mesh(ca, sg),
                  rot_y(0.0), (0.0, 0.0, 0.0))
    # dynamic middle server rack at z=31.0 (pivots around back-bottom edge x=-12.45)
    rmode, rtilt, rphase = ("intact", 0.0, 0) if rack_state is None else rack_state
    r_damaged = (rmode != "intact")
    led_mode = ("normal_b" if rphase else "normal_a") if rmode == "intact" else (
        "surge_%d" % (rphase % 3) if rmode == "surge" else "ember"
    )
    if abs(rtilt) < 0.05 and not r_damaged:
        _put_resident(r, ("mid_rack_body", False), lambda: _server_rack_mesh(False),
                      rot_y(0.0), (-12.0, GF, 31.0))
        _put_resident(r, ("mid_rack_leds", led_mode), lambda lm=led_mode: _rack_leds_mesh(lm),
                      rot_y(0.0), (-12.0, GF, 31.0))
    else:
        piv = (-12.45, GF, 31.0)
        rt = rot_z(rtilt)
        off = m_apply(rt, (0.45, 0.0, 0.0))
        rpos = (piv[0] + off[0], piv[1] + off[1], piv[2] + off[2])
        if rmode == "ember":
            _put_resident(r, ("mid_rack_settled", round(rtilt, 2)),
                          lambda: _server_rack_mesh(True), rt, rpos)
            _put_resident(r, ("mid_rack_leds_settled", round(rtilt, 2)),
                          lambda: _rack_leds_mesh("ember"), rt, rpos)
        else:
            _dyn(r, _server_rack_mesh(True), rt, rpos)
            _dyn(r, _rack_leds_mesh(led_mode), rt, rpos)
    _put_resident(r, ("front_doors", bool(front_open)),
                  lambda fo=bool(front_open): _front_doors_mesh(fo),
                  rot_y(0.0), (0.0, 0.0, 0.0))
    _put_resident(r, ("study_door", bool(study_open)),
                  lambda: box(2.4, 2.8, 0.14, (72, 42, 28)),
                  rot_y(0.0),
                  (0.0, FF + (0.07 if study_open else 1.4), ROOMS_Z + (1.6 if study_open else 0.0)))
    _put_resident(r, ("terrace_doors", bool(terrace_open)),
                  lambda to=bool(terrace_open): _terrace_doors_mesh(to),
                  rot_y(0.0), (0.0, 0.0, 0.0))
    chs = CHANDELIERS if chandeliers is None else chandeliers
    for c in chs:
        if c is None:
            continue
        if getattr(r, "frustum_cull", True) and not r.visible_sphere(c, 1.4):
            continue
        _put_packed_yaw(r, "chandelier", chandelier_mesh, c, tm * 0.002)
        r.add_sprite((c[0], c[1] - 0.1, c[2]), _fx.glow((255, 214, 152), 1.6, int(tm), intensity=0.6,
                                                        max_px=64), layer=_fx.FX_LAYER)
    if cars is None:
        cars = [(x, z, yaw, paint, False) for x, z, yaw, paint in CARS]
    for x, z, yaw, paint, burned in cars:
        _put_resident(r, ("car", x, z, yaw, paint, bool(burned)),
                      lambda p=paint, b=bool(burned): car_mesh(p, b),
                      rot_y(yaw), (x, 0.0, z))
    show_fx = crates is not None
    if crates is None:
        crates = [(0.0, -1.0)] * len(CRATE_SPOTS)
    for idx, ((x, y, z, yaw), (open_u, loot_u)) in enumerate(zip(CRATE_SPOTS, crates)):
        cy = 0.03 if y == 0.0 else y + 0.015
        ry = rot_y(yaw)
        hpos = v_add((x, cy, z), m_apply(ry, hinge))
        _put_resident(r, ("crate_base", idx), lambda m=base_m: m, ry, (x, cy, z))
        if open_u <= 0.0:
            _put_resident(r, ("crate_lid_closed", idx), lambda m=lid_m: m, ry, hpos)
            if show_fx:
                r.add_sprite((x, cy + 0.56, z),
                             _fx.glow((118, 224, 132), 0.20, int(tm), pulse=0.30,
                                      seed=70 + idx, intensity=0.35, max_px=12),
                             layer=_fx.FX_LAYER)
        else:
            ang = crate_lid_angle(open_u)
            if open_u >= 1.0:
                _put_resident(r, ("crate_lid_open", idx), lambda m=lid_m: m, m_mul(ry, rot_x(100.0)), hpos)
            else:
                _dyn(r, lid_m, m_mul(ry, rot_x(ang)), hpos)
                r.add_sprite((x, cy + 0.42, z),
                             _fx.glow((255, 228, 176), 0.28, int(tm), intensity=0.45, max_px=16),
                             layer=_fx.FX_LAYER)
            if 0.0 <= loot_u < 1.0:
                sc = 1.0 - 0.55 * loot_u
                lift = 0.24 * math.sin(loot_u * math.pi * 0.7)
                verts = [v_add(m_apply(ry, (v[0] * sc, (v[1] - 0.33) * sc + 0.33 + lift, v[2] * sc)), (x, cy, z))
                         for v in loot_m.verts]
                r.add_dynamic(verts, [(f[0], f[1], f[2], f[3], None, f[4]) for f in loot_m.faces])
    for x, z in LAMPS:
        r.add_sprite((x, E.LAMP_H + 0.28, z), _fx.glow((255, 214, 150), 0.9, int(tm), flicker=0.05,
                                                       seed=int(x * 7 + z)), layer=_fx.FX_LAYER)
    for s in (-1, 1):
        for z in (40.0, 48.0):
            r.add_sprite((s * 8.6, FF + 1.75, z), _fx.glow((255, 214, 150), 0.7, int(tm), flicker=0.05,
                                                          seed=int(z + s)), layer=_fx.FX_LAYER)
    hx, hy, hz = HELIPAD_AT
    for k in range(8):
        a = math.tau * k / 8.0
        r.add_sprite((hx + math.cos(a) * 5.0, hy + 0.12, hz + math.sin(a) * 5.0),
                     _fx.beacon((255, 162, 64), 0.32, int(tm), period_ms=1400.0, phase=k * 175.0),
                     layer=_fx.FX_LAYER)
    ENV.draw_fx(r, tm)


# the stock night light leaves the cast dim blue with hot rims: warm lamplight
# inside the house, a brighter, less blue moon outside
_INDOOR = Light(direction=(-0.25, 0.85, -0.35), ambient=0.48, diffuse=0.5, sky=0.08, tint=(1.0, 0.9, 0.76))
_OUTDOOR = Light(**dict(LOOK["light"], ambient=0.40, diffuse=0.48, tint=(0.8, 0.85, 1.0)))


def _indoors(eye):
    return abs(eye[0]) < HX and 0.0 < eye[2] < HZ and eye[1] < CEIL


def frame(eye, tgt, fov, lights=(), t=0, size=None, chandeliers_up=(True, True), sec_light=1.0):
    r = renderer()[0]
    r.resize(*(size or RES))
    r.set_camera(eye, tgt, fov, 0.0)
    r.fog, r.fog_start, r.fog_end = FOG, FOG_START, FOG_END
    r.light = _INDOOR if _indoors(eye) else _OUTDOOR
    try:
        r.set_lights(list(lights) + house_lights(chandeliers_up, sec_light=sec_light, near=tgt))
    except Exception:
        pass
    try:
        r.set_pools(pools(chandeliers_up, sec_light=sec_light, near=tgt))
    except Exception:
        pass
    W7.sky(r, r.surface, t, "night")
    r.begin()
    r.add_static()
    return r


def present(r, surface):
    if getattr(r, "backend", "") == "gl":
        r.hdr = True
        r.flush_to(surface, post={
            "bloom": 0.26, "bloom_knee": 0.96,
            "lut": _fx.cine_curve(), "dither_step": _fx.DITHER_STEP,
        })
        return
    surf = r.surface
    r.flush(surf)
    try:
        _fx.grade_cine(surf)
    except Exception:
        pass
    _fx.present_crisp(surf, surface)
