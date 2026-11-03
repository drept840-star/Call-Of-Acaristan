"""Mission 3 in 2.5D: the five playable maps drawn in 3D over the 2D rules.

``draw.game_draw`` hands the frame here while ``game.topdown3d`` is on for
Mission 3, and ``draw._m3_td3d_gate`` keeps that to each stage on its own
map: the cell-block breakout, comms, archives, the kill order and the
broadcast. The interrogation (monitor POV and breach film) and the vent
film stay 2D. The sim, the doors, the detainees and every collision rect
stay where they were; this module only changes what the world looks like.
The 2D screen passes (alarm wash, waypoint, vignette, HUD, prompts,
crafting, wing overlays, death tilt) run on top through
``draw._draw_screen_passes`` on the cell block and
``draw._draw_wing_screen_passes`` on the wings, and ``draw._PROJ`` makes
their world anchors project through this frame's ``td.View``. The wing
sets, lamps and live props live in ``wings3d``.

Set: the map glyphs are the source. ``C`` is the border or a block wall,
``D`` a door (barred on the cell row, steel slabs elsewhere). Furniture
stands on the 2D barrier rects so it matches what Biribel bumps into.
Walls and doors are drawn per frame with the M1 cutaway; floor, paint,
furniture, cells and lamps are one static batch.

The 2D lamp table is laid out for an older map, so the tubes here are
authored per room. Any renderer error turns 2.5D off for the rest of the
run (``td.disable``) and the frame falls back to the 2D painter.
"""
import math

from core.config import HEIGHT, TILE_SIZE, WIDTH, font_terminal_small, screen
from core.state import STATE
from engine.core import now_ms as _now_ms, now_s as _now_s
from game import topdown3d as td
from game.topdown3d import K, to3
from missions.m1 import draw3d as _m1
from missions.m1 import grade3d as _grade
from missions.m3 import draw as _d
from missions.m3 import maps as _maps
from missions.m3 import systems as _s
from missions.m3 import wings3d as _wings
from missions.m3 import world as _wd

CAM = td.CAMS["MISSION3"]
T = TILE_SIZE
AIM_H = _m1.AIM_H
STUB_H = _m1.STUB_H
CUT_CAP = _m1.CUT_CAP
DOOR_H = _m1.DOOR_H
WALL_H = {"border": 3.2, "block": 2.7, "shelf": 2.1, "cube": 1.35}

WALL = (74, 74, 70)              # grimy whitewash above the dado
DADO = (44, 60, 56)              # institutional green paint, waist down
DADO_H = 1.25
BORDER = (66, 64, 60)
CAP = (24, 25, 27)               # wall tops: flat and dark so rooms read
RIM = (104, 106, 102)            # lit lip where a wall top meets open floor
RIM_CUT = (58, 60, 62)
STEEL = (70, 74, 78)
DARK = (34, 36, 38)
SLEEVE = (88, 64, 46)            # chair.py prisoner wardrobe
SLEEVE_D = (56, 42, 32)
TUBE = (255, 240, 214)
VOID = _m1.VOID
RING_CALM = (200, 92, 70)        # M1's calm ring is lost on the dark cell floor
AMBIENT = (170, 172, 172)
NIGHT = dict(_m1.NIGHT, ambient=0.36, diffuse=0.42, tint=(0.95, 1.0, 0.98))

PRISONER = dict(jacket=SLEEVE, pants=SLEEVE, vest=None, pouches=False, accent=None,
                armband=SLEEVE, belt=None, buckle=None, cuff=SLEEVE_D, lapel=None, shirt=None)
INMATE = dict(jacket=(168, 92, 34), pants=(168, 92, 34), vest=None, pouches=False, accent=None,
              armband=(228, 180, 86), belt=None, buckle=None, cuff=(92, 48, 24), lapel=None,
              shirt=None, long_coat=None)
# enemy type -> (rig, spec overrides)
_FOE = {"guard": ("os12", {}),
        "marksman": ("os12", {"jacket": (58, 46, 40)}),
        "breacher": ("shotgun", {"vest": (46, 48, 44)}),
        "shield": ("pistol", {"vest": (52, 54, 50)}),
        "technician": ("pistol", {"jacket": (70, 72, 64)})}

_FLOOR = {".": ("pavement", (40, 41, 41)), "P": ("pavement", (40, 41, 41)),
          "D": ("pavement", (40, 41, 41)), "g": ("pavement", (50, 50, 52)),
          "O": ("concrete", (36, 43, 45)), "L": ("concrete", (42, 50, 52)),
          "Y": ("pavement", (54, 54, 50)), "M": ("concrete", (42, 44, 42)),
          "K": ("concrete", (50, 53, 58)), "E": ("concrete", (40, 42, 42))}

# 2D barrier rects (x, y, w, h in tiles) and what stands on them
_PROPS = (("fridge", 3.31, 21.25, 0.375, 0.5), ("stove", 5.28, 21.28, 0.44, 0.44),
          ("counter", 4.03, 23.38, 0.94, 0.25),
          *(("console", 13.125 + 4 * k, 19.125, 0.69, 0.34) for k in range(6)),
          ("lockers", 13.06, 23.28, 2.875, 0.625), ("gunrack", 31.06, 23.38, 1.875, 0.375),
          ("briefing", 21.56, 21.09, 2.875, 0.69),
          *(("wallrack", c, 19.125, 1.09, 0.47) for c in (37.7, 39.2, 42.6)),
          ("ammo", 38.0, 22.6, 0.84, 0.66), ("ammo", 42.2, 22.6, 0.84, 0.66),
          ("washers", 5.0, 33.0, 5.28, 0.66), ("table", 10.19, 36.0, 2.75, 0.625),
          ("hamper", 5.75, 40.81, 0.69, 0.47), ("hamper", 14.84, 34.70, 0.69, 0.47),
          ("bench", 20.91, 40.89, 1.19, 0.25), ("bench", 26.5, 40.89, 1.19, 0.25),
          ("rack", 19.98, 35.27, 0.81, 1.09), ("rack", 27.39, 35.27, 0.81, 1.09),
          ("tank_h", 33.5, 34.03, 1.0, 1.94), ("tank_v", 41.44, 34.73, 1.125, 1.31),
          ("workbench", 37.30, 38.09, 2.0, 0.91))

# (col, row in tiles, reach px, colour, key): tubes per room, floods outside
_LAMPS = (*((9.5 + 8 * i, 8.5, 190, td.mix(col, (255, 255, 255), 0.3), "cell")
            for i, col in enumerate(_d._NEIGHBOR_LIGHT_COLS)),
          (33.5, 8.5, 190, TUBE, "cell"),
          *((c, 14.5, 170, (236, 240, 246), "cor") for c in (8, 12.5, 17, 21.5, 26, 30.5, 35)),
          (41.5, 15.0, 150, (190, 255, 220), "exit"),
          (4.5, 22.5, 150, (200, 236, 250), "kit"),
          *((c, 21.5, 230, (230, 236, 240), "hall") for c in (15, 22.5, 30)),
          (38.0, 21.5, 190, (240, 232, 214), "arm"), (42.5, 21.5, 190, (240, 232, 214), "arm"),
          (41.5, 19.7, 120, (110, 196, 132), "arm"),      # green work light on the K-9 stand
          *((c, 28.0, 210, (236, 240, 246), "low") for c in (8, 16, 24, 32, 40)),
          (8, 36.5, 220, (214, 236, 246), "lau"), (14, 36.5, 220, (214, 236, 246), "lau"),
          (19.0, 34.5, 300, (255, 230, 180), "wfl"), (30.0, 39.5, 300, (255, 230, 180), "wfl"),
          (35, 36.0, 220, (250, 226, 190), "mnt"), (41, 38.0, 220, (250, 226, 190), "mnt"),
          (2.5, 2.5, 340, (255, 230, 180), "fl"), (45.5, 2.5, 340, (255, 230, 180), "fl"),
          (2.5, 45.5, 340, (255, 230, 180), "fl"), (45.5, 45.5, 340, (255, 230, 180), "fl"))
_LAMP_H = {"fl": 4.0, "exit": 2.45, "wfl": 3.1}
_YARD_MID = (24.5, 37.0)

# per wing: (whitewash, dado) of the block walls
_WALLS = {"cell": (WALL, DADO), "comms": ((68, 72, 74), (40, 52, 60)),
          "archives": ((86, 80, 70), (70, 52, 38)), "killorder": ((78, 78, 76), (52, 54, 58)),
          "broadcast": ((64, 62, 72), (40, 38, 50))}

_cache = {"walls": None, "packed": {}, "meshes": {}, "night": {}, "doors": None}


# ── frame ──────────────────────────────────────────────────────────────

def game_draw3d(fcx, fcy):
    """Draw one Mission 3 breakout frame in 2.5D onto ``screen``. False
    when the renderer failed (2.5D is off now; the caller draws 2D)."""
    cam_x, cam_y = int(round(fcx)), int(round(fcy))
    _d._M3_CAM[0], _d._M3_CAM[1] = cam_x, cam_y
    v = td.View(CAM, fcx + WIDTH / 2.0, fcy + HEIGHT / 2.0)
    _tick()
    if not render_world(screen, v):
        return False
    _labels(screen, v)
    if STATE.muzzle_flash_timer > 0:
        STATE.muzzle_flash_timer -= 1
    _d._PROJ[0] = v
    try:
        if _key() == "cell":
            _d._draw_screen_passes(cam_x, cam_y, world3d=True)
        else:
            _d._draw_wing_screen_passes(cam_x, cam_y)
    finally:
        _d._PROJ[0] = None
    return True


def _tick():
    """The blood fade the 2D world pass ages; the 3D frame ages it the same."""
    for decal in STATE.blood_decals[:]:
        decal[2] -= 0.25
        if decal[2] <= 0:
            STATE.blood_decals.remove(decal)


def render_world(surface, v):
    """Draw the cell block and its cast through view ``v`` onto ``surface``."""
    from cutscenes import m6fx3d as _fx
    from cutscenes import m6world3d as _w
    from engine3d import Light
    r, buf = _w.rend(*CAM.res)
    saved = (r.light, r.fog, r.fog_start, r.fog_end, r.light_cap)
    tm = _now_ms()
    try:
        r.light = Light(**NIGHT)
        r.fog, r.fog_start, r.fog_end = VOID, 32.0, 64.0
        r.light_cap = 8
        v.apply(r)
        buf.fill(VOID)
        r.begin()
        first = _w.static_scene(r, ("m3_td3d", id(_maps.MISSION3_MAP)))
        ok = False
        try:
            if first:
                _build_set(r)
            ok = True
        finally:
            _w.static_end(r, ok)
        flashes = []
        _draw_walls(r)
        _draw_doors(r)
        if _key() == "cell":
            _draw_story_props(r, tm)
        else:
            _wings.draw_live(r, _key(), tm, flashes)
        _draw_cast(r, flashes, tm)
        _draw_fx(r, flashes, tm)
        dyn = _m1._flash_lights(flashes, tm)
        _lamp_lights(r, v, flashes, tm)
        r.flush(buf)
    except Exception:
        import traceback
        traceback.print_exc()
        td.disable()                  # next frame is the 2D painter
        return False
    finally:
        r.light, r.fog, r.fog_start, r.fog_end, r.light_cap = saved
    _fx.present_crisp(buf, surface)
    wing = [] if _key() == "cell" else _wings.dyn_lights(_key(), tm)
    _grade.apply(surface, v, _night_lights() + dyn + wing + _presence(), ambient=_wings.AMBIENT.get(_key(), AMBIENT))
    return True


# ── helpers ────────────────────────────────────────────────────────────

def _key():
    return _d._m3_map_key()


def _lamps():
    return _LAMPS if _key() == "cell" else _wings.lamps(_key())


def _dims():
    return _maps._live_map_dims()


def _glyph(col, row):
    grid = _maps.MISSION3_MAP
    if 0 <= row < len(grid) and 0 <= col < len(grid[row]):
        return grid[row][col]
    return ""


def _tc(col, row, h=0.0):
    """World point of a tile-unit position (col, row may be fractional)."""
    return to3(col * T, row * T, h)


def _put(r, mesh, pos, yaw=0.0, roll=0.0, scale=1.0, pitch=0.0):
    td.put(r, mesh, pos, yaw, roll, round(scale, 2), cache=_cache["packed"], pitch=pitch)


def _mesh(key, build):
    m = _cache["meshes"].get(key)
    if m is None:
        m = _cache["meshes"][key] = build()
    return m


def _hash(a, b, n):
    return ((a * 73856093) ^ (b * 19349663)) % n


def _shade(col, k):
    return tuple(max(0, min(255, int(c * k))) for c in col)


def _floor_tex(col, name):
    from engine3d import tex
    return tex(name, like=tuple(max(0, min(255, int(c))) for c in col), tint=True)


def _tile_col(col, row, base):
    k = 1.0 + (_hash(col, row, 9) - 4) * 0.011
    lean = (_hash(col + 3, row + 11, 5) - 2) * 0.006
    return (base[0] * k * (1.0 + lean), base[1] * k, base[2] * k * (1.0 - lean))


def _glow(col, size, tm, k=0.8, px=16, **kw):
    from cutscenes import m6fx3d as _fx
    return _fx.glow(col, size, tm, intensity=k, max_px=px, **kw)


# ── static set ─────────────────────────────────────────────────────────

def _build_set(r):
    from cutscenes import m6world3d as _w
    from engine3d import quad_xz
    key = _key()
    floor = _FLOOR if key == "cell" else _wings.FLOOR[key]
    w, h = _dims()
    for row in range(h):
        for col in range(w):
            g = _glyph(col, row)
            if g not in floor:
                continue
            name, base = floor[g]
            if g == "K" and (col + row) % 2:
                base = _shade(base, 0.78)
            cell = (col - 7) // 8
            if key == "cell" and 6 <= row <= 11 and 0 <= cell <= 2 and (col - 7) % 8 < 6:
                base = td.mix(base, _d._NEIGHBOR_THEMES[cell]["tint"], 0.22)
            _w.add(r, quad_xz(col * T * K, -(row + 1) * T * K, (col + 1) * T * K, -row * T * K, 0.0,
                              _floor_tex(_tile_col(col, row, base), name), layer=0))
    if key == "cell":
        _paint(r)
        for kind, x, y, pw, ph in _PROPS:
            _furniture(r, kind, x, y, pw, ph)
        _cells(r)
        _own_cell(r)
    else:
        _wings.build(r, key)
    for kind, ptx, pty, arg in _d._M3_DRESSING_PROPS.get(key, ()):
        if _d._bg_prop_overlaps_solid(kind, ptx, pty, arg):
            continue
        if kind in ("crates", "barrels", "coil"):
            _m1._dressing(r, kind, ptx * T, pty * T, arg)
        else:
            x, _, z = _tc(ptx, pty)
            _w.add(r, _cart_mesh(kind, x, z))
    for col, row, _rad, color, lk in _lamps():
        _fixture(r, col, row, color, lk)


def _paint(r):
    """Hazard stripes round the exit, yard court lines, hall seams."""
    from cutscenes import m6world3d as _w
    from engine3d import quad_xz
    y = 0.006
    x0, x1, z0, z1 = 40 * T * K, 43 * T * K, -17 * T * K, -14 * T * K
    for i in range(12):
        a = x0 + i * (x1 - x0) / 12.0
        col = (180, 150, 40) if i % 2 else (30, 30, 28)
        _w.add(r, quad_xz(a, z1 - 0.12, a + (x1 - x0) / 12.0, z1, y, col, layer=1))
        _w.add(r, quad_xz(a, z0, a + (x1 - x0) / 12.0, z0 + 0.12, y, col, layer=1))
    line = (120, 118, 100)
    yx0, yx1, yz0, yz1 = 19.6 * T * K, 29.4 * T * K, -41.6 * T * K, -32.4 * T * K
    for a, b, c, d in ((yx0, yz0, yx1, yz0 + 0.05), (yx0, yz1 - 0.05, yx1, yz1),
                       (yx0, yz0, yx0 + 0.05, yz1), (yx1 - 0.05, yz0, yx1, yz1),
                       (yx0, (yz0 + yz1) / 2 - 0.025, yx1, (yz0 + yz1) / 2 + 0.025)):
        _w.add(r, quad_xz(a, b, c, d, y, line, layer=1))
    seam = (30, 36, 38)
    w, h = _dims()
    for row in range(h):
        for col in range(w):
            if _glyph(col, row) not in ("O", ".") or col % 2 or row % 2:
                continue
            sx, sz = col * T * K, -row * T * K
            _w.add(r, quad_xz(sx - 0.01, sz - 2 * T * K, sx + 0.01, sz, 0.004, seam, layer=1))
            _w.add(r, quad_xz(sx, sz - 0.01, sx + 2 * T * K, sz + 0.01, 0.004, seam, layer=1))


def _cart_mesh(kind, x, z):
    from engine3d import Mesh, box
    m = Mesh()
    if kind == "mop":
        m.add(box(0.4, 0.34, 0.34, (150, 120, 40), center=(x, 0.17, z)))
        m.add(box(0.04, 1.2, 0.04, (120, 100, 70), center=(x + 0.1, 0.7, z)))
    else:
        m.add(box(0.9, 0.08, 0.55, (70, 72, 76), center=(x, 0.7, z)))
        m.add(box(0.9, 0.08, 0.55, (70, 72, 76), center=(x, 0.25, z)))
        for sx in (-0.42, 0.42):
            m.add(box(0.04, 0.75, 0.5, (52, 54, 56), center=(x + sx, 0.42, z)))
        m.add(box(0.36, 0.26, 0.3, (110, 88, 52), center=(x - 0.15, 0.87, z)))
    return m


def _furniture(r, kind, tx, ty, tw, th):
    """One piece on its barrier rect (tile units, top-left + size)."""
    from cutscenes import m6world3d as _w
    from engine3d import Mesh, box, rot_y, rot_z, tex
    x, _, z = _tc(tx + tw / 2.0, ty + th / 2.0)
    w, d = tw * T * K, th * T * K
    steel = tex("steel", like=STEEL)
    if kind == "counter":
        _w.add(r, box(w, 0.86, d, tex("steel", like=(64, 66, 68)), center=(x, 0.43, z)))
        _w.add(r, box(w + 0.04, 0.05, d + 0.04, (118, 122, 124), center=(x, 0.885, z)))
    elif kind == "stove":
        _w.add(r, box(w, 0.86, d, (40, 40, 42), center=(x, 0.43, z), cols={"top": (24, 24, 26)}))
        for i in range(4):
            bx, bz = x + (i % 2 - 0.5) * w * 0.5, z + (i // 2 - 0.5) * d * 0.5
            _w.add(r, box(0.14, 0.02, 0.14, (70, 70, 72), center=(bx, 0.87, bz)))
    elif kind == "fridge":
        _w.add(r, box(w, 1.9, d, tex("steel", like=(150, 154, 150), tint=True), center=(x, 0.95, z),
                      cols={"top": (168, 172, 168)}))
        _w.add(r, box(0.04, 0.6, 0.04, (60, 62, 64), center=(x + w / 2.0 - 0.08, 1.2, z + d / 2.0 + 0.02)))
    elif kind == "console":
        _w.add(r, box(w, 1.0, d, tex("steel", like=(34, 42, 44), tint=True), center=(x, 0.5, z),
                      cols={"top": (40, 50, 52)}))
        _w.add(r, box(w * 0.55, 0.02, d * 0.5, (40, 120, 96), center=(x - w * 0.14, 1.01, z), emissive=True))
        _w.add(r, box(0.06, 0.03, 0.06, (220, 60, 44) if int(tx) % 8 == 5 else (80, 230, 140),
                      center=(x + w * 0.32, 1.02, z), emissive=True))
    elif kind == "lockers":
        n = 3
        for i in range(n):
            cx = x - w / 2.0 + (i + 0.5) * w / n
            _w.add(r, box(w / n - 0.12, 1.9, d, tex("steel", like=(52, 64, 60), tint=True), center=(cx, 0.95, z),
                          cols={"top": (66, 78, 72)}))
            _w.add(r, box(0.02, 1.7, 0.02, (24, 30, 30), center=(cx, 0.95, z - d / 2.0 - 0.01)))
            for vy in (1.6, 1.68, 1.76):
                for sx in (-0.25, 0.25):
                    _w.add(r, box(0.3, 0.02, 0.02, (24, 30, 30), center=(cx + sx, vy, z - d / 2.0 - 0.01)))
    elif kind == "gunrack":
        _w.add(r, box(w, 1.3, d * 0.5, (30, 30, 28), center=(x, 0.65, z + d / 4.0), cols={"top": (44, 42, 38)}))
        for i in range(4):
            gx = x - w / 2.0 + 0.4 + i * (w - 0.8) / 3.0
            _w.add(r, box(0.07, 1.0, 0.1, (70, 74, 72), center=(gx, 0.7, z - 0.05)))
            _w.add(r, box(0.1, 0.24, 0.14, (40, 36, 30), center=(gx, 0.3, z - 0.05)))
    elif kind == "wallrack":
        _w.add(r, box(w, 1.3, 0.08, (48, 58, 54), center=(x, 1.25, z - d / 2.0 + 0.04)))
        for vy in (0.7, 1.45):
            _w.add(r, box(w - 0.1, 0.06, 0.26, (92, 108, 98), center=(x, vy, z - d / 2.0 + 0.15)))
        for i in range(3):                               # long guns stood in the slats
            gx = x - w / 3.0 + i * w / 3.0
            _w.add(r, box(0.07, 0.9, 0.07, (150, 146, 126), center=(gx, 1.1, z - d / 2.0 + 0.2)))
            _w.add(r, box(0.1, 0.3, 0.1, (96, 70, 46), center=(gx, 0.78, z - d / 2.0 + 0.2)))
    elif kind == "ammo":
        _w.add(r, box(w, 0.46, d, tex("steel", like=(46, 54, 46), tint=True), center=(x, 0.23, z),
                      cols={"top": (54, 62, 52)}))
        _w.add(r, box(0.03, 0.012, d - 0.12, (24, 28, 24), center=(x, 0.466, z)))
        for sx in (-0.1, 0.1):
            _w.add(r, box(0.06, 0.02, 0.06, (150, 120, 56), center=(x + sx, 0.47, z + d / 2.0 - 0.12)))
    elif kind == "briefing":
        _w.add(r, box(w, 0.06, d, (62, 60, 50), center=(x, 0.74, z)))
        _w.add(r, box(w + 0.04, 0.03, d + 0.04, (34, 32, 28), center=(x, 0.7, z)))
        for sx in (-w / 2.0 + 0.1, w / 2.0 - 0.1):
            _w.add(r, box(0.08, 0.7, d - 0.2, DARK, center=(x + sx, 0.35, z)))
        _w.add(r, box(w * 0.38, 0.01, d * 0.6, (44, 62, 50), center=(x - w * 0.22, 0.775, z)))
        for i, (px, pz) in enumerate(((0.12, -0.1), (0.24, 0.08), (0.36, -0.04))):
            _w.add(r, box(0.24, 0.01, 0.17, (128, 120, 96), center=(x + px * w, 0.78 + i * 0.002, z + pz)))
        for cx, cz in ((x - w / 2.0 - 0.35, z), (x + w / 2.0 + 0.35, z), (x, z + d / 2.0 + 0.4), (x, z - d / 2.0 - 0.4)):
            _w.add(r, box(0.42, 0.06, 0.42, (34, 38, 38), center=(cx, 0.46, cz), cols={"top": (54, 58, 56)}))
            for lx in (-0.17, 0.17):
                for lz in (-0.17, 0.17):
                    _w.add(r, box(0.04, 0.44, 0.04, DARK, center=(cx + lx, 0.22, cz + lz)))
    elif kind in ("table", "workbench"):
        h = 0.9 if kind == "workbench" else 0.76
        wood = tex("crate", like=(92, 74, 52)) if kind == "workbench" else tex("steel", like=(84, 86, 86))
        _w.add(r, box(w, 0.06, d, wood, center=(x, h - 0.03, z)))
        for sx in (-w / 2.0 + 0.06, w / 2.0 - 0.06):
            for sz in (-d / 2.0 + 0.06, d / 2.0 - 0.06):
                _w.add(r, box(0.06, h - 0.06, 0.06, DARK, center=(x + sx, (h - 0.06) / 2.0, z + sz)))
        if kind == "workbench":
            _w.add(r, box(w, 0.9, 0.04, tex("crate", like=(70, 58, 44)), center=(x, h + 0.45, z - d / 2.0)))
            _w.add(r, box(0.16, 0.14, 0.12, (60, 70, 90), center=(x - w / 2.0 + 0.2, h + 0.07, z)))
            for i, col in enumerate(((140, 40, 34), (90, 92, 94), (150, 120, 40))):
                _w.add(r, box(0.04, 0.3, 0.02, col, center=(x - 0.3 + i * 0.2, h + 0.6, z - d / 2.0 + 0.03)))
    elif kind == "bench":
        _w.add(r, box(w, 0.06, max(0.3, d), (84, 68, 48), center=(x, 0.45, z)))
        for sx in (-w / 2.0 + 0.1, w / 2.0 - 0.1):
            _w.add(r, box(0.06, 0.42, max(0.3, d) - 0.06, DARK, center=(x + sx, 0.21, z)))
    elif kind == "washers":
        n = max(1, int(round(w / 0.9)))
        for i in range(n):
            cx = x - w / 2.0 + (i + 0.5) * w / n
            _w.add(r, box(w / n - 0.06, 1.0, d, tex("steel", like=(150, 152, 150)), center=(cx, 0.5, z),
                          cols={"top": (176, 178, 176)}))
            _w.add(r, box(0.5, 0.5, 0.02, (30, 36, 40), center=(cx, 0.52, z + d / 2.0 + 0.01)))
            _w.add(r, box(0.36, 0.36, 0.02, (60, 90, 110), center=(cx, 0.52, z + d / 2.0 + 0.02)))
    elif kind == "hamper":
        _w.add(r, box(w, 0.78, d, tex("m7_plaster", like=(140, 130, 104)), center=(x, 0.39, z),
                      cols={"top": (178, 170, 150)}))
    elif kind == "rack":                                 # pull-up frame, mats either side
        frame = (96, 98, 100)
        for sz in (-d / 2.0 + 0.05, d / 2.0 - 0.05):
            _w.add(r, box(0.08, 2.1, 0.08, frame, center=(x, 1.05, z + sz)))
            _w.add(r, box(0.3, 0.04, 0.3, DARK, center=(x, 0.02, z + sz)))
        _w.add(r, box(0.05, 0.05, d, (150, 152, 154), center=(x, 2.08, z)))
        _w.add(r, box(0.9, 0.04, d * 0.8, (44, 52, 60), center=(x - 0.55, 0.02, z)))
    elif kind == "tank_h":
        rad = min(w, d) / 2.0
        m = Mesh()
        for a in (0.0, 45.0):
            m.add(box(rad * 2.0 * 0.83, rad * 2.0, max(w, d) - 0.1, steel), m=rot_z(a))
        m.add(box(rad * 2.0, rad * 2.0 * 0.83, max(w, d) - 0.1, steel))
        out = Mesh()
        out.add(m, t=(x, rad, z))
        _w.add(r, out)
        for sz in (-d / 3.0, d / 3.0):
            _w.add(r, box(rad * 1.6, rad * 0.9, 0.12, DARK, center=(x, rad * 0.45, z + sz)))
        _w.add(r, box(0.12, 0.5, 0.12, (150, 120, 40), center=(x, rad * 2.0 + 0.2, z)))
    elif kind == "tank_v":
        rad = min(w, d) / 2.0
        m = Mesh()
        for a in (0.0, 45.0):
            m.add(box(rad * 1.7, 2.2, rad * 1.7, tex("rust", like=(92, 80, 66))), m=rot_y(a))
        out = Mesh()
        out.add(m, t=(x, 1.1, z))
        _w.add(r, out)
        _w.add(r, box(rad * 1.2, 0.1, rad * 1.2, (60, 58, 54), center=(x, 2.25, z)))
        _w.add(r, box(0.1, 0.1, 0.1, (220, 60, 40), center=(x + rad * 0.86, 1.4, z), emissive=True))


def _cot(r, x0, z0, z1, blanket):
    """Wall bunk against the west wall: frame, mattress, blanket."""
    from cutscenes import m6world3d as _w
    from engine3d import box
    w = 0.72
    x = x0 + w / 2.0
    z = (z0 + z1) / 2.0
    d = abs(z1 - z0)
    _w.add(r, box(w, 0.08, d, DARK, center=(x, 0.4, z)))
    _w.add(r, box(w - 0.06, 0.1, d - 0.08, (110, 104, 88), center=(x, 0.49, z)))
    _w.add(r, box(w - 0.04, 0.04, d * 0.55, blanket, center=(x, 0.56, z - d * 0.2)))
    for sz in (-d / 2.0 + 0.05, d / 2.0 - 0.05):
        _w.add(r, box(0.05, 0.4, 0.05, DARK, center=(x + w / 2.0 - 0.05, 0.2, z + sz)))


def _toilet(r, x, z):
    from cutscenes import m6world3d as _w
    from engine3d import box
    _w.add(r, box(0.42, 0.42, 0.5, (150, 154, 156), center=(x, 0.21, z)))
    _w.add(r, box(0.3, 0.02, 0.34, (40, 44, 46), center=(x, 0.43, z + 0.02)))
    _w.add(r, box(0.42, 0.5, 0.14, (140, 144, 146), center=(x, 0.6, z + 0.25)))


def _cells(r):
    """The three neighbour cells: bunks, toilets and what each holds."""
    from cutscenes import m6world3d as _w
    from engine3d import box, tex
    for idx in range(3):
        c0 = 6 + idx * 8
        x0, _, _z = _tc(c0 + 1, 0)
        _, _, z0 = _tc(0, 9.05)
        _, _, z1 = _tc(0, 11.95)
        _cot(r, x0, z0, z1, ((70, 76, 64), (84, 70, 52), (60, 62, 70))[idx])
        tx, _, tz = _tc(c0 + 6.6, 6.45)
        _toilet(r, tx, tz)
        if idx == 0:                                        # storage shelves on the north wall
            sx, _, sz = _tc(c0 + 3.5, 6.25)
            for y in (0.5, 1.1, 1.7):
                _w.add(r, box(2.2, 0.05, 0.42, tex("steel", like=(72, 74, 76)), center=(sx, y, sz)))
            for dx in (-1.08, 1.08):
                _w.add(r, box(0.05, 1.8, 0.42, DARK, center=(sx + dx, 0.9, sz)))
            for i in range(5):
                _w.add(r, box(0.34, 0.26, 0.3, tex("crate", like=(110, 88, 56)),
                              center=(sx - 0.8 + i * 0.4, 0.66 + (i % 2) * 0.6, sz)))
        elif idx == 1:                                      # restraint chair and a tray
            cx, _, cz = _tc(c0 + 4.0, 7.3)
            _w.add(r, box(0.5, 0.08, 0.5, DARK, center=(cx, 0.48, cz)))
            _w.add(r, box(0.5, 0.7, 0.06, DARK, center=(cx, 0.85, cz + 0.24)))
            for sx in (-0.22, 0.22):
                _w.add(r, box(0.05, 0.48, 0.05, DARK, center=(cx + sx, 0.24, cz - 0.2)))
                _w.add(r, box(0.08, 0.04, 0.4, (90, 70, 46), center=(cx + sx, 0.66, cz)))
            ttx, _, ttz = _tc(c0 + 2.6, 11.2)
            _w.add(r, box(0.4, 0.03, 0.28, (120, 122, 120), center=(ttx, 0.015, ttz)))
        else:                                               # the remains on the bunk, a bucket
            bone = tex("bone", like=(176, 168, 144))
            bx, _, bz = _tc(c0 + 1.36, 10.5)
            _w.add(r, box(0.2, 0.18, 0.22, bone, center=(bx, 0.66, bz - 0.7)))
            _w.add(r, box(0.26, 0.1, 0.6, bone, center=(bx, 0.6, bz - 0.25)))
            for sx in (-0.08, 0.08):
                _w.add(r, box(0.05, 0.05, 0.7, bone, center=(bx + sx, 0.58, bz + 0.4)))
            kx, _, kz = _tc(c0 + 5.5, 11.0)
            _w.add(r, box(0.32, 0.36, 0.32, tex("rust", like=(80, 72, 60)), center=(kx, 0.18, kz)))


def _own_cell(r):
    """Biribel's cell: bunk, wall monitor and conduit, toilet, sink, drain."""
    from cutscenes import m6world3d as _w
    from engine3d import box, disc_xz
    x0, _, _z = _tc(31, 0)
    _, _, z0 = _tc(0, 9.05)
    _, _, z1 = _tc(0, 11.95)
    _cot(r, x0, z0, z1, (64, 70, 58))
    mx, _, mz = _tc(33.5, 6.08)
    _w.add(r, box(1.1, 0.68, 0.1, (22, 24, 26), center=(mx, 1.95, mz)))
    _w.add(r, box(0.96, 0.54, 0.02, (36, 56, 64), center=(mx, 1.95, mz - 0.06), emissive=True))
    _w.add(r, box(0.06, 0.8, 0.06, DARK, center=(mx, 2.7, mz + 0.02)))
    sx, _, sz = _tc(33.5, 6.52)
    _w.add(r, box(0.12, 1.2, 0.12, DARK, center=(sx, 0.6, sz)))             # monitor stand post
    tx, _, tz = _tc(36.55, 6.45)
    _toilet(r, tx, tz)
    kx, _, kz = _tc(35.6, 6.2)
    _w.add(r, box(0.5, 0.14, 0.34, (150, 154, 156), center=(kx, 0.82, kz)))
    _w.add(r, box(0.1, 0.75, 0.1, (120, 124, 126), center=(kx, 0.375, kz)))
    dc, dr = _s._DRAIN_TILE_COL, _s._DRAIN_TILE_ROW
    dx, _, dz = _tc(dc + 0.5, dr + 0.5)
    _w.add(r, disc_xz(dx, dz, 0.36, 0.004, (24, 24, 24), n=12, layer=1))
    for i in range(-2, 3):
        _w.add(r, box(0.5, 0.012, 0.035, (74, 74, 70), center=(dx, 0.008, dz + i * 0.11)))
    for i in range(3):                                        # conduit down the east wall
        cx, _, cz = _tc(36.9, 7.0 + i * 1.6)
        _w.add(r, box(0.05, 0.05, 1.5, DARK, center=(cx, 2.3, cz)))


def _fixture(r, col, row, color, key):
    """A ceiling tube in a room, or a flood pole outside."""
    from cutscenes import m6world3d as _w
    from engine3d import box
    x, _, z = _tc(col, row)
    if key == "fl":
        _m1._lamp_fixture(r, "fl_m3", col * T, row * T + 0.9 / K, color)
        return
    h = _LAMP_H.get(key, 2.5)
    if key == "wfl":                                  # flood on the yard wall, aimed in
        side = 1.0 if col < _YARD_MID[0] else -1.0
        _w.add(r, box(0.5, 0.12, 0.14, DARK, center=(x + side * 0.25, h, z)))
        _w.add(r, box(0.34, 0.26, 0.4, (40, 42, 44), center=(x + side * 0.55, h - 0.05, z)))
        _w.add(r, box(0.02, 0.2, 0.32, color, center=(x + side * 0.73, h - 0.07, z), emissive=True))
        return
    if key == "exit":
        _w.add(r, box(0.7, 0.28, 0.08, (24, 40, 30), center=(x, h, z)))
        _w.add(r, box(0.6, 0.18, 0.02, color, center=(x, h, z - 0.05), emissive=True))
        return
    # in-room tubes have no mesh: seen through the roof they hung over heads


# ── walls and doors ────────────────────────────────────────────────────

def _wall_kind(col, row):
    if _glyph(col, row) != "C":
        return None
    w, h = _dims()
    if row in (0, h - 1) or col in (0, w - 1):
        return "border"
    if _key() == "archives":                  # free-standing C runs: stacks and cubicle walls
        if 6 <= col <= 17 and 20 <= row <= 34:
            return "shelf"
        if 30 <= col <= 41 and 20 <= row <= 34:
            return "cube"
    return "block"


def _wall_boxes():
    """Merged wall boxes (col, row, w, h, kind) in tiles: horizontal runs,
    then identical runs stacked down."""
    key = id(_maps.MISSION3_MAP)
    hit = _cache["walls"]
    if hit is not None and hit[0] == key:
        return hit[1]
    mw, mh = _dims()
    runs = {}
    for row in range(mh):
        col = 0
        while col < mw:
            kind = _wall_kind(col, row)
            if kind is None:
                col += 1
                continue
            end = col
            while end + 1 < mw and _wall_kind(end + 1, row) == kind:
                end += 1
            runs[(row, col)] = [kind, col, row, end + 1 - col, 1]
            col = end + 1
    out = []
    for row in range(mh):
        for k in sorted(k for k in runs if k[0] == row):
            run = runs.pop(k, None)
            if run is None:
                continue
            kind, c0, r0, w, h = run
            while True:
                below = runs.get((r0 + h, c0))
                if below is None or below[0] != kind or below[3] != w:
                    break
                runs.pop((r0 + h, c0))
                h += 1
            out.append((c0, r0, w, h, kind))
    _cache["walls"] = (key, out)
    return out


def _wall_mesh(kind, w, d, hgt):
    """A wall box: whitewash over a painted dado (bare concrete on the
    border), a grime foot, a flat dark top."""
    wall, dado = _WALLS.get(_key(), _WALLS["cell"])
    key = ("wall", kind, round(w, 3), round(d, 3), hgt, wall)
    m = _cache["meshes"].get(key)
    if m is not None:
        return m
    from engine3d import Mesh, box, tex
    cut = hgt < WALL_H[kind] - 0.01
    if kind in ("shelf", "cube"):
        m = _cache["meshes"][key] = (_shelf_mesh if kind == "shelf" else _cube_mesh)(w, d, hgt, cut)
        return m
    body = BORDER if kind == "border" else wall
    low = _shade(BORDER, 0.78) if kind == "border" else dado
    m = Mesh()
    m.add(box(w, hgt, d, tex("concrete", like=body, tint=True), center=(0.0, hgt / 2.0, 0.0),
              cols={"top": CUT_CAP if cut else CAP}))
    for y0, y1, col in ((0.0, DADO_H, low), (0.0, 0.22, _shade(low, 0.62))):
        y1 = min(y1, hgt - 0.02)
        if y1 > y0:
            grow = 0.02 if y0 == 0.0 and y1 > 0.3 else 0.03
            m.add(box(w + grow, y1 - y0, d + grow, tex("concrete", like=col, tint=True),
                      center=(0.0, (y0 + y1) / 2.0, 0.0), skip=("top", "bottom")))
    if kind != "border" and hgt > DADO_H + 0.1:
        m.add(box(w + 0.025, 0.05, d + 0.025, _shade(dado, 0.7), center=(0.0, DADO_H, 0.0),
                  skip=("top", "bottom")))
    _cache["meshes"][key] = m
    return m


_BOOKS = ((112, 44, 38), (52, 70, 96), (126, 104, 60), (60, 84, 58), (138, 126, 104), (84, 52, 70))


def _shelf_mesh(w, d, hgt, cut):
    """Archive stack: a dark wood carcass, shelf boards, book spines down
    both long faces."""
    from engine3d import Mesh, box, tex
    m = Mesh()
    m.add(box(w, hgt, d, tex("crate", like=(66, 48, 32)), center=(0.0, hgt / 2.0, 0.0),
              cols={"top": CUT_CAP if cut else (40, 30, 22)}))
    along_x = w >= d
    span = w if along_x else d
    n = max(1, int(span / 0.32))
    for k, y in enumerate(y for y in (0.12, 0.62, 1.12, 1.62) if y + 0.4 < hgt):
        for i in range(n):
            col = _BOOKS[_hash(i, k, len(_BOOKS))]
            hb = 0.3 + 0.06 * _hash(i + 5, k, 3)
            a = -span / 2.0 + (i + 0.5) * span / n
            for side in (-1.0, 1.0):
                if along_x:
                    m.add(box(span / n - 0.03, hb, 0.02, col, center=(a, y + hb / 2.0, side * (d / 2.0 + 0.01))))
                else:
                    m.add(box(0.02, hb, span / n - 0.03, col, center=(side * (w / 2.0 + 0.01), y + hb / 2.0, a)))
        m.add(box(w + 0.04, 0.04, d + 0.04, (84, 62, 42), center=(0.0, y - 0.02, 0.0), skip=("top", "bottom")))
    return m


def _cube_mesh(w, d, hgt, cut):
    """Cubicle partition: blue-grey fabric on a steel frame, a pale top rail."""
    from engine3d import Mesh, box, tex
    m = Mesh()
    m.add(box(w, hgt, d, tex("m7_plaster", like=(70, 78, 92), tint=True), center=(0.0, hgt / 2.0, 0.0),
              cols={"top": CUT_CAP if cut else (92, 96, 104)}))
    m.add(box(w + 0.03, 0.08, d + 0.03, (40, 42, 46), center=(0.0, 0.04, 0.0), skip=("top", "bottom")))
    return m


def _solid(col, row):
    return _glyph(col, row) in ("C", "D", "")


def _rim_mesh(sc, sr, sw, sh, hgt, full=WALL_H["block"]):
    """The lip round a wall run's top, only on edges that face open floor:
    the outline that tells wall from floor at a glance."""
    def build():
        from engine3d import Mesh, box
        m = Mesh()
        cut = hgt < full - 0.01
        col = RIM_CUT if cut else RIM
        y, t, tk = hgt + 0.012, 0.07, 0.024
        cx, cz = (sc + sw / 2.0) * T * K, -(sr + sh / 2.0) * T * K

        def run(cells, edge):
            i = 0
            while i < len(cells):
                if not cells[i][1]:
                    i += 1
                    continue
                j = i
                while j + 1 < len(cells) and cells[j + 1][1]:
                    j += 1
                a, b = cells[i][0], cells[j][0] + 1
                if edge in ("n", "s"):
                    zz = -(sr if edge == "n" else sr + sh) * T * K + (-t / 2.0 if edge == "n" else t / 2.0)
                    m.add(box((b - a) * T * K, tk, t, col,
                              center=((a + b) / 2.0 * T * K - cx, y, zz - cz)))
                else:
                    xx = (sc if edge == "w" else sc + sw) * T * K + (t / 2.0 if edge == "w" else -t / 2.0)
                    m.add(box(t, tk, (b - a) * T * K, col,
                              center=(xx - cx, y, -(a + b) / 2.0 * T * K - cz)))
                i = j + 1
        run([(c, not _solid(c, sr - 1)) for c in range(sc, sc + sw)], "n")
        run([(c, not _solid(c, sr + sh)) for c in range(sc, sc + sw)], "s")
        run([(rw, not _solid(sc - 1, rw)) for rw in range(sr, sr + sh)], "w")
        run([(rw, not _solid(sc + sw, rw)) for rw in range(sr, sr + sh)], "e")
        return m
    return _mesh(("rim", sc, sr, sw, sh, round(hgt, 3), full), build)


def _cut(zone, snap, c, row):
    k = _m1._cut_level(("m3", c, row), _m1._hides(zone, c * T, row * T, (c + 1) * T, (row + 1) * T), snap)
    return round(k * 8) / 8.0


def _draw_walls(r):
    """Wall boxes at full height, except the stretch between the camera
    and Biribel, which sinks to a stub (the M1 cutaway)."""
    zone = _m1._cut_zone()
    snap = _m1._cut_snap()
    for c0, r0, w, h, kind in _wall_boxes():
        along_x = w >= h
        n = w if along_x else h
        levels = [min(_cut(zone, snap, c0 + i, r0 + j) for j in range(h)) if along_x else
                  min(_cut(zone, snap, c0 + j, r0 + i) for j in range(w)) for i in range(n)]
        i = 0
        while i < n:
            j = i
            while j + 1 < n and levels[j + 1] == levels[i]:
                j += 1
            if along_x:
                sc, sr, sw, sh = c0 + i, r0, j - i + 1, h
            else:
                sc, sr, sw, sh = c0, r0 + i, w, j - i + 1
            full = WALL_H[kind]
            hgt = STUB_H + (full - STUB_H) * levels[i]
            cx, _, cz = to3((sc + sw / 2.0) * T, (sr + sh / 2.0) * T)
            _put(r, _wall_mesh(kind, sw * T * K, sh * T * K, hgt), (cx, 0.0, cz))
            _put(r, _rim_mesh(sc, sr, sw, sh, hgt, full), (cx, 0.0, cz))
            i = j + 1


def _door_tiles():
    key = id(_maps.MISSION3_MAP)
    hit = _cache["doors"]
    if hit is not None and hit[0] == key:
        return hit[1]
    out = []
    w, h = _dims()
    for row in range(h):
        for col in range(w):
            if _glyph(col, row) != "D":
                continue
            along_x = _glyph(col, row - 1) not in ("C", "")
            if along_x:
                slide = -1 if _glyph(col - 1, row) == "C" else 1
            else:
                slide = -1 if _glyph(col, row - 1) == "C" else 1
            out.append((col, row, along_x, slide))
    _cache["doors"] = (key, out)
    return out


def _door_mesh(style, hgt, locked):
    """Door panel spanning x (one tile), ``hgt`` tall, LED on the +z face."""
    def build():
        from engine3d import Mesh, box, tex
        m = Mesh()
        w = T * K - 0.08
        if style == "bars":
            m.add(box(w, 0.08, 0.1, DARK, center=(0.0, hgt - 0.04, 0.0)))
            m.add(box(w, 0.08, 0.1, DARK, center=(0.0, 0.04, 0.0)))
            m.add(box(w, 0.06, 0.08, DARK, center=(0.0, hgt * 0.5, 0.0)))
            for i in range(7):
                m.add(box(0.04, hgt, 0.04, (88, 92, 96), center=(-w / 2.0 + 0.1 + i * (w - 0.2) / 6.0,
                                                                 hgt / 2.0, 0.0)))
        else:
            m.add(box(w, hgt, 0.12, tex("steel", like=(60, 66, 70)), center=(0.0, hgt / 2.0, 0.0)))
            if hgt > 1.7:
                m.add(box(0.36, 0.24, 0.13, (30, 44, 52), center=(0.0, 1.6, 0.0)))
            m.add(box(0.08, 0.2, 0.14, (110, 112, 110), center=(w / 2.0 - 0.18, min(hgt - 0.2, 1.0), 0.0)))
        led = (220, 40, 34) if locked else (60, 220, 110)
        m.add(box(0.06, 0.06, 0.02, led, center=(w / 2.0 - 0.1, min(hgt - 0.1, 1.35), 0.08), emissive=True))
        return m
    return _mesh(("door", style, hgt, locked), build)


def _draw_doors(r):
    """Every D tile: lintel to wall height, the panel slid by its open
    progress, and Biribel's blown door down in the corridor."""
    from engine3d import box
    zone = _m1._cut_zone()
    snap = _m1._cut_snap()
    for col, row, along_x, slide in _door_tiles():
        _door, locked, open_p, _breach, _hits = _s._m3_door_tile_state(col, row)
        level = _cut(zone, snap, col, row)
        hgt = STUB_H + (WALL_H["block"] - STUB_H) * level
        x, _, z = _tc(col + 0.5, row + 0.5)
        yaw = 0.0 if along_x else 90.0
        if hgt > DOOR_H + 0.05:
            wall = _WALLS.get(_key(), _WALLS["cell"])[0]
            lin = _mesh(("lintel", round(hgt, 3), wall), lambda h=hgt, c=wall: box(T * K, h - DOOR_H, T * K, c,
                                                                    center=(0.0, (h + DOOR_H) / 2.0, 0.0),
                                                                    cols={"top": CAP if h >= WALL_H["block"] - 0.01 else CUT_CAP}))
            _put(r, lin, (x, 0.0, z))
            _put(r, _rim_mesh(col, row, 1, 1, hgt), (x, 0.0, z))
        cell_row = row == _d._DOOR_TILE_ROW and _key() == "cell"
        blown = cell_row and col in (_d._DOOR_TILE_COL, _d._DOOR_TILE_COL + 1) and open_p >= 1.0
        if blown:
            if col == _d._DOOR_TILE_COL:
                _blown_door(r, x + T * K / 2.0, z)
            continue
        if open_p >= 0.98:
            continue
        off = slide * open_p * (T * K - 0.1)
        pos = (x + off, 0.0, z) if along_x else (x, 0.0, z - off)
        style = "bars" if cell_row else "slab"
        _put(r, _door_mesh(style, round(min(DOOR_H, hgt), 2), bool(locked)), pos, yaw=yaw)


def _blown_door(r, x, z):
    """Volkov's charge: the barred panel flat in the corridor, a scorch mark."""
    from engine3d import Mesh, box, quad_xz, tex
    def build():
        m = Mesh()
        w = 2 * T * K - 0.2
        m.add(box(w, 0.08, 1.9, DARK, center=(0.0, 0.04, 0.0)))
        for i in range(10):
            m.add(box(0.05, 0.05, 1.8, (78, 80, 84), center=(-w / 2.0 + 0.15 + i * (w - 0.3) / 9.0, 0.1, 0.0)))
        return m
    def scorch():
        m = Mesh()
        m.add(quad_xz(-1.4, -1.2, 1.4, 1.2, 0.005, tex("scorch", like=(36, 32, 28)), layer=1))
        return m
    _put(r, _mesh(("scorch",), scorch), (x, 0.0, z - T * K * 0.6))
    _put(r, _mesh(("blown",), build), (x + 0.2, 0.0, z - T * K * 1.1), yaw=8.0)


# ── story props ────────────────────────────────────────────────────────

def _draw_story_props(r, tm):
    """The interrogation chair (whole, or broken), the vent grate and the
    armory K-9 rack: the pieces the breakout changes."""
    from engine3d import Mesh, box
    from cutscenes import m6fx3d as _fx
    cx, cy = _wd._interrogation_chair_pos()
    x, _, z = to3(cx, cy)
    broken = bool(getattr(STATE, "mission3_chair_broken", False))

    def chair():
        m = Mesh()
        if broken:
            m.add(box(0.5, 0.06, 0.5, DARK, center=(0.0, 0.03, 0.0)))
            m.add(box(0.5, 0.06, 0.6, DARK, center=(0.1, 0.03, -0.55)))
            m.add(box(0.05, 0.05, 0.48, DARK, center=(-0.45, 0.03, 0.2)))
            m.add(box(0.08, 0.02, 0.4, (90, 70, 46), center=(0.4, 0.01, 0.3)))
        else:
            m.add(box(0.5, 0.08, 0.5, DARK, center=(0.0, 0.48, 0.0)))
            m.add(box(0.5, 0.7, 0.06, DARK, center=(0.0, 0.85, -0.24)))
            for sx in (-0.22, 0.22):
                for sz in (-0.2, 0.2):
                    m.add(box(0.05, 0.48, 0.05, DARK, center=(sx, 0.24, sz)))
        return m
    _put(r, _mesh(("chair", broken), chair), (x, 0.0, z))
    vx, _, vz = _tc(_wd._VENT_GRATE_COL + 0.5, _wd._VENT_GRATE_ROW + 0.45)
    vent_open = bool(getattr(STATE, "mission3_vent_open", False))

    def vent():
        m = Mesh()
        m.add(box(0.9, 0.012, 0.56, (14, 14, 16) if vent_open else (30, 30, 30), center=(0.0, 0.006, 0.0)))
        if vent_open:
            m.add(box(0.9, 0.04, 0.56, (70, 72, 70), center=(0.3, 0.04, 0.4)))
        else:
            for i in range(-3, 4):
                m.add(box(0.04, 0.02, 0.5, (74, 74, 70), center=(i * 0.12, 0.012, 0.0)))
        return m
    _put(r, _mesh(("vent", vent_open), vent), (vx, 0.0, vz))
    kx, _, kz = _tc(_wd._K9_STAND_COL + 0.5, _wd._K9_STAND_ROW + 0.15)
    _put(r, _mesh(("k9rack",), lambda: box(1.0, 0.9, 0.08, (52, 46, 38), center=(0.0, 1.3, 0.0))), (kx, 0.0, kz))
    if not getattr(STATE, "k9_unlocked", False):
        from ui import mp3d
        gun, _mz = mp3d.gun("k9_smg")
        _put(r, gun, (kx - 0.3, 1.32, kz - 0.08), yaw=90.0, roll=90.0)
        r.add_sprite((kx, 1.3, kz - 0.1), _glow((255, 210, 120), 0.5, tm, 0.5, 18), layer=_fx.FX_LAYER)


# ── cast ───────────────────────────────────────────────────────────────

def _melee_hum(weapon):
    """Biribel holding the chair leg or the shiv where the pistol would sit."""
    key = ("m3melee", weapon)
    h = _cache["meshes"].get(key)
    if h is not None:
        return h
    from engine3d import Humanoid, Mesh, box
    from cutscenes.cast3d import spec3d
    from ui import mp3d
    s = spec3d("biribel", **PRISONER)
    h = Humanoid(s)
    m = Mesh()
    if weapon == "chair_leg":
        m.add(box(0.05, 0.05, 0.62, (70, 58, 44), center=(0.0, 0.0, 0.27)))
        m.add(box(0.07, 0.07, 0.08, (54, 44, 34), center=(0.0, 0.0, 0.56)))
        tip = 0.6
    else:
        m.add(box(0.04, 0.04, 0.1, (60, 54, 46), center=(0.0, 0.0, 0.02)))
        m.add(box(0.015, 0.03, 0.16, (170, 172, 168), center=(0.0, 0.0, 0.15)))
        tip = 0.23
    h._rifle = m
    h._weapon = mp3d.HOLD_BY_RIG["pistol"]
    h._muzzle_z = tip
    h._gl_spec_key = repr(sorted(s.items())) + "|td|m3_%s" % weapon
    _cache["meshes"][key] = h
    return h


def _unarmed(r, hum, x, y, angle, key, tint=None):
    from engine3d import POSES, pose_run
    phase, moving = _m1._motion(key, x, y, angle)
    pose = pose_run(phase, lean=3) if moving else dict(POSES["stand"])
    r.add_humanoid(hum, pose, to3(x, y), td.yaw_rad(angle), rifle_on=False, tint=tint)


def _draw_player(r, flashes):
    p = STATE.player
    if p is None:
        return
    x, y = p.rect.centerx, p.rect.centery
    if STATE.player_dead:
        _m1._draw_dead_player(r, td.armed("biribel", "pistol", **PRISONER))
        return
    _m1._feet(r, x, y, _m1.RING_YOU, rad=0.52)
    weapon = getattr(STATE, "mission3_weapon", "none")
    if getattr(STATE, "player_disarmed", False) or weapon == "none":
        _unarmed(r, td.armed("biribel", "pistol", **PRISONER), x, y, p.angle, "player")
        return
    if weapon in ("chair_leg", "shiv"):
        melee = _s._mission3_melee_progress() if getattr(STATE, "melee_active", False) else None
        _m1._body(r, _melee_hum(weapon), x, y, p.angle, "pistol", "ready", "player", melee=melee)
        return
    rig = p.rig_weapon_name()
    mode = "ready" if STATE.is_reloading else "aim"
    _m1._body(r, td.armed("biribel", rig, **PRISONER), x, y, p.angle, rig, mode, "player", flashes,
              STATE.muzzle_flash_timer > 0)


def _shield_mesh():
    from engine3d import Mesh, box
    m = Mesh()
    m.add(box(0.7, 1.3, 0.06, (44, 50, 56), center=(0.0, 0.85, 0.0)))
    m.add(box(0.5, 0.12, 0.07, (90, 110, 120), center=(0.0, 1.25, 0.0)))
    m.add(box(0.6, 0.06, 0.07, (180, 170, 60), center=(0.0, 0.5, 0.0)))
    return m


def _draw_enemies(r, flashes, tm):
    for e in STATE.enemies:
        if getattr(e, "hp", 1) <= 0:
            continue
        kind = getattr(_s._m3l(e), "kind", None) or "guard"
        rig, spec = _FOE.get(kind, _FOE["guard"])
        hum = td.armed("ipa", rig, **dict({"jacket": _m1.IPA}, **spec))
        mode = "aim" if e.state in ("CHASE", "ATTACK") else "ready"
        burn = getattr(e, "burn", 0)
        tint = _m1.CHAR if burn else (e.body_tint, 0.55) if getattr(e, "body_tint", None) else None
        x, y = e.rect.centerx, e.rect.centery
        _m1._feet(r, x, y, _m1.RING_FOE.get(e.state, RING_CALM))
        _m1._body(r, hum, x, y, e.angle, rig, mode, ("e", e.uid), tint=tint)
        if kind == "shield":
            ox, oy = math.cos(e.angle) * 22.0, math.sin(e.angle) * 22.0
            _put(r, _mesh(("shield",), _shield_mesh), to3(x + ox, y + oy),
                 yaw=td.yaw_of(math.degrees(e.angle)))
        _m1._burning(r, x, y, min(1.0, burn / 40.0), tm, e.uid * 5, flashes)


def _detainee_hum(d):
    cloth, dark, hi, stripe, skin, hair, _o, _c = _wd._detainee_palette(d.get("seed", 0), d.get("room", "yard"))
    return td.armed("civilian", "pistol", jacket=cloth, pants=dark, long_coat=None, vest=None,
                    pouches=False, lapel=None, shirt=None, armband=stripe, cuff=hi, skin=skin, hair=hair)


def _draw_detainees(r):
    from engine3d import POSES
    p = STATE.player
    for i, d in enumerate(getattr(STATE, "mission3_detainees", ()) or ()):
        x, y = _wd._detainee_draw_pos(d)
        hum = _detainee_hum(d)
        at = to3(x, y)
        if d.get("dead"):
            r.add_sprite((at[0], 0.02, at[2]), td.blood_pool(0.7), layer=0)
            r.add_humanoid(hum, dict(POSES["dead_back"]), at, td.yaw_rad(d.get("seed", 0) * 0.7),
                           rifle_on=False)
            continue
        pose = d.get("pose", "stand")
        key = ("det", i)
        r.add_sprite((at[0], 0.02, at[2]), td.shadow(0.42), layer=0)
        if pose == "pace_x" and d.get("state") != "cower":
            ang = 0.0 if math.cos(d.get("timer", 0) * 0.025 + d.get("seed", 0)) >= 0 else math.pi
            _unarmed(r, hum, x, y, ang, key)
            continue
        if p is not None and pose not in ("bars", "pushup", "worker"):
            ang = math.atan2(p.rect.centery - y, p.rect.centerx - x)
        else:
            ang = math.pi / 2.0 if pose == "bars" else d.get("seed", 0) * 1.3
        name = ("crouch" if d.get("state") == "cower" or pose == "cower" else
                {"bars": "ready", "sit": "slump", "pushup": "prone", "worker": "kneel_over",
                 "lean": "stand", "fold": "stand"}.get(pose, "stand"))
        r.add_humanoid(hum, dict(POSES[name]), at, td.yaw_rad(ang), rifle_on=False)


def _draw_inmate(r):
    if not getattr(STATE, "m3_black_ledger_inmate_active", False):
        return
    inmate = getattr(STATE, "m3_black_ledger_inmate", None)
    if not inmate:
        return
    x, y = inmate["x"], inmate["y"]
    p = STATE.player
    ang = math.atan2(p.rect.centery - y, p.rect.centerx - x) if p is not None else math.pi / 2.0
    r.add_sprite(to3(x, y, 0.02), td.shadow(0.5), layer=0)
    _unarmed(r, td.armed("civilian", "pistol", **INMATE), x, y, ang, "inmate")


def _draw_cast(r, flashes, tm):
    _m1._draw_corpses(r, flashes, tm)
    _draw_detainees(r)
    _draw_enemies(r, flashes, tm)
    _draw_inmate(r)
    _draw_volkov(r, flashes, tm)
    _draw_player(r, flashes)


def _draw_volkov(r, flashes, tm):
    """Volkov covering Biribel through the wings, his tracer cues and the
    K-9 mags he throws."""
    from cutscenes import m6fx3d as _fx
    if not getattr(STATE, "m3_volkov_ally_active", False) or _key() == "cell":
        return
    x = getattr(STATE, "m3_volkov_ally_x", 0.0)
    y = getattr(STATE, "m3_volkov_ally_y", 0.0)
    shots = getattr(STATE, "m3_volkov_ally_shots", None) or ()
    _m1._feet(r, x, y, (110, 170, 230), rad=0.48)
    _m1._body(r, td.armed("volkov", "os12"), x, y, getattr(STATE, "m3_volkov_ally_angle", 0.0), "os12",
              "aim" if shots else "ready", "volkov_m3", flashes, bool(shots))
    for x1, y1, x2, y2, _life in shots:
        r.add_line3d(to3(x1, y1, AIM_H), to3(x2, y2, AIM_H), (255, 190, 90), 2, layer=4)
    for mag in getattr(STATE, "m3_volkov_mags", None) or ():
        if mag.get("caught"):
            continue
        p = to3(mag["x"], mag["y"], 0.9)
        _put(r, _mesh(("k9mag",), lambda: _m1._pickup_mesh("mag")), p, yaw=math.degrees(mag.get("rot", 0.0)))
        r.add_sprite(p, _glow((255, 210, 120), 0.2, tm, 0.6, 12), layer=_fx.FX_LAYER)


def _draw_fx(r, flashes, tm):
    from cutscenes import m6fx3d as _fx
    from core.config import C_BULLET
    from engine3d import m_apply, m_mul, rot_x, rot_y
    from ui import mp3d
    t = _now_s()
    for pu in STATE.pickups:
        x, _, z = to3(pu[0], pu[1])
        bob = 0.06 * math.sin(t * 3 + pu[0])
        kind = pu[2]
        if kind == "sidearm":
            gun, _mz = mp3d.gun("pistol")
            _put(r, gun, (x, 0.25 + bob, z), yaw=(t * 60.0 + pu[0]) % 360.0, roll=90.0)
            col = (220, 180, 80)
        else:
            kind = "bandage" if kind == "bandage" else "mag"
            _put(r, _mesh(("pickup", kind), lambda k=kind: _m1._pickup_mesh(k)), (x, 0.25 + bob, z),
                 yaw=(t * 60.0 + pu[0]) % 360.0)
            col = _m1._PICKUP_COL.get(kind, (255, 210, 40))
        r.add_sprite((x, 0.3, z), _glow(col, 0.28, tm, 0.7, 16), layer=_fx.FX_LAYER)
    for decal in STATE.blood_decals:
        k = max(0.0, min(1.0, decal[2] / 255.0))
        if k > 0.05:
            r.add_sprite(to3(decal[0], decal[1], 0.015),
                         td.blood_pool(min(1.0, decal[3] / 24.0) * k, (80, 12, 14)), layer=0)
    for fz in STATE.fire_zones:
        x, _, z = to3(fz.x, fz.y)
        life = fz.life / float(max(1, fz.max_life))
        heat = min(1.0, life * 4.0)
        rad = fz.radius * K
        r.add_sprite((x, 0.02, z), td.blood_pool(min(1.0, rad / 2.0), (26, 18, 14)), layer=0)
        _m1._fuel_pool_at(r, x, z, rad * (0.55 + 0.45 * heat), fz.x * 0.37 + fz.y * 0.11)
        n = 1 + min(9, int(rad / 0.3))
        for i in range(n):
            a = i * 2.39996 + fz.x * 0.013
            d = 0.0 if i == 0 else rad * 0.8 * math.sqrt(i / float(n))
            size = (0.5 if i == 0 else 0.34) * min(1.2, 0.4 + rad * 0.35) * heat
            _m1._fire(r, (x + math.cos(a) * d, 0.0, z + math.sin(a) * d), tm, int(fz.x) + i, size,
                      glow=i == 0)
        flashes.append({"pos": (x, 1.0, z), "color": (255, 140, 56), "intensity": heat, "range": 4.0 + rad})
    for b in STATE.thrown_bottles:
        bt = b["t"]
        p = to3(b["x"], b["y"], 0.9 + math.sin(bt * math.pi) * 1.2)
        yaw = td.yaw_of(math.degrees(math.atan2(b["ty"] - b["start_y"], b["tx"] - b["start_x"])))
        mesh, flame = _m1._molotov()
        pitch = (b.get("spin", 0) + bt * 540) % 360.0
        _put(r, mesh, p, yaw=yaw, pitch=pitch)
        fx, fy, fzz = m_apply(m_mul(rot_y(yaw), rot_x(pitch)), flame)
        r.add_sprite((p[0] + fx, p[1] + fy, p[2] + fzz),
                     _glow((255, 140, 40), 0.22, tm, 1.0, 16, flicker=0.55, seed=int(p[2] * 100),
                           core=(255, 200, 120)), layer=_fx.FX_LAYER)
        r.add_sprite((p[0], 0.02, p[2]), td.shadow(0.16, alpha=120), layer=0)
    for b in STATE.bullets:
        head = to3(b["x"], b["y"], AIM_H)
        tail = to3(b.get("prev_x", b["x"] - b["dx"]), b.get("prev_y", b["y"] - b["dy"]), AIM_H)
        r.add_line3d(tail, head, (255, 220, 140), 2, layer=4)
        r.add_sprite(head, _glow(C_BULLET, 0.12, tm, 0.9, 10), layer=_fx.FX_LAYER)
    td.dots(r, [(to3(p.x, p.y, 0.25 + 0.03 * getattr(p, "life", 0)), p.color, getattr(p, "size", 2))
                for p in STATE.particles], layer=_fx.FX_LAYER)
    td.dots(r, [(to3(c.x, c.y, 0.03), (200, 160, 70), 2) for c in STATE.casings], layer=1)


# ── lights ─────────────────────────────────────────────────────────────

def _lamp_head(col, row, key):
    x, _, z = _tc(col, row)
    if key == "fl":
        return (x, 4.1, z)
    if key == "wfl":
        x += (0.7 if col < _YARD_MID[0] else -0.7)
    return (x, _LAMP_H.get(key, 2.5) - 0.05, z)


def _pool_at(col, row, key):
    """Where a lamp's floor pool sits: under it, or thrown into the yard."""
    hx, _, hz = _lamp_head(col, row, key)
    if key == "wfl":
        mx, _, mz = _tc(*_YARD_MID)
        return (hx + (mx - hx) * 0.3, hz + (mz - hz) * 0.3)
    return (hx, hz)


def _lamp_lights(r, v, flashes, tm):
    """Lamp pools light the baked floor; the lamps nearest the camera focus
    plus the flashes are the eight per-frame lights."""
    fx, fz = v.tgt[0], v.tgt[2]
    pools, near = [], []
    for col, row, rad, color, key in _lamps():
        head = _lamp_head(col, row, key)
        reach = rad * K * 1.6
        pools.append({"pos": head, "range": reach, "color": color, "intensity": 2.0,
                      "hot": td.mix(color, (255, 250, 235), 0.5)})
        near.append(((head[0] - fx) ** 2 + (head[2] - fz) ** 2,
                     {"pos": head, "color": color, "intensity": 0.45, "range": reach}))
    p = STATE.player
    if p is not None:
        flashes.append({"pos": to3(p.rect.centerx, p.rect.centery, 1.7), "color": (190, 205, 230),
                        "intensity": 0.8, "range": 3.0})
    near.sort(key=lambda e: e[0])
    lights = [e[1] for e in near[:max(0, 8 - len(flashes))]]
    r.set_pools(pools)
    r.set_lights(flashes[:8] + lights, cap=8)


_POOL_K = {"cell": 0.5, "cor": 0.5, "exit": 0.45, "kit": 0.45, "hall": 0.5, "arm": 0.5, "low": 0.5,
           "lau": 0.48, "fl": 0.6, "wfl": 0.6, "mnt": 0.5}


def _presence():
    """Faint pools round Biribel and the live guards: nobody vanishes
    between the tubes."""
    p = STATE.player
    if p is None or STATE.player_dead:
        return []
    x, _, z = to3(p.rect.centerx, p.rect.centery)
    out = [("pool", (x, 0.0, z), (150, 160, 178), 2.4, 0.2)]
    for e in STATE.enemies:
        if getattr(e, "hp", 1) > 0:
            ex, _, ez = to3(e.rect.centerx, e.rect.centery)
            out.append(("pool", (ex, 0.0, ez), (170, 160, 150), 1.6, 0.12))
    return out


def _night_lights():
    """Fixed lights for the grade: each tube's throw and bulb."""
    lamps = _lamps()
    hit = _cache["night"].get(lamps)
    if hit is not None:
        return hit
    out = []
    for col, row, rad, color, key in lamps:
        px, pz = _pool_at(col, row, key)
        out.append(("pool", (px, 0.0, pz), color, rad * K * 1.6 * 0.72,
                    _POOL_K.get(key, _wings.POOL_K.get(key, 0.45))))
        if key in ("fl", "wfl", "exit"):                 # only fixtures you can see glow
            out.append(("glow", _lamp_head(col, row, key), color, 0.5, 0.45))
    _cache["night"][lamps] = out
    return out


# ── screen space ───────────────────────────────────────────────────────

_PLAQUES = {}
# stencils the 2D set prints on props: (col, row, height m, text, colour)
_TAGS = ((38.42, 22.93, 0.47, "9MM", (120, 150, 120)), (42.62, 22.93, 0.47, "SMG", (120, 150, 120)))


def _tag(text, col):
    hit = _PLAQUES.get(("tag", text))
    if hit is None:
        hit = _PLAQUES[("tag", text)] = font_terminal_small.render(text, True, col)
    return hit


def _plaque(idx):
    """The 2D neighbour-cell plaque: label, sub line, accent bar."""
    import pygame
    hit = _PLAQUES.get(idx)
    if hit is not None:
        return hit
    theme = _d._NEIGHBOR_THEMES[idx]
    accent = theme["accent"]
    lbl = font_terminal_small.render(theme["label"], True, accent)
    sub = font_terminal_small.render(theme["sub"], True, (140, 130, 110))
    w = max(lbl.get_width(), sub.get_width()) + 16
    h = lbl.get_height() + sub.get_height() + 8
    out = pygame.Surface((w, h), pygame.SRCALPHA)
    out.fill((0, 0, 0, 176))
    pygame.draw.rect(out, (*accent, 150), out.get_rect(), 1)
    pygame.draw.rect(out, (*accent, 190), (0, 0, 4, h))
    out.blit(lbl, (9, 4))
    out.blit(sub, (9, 4 + lbl.get_height()))
    _PLAQUES[idx] = out
    return out


def _room_plaque(text, accent):
    import pygame
    hit = _PLAQUES.get(("room", text))
    if hit is None:
        lbl = font_terminal_small.render(text, True, accent)
        w, h = lbl.get_width() + 16, lbl.get_height() + 6
        hit = pygame.Surface((w, h), pygame.SRCALPHA)
        hit.fill((0, 0, 0, 170))
        pygame.draw.rect(hit, (*accent, 140), hit.get_rect(), 1)
        pygame.draw.rect(hit, (*accent, 190), (0, 0, 4, h))
        hit.blit(lbl, (9, 3))
        _PLAQUES[("room", text)] = hit
    return hit


def _wing_plaques(s, v):
    """Room names on each room's north wall, like the cell plaques."""
    accent = _wings.ACCENT[_key()]
    for col, row, text in _wings.PLAQUES.get(_key(), ()):
        pt = v.screen_sim(col * T, row * T, 2.3)
        if pt is None or not (-200 < pt[0] < WIDTH + 40 and -40 < pt[1] < HEIGHT + 40):
            continue
        img = _room_plaque(text, accent)
        s.blit(img, (int(pt[0]), int(pt[1]) - img.get_height()))


def _labels(s, v):
    """Cell plaques, detainee barks and the unpinned floating texts, as the
    2D world pass draws them, anchored over the 3D set."""
    import pygame
    if _key() != "cell":
        _wing_plaques(s, v)
    for tx, ty, h, text, col in (_TAGS if _key() == "cell" else ()):
        pt = v.screen_sim(tx * T, ty * T, h)
        if pt is None or not (-40 < pt[0] < WIDTH + 40 and -40 < pt[1] < HEIGHT + 40):
            continue
        img = _tag(text, col)
        s.blit(img, (int(pt[0]) - img.get_width() // 2, int(pt[1]) - img.get_height() // 2))
    for idx in (range(3) if _key() == "cell" else ()):
        pt = v.screen_sim((7.15 + 8 * idx) * T, 13.0 * T, 2.45)   # over the cell door, corridor face
        if pt is None or not (-200 < pt[0] < WIDTH + 40 and -40 < pt[1] < HEIGHT + 40):
            continue
        img = _plaque(idx)
        s.blit(img, (int(pt[0]), int(pt[1]) - img.get_height()))
    for d in getattr(STATE, "mission3_detainees", ()) or ():
        if d.get("dead") or d.get("line_timer", 0) <= 0 or not d.get("line"):
            continue
        x, y = _wd._detainee_draw_pos(d)
        pt = v.screen_sim(x, y, 2.0)
        if pt is None or not (-80 < pt[0] < WIDTH + 80 and -80 < pt[1] < HEIGHT + 80):
            continue
        sx, sy = int(pt[0]), int(pt[1])
        alpha = min(220, int(d["line_timer"] * 3))
        txt = font_terminal_small.render(d["line"], True, (190, 204, 184))
        txt.set_alpha(alpha)
        bg = pygame.Surface((txt.get_width() + 16, txt.get_height() + 8), pygame.SRCALPHA)
        pygame.draw.rect(bg, (2, 4, 4, min(162, alpha)), bg.get_rect(), border_radius=5)
        pygame.draw.rect(bg, (90, 104, 88, min(90, alpha)), bg.get_rect(), 1, border_radius=5)
        s.blit(bg, (sx - bg.get_width() // 2, sy - bg.get_height() - 4))
        s.blit(txt, (sx - txt.get_width() // 2, sy - bg.get_height()))
    for ft in STATE.floating_texts:
        if len(ft) >= 6 and ft[5] == "pin":
            continue
        pt = v.screen_sim(ft[0], ft[1], 1.9)
        if pt is None:
            continue
        txt = font_terminal_small.render(ft[2], True, ft[3])
        s.blit(txt, (int(pt[0]) - txt.get_width() // 2, int(pt[1])))
