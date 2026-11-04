"""Mission 4 in 2.5D: the curfew street and the radio station in 3D.

``draw.game_draw`` hands the frame here while ``game.topdown3d`` is on
(``CAMS["MISSION4"]``). The sim, the AI and every collision rect stay 2D;
this module only changes what the world looks like. World-anchored 2D
passes (the street arrow, floating texts) project through ``draw._PROJ``;
the screen passes (rain, scanlines, flash, HUD, dialogue, reticle) are
``draw._draw_screen_passes``.

Two sets share the module, picked by the live map:

- Street: the 40x40 block lattice. ``C`` is split by ``maps.M4_BLOCKS``
  (one box per block, height from its storeys, windows on the faces the
  camera sees), the station block, the map border and filler. Wrecked
  cars ``H``/``h`` and jersey barriers ``B`` are cover; sodium posts line
  the boulevard. The street is wet: puddles and lamp reflections.
- Station: the 36x28 building. Whitewash over a blue-grey dado inside,
  a concrete cordon round the ring, the weak east wall ``W`` (cracked,
  rubble once ``STATE.m4_breached``), interior door lintels, barricade
  sites drawn per frame from ``STATE.m4_barricades``, and the furniture
  of ``world.STATION_PROPS``.

Walls are drawn per frame with the M1 cutaway; floors, paint, cars,
props and lamps are one static batch per map. Any renderer error turns
2.5D off for the run (``td.disable``) and the frame falls back to 2D.
"""
import math

from core.config import HEIGHT, TILE_SIZE, WIDTH, font_terminal_small, screen
from core.state import STATE
from engine.core import now_ms as _now_ms, now_s as _now_s
from game import topdown3d as td
from game.topdown3d import K, to3
from missions.m1 import draw3d as _m1
from missions.m1 import grade3d as _grade
from missions.m4 import draw as _d
from missions.m4 import maps as _maps
from missions.m4 import world as _wd
from missions.m4.maps import M4_BLOCKS, STATION_BLOCK
from missions.m4.meta import (JAMMER_TILE, STATION_DOOR_TILE, TRANSMITTER_TILE,
                              VASILE_CACHE_TILE, STAGE_AFTERMATH, STAGE_ESCORT, STAGE_SIEGE)

CAM = td.CAMS["MISSION4"]
T = TILE_SIZE
S = T * K                          # one tile in metres
AIM_H = _m1.AIM_H
STUB_H = _m1.STUB_H
CUT_CAP = _m1.CUT_CAP
DOOR_H = _m1.DOOR_H
WIN_TOP = 2.0                      # lintel of a window site
VOID = _m1.VOID

ASPHALT = (32, 34, 36)
WET = (22, 25, 30)
SIDEWALK = (66, 66, 63)
CURB = (96, 95, 90)
LANE = (150, 140, 96)
FOYER = (64, 54, 44)
HALL = (50, 58, 62)                # transmitter hall and the north wings: cool lino
CORRIDOR = (58, 60, 56)
ENTRY = (66, 58, 48)               # entry hall and the south wings: worn parquet tone
THRESH = (74, 72, 66)
HAZARD = (170, 140, 40)

WASH = (80, 82, 78)                # station whitewash above the dado
DADO = (44, 58, 64)                # KRAP blue-grey paint, waist down
DADO_H = 1.2
CAP = (24, 25, 27)
RIM = (104, 106, 102)
RIM_CUT = (58, 60, 62)
CORDON = (70, 68, 63)
GLASS = (14, 16, 21)
LIT = (156, 122, 70)
FRAME = (58, 60, 62)
CHAR = ((26, 22, 20), 0.85)
FIRE = (255, 140, 56)
COLD = (198, 214, 244)
WARM = (255, 196, 130)
PHOSPHOR = (196, 255, 214)
TUBE = (224, 236, 228)
STEEL = (58, 62, 66)
WOOD = (92, 66, 44)
PLANK = (112, 84, 54)

NIGHT_STREET = dict(_m1.NIGHT, ambient=0.30, diffuse=0.42, tint=(0.90, 0.96, 1.06))
NIGHT_STATION = dict(_m1.NIGHT, ambient=0.33, diffuse=0.40, tint=(0.95, 1.02, 0.98))
AMBIENT_STREET = (150, 156, 172)   # the m4street grade: blue-cyan night
AMBIENT_STATION = (156, 166, 160)  # phosphor-green inside the station

WALL_H = {"border": 3.0, "filler": 3.0, "station": 3.4, "cordon": 2.0, "build": 2.9, "weak": 2.9}
_STYLE = {"row": ("brick", (84, 62, 52), (110, 92, 80)),
          "apartment": ("concrete", (76, 78, 80), (104, 106, 106)),
          "palace": ("m7_plaster", (104, 92, 70), (132, 120, 96)),
          "station": ("concrete", (70, 74, 78), (98, 104, 108)),
          "border": ("concrete", (62, 60, 56), (80, 78, 72)),
          "filler": ("concrete", (62, 60, 56), (80, 78, 72))}

# (tile x, tile y, reach px, colour, family, arm (dx, dy)). Posts stand on
# the sidewalks with the arm out over the road; "wire" lamps hang over the
# cross-street junctions; "door" is the warm lamp over the station door.
_STREET_LAMPS = (
    (4.5, 17.25, 170, COLD, "post", (0, 1)), (10.5, 17.25, 170, COLD, "post", (0, 1)),
    (22.5, 17.25, 170, COLD, "post", (0, 1)), (28.5, 17.25, 170, COLD, "post", (0, 1)),
    (7.5, 21.75, 170, COLD, "post", (0, -1)), (13.5, 21.75, 170, COLD, "post", (0, -1)),
    (19.5, 21.75, 170, COLD, "post", (0, -1)), (26.5, 21.75, 170, COLD, "post", (0, -1)),
    (32.5, 21.75, 150, COLD, "post", (0, -1)),
    (10.0, 4.5, 130, (186, 200, 230), "wire", (0, 0)), (22.0, 9.0, 130, (186, 200, 230), "wire", (0, 0)),
    (4.0, 13.5, 120, (186, 200, 230), "wire", (0, 0)), (16.0, 13.5, 120, (186, 200, 230), "wire", (0, 0)),
    (34.0, 9.0, 120, (186, 200, 230), "wire", (0, 0)), (10.0, 24.5, 120, (186, 200, 230), "wire", (0, 0)),
    (28.0, 30.5, 120, (186, 200, 230), "wire", (0, 0)), (16.0, 35.5, 110, (186, 200, 230), "wire", (0, 0)),
    (33.6, 19.5, 190, WARM, "door", (0, 0)),
)
_STATION_LAMPS = (
    (8.5, 7.5, 140, TUBE, "tube", (0, 0)), (14.5, 7.0, 150, PHOSPHOR, "tube", (0, 0)),
    (21.5, 7.0, 150, PHOSPHOR, "tube", (0, 0)), (27.5, 7.5, 140, TUBE, "tube", (0, 0)),
    (12.0, 12.0, 120, TUBE, "tube", (0, 0)), (24.0, 12.0, 120, TUBE, "tube", (0, 0)),
    (8.5, 17.5, 140, TUBE, "tube", (0, 0)), (15.0, 17.5, 150, (230, 224, 204), "tube", (0, 0)),
    (21.0, 17.5, 150, (230, 224, 204), "tube", (0, 0)), (27.5, 17.5, 140, (255, 120, 110), "tube", (0, 0)),
    (5.25, 3.25, 170, COLD, "post", (1, 1)), (30.75, 3.25, 170, COLD, "post", (-1, 1)),
    (5.25, 22.75, 170, COLD, "post", (1, -1)), (30.75, 22.75, 170, COLD, "post", (-1, -1)),
    (11.5, 22.75, 180, COLD, "post", (0, 1)), (24.5, 22.75, 180, COLD, "post", (0, 1)),
    (17.5, 21.6, 160, WARM, "door", (0, 0)),
)
_LAMP_H = {"post": 3.5, "wire": 3.4, "door": 2.6, "tube": 2.55}
_POOL_K = {"post": 0.62, "wire": 0.5, "door": 0.66, "tube": 0.5}
_BURNING_CARS = {"street": ((18, 20),), "station": ((25, 24),)}

_cache = {"walls": None, "meshes": {}, "packed": {}, "night": None, "blocks": None, "tgt": None,
          "doors": None}


# ── frame ──────────────────────────────────────────────────────────────

def game_draw3d(fcx, fcy):
    """Draw one Mission 4 gameplay frame in 2.5D onto ``screen``. False
    when the renderer failed (2.5D is off now; the caller draws 2D)."""
    cam_x, cam_y = int(round(fcx)), int(round(fcy))
    _d._M4_CAM[0], _d._M4_CAM[1] = cam_x, cam_y
    v = td.View(CAM, fcx + WIDTH / 2.0, fcy + HEIGHT / 2.0)
    _tick()
    if not render_world(screen, v):
        return False
    _d._PROJ[0] = v
    try:
        _labels(screen, v)
        _d._draw_m4_floating(screen, cam_x, cam_y)
        _d._draw_m4_street_arrow(screen, cam_x, cam_y)
    finally:
        _d._PROJ[0] = None
    if STATE.muzzle_flash_timer > 0:
        STATE.muzzle_flash_timer -= 1
    _d._draw_screen_passes(cam_x, cam_y, world3d=True)
    return True


def _tick():
    """Blood fades as it does in the 2D floor pass."""
    for decal in STATE.blood_decals[:]:
        decal[2] -= 0.25
        if decal[2] <= 0:
            STATE.blood_decals.remove(decal)


def render_world(surface, v):
    """Draw the live M4 set and cast through view ``v`` onto ``surface``."""
    from cutscenes import m6fx3d as _fx
    from cutscenes import m6world3d as _w
    from engine3d import Light
    r, buf = _w.rend(*CAM.res)
    saved = (r.light, r.fog, r.fog_start, r.fog_end, r.light_cap)
    tm = _now_ms()
    station = _station()
    try:
        r.light = Light(**(NIGHT_STATION if station else NIGHT_STREET))
        r.fog, r.fog_start, r.fog_end = VOID, 32.0, 64.0
        r.light_cap = 8
        v.apply(r)
        buf.fill(VOID)
        r.begin()
        first = _w.static_scene(r, ("m4_td3d", _key(), id(_maps.MISSION4_MAP)))
        ok = False
        try:
            if first:
                _build_set(r)
            ok = True
        finally:
            _w.static_end(r, ok)
        flashes = []
        _draw_walls(r)
        _draw_openings(r)
        _draw_dynamic_set(r, flashes, tm)
        _draw_apc(r, flashes, tm)
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
    _grade.apply(surface, v, _night_lights() + dyn,
                 ambient=AMBIENT_STATION if station else AMBIENT_STREET)
    return True


# ── helpers ────────────────────────────────────────────────────────────

def _grid():
    return _maps.MISSION4_MAP


def _station():
    return _d._m4_is_station(_grid())


def _key():
    return "station" if _station() else "street"


def _dims():
    g = _grid()
    return (len(g[0]) if g else 0), len(g)


def _glyph(col, row):
    g = _grid()
    if 0 <= row < len(g) and 0 <= col < len(g[row]):
        return g[row][col]
    return ""


def _tc(col, row, h=0.0):
    return to3(col * T + T / 2.0, row * T + T / 2.0, h)


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


def _glow(col, size, tm, k=0.8, px=16, **kw):
    from cutscenes import m6fx3d as _fx
    return _fx.glow(col, size, tm, intensity=k, max_px=px, **kw)


def _fx_layer():
    from cutscenes import m6fx3d as _fx
    return _fx.FX_LAYER


def _floor_tex(col, name):
    from engine3d import tex
    return tex(name, like=tuple(max(0, min(255, int(c))) for c in col), tint=True)


def _tile_col(col, row, base):
    k = 1.0 + (_hash(col, row, 9) - 4) * 0.012
    lean = (_hash(col + 3, row + 11, 5) - 2) * 0.006
    return (base[0] * k * (1.0 + lean), base[1] * k, base[2] * k * (1.0 - lean))


def _box_at(r, w, h, d, col, x, y, z, **kw):
    from cutscenes import m6world3d as _w
    from engine3d import box
    _w.add(r, box(w, h, d, col, center=(x, y, z), **kw))


# ── floors ─────────────────────────────────────────────────────────────

_MARKER_FLOOR = {"street": {"E": ".", "M": "d", "P": ".", "V": "d", "H": ".", "h": ".", "B": ".",
                            "R": ".", "a": "d", "X": "F", "S": "F", "G": "F", "J": "F", "T": "F",
                            "N": "F", "O": "F", "L": "F"},
                 "station": {"T": "O", "J": "O", "N": "F", "P": ".", "Z": ".", "H": ".", "h": ".",
                             "B": ".", "E": ".", "M": "."}}


def _floor_at(col, row):
    """(colour, texture name) of the ground tile."""
    ch = _glyph(col, row)
    ch = _MARKER_FLOOR[_key()].get(ch, ch)
    if ch == "d":
        return SIDEWALK, "concrete"
    if ch == "F":
        return (ENTRY if _station() else FOYER), "m7_tile"
    if ch == "O":
        return HALL, "m7_tile"
    if ch == "L":
        return CORRIDOR, "m7_tile"
    if ch in ("D", "b", "w"):
        return THRESH, "concrete"
    if ch == "A":
        return ASPHALT, "pavement"
    if ch == "g":
        return (48, 46, 42), "concrete"
    if _hash(col * 3 + 1, row * 5 + 2, 100) < 9:
        return WET, "pavement"         # rain standing in the ruts
    return ASPHALT, "pavement"


def _build_set(r):
    from cutscenes import m6world3d as _w
    from engine3d import quad_xz
    mw, mh = _dims()
    for row in range(mh):
        for col in range(mw):
            if _glyph(col, row) in ("C", "W"):
                continue
            base, name = _floor_at(col, row)
            _w.add(r, quad_xz(col * S, -(row + 1) * S, (col + 1) * S, -row * S, 0.0,
                              _floor_tex(_tile_col(col, row, base), name), layer=0))
    _paint(r)
    for row in range(mh):
        for col in range(mw):
            ch = _glyph(col, row)
            if ch == "B":
                _barrier(r, col, row)
            elif ch == "H" and _glyph(col - 1, row) != "H":
                _car(r, col, row, True)
            elif ch == "h" and _glyph(col, row - 1) != "h":
                _car(r, col, row, False)
    if _station():
        _station_props(r)
        _hold_marks(r)
    else:
        _mast(r)
    for lamp in _lamps():
        _lamp_fixture(r, lamp)


def _paint(r):
    """Lane dashes, curbs, the APC lane's hazard stripes, room seams."""
    from cutscenes import m6world3d as _w
    from engine3d import quad_xz
    y = 0.006
    mw, mh = _dims()
    for row in range(mh):
        for col in range(mw):
            ch = _glyph(col, row)
            x0, z0 = col * S, -row * S
            if ch == "R":
                _w.add(r, quad_xz(x0 + 0.45, z0 - S / 2.0 - 0.05, x0 + S - 0.45, z0 - S / 2.0 + 0.05, y,
                                  LANE, layer=1))
            if ch == "d":
                for dc, dr, edge in ((0, -1, "n"), (0, 1, "s"), (-1, 0, "w"), (1, 0, "e")):
                    if _MARKER_FLOOR[_key()].get(_glyph(col + dc, row + dr), _glyph(col + dc, row + dr)) != ".":
                        continue
                    t = 0.09
                    if edge == "n":
                        q = (x0, z0 - t, x0 + S, z0)
                    elif edge == "s":
                        q = (x0, z0 - S, x0 + S, z0 - S + t)
                    elif edge == "w":
                        q = (x0, z0 - S, x0 + t, z0)
                    else:
                        q = (x0 + S - t, z0 - S, x0 + S, z0)
                    _w.add(r, quad_xz(*q, y, CURB, layer=1))
                if col % 2 == 0:            # slab joints
                    _w.add(r, quad_xz(x0 - 0.01, z0 - S, x0 + 0.01, z0, 0.004, (50, 50, 48), layer=1))
            if ch == "A":
                for i in range(2):
                    a = x0 + i * S / 2.0
                    _w.add(r, quad_xz(a + 0.05, z0 - S + 0.18, a + 0.4, z0 - 0.18, y, HAZARD, layer=1))
            if ch in ("O", "F", "L") and (col + row) % 2 == 0 and _station():
                _w.add(r, quad_xz(x0, z0 - 0.012, x0 + S, z0 + 0.012, 0.004, _shade(_floor_at(col, row)[0], 0.7),
                                  layer=1))


def _barrier(r, col, row):
    """Jersey barrier on the 2D collision rect (x+4, y+12, 56, 40)."""
    from engine3d import tex
    x, _, z = _tc(col, row)
    shade = 62 + _hash(col, row, 30)
    body = tex("concrete", like=(shade, shade, shade - 4))
    _box_at(r, 56 * K, 0.3, 40 * K, body, x, 0.15, z)
    _box_at(r, 56 * K, 0.5, 40 * K * 0.55, body, x, 0.55, z, cols={"top": (98, 96, 88)})
    _box_at(r, 0.5, 0.06, 0.02, (200, 60, 50), x, 0.6, z - 40 * K * 0.28 - 0.01)


CAR_LEN = 2.97                     # car_m2 nose to tail at its import scale
_CAR_PAINT = ((70, 76, 86), (96, 70, 52), (62, 80, 66), (110, 104, 92), (80, 40, 38))


def _car_mesh(pal, burned):
    """car_m2 repainted to ``_CAR_PAINT[pal]``, ``burned`` 0..1 toward a
    charred shell (ported from missions.m2.draw3d._car_mesh)."""
    key = ("car", pal, round(burned, 1))
    m = _cache["meshes"].get(key)
    if m is not None:
        return m
    from engine3d import Mesh
    body = _CAR_PAINT[pal]
    try:
        from game.render3d_bridge import load_mesh_asset
        verts, faces = load_mesh_asset("car_m2")
    except (OSError, ValueError):
        m = _cache["meshes"][key] = _m1._sedan(body)
        return m
    paint = [sum(f[1]) for f in faces if f[2] == 3]
    base = (sum(paint) / float(len(paint))) if paint else 1.0
    m = Mesh()
    m.verts = [tuple(v) for v in verts]
    for idx, col, grp in faces:
        col = tuple(col)
        if grp == 3:
            col = _shade(body, sum(col) / base)
        if burned:
            col = td.mix(col, CHAR[0], CHAR[1] * burned)
        m.faces.append((tuple(idx), col, 2, True, False))
    _cache["meshes"][key] = m
    return m


def _car(r, col, row, along_x):
    """A wrecked car over its two tiles: stripped, glass out, most burned."""
    from cutscenes import m6world3d as _w
    from engine3d import Mesh
    if along_x:
        x, _, z = to3((col + 1) * T, row * T + T / 2.0)
        yaw = 0.0 if _hash(col, row, 2) else 180.0
    else:
        x, _, z = to3(col * T + T / 2.0, (row + 1) * T)
        yaw = 90.0 if _hash(col, row, 2) else 270.0
    pal = _hash(col, row, len(_CAR_PAINT))
    burned = 1.0 if _hash(col + 7, row, 3) else 0.6
    from engine3d import quad_xz, rot_y
    src = _car_mesh(pal, burned)
    k = 2 * S * 0.94 / CAR_LEN          # two tiles long, a touch short of the rect
    scaled = Mesh([(a * k, b * k, c * k) for a, b, c in src.verts], src.faces)
    _w.add(r, Mesh().add(scaled, m=rot_y(yaw), t=(x, 0.0, z)))
    hx, hz = (1.5, 0.9) if along_x else (0.9, 1.5)
    _w.add(r, quad_xz(x - hx, z - hz, x + hx, z + hz, 0.004, (22, 20, 19), layer=1))


def _mast(r):
    """The radio mast on the station block's roof: the street's landmark."""
    bx, by, bw, bh = STATION_BLOCK
    x, _, z = to3((bx + bw / 2.0) * T, (by + 2) * T)
    base = WALL_H["station"]
    h = 6.5
    for dx, dz in ((-0.3, -0.3), (0.3, -0.3), (-0.3, 0.3), (0.3, 0.3)):
        _box_at(r, 0.05, h, 0.05, (60, 62, 66), x + dx * (1 - 0.0), base + h / 2.0, z + dz)
    for i in range(1, 9):
        y = base + i * h / 9.0
        k = 1.0 - i * 0.06
        _box_at(r, 0.62 * k, 0.03, 0.03, (70, 72, 76), x, y, z - 0.3)
        _box_at(r, 0.03, 0.03, 0.62 * k, (70, 72, 76), x - 0.3, y, z)
    _box_at(r, 0.9, 0.5, 0.06, (40, 42, 46), x, base + h - 1.2, z - 0.32)


def _hold_marks(r):
    """The hold zone round the transmitter: a painted arc on the hall floor."""
    from cutscenes import m6world3d as _w
    from engine3d import quad_xz
    x, _, z = _tc(*TRANSMITTER_TILE)
    rad = 2.6
    for i in range(24):
        if i % 2:
            continue
        a0, a1 = math.pi * 2 * i / 24.0, math.pi * 2 * (i + 1) / 24.0
        cx, cz = x + math.cos((a0 + a1) / 2) * rad, z + math.sin((a0 + a1) / 2) * rad
        _w.add(r, quad_xz(cx - 0.12, cz - 0.12, cx + 0.12, cz + 0.12, 0.007, (120, 104, 40), layer=1))


# ── station furniture ──────────────────────────────────────────────────

_BOOKS = ((112, 44, 38), (52, 70, 96), (126, 104, 60), (60, 84, 58), (138, 126, 104), (84, 52, 70))


def _station_props(r):
    for c, row, tw, th, inset in _wd.STATION_PROPS:
        x0, y0 = c * T + inset, row * T + inset
        w, d = (tw * T - 2 * inset) * K, (th * T - 2 * inset) * K
        x, _, z = to3(x0 + (tw * T - 2 * inset) / 2.0, y0 + (th * T - 2 * inset) / 2.0)
        kind = _prop_kind(c, row)
        _prop(r, kind, x, z, w, d)


def _prop_kind(c, row):
    return {(15, 5): "rack", (12, 7): "console", (23, 7): "console", (14, 19): "counter",
            (20, 19): "counter", (9, 5): "shelf", (26, 6): "bench", (8, 18): "desk",
            (27, 19): "studio"}.get((c, row), "desk")


def _prop(r, kind, x, z, w, d):
    from engine3d import tex
    if kind == "rack":
        n = 7
        cw = w / n
        for i in range(n):
            cx = x - w / 2.0 + (i + 0.5) * cw
            _box_at(r, cw - 0.04, 2.1, d, tex("steel", like=(42, 46, 50)), cx, 1.05, z,
                    cols={"top": (30, 32, 36)})
            _box_at(r, cw - 0.2, 1.6, 0.02, (28, 30, 34), cx, 1.1, z - d / 2.0 - 0.01)
            for k in range(6):
                led = ((80, 230, 120), (230, 180, 60), (80, 230, 120))[_hash(i, k, 3)]
                _box_at(r, 0.05, 0.03, 0.02, led, cx - 0.2 + (k % 3) * 0.2, 1.6 - (k // 3) * 0.5, z - d / 2.0 - 0.025,
                        emissive=True)
            for k in range(4):
                _box_at(r, cw - 0.3, 0.02, 0.022, (60, 64, 70), cx, 0.5 + k * 0.12, z - d / 2.0 - 0.02)
        _box_at(r, w, 0.1, 0.1, (34, 36, 40), x, 2.2, z - d / 2.0 + 0.05)
    elif kind == "console":
        _box_at(r, w, 0.82, d, tex("steel", like=(54, 58, 62)), x, 0.41, z, cols={"top": (40, 44, 48)})
        along_x = w >= d
        n = max(1, int((w if along_x else d) / 0.55))
        for i in range(n):
            a = -((w if along_x else d) / 2.0) + (i + 0.5) * (w if along_x else d) / n
            mx, mz = (x + a, z) if along_x else (x, z + a)
            _box_at(r, 0.42, 0.34, 0.3, (30, 32, 34), mx, 1.0, mz)
            _box_at(r, 0.34 if along_x else 0.02, 0.26, 0.02 if along_x else 0.34, (110, 220, 150),
                    mx if along_x else mx - 0.16, 1.0, mz - 0.16 if along_x else mz, emissive=True)
        for i in range(5):
            _box_at(r, 0.06, 0.03, 0.06, (200, 190, 120), x - w / 2.0 + 0.2 + i * 0.12, 0.84, z - d / 2.0 + 0.08,
                    emissive=True)
    elif kind == "counter":
        _box_at(r, w, 1.05, d, tex("crate", like=WOOD), x, 0.525, z, cols={"top": (70, 52, 36)})
        _box_at(r, w + 0.08, 0.05, d + 0.08, (120, 96, 64), x, 1.08, z)
        _box_at(r, 0.3, 0.22, 0.22, (40, 42, 44), x + w * 0.25, 1.21, z)
    elif kind == "shelf":
        _box_at(r, w, 2.1, d, tex("crate", like=(66, 48, 32)), x, 1.05, z, cols={"top": (40, 30, 22)})
        n = max(1, int(d / 0.3))
        for k, y in enumerate((0.15, 0.65, 1.15, 1.65)):
            for i in range(n):
                col = _BOOKS[_hash(i, k, len(_BOOKS))]
                hb = 0.3 + 0.06 * _hash(i + 5, k, 3)
                a = -d / 2.0 + (i + 0.5) * d / n
                for side in (-1.0, 1.0):
                    _box_at(r, 0.02, hb, d / n - 0.03, col, x + side * (w / 2.0 + 0.01), y + hb / 2.0, z + a)
    elif kind == "bench":
        _box_at(r, w, 0.9, d, tex("steel", like=(64, 66, 62)), x, 0.45, z, cols={"top": (86, 80, 66)})
        _box_at(r, 0.4, 0.3, 0.32, (34, 36, 38), x, 1.05, z - 0.3)
        _box_at(r, 0.3, 0.2, 0.02, (90, 230, 160), x - 0.05, 1.05, z - 0.3 - 0.17, emissive=True)
        _box_at(r, 0.2, 0.14, 0.4, (130, 60, 40), x, 0.97, z + 0.35)
    elif kind == "desk":
        _m1._desk(r, *_sim_of(x, z))
    elif kind == "studio":
        _box_at(r, w, 0.76, d, tex("crate", like=(60, 46, 34)), x, 0.38, z, cols={"top": (46, 36, 28)})
        for i in (-1, 1):
            _box_at(r, 0.04, 0.32, 0.04, (30, 30, 32), x + i * 0.4, 0.95, z)
            _box_at(r, 0.1, 0.16, 0.1, (60, 62, 64), x + i * 0.4, 1.15, z)
        _box_at(r, 0.6, 0.06, 0.4, (36, 38, 40), x, 0.79, z + 0.1)


def _sim_of(x, z):
    return x / K, -z / K


# ── walls ──────────────────────────────────────────────────────────────

def _block_of(col, row):
    hit = _cache["blocks"]
    if hit is None:
        lut = {}
        for bid, bx, by, bw, bh, style, storeys in M4_BLOCKS:
            for yy in range(by, by + bh):
                for xx in range(bx, bx + bw):
                    lut[(xx, yy)] = (bid, bx, by, bw, bh, style, storeys)
        hit = _cache["blocks"] = lut
    return hit.get((col, row))


def _wall_kind(col, row):
    ch = _glyph(col, row)
    mw, mh = _dims()
    if ch == "W":
        return "weak"
    if ch != "C":
        return None
    border = row in (0, mh - 1) or col in (0, mw - 1)
    if _station():
        return "cordon" if border else "build"
    if border:
        return "border"
    bx, by, bw, bh = STATION_BLOCK
    if bx <= col < bx + bw + 1 and by <= row < by + bh:
        return "station"
    blk = _block_of(col, row)
    return ("b:" + blk[0]) if blk else "filler"


def _height(kind):
    if kind.startswith("b:"):
        blk = next(b for b in M4_BLOCKS if b[0] == kind[2:])
        return 2.6 + 0.3 * blk[6]
    return WALL_H[kind]


def _wall_boxes():
    """Merged wall boxes (col, row, w, h, kind) in tiles: horizontal runs,
    then identical runs stacked down. Cached per map."""
    key = id(_grid())
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


def _street_wall_mesh(kind, sc, sr, sw, sh, hgt):
    """A street wall segment: textured body, the M1 shade bands, a cornice,
    and (at full height) the windows on the faces the camera sees."""
    full = _height(kind)
    cut = hgt < full - 0.01
    key = ("sw", kind, sc, sr, sw, sh, round(hgt, 3)) if not cut else ("swc", kind, sw, sh, round(hgt, 3))

    def build():
        from engine3d import Mesh, box, tex
        style = "border" if kind == "border" else "filler" if kind == "filler" else "station" \
            if kind == "station" else _block_of(sc, sr)[5]
        name, body, cap = _STYLE[style]
        w, d = sw * S, sh * S
        m = Mesh()
        m.add(box(w, hgt, d, tex(name, like=body), center=(0.0, hgt / 2.0, 0.0),
                  cols={"top": CUT_CAP if cut else _shade(body, 0.5)}))
        for y0, y1, k in _m1.WALL_SHADE:
            y1 = min(y1, hgt - 0.02)
            if y1 > y0:
                m.add(box(w + 0.02, y1 - y0, d + 0.02, tex(name, like=_shade(body, k)),
                          center=(0.0, (y0 + y1) / 2.0, 0.0), skip=("top", "bottom")))
        if cut:
            return m
        m.add(box(w + 0.08, 0.16, d + 0.08, _shade(cap, 0.8), center=(0.0, hgt - 0.08, 0.0)))
        if kind.startswith("b:") or kind == "station":
            _windows(m, kind, sc, sr, sw, sh, hgt)
        return m
    return _mesh(key, build)


def _windows(m, kind, sc, sr, sw, sh, hgt):
    """Windows on the south face of a block and on its east/west faces:
    dark glass mostly, a few lit behind curtains, some boarded, some
    blown out. Storefront shutters on the ground floor over a sidewalk."""
    from engine3d import box
    blk = _block_of(sc, sr) if kind.startswith("b:") else None
    bx, by, bw, bh = (blk[1], blk[2], blk[3], blk[4]) if blk else STATION_BLOCK
    if kind == "station":
        bw += 1
    w, d = sw * S, sh * S
    rows = [y for y in (1.15, 2.05, 2.95, 3.85) if y + 0.5 < hgt - 0.2]
    faces = []
    if sr + sh == by + bh:
        faces += [("s", c) for c in range(sc, sc + sw)]
    if sc == bx:
        faces += [("w", rr) for rr in range(sr, sr + sh)]
    if sc + sw == bx + bw:
        faces += [("e", rr) for rr in range(sr, sr + sh)]
    for face, i in faces:
        if face == "s":
            ax, az, along = (i + 0.5 - sc) * S - w / 2.0, -d / 2.0 - 0.025, True
            below = _glyph(i, sr + sh)
        else:
            ax = (-w / 2.0 - 0.025) if face == "w" else (w / 2.0 + 0.025)
            az, along = -((i + 0.5 - sr) * S - d / 2.0), False
            below = _glyph(sc - 1 if face == "w" else sc + sw, i)
        for k, y in enumerate(rows):
            pick = _hash(i * 7 + (0 if face == "s" else 31), k * 13 + sr + sc, 100)
            if k == 0 and below == "d" and kind != "station":
                col = (60, 58, 54) if pick > 8 else (150, 112, 64)
                sz = (1.3, 0.95) if along else (1.3, 0.95)
                if along:
                    m.add(box(sz[0], sz[1], 0.04, col, center=(ax, 0.6, az), emissive=pick <= 8))
                    for j in range(5):
                        m.add(box(sz[0], 0.02, 0.05, (40, 38, 36), center=(ax, 0.2 + j * 0.18, az)))
                else:
                    m.add(box(0.04, sz[1], sz[0], col, center=(ax, 0.6, az), emissive=pick <= 8))
                continue
            lit = pick < 12
            boarded = 12 <= pick < 26
            broken = 26 <= pick < 36
            col = LIT if lit else (6, 7, 9) if broken else GLASS
            gw, gh = 0.62, 0.56
            if along:
                m.add(box(gw, gh, 0.04, col, center=(ax, y, az), emissive=lit))
                m.add(box(gw + 0.12, 0.06, 0.07, FRAME, center=(ax, y - gh / 2.0 - 0.03, az)))
                if boarded:
                    for j in (-1, 1):
                        m.add(box(gw + 0.05, 0.08, 0.06, PLANK, center=(ax, y + j * 0.14, az - 0.01)))
            else:
                m.add(box(0.04, gh, gw, col, center=(ax, y, az), emissive=lit))
                m.add(box(0.07, 0.06, gw + 0.12, FRAME, center=(ax, y - gh / 2.0 - 0.03, az)))
                if boarded:
                    for j in (-1, 1):
                        m.add(box(0.06, 0.08, gw + 0.05, PLANK, center=(ax, y + j * 0.14, az)))


def _station_wall_mesh(kind, w, d, hgt):
    """Station walls: whitewash over a dado, a grime foot, a flat dark top;
    the cordon is bare concrete; the weak wall is cracked and patched."""
    key = ("stw", kind, round(w, 3), round(d, 3), round(hgt, 3))

    def build():
        from engine3d import Mesh, box, tex
        cut = hgt < WALL_H[kind] - 0.01
        m = Mesh()
        if kind == "cordon":
            m.add(box(w, hgt, d, tex("concrete", like=CORDON), center=(0.0, hgt / 2.0, 0.0),
                      cols={"top": CUT_CAP if cut else (92, 90, 84)}))
            m.add(box(w + 0.03, 0.2, d + 0.03, _shade(CORDON, 0.6), center=(0.0, 0.1, 0.0), skip=("top", "bottom")))
            return m
        body = WASH if kind == "build" else _shade(WASH, 0.86)
        m.add(box(w, hgt, d, tex("m7_plaster", like=body, tint=True), center=(0.0, hgt / 2.0, 0.0),
                  cols={"top": CUT_CAP if cut else CAP}))
        for y0, y1, col in ((0.0, DADO_H, DADO), (0.0, 0.2, _shade(DADO, 0.6))):
            y1 = min(y1, hgt - 0.02)
            if y1 > y0:
                m.add(box(w + (0.02 if y1 > 0.3 else 0.03), y1 - y0, d + (0.02 if y1 > 0.3 else 0.03),
                          tex("concrete", like=col, tint=True), center=(0.0, (y0 + y1) / 2.0, 0.0),
                          skip=("top", "bottom")))
        if hgt > DADO_H + 0.1:
            m.add(box(w + 0.025, 0.05, d + 0.025, _shade(DADO, 0.7), center=(0.0, DADO_H, 0.0),
                      skip=("top", "bottom")))
        if kind == "weak":
            crack = (30, 30, 30)
            for y, ang in ((0.7, 0.35), (1.5, -0.5), (2.2, 0.2)):
                if y < hgt - 0.1:
                    m.add(box(w + 0.03, 0.03, d * 0.7, crack, center=(0.0, y, ang * d * 0.3)))
                    m.add(box(w + 0.03, 0.22, 0.03, crack, center=(0.0, y + 0.1, ang * d * 0.5)))
            m.add(box(w + 0.035, 0.6, d * 0.4, (62, 66, 60), center=(0.0, 1.0, -d * 0.18), skip=("top", "bottom")))
        return m
    return _mesh(key, build)


def _solid(col, row):
    return _glyph(col, row) in ("C", "W", "") or (_glyph(col, row) == "D" and False)


def _rim_mesh(sc, sr, sw, sh, hgt, full):
    """The lit lip round a wall top on the edges that face open floor
    (ported from missions.m3.draw3d._rim_mesh)."""
    def build():
        from engine3d import Mesh, box
        m = Mesh()
        col = RIM_CUT if hgt < full - 0.01 else RIM
        y, t, tk = hgt + 0.012, 0.07, 0.024
        cx, cz = (sc + sw / 2.0) * S, -(sr + sh / 2.0) * S

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
                    zz = -(sr if edge == "n" else sr + sh) * S + (-t / 2.0 if edge == "n" else t / 2.0)
                    m.add(box((b - a) * S, tk, t, col, center=((a + b) / 2.0 * S - cx, y, zz - cz)))
                else:
                    xx = (sc if edge == "w" else sc + sw) * S + (t / 2.0 if edge == "w" else -t / 2.0)
                    m.add(box(t, tk, (b - a) * S, col, center=(xx - cx, y, -(a + b) / 2.0 * S - cz)))
                i = j + 1
        run([(c, not _solid(c, sr - 1)) for c in range(sc, sc + sw)], "n")
        run([(c, not _solid(c, sr + sh)) for c in range(sc, sc + sw)], "s")
        run([(rw, not _solid(sc - 1, rw)) for rw in range(sr, sr + sh)], "w")
        run([(rw, not _solid(sc + sw, rw)) for rw in range(sr, sr + sh)], "e")
        return m
    return _mesh(("rim", id(_grid()), sc, sr, sw, sh, round(hgt, 3)), build)


def _cut(zone, snap, c, row):
    k = _m1._cut_level(("m4", c, row), _m1._hides(zone, c * T, row * T, (c + 1) * T, (row + 1) * T), snap)
    return round(k * 8) / 8.0


def _draw_walls(r):
    """Wall boxes at full height, except the stretch between the camera
    and Biribel, which sinks to a stub (the M1 cutaway)."""
    zone = _m1._cut_zone()
    snap = _m1._cut_snap()
    station = _station()
    breached = bool(getattr(STATE, "m4_breached", False))
    for c0, r0, w, h, kind in _wall_boxes():
        if kind == "weak" and breached:
            _rubble(r, c0, r0, w, h)
            continue
        along_x = w >= h
        n = w if along_x else h
        levels = [min(_cut(zone, snap, c0 + i, r0 + j) for j in range(h)) if along_x else
                  min(_cut(zone, snap, c0 + j, r0 + i) for j in range(w)) for i in range(n)]
        full = _height(kind)
        i = 0
        while i < n:
            j = i
            while j + 1 < n and levels[j + 1] == levels[i]:
                j += 1
            if along_x:
                sc, sr, sw, sh = c0 + i, r0, j - i + 1, h
            else:
                sc, sr, sw, sh = c0, r0 + i, w, j - i + 1
            hgt = STUB_H + (full - STUB_H) * levels[i]
            cx, _, cz = to3((sc + sw / 2.0) * T, (sr + sh / 2.0) * T)
            if station:
                _put(r, _station_wall_mesh(kind, sw * S, sh * S, hgt), (cx, 0.0, cz))
                if kind != "cordon":
                    _put(r, _rim_mesh(sc, sr, sw, sh, hgt, full), (cx, 0.0, cz))
            else:
                _put(r, _street_wall_mesh(kind, sc, sr, sw, sh, hgt), (cx, 0.0, cz))
            i = j + 1


def _rubble(r, c0, r0, w, h):
    """The blown weak wall: broken stubs, a spill of blocks, scorch."""
    from engine3d import box, tex
    for row in range(r0, r0 + h):
        for col in range(c0, c0 + w):
            x, _, z = _tc(col, row)
            for i in range(5):
                a = _hash(col * 5 + i, row, 360) * math.pi / 180.0
                d = 0.15 + 0.12 * _hash(i, row + col, 5)
                s = 0.18 + 0.05 * _hash(i + 2, row, 4)
                col3 = (WASH, DADO, (60, 60, 58))[i % 3]
                _put(r, _mesh(("rub", round(s, 2), col3), lambda s=s, c=col3: box(s, s * 0.6, s, tex("concrete", like=c))),
                     (x + math.cos(a) * d - 0.3, s * 0.3, z + math.sin(a) * d), yaw=float(_hash(i, col, 90)))
            r.add_sprite((x - 0.5, 0.02, z), td.blood_pool(0.9, (18, 16, 14)), layer=0)
    for row in (r0 - 1, r0 + h):
        x, _, z = _tc(c0, row)
        _put(r, _mesh(("stub",), lambda: box(S, 0.5, S * 0.4, tex("m7_plaster", like=WASH, tint=True))),
             (x, 0.0, z + (S * 0.3 if row < r0 else -S * 0.3)))


# ── openings: doors and barricade sites ───────────────────────────────

def _openings():
    key = id(_grid())
    hit = _cache["doors"]
    if hit is not None and hit[0] == key:
        return hit[1]
    out = []
    mw, mh = _dims()
    walls = ("C", "W", "b", "w")
    for row in range(mh):
        for col in range(mw):
            ch = _glyph(col, row)
            if ch not in ("D", "b", "w"):
                continue
            along_x = _glyph(col - 1, row) in walls + ("D",) or _glyph(col + 1, row) in walls + ("D",)
            if _glyph(col, row - 1) in walls and _glyph(col, row + 1) in walls:
                along_x = False
            out.append((col, row, ch, along_x))
    _cache["doors"] = (key, out)
    return out


def _wall_kind_near(col, row):
    for dc, dr in ((-1, 0), (1, 0), (0, -1), (0, 1)):
        k = _wall_kind(col + dc, row + dr)
        if k is not None and k != "weak":
            return k
    return "build" if _station() else "station"


def _draw_openings(r):
    """Lintels over every door and site, frames, and the barricade a site
    carries (``STATE.m4_barricades[(col, row)]``)."""
    from engine3d import box, tex
    zone = _m1._cut_zone()
    snap = _m1._cut_snap()
    bars = getattr(STATE, "m4_barricades", None) or {}
    station = _station()
    for col, row, ch, along_x in _openings():
        kind = _wall_kind_near(col, row)
        full = _height(kind)
        level = _cut(zone, snap, col, row)
        hgt = STUB_H + (full - STUB_H) * level
        x, _, z = _tc(col, row)
        top = WIN_TOP if ch == "w" else DOOR_H
        body = WASH if station else _STYLE["station"][1]
        if hgt > top + 0.05:
            key = ("lintel", round(hgt, 3), round(top, 2), body, hgt >= full - 0.01)
            _put(r, _mesh(key, lambda h=hgt, t=top, c=body, f=hgt >= full - 0.01:
                          box(S, h - t, S, tex("m7_plaster", like=c, tint=True), center=(0.0, (h + t) / 2.0, 0.0),
                              cols={"top": CAP if f else CUT_CAP})), (x, 0.0, z))
            if station:
                _put(r, _rim_mesh(col, row, 1, 1, hgt, full), (x, 0.0, z))
        if ch == "D":
            continue
        yaw = 0.0 if along_x else 90.0
        _put(r, _mesh(("frame", ch, round(min(top, hgt), 2)), lambda c=ch, h=min(top, hgt): _frame_mesh(c, h)),
             (x, 0.0, z), yaw=yaw)
        bar = bars.get((col, row))
        if bar and bar.get("kind") and bar.get("hp", 0) > 0:
            frac = max(0.0, min(1.0, bar["hp"] / float(max(1, bar.get("max", 1)))))
            _put(r, _barricade_mesh(bar["kind"], frac, round(min(top, hgt), 2)), (x, 0.0, z), yaw=yaw)
        elif bar and bar.get("kind"):
            _put(r, _mesh(("wreck", bar["kind"]), lambda k=bar["kind"]: _wreck_mesh(k)), (x, 0.0, z), yaw=yaw)


def _frame_mesh(ch, h):
    """Jambs either side of a site; a window keeps broken glass teeth."""
    from engine3d import Mesh, box
    m = Mesh()
    for side in (-1, 1):
        m.add(box(0.1, h, 0.22, FRAME, center=(side * (S / 2.0 - 0.05), h / 2.0, 0.0)))
    if ch == "w":
        for i in range(4):
            m.add(box(0.12, 0.16 + 0.05 * (i % 2), 0.02, (90, 120, 130),
                      center=(-S / 2.0 + 0.2 + i * 0.38, h - 0.12, 0.0), emissive=False))
    return m


def _barricade_mesh(kind, frac, h):
    """Planks nailed across a door, a welded plate, boards over a window.
    Damage drops planks and scorches the plate."""
    steps = 6 if kind == "plate" else 4
    k = max(1, int(math.ceil(frac * steps)))
    key = ("bar", kind, k, h)

    def build():
        from engine3d import Mesh, box, tex
        m = Mesh()
        span = S - 0.1
        if kind == "plate":
            col = td.mix((92, 96, 100), (40, 30, 24), 1.0 - k / float(steps))
            m.add(box(span, min(h, 2.2), 0.08, tex("steel", like=col), center=(0.0, min(h, 2.2) / 2.0, 0.0)))
            for yy in (0.25, min(h, 2.2) - 0.25):
                for xx in (-span / 2.0 + 0.12, span / 2.0 - 0.12):
                    m.add(box(0.06, 0.06, 0.1, (150, 150, 146), center=(xx, yy, 0.0)))
            m.add(box(span + 0.04, 0.05, 0.12, (170, 120, 60), center=(0.0, min(h, 2.2) - 0.02, 0.0)))
            if k < steps:
                for i in range(steps - k):
                    m.add(box(0.18, 0.12, 0.1, (24, 20, 18),
                              center=(-span / 2.0 + 0.3 + 0.27 * i, 0.5 + 0.23 * (i % 3), 0.0)))
            return m
        n = 3 if kind == "planks" else 2
        heights = (0.45, 1.05, 1.65) if kind == "planks" else (0.95, 1.45)
        shown = max(1, int(math.ceil(n * k / float(steps))))
        for i in range(shown):
            tilt = (-0.12, 0.1, -0.06)[i % 3]
            m.add(box(span + 0.18, 0.2, 0.06, tex("m7_plank", like=PLANK),
                      center=(0.0, heights[i], 0.04 * (i % 2)), cols={"top": (130, 100, 66)}))
            m.add(box(0.06, 0.06, 0.08, (170, 170, 160), center=(-span / 2.0, heights[i], 0.0)))
            m.add(box(0.06, 0.06, 0.08, (170, 170, 160), center=(span / 2.0, heights[i] + tilt, 0.0)))
        return m
    return _mesh(key, build)


def _wreck_mesh(kind):
    """A broken barricade: splinters on the floor (or a bent plate)."""
    from engine3d import Mesh, box, tex
    m = Mesh()
    if kind == "plate":
        m.add(box(S - 0.2, 0.06, 1.0, tex("steel", like=(54, 46, 40)), center=(0.0, 0.03, 0.55)))
        return m
    for i in range(4):
        m.add(box(0.6 + 0.1 * (i % 2), 0.05, 0.16, tex("m7_plank", like=_shade(PLANK, 0.7)),
                  center=(-0.4 + i * 0.25, 0.03, 0.3 + 0.18 * (i % 3))))
    return m


# ── dynamic set: objectives, burning wrecks, the cache, the jammer ─────

def _draw_dynamic_set(r, flashes, tm):
    t = _now_s()
    for col, row in _BURNING_CARS[_key()]:
        if _glyph(col, row) not in ("H", "h"):
            continue
        x, _, z = to3((col + 1) * T, row * T + T / 2.0)
        for i in range(3):
            _m1._fire(r, (x - 0.7 + i * 0.7, 0.65, z + 0.05 * i), tm, col * 9 + i, 0.32 + 0.06 * i)
        flick = 0.85 + 0.15 * math.sin(t * 13.0 + col)
        flashes.append({"pos": (x, 1.3, z), "color": FIRE, "intensity": 1.1 * flick, "range": 6.0})
    if _station():
        x, _, z = _tc(*TRANSMITTER_TILE)
        on_air = getattr(STATE, "mission4_stage", "") == STAGE_SIEGE
        col = (120, 255, 170) if on_air else (90, 120, 130)
        for i in range(7):
            cx, _, cz = to3((15 + i) * T + T / 2.0, 5 * T + T / 2.0)
            if (int(t * 6 + i * 3) % 4) or not on_air:
                r.add_sprite((cx, 2.25, cz - 0.4), _glow(col, 0.1, tm, 0.7, 8), layer=_fx_layer())
        jx, _, jz = _tc(*JAMMER_TILE)
        if getattr(STATE, "m4_jammer_installed", False):
            _put(r, _mesh(("jammer",), _jammer_mesh), (jx, 0.0, jz))
            blink = (int(t * 3) % 2) == 0
            r.add_sprite((jx + 0.15, 0.62, jz - 0.2), _glow((255, 70, 60) if blink else (90, 20, 18), 0.12, tm, 0.9, 10),
                         layer=_fx_layer())
            flashes.append({"pos": (jx, 1.0, jz), "color": (180, 220, 255), "intensity": 0.5, "range": 3.0})
        _studio_sign(r, tm, on_air)
    else:
        bx, by, bw, bh = STATION_BLOCK
        mx, _, mz = to3((bx + bw / 2.0) * T, (by + 2) * T)
        if (int(t * 1.4) % 2) == 0:
            r.add_sprite((mx, WALL_H["station"] + 6.6, mz), _glow((255, 50, 40), 0.26, tm, 1.0, 16),
                         layer=_fx_layer())
    _beacons(r, t)


def _beacons(r, t):
    """Pulsing floor rings on the live objective tiles (the 2D bracket pass)."""
    g = _grid()
    stage = getattr(STATE, "mission4_stage", "")
    station = _station()
    rad = 0.55 + 0.08 * math.sin(t * 3.0)
    marks = []
    if not station and stage == STAGE_ESCORT:
        marks.append((STATION_DOOR_TILE, (255, 200, 90)))
    if station:
        for (col, row) in (TRANSMITTER_TILE, JAMMER_TILE):
            if g[row][col] in ("T", "J"):
                if g[row][col] == "J" and getattr(STATE, "m4_jammer_installed", False):
                    continue
                marks.append(((col, row), (170, 210, 250)))
    for (col, row), col3 in marks:
        x, _, z = _tc(col, row)
        td.ring(r, x, z, rad, col3, n=20, width=2)
        td.ring(r, x, z, rad * 0.6, td.mix(col3, (0, 0, 0), 0.4), n=14, width=1)


APC_OLIVE = (66, 74, 54)
APC_DARK = (40, 44, 34)
APC_TYRE = (20, 20, 22)


def _apc_mesh():
    """Wave 5 APC: eight-wheel box hull, sloped glacis, small turret, IPA
    stripe. Built along +z (nose forward) to the apc.HULL footprint."""
    from engine3d import Mesh, box
    from missions.m4 import apc as _apc
    w = _apc.HULL_W * K * 0.92
    ln = _apc.HULL_L * K * 0.96
    m = Mesh()
    m.add(box(w, 0.9, ln, APC_OLIVE, center=(0.0, 0.95, 0.0)))
    m.add(box(w * 0.86, 0.55, ln * 0.62, _shade(APC_OLIVE, 0.9), center=(0.0, 1.66, -ln * 0.08)))
    m.add(box(w * 0.92, 0.36, ln * 0.2, _shade(APC_OLIVE, 1.12), center=(0.0, 1.32, ln * 0.4)))
    m.add(box(w * 0.98, 0.12, ln * 0.98, APC_DARK, center=(0.0, 0.52, 0.0)))
    m.add(box(0.9, 0.4, 0.9, _shade(APC_OLIVE, 0.82), center=(0.0, 2.12, -ln * 0.06)))
    m.add(box(0.12, 0.12, 1.3, APC_DARK, center=(0.0, 2.14, ln * 0.3)))
    for i in range(4):
        z = -ln * 0.36 + i * ln * 0.24
        for sx in (-1, 1):
            m.add(box(0.3, 0.86, 0.86, APC_TYRE, center=(sx * (w / 2.0 - 0.1), 0.43, z)))
    m.add(box(w * 1.0, 0.1, 0.5, (150, 40, 34), center=(0.0, 1.2, -ln * 0.2)))
    for dz in (-0.34, 0.12):                                   # roof hatches
        m.add(box(0.62, 0.08, 0.62, APC_DARK, center=(w * 0.24, 1.97, ln * dz)))
    m.add(box(w * 0.7, 0.06, ln * 0.14, (28, 30, 26), center=(0.0, 1.95, -ln * 0.36)))  # engine grille
    for sx in (-1, 1):                                         # vision slits + side boxes
        m.add(box(0.04, 0.08, ln * 0.4, (16, 18, 16), center=(sx * w * 0.43, 1.62, ln * 0.05)))
        m.add(box(0.2, 0.3, 0.7, _shade(APC_OLIVE, 0.78), center=(sx * (w / 2.0 + 0.06), 1.1, -ln * 0.25)))
    m.add(box(0.5, 0.04, 0.5, (196, 192, 176), center=(-w * 0.24, 1.95, -ln * 0.1)))  # IPA roundel
    for sx in (-1, 1):
        m.add(box(0.2, 0.14, 0.04, (255, 236, 180), center=(sx * w * 0.32, 1.1, ln / 2.0 + 0.01),
                  emissive=True))
        m.add(box(0.14, 0.1, 0.04, (200, 30, 26), center=(sx * w * 0.36, 1.1, -ln / 2.0 - 0.01),
                  emissive=True))
    return m


def _draw_apc(r, flashes, tm):
    apc = getattr(STATE, "m4_apc", None)
    if not apc or not _station():
        return
    x, _, z = to3(apc["x"], apc["y"])
    bob = 0.0 if apc["phase"] == "parked" else 0.03 * math.sin(tm * 0.03)
    _put(r, _mesh(("apc",), _apc_mesh), (x, bob, z), yaw=td.yaw_rad(apc["yaw"]))
    if apc["phase"] in ("parked", "back"):
        return
    fx, fz = math.cos(apc["yaw"]) * K, -math.sin(apc["yaw"]) * K
    from missions.m4 import apc as _apc
    nose = _apc.HULL_L * 0.5
    flashes.append({"pos": (x + fx * nose, 1.1, z + fz * nose), "color": (255, 230, 170),
                    "intensity": 1.3, "range": 9.0})


def _jammer_mesh():
    from engine3d import Mesh, box
    m = Mesh()
    m.add(box(0.6, 0.42, 0.4, (40, 44, 40), center=(0.0, 0.21, 0.0)))
    m.add(box(0.5, 0.06, 0.3, (24, 26, 24), center=(0.0, 0.45, 0.0)))
    for dx in (-0.2, 0.0, 0.2):
        m.add(box(0.02, 0.9, 0.02, (90, 94, 100), center=(dx, 0.9, 0.1)))
    m.add(box(0.3, 0.16, 0.02, (110, 200, 240), center=(-0.1, 0.25, -0.21), emissive=True))
    return m


def _cache_mesh():
    """The KRAP comms cache: olive case, latches, the radio strapped on."""
    from engine3d import Mesh, box
    m = Mesh()
    m.add(box(0.7, 0.36, 0.44, (56, 64, 46), center=(0.0, 0.18, 0.0)))
    m.add(box(0.72, 0.04, 0.46, (40, 47, 34), center=(0.0, 0.2, 0.0)))
    for dx in (-0.18, 0.18):
        m.add(box(0.06, 0.1, 0.02, (146, 128, 74), center=(dx, 0.24, -0.23)))
    m.add(box(0.32, 0.2, 0.26, (34, 36, 40), center=(0.12, 0.46, 0.02)))
    m.add(box(0.02, 0.6, 0.02, (70, 74, 80), center=(0.26, 0.86, 0.1)))
    m.add(box(0.2, 0.06, 0.02, (196, 192, 176), center=(-0.18, 0.3, -0.23)))
    return m


def _studio_sign(r, tm, on_air):
    """ON AIR over the studio door: red when the feed is up."""
    x, _, z = _tc(27, 14)
    col = (255, 60, 50) if on_air else (70, 30, 28)
    _put(r, _mesh(("onair", on_air), lambda: _onair_mesh(col)), (x, 0.0, z + S / 2.0 - 0.02))
    if on_air:
        r.add_sprite((x, 2.45, z + S / 2.0 - 0.1), _glow((255, 70, 60), 0.3, tm, 0.7, 14), layer=_fx_layer())


def _onair_mesh(col):
    from engine3d import Mesh, box
    m = Mesh()
    m.add(box(0.7, 0.24, 0.06, (30, 30, 32), center=(0.0, 2.45, 0.0)))
    m.add(box(0.6, 0.16, 0.02, col, center=(0.0, 2.45, -0.04), emissive=True))
    return m


# ── cast ───────────────────────────────────────────────────────────────

_FOE = {"guard": ("os12", {}),
        "marksman": ("os12", {"jacket": (58, 46, 40), "vest": (40, 36, 32)}),
        "breacher": ("shotgun", {"vest": (46, 48, 44)}),
        "loyalist": ("os12", {"jacket": (74, 66, 50)})}
_ALLY = {"VASILE": ("vasile", "os12", {}),
         "MARU": ("maru", "pistol", {})}
SOLDIER = dict(jacket=(66, 72, 54), pants=(52, 56, 44), vest=(46, 50, 40), armband=(70, 150, 90))
CIVILIAN = dict(jacket=(74, 70, 64), pants=(46, 46, 50), long_coat=None, vest=None, pouches=False,
                lapel=None, shirt=None, armband=(70, 150, 90))


def _ally_hum(name, rec):
    look = (rec or {}).get("look")
    rig = (rec or {}).get("combat") or "os12"
    rig = {"rifle": "os12", "smg": "k9_smg", "pistol": "pistol", "shotgun": "shotgun"}.get(rig, rig)
    if look == "soldier":
        return td.armed("ipa", rig, **SOLDIER), rig
    if look == "civilian":
        tint = (rec or {}).get("coat") or CIVILIAN["jacket"]
        return td.armed("civilian", "pistol", **dict(CIVILIAN, jacket=tint)), "pistol"
    who, rig0, spec = _ALLY.get(name, ("krap", "os12", {}))
    if (rec or {}).get("weapon") == "folder":
        rig0 = "pistol"
    return td.armed(who, rig0, **spec), rig0


def _draw_allies(r, flashes):
    from engine3d import POSES
    live = {a["name"]: a for a in getattr(STATE, "m4_allies", []) or []}
    for row in _wd.friendly_npcs():
        name, (x, y), _col, facing = row[0], row[1], row[2], row[3]
        rec = live.get(name)
        hum, rig = _ally_hum(name, rec)
        if rec and (rec.get("downed", 0) > 0 or rec.get("dead")):
            at = to3(x, y)
            r.add_sprite((at[0], 0.02, at[2]), td.blood_pool(0.7), layer=0)
            r.add_humanoid(hum, dict(POSES["dead_back"]), at, td.yaw_rad(facing), rifle_on=False)
            continue
        armed = not rec or rec.get("armed", True)
        mode = "aim" if rec and rec.get("cooldown", 0) > 0 else "ready"
        _m1._feet(r, x, y, (110, 170, 230), rad=0.4)
        flash = bool(rec and rec.get("muzzle", 0) > 0)
        _m1._body(r, hum, x, y, facing, rig, mode if armed else "ready", ("ally", name), flashes, flash,
                  tint=((255, 255, 255), 0.35) if rec and rec.get("hit_flash", 0) > 0 else None)
        if name == "VASILE" and getattr(STATE, "m4_cache_carried", False):
            bx, _, bz = to3(x - math.cos(facing) * 12.0, y - math.sin(facing) * 12.0)
            _put(r, _mesh(("cache",), _cache_mesh), (bx, 0.95, bz), yaw=td.yaw_of(math.degrees(facing)), scale=0.7)


def _draw_cast(r, flashes, tm):
    _m1._draw_corpses(r, flashes, tm)
    for e in STATE.enemies:
        if getattr(e, "hp", 1) <= 0:
            continue
        kind = getattr(_wd._m4l(e), "kind", None) or "guard"
        rig, spec = _FOE.get(kind, _FOE["guard"])
        hum = td.armed("ipa", rig, **dict({"jacket": _m1.IPA}, **spec))
        mode = "aim" if e.state in ("CHASE", "ATTACK") else "ready"
        burn = getattr(e, "burn", 0)
        tint = _m1.CHAR if burn else (e.body_tint, 0.55) if getattr(e, "body_tint", None) else None
        x, y = e.rect.centerx, e.rect.centery
        _m1._feet(r, x, y, _m1.RING_FOE.get(e.state, _m1.RING_FOE_CALM))
        _m1._body(r, hum, x, y, e.angle, rig, mode, ("e", e.uid), tint=tint)
        _m1._burning(r, x, y, min(1.0, burn / 40.0), tm, e.uid * 5, flashes)
    _draw_allies(r, flashes)
    p = STATE.player
    if p is None:
        return
    if STATE.player_dead:
        _m1._draw_dead_player(r)
        return
    hum, rig = _m1.player_hum()
    melee = _m1._melee_progress()
    mode = "ready" if STATE.is_reloading else "aim"
    _m1._feet(r, p.rect.centerx, p.rect.centery, _m1.RING_YOU, rad=0.46)
    _m1._body(r, hum, p.rect.centerx, p.rect.centery, p.angle, rig, mode, "player", flashes,
              STATE.muzzle_flash_timer > 0 and melee is None, melee=melee)


# ── fx ─────────────────────────────────────────────────────────────────

def _draw_fx(r, flashes, tm):
    from core.config import C_BULLET
    t = _now_s()
    for pu in STATE.pickups:
        x, _, z = to3(pu[0], pu[1])
        bob = 0.06 * math.sin(t * 3 + pu[0])
        kind = "bandage" if (pu[2] if len(pu) > 2 else "bandage") == "bandage" else "mag"
        _put(r, _mesh(("pickup", kind), lambda k=kind: _m1._pickup_mesh(k)), (x, 0.25 + bob, z),
             yaw=(t * 60.0 + pu[0]) % 360.0)
        r.add_sprite((x, 0.3, z), _glow(_m1._PICKUP_COL.get(kind, (255, 210, 40)), 0.28, tm, 0.7, 16),
                     layer=_fx_layer())
    for decal in STATE.blood_decals:
        k = max(0.0, min(1.0, decal[2] / 255.0))
        if k > 0.05:
            r.add_sprite(to3(decal[0], decal[1], 0.015),
                         td.blood_pool(min(1.0, decal[3] / 24.0) * k, (80, 12, 14)), layer=0)
    fx0, fz0 = _cache.get("tgt") or (0.0, 0.0)
    for fz in getattr(STATE, "fire_zones", []):
        x, _, z = to3(fz.x, fz.y)
        if abs(x - fx0) > 22.0 or abs(z - fz0) > 18.0:
            continue
        heat = min(1.0, fz.life / float(max(1, fz.max_life)) * 4.0)
        rad = fz.radius * K
        r.add_sprite((x, 0.02, z), td.blood_pool(min(1.0, rad / 2.0), (26, 18, 14)), layer=0)
        n = 1 + min(6, int(rad / 0.3))
        for i in range(n):
            a = i * 2.39996 + fz.x * 0.013
            d = 0.0 if i == 0 else rad * 0.8 * math.sqrt(i / float(n))
            size = (0.5 if i == 0 else 0.34) * min(1.2, 0.4 + rad * 0.35) * heat
            _m1._fire(r, (x + math.cos(a) * d, 0.0, z + math.sin(a) * d), tm, int(fz.x) + i, size, glow=i == 0)
        flashes.append({"pos": (x, 1.0, z), "color": FIRE, "intensity": heat, "range": 4.0 + rad})
    for laser in getattr(STATE, "m4_lasers", []) or []:
        a = max(0.0, min(1.0, laser.get("life", 0) / 45.0))
        p0 = to3(laser["from"][0], laser["from"][1], AIM_H + 0.2)
        p1 = to3(laser["to"][0], laser["to"][1], AIM_H)
        r.add_line3d(p0, p1, td.mix((40, 6, 4), (255, 35, 22), a), 2, layer=4)
        r.add_sprite(p1, _glow((255, 45, 30), 0.14, tm, 0.8 * a, 10), layer=_fx_layer())
    for b in STATE.bullets:
        head = to3(b["x"], b["y"], AIM_H)
        tail = to3(b.get("prev_x", b["x"] - b["dx"]), b.get("prev_y", b["y"] - b["dy"]), AIM_H)
        r.add_line3d(tail, head, (255, 220, 140), 2, layer=4)
        r.add_sprite(head, _glow(C_BULLET, 0.12, tm, 0.9, 10), layer=_fx_layer())
    td.dots(r, [(to3(p.x, p.y, 0.25 + 0.03 * getattr(p, "life", 0)), p.color, getattr(p, "size", 2))
                for p in STATE.particles], layer=_fx_layer())
    td.dots(r, [(to3(c.x, c.y, 0.03), (200, 160, 70), 2) for c in STATE.casings], layer=1)


# ── lights ─────────────────────────────────────────────────────────────

def _lamps():
    return _STATION_LAMPS if _station() else _STREET_LAMPS


def _lamp_base(lamp):
    tx, ty = lamp[0], lamp[1]
    return tx * T, ty * T


def _lamp_head(lamp):
    bx, by = _lamp_base(lamp)
    dx, dy = lamp[5]
    n = math.hypot(dx, dy) or 1.0
    arm = 0.9 / K if lamp[4] == "post" else 0.0
    return to3(bx + dx / n * arm, by + dy / n * arm, _LAMP_H[lamp[4]])


def _lamp_fixture(r, lamp):
    from cutscenes import m6world3d as _w
    from engine3d import Mesh, box
    fam, col = lamp[4], lamp[3]
    bx, by = _lamp_base(lamp)
    x, _, z = to3(bx, by)
    hx, hy, hz = _lamp_head(lamp)
    metal = (30, 31, 34)
    if fam == "post":
        h = _LAMP_H["post"]
        _box_at(r, 0.12, h, 0.12, metal, x, h / 2.0, z)
        m = Mesh()
        m.add(box(0.07, 0.07, 0.07, metal, center=(0.0, 0.0, 0.0)))
        steps = 6
        for i in range(1, steps + 1):
            k = i / float(steps)
            _box_at(r, 0.07, 0.07, 0.07, metal, x + (hx - x) * k, h + 0.02, z + (hz - z) * k)
        _box_at(r, 0.36, 0.1, 0.24, metal, hx, hy + 0.02, hz)
        _box_at(r, 0.28, 0.03, 0.18, col, hx, hy - 0.04, hz, emissive=True)
        _box_at(r, 0.22, 0.4, 0.04, (40, 44, 40), x, 1.6, z - 0.07)
    elif fam == "wire":
        _box_at(r, 0.02, 0.8, 0.02, metal, hx, hy + 0.45, hz)
        _box_at(r, 0.34, 0.12, 0.34, metal, hx, hy + 0.04, hz)
        _box_at(r, 0.24, 0.03, 0.24, col, hx, hy - 0.03, hz, emissive=True)
    elif fam == "door":
        _box_at(r, 0.3, 0.1, 0.24, metal, hx, hy + 0.05, hz)
        _box_at(r, 0.22, 0.04, 0.16, col, hx, hy - 0.01, hz, emissive=True)
        if not _station():
            _box_at(r, 0.06, 0.34, 1.6, (36, 52, 64), hx - 0.1, 2.85, hz)
            _box_at(r, 0.02, 0.24, 1.4, (150, 190, 220), hx - 0.14, 2.85, hz, emissive=True)
    elif fam == "tube":
        _box_at(r, 1.1, 0.08, 0.18, metal, hx, hy + 0.04, hz)
        _box_at(r, 0.96, 0.03, 0.1, col, hx, hy - 0.01, hz, emissive=True)
        _w.add(r, box(0.02, 0.4, 0.02, metal, center=(hx - 0.45, hy + 0.25, hz)))
        _w.add(r, box(0.02, 0.4, 0.02, metal, center=(hx + 0.45, hy + 0.25, hz)))


def _lamp_lights(r, v, flashes, tm):
    """Lamp pools light the baked floor; the lamps nearest the camera focus
    plus the flashes are the eight per-frame lights."""
    fx, fz = v.tgt[0], v.tgt[2]
    _cache["tgt"] = (fx, fz)
    pools, near = [], []
    for lamp in _lamps():
        head = _lamp_head(lamp)
        reach = lamp[2] * K * 1.6
        color = lamp[3]
        pools.append({"pos": head, "range": reach, "color": color, "intensity": 2.0,
                      "hot": td.mix(color, (255, 250, 235), 0.5)})
        near.append(((head[0] - fx) ** 2 + (head[2] - fz) ** 2,
                     {"pos": head, "color": color, "intensity": 0.45, "range": reach}))
        if lamp[4] in ("post", "wire", "door"):
            r.add_sprite(head, _glow(color, 0.28, tm, 0.9, 18), layer=_fx_layer())
    p = STATE.player
    if p is not None:
        flashes.append({"pos": to3(p.rect.centerx, p.rect.centery, 1.7), "color": (190, 205, 230),
                        "intensity": 0.8, "range": 3.0})
    near.sort(key=lambda e: e[0])
    lights = [e[1] for e in near[:max(0, 8 - len(flashes))]]
    r.set_pools(pools)
    r.set_lights(flashes[:8] + lights, cap=8)


def _night_lights():
    """Fixed lights for the grade: lamp throws and bulbs, wet-road
    reflections on the street, burning wrecks."""
    key = (_key(), id(_grid()))
    hit = _cache["night"]
    if hit is not None and hit[0] == key:
        return hit[1]
    out = []
    station = _station()
    for lamp in _lamps():
        fam = lamp[4]
        hx, hy, hz = _lamp_head(lamp)
        reach = lamp[2] * K * 1.6
        out.append(("pool", (hx, 0.0, hz), lamp[3], reach * 0.72, _POOL_K.get(fam, 0.45)))
        out.append(("glow", (hx, hy, hz), lamp[3], 0.6 if fam != "tube" else 0.8, 0.55))
        if not station and fam in ("post", "wire", "door"):
            out.append(("reflect", (hx, 0.0, hz - 0.4), lamp[3], 0.6, 0.34))
    for col, row in _BURNING_CARS[_key()]:
        x, _, z = to3((col + 1) * T, row * T + T / 2.0)
        out.append(("pool", (x, 0.0, z), FIRE, 3.2, 0.5))
        out.append(("glow", (x, 1.0, z), FIRE, 1.0, 0.6))
    _cache["night"] = (key, out)
    return out


# ── screen space ───────────────────────────────────────────────────────

def _labels(s, v):
    """Ally names (and HP bars while the station holds) over their heads."""
    import pygame
    live = {a["name"]: a for a in getattr(STATE, "m4_allies", []) or []}
    for row in _wd.friendly_npcs():
        name, (x, y), col = row[0], row[1], row[2]
        rec = live.get(name)
        down = bool(rec and (rec.get("downed", 0) > 0 or rec.get("dead")))
        pt = v.screen_sim(x, y, 0.6 if down else 2.2)
        if pt is None or not (-40 < pt[0] < WIDTH + 40 and -40 < pt[1] < HEIGHT + 40):
            continue
        label = (rec or {}).get("label") or name
        img = font_terminal_small.render(label, True, col if not down else (220, 90, 80))
        tx, ty = int(pt[0]) - img.get_width() // 2, int(pt[1]) - img.get_height()
        s.blit(font_terminal_small.render(label, True, (0, 0, 0)), (tx + 1, ty + 1))
        s.blit(img, (tx, ty))
        if rec and rec.get("max_hp"):
            frac = max(0.0, min(1.0, rec["hp"] / float(rec["max_hp"])))
            if frac < 1.0 or down:
                bw = 30
                bx, by = int(pt[0]) - bw // 2, ty + img.get_height() + 1
                pygame.draw.rect(s, (20, 20, 20), (bx - 1, by - 1, bw + 2, 5))
                pygame.draw.rect(s, (220, 80, 70) if down else (120, 220, 150), (bx, by, int(bw * frac), 3))
