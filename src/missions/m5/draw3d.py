"""Mission 5 in 2.5D: Guard HQ, the Lower Quarter, the print works and the
tunnel in 3D.

``draw.submit_frame`` hands the frame here while ``game.topdown3d`` is on
(``CAMS["MISSION5"]``). The sim, the AI and every collision rect stay 2D;
this module only changes what the world looks like. Walls are drawn per
frame with the M1 cutaway; floors, paint, props and lamps are one static
batch per map. The world is one UiPass on the FLOOR layer, then the
world-anchored text (projected through the view) and the existing M5 screen
passes (rain, scanlines, death edge, flash, HUD, dialogue, FPV, reticle).
Any renderer error turns 2.5D off for the run (``td.disable``) and the
frame falls back to 2D.

Sets (picked by the live map): ``hq`` 30x16, ``quarter`` 40x30, ``print``
26x20 (also the raid), ``tunnel`` 48x12.
"""
import math

from core import config as _config
from core import outfits as _outfits
from core.config import HEIGHT, TILE_SIZE, WIDTH, font_terminal_small
from core.state import STATE
from engine.core import now_ms as _now_ms, now_s as _now_s
from engine.render2d import Layer as _L, UiPassDraw as _UiPassDraw
from game import topdown3d as td
from game.topdown3d import K, to3
from missions.m1 import draw3d as _m1
from missions.m1 import grade3d as _grade
from missions.m5 import decor as _decor
from missions.m5 import decor_paint as _paint
from missions.m5 import draw as _d
from missions.m5 import maps as _maps
from missions.m5 import quarter as _quarter
from missions.m5.meta import (QUARTER_TRAM_TILES, STAGE_DONE, STAGE_HQ, STAGE_PRINTWORKS,
                              STAGE_QUARTER, STAGE_RAID, STAGE_TUNNEL, C_VASILE)
from missions.m5.world import friendly_npcs

CAM = td.CAMS["MISSION5"]
T = TILE_SIZE
S = T * K                          # one tile in metres
AIM_H = _m1.AIM_H
STUB_H = _m1.STUB_H
CUT_CAP = (56, 58, 66)             # lifted: cut wall tops read as shapes, not black slabs
DOOR_H = _m1.DOOR_H
VOID = _m1.VOID

CAP = (54, 56, 62)
RIM = (104, 106, 102)
RIM_CUT = (58, 60, 62)
GLASS = (14, 16, 21)
LIT = (156, 122, 70)
FRAME = (58, 60, 62)
FIRE = (255, 140, 56)
STEEL = (58, 62, 66)
WOOD = (92, 66, 44)
WET = (24, 27, 32)
CURB = (96, 95, 90)
TUBE = (236, 236, 226)

_NIGHT = {"hq": dict(_m1.NIGHT, ambient=0.34, diffuse=0.40, tint=(1.06, 1.0, 0.9)),
          "quarter": dict(_m1.NIGHT, ambient=0.30, diffuse=0.42, tint=(0.88, 0.95, 1.08)),
          "print": dict(_m1.NIGHT, ambient=0.34, diffuse=0.40, tint=(1.05, 1.0, 0.94)),
          "tunnel": dict(_m1.NIGHT, ambient=0.30, diffuse=0.38, tint=(0.92, 1.0, 1.0))}
_AMBIENT = {"hq": (164, 156, 140), "quarter": (96, 106, 140), "print": (146, 132, 112),
            "raid": (144, 120, 110), "tunnel": (112, 112, 102)}

_FLOORS = {
    "hq": {"O": ((62, 68, 74), "m7_tile"), "L": ((66, 64, 58), "m7_tile"),
           "F": ((78, 66, 52), "m7_tile"), "D": ((74, 72, 66), "concrete")},
    "quarter": {".": ((38, 40, 44), "pavement"), "d": ((70, 70, 66), "concrete"),
                "F": ((62, 56, 48), "concrete"), "D": ((74, 72, 66), "concrete"),
                "L": ((58, 58, 56), "concrete")},
    "print": {"O": ((78, 70, 60), "concrete"), "L": ((60, 62, 60), "m7_tile"),
              "F": ((74, 62, 50), "m7_tile"), "D": ((80, 76, 68), "concrete"),
              "S": ((44, 42, 38), "concrete")},
    "tunnel": {"L": ((56, 60, 60), "concrete"), "O": ((56, 60, 60), "concrete"),
               "D": ((60, 62, 60), "concrete")},
}
_INNER = {"hq": ("m7_plaster", (86, 88, 84), (46, 58, 76)),
          "print": ("brick", (104, 74, 58), (52, 46, 42)),
          "tunnel": ("concrete", (70, 74, 74), (42, 50, 50))}
_BUILD = (("brick", (84, 62, 52), (110, 92, 80)), ("concrete", (76, 78, 80), (104, 106, 106)),
          ("m7_plaster", (96, 88, 72), (124, 114, 92)))
_STYLE = {"border": ("concrete", (58, 58, 56), (76, 76, 72)),
          "works": ("brick", (78, 68, 62), (104, 96, 88))}
_GUARD_KIT = dict(jacket=_outfits.GUARD_BLACK, pants=_outfits.GUARD_PANTS,
                  vest=_outfits.GUARD_VEST, armband=_outfits.GUARD_ARMBAND)
CIVILIAN = dict(jacket=(74, 70, 64), pants=(46, 46, 50), long_coat=None, vest=None, pouches=False,
                lapel=None, shirt=None, armband=None)

_cache = {"kinds": None, "walls": None, "meshes": {}, "packed": {}, "doors": None, "lights": None,
          "view": None, "tgt": None}


# ── frame ──────────────────────────────────────────────────────────────

def submit_frame(q, fcx, fcy):
    """Submit one Mission 5 frame in 2.5D. The screen passes keep the 2D
    painter's order (ADR-017)."""
    cam_x, cam_y = int(round(fcx)), int(round(fcy))
    v = td.View(CAM, fcx + WIDTH / 2.0, fcy + HEIGHT / 2.0)
    _cache["view"] = v
    _tick()
    sub = q.submit
    sub(_UiPassDraw(lambda s: render_world(s, v), "m5.world3d"), _L.FLOOR, sort_key=0)
    sub(_UiPassDraw(lambda s: _labels(s, v), "m5.labels3d"), _L.FX_WORLD, sort_key=(9, 0))
    sub(_UiPassDraw(_grade.vignette, "m5.vignette"), _L.OVERLAY_WORLD, sort_key=(3, 0))
    _d._submit_rain(q, 0)
    _d._submit_scanlines(q, 1)
    if STATE.player_dead:
        sub(_UiPassDraw(_draw_death_edge, "m5.death_edge"), _L.UI, sort_key=2)
    _d._submit_gc_flash(q, 3)
    sub(_UiPassDraw(lambda s: _d._draw_hud(s, cam_x, cam_y), "m5.hud"), _L.UI, sort_key=4)
    sub(_UiPassDraw(_d._draw_dialogue, "m5.dialogue"), _L.UI, sort_key=5)
    if _d._m5_fpv.active():
        sub(_UiPassDraw(_d._m5_fpv.draw, "m5.fpv"), _L.UI, sort_key=6)
    else:
        sub(_UiPassDraw(_d._draw_reticle_ui, "m5.reticle"), _L.UI, sort_key=7)


def _tick():
    """The per-frame timers the 2D passes age: blood fade, muzzle flash."""
    for decal in STATE.blood_decals[:]:
        decal[2] -= 0.25
        if decal[2] <= 0:
            STATE.blood_decals.remove(decal)
    if STATE.muzzle_flash_timer > 0:
        STATE.muzzle_flash_timer -= 1


def _draw_death_edge(surface):
    import pygame
    red = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    for i in range(6):
        pygame.draw.rect(red, (120, 0, 0, 70 - i * 10), (i * 6, i * 6, WIDTH - i * 12, HEIGHT - i * 12), 6)
    surface.blit(red, (0, 0))


def render_world(surface, v):
    """Draw the live M5 set and cast through view ``v`` onto ``surface``."""
    from cutscenes import m6fx3d as _fx
    from cutscenes import m6world3d as _w
    from engine3d import Light
    r, buf = _w.rend(*CAM.res)
    saved = (r.light, r.fog, r.fog_start, r.fog_end, r.light_cap)
    tm = _now_ms()
    kind = _kind()
    try:
        r.light = Light(**_NIGHT[kind])
        r.fog, r.fog_start, r.fog_end = VOID, 32.0, 64.0
        r.light_cap = 8
        v.apply(r)
        buf.fill(VOID)
        r.begin()
        first = _w.static_scene(r, ("m5_td3d", kind, id(_grid())))
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
        _draw_cast(r, flashes, tm)
        _draw_fx(r, flashes, tm)
        dyn = _m1._flash_lights(flashes, tm)
        grade = _lamp_lights(r, v, flashes, tm)
        td.cast_shadows(r)
        r.flush(buf)
    except Exception:
        import traceback
        traceback.print_exc()
        td.disable()                  # next frame is the 2D painter
        return False
    finally:
        r.light, r.fog, r.fog_start, r.fog_end, r.light_cap = saved
    _fx.present_crisp(buf, surface)
    _grade.apply(surface, v, grade + dyn, ambient=_AMBIENT[_ambient_key(kind)])
    return True


# ── helpers ────────────────────────────────────────────────────────────

def _grid():
    return _maps.MISSION5_MAP


def _kind():
    g = _grid()
    if g is _maps.MISSION5_HQ_MAP:
        return "hq"
    if g is _maps.MISSION5_QUARTER_MAP:
        return "quarter"
    if g is _maps.MISSION5_TUNNEL_MAP:
        return "tunnel"
    return "print"


def _ambient_key(kind):
    return "raid" if kind == "print" and getattr(STATE, "mission5_stage", None) == STAGE_RAID else kind


def _stage():
    return getattr(STATE, "mission5_stage", None)


def _dims():
    g = _grid()
    return (len(g[0]) if g else 0), len(g)


def _glyph(col, row):
    g = _grid()
    if 0 <= row < len(g) and 0 <= col < len(g[row]):
        return g[row][col]
    return "C"


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


def _tex(col, name):
    from engine3d import tex
    return tex(name, like=tuple(max(0, min(255, int(c))) for c in col), tint=True)


def _box_at(r, w, h, d, col, x, y, z, **kw):
    from cutscenes import m6world3d as _w
    from engine3d import box
    _w.add(r, box(w, h, d, col, center=(x, y, z), **kw))


def _px_box(r, rect, h, col, name="concrete", top=None, y0=0.0):
    """A box on a sim-pixel rect (x, y, w, h) standing ``h`` metres tall."""
    from engine3d import tex
    x, y, w, hh = rect
    cx, _, cz = to3(x + w / 2.0, y + hh / 2.0)
    cols = {"top": top} if top else {}
    _box_at(r, w * K, h, hh * K, tex(name, like=col), cx, y0 + h / 2.0, cz, cols=cols)
    return cx, cz


# ── floors ─────────────────────────────────────────────────────────────

def _floor_ch(col, row):
    ch = _glyph(col, row)
    if ch in ("E", "M"):
        return "."
    if ch in ("N", "X", "I", "H"):
        return "O"
    if ch == "P":
        return "F"
    if ch == "G":
        return "L"
    if ch == "D" and _kind() == "quarter":
        return "d"
    if ch == "B":
        for dc, dr in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            n = _glyph(col + dc, row + dr)
            if n not in ("B", "C", "H"):
                return _floor_ch(col + dc, row + dr)
        return "." if _kind() == "quarter" else "O"
    return ch


def _floor_at(col, row):
    """(colour, texture) of the ground tile, or None for water."""
    ch = _floor_ch(col, row)
    if ch == "W":
        return None
    if _kind() == "hq":
        return _hq_floor(col, row, ch)
    tab = _FLOORS[_kind()]
    base, name = tab.get(ch) or tab.get(".") or next(iter(tab.values()))
    k = 1.0 + (_hash(col, row, 9) - 4) * 0.012
    if _kind() == "quarter" and ch == "." and _hash(col * 3 + 1, row * 5 + 2, 100) < 9:
        base = WET
    if _kind() == "tunnel" and any(_floor_ch(col + dc, row + dr) == "W"
                                   for dc in (-1, 0, 1) for dr in (-1, 0, 1)):
        k *= 0.72                  # splashed concrete at the flood's edge
    return (base[0] * k, base[1] * k, base[2] * k), name


def _build_set(r):
    from cutscenes import m6world3d as _w
    from engine3d import quad_xz
    mw, mh = _dims()
    kind = _kind()
    for row in range(mh):
        for col in range(mw):
            if _glyph(col, row) == "C":
                continue
            fl = _floor_at(col, row)
            x0, z0 = col * S, -row * S
            if fl is None:
                _water_tile(r, col, row)
                continue
            if kind == "hq" and _floor_ch(col, row) == "F":
                h = S / 2.0
                for i in range(2):
                    for j in range(2):
                        c = (78, 72, 62) if (i + j + col + row) % 2 else (52, 48, 44)
                        _w.add(r, quad_xz(x0 + i * h, z0 - (j + 1) * h, x0 + (i + 1) * h, z0 - j * h, 0.0,
                                          _tex(c, "concrete"), layer=0))
                continue
            _w.add(r, quad_xz(x0, z0 - S, x0 + S, z0, 0.0, _tex(*fl), layer=0))
    _paint_ground(r)
    for row in range(mh):
        for col in range(mw):
            _tile_prop(r, col, row)
    {"hq": _hq_props, "quarter": _quarter_props, "print": _print_props, "tunnel": _tunnel_props}[kind](r)
    for lamp in _static_lights():
        _lamp_fixture(r, lamp)


WATER = (20, 50, 58)
SHALLOW = (44, 88, 86)
DEEP = (10, 26, 36)
FOAM = (120, 156, 150)
RAIL = (118, 112, 104)
WATER_Y = -0.14
BED_Y = -0.5
SUB = 3
RAIL_ROW = 6


def _is_water(col, row):
    return _floor_ch(col, row) == "W"


def _water_tile(r, col, row):
    """Sunken silt bed and a tall concrete lip on the shore sides, dark and
    wet below the waterline; the surface itself is the animated wave mesh
    (_water_surface)."""
    from cutscenes import m6world3d as _w
    from engine3d import box, quad_xz
    x0, z0 = col * S, -row * S
    _w.add(r, quad_xz(x0, z0 - S, x0 + S, z0, BED_Y, (14, 20, 20), layer=0))
    t = 0.14
    for dc, dr, bx, bz, w, d in ((0, -1, x0 + S / 2, z0 - t / 2, S, t), (0, 1, x0 + S / 2, z0 - S + t / 2, S, t),
                                 (-1, 0, x0 + t / 2, z0 - S / 2, t, S), (1, 0, x0 + S - t / 2, z0 - S / 2, t, S)):
        if not _is_water(col + dc, row + dr):
            _w.add(r, box(w, 0.46, d, (34, 40, 40), center=(bx, -0.29, bz)))
            _w.add(r, box(w, 0.14, d, (66, 68, 64), center=(bx, 0.01, bz), cols={"top": (96, 96, 88)}))


def _wave(x, z, t):
    return (0.06 * math.sin(x * 2.3 + t * 1.1 + math.sin(z * 1.7 + t * 0.6)) +
            0.045 * math.sin(z * 3.1 - t * 1.6 + x * 0.8) +
            0.02 * math.sin((x + z) * 5.3 + t * 2.4))


def _water_cells():
    cells = _cache.get("wcells")
    if cells is None:
        cells = _cache["wcells"] = [(c, rr) for rr in range(4, 8) for c in range(27, 38) if _is_water(c, rr)]
    return cells


def _shore(i, j):
    """Metres from grid vertex (i, j) to the nearest dry tile; static, cached."""
    tab = _cache.setdefault("shore", {})
    v = tab.get((i, j))
    if v is None:
        step = S / SUB
        x, z = i * step, j * step
        col, row = int(x // S), int(z // S)
        v = 9.0
        for dr in range(-3, 4):
            for dc in range(-3, 4):
                c, rr = col + dc, row + dr
                if _is_water(c, rr):
                    continue
                ddx = max(c * S - x, 0.0, x - (c + 1) * S)
                ddz = max(rr * S - z, 0.0, z - (rr + 1) * S)
                v = min(v, math.hypot(ddx, ddz))
        tab[(i, j)] = v
    return v


def _water_surface(r, tm):
    """The flood as a rolling heightfield: teal in the shallows by the lip,
    near-black over the deep middle, crests a shade lighter. Colour moves
    smoothly from face to face so the swell reads as one sheet."""
    t = tm / 1000.0
    fx, fz = _cache.get("tgt") or (0.0, 0.0)
    n = SUB
    step = S / n
    verts, faces, index = [], [], {}
    lamps = [(l["head"][0], l["head"][2], l["col"]) for l in _lights_for(STAGE_TUNNEL)]

    def vert(i, j):
        k = (i, j)
        v = index.get(k)
        if v is None:
            x, z = i * step, -j * step
            v = index[k] = len(verts)
            verts.append((x, WATER_Y + _wave(x, z, t), z))
        return v
    for col, row in _water_cells():
        x0, z0 = col * S, -row * S
        if abs(x0 - fx) > 26.0 or abs(z0 - fz) > 20.0:
            continue
        for a in range(n):
            for b in range(n):
                i, j = col * n + a, row * n + b
                q = (vert(i, j), vert(i + 1, j), vert(i + 1, j + 1), vert(i, j + 1))
                h = sum(verts[v][1] for v in q) / 4.0 - WATER_Y
                cx, cz = (i + 0.5) * step, -(j + 0.5) * step
                d = (_shore(i, j) + _shore(i + 1, j) + _shore(i + 1, j + 1) + _shore(i, j + 1)) / 4.0
                base = td.mix(SHALLOW, DEEP, min(1.0, d / 1.4) ** 0.7)
                c_ = _shade(base, max(0.86, min(1.22, 1.0 + h * 1.8)))
                for lx, lz, lc in lamps:
                    g = max(0.0, 1.0 - math.hypot(cx - lx, cz - lz) / 2.6)
                    if g > 0.0:
                        c_ = td.mix(c_, lc, 0.32 * g * g)
                faces.append((q, c_, 0, True, None, False))
    if faces:
        r.add_dynamic(verts, faces)


def _rails(r):
    """The old narrow-gauge track along the tunnel floor, row 6, with
    sleepers; under the flood it is drawn per frame (_rails_under)."""
    from engine3d import tex
    z = -(6.5 * T) * K
    mw, _ = _dims()
    wood = tex("crate", like=(74, 54, 38))
    for col in range(1, mw - 1):
        if _glyph(col, RAIL_ROW) in ("C", "W"):
            continue
        x0 = col * S
        for k in range(4):
            _box_at(r, 0.16, 0.05, S * 0.52, wood, x0 + (k + 0.5) * S / 4.0, 0.025, z)
        for dz in (-0.2, 0.2):
            _box_at(r, S, 0.06, 0.05, RAIL, x0 + S / 2.0, 0.08, z + dz, cols={"top": (170, 162, 150)})


def _rails_under(r, t):
    """The track seen through the flood: it runs off the lip and fades into
    the deep, rails bent by the moving surface like refraction."""
    z = -(RAIL_ROW + 0.5) * S
    run = [c for c, rr in _water_cells() if rr == RAIL_ROW]
    if not run:
        return
    xa, xb = min(run) * S, (max(run) + 1) * S
    y = WATER_Y + 0.015
    seg = S / 4.0

    def fade(x):
        return min(1.0, min(x - xa, xb - x) / 1.8)

    def bend(x, zz):
        return 0.035 * math.sin(x * 4.0 + t * 1.7) + 0.025 * math.sin(zz * 6.0 - t * 2.3)
    x = xa
    while x < xb - 1e-6:
        f = fade(x + seg / 2.0)
        x1 = x + seg
        for dz in (-0.2, 0.2):
            zz = z + dz
            r.add_line3d((x, y + _wave(x, zz, t), zz + bend(x, zz)), (x1, y + _wave(x1, zz, t), zz + bend(x1, zz)),
                         td.mix(RAIL, DEEP, 0.2 + 0.5 * f), 1, layer=1)
        sx = x + seg / 2.0
        if f < 0.95:
            r.add_line3d((sx + bend(sx, z - 0.42), y + _wave(sx, z - 0.42, t), z - 0.42),
                         (sx + bend(sx, z + 0.42), y + _wave(sx, z + 0.42, t), z + 0.42),
                         td.mix((74, 54, 38), DEEP, 0.35 + 0.6 * f), 1, layer=1)
        x = x1


def _water_dynamic(r, tm, lamps_on=True):
    """Glints riding the crests, foam along every lip, the track under the
    flood and the lamp streaks."""
    t = tm / 1000.0
    cells = _water_cells()
    if not cells:
        return
    fx, fz = _cache.get("tgt") or (0.0, 0.0)
    _rails_under(r, t)
    for i, (c, rr) in enumerate(cells):
        x0, z0 = c * S, -rr * S
        if abs(x0 - fx) > 24.0 or abs(z0 - fz) > 18.0:
            continue
        for k in range(3):
            gx = x0 + 0.2 + ((_hash(i * 3 + k, 5, 100) / 100.0) + t * 0.05) % 1.0 * (S - 0.7)
            gz = z0 - 0.2 - _hash(k, i, 100) / 100.0 * (S - 0.4)
            h = _wave(gx, gz, t)
            if h < 0.045:
                continue
            a = min(1.0, (h - 0.045) / 0.05)
            ln = 0.15 + 0.3 * a
            r.add_line3d((gx, WATER_Y + 0.02 + h, gz), (gx + ln, WATER_Y + 0.02 + h, gz),
                         td.mix(SHALLOW, (190, 216, 210), 0.35 + 0.5 * a), 1, layer=1)
        for dc, dr in ((0, -1), (0, 1), (-1, 0), (1, 0)):
            if _is_water(c + dc, rr + dr):
                continue
            for j in range(3):
                u = (j + 0.25 + 0.15 * math.sin(t * 0.9 + i * 1.3 + j * 2.1)) / 3.0
                w = 0.22 + 0.12 * math.sin(t * 1.4 + i + j * 1.9)
                lap = 0.3 + 0.06 * math.sin(t * 1.8 + i * 0.7 + j)
                if dr:
                    zz = z0 - lap if dr < 0 else z0 - S + lap
                    a, b = (x0 + u * S, zz), (x0 + u * S + w, zz)
                else:
                    xx = x0 + lap if dc < 0 else x0 + S - lap
                    a, b = (xx, z0 - u * S), (xx, z0 - u * S - w)
                r.add_line3d((a[0], WATER_Y + 0.04 + _wave(a[0], a[1], t), a[1]),
                             (b[0], WATER_Y + 0.04 + _wave(b[0], b[1], t), b[1]), FOAM, 1, layer=1)
    for lamp in _lights_for(STAGE_TUNNEL):
        hx, hz = lamp["head"][0], lamp["head"][2]
        c, rr = int(hx // S), int(-hz // S)
        if not _is_water(c, rr):
            continue
        for j in range(6):
            wob = 0.1 * math.sin(t * 2.2 + j * 1.3 + hx)
            half = max(0.06, 0.34 - j * 0.05) * (0.8 + 0.2 * math.sin(t * 3.1 + j))
            zz = hz - 0.05 - j * 0.14
            y = WATER_Y + 0.03 + _wave(hx, zz, t)
            r.add_line3d((hx - half + wob, y, zz), (hx + half + wob, y, zz),
                         td.mix(lamp["col"], SHALLOW, 0.2 + 0.12 * j), 1, layer=1)


def _paint_ground(r):
    """Curbs, lane dashes, stair steps, slab joints."""
    from cutscenes import m6world3d as _w
    from engine3d import quad_xz
    kind = _kind()
    mw, mh = _dims()
    y = 0.006
    for row in range(mh):
        for col in range(mw):
            ch = _glyph(col, row)
            x0, z0 = col * S, -row * S
            if kind == "quarter":
                if ch == "d":
                    for dc, dr, edge in ((0, -1, "n"), (0, 1, "s"), (-1, 0, "w"), (1, 0, "e")):
                        if _floor_ch(col + dc, row + dr) != ".":
                            continue
                        t = 0.09
                        q = {"n": (x0, z0 - t, x0 + S, z0), "s": (x0, z0 - S, x0 + S, z0 - S + t),
                             "w": (x0, z0 - S, x0 + t, z0), "e": (x0 + S - t, z0 - S, x0 + S, z0)}[edge]
                        _w.add(r, quad_xz(*q, y, CURB, layer=1))
                if ch in (".", "E", "M") and col % 2 == 0 and _floor_ch(col, row + 1) == "." \
                        and _floor_ch(col, row - 1) != ".":
                    _w.add(r, quad_xz(x0 + 0.35, z0 - S - 0.04, x0 + S - 0.35, z0 - S + 0.04, y,
                                      (150, 140, 96), layer=1))
            elif ch == "S":
                for i in range(4):
                    shade = 0.55 + 0.12 * i
                    _w.add(r, quad_xz(x0 + 0.1, z0 - S + 0.1 + i * 0.37, x0 + S - 0.1, z0 - S + 0.4 + i * 0.37,
                                      y, _shade((120, 112, 100), shade), layer=1))
            elif ch in ("O", "L", "F") and (col + row) % 2 == 0:
                _w.add(r, quad_xz(x0, z0 - 0.012, x0 + S, z0 + 0.012, 0.004, (36, 38, 38), layer=1))


# ── props ──────────────────────────────────────────────────────────────

def _tile_prop(r, col, row):
    """The per-tile furniture: B and H glyphs."""
    ch = _glyph(col, row)
    kind = _kind()
    x, _, z = _tc(col, row)
    if ch == "B":
        if kind == "hq":
            if row == 4:
                _bench(r, x, z)
            elif row == 3:
                if _glyph(col - 1, row) != "B":
                    _desk(r, col, row)
            else:
                _crate(r, col, row, x, z)
        elif kind == "quarter":
            if (col, row) not in QUARTER_TRAM_TILES:
                _barrier(r, col, row, x, z)
        elif kind == "print":
            (_paper if (col <= 12 and row <= 5) else _crate)(r, col, row, x, z)
        else:
            _rubble(r, col, row, x, z)
    elif ch == "H" and _glyph(col - 1, row) != "H":
        _press(r, col, row)


def _crate(r, col, row, x, z):
    from engine3d import tex
    h = 0.8 + 0.1 * _hash(col, row, 3)
    _box_at(r, S * 0.8, h, S * 0.8, tex("crate", like=WOOD), x, h / 2.0, z, cols={"top": (120, 92, 60)})
    _box_at(r, S * 0.82, 0.06, S * 0.82, (60, 44, 30), x, h * 0.5, z, skip=("top", "bottom"))


def _paper(r, col, row, x, z):
    from engine3d import tex
    _box_at(r, S * 0.82, 0.14, S * 0.82, tex("crate", like=(80, 60, 40)), x, 0.07, z)
    n = 5
    for i in range(n):
        _box_at(r, S * 0.74, 0.2, S * 0.74, (206, 202, 190) if i % 2 else (190, 186, 174), x, 0.24 + i * 0.2, z)
    _box_at(r, S * 0.78, 0.03, 0.03, (150, 40, 36), x, 0.9, z - S * 0.38)


def _bench(r, x, z):
    from engine3d import tex
    _box_at(r, S * 0.92, 0.1, S * 0.5, tex("crate", like=(112, 84, 54)), x, 0.5, z)
    for dx in (-0.6, 0.6):
        _box_at(r, 0.08, 0.5, S * 0.4, STEEL, x + dx, 0.25, z)


def _desk(r, col, row):
    """Vasile's desk: three tiles of dark wood, papers and the Guard flag."""
    from engine3d import tex
    x, _, z = _tc(col + 1, row)
    w = 3 * S * 0.96
    _box_at(r, w, 0.95, S * 0.8, tex("crate", like=(70, 52, 38)), x, 0.475, z, cols={"top": (96, 72, 50)})
    for i in range(3):
        _box_at(r, 0.3, 0.012, 0.22, (216, 212, 198), x - 0.6 + i * 0.55, 0.96, z + 0.05, yaw=None) \
            if False else _box_at(r, 0.3, 0.012, 0.22, (216, 212, 198), x - 0.6 + i * 0.55, 0.96, z + 0.05)
    _box_at(r, 0.2, 0.18, 0.14, (30, 32, 34), x + 0.9, 1.04, z)


def _barrier(r, col, row, x, z):
    """Checkpoint jersey barrier with a painted stripe."""
    from engine3d import tex
    shade = 74 + _hash(col, row, 24)
    body = tex("concrete", like=(shade, shade, shade - 4))
    _box_at(r, S * 0.9, 0.34, S * 0.46, body, x, 0.17, z)
    _box_at(r, S * 0.9, 0.6, S * 0.26, body, x, 0.64, z, cols={"top": (110, 108, 98)})
    _box_at(r, S * 0.6, 0.1, 0.02, (196, 60, 44), x, 0.7, z - S * 0.14)


def _rubble(r, col, row, x, z):
    from engine3d import tex
    for i in range(5):
        s = 0.22 + 0.06 * _hash(col + i, row, 4)
        _box_at(r, s, s * 0.7, s, tex("concrete", like=(66 + i * 4, 66 + i * 4, 64)),
                x + (_hash(i, col, 9) - 4) * 0.12, s * 0.35 + 0.1 * (i == 2), z + (_hash(i, row, 9) - 4) * 0.12)


def _press(r, col, row):
    """A two-tile flatbed press: steel body, drum, feeder, status lamp."""
    from engine3d import tex
    x, _, z = to3((col + 1) * T, row * T + T / 2.0)
    w, d = 2 * S * 0.94, S * 0.84
    _box_at(r, w, 0.9, d, tex("steel", like=(52, 56, 60)), x, 0.45, z, cols={"top": (40, 44, 48)})
    _box_at(r, w * 0.5, 0.6, d * 0.7, tex("steel", like=(70, 74, 78)), x - w * 0.12, 1.2, z)
    for i in range(3):
        _box_at(r, w * 0.46, 0.14, 0.14, (30, 32, 34), x - w * 0.12, 1.1 + i * 0.2, z - d * 0.2)
    _box_at(r, w * 0.3, 0.12, d * 0.9, (200, 196, 180), x + w * 0.34, 0.96, z)
    _box_at(r, w, 0.06, 0.03, (190, 150, 40), x, 0.18, z - d / 2.0 - 0.01)
    _box_at(r, 0.1, 0.06, 0.04, (90, 240, 130), x + w * 0.4, 1.5, z - d / 2.0 - 0.02, emissive=True)


def _locker(r, x, z, yaw=0.0):
    from engine3d import tex
    _box_at(r, 0.66, 1.9, 0.56, tex("steel", like=(62, 68, 74)), x, 0.95, z, cols={"top": (40, 44, 50)})
    _box_at(r, 0.02, 1.6, 0.02, (30, 32, 36), x, 1.0, z - 0.29)
    _box_at(r, 0.5, 0.12, 0.02, (14, 14, 16), x, 1.5, z - 0.29)


def _hq_props(r):
    from engine3d import tex
    steel = tex("steel", like=(62, 68, 74))
    # locker bank, bench, sign-up desk, armory bench, rifle racks, cabinets
    x, z = _px_box(r, _paint.HQ_SOLIDS[0], 1.9, (62, 68, 74), "steel", top=(40, 44, 50))
    w = _paint.HQ_SOLIDS[0][2] * K
    for i in range(1, 10):
        _box_at(r, 0.02, 1.7, 0.02, (28, 30, 34), x - w / 2.0 + i * w / 10.0, 1.0, z - _paint.HQ_SOLIDS[0][3] * K / 2.0 - 0.01)
    _px_box(r, _paint.HQ_SOLIDS[1], 0.5, (112, 84, 54), "crate")
    _px_box(r, _paint.HQ_SOLIDS[2], 1.0, (96, 72, 50), "crate", top=(120, 96, 66))
    _px_box(r, _paint.HQ_SOLIDS[3], 1.0, (66, 70, 74), "steel", top=(88, 82, 70))
    x, z = _px_box(r, _paint.HQ_SOLIDS[4], 1.6, (46, 48, 52), "steel", top=(30, 32, 34))
    for i in range(5):
        _box_at(r, 0.06, 0.06, 1.1, (28, 28, 30), x - 0.1, 1.0, z - 0.8 + i * 0.42)
    _px_box(r, _paint.HQ_SOLIDS[5], 1.3, (84, 88, 90), "steel", top=(60, 64, 66))
    del steel
    _hq_dress(r)


# ── Guard HQ dressing (mirrors decor_paint.paint_hq) ───────────────────

GUARD_RED = (176, 30, 32)
KRAP_BLUE = (52, 86, 150)
GOLD = (160, 128, 64)
HQ_OFFICE = (20, 2, 8, 6)          # cols, rows of Vasile's planked office


def _hq_floor(col, row, ch):
    """The 2D finish per room: warm slabs, dark corridor screed, planks in
    the office. The locker hall's half-tile checks are split in _build_set."""
    oc, orw, ow, oh = HQ_OFFICE
    if oc <= col < oc + ow and orw <= row < orw + oh:
        k = 1.0 + (_hash(col, row, 7) - 3) * 0.03
        return (92 * k, 66 * k, 44 * k), "m7_plank"
    if ch == "L":
        v = 50 + (col * 5 + row * 11) % 6
        return (v, v - 2, v - 6), "concrete"
    if ch == "D":
        return (70, 64, 56), "concrete"
    v = 62 + (col * 7 + row * 13) % 7
    return (v, v - 4, v - 10), "concrete"


def _decal(r, px, py, pw, ph, col, y=0.008):
    """A flat floor patch on a sim-pixel rect."""
    from cutscenes import m6world3d as _w
    from engine3d import quad_xz
    _w.add(r, quad_xz(px * K, -(py + ph) * K, (px + pw) * K, -py * K, y, col, layer=1))


def _on_wall(r, px, py, w, h, y, col, d=0.03, out=0.0, **kw):
    """A panel w x h metres on the south-facing wall face whose sim-pixel
    edge is ``py``, centred on sim x ``px`` at height ``y``."""
    _box_at(r, w, h, d, col, px * K, y, -py * K - d / 2.0 - 0.015 - out, **kw)


def _portrait3d(r, px, py, w, h, y):
    _on_wall(r, px, py, w, h, y, GOLD, d=0.05)
    _on_wall(r, px, py, w - 0.12, h - 0.12, y, (40, 34, 30), d=0.05, out=0.01)
    _on_wall(r, px, py, w * 0.28, h * 0.34, y + h * 0.1, (206, 170, 140), out=0.06)
    _on_wall(r, px, py, w * 0.56, h * 0.22, y - h * 0.26, (20, 20, 24), out=0.06)
    _on_wall(r, px, py, w * 0.08, h * 0.05, y - h * 0.22, GUARD_RED, out=0.07)


def _banner3d(r, px, py):
    _on_wall(r, px, py, 0.42, 0.95, 2.05, (18, 18, 22))
    _on_wall(r, px, py, 0.42, 0.32, 2.05, GUARD_RED, out=0.01)
    _on_wall(r, px, py, 0.14, 0.14, 2.05, (200, 170, 90), out=0.02)
    _on_wall(r, px, py, 0.56, 0.05, 2.54, (30, 30, 34), out=0.01)


def _flag3d(r, px, py):
    x, _, z = to3(px, py)
    _box_at(r, 0.32, 0.06, 0.32, (60, 54, 44), x, 0.03, z)
    _box_at(r, 0.04, 2.3, 0.04, (180, 160, 110), x, 1.15, z)
    _box_at(r, 0.6, 0.22, 0.02, (18, 18, 22), x + 0.32, 2.1, z)
    _box_at(r, 0.6, 0.22, 0.02, GUARD_RED, x + 0.32, 1.88, z)
    _box_at(r, 0.07, 0.07, 0.07, (200, 170, 90), x, 2.34, z)


def _hq_dress(r):
    """The painted HQ props of the 2D view, built in 3D. Things the 2D map
    hangs on the corridor's south wall go on the north wall here: the south
    wall sinks to a stub between the camera and Biribel."""
    from engine3d import tex
    import random
    rnd = random.Random(55)
    wood = tex("crate", like=(112, 82, 52))
    # Locker hall: runner, taped-over names, kit bag, torn patch, TV.
    _decal(r, 1 * T + 16, 10 * T + 30, 7 * T - 32, 2 * T + 20, (96, 76, 52), 0.006)
    _decal(r, 1 * T + 20, 10 * T + 34, 7 * T - 40, 2 * T + 12, (64, 50, 40), 0.009)
    _decal(r, 1 * T + 28, 10 * T + 42, 7 * T - 56, 2 * T - 4, (52, 40, 32), 0.011)
    _decal(r, 1 * T + 30, 10 * T + 44, 7 * T - 60, 2 * T - 8, (64, 50, 40), 0.012)
    lk = _paint.HQ_SOLIDS[0]
    for i in range(14):
        x = 1 * T + 6 + i * 31
        if x + 28 > 8 * T:
            break
        _on_wall(r, x + 14, lk[1] + lk[3], 0.5, 0.11, 1.45,
                 (10, 10, 12) if i in (2, 6, 9) else (210, 206, 190), d=0.02)
    _box_at(r, 0.95, 0.3, 0.5, tex("crate", like=(54, 62, 46)), (6 * T + 24) * K, 0.15, -(11 * T + 47) * K)
    _decal(r, 5 * T + 22, 13 * T + 12, 16, 16, (230, 230, 230), 0.01)
    _decal(r, 5 * T + 24, 13 * T + 14, 12, 12, KRAP_BLUE, 0.012)
    _decal(r, 3 * T - 4, 12 * T + 4, 12, 10, (210, 210, 200), 0.01)
    tvx, tvz = (2 * T + 77) * K, -(15 * T - 12) * K
    _box_at(r, 1.4, 0.55, 0.45, wood, tvx, 0.275, tvz)
    _box_at(r, 1.0, 0.62, 0.14, (24, 24, 28), tvx, 0.88, tvz - 0.08)
    # Corridor: half-done repaint along the north wall, KRAP blue giving way
    # to Guard black; drips where the brush stopped.
    split = int(18.3 * T)
    for col in range(9, 24):
        if _glyph(col, 9) != "C":
            continue
        for x0, x1 in ((col * T, min((col + 1) * T, split)), (max(col * T, split), (col + 1) * T)):
            if x1 <= x0:
                continue
            blue = x1 <= split
            cx, w = (x0 + x1) / 2.0, (x1 - x0) * K
            _on_wall(r, cx, 10 * T, w, 0.32, 1.05, KRAP_BLUE if blue else (22, 22, 26))
            _on_wall(r, cx, 10 * T, w, 0.07, 1.05, (220, 222, 226) if blue else GUARD_RED, out=0.005)
    for _ in range(9):
        dx = split - rnd.randint(0, 22)
        h = rnd.uniform(0.12, 0.55)
        _on_wall(r, dx, 10 * T, 0.04, h, 1.21 - h / 2.0, (22, 22, 26), out=0.012)
    for px in (int(11.2 * T), int(20.5 * T)):
        _portrait3d(r, px, 10 * T, 0.62, 0.8, 1.95)
    for bx in (int(12.3 * T), int(15.3 * T), int(21.3 * T)):
        _banner3d(r, bx + 7, 10 * T)
    nb = int(16.3 * T) + 44                                      # notice board
    _on_wall(r, nb, 10 * T, 2.2, 0.82, 1.62, (82, 60, 40))
    _on_wall(r, nb, 10 * T, 2.08, 0.7, 1.62, (120, 90, 58), out=0.01)
    for i in range(6):
        sx = nb - 88 // 2 + 5 + i * 14 + 5
        _on_wall(r, sx, 10 * T, 0.27, 0.36, 1.64, (226, 224, 214), out=0.02)
        for k in range(3):
            _on_wall(r, sx, 10 * T, 0.2, 0.025, 1.74 - k * 0.09, (60, 60, 70), out=0.025)
            if i != 4:
                _on_wall(r, sx, 10 * T, 0.24, 0.02, 1.74 - k * 0.09, GUARD_RED, out=0.03)
    _portrait3d(r, nb, 10 * T, 0.78, 0.66, 2.45)                 # Retardovici, new frame
    for k in range(4):
        _on_wall(r, nb - 30 + k * 20, 10 * T, 0.03, 0.03, 2.06, (20, 18, 16), out=0.005)
    _decal(r, split - 50, 10 * T + 12, 110, 40, (182, 180, 170), 0.01)       # drop cloth
    for _ in range(18):
        rr = rnd.randint(2, 5)
        _decal(r, split - 46 + rnd.randint(0, 100), 10 * T + 14 + rnd.randint(0, 34), rr, rr, (24, 24, 28), 0.012)
    _decal(r, split + 4, 10 * T + 22, 9, 5, (40, 70, 130), 0.012)
    lad = (170, 140, 80)
    for lx in (split - 30, split - 6):
        _box_at(r, 0.05, 1.9, 0.05, lad, lx * K, 0.95, -(10 * T + 6) * K)
    for i in range(6):
        _box_at(r, (24 * K), 0.04, 0.04, (150, 120, 70), (split - 18) * K, 0.25 + i * 0.3, -(10 * T + 6) * K)
    for tx, ty, top in ((split + 26, 10 * T + 30, (16, 16, 18)), (split + 44, 10 * T + 40, GUARD_RED),
                        (split + 12, 10 * T + 44, (16, 16, 18))):
        _box_at(r, 0.36, 0.38, 0.36, (60, 60, 64), tx * K, 0.19, -ty * K, cols={"top": top})
        _box_at(r, 0.37, 0.03, 0.37, (90, 90, 96), tx * K, 0.36, -ty * K, skip=("top", "bottom"))
    for i in range(5):                                          # queue tape
        _decal(r, int(13.2 * T) + i * 24, 12 * T + 44, 12, 4, (200, 170, 40), 0.01)
    dx, dy, dw, dh = _paint.HQ_SOLIDS[2]                        # sign-up desk top
    for i in range(4):
        _box_at(r, 0.45, 0.02, 0.06, (200, 30, 30), (dx + 17) * K, 1.01 + i * 0.02, -(dy + 7 + i * 3) * K)
    _box_at(r, 0.62, 0.012, 0.38, (222, 218, 200), (dx + 53) * K, 1.006, -(dy + 13) * K)
    from game.scenery3d import prop, medical_supplies
    crt = prop("monitor_crt")
    if crt is not None:
        _put(r, crt, ((dx + dw - 18) * K, 1.0, -(dy + dh / 2) * K), yaw=180)
    else:
        _box_at(r, 0.42, 0.36, 0.32, (150, 142, 120), (dx + dw - 18) * K, 1.18, -(dy + dh / 2) * K)
    for px, py, w in ((int(10.5 * T), int(11.8 * T), 46), (int(22.2 * T), int(12.1 * T), 30)):
        h = max(6, w // 3)
        _decal(r, px + 4, py, w - 10, h, (40, 50, 64), 0.007)
        _decal(r, px, py + 2, w, h - 4, (40, 50, 64), 0.007)
        _decal(r, px + 6, py + 2, w // 2 - 6, 1.5, (120, 140, 170), 0.009)
    # Briefing room: projector screen with the new crest, lectern, chairs, flags.
    _on_wall(r, 14.5 * T, 2 * T, 6.2, 1.7, 1.85, (30, 30, 34))
    _on_wall(r, 14.5 * T, 2 * T, 6.0, 1.5, 1.85, (226, 226, 230), out=0.01, emissive=True)
    _on_wall(r, 14.5 * T, 2 * T, 0.62, 0.62, 1.85, (20, 20, 24), out=0.02)
    _on_wall(r, 14.5 * T, 2 * T, 0.3, 0.3, 1.85, GUARD_RED, out=0.03)
    lx, lz = (14.2 * T + 19) * K, -(2 * T + 41) * K
    _box_at(r, 0.7, 1.1, 0.5, tex("crate", like=(90, 64, 44)), lx, 0.55, lz, cols={"top": (110, 80, 56)})
    seat = (58, 62, 70)
    for cx in range(11, 18):
        for ry in (5.55, 6.45):
            if cx == 12 and ry > 6:
                continue   # the recruit stands here
            x, z = (cx * T + 31) * K, -(ry * T + 10) * K
            _box_at(r, 0.06, 0.42, 0.06, (30, 32, 36), x, 0.21, z)
            _box_at(r, 0.56, 0.06, 0.5, seat, x, 0.45, z)
            _box_at(r, 0.56, 0.5, 0.06, seat, x, 0.72, z - 0.24)
    _flag3d(r, 10 * T + 20, 3 * T)
    _flag3d(r, 18 * T + 34, 3 * T)
    # Vasile's office: rug, flags, blinds, portrait, plant, chair.
    rx, ry, rw, rh = int(20.6 * T), int(4.2 * T), int(6.6 * T), int(3.2 * T)
    _decal(r, rx, ry, rw, rh, GOLD, 0.006)
    _decal(r, rx + 4, ry + 4, rw - 8, rh - 8, (92, 30, 32), 0.009)
    _decal(r, rx + 10, ry + 10, rw - 20, rh - 20, (120, 42, 40), 0.011)
    _decal(r, rx + 13, ry + 13, rw - 26, rh - 26, (92, 30, 32), 0.012)
    _flag3d(r, 20 * T + 20, 2 * T + 40)
    _flag3d(r, 27 * T + 10, 2 * T + 40)
    wx = 20.8 * T + 0.8 * T
    _on_wall(r, wx, 2 * T, 2.6, 1.4, 1.75, FRAME, d=0.05)
    _on_wall(r, wx, 2 * T, 2.44, 1.26, 1.75, (150, 142, 118), out=0.01, emissive=True)
    for i in range(8):
        _on_wall(r, wx, 2 * T, 2.44, 0.035, 1.17 + i * 0.16, (96, 88, 70), out=0.02)
    _portrait3d(r, 24.5 * T, 2 * T, 0.9, 1.15, 1.9)
    pcx, pcz = 21 * T * K, -7.4 * T * K
    _box_at(r, 0.42, 0.4, 0.42, tex("crate", like=(70, 50, 34)), pcx, 0.2, pcz)
    for a in range(7):
        _box_at(r, 0.26, 0.2, 0.26, (46, 96, 50) if a % 2 else (38, 80, 42),
                pcx + math.cos(a * 0.9) * 0.24, 0.5 + 0.12 * (a % 3), pcz + math.sin(a * 0.9) * 0.24)
    chx, chz = (23.7 * T + 25) * K, -(4.05 * T + 15) * K
    _box_at(r, 0.7, 0.1, 0.62, (40, 30, 26), chx, 0.5, chz)
    _box_at(r, 0.7, 0.7, 0.1, (40, 30, 26), chx, 0.9, chz - 0.3)
    _box_at(r, 0.08, 0.45, 0.08, (24, 22, 20), chx, 0.22, chz)
    # Armory: tools on the bench, ammo crates, the motor-pool window.
    wb = _paint.HQ_SOLIDS[3]
    for i in range(5):
        _box_at(r, 0.3, 0.05, 0.1, (150, 150, 156), (wb[0] + 14 + i * 22) * K, 1.03, -(wb[1] + 8) * K)
    # Supply end of the existing armory bench: no extra collision or interaction.
    _put(r, _mesh("hq_medical", medical_supplies),
         ((wb[0] + wb[2] - 16) * K, 1.0, -(wb[1] + wb[3] / 2) * K), yaw=180)
    lcd = prop("monitor_lcd")
    if lcd is not None:
        _put(r, lcd, ((wb[0] + 30) * K, 1.0, -(wb[1] + wb[3] / 2) * K), yaw=180)
    else:
        _box_at(r, 0.45, 0.3, 0.08, (50, 54, 58), (wb[0] + 30) * K, 1.15, -(wb[1] + wb[3] / 2) * K)
    for cx, cy in ((24.2, 12.6), (24.7, 12.65), (24.3, 12.2)):
        x, z = (cx * T + 15) * K, -(cy * T + 10) * K
        _box_at(r, 0.75, 0.42, 0.5, tex("crate", like=(70, 84, 50)), x, 0.21, z, cols={"top": (78, 92, 56)})
        _box_at(r, 0.25, 0.01, 0.08, (220, 200, 90), x - 0.15, 0.425, z)
    wz = -(10.8 * T + 0.7 * T) * K
    _box_at(r, 0.04, 1.1, 2.3, FRAME, 28 * S - 0.02, 1.6, wz)
    _box_at(r, 0.04, 0.96, 2.16, (24, 28, 34), 28 * S - 0.04, 1.6, wz)
    for k in (-0.5, 0.5):
        _box_at(r, 0.02, 0.5, 0.7, (12, 12, 14), 28 * S - 0.06, 1.4, wz + k)


def _quarter_props(r):
    from engine3d import tex
    # the burnt-out tram over its three tiles
    rc = _paint_tram_rect()
    cx, cz = to3(rc.centerx, rc.centery)[0], to3(rc.centerx, rc.centery)[2]
    w, d = rc.w * K, rc.h * K
    _box_at(r, w, 1.0, d, tex("steel", like=(88, 40, 32)), cx, 0.55, cz)
    _box_at(r, w * 0.98, 1.0, d * 0.96, tex("concrete", like=(122, 116, 100)), cx, 1.55, cz,
            cols={"top": (34, 28, 26)})
    _box_at(r, w * 1.0, 0.34, d * 1.0, (24, 20, 18), cx, 2.2, cz)
    for i in range(7):
        gx = cx - w / 2.0 + 0.5 + i * (w - 1.0) / 6.0
        _box_at(r, 0.6, 0.6, 0.03, GLASS, gx, 1.65, cz - d / 2.0 - 0.02)
    _box_at(r, 0.04, 1.2, 0.04, (22, 20, 20), cx, 3.0, cz)
    # the MAG van and the paper bales
    vx, vz = _px_box(r, _paint.Q_SOLIDS[0], 1.9, (58, 62, 66), "steel", top=(70, 72, 74), y0=0.25)
    _box_at(r, 1.2, 0.5, 1.0, (40, 44, 48), vx, 0.95, vz - 1.4)
    _box_at(r, 1.26, 0.7, 0.04, (30, 40, 50), vx, 1.8, vz - 1.52, emissive=False)
    for sx in (-0.62, 0.62):
        for dz in (-1.0, 0.9):
            _box_at(r, 0.16, 0.5, 0.5, (16, 16, 18), vx + sx, 0.25, vz + dz)
    bx, bz = _px_box(r, _paint.Q_SOLIDS[1], 0.8, (190, 186, 170), "concrete", top=(206, 202, 190))
    _box_at(r, 1.0, 0.7, 1.4, (200, 196, 180), bx, 1.15, bz + 0.1)
    # the blade sign
    sg = _paint.SIGN_RECT
    sx, _, sz = to3(sg.centerx, sg.centery)
    _box_at(r, sg.w * K, 0.7, 0.1, (28, 30, 34), sx, 3.3, sz)
    _box_at(r, sg.w * K - 0.2, 0.5, 0.04, (255, 90, 80), sx, 3.3, sz - 0.06, emissive=True)
    # works windows on the west face (x = 34 tiles)
    for row in (11, 14, 17):
        wx, _, wz = to3(34 * T - 0.04 / K, row * T + 32)
        _box_at(r, 0.04, 0.9, 1.0, LIT, wx, 1.7, wz, emissive=True)
        _box_at(r, 0.06, 0.06, 1.1, FRAME, wx, 1.2, wz)


def _paint_tram_rect():
    from missions.m5 import tram_wreck
    return tram_wreck.RECT


def _print_props(r):
    from engine3d import tex
    x, _, z = _tc(20, 4)
    _box_at(r, 1.5, 0.78, 0.8, tex("crate", like=(70, 52, 38)), x, 0.39, z, cols={"top": (96, 72, 50)})
    _box_at(r, 0.4, 0.04, 0.3, (220, 216, 200), x - 0.3, 0.8, z)


def _tunnel_props(r):
    from engine3d import tex
    _rails(r)
    # the river gate on the east wall, grille over a cyan wash
    x, _, z = to3(47 * T - 0.05 / K, 6 * T + T / 2.0)
    _box_at(r, 0.04, 2.3, S * 0.9, (60, 150, 170), x + 0.02, 1.15, z, emissive=True)
    for i in range(9):
        _box_at(r, 0.05, 2.3, 0.05, (24, 26, 28), x - 0.04, 1.15, z - S * 0.42 + i * S * 0.105)
    for y in (0.3, 1.2, 2.2):
        _box_at(r, 0.07, 0.07, S * 0.96, (30, 32, 34), x - 0.05, y, z)
    # a cable run along the north vault
    for row, c0, c1 in ((2, 10, 27), (4, 1, 13)):
        cx, _, cz = to3(((c0 + c1 + 1) / 2.0) * T, row * T + 6)
        _box_at(r, (c1 - c0 + 1) * S, 0.08, 0.08, tex("steel", like=(40, 44, 44)), cx, 2.5, cz)


def _static_lights():
    return _lights_for(STAGE_PRINTWORKS if _kind() == "print" else _stage_of_kind())


def _stage_of_kind():
    return {"hq": STAGE_HQ, "quarter": STAGE_QUARTER, "tunnel": STAGE_TUNNEL}.get(_kind(), STAGE_PRINTWORKS)


def _lights_for(stage):
    """The lamp rows of ``stage`` as dicts: sim pos, reach, colour, flicker
    kind, fixture family and the 3D head position."""
    key = (stage, id(_grid()))
    hit = _cache["lights"]
    if hit is None:
        hit = _cache["lights"] = {}
    if key in hit:
        return hit[key]
    out = []
    kind = _kind()
    for i, (px, py, rad, col, fk) in enumerate(_decor._STAGE_LIGHTS.get(stage, ())):
        fam, h, arm = "tube", 2.55, (0, 0)
        if fk.startswith("siren"):
            fam, h = "siren", 2.6
        elif kind == "quarter":
            if fk == "fire":
                fam, h = "fire", 1.8
            elif col == (255, 176, 92) or col == (220, 230, 255):
                fam, h = "post", 3.4
                arm = (0, 1) if py < 15 * T else (0, -1) if col != (220, 230, 255) else (0, 0)
            elif col == (255, 90, 80):
                fam, h = "sign", 3.3
            elif col == (255, 200, 130) and px < 34 * T:
                fam, h = "door", 2.5
            else:
                fam, h = "win", 1.7
                px = 34 * T - 14
        hx, hy, hz = to3(px + arm[0] * 0.9 / K, py + arm[1] * 0.9 / K, h)
        out.append({"x": px, "y": py, "reach": rad * K * 1.6, "col": col, "kind": fk, "fam": fam,
                    "h": h, "arm": arm, "head": (hx, hy, hz), "seed": i * 7})
    hit[key] = out
    return out


def _lamp_fixture(r, lamp):
    fam, col = lamp["fam"], lamp["col"]
    if fam in ("fire", "win", "sign"):
        return
    metal = (30, 31, 34)
    hx, hy, hz = lamp["head"]
    x, _, z = to3(lamp["x"], lamp["y"])
    if fam == "post":
        h = lamp["h"]
        _box_at(r, 0.12, h, 0.12, metal, x, h / 2.0, z)
        for i in range(1, 7):
            k = i / 6.0
            _box_at(r, 0.07, 0.07, 0.07, metal, x + (hx - x) * k, h + 0.02, z + (hz - z) * k)
        _box_at(r, 0.36, 0.1, 0.24, metal, hx, hy + 0.02, hz)
        _box_at(r, 0.28, 0.03, 0.18, col, hx, hy - 0.04, hz, emissive=True)
    elif fam == "door":
        _box_at(r, 0.3, 0.1, 0.24, metal, hx, hy + 0.05, hz)
        _box_at(r, 0.22, 0.04, 0.16, col, hx, hy - 0.01, hz, emissive=True)
    else:                                    # tube
        _box_at(r, 1.1, 0.08, 0.18, metal, hx, hy + 0.04, hz)
        _box_at(r, 0.96, 0.03, 0.1, col, hx, hy - 0.01, hz, emissive=True)


# ── walls ──────────────────────────────────────────────────────────────

def _kinds():
    """(col, row) -> wall kind, cached per map. The quarter's buildings are
    the connected C blobs that do not touch the map edge."""
    g = _grid()
    hit = _cache["kinds"]
    if hit is not None and hit[0] == id(g):
        return hit[1]
    mw, mh = _dims()
    kind = _kind()
    out = {}
    if kind != "quarter":
        name = "vault" if kind == "tunnel" else "wall"
        for row in range(mh):
            for col in range(mw):
                if g[row][col] == "C":
                    out[(col, row)] = name
    else:
        for row in range(10, 21):
            for col in range(34, 39):
                if g[row][col] == "C":
                    out[(col, row)] = "works"
        comp = 0
        for row in range(mh):
            for col in range(mw):
                if g[row][col] != "C" or (col, row) in out:
                    continue
                stack, cells, edge = [(col, row)], [], False
                out[(col, row)] = None
                while stack:
                    c, rr = stack.pop()
                    cells.append((c, rr))
                    edge = edge or c in (0, mw - 1) or rr in (0, mh - 1)
                    for dc, dr in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                        n = (c + dc, rr + dr)
                        if 0 <= n[0] < mw and 0 <= n[1] < mh and g[n[1]][n[0]] == "C" and n not in out:
                            out[n] = None
                            stack.append(n)
                name = "border" if edge else "b%d" % comp
                comp += 1
                for cell in cells:
                    out[cell] = name
    _cache["kinds"] = (id(g), out)
    return out


def _wall_kind(col, row):
    return _kinds().get((col, row))


def _height(kind):
    if kind.startswith("b") and kind[1:].isdigit():
        return 2.9 + 0.3 * _hash(int(kind[1:]), 5, 4)
    return {"border": 3.0, "works": 4.6, "wall": 3.0, "vault": 2.8}[kind]


def _wall_boxes():
    """Merged wall boxes (col, row, w, h, kind) in tiles."""
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


def _style_of(kind):
    if kind in _STYLE:
        return _STYLE[kind]
    return _BUILD[int(kind[1:]) % len(_BUILD)]


def _outer_wall_mesh(kind, sc, sr, sw, sh, hgt):
    """A quarter wall segment: textured body, the M1 shade bands, a cornice
    and (at full height) windows on the faces the camera sees."""
    full = _height(kind)
    cut = hgt < full - 0.01
    key = ("ow", kind, sc, sr, sw, sh, round(hgt, 3)) if not cut else ("owc", kind, sw, sh, round(hgt, 3))

    def build():
        from engine3d import Mesh, box, tex
        name, body, cap = _style_of(kind)
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
        if kind != "border":
            _windows(m, kind, sc, sr, sw, sh, hgt)
        return m
    return _mesh(key, build)


def _windows(m, kind, sc, sr, sw, sh, hgt):
    """Dark glass, a few lit behind curtains, some boarded, on the south,
    west and east faces that look onto open ground."""
    from engine3d import box
    w, d = sw * S, sh * S
    rows = [y for y in (1.15, 2.05, 2.95, 3.85) if y + 0.5 < hgt - 0.2]
    faces = [("s", c) for c in range(sc, sc + sw) if _glyph(c, sr + sh) != "C"]
    faces += [("w", rr) for rr in range(sr, sr + sh) if _glyph(sc - 1, rr) != "C"]
    faces += [("e", rr) for rr in range(sr, sr + sh) if _glyph(sc + sw, rr) != "C"]
    for face, i in faces:
        if face == "s":
            ax, az = (i + 0.5 - sc) * S - w / 2.0, -d / 2.0 - 0.025
        else:
            ax = (-w / 2.0 - 0.025) if face == "w" else (w / 2.0 + 0.025)
            az = -((i + 0.5 - sr) * S - d / 2.0)
        for k, y in enumerate(rows):
            pick = _hash(i * 7 + (0 if face == "s" else 31), k * 13 + sr + sc, 100)
            lit, boarded = pick < 12, 12 <= pick < 26
            col = LIT if lit else (6, 7, 9) if 26 <= pick < 36 else GLASS
            gw, gh = 0.62, 0.56
            if face == "s":
                m.add(box(gw, gh, 0.04, col, center=(ax, y, az), emissive=lit))
                m.add(box(gw + 0.12, 0.06, 0.07, FRAME, center=(ax, y - gh / 2.0 - 0.03, az)))
                if boarded:
                    m.add(box(gw + 0.05, 0.08, 0.06, (112, 84, 54), center=(ax, y, az - 0.01)))
            else:
                m.add(box(0.04, gh, gw, col, center=(ax, y, az), emissive=lit))
                m.add(box(0.07, 0.06, gw + 0.12, FRAME, center=(ax, y - gh / 2.0 - 0.03, az)))
                if boarded:
                    m.add(box(0.06, 0.08, gw + 0.05, (112, 84, 54), center=(ax, y, az)))


def _inner_wall_mesh(w, d, hgt, full):
    """Interior walls: plaster/brick/concrete over a dado, a dark cap."""
    cut = hgt < full - 0.01
    kind = _kind()
    key = ("iw", kind, round(w, 3), round(d, 3), round(hgt, 3))

    def build():
        from engine3d import Mesh, box, tex
        name, body, dado = _INNER[kind]
        m = Mesh()
        m.add(box(w, hgt, d, tex(name, like=body, tint=True), center=(0.0, hgt / 2.0, 0.0),
                  cols={"top": CUT_CAP if cut else CAP}))
        dh = min(1.15, hgt - 0.02)
        m.add(box(w + 0.02, dh, d + 0.02, tex("concrete", like=dado, tint=True),
                  center=(0.0, dh / 2.0, 0.0), skip=("top", "bottom")))
        if hgt > 1.25:
            m.add(box(w + 0.025, 0.05, d + 0.025, _shade(dado, 0.7), center=(0.0, 1.15, 0.0),
                      skip=("top", "bottom")))
        return m
    return _mesh(key, build)


def _rim_mesh(sc, sr, sw, sh, hgt, full):
    """The lit lip round a wall top on the edges that face open floor."""
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
        run([(c, _glyph(c, sr - 1) != "C") for c in range(sc, sc + sw)], "n")
        run([(c, _glyph(c, sr + sh) != "C") for c in range(sc, sc + sw)], "s")
        run([(rw, _glyph(sc - 1, rw) != "C") for rw in range(sr, sr + sh)], "w")
        run([(rw, _glyph(sc + sw, rw) != "C") for rw in range(sr, sr + sh)], "e")
        return m
    return _mesh(("rim", id(_grid()), sc, sr, sw, sh, round(hgt, 3)), build)


def _cut(zone, snap, c, row):
    k = _m1._cut_level(("m5", c, row), _m1._hides(zone, c * T, row * T, (c + 1) * T, (row + 1) * T), snap)
    return round(k * 8) / 8.0


def _draw_walls(r):
    """Wall boxes at full height, except the stretch between the camera
    and Biribel, which sinks to a stub (the M1 cutaway)."""
    zone = _m1._cut_zone()
    snap = _m1._cut_snap()
    quarter = _kind() == "quarter"
    for c0, r0, w, h, kind in _wall_boxes():
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
            if quarter:
                _put(r, _outer_wall_mesh(kind, sc, sr, sw, sh, hgt), (cx, 0.0, cz))
            else:
                _put(r, _inner_wall_mesh(sw * S, sh * S, hgt, full), (cx, 0.0, cz))
                _put(r, _rim_mesh(sc, sr, sw, sh, hgt, full), (cx, 0.0, cz))
            i = j + 1


def _doors():
    key = id(_grid())
    hit = _cache["doors"]
    if hit is not None and hit[0] == key:
        return hit[1]
    mw, mh = _dims()
    out = [(c, rr) for rr in range(mh) for c in range(mw) if _glyph(c, rr) == "D"]
    _cache["doors"] = (key, out)
    return out


def _kind_near(col, row):
    for dc, dr in ((-1, 0), (1, 0), (0, -1), (0, 1)):
        k = _wall_kind(col + dc, row + dr)
        if k is not None:
            return k
    return "wall" if _kind() != "quarter" else "works"


def _draw_openings(r):
    """A lintel over every door tile and a jamb on each side that meets a wall."""
    zone = _m1._cut_zone()
    snap = _m1._cut_snap()
    quarter = _kind() == "quarter"
    for col, row in _doors():
        kind = _kind_near(col, row)
        full = _height(kind)
        level = _cut(zone, snap, col, row)
        hgt = STUB_H + (full - STUB_H) * level
        x, _, z = _tc(col, row)
        sides = tuple(_glyph(col + dc, row + dr) == "C" for dc, dr in ((-1, 0), (1, 0), (0, -1), (0, 1)))
        top = min(DOOR_H, hgt)
        _put(r, _mesh(("jamb", sides, round(top, 2)), lambda s=sides, t=top: _jambs(s, t)), (x, 0.0, z))
        if hgt > DOOR_H + 0.05:
            _put(r, _lintel_mesh(kind, hgt, hgt >= full - 0.01, quarter), (x, 0.0, z))


def _jambs(sides, h):
    from engine3d import Mesh, box
    m = Mesh()
    for on, (dx, dz, w, d) in zip(sides, ((-1, 0, 0.1, 0.4), (1, 0, 0.1, 0.4), (0, 1, 0.4, 0.1), (0, -1, 0.4, 0.1))):
        if on:
            m.add(box(w, h, d, FRAME, center=(dx * (S / 2.0 - w / 2.0) if dx else 0.0, h / 2.0,
                                              dz * (S / 2.0 - d / 2.0) if dz else 0.0)))
    return m


def _lintel_mesh(kind, hgt, full, quarter):
    key = ("lintel", kind, round(hgt, 3), full)

    def build():
        from engine3d import box, tex
        if quarter:
            name, body, _cap = _style_of(kind)
        else:
            name, body, _d2 = _INNER[_kind()]
        return box(S, hgt - DOOR_H, S, tex(name, like=body, tint=True), center=(0.0, (hgt + DOOR_H) / 2.0, 0.0),
                   cols={"top": CAP if full else CUT_CAP})
    return _mesh(key, build)


# ── dynamic set ────────────────────────────────────────────────────────

def _draw_dynamic_set(r, flashes, tm):
    t = _now_s()
    kind = _kind()
    if kind == "quarter":
        rc = _paint_tram_rect()
        x, _, z = to3(rc.centerx, rc.centery)
        for i, dx in enumerate((-2.0, 0.0, 2.0)):
            _m1._fire(r, (x + dx, 2.4, z), tm, 11 + i, 0.55, glow=i == 1)
        sx, _, sz = to3(*_quarter.SEARCH_ORIGIN)
        _put(r, _mesh(("slamp",), _searchlight_mesh), (sx, 0.0, sz))
        if _stage() == STAGE_QUARTER and _quarter._S:
            _searchlight(r, tm, flashes)
            _civilian(r)
    for lamp in _lights_for(_cur_stage()):
        hx, hy, hz = lamp["head"]
        if lamp["fam"] == "siren":
            a = _flick(lamp["kind"], lamp["seed"], t)
            col = lamp["col"]
            _box_at(r, 0.3, 0.14, 0.3, td.mix((30, 30, 34), col, a), hx, hy, hz, emissive=a > 0.4)
            if a > 0.35:
                r.add_sprite((hx, hy, hz), _glow(col, 0.4, tm, a, 22), layer=_fx_layer())
        elif lamp["fam"] in ("post", "door", "sign", "win"):
            r.add_sprite((hx, hy, hz), _glow(lamp["col"], 0.28, tm, 0.9 * _flick(lamp["kind"], lamp["seed"], t), 18),
                         layer=_fx_layer())
    if kind == "tunnel":
        _water_surface(r, tm)
        _water_dynamic(r, tm)
    _beacon(r, t)


def _searchlight_mesh():
    from engine3d import Mesh, box
    m = Mesh()
    m.add(box(0.14, 3.0, 0.14, (30, 31, 34), center=(0.0, 1.5, 0.0)))
    m.add(box(0.5, 0.34, 0.5, (40, 42, 46), center=(0.0, 3.1, 0.0)))
    return m


def _searchlight(r, tm, flashes):
    ox, oy = _quarter.SEARCH_ORIGIN
    a = _quarter._search_angle()
    head = to3(ox, oy, 3.1)
    half = _quarter.SEARCH_HALF
    lit = bool(_quarter._S.get("lit"))
    k = 1.0 if lit else 0.55
    for off in (-half, -half / 2.0, 0.0, half / 2.0, half):
        tip = to3(ox + math.cos(a + off) * _quarter.SEARCH_LEN, oy + math.sin(a + off) * _quarter.SEARCH_LEN, 0.05)
        r.add_line3d(head, tip, _shade((255, 250, 220), 0.55 * k), 1, layer=4)
    end = to3(ox + math.cos(a) * _quarter.SEARCH_LEN * 0.55, oy + math.sin(a) * _quarter.SEARCH_LEN * 0.55, 0.0)
    r.add_sprite((end[0], 0.06, end[2]), _glow((255, 248, 214), 1.4, tm, 0.5 * k, 30), layer=_fx_layer())
    flashes.append({"pos": (end[0], 0.7, end[2]), "color": (255, 246, 214), "intensity": 0.6 * k, "range": 5.0})
    r.add_sprite(head, _glow((255, 250, 230), 0.32, tm, 1.0, 20), layer=_fx_layer())


def _civilian(r):
    from engine3d import POSES
    S_ = _quarter._S
    state = S_.get("civ")
    if state == "gone" or S_.get("civ_alpha", 255) < 60:
        return
    hum = td.armed("civilian", "pistol", **CIVILIAN)
    x, y = S_["civ_x"], _quarter.CIV_POS[1]
    if state == "held":
        at = to3(x, y)
        r.add_sprite((at[0], 0.02, at[2]), td.shadow(0.7, 0.5, 120), layer=0)
        r.add_humanoid(hum, dict(POSES["kneel"]), at, td.yaw_rad(0.0), rifle_on=False)
    else:
        _unarmed(r, hum, x, y, 0.0, "civ")


def _beacon(r, t):
    pos = _d._objective_world_pos()
    if pos is None:
        return
    x, _, z = to3(pos[0], pos[1])
    rad = 0.55 + 0.1 * math.sin(t * 3.0)
    col = (220, 190, 70)
    td.ring(r, x, z, rad, col, n=20, width=2)
    td.ring(r, x, z, rad * 0.6, td.mix(col, (0, 0, 0), 0.4), n=14, width=1)


# ── cast ───────────────────────────────────────────────────────────────

def _unarmed(r, hum, x, y, angle, key, tint=None):
    from engine3d import POSES, pose_run
    phase, moving = _m1._motion(key, x, y, angle)
    pose = pose_run(phase, lean=4) if moving else dict(POSES["stand"])
    r.add_humanoid(hum, pose, to3(x, y), td.yaw_rad(angle), rifle_on=False, tint=tint)


def _guard_hum(e):
    kind = getattr(_d._m5g(e), "kind", "") or ""
    rig = "shotgun" if "shotgun" in kind else "k9_smg" if kind in ("smg", "k9", "k9_smg") else "os12"
    spec = dict(_GUARD_KIT)
    if kind == "marksman":
        spec.update(jacket=(34, 30, 28), vest=(30, 28, 26))
    elif kind == "raider":
        spec.update(vest=(52, 54, 48))
    return td.armed("ipa", rig, **spec), rig


def _draw_cast(r, flashes, tm):
    _draw_corpses(r)
    for e in STATE.enemies:
        if getattr(e, "hp", 1) <= 0:
            continue
        hum, rig = _guard_hum(e)
        mode = "aim" if e.state in ("CHASE", "ATTACK") else "ready"
        burn = getattr(e, "burn", 0)
        tint = _m1.CHAR if burn else (e.body_tint, 0.55) if getattr(e, "body_tint", None) else None
        x, y = e.rect.centerx, e.rect.centery
        _m1._feet(r, x, y, _m1.RING_FOE.get(e.state, _m1.RING_FOE_CALM))
        _m1._body(r, hum, x, y, e.angle, rig, mode, ("e", e.uid), tint=tint)
        _m1._burning(r, x, y, min(1.0, burn / 40.0), tm, e.uid * 5, flashes)
    _draw_hq_npcs(r)
    _draw_maru(r, flashes, tm)
    _draw_player(r, flashes)


def _draw_player(r, flashes):
    p = STATE.player
    if p is None:
        return
    outfit = _outfits.gameplay_outfit(STATE) or _outfits.OUTFIT_KRAP
    ov = _outfits.biribel_3d(outfit)
    rig = p.rig_weapon_name()
    hum = td.armed("biribel", rig, **ov)
    if STATE.player_dead:
        _m1._draw_dead_player(r, hum)
        return
    x, y = p.rect.centerx, p.rect.centery
    _m1._feet(r, x, y, _m1.RING_YOU, rad=0.46)
    if getattr(STATE, "player_disarmed", False):
        _unarmed(r, hum, x, y, p.angle, "player")
        return
    melee = _m1._melee_progress()
    mode = "ready" if STATE.is_reloading else "aim"
    _m1._body(r, hum, x, y, p.angle, rig, mode, "player", flashes,
              STATE.muzzle_flash_timer > 0 and melee is None, melee=melee)


def _draw_maru(r, flashes, tm):
    m = getattr(STATE, "m5_maru", None)
    for name, (x, y), _col, facing, _weapon in friendly_npcs():
        hum = td.armed("maru", "pistol")
        flash = bool(m and m.get("muzzle", 0) > 0)
        hit = bool(m and m.get("hit_flash", 0) > 0)
        _m1._feet(r, x, y, (110, 170, 230), rad=0.4)
        _m1._body(r, hum, x, y, facing, "pistol", "aim" if flash else "ready", ("maru", name), flashes, flash,
                  tint=((255, 255, 255), 0.35) if hit else None)
    for mag in getattr(STATE, "m5_maru_mags", None) or ():
        if mag["age"] < mag.get("delay", 0):
            continue
        dur = max(1, mag.get("duration", 42))
        t = max(0.0, min(1.0, (mag["age"] - mag.get("delay", 0)) / dur))
        lift = math.sin(math.pi * t) * mag.get("arc_height", 76.0) * K
        x, _, z = to3(mag["x"], mag["y"])
        r.add_sprite((x, 0.02, z), td.shadow(0.3, 0.2, 110), layer=0)
        _put(r, _mesh(("mag",), lambda: _m1._pickup_mesh("mag")), (x, 0.3 + lift, z),
             yaw=math.degrees(mag.get("rot", 0.0)) % 360.0)


def _hq_look(n):
    who, ward = _d._HQ_LOOKS.get(n["name"], ("krap", {}))
    ov = {k: ward[k] for k in ("hair", "shirt", "skin", "bulk") if k in ward}
    if who == "civilian":
        ov.update(long_coat=None, jacket=ward.get("coat"), pants=ward.get("trousers"))
    if n.get("armband") and not n.get("vasile"):
        ov["armband"] = _outfits.GUARD_ARMBAND
    return td.armed(who, "pistol", **ov)


def _draw_hq_npcs(r):
    if _stage() != STAGE_HQ:
        return
    p = STATE.player
    ppos = (p.rect.centerx, p.rect.centery) if p else None
    for n in getattr(STATE, "m5_hq_npcs", None) or ():
        x, y = n["x"], n["y"]
        if n.get("prop"):
            lx, _, lz = to3(x, y)
            _locker(r, lx, lz)
            continue
        if n.get("vasile"):
            fx, _, fz = to3(x + 34, y - 8)
            _put(r, _mesh(("flag",), _flag_mesh), (fx, 0.95, fz))
        right = n.get("face_right", n["x"] % 2 < 1)
        angle = 0.0 if right else math.pi
        if ppos is not None and math.hypot(ppos[0] - x, ppos[1] - y) < _d._HQ_FACE_RADIUS:
            angle = math.atan2(ppos[1] - y, ppos[0] - x)
            n["face_right"] = ppos[0] >= x
        _unarmed(r, _hq_look(n), x, y, angle, ("hq", n["name"]))


def _flag_mesh():
    from engine3d import Mesh, box
    m = Mesh()
    m.add(box(0.04, 1.3, 0.04, (180, 170, 140), center=(0.0, 0.65, 0.0)))
    m.add(box(0.6, 0.2, 0.03, (20, 20, 24), center=(0.32, 1.15, 0.0)))
    m.add(box(0.6, 0.2, 0.03, (190, 30, 30), center=(0.32, 0.95, 0.0)))
    return m


def _draw_corpses(r):
    from engine3d import blend
    hum = td.armed("ipa", "os12", **_GUARD_KIT)
    for c in list(getattr(STATE, "corpses", ())):
        k = min(1.0, c.t / float(_m1.CORPSE_FALL))
        pose = blend("kneel", "dead_side", k) if k > 0.35 else blend("stand", "kneel", k / 0.35)
        at = to3(c.x, c.y)
        if k >= 1.0:
            r.add_sprite((at[0], 0.02, at[2]), td.blood_pool(min(1.0, (c.t - _m1.CORPSE_FALL) / 90.0)), layer=0)
        r.add_sprite((at[0], 0.02, at[2]), td.shadow(0.75, 0.55, 110), layer=0)
        r.add_humanoid(hum, pose, at, td.yaw_rad(c.angle) + 90.0 * c.fall_dir, rifle_on=False,
                       tint=_m1.CHAR if hasattr(c, "burn") else None)


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
    for b in STATE.bullets:
        head = to3(b["x"], b["y"], AIM_H)
        tail = to3(b.get("prev_x", b["x"] - b["dx"]), b.get("prev_y", b["y"] - b["dy"]), AIM_H)
        r.add_line3d(tail, head, (255, 220, 140), 2, layer=4)
        r.add_sprite(head, _glow(C_BULLET, 0.12, tm, 0.9, 10), layer=_fx_layer())
    td.dots(r, [(to3(p.x, p.y, 0.25 + 0.03 * getattr(p, "life", 0)), p.color, getattr(p, "size", 2))
                for p in STATE.particles], layer=_fx_layer())
    td.dots(r, [(to3(c.x, c.y, 0.03), (200, 160, 70), 2) for c in STATE.casings], layer=1)


# ── lights ─────────────────────────────────────────────────────────────

def _cur_stage():
    st = _stage()
    kind = _kind()
    if kind == "print":
        return STAGE_RAID if st == STAGE_RAID else STAGE_PRINTWORKS
    return _stage_of_kind()


def _flick(kind, seed, t):
    if kind == "bad":
        return 0.25 if int(t * 11 + seed) % 7 < 2 else 1.0
    if kind == "fire":
        return 0.8 + 0.2 * math.sin(t * 13 + seed) + 0.1 * math.sin(t * 29)
    if kind == "sirenA":
        return 0.12 + 0.88 * max(0.0, math.sin(t * 6.0))
    if kind == "sirenB":
        return 0.12 + 0.88 * max(0.0, -math.sin(t * 6.0))
    return 1.0


def _lamp_lights(r, v, flashes, tm):
    """Pools light the baked floor; the lamps nearest the camera focus plus
    the flashes are the eight per-frame lights. Returns the grade lights."""
    fx, fz = v.tgt[0], v.tgt[2]
    _cache["tgt"] = (fx, fz)
    t = _now_s()
    pools, near, grade = [], [], []
    wet = _kind() == "quarter"
    for lamp in _lights_for(_cur_stage()):
        k = _flick(lamp["kind"], lamp["seed"], t)
        head = lamp["head"]
        reach, color = lamp["reach"], lamp["col"]
        pools.append({"pos": head, "range": reach, "color": color, "intensity": 2.0 * k,
                      "hot": td.mix(color, (255, 250, 235), 0.5)})
        near.append(((head[0] - fx) ** 2 + (head[2] - fz) ** 2,
                     {"pos": head, "color": color, "intensity": 0.45 * k, "range": reach}))
        grade.append(("pool", (head[0], 0.0, head[2]), color, reach * 0.72, 0.5 * k))
        grade.append(("glow", head, color, 0.7 if lamp["fam"] == "tube" else 0.6, 0.55 * k))
        if wet and lamp["fam"] in ("post", "door"):
            grade.append(("reflect", (head[0], 0.0, head[2] - 0.4), color, 0.6, 0.34 * k))
    p = STATE.player
    if p is not None:
        pp = to3(p.rect.centerx, p.rect.centery, 1.7)
        flashes.append({"pos": pp, "color": (190, 205, 230), "intensity": 1.35, "range": 4.0})
        grade.append(("pool", (pp[0], 0.0, pp[2]), (170, 190, 225), 3.2, 0.42))
    near.sort(key=lambda e: e[0])
    lights = [e[1] for e in near[:max(0, 8 - len(flashes))]]
    r.set_pools(pools[:32])
    r.set_lights(flashes[:8] + lights, cap=8)
    return grade


# ── screen space ───────────────────────────────────────────────────────

def _at(v, x, y, h):
    p = v.screen_sim(x, y, h)
    return None if p is None else (int(p[0]), int(p[1]))


def _on_screen(pt):
    return pt is not None and -50 < pt[0] < WIDTH + 50 and -50 < pt[1] < HEIGHT + 50


def _tag(s, text, col, pt):
    img = font_terminal_small.render(text, True, col)
    tx, ty = pt[0] - img.get_width() // 2, pt[1] - img.get_height()
    s.blit(font_terminal_small.render(text, True, (0, 0, 0)), (tx + 1, ty + 1))
    s.blit(img, (tx, ty))
    return ty + img.get_height()


def _labels(s, v):
    """Names, Maru's health, floating texts and the inspect prompt, projected."""
    import pygame
    stage = _stage()
    if stage == STAGE_HQ:
        for n in getattr(STATE, "m5_hq_npcs", None) or ():
            if n.get("prop"):
                continue
            pt = _at(v, n["x"], n["y"], 2.2)
            if _on_screen(pt):
                _tag(s, n["name"], C_VASILE if n.get("vasile") else (170, 180, 195), pt)
    m = getattr(STATE, "m5_maru", None)
    for name, (x, y), color, _facing, _w in friendly_npcs():
        pt = _at(v, x, y, 2.2)
        if not _on_screen(pt):
            continue
        by = _tag(s, name, color, pt)
        if m and stage in (STAGE_RAID, STAGE_TUNNEL):
            bw = 34
            frac = max(0.0, min(1.0, m["hp"] / max(1, m["max_hp"])))
            bx = pt[0] - bw // 2
            pygame.draw.rect(s, (28, 28, 28), (bx, by + 2, bw, 4))
            pygame.draw.rect(s, (120, 220, 150) if frac > 0.35 else (220, 80, 70), (bx, by + 2, int(bw * frac), 4))
            if m.get("waiting"):
                from engine.text import T as _T
                w = font_terminal_small.render(_T("draw.waiting"), True, (220, 200, 120))
                s.blit(w, (pt[0] - w.get_width() // 2, by + 8))
    for ft in STATE.floating_texts:
        if len(ft) >= 6 and ft[5] == "pin":
            continue
        pt = _at(v, ft[0], ft[1], 1.8)
        if _on_screen(pt):
            img = font_terminal_small.render(ft[2], True, ft[3])
            s.blit(img, (pt[0] - img.get_width() // 2, pt[1]))
    if getattr(STATE, "m5_dialogue_active", False) or _d._m5_fpv.active() or stage == STAGE_DONE:
        return
    i = _decor.nearest_inspectable()
    if i is not None:
        x, y = _decor.INSPECTABLES[i][1]
        pt = _at(v, x, y, 0.9)
        if pt is not None:
            for img, pos in _decor._prompt_parts(i, int(x - pt[0]), int(y - pt[1]), s.get_size()):
                s.blit(img, pos)
