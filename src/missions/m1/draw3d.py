"""Mission 1 in 2.5D: the warehouse frame drawn in 3D over the 2D rules.

``draw.submit_frame`` hands the frame here while ``game.topdown3d`` is on.
The sim, AI, collision and every timer stay where they were; this module
only changes what the world looks like. Screen-space passes (HUD, radio,
reticle, hotwire panel, standoff letterbox, rain, scanlines, vignette, the
death tilt) are the 2D ones, and world-anchored labels (desk tags, door
prompts, floating texts, stealth meters) are projected through the frame's
``td.View``.

Set: the map glyphs are the source. ``C`` above the street row is a house
facade, below it a row of shipping containers; ``W`` is the warehouse block
wall. Walls are drawn per frame from packed meshes so the ones standing
between the camera and Biribel drop to a stub (the cutaway); the floor,
props and lamps are one static batch.

Any renderer error turns 2.5D off for the rest of the run
(``td.disable``) and the frame falls back to the 2D painter.
"""
import math

import pygame

from core.config import (C_TERMINAL, DOOR_INTERACT_RANGE, HEIGHT, TILE_SIZE, WIDTH,
                         draw_scanlines, font_prompt, font_terminal_small,
                         get_scaled_mouse)
from core.state import STATE
from engine.core import now_ms as _now_ms, now_s as _now_s
from engine.text import T as _T
from engine.render2d import Layer as _L, UiPassDraw as _UiPassDraw
from game import topdown3d as td
from game.topdown3d import K, to3
from missions.m1 import draw as _d
from missions.m1 import grade3d as _grade
from missions.m1 import stealth as _st
from missions.m1.map import MAP_W, MAP_H, M1_STREET_ROW, mission1_map

CAM = td.CAMS["MISSION1"]
AIM_H = 1.2                      # bullets fly at chest height
FACADE_H = 3.4
CONTAINER_H = 2.6
BLOCK_H = 2.8                    # warehouse W wall
STUB_H = 0.45                    # cut-away wall
CUT_CAP = (26, 27, 31)           # section colour on top of a cut wall
FENCE_H = 1.9
SHUTTER_H = 3.0
DOOR_H = 2.3
BAY_H = 3.0
CUT_BACK = 2.4                   # tiles south of Biribel a wall may hide him
CUT_SIDE = 3.0                   # tiles either side: wide enough that the cut reads as a room cutaway
CUT_STEP = 0.125                 # cut level change per frame: a wall sinks or rises in 8 frames
WALK_RAD_PER_M = 2.6
CORPSE_FALL = 30

NIGHT = dict(direction=(-0.30, 0.85, -0.42), ambient=0.30, diffuse=0.44, sky=0.08,
             tint=(0.80, 0.88, 1.05))
VOID = (8, 9, 12)
CONTAINER_COLS = ((122, 44, 36), (44, 66, 100), (112, 66, 38), (92, 94, 96))
IPA = (80, 60, 50)               # core.config.C_IPA_UNIFORM
MAG = (50, 55, 45)               # core.config.C_MAG_UNIFORM
CHAR = ((22, 18, 16), 0.45)      # tint on a burning or burnt body
RING_YOU = (75, 227, 122)
RING_FOE = {"ATTACK": (230, 56, 44), "CHASE": (230, 56, 44), "SEARCH": (236, 150, 48)}
RING_FOE_CALM = (150, 74, 60)

_FULL_H = {"container": CONTAINER_H, "facade": FACADE_H, "block": BLOCK_H}
_cache = {"walls": None, "packed": {}, "meshes": {}, "motion": {}, "view": None,
          "cut": {}, "cut_at": None}


# ── frame ──────────────────────────────────────────────────────────────

def view():
    """The last frame's camera (aim and labels use it), or None."""
    return _cache["view"]


def submit_frame(q, fcx, fcy):
    """Submit one Mission 1 frame in 2.5D. Draw order of the screen passes
    is the 2D painter's (ADR-017)."""
    fx, fy = fcx + WIDTH / 2.0, fcy + HEIGHT / 2.0
    v = td.View(CAM, fx, fy)
    _cache["view"] = v
    _tick_decals()
    q.submit(_UiPassDraw(lambda s: render_world(s, v), "m1.world3d"), _L.FLOOR, sort_key=0)
    q.submit(_UiPassDraw(lambda s: _labels(s, v), "m1.labels3d"), _L.FX_WORLD, sort_key=(9, 0))
    if STATE.truck_hotwiring:
        q.submit(_UiPassDraw(_d._draw_m1_hotwire, "m1.hotwire"), _L.FX_WORLD, sort_key=(10, 0))
    _overlay(q, v)
    _d._submit_m1_rain(q, fcy)
    if getattr(STATE, "_m1_standoff", None):
        q.submit(_UiPassDraw(lambda s: _d._draw_m1_standoff(
            s, fcx, fcy, anchor=lambda k: _at(v, k.rect.centerx, k.rect.centery, 2.6)),
            "m1.standoff"), _L.DEBUG, sort_key=1)
    else:
        q.submit(_UiPassDraw(lambda s: _d._draw_m1_hud(s, fcx, fcy), "m1.hud"), _L.UI, sort_key=0)
    if STATE.player_dead:
        from entities import death_anim
        q.submit(_UiPassDraw(death_anim.apply_camera_tilt, "m1.death_tilt"), _L.UI, sort_key=1)


def _tick_decals():
    """The per-frame timers the 2D ground pass ages (blood fade, breach
    markers): the 3D frame must age them the same or replays drift."""
    for marker in STATE.breach_markers[:]:
        marker[2] -= 1
        if marker[2] <= 0:
            STATE.breach_markers.remove(marker)
    for decal in STATE.blood_decals[:]:
        decal[2] -= 0.5
        if decal[2] <= 0:
            STATE.blood_decals.remove(decal)


def render_world(surface, v, actors=None, lit=None, film=None):
    """Draw the M1 set through view ``v`` onto ``surface``. ``actors`` is an
    optional callback(r, flashes, tm) that replaces the gameplay cast (the
    drop-off film uses it); ``lit`` caps the lamps to the ones near it.
    ``film`` (the escape cut) turns the wall cutaway off: walls stand at
    full height except the tiles in ``film["gone"]``, which are not drawn,
    and ``film["grade"]`` adds light tuples to the night grade."""
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
        first = _w.static_scene(r, ("m1_td3d", id(mission1_map)))
        ok = False
        try:
            if first:
                _build_set(r)
            ok = True
        finally:
            _w.static_end(r, ok)
        flashes = []
        _draw_walls(r, film)
        _draw_doors(r, film)
        if actors is not None:
            actors(r, flashes, tm)
        else:
            _draw_cast(r, flashes, tm)
            _draw_fx(r, flashes, tm)
        dyn = _dyn_lights(flashes, tm)
        _lamp_lights(r, v, flashes, tm, actors)
        r.flush(buf)
    except Exception:
        import traceback
        traceback.print_exc()
        td.disable()                  # next frame is the 2D painter
        _cache["view"] = None
        return False
    finally:
        r.light, r.fog, r.fog_start, r.fog_end, r.light_cap = saved
    _fx.present_crisp(buf, surface)
    _grade.apply(surface, v, _night_lights() + dyn + list((film or {}).get("grade", ())))
    return True


# ── set ────────────────────────────────────────────────────────────────

def _glyph(col, row):
    if 0 <= row < MAP_H and 0 <= col < len(mission1_map[row]):
        return mission1_map[row][col]
    return ""


def _wall_kind(col, row):
    ch = _glyph(col, row)
    if ch == "W":
        return "block"
    if ch == "C":
        return "facade" if row <= M1_STREET_ROW else "container"
    return None


def _wall_boxes():
    """Merged wall boxes (kind, col, row, w, h, variant) in tiles, from the
    glyphs: horizontal runs (containers cut at 4 tiles, a 20 ft box), then
    identical runs stacked down are merged."""
    if _cache["walls"] is not None:
        return _cache["walls"]
    runs = {}
    for row in range(MAP_H):
        col = 0
        while col < MAP_W:
            kind = _wall_kind(col, row)
            if kind is None:
                col += 1
                continue
            end = col
            while end + 1 < MAP_W and _wall_kind(end + 1, row) == kind:
                end += 1
            step = 4 if kind == "container" else MAP_W
            for c0 in range(col, end + 1, step):
                runs[(row, c0)] = [kind, c0, row, min(step, end + 1 - c0), 1]
            col = end + 1
    out = []
    for row in range(MAP_H):
        for key in sorted(k for k in runs if k[0] == row):
            box = runs.pop(key, None)
            if box is None:
                continue
            kind, c0, r0, w, h = box
            while True:
                below = runs.get((r0 + h, c0))
                if below is None or below[0] != kind or below[3] != w:
                    break
                runs.pop((r0 + h, c0))
                h += 1
            out.append((kind, c0, r0, w, h, _d._m1_hash(c0, r0, 4)))
    _cache["walls"] = out
    return out


def _wall_mesh(kind, w, d, hgt, var):
    key = ("wall", kind, round(w, 3), round(d, 3), hgt, var)
    m = _cache["meshes"].get(key)
    if m is not None:
        return m
    from engine3d import Mesh, box, tex
    m = Mesh()
    cut = hgt < _FULL_H[kind] - 0.01
    if kind == "container":
        col = CONTAINER_COLS[var]
        side = tex("metal_rib", like=col)
        cap = CUT_CAP if cut else td.mix(col, (0, 0, 0), 0.25)
        m.add(box(w, hgt, d, side, center=(0.0, hgt / 2.0, 0.0), cols={"top": cap}, seg=3.2))
        if hgt > STUB_H:
            # corner castings and the door rods on the short ends
            for sx in (-1, 1):
                m.add(box(0.12, hgt, 0.12, td.mix(col, (0, 0, 0), 0.4),
                          center=(sx * (w / 2.0 - 0.05), hgt / 2.0, -d / 2.0 + 0.05)))
    elif kind == "facade":
        brick = tex("brick", like=(92, 62, 50))
        m.add(box(w, hgt, d, brick, center=(0.0, hgt / 2.0, 0.0),
                  cols={"top": CUT_CAP if cut else (58, 54, 52)}, seg=3.2))
        if not cut:
            m.add(box(w + 0.06, 0.16, d + 0.06, (64, 60, 58), center=(0.0, hgt - 0.08, 0.0)))
    else:
        block = tex("concrete", like=(96, 92, 86))
        m.add(box(w, hgt, d, block, center=(0.0, hgt / 2.0, 0.0),
                  cols={"top": CUT_CAP if cut else (70, 68, 64)}, seg=3.2))
    _wall_shade(m, kind, w, d, hgt, var, cut)
    _cache["meshes"][key] = m
    return m


# Wall volume: darker grime bands at the foot, a lit band under the roof
# edge. (height from, height to, brightness) - skins a hair proud of the wall.
WALL_SHADE = ((0.0, 0.32, 0.6), (0.32, 0.8, 0.8))
WALL_LIT = (0.28, 1.14)


def _wall_shade(m, kind, w, d, hgt, var, cut):
    from engine3d import box, tex
    if kind == "container":
        name, like = "metal_rib", CONTAINER_COLS[var]
    elif kind == "facade":
        name, like = "brick", (92, 62, 50)
    else:
        name, like = "concrete", (96, 92, 86)
    for y0, y1, k in WALL_SHADE:
        y1 = min(y1, hgt - 0.02)
        if y1 > y0:
            col = tex(name, like=tuple(int(c * k) for c in like))
            m.add(box(w + 0.02, y1 - y0, d + 0.02, col, center=(0.0, (y0 + y1) / 2.0, 0.0),
                      skip=("top", "bottom")))
    if not cut and kind != "facade":
        band, k = WALL_LIT
        col = tex(name, like=tuple(min(255, int(c * k)) for c in like))
        m.add(box(w + 0.015, band, d + 0.015, col, center=(0.0, hgt - band / 2.0 - 0.02, 0.0),
                  skip=("top", "bottom")))


def _facade_windows(r, c0, r0, w):
    """Lit and dark windows on a facade run's south face (static)."""
    from engine3d import box
    from cutscenes import m6world3d as _w
    s = TILE_SIZE * K
    for col in range(c0, c0 + w):
        if not 0 < col < MAP_W - 1 or _d._m1_hash(col, r0, 3) == 0:
            continue
        lit = _d._m1_hash(col + 5, r0, 7) == 0
        x, _, z = to3(col * TILE_SIZE + TILE_SIZE / 2.0, (r0 + 1) * TILE_SIZE)
        glass = (150, 118, 66) if lit else (26, 30, 38)
        _w.add(r, box(0.62, 0.78, 0.04, glass, center=(x, 1.9, z - 0.02), emissive=lit))
        _w.add(r, box(0.74, 0.07, 0.10, (52, 54, 56), center=(x, 1.48, z - 0.04)))
        if s and lit:
            continue


def _bands():
    """Floor bands (y0, y1, colour) in sim px, north to south."""
    T = TILE_SIZE
    pave_n, road, pave_s, yard = _d._M1_PAVE_N, _d._M1_ROAD, _d._M1_PAVE_S, _d._M1_YARD
    return ((0, pave_n[1], (56, 56, 55)), (road[0], road[1], (30, 31, 34)),
            (pave_s[0], pave_s[1], (55, 55, 53)), (yard[0], (M1_STREET_ROW + 1) * T, (46, 46, 44)),
            ((M1_STREET_ROW + 1) * T, 21 * T, (41, 40, 37)), (21 * T, 30 * T, (50, 47, 43)),
            (30 * T, MAP_H * T, (32, 32, 34)))


def _floor_col(y):
    for y0, y1, col in _bands():
        if y0 <= y < y1:
            return col
    return (40, 40, 40)


def _floor_tex(col, k=1.0):
    """The paving texture over ``col`` scaled by ``k`` (shadows, stains keep
    the concrete grain instead of a flat patch)."""
    from engine3d import tex
    return tex("pavement", like=tuple(max(0, min(255, int(c * k))) for c in col), tint=True)


def _tile_col(col, row, base):
    """``base`` with a per-tile shift of up to ~4% brightness and a faint
    warm/cool lean, fixed by the tile, so the paving is not one flat sheet."""
    k = 1.0 + (_d._m1_hash(col, row, 9) - 4) * 0.011
    lean = (_d._m1_hash(col + 3, row + 11, 5) - 2) * 0.006
    return (base[0] * k * (1.0 + lean), base[1] * k, base[2] * k * (1.0 - lean))


def _build_set(r):
    """Static batch: floor bands, street furniture, props, lamps, desks."""
    from cutscenes import m6world3d as _w
    from engine3d import box, quad_xz
    T = TILE_SIZE
    W = MAP_W * T * K

    # one quad per tile and band slice, each with its own slight tint
    for y0, y1, base in _bands():
        for row in range(y0 // T, (y1 - 1) // T + 1):
            ya, yb = max(y0, row * T), min(y1, (row + 1) * T)
            for col in range(MAP_W):
                _w.add(r, quad_xz(col * T * K, -yb * K, (col + 1) * T * K, -ya * K, 0.0,
                                  _floor_tex(_tile_col(col, row, base)), layer=0))
    _ground_decals(r)
    _contact_shadows(r)
    road = _d._M1_ROAD
    # curbs, lane dashes, puddles
    for y, face in ((road[0], 1), (road[1], -1)):
        _w.add(r, box(W, 0.12, 0.16, (88, 88, 84), center=(W / 2.0, 0.06, -y * K)))
    for x in range(T, MAP_W * T - T, 96):
        _w.add(r, quad_xz(x * K, -_d._M1_LANE_Y * K - 0.05, (x + 44) * K, -_d._M1_LANE_Y * K + 0.05,
                          0.008, (150, 146, 120), layer=1))
    for px, py, pw, ph in _d._M1_PUDDLES:
        _w.add(r, quad_xz(px * K, -(py + ph) * K, (px + pw) * K, -py * K, 0.006, (44, 50, 62), layer=1))
    # warehouse expansion joints
    for gx in range(0, MAP_W * T + 1, 128):
        _w.add(r, quad_xz(gx * K - 0.02, -30 * T * K, gx * K + 0.02, -21 * T * K, 0.004,
                          (38, 36, 32), layer=1))
    # bay chevrons
    for i in range(6):
        col = (170, 140, 40) if i % 2 == 0 else (25, 25, 25)
        x0 = (11 + i) * T
        _w.add(r, quad_xz(x0 * K, -(30 * T + 26) * K, (x0 + T) * K, -(30 * T + 8) * K, 0.006,
                          col, layer=1))
    for kind, c0, r0, w, h, var in _wall_boxes():
        if kind == "facade":
            _facade_windows(r, c0, r0, w)
    for row in range(MAP_H):
        for col in range(MAP_W):
            _glyph_prop(r, col, row, _glyph(col, row))
    for kind, ptx, pty, arg in _d._M1_DRESSING_PROPS:
        if not _d._m1_prop_overlaps_solid(kind, ptx, pty, arg):
            _dressing(r, kind, ptx * T + T / 2.0, pty * T + T / 2.0, arg)
    for desk in STATE.desks:
        _desk(r, desk["x"], desk["y"])
    for tx, ty, _rad, col, key in _d._M1_LAMPS:
        _lamp_fixture(r, key, tx * T + T / 2.0, ty * T + T / 2.0, col)
    # oil stain by the miniboss, papers by the desks, tire tracks to the exfil
    ox, oy = 10 * T + 32, 27 * T + 40
    _w.add(r, quad_xz((ox - 34) * K, -(oy + 14) * K, (ox + 34) * K, -(oy - 14) * K, 0.005,
                      (24, 23, 22), layer=1))
    for ptx, pty in ((12, 22), (19, 23), (7, 27)):
        px, py = ptx * T + 20, pty * T + 44
        _w.add(r, quad_xz(px * K, -(py + 10) * K, (px + 14) * K, -py * K, 0.007,
                          (205, 198, 180), layer=1))


def _wobble(col, row, n=9):
    return [0.72 + 0.07 * _d._m1_hash(col + i * 7, row * 3 + i, 5) for i in range(n)]


def _ground_decals(r):
    """Scattered by tile hash: dirt by the walls, oil by the curbs, wet
    puddles outdoors, hairline cracks anywhere."""
    from cutscenes import m6world3d as _w
    from engine3d import disc_xz, quad_xz
    T = TILE_SIZE
    for row in range(MAP_H):
        for col in range(MAP_W):
            if _glyph(col, row) != ".":
                continue
            h = _d._m1_hash(col * 3 + 1, row * 5 + 2, 23)
            ox = (_d._m1_hash(col, row * 7, 9) - 4) * 0.12
            oz = (_d._m1_hash(col * 5, row, 9) - 4) * 0.1
            x, _, z = to3(col * T + T / 2.0, row * T + T / 2.0)
            x, z = x + ox, z + oz
            fc = _tile_col(col, row, _floor_col(row * T + T / 2.0))
            walled = any(_wall_kind(col + dc, row + dr) for dc, dr in ((1, 0), (-1, 0), (0, 1), (0, -1)))
            outdoor = row <= M1_STREET_ROW or row >= 30
            curb = row in (2, 6)
            if walled and h < 8:
                rad = 0.4 + 0.05 * (h % 4)
                dirt = td.mix(fc, (74, 60, 42), 0.4)
                _w.add(r, disc_xz(x, z, rad, 0.004, _floor_tex(dirt, 0.92), n=9,
                                  wobble=_wobble(col, row)))
            elif curb and h < 6:
                _w.add(r, disc_xz(x, z, 0.42, 0.004, _floor_tex(fc, 0.62), n=9, wobble=_wobble(col, row)))
                _w.add(r, disc_xz(x + 0.06, z, 0.22, 0.005, (16, 15, 19), n=7, layer=2,
                                  wobble=_wobble(row, col, 7)))
            elif outdoor and h in (8, 9, 10):
                rad = 0.35 + 0.08 * (h - 8)
                _w.add(r, disc_xz(x, z, rad, 0.005, (34, 40, 52), n=9, wobble=_wobble(col, row)))
                _w.add(r, disc_xz(x - rad * 0.2, z + rad * 0.15, rad * 0.4, 0.006, (48, 56, 70),
                                  n=7, layer=2))
            elif h in (11, 12, 13):
                ang = _d._m1_hash(col, row, 8) * math.pi / 8.0
                cx, cz = x, z
                for i in range(4):
                    ang += (_d._m1_hash(col + i, row - i, 5) - 2) * 0.35
                    nx, nz = cx + math.cos(ang) * 0.18, cz + math.sin(ang) * 0.18
                    _w.add(r, quad_xz(min(cx, nx) - 0.012, min(cz, nz) - 0.012,
                                      max(cx, nx) + 0.012, max(cz, nz) + 0.012, 0.004,
                                      _floor_tex(fc, 0.6), layer=1))
                    cx, cz = nx, nz


AO_STEPS = (0.55, 0.72, 0.87)       # floor darkening from the wall base outwards
AO_STEP_PX = 7                      # sim px per step: the band is ~0.5 m deep


def _ao_rect(r, x0, y0, x1, y1, steps=AO_STEPS, step=AO_STEP_PX):
    """Contact shadow bands round a footprint (sim px), darkest at its foot."""
    from cutscenes import m6world3d as _w
    from engine3d import quad_xz
    for i, k in enumerate(steps):
        a, b = i * step, (i + 1) * step
        for ya, yb, xa, xb in ((y1 + a, y1 + b, x0 - b, x1 + b), (y0 - b, y0 - a, x0 - b, x1 + b),
                               (y0 - a, y1 + a, x0 - b, x0 - a), (y0 - a, y1 + a, x1 + a, x1 + b)):
            col = _floor_col((ya + yb) / 2.0)
            _w.add(r, quad_xz(xa * K, -yb * K, xb * K, -ya * K, 0.003, _floor_tex(col, k), layer=1))


def _shadow_at(r, x, z, hw, hd, k=0.5):
    """A two-step drop shadow under a static prop (world metres)."""
    from cutscenes import m6world3d as _w
    from engine3d import quad_xz
    col = _floor_col(-z / K)
    for grow, kk in ((0.18, (1.0 + k) / 2.0), (0.0, k)):
        _w.add(r, quad_xz(x - hw - grow, z - hd - grow, x + hw + grow, z + hd + grow, 0.0035 + grow * 0.001,
                          _floor_tex(col, kk), layer=1))


def _contact_shadows(r):
    """Ambient occlusion where walls, fences and shutters meet the floor, and
    drop shadows under the parked cars, barrels, crates and desks."""
    T = TILE_SIZE
    for kind, c0, r0, w, h, var in _wall_boxes():
        _ao_rect(r, c0 * T, r0 * T, (c0 + w) * T, (r0 + h) * T)
    for row in range(MAP_H):
        for col in range(MAP_W):
            ch = _glyph(col, row)
            if ch == "f":
                cy = row * T + T / 2.0
                _ao_rect(r, col * T, cy - 1, (col + 1) * T, cy + 1, (0.68, 0.84), 5)
            elif ch in ("S", "T") and _glyph(col - 1, row) != ch and _glyph(col, row - 1) != ch:
                w, h = _d._m1_run_size(col, row, ch)
                cx, _, cz = to3(col * T + w * T / 2.0, row * T + h * T / 2.0)
                if ch == "S":
                    _ao_rect(r, col * T, row * T + T // 4, (col + w) * T, row * T + 3 * T // 4)
                elif (w, h) == (4, 1):
                    _shadow_at(r, cx, cz, 2.0, 0.85, 0.45)
                else:
                    _shadow_at(r, cx, cz, 2.2, 0.95, 0.42)
            elif ch == "F":
                x, _, z = to3(col * T + T / 2.0, row * T + T / 2.0)
                _shadow_at(r, x, z, 0.36, 0.36, 0.55)
    for kind, ptx, pty, arg in _d._M1_DRESSING_PROPS:
        if not _d._m1_prop_overlaps_solid(kind, ptx, pty, arg):
            x, _, z = to3(ptx * T + T / 2.0, pty * T + T / 2.0)
            _shadow_at(r, x + 0.25, z, 0.75, 0.6, 0.55)
    for desk in STATE.desks:
        x, _, z = to3(desk["x"], desk["y"])
        _shadow_at(r, x, z, 0.7, 0.4, 0.6)


def _glyph_prop(r, col, row, ch):
    from cutscenes import m6world3d as _w
    from engine3d import box, tex
    T = TILE_SIZE
    x, _, z = to3(col * T + T / 2.0, row * T + T / 2.0)
    s = T * K
    if ch == "f":
        post = (36, 38, 40)
        _w.add(r, box(0.08, FENCE_H, 0.08, post, center=(x - s / 2.0 + 0.04, FENCE_H / 2.0, z)))
        _w.add(r, box(s, 0.05, 0.05, post, center=(x, FENCE_H - 0.03, z)))
        _w.add(r, box(s, FENCE_H - 0.1, 0.02, tex("metal_rib", like=(54, 58, 62)),
                      center=(x, (FENCE_H - 0.1) / 2.0, z)))
    elif ch == "r":
        for i in range(4):
            dx = (_d._m1_hash(col, row + i, 9) - 4) * 0.08
            dz = (_d._m1_hash(col + i, row, 9) - 4) * 0.08
            hh = 0.08 + 0.05 * (i % 2)
            _w.add(r, box(0.26, hh, 0.18, (78, 70, 62), center=(x + dx, hh / 2.0, z + dz)))
    elif ch == "F":
        _w.add(r, _barrel(x, z, (70, 52, 40)))
    elif ch == "L":
        _lamp_fixture(r, "sl_glyph", col * T + T / 2.0, row * T + T / 2.0, (190, 210, 255))
    elif ch in ("S", "T") and _glyph(col - 1, row) != ch and _glyph(col, row - 1) != ch:
        w, h = _d._m1_run_size(col, row, ch)
        cx, _, cz = to3(col * T + w * T / 2.0, row * T + h * T / 2.0)
        if ch == "S":
            _w.add(r, box(w * s, SHUTTER_H, s * 0.5, tex("metal_rib", like=(96, 98, 100)),
                          center=(cx, SHUTTER_H / 2.0, cz), cols={"top": (60, 62, 64)}))
            _w.add(r, box(w * s + 0.2, 0.4, s * 0.6, (52, 54, 56), center=(cx, SHUTTER_H + 0.2, cz)))
        elif (w, h) == (4, 1):
            _w.add(r, _at_mesh(_truck(), cx, cz))
        else:
            _w.add(r, _at_mesh(_mesh("sedan", lambda: _sedan((110, 72, 50))), cx, cz, 180.0))


def _barrel(x, z, col, h=0.9, rad=0.3):
    from engine3d import Mesh, prism, m_mul, rot_x
    prof = [(math.cos(a) * rad, math.sin(a) * rad) for a in
            [2 * math.pi * i / 8 for i in range(8)]]
    m = prism(prof, h, col, z0=0.0, cols={"back": td.mix(col, (0, 0, 0), 0.4)})
    out = Mesh()
    out.add(m, m=rot_x(-90.0), t=(x, 0.0, z))
    return out


GLASS = (40, 52, 64)
CHROME = (118, 120, 120)
TYRE = (18, 18, 20)
TRUCK_SCALE = 0.62               # truck_m7 is a 6.1 m army truck; the street lane is narrower


def _at_mesh(m, x, z, yaw=0.0):
    from engine3d import Mesh, rot_y
    return Mesh().add(m, m=rot_y(yaw), t=(x, 0.0, z))


def _wheels(m, xs, half_w, rad=0.32, depth=0.22):
    """Octagonal tyres with a hub, flush with the body sides."""
    from engine3d import prism
    ring = [(math.cos(a) * rad, math.sin(a) * rad) for a in
            [math.pi / 8 + i * math.pi / 4 for i in range(8)]]
    hub = [(x * 0.5, y * 0.5) for x, y in ring]
    for wx in xs:
        for side in (-1, 1):
            z0 = side * half_w - (depth if side > 0 else 0.0) + side * 0.03
            m.add(prism([(x + wx, y + rad) for x, y in ring], depth, TYRE, z0=z0))
            hz = z0 + (depth if side > 0 else 0.0) + side * 0.004 - (0.01 if side > 0 else 0.0)
            m.add(prism([(x + wx, y + rad) for x, y in hub], 0.01, (70, 72, 74), z0=hz))


def _lamps(m, front_x, back_x, y, half_w, head=(232, 216, 160), tail=(150, 28, 24)):
    from engine3d import box
    for side in (-1, 1):
        m.add(box(0.04, 0.12, 0.26, head, center=(front_x, y, side * (half_w - 0.24)), emissive=True))
        m.add(box(0.04, 0.12, 0.2, tail, center=(back_x, y + 0.04, side * (half_w - 0.2)),
                  emissive=True))
    m.add(box(0.03, 0.1, 0.36, (196, 196, 180), center=(back_x, y - 0.14, 0.0)))   # plate


def _car_finish(m, col, W, cw, wheel_xs, screen, roof, sill):
    """Shared car detail: dark wheel wells round the tyres, a grime sill,
    a few rust flecks, a metallic glint on the roof and two streaks of
    reflection across the windscreen. ``screen`` is the windscreen edge
    (two profile points), ``roof`` (x0, x1, y) the roof panel, ``sill``
    (x0, x1, y) the lower body line."""
    from engine3d import Mesh, box, rot_z
    well = (12, 12, 14)
    grime = td.mix(col, (26, 22, 18), 0.55)
    for side in (-1, 1):
        zs = side * (W / 2.0 + 0.004)
        for wx in wheel_xs:
            m.add(box(0.86, 0.44, 0.012, well, center=(wx, 0.5, zs)))
        m.add(box(sill[1] - sill[0], 0.1, 0.012, grime, center=((sill[0] + sill[1]) / 2.0, 0.37, zs)))
        for i in range(3):
            fx = sill[0] + (sill[1] - sill[0]) * (0.2 + 0.3 * i) + 0.1 * side
            m.add(box(0.07, 0.05, 0.014, (78, 46, 30), center=(fx, 0.46 + 0.05 * (i % 2), zs)))
    x0, x1, y = roof
    m.add(box((x1 - x0) * 0.7, 0.012, cw * 0.18, td.mix(col, (255, 255, 255), 0.42),
              center=(x0 + (x1 - x0) * 0.45, y + 0.007, -cw * 0.18)))
    (ax, ay), (bx, by) = screen
    ang = math.degrees(math.atan2(by - ay, bx - ax))
    ln = math.hypot(bx - ax, by - ay) * 0.8
    nx, ny = -(by - ay), (bx - ax)
    nl = math.hypot(nx, ny) or 1.0
    mx, my = (ax + bx) / 2.0 - nx / nl * 0.012, (ay + by) / 2.0 - ny / nl * 0.012
    if my < (ay + by) / 2.0:                       # keep the streak on the outside of the glass
        mx, my = (ax + bx) / 2.0 + nx / nl * 0.012, (ay + by) / 2.0 + ny / nl * 0.012
    for zc, wd in ((-cw * 0.22, 0.16), (cw * 0.12, 0.06)):
        g = Mesh().add(box(ln, 0.012, wd, (128, 146, 162)), m=rot_z(ang), t=(mx, my, zc))
        m.add(g)


def _sedan(col):
    """Boxy 70s saloon, 4.2 m, nose +x: a sloped body, a narrower glass
    cabin, chrome bumpers and octagon tyres."""
    from engine3d import Mesh, box, prism
    L, W = 4.2, 1.7
    m = Mesh()
    top = td.mix(col, (255, 255, 255), 0.14)
    side = td.mix(col, (0, 0, 0), 0.18)
    body = [(-2.1, 0.30), (2.1, 0.30), (2.12, 0.60), (2.02, 0.80), (0.95, 0.86),
            (-1.45, 0.86), (-2.06, 0.80), (-2.12, 0.60)]
    m.add(prism(body, W, col, z0=-W / 2.0, cols={3: top, 4: top, 5: top, "front": side, "back": side}))
    cw = W * 0.88
    cabin = [(-1.3, 0.86), (0.9, 0.86), (0.32, 1.36), (-0.98, 1.36)]
    m.add(prism(cabin, cw, td.mix(col, (0, 0, 0), 0.1), z0=-cw / 2.0,
                cols={1: GLASS, 3: GLASS, "front": GLASS, "back": GLASS, 2: top}))
    _car_finish(m, col, W, cw, (-1.3, 1.3), ((0.9, 0.86), (0.32, 1.36)), (-0.98, 0.32, 1.36),
                (-1.45, 0.95, 0.86))
    for side in (-1, 1):                       # door pillars over the side glass
        for px, w in ((-0.3, 0.1), (-1.0, 0.14), (0.55, 0.08)):
            m.add(box(w, 0.48, 0.02, td.mix(col, (0, 0, 0), 0.15),
                      center=(px, 1.11, side * (cw / 2.0 + 0.005))))
        m.add(box(3.6, 0.03, 0.02, CHROME, center=(0.0, 0.72, side * (W / 2.0 + 0.005))))
    for bx in (-2.16, 2.16):
        m.add(box(0.1, 0.12, W + 0.04, CHROME, center=(bx, 0.42, 0.0)))
    m.add(box(0.04, 0.16, 0.7, (26, 26, 28), center=(2.13, 0.62, 0.0)))           # grille
    _wheels(m, (-1.3, 1.3), W / 2.0)
    _lamps(m, 2.14, -2.14, 0.64, W / 2.0)
    return m


def _van(col):
    """Panel van, 3.6 m, nose +x: one sloped shell with a cab window band."""
    from engine3d import Mesh, box, prism
    L, W = 3.6, 1.62
    m = Mesh()
    top = td.mix(col, (255, 255, 255), 0.16)
    side = td.mix(col, (0, 0, 0), 0.18)
    shell = [(-1.8, 0.32), (1.8, 0.32), (1.86, 0.76), (1.6, 1.04), (1.02, 1.86), (-1.78, 1.92)]
    m.add(prism(shell, W, col, z0=-W / 2.0, cols={2: top, 3: GLASS, 4: top, "front": side, "back": side}))
    _car_finish(m, col, W, W, (-1.15, 1.2), ((1.6, 1.04), (1.02, 1.86)), (-1.7, 0.9, 1.91),
                (-1.7, 1.5, 0.4))
    for side in (-1, 1):
        zs = side * (W / 2.0 + 0.005)
        m.add(box(0.62, 0.4, 0.02, GLASS, center=(0.78, 1.36, zs)))               # cab window
        m.add(box(0.03, 1.3, 0.02, td.mix(col, (0, 0, 0), 0.3), center=(0.34, 1.0, zs)))   # door seam
        m.add(box(0.03, 1.3, 0.02, td.mix(col, (0, 0, 0), 0.3), center=(-0.7, 1.0, zs)))  # slider
        m.add(box(0.1, 0.06, 0.06, (24, 24, 26), center=(1.4, 1.3, side * (W / 2.0 + 0.06))))  # mirror
    m.add(box(0.02, 1.3, 0.02, td.mix(col, (0, 0, 0), 0.3), center=(-1.79, 1.12, 0.0)))  # rear doors
    for bx in (-1.85, 1.9):
        m.add(box(0.1, 0.14, W + 0.04, (40, 42, 44), center=(bx, 0.42, 0.0)))
    _wheels(m, (-1.15, 1.2), W / 2.0, rad=0.33)
    _lamps(m, 1.87, -1.8, 0.66, W / 2.0)
    return m


_TRUCK = []


def _truck():
    """IPA army truck (game/content/meshes/truck_m7), nose +x; the block van
    stands in when the asset is missing."""
    if not _TRUCK:
        from engine3d import Mesh
        try:
            from game.render3d_bridge import load_mesh_asset
            verts, faces = load_mesh_asset("truck_m7")
            m = Mesh()
            m.verts = [(v[0] * TRUCK_SCALE, v[1] * TRUCK_SCALE, v[2] * TRUCK_SCALE) for v in verts]
            m.faces = [(tuple(f[0]), tuple(f[1]), 2, True, f[2] > 0) for f in faces]
        except (OSError, ValueError):
            m = _van((64, 78, 62))
        _TRUCK.append(m)
    return _TRUCK[0]


def _dressing(r, kind, x2, y2, arg):
    from cutscenes import m6world3d as _w
    from engine3d import box, tex
    x, _, z = to3(x2, y2)
    if kind == "crates":
        crate = tex("crate", like=(118, 92, 60))
        s = 0.8 * float(arg)
        _w.add(r, box(s, s, s, crate, center=(x, s / 2.0, z)))
        _w.add(r, box(s * 0.8, s * 0.8, s * 0.8, crate, center=(x + s * 0.7, s * 0.4, z - 0.2)))
        _w.add(r, box(s * 0.7, s * 0.7, s * 0.7, crate, center=(x + 0.1, s + s * 0.35, z + 0.05)))
    elif kind == "barrels":
        for i in range(int(arg)):
            col = ((52, 74, 60), (96, 54, 36), (60, 64, 70))[i % 3]
            _w.add(r, _barrel(x + (i % 2) * 0.62 - 0.3, z + (i // 2) * 0.62, col))
    elif kind == "coil":
        from engine3d import disc_xz
        _w.add(r, disc_xz(x, z, 0.5, 0.18, (60, 46, 34), n=12))
        _w.add(r, disc_xz(x, z, 0.18, 0.19, (24, 22, 20), n=8, layer=2))


def _desk(r, x2, y2):
    from cutscenes import m6world3d as _w
    from engine3d import box, tex
    x, _, z = to3(x2, y2)
    wood = tex("crate", like=(92, 66, 44))
    _w.add(r, box(1.3, 0.06, 0.7, wood, center=(x, 0.76, z)))
    for sx in (-0.58, 0.58):
        _w.add(r, box(0.06, 0.73, 0.62, (60, 44, 30), center=(x + sx, 0.365, z)))
    _w.add(r, box(0.34, 0.03, 0.24, (205, 198, 180), center=(x - 0.25, 0.805, z)))
    _w.add(r, box(0.42, 0.3, 0.05, (30, 32, 34), center=(x + 0.25, 0.96, z + 0.2)))
    _w.add(r, box(0.36, 0.24, 0.01, (120, 170, 190), center=(x + 0.25, 0.96, z + 0.17), emissive=True))


def _lamp_fixture(r, key, x2, y2, col):
    from cutscenes import m6world3d as _w
    from engine3d import box
    x, _, z = to3(x2, y2)
    fam = key.split("_")[0]
    metal = (30, 31, 34)
    if fam == "wh":
        _w.add(r, box(0.03, 0.6, 0.03, metal, center=(x, 3.5, z)))
        _w.add(r, box(1.1, 0.1, 0.24, metal, center=(x, 3.18, z)))
        _w.add(r, box(0.96, 0.03, 0.14, col, center=(x, 3.12, z), emissive=True))
    elif fam in ("sl", "fl"):
        h = 4.2 if fam == "fl" else 3.6
        _w.add(r, box(0.12, h, 0.12, metal, center=(x, h / 2.0, z)))
        arm = 0.9
        _w.add(r, box(0.08, 0.08, arm, metal, center=(x, h, z - arm / 2.0)))
        _w.add(r, box(0.36, 0.12, 0.24, metal, center=(x, h - 0.04, z - arm)))
        _w.add(r, box(0.28, 0.03, 0.18, col, center=(x, h - 0.11, z - arm), emissive=True))
    elif fam == "gate":
        _w.add(r, box(0.4, 0.22, 0.16, (35, 33, 30), center=(x, 2.4, z)))
        _w.add(r, box(0.3, 0.14, 0.02, col, center=(x, 2.4, z - 0.09), emissive=True))
    elif fam == "ex":
        for a in (0.0, 2.1, 4.2):
            _w.add(r, box(0.04, 1.6, 0.04, (40, 42, 44),
                          center=(x + math.cos(a) * 0.25, 0.8, z + math.sin(a) * 0.25)))
        _w.add(r, box(0.42, 0.26, 0.2, (60, 62, 64), center=(x, 1.7, z)))
        _w.add(r, box(0.34, 0.18, 0.02, col, center=(x, 1.7, z - 0.11), emissive=True))
    elif fam == "dk":
        pass                                      # the desk monitor is the light


def _lamp_head(key, x2, y2):
    x, _, z = to3(x2, y2)
    fam = key.split("_")[0]
    if fam in ("sl", "fl"):
        return (x, (4.2 if fam == "fl" else 3.6) - 0.2, z - 0.9)
    if fam == "wh":
        return (x, 3.0, z)
    if fam == "gate":
        return (x, 2.3, z - 0.2)
    if fam == "ex":
        return (x, 1.7, z - 0.2)
    return (x, 1.1, z)


def _lamp_lights(r, v, flashes, tm, actors=None):
    """Lamp pools light the baked floor; the lamps nearest the camera focus
    (plus muzzle and fire flashes) are the eight per-frame lights."""
    from cutscenes import m6fx3d as _fx
    fx, fz = v.tgt[0], v.tgt[2]
    pools, near = [], []
    T = TILE_SIZE
    for tx, ty, rad, col, key in _d._M1_LAMPS:
        head = _lamp_head(key, tx * T + T / 2.0, ty * T + T / 2.0)
        reach = rad * K * 1.6
        pools.append({"pos": head, "range": reach, "color": col, "intensity": 2.2,
                      "hot": td.mix(col, (255, 250, 235), 0.5)})
        near.append(((head[0] - fx) ** 2 + (head[2] - fz) ** 2,
                     {"pos": head, "color": col, "intensity": 0.45, "range": reach}))
        if key.split("_")[0] != "dk":
            r.add_sprite(head, _fx.glow(col, 0.3, tm, intensity=0.9, max_px=18), layer=_fx.FX_LAYER)
    for row in range(MAP_H):
        for col in range(MAP_W):
            if _glyph(col, row) == "F":
                x, _, z = to3(col * T + T / 2.0, row * T + T / 2.0)
                p = (x, 1.05, z)
                _fire(r, (x, 0.9, z), tm, col * 7 + row, 0.3)
                flashes.append({"pos": p, "color": (255, 140, 60), "intensity": 0.9, "range": 5.0})
                pools.append({"pos": p, "range": 3.0, "color": (255, 140, 60), "intensity": 0.9})
    p = STATE.player
    if p is not None and actors is None:
        # a faint fill on Biribel so he reads on a black street
        flashes.append({"pos": to3(p.rect.centerx, p.rect.centery, 1.7), "color": (190, 205, 230),
                        "intensity": 0.9, "range": 3.0})
        # the nearest enemies get a fill too: local lights only reach the
        # per-frame meshes, so bodies lift off the baked floor
        px, py = p.rect.center
        foes = sorted(STATE.enemies, key=lambda e: (e.rect.centerx - px) ** 2 + (e.rect.centery - py) ** 2)
        for e in foes[:max(0, min(3, 8 - len(flashes)))]:
            flashes.append({"pos": to3(e.rect.centerx, e.rect.centery, 1.7), "color": (220, 200, 180),
                            "intensity": 0.7, "range": 2.8})
    near.sort(key=lambda e: e[0])
    lights = [e[1] for e in near[:max(0, 8 - len(flashes))]]
    r.set_pools(pools)
    r.set_lights(flashes + lights, cap=8)


# ── walls and doors (per frame) ────────────────────────────────────────

# ── night grade lights (grade3d) ───────────────────────────────────────

WINDOW_WARM = (255, 190, 100)
TAIL_RED = (226, 44, 32)
FIRE_ORANGE = (255, 140, 56)
_POOL_K = {"sl": 0.62, "fl": 0.66, "wh": 0.52, "dk": 0.32, "gate": 0.42, "ex": 0.5}


def _night_lights():
    """The fixed lights of the set for ``grade3d``: lamp throws and bulbs,
    lit windows (glass, spill, wet reflection), the parked cars' tail lights."""
    hit = _cache.get("night")
    if hit is not None:
        return hit
    T = TILE_SIZE
    out = []
    for tx, ty, rad, col, key in _d._M1_LAMPS:
        fam = key.split("_")[0]
        hx, hy, hz = _lamp_head(key, tx * T + T / 2.0, ty * T + T / 2.0)
        reach = rad * K * 1.6
        out.append(("pool", (hx, 0.0, hz), col, reach * 0.72, _POOL_K.get(fam, 0.45)))
        if fam != "dk":
            out.append(("glow", (hx, hy, hz), col, 0.7, 0.55))
        if fam in ("sl", "fl"):
            out.append(("reflect", (hx, 0.0, hz - 0.3), col, 0.55, 0.3))
    for kind, c0, r0, w, h, var in _wall_boxes():
        if kind != "facade":
            continue
        for col in range(c0, c0 + w):
            if not 0 < col < MAP_W - 1 or _d._m1_hash(col, r0, 3) == 0:
                continue
            if _d._m1_hash(col + 5, r0, 7) != 0:
                continue
            x, _, z = to3(col * T + T / 2.0, (r0 + 1) * T)
            out.append(("glow", (x, 1.9, z - 0.05), WINDOW_WARM, 0.95, 0.5))
            out.append(("pool", (x, 0.0, z - 1.0), WINDOW_WARM, 1.4, 0.32))
            out.append(("reflect", (x, 0.0, z - 0.45), WINDOW_WARM, 0.42, 0.24))
    for row in range(MAP_H):
        for col in range(MAP_W):
            ch = _glyph(col, row)
            if ch not in ("S", "T") or _glyph(col - 1, row) == ch or _glyph(col, row - 1) == ch:
                continue
            w, h = _d._m1_run_size(col, row, ch)
            if ch != "T":
                continue
            cx, _, cz = to3(col * T + w * T / 2.0, row * T + h * T / 2.0)
            truck = (w, h) == (4, 1)
            tail_x = cx - 1.9 if truck else cx + 2.14   # the sedan is parked nose west
            for side in (-1, 1):
                p = (tail_x, 0.7, cz + side * 0.62)
                out.append(("glow", p, TAIL_RED, 0.42, 0.3 if truck else 0.55))
                out.append(("reflect", (p[0], 0.0, p[2] - 0.2), TAIL_RED, 0.26, 0.22))
    _cache["night"] = out
    return out


def _flicker(tm, seed):
    return 0.8 + 0.12 * math.sin(tm * 0.017 + seed) + 0.08 * math.sin(tm * 0.053 + seed * 1.7)


def _dyn_lights(flashes, tm):
    """This frame's lights for ``grade3d``: every flash the cast and fx
    queued (muzzles, molotov fires, burning bodies, headlights), fires
    flickering, plus the burning barrels."""
    out = []
    for i, f in enumerate(flashes):
        col, k, rng = f["color"], f.get("intensity", 1.0), f.get("range", 4.0)
        fire = col[0] > 200 and col[1] < 160
        if fire:
            k *= _flicker(tm, i * 3.1 + f["pos"][0])
        out.append(("pool", f["pos"], col, rng * 0.55, min(0.75, 0.38 * k)))
        out.append(("glow", f["pos"], col, rng * 0.22, min(0.8, 0.42 * k)))
    T = TILE_SIZE
    for row in range(MAP_H):
        for col in range(MAP_W):
            if _glyph(col, row) == "F":
                x, _, z = to3(col * T + T / 2.0, row * T + T / 2.0)
                k = _flicker(tm, col * 7 + row)
                out.append(("pool", (x, 0.0, z), FIRE_ORANGE, 2.6, 0.5 * k))
                out.append(("glow", (x, 1.05, z), FIRE_ORANGE, 1.0, 0.55 * k))
                out.append(("reflect", (x, 0.0, z - 0.4), FIRE_ORANGE, 0.5, 0.25 * k))
    return out


def _put(r, mesh, pos, yaw=0.0, roll=0.0, scale=1.0, pitch=0.0):
    td.put(r, mesh, pos, yaw, roll, scale, cache=_cache["packed"], pitch=pitch)


_FLAMES = {}


def _fire(r, pos, tm, seed, size):
    """``m7world3d.fire`` (no smoke) with the flame mesh packed once per
    animation step at the origin and moved per frame: re-packing every
    flame every frame was most of a molotov's cost. The step boundary is
    staggered by seed so a fire's flames do not all re-pack on one frame."""
    from cutscenes import m7world3d as _m7
    from cutscenes import m6fx3d as _fx
    if size <= 0.0:
        return
    if not hasattr(r, "add_packed"):
        _m7.fire(r, pos, tm, seed=seed, size=size, smoky=False)
        return
    x, y, z = pos
    flicker = _m7._fire_flicker(tm, seed)
    r.add_sprite((x, y + size * 0.8, z),
                 _fx.glow((255, 111, 34), size * 1.9, tm, flicker=0.08, seed=seed,
                          core=(255, 196, 96), intensity=0.34 * flicker, max_px=70),
                 layer=_fx.FX_LAYER)
    step_ms = _m7._FIRE_STEP_MS
    step = int((tm + (seed % 4) * step_ms / 4.0) // step_ms)
    cam = getattr(r, "cam", None)
    ang = 0.0 if cam is None else math.atan2(cam[2] - z, cam[0] - x)
    ang = round(ang * 16.0 / math.pi) * math.pi / 16.0
    yk = round(y, 2)
    sq = round(math.log(size) * 12.0)        # ~8% size steps: a fading fire still hits
    key = (seed, yk, sq, ang)
    hit = _FLAMES.get(key)
    if hit is None or hit[0] != step:
        if len(_FLAMES) > 512:
            _FLAMES.clear()
        m = _m7.flame_mesh((0.0, yk, 0.0), step * step_ms, seed, math.exp(sq / 12.0),
                           heat=_m7._fire_flicker(step * step_ms, seed),
                           cam=(math.cos(ang) * 10.0, yk, math.sin(ang) * 10.0))
        faces = [(f[0], f[1], f[2], f[3], None, f[4]) for f in m.faces]
        hit = _FLAMES[key] = (step, r.pack(m.verts, faces))
    if hit[1] is not None:
        arr = hit[1].copy()
        arr[:, 0] += x
        arr[:, 1] += y - yk
        arr[:, 2] += z
        r.add_packed(arr)


def _cut_zone():
    """Sim rect (x0, y0, x1, y1) where a wall would hide Biribel, or None."""
    p = STATE.player
    if p is None:
        return None
    T = TILE_SIZE
    x, y = p.rect.centerx, p.rect.centery
    return (x - CUT_SIDE * T, y, x + CUT_SIDE * T, y + CUT_BACK * T)


def _hides(zone, x0, y0, x1, y1):
    """Does a tall thing on sim rect (x0, y0, x1, y1) stand in the cut zone?"""
    return (zone is not None and x1 > zone[0] and x0 < zone[2] and y1 > zone[1] and y0 < zone[3]
            and y0 > zone[1] - TILE_SIZE * 0.5)


def _stub(w, d):
    from engine3d import box
    return box(w, STUB_H, d, (44, 46, 50), center=(0.0, STUB_H / 2.0, 0.0), cols={"top": CUT_CAP})


def _cut_snap():
    """Snap the cut levels instead of easing them on the first frame and
    after a teleport (dev jumps, restarts, the shot tools)."""
    p = STATE.player
    at = None if p is None else (p.rect.centerx, p.rect.centery)
    last, _cache["cut_at"] = _cache["cut_at"], at
    return (at is None or last is None
            or math.hypot(at[0] - last[0], at[1] - last[1]) > 3 * TILE_SIZE)


def _cut_level(key, cut, snap):
    """Eased cut level of one wall tile or door: 1 full height, 0 a stub."""
    want = 0.0 if cut else 1.0
    k = _cache["cut"].get(key, 1.0)
    k = want if snap else (min(want, k + CUT_STEP) if want > k else max(want, k - CUT_STEP))
    _cache["cut"][key] = k
    return k


def _draw_walls(r, film=None):
    """Wall boxes at full height, except the tiles of a run that stand
    between the camera and Biribel: the run is split there and that
    stretch sinks to a stub over a few frames (and rises again behind him).
    A film has no cutaway; its ``gone`` tiles are left out."""
    T = TILE_SIZE
    gone = film.get("gone", ()) if film else ()
    zone = None if film else _cut_zone()
    snap = True if film else _cut_snap()
    _cache["cut_snap"] = snap

    def level(c, row):
        if (c, row) in gone:
            return -1.0
        if film:
            return 1.0
        k = _cut_level((c, row), _hides(zone, c * T, row * T, (c + 1) * T, (row + 1) * T), snap)
        return round(k * 8) / 8.0                 # eighths, so the stretch meshes stay cached

    for kind, c0, r0, w, h, var in _wall_boxes():
        var = var if kind == "container" else 0
        along_x = w >= h
        n = w if along_x else h
        levels = [min(level(c0 + i, r0 + j) for j in range(h)) if along_x else
                  min(level(c0 + j, r0 + i) for j in range(w)) for i in range(n)]
        i = 0
        while i < n:
            j = i
            while j + 1 < n and levels[j + 1] == levels[i]:
                j += 1
            if along_x:
                sc, sr, sw, sh = c0 + i, r0, j - i + 1, h
            else:
                sc, sr, sw, sh = c0, r0 + i, w, j - i + 1
            if levels[i] < 0.0:
                i = j + 1
                continue
            hgt = STUB_H + (_FULL_H[kind] - STUB_H) * levels[i]
            cx, _, cz = to3((sc + sw / 2.0) * T, (sr + sh / 2.0) * T)
            _put(r, _wall_mesh(kind, sw * T * K, sh * T * K, hgt, var), (cx, 0.0, cz))
            if levels[i] >= 1.0 and kind != "container":
                for tc in range(sc, sc + sw):
                    for tr in range(sr, sr + sh):
                        _roof_prop(r, tc, tr, hgt)
            i = j + 1


def _roof_prop(r, col, row, hgt):
    """Rooftop clutter on a full-height wall tile, fixed by the tile: AC
    boxes, vent stacks, tar patches. Hidden with the wall when it is cut."""
    pick = _d._m1_hash(col * 11 + 3, row * 13 + 5, 9)
    if pick > 2:
        return
    x, _, z = to3(col * TILE_SIZE + TILE_SIZE / 2.0, row * TILE_SIZE + TILE_SIZE / 2.0)
    x += (_d._m1_hash(col, row, 5) - 2) * 0.12
    _put(r, _mesh(("roof", pick), lambda: _roof_mesh(pick)), (x, hgt, z),
         yaw=90.0 * _d._m1_hash(row, col, 2))


def _roof_mesh(pick):
    from engine3d import Mesh, box
    m = Mesh()
    if pick == 0:                                  # AC unit: lit lid, dark sides, fan grille
        m.add(box(0.72, 0.36, 0.52, (64, 66, 68), center=(0.0, 0.18, 0.0),
                  cols={"top": (96, 98, 100)}))
        m.add(box(0.36, 0.01, 0.36, (30, 32, 34), center=(-0.1, 0.365, 0.0)))
        m.add(box(0.74, 0.03, 0.04, (110, 112, 112), center=(0.0, 0.33, -0.25)))
    elif pick == 1:                                # vent stack with a cap
        m.add(box(0.16, 0.5, 0.16, (54, 52, 50), center=(0.0, 0.25, 0.0), cols={"top": (24, 24, 26)}))
        m.add(box(0.28, 0.05, 0.28, (82, 80, 78), center=(0.0, 0.54, 0.0)))
    else:                                          # tar patch and a hatch
        m.add(box(1.0, 0.012, 0.7, (34, 33, 34), center=(0.0, 0.006, 0.0)))
        m.add(box(0.5, 0.1, 0.5, (58, 56, 54), center=(0.25, 0.05, 0.05), cols={"top": (78, 76, 72)}))
    return m


def _door_axis(d):
    """True when the doorway runs along x (walls left and right of it)."""
    col, row = d.rect.x // TILE_SIZE, d.rect.y // TILE_SIZE
    return _glyph(col - 1, row) not in ("", ".") or _glyph(col + 1, row) not in ("", ".")


def _draw_doors(r, film=None):
    from engine3d import Mesh, box, tex
    T = TILE_SIZE
    s = T * K
    zone = None if film else _cut_zone()
    snap = _cache.get("cut_snap", True)
    for d in STATE.doors:
        p = max(0.0, min(1.0, d.anim_progress))
        if d.is_bay:
            bays = [b for b in STATE.doors if b.is_bay]
            if d is not min(bays, key=lambda b: b.rect.x):
                continue
            cx, _, cz = to3(d.rect.x + T * 1.5, d.rect.centery)
            if _cut_level(("door", d.rect.x, d.rect.y), _hides(zone, d.rect.x, d.rect.y, d.rect.x + 3 * T,
                                                               d.rect.bottom), snap) < 0.5:
                _put(r, _mesh(("door_stub", 3), lambda: _stub(3 * s, 0.3)), (cx, 0.0, cz))
                continue
            key = ("bay", round(p, 2))
            m = _cache["meshes"].get(key)
            if m is None:
                m = Mesh()
                y0 = BAY_H * p
                if y0 < BAY_H - 0.05:
                    m.add(box(3 * s, BAY_H - y0, 0.14, tex("metal_rib", like=(150, 132, 70)),
                              center=(0.0, y0 + (BAY_H - y0) / 2.0, 0.0)))
                m.add(box(3 * s + 0.3, 0.5, 0.4, (52, 54, 56), center=(0.0, BAY_H + 0.25, 0.0)))
                _cache["meshes"][key] = m
            _put(r, m, (cx, 0.0, cz))
            continue
        along_x = _door_axis(d)
        cx, _, cz = to3(d.rect.centerx, d.rect.centery)
        if _cut_level(("door", d.rect.x, d.rect.y), _hides(zone, *d.rect.topleft, *d.rect.bottomright),
                      snap) < 0.5:
            _put(r, _mesh(("door_stub", 1), lambda: _stub(s, 0.3)), (cx, 0.0, cz),
                 yaw=0.0 if along_x else 90.0)
            continue
        col = (120, 46, 40) if d.locked else (86, 90, 96)
        key = ("door", round(p, 2), d.locked)
        m = _cache["meshes"].get(key)
        if m is None:
            m = Mesh()
            frame = (44, 46, 50)
            m.add(box(0.12, DOOR_H, 0.3, frame, center=(-s / 2.0 + 0.06, DOOR_H / 2.0, 0.0)))
            m.add(box(0.12, DOOR_H, 0.3, frame, center=(s / 2.0 - 0.06, DOOR_H / 2.0, 0.0)))
            m.add(box(s, 0.24, 0.3, frame, center=(0.0, DOOR_H + 0.12, 0.0)))
            pw = (s - 0.24) * (1.0 - p)
            if pw > 0.02:
                m.add(box(pw, DOOR_H - 0.04, 0.08, tex("steel", like=col),
                          center=(-s / 2.0 + 0.12 + pw / 2.0, DOOR_H / 2.0, 0.0)))
            if d.locked:
                m.add(box(0.1, 0.1, 0.02, (230, 50, 40), center=(s / 2.0 - 0.3, 1.3, -0.16),
                          emissive=True))
            _cache["meshes"][key] = m
        _put(r, m, (cx, 0.0, cz), yaw=0.0 if along_x else 90.0)


# ── cast ───────────────────────────────────────────────────────────────

def _motion(key, x, y, angle):
    """Walk phase from how far an actor moved since last frame."""
    m = _cache["motion"].get(key)
    if m is None:
        m = _cache["motion"][key] = [x, y, 0.0, 0.0]
    step = math.hypot(x - m[0], y - m[1]) * K
    if step > 1.0:
        step = 0.0                                # a respawn or a teleport, not a stride
    fwd = math.cos(angle) * (x - m[0]) + math.sin(angle) * (y - m[1])
    m[3] = m[3] * 0.8 + step * 60.0 * 0.2
    m[2] += step * WALK_RAD_PER_M * (1.0 if fwd >= 0.0 else -1.0)
    m[0], m[1] = x, y
    return m[2], m[3] > 0.5


# Pistol-butt strike, as offsets on the aim hold: (progress, offsets). The
# torso coils back, then whips through with a lean while the gun arm chops
# the butt down and forward; the last half eases home.
MELEE_KEYS = (
    (0.00, {}),
    (0.28, {"twist": -38, "spine": -4, "rsh_p": 34, "rel": 38, "rifle_p": -48,
            "lsh_p": -26, "lel": 30, "head_y": 10}),
    (0.42, {"twist": 34, "spine": 18, "rsh_p": 18, "rel": -46, "rifle_p": 64,
            "lsh_p": -40, "lel": 46, "head_y": -8, "head_p": 8}),
    (0.55, {"twist": 28, "spine": 15, "rsh_p": 12, "rel": -38, "rifle_p": 56,
            "lsh_p": -36, "lel": 40, "head_p": 6}),
    (1.00, {}),
)
MELEE_LUNGE_PX = 12        # sim px the body steps into the strike


def _ease(t):
    return t * t * (3.0 - 2.0 * t)


def _melee_offsets(p):
    for (p0, a), (p1, b) in zip(MELEE_KEYS, MELEE_KEYS[1:]):
        if p <= p1:
            t = _ease((p - p0) / (p1 - p0))
            return {k: a.get(k, 0.0) + (b.get(k, 0.0) - a.get(k, 0.0)) * t
                    for k in set(a) | set(b)}
    return {}


def _melee_progress():
    if not getattr(STATE, "melee_active", False) or STATE.melee_timer <= 0:
        return None
    dur = max(1.0, float(getattr(STATE, "melee_duration", 18)))
    return max(0.0, min(1.0, 1.0 - STATE.melee_timer / dur))


def _body(r, hum, x, y, angle, rig, mode, key, flashes=None, flash=False, tint=None,
          melee=None):
    from engine3d import POSES, pose_run
    phase, moving = _motion(key, x, y, angle)
    base = pose_run(phase, lean=4) if moving else dict(POSES["stand"])
    pose = td.held(hum, base, rig, mode)
    if melee is not None:
        for k, v in _melee_offsets(melee).items():
            pose[k] = pose.get(k, 0.0) + v
        lunge = MELEE_LUNGE_PX * math.sin(math.pi * min(1.0, melee / 0.7))
        x, y = x + math.cos(angle) * lunge, y + math.sin(angle) * lunge
    if flash:
        pose["rifle_p"] = pose.get("rifle_p", 0.0) - 6.0
    joints = r.add_humanoid(hum, pose, to3(x, y), td.yaw_rad(angle), rifle_on=True, tint=tint)
    if flash and joints and flashes is not None:
        mz = joints.get("muzzle")
        if mz is not None:
            from cutscenes import m6fx3d as _fx
            flashes.append({"pos": mz, "color": (255, 196, 120), "intensity": 1.4, "range": 5.0})
            r.add_sprite(mz, _fx.glow((255, 214, 150), 0.32, _now_ms(), core=(255, 250, 236),
                                      intensity=1.3, max_px=28), layer=_fx.FX_LAYER)
    return joints


def _feet(r, x, y, col, rad=0.42):
    """A tactical floor marker over a soft drop shadow: who is who reads
    from the floor."""
    r.add_sprite(to3(x, y, 0.02), td.tac_ring(rad, col), layer=0)


def _burning(r, x, y, k, tm, seed, flashes, lying=False):
    """Flames on a body: three licks up a standing one, a row along a
    fallen one. ``k`` 0..1 is how hard it still burns."""
    if k <= 0.0:
        return
    bx, _, bz = to3(x, y)
    if lying:
        licks = ((-0.4, 0.2, -0.1, 0.34), (0.1, 0.25, -0.15, 0.42), (0.5, 0.2, -0.1, 0.3))
    else:
        licks = ((0.0, 0.3, -0.3, 0.42), (0.16, 0.9, -0.28, 0.34), (-0.1, 1.4, -0.24, 0.26))
    for i, (dx, hy, dz, size) in enumerate(licks):
        _fire(r, (bx + dx, hy, bz + dz), tm, seed + i, size * k)
    if len(flashes) < 6:
        flashes.append({"pos": (bx, 1.0, bz), "color": (255, 128, 48),
                        "intensity": 1.2 * k, "range": 3.5})


def _enemy_hum(e):
    if e.is_commander:
        return td.armed("commander", "pistol"), "pistol"
    if e.is_ambush_enemy:
        return td.armed("ipa", "os12", jacket=MAG), "os12"
    return td.armed("ipa", "os12", jacket=IPA), "os12"


def player_hum():
    p = STATE.player
    rig = p.rig_weapon_name() if p is not None else "pistol"
    return td.armed("biribel", rig), rig


def _draw_cast(r, flashes, tm):
    from engine3d import blend
    T = TILE_SIZE
    vpos = getattr(STATE, "volkov_pos", None)
    if vpos and not STATE.volkov_escape_timer and not STATE.volkov_escaped:
        p = STATE.player
        ang = (math.atan2(p.rect.centery - vpos[1], p.rect.centerx - vpos[0]) if p
               else math.pi * 0.75)
        _body(r, td.armed("volkov", "pistol"), vpos[0], vpos[1], ang, "pistol", "ready", "volkov")
    if STATE.firefight_triggered and STATE.volkov_escape_timer > 0:
        vp = STATE.volkov_escape_pos
        if vp and not STATE.volkov_escaped:
            ang = math.atan2(29 * T + 32 - vp[1], 15 * T + 32 - vp[0])
            _body(r, td.armed("volkov", "pistol"), vp[0], vp[1], ang, "pistol", "ready", "volkov")
        kp = STATE.commander_escape_pos
        if kp and not STATE.commander_escaped:
            ang = math.atan2(29 * T + 32 - kp[1], 15 * T + 32 - kp[0])
            _body(r, td.armed("commander", "pistol"), kp[0], kp[1], ang, "pistol", "ready", "commander")
    if getattr(STATE, "exfil_van_arrived", False):
        # rear against the east wall, nose west (the 2D van overlaps the wall)
        cx, _, cz = to3(27 * T - 1.8 / K, 31 * T + 16)
        r.add_sprite((cx, 0.02, cz), td.shadow(2.0, 0.95, 150), layer=0)
        _put(r, _mesh("van", lambda: _van((34, 36, 40))), (cx, 0.0, cz), yaw=180.0)
    if STATE.notebook_collected and STATE.EXFIL_POS:
        ex, _, ez = to3(*STATE.EXFIL_POS)
        ex -= 1.0                     # clear of the van's nose when both are parked
        r.add_sprite((ex, 0.02, ez), td.shadow(2.1, 0.95, 150), layer=0)
        _put(r, _truck(), (ex, 0.0, ez))
        for wz in (-0.6, 0.6):
            flashes.append({"pos": (ex + 2.2, 0.8, ez + wz), "color": (255, 230, 150),
                            "intensity": 0.7, "range": 6.0})
    for x, y, n in getattr(STATE, "_m1_brick_piles", ()):
        for i in range(min(3, n + 1)):
            bx, _, bz = to3(x + (-9, 1, -4)[i], y + (2, 3, -3)[i])
            _put(r, _mesh("brick", lambda: _box(0.3, 0.1, 0.15, (128, 64, 48))),
                 (bx, 0.05 + 0.1 * (i == 2), bz), yaw=i * 30.0)
    _draw_corpses(r, flashes, tm)
    flash_on = STATE.muzzle_flash_timer > 0
    for e in STATE.enemies:
        hum, rig = _enemy_hum(e)
        mode = "aim" if e.state in ("CHASE", "ATTACK") else "ready"
        burn = getattr(e, "burn", 0)
        tint = CHAR if burn else (e.body_tint, 0.55) if e.body_tint else None
        _feet(r, e.rect.centerx, e.rect.centery, RING_FOE.get(e.state, RING_FOE_CALM))
        _body(r, hum, e.rect.centerx, e.rect.centery, e.angle, rig, mode, ("e", e.uid), tint=tint)
        _burning(r, e.rect.centerx, e.rect.centery, min(1.0, burn / 40.0), tm, e.uid * 5, flashes)
    p = STATE.player
    if p is None:
        return
    if STATE.player_dead:
        _draw_dead_player(r)
        return
    hum, rig = player_hum()
    melee = _melee_progress()
    mode = "ready" if STATE.is_reloading else "aim"
    _feet(r, p.rect.centerx, p.rect.centery, RING_YOU, rad=0.46)
    _body(r, hum, p.rect.centerx, p.rect.centery, p.angle, rig, mode, "player", flashes,
          flash_on and melee is None, melee=melee)
    _burning(r, p.rect.centerx, p.rect.centery,
             min(1.0, getattr(STATE, "_m1_player_burn", 0) / 30.0), tm, 7, flashes)


def _draw_corpses(r, flashes, tm):
    from engine3d import blend
    for c in list(getattr(STATE, "corpses", ())):
        hum = (td.armed("commander", "pistol") if c.is_commander else
               td.armed("ipa", "os12", jacket=MAG if c.is_mag else IPA))
        k = min(1.0, c.t / float(CORPSE_FALL))
        pose = blend("kneel", "dead_side", k) if k > 0.35 else blend("stand", "kneel", k / 0.35)
        at = to3(c.x, c.y)
        if k >= 1.0:
            r.add_sprite((at[0], 0.02, at[2]), td.blood_pool(min(1.0, (c.t - CORPSE_FALL) / 90.0)),
                         layer=0)
        burnt = hasattr(c, "burn")
        r.add_sprite((at[0], 0.02, at[2]), td.shadow(0.75, 0.55, 110), layer=0)
        r.add_humanoid(hum, pose, at, td.yaw_rad(c.angle) + 90.0 * c.fall_dir, rifle_on=False,
                       tint=CHAR if burnt else None)
        if burnt:
            _burning(r, c.x, c.y, min(1.0, c.burn / 120.0), tm, id(c) % 97, flashes, lying=True)


def _xz(x, y):
    p = to3(x, y)
    return p[0], p[2]


def _draw_dead_player(r):
    from engine3d import blend
    p = STATE.player
    t = getattr(STATE, "death_anim_timer", 999)
    k = min(1.0, t / 40.0)
    slide = min(1.0, t / 30.0)
    x = p.rect.centerx + getattr(STATE, "death_player_slide_x", 0.0) * slide
    y = p.rect.centery + getattr(STATE, "death_player_slide_y", 0.0) * slide
    pool = getattr(STATE, "death_blood_pool_pos", None)
    if pool is not None and STATE.death_blood_pool_radius > 0:
        px, _, pz = to3(*pool)
        rad = STATE.death_blood_pool_radius / 40.0
        r.add_sprite((px, 0.02, pz), td.blood_pool(min(1.0, rad), (60, 8, 8)), layer=0)
    if getattr(STATE, "death_weapon_ejected", False) and STATE.death_weapon_pos is not None:
        from ui import mp3d
        mesh, _mz = mp3d.gun(STATE.death_weapon_type)
        wx, _, wz = to3(*STATE.death_weapon_pos)
        _put(r, mesh, (wx, 0.04, wz), yaw=STATE.death_weapon_rotation, roll=90.0)
    hum, _rig = player_hum()
    pose = blend("kneel", "dead_back", k) if k > 0.4 else blend("stand", "kneel", k / 0.4)
    r.add_humanoid(hum, pose, to3(x, y), td.yaw_rad(p.angle), rifle_on=False)


def _mesh(key, build):
    m = _cache["meshes"].get(key)
    if m is None:
        m = _cache["meshes"][key] = build()
    return m


def _box(w, h, d, col, emissive=False):
    from engine3d import box
    return box(w, h, d, col, center=(0.0, 0.0, 0.0), emissive=emissive)


# ── fx ─────────────────────────────────────────────────────────────────

_PICKUP_COL = {"bandage": (100, 255, 100), "bottle": (255, 150, 70)}

_MOLOTOV = []


def _molotov():
    """The thrown molotov and the molotov pickup: game/content/meshes/molotov
    (tools/ae_import_molotov.py), bottle centred on the origin, rag and three
    flame shells included, the flame faces emissive. The block bottle stands
    in when the asset is missing.

    Returns ``(mesh, flame)`` - ``flame`` is the centroid of the emissive
    faces in mesh space, so a thrown bottle's wick light can follow the
    tumble instead of sitting at the glass."""
    if not _MOLOTOV:
        from engine3d import Mesh
        try:
            from game.render3d_bridge import load_mesh_asset
            verts, faces = load_mesh_asset("molotov")
            m = Mesh()
            m.verts = [tuple(v) for v in verts]
            m.faces = [(tuple(f[0]), tuple(f[1]), 2, True, f[2] == 1) for f in faces]
        except (OSError, ValueError):
            m = _pickup_mesh("bottle")
        hot = [i for f in m.faces if f[4] for i in f[0]]
        n = float(len(hot)) or 1.0
        flame = tuple(sum(m.verts[i][k] for i in hot) / n for k in range(3))
        _MOLOTOV.append((m, flame))
    return _MOLOTOV[0]


def _pickup_mesh(kind):
    from engine3d import Mesh, box
    m = Mesh()
    if kind == "bandage":
        m.add(box(0.3, 0.12, 0.2, (226, 222, 210), center=(0.0, 0.06, 0.0)))
        m.add(box(0.14, 0.01, 0.04, (200, 40, 40), center=(0.0, 0.125, 0.0), emissive=True))
        m.add(box(0.04, 0.01, 0.14, (200, 40, 40), center=(0.0, 0.125, 0.0), emissive=True))
    elif kind == "bottle":
        m.add(box(0.1, 0.26, 0.1, (60, 120, 70), center=(0.0, 0.13, 0.0)))
        m.add(box(0.05, 0.08, 0.05, (200, 190, 160), center=(0.0, 0.3, 0.0)))
    elif kind == "keycard":
        m.add(box(0.22, 0.02, 0.14, (240, 200, 60), center=(0.0, 0.01, 0.0), emissive=True))
    else:
        m.add(box(0.12, 0.2, 0.06, (40, 40, 44), center=(0.0, 0.1, 0.0)))
        m.add(box(0.1, 0.02, 0.05, (200, 160, 70), center=(0.0, 0.21, 0.0)))
    return m


def _fuel_pool(x, z, rad, seed):
    """Burning spilt fuel: three ragged emissive rings, dark rim to hot
    centre, so the flames stand in one fire instead of separate braziers."""
    from engine3d import Mesh
    m = Mesh()
    n = 20
    for rr, col, y in ((rad * 0.85, (46, 16, 10), 0.012), (rad * 0.6, (112, 32, 12), 0.018),
                       (rad * 0.3, (196, 84, 24), 0.024)):
        pts = []
        for i in range(n):
            a = math.tau * i / n
            k = 0.86 + 0.14 * math.sin(seed + i * 2.3) * math.cos(seed * 0.7 + i * 1.1)
            pts.append((x + math.cos(a) * rr * k, y, z + math.sin(a) * rr * k))
        m.face(pts, col, 2, True, True)
    return m


FIRE_CULL_PX = 256       # fire zones this far outside the 2D camera rect are skipped
_POOLS = {}


def _fuel_pool_at(r, x, z, rad, seed):
    """``_fuel_pool`` packed once at the origin per (seed, ~6% radius step) and
    moved per frame; rebuilding and packing it per zone per frame was the bulk
    of a late-mission fire's cost (the bay fire alone is 26 zones)."""
    if not hasattr(r, "add_packed"):
        from cutscenes import m6world3d as _w
        _w.add(r, _fuel_pool(x, z, rad, seed))
        return
    rq = round(math.log(max(rad, 0.05)) * 16.0)
    key = (round(seed, 1), rq)
    arr = _POOLS.get(key)
    if arr is None:
        if len(_POOLS) > 512:
            _POOLS.clear()
        m = _fuel_pool(0.0, 0.0, math.exp(rq / 16.0), seed)
        faces = [(f[0], f[1], f[2], f[3], None, f[4]) for f in m.faces]
        arr = _POOLS[key] = r.pack(m.verts, faces)
    if arr is not None:
        arr = arr.copy()
        arr[:, 0] += x
        arr[:, 2] += z
        r.add_packed(arr)


def _draw_fx(r, flashes, tm):
    from cutscenes import m6fx3d as _fx
    from core.config import C_BULLET
    t = _now_s()
    for pu in STATE.pickups:
        x, _, z = to3(pu[0], pu[1])
        bob = 0.06 * math.sin(t * 3 + pu[0])
        mesh = _molotov()[0] if pu[2] == "bottle" else _mesh(("pickup", pu[2]),
                                                             lambda k=pu[2]: _pickup_mesh(k))
        _put(r, mesh, (x, 0.25 + bob, z), yaw=(t * 60.0 + pu[0]) % 360.0)
        r.add_sprite((x, 0.3, z), _fx.glow(_PICKUP_COL.get(pu[2], (255, 210, 40)), 0.28, tm,
                                           intensity=0.7, max_px=16), layer=_fx.FX_LAYER)
    if STATE.firefight_triggered and not STATE.notebook_collected and STATE.NOTEBOOK_POS:
        x, _, z = to3(*STATE.NOTEBOOK_POS)
        _put(r, _mesh("notebook", lambda: _box(0.22, 0.04, 0.3, (20, 20, 20))), (x, 0.3, z))
        r.add_sprite((x, 0.35, z), _fx.glow((255, 220, 100), 0.35, tm, pulse=0.3, intensity=0.8,
                                            max_px=20), layer=_fx.FX_LAYER)
    for desk in STATE.desks:
        x, _, z = to3(desk["x"], desk["y"])
        col = (100, 220, 100) if desk["read"] else (240, 190, 50)
        r.add_sprite((x - 0.45, 0.85, z), _fx.glow(col, 0.08, tm, core=col, max_px=8),
                     layer=_fx.FX_LAYER)
    for mx, my, timer in STATE.breach_markers:
        r.add_sprite(to3(mx, my, 0.05), _fx.glow((255, 80, 20), 0.4, tm,
                                                 intensity=min(1.0, timer / 60.0), max_px=26),
                     layer=_fx.FX_LAYER)
    for decal in STATE.blood_decals:
        k = max(0.0, min(1.0, decal[2] / 255.0))
        if k > 0.05:
            r.add_sprite(to3(decal[0], decal[1], 0.015),
                         td.blood_pool(min(1.0, decal[3] / 24.0) * k, (80, 12, 14)), layer=0)
    cx0, cy0 = _d._M1_CAM[0] - FIRE_CULL_PX, _d._M1_CAM[1] - FIRE_CULL_PX
    cx1, cy1 = cx0 + WIDTH + 2 * FIRE_CULL_PX, cy0 + HEIGHT + 2 * FIRE_CULL_PX
    for fz in STATE.fire_zones:
        if not (cx0 < fz.x < cx1 and cy0 < fz.y < cy1):
            continue                              # off-screen: no flames, pool or light
        life = fz.life / float(max(1, fz.max_life))
        heat = min(1.0, life * 4.0)               # the last quarter of a fire dies down
        x, _, z = to3(fz.x, fz.y)
        rad = fz.radius * K
        r.add_sprite((x, 0.02, z), td.blood_pool(min(1.0, rad / 2.0), (26, 18, 14)), layer=0)
        _fuel_pool_at(r, x, z, rad * (0.55 + 0.45 * heat), fz.x * 0.37 + fz.y * 0.11)
        n = 1 + min(9, int(rad / 0.3))
        for i in range(n):                        # the layered M7 flame: a tall core, licks over the pool
            a = i * 2.39996 + fz.x * 0.013
            d = 0.0 if i == 0 else rad * 0.8 * math.sqrt(i / float(n))
            size = (0.5 if i == 0 else 0.34) * min(1.2, 0.4 + rad * 0.35) * heat
            # no smoke: from the top-down camera it smears over the walls behind
            _fire(r, (x + math.cos(a) * d, 0.0, z + math.sin(a) * d), tm, int(fz.x) + i, size)
        flashes.append({"pos": (x, 1.0, z), "color": (255, 140, 60), "intensity": 1.0 * heat,
                        "range": 4.0 + rad})
    from engine3d import m_apply, m_mul, rot_x, rot_y
    for b in STATE.thrown_bottles:
        bt = b["t"]
        p = to3(b["x"], b["y"], 0.9 + math.sin(bt * math.pi) * 1.2)
        yaw = td.yaw_of(math.degrees(math.atan2(b["ty"] - b["start_y"], b["tx"] - b["start_x"])))
        if b.get("brick"):
            # M1 brick: a tumbling block, no wick and no fire light.
            _put(r, _mesh("brick", lambda: _box(0.22, 0.1, 0.11, (120, 62, 44))), p,
                 yaw=yaw, pitch=(b.get("spin", 0) + bt * 900) % 360.0)
        else:
            mesh, flame = _molotov()
            pitch = (b.get("spin", 0) + bt * 540) % 360.0
            _put(r, mesh, p, yaw=yaw, pitch=pitch)
            fx, fy, fz = m_apply(m_mul(rot_y(yaw), rot_x(pitch)), flame)
            r.add_sprite((p[0] + fx, p[1] + fy, p[2] + fz),
                         _fx.glow((255, 140, 40), 0.22, tm, flicker=0.55, seed=int(p[2] * 100),
                                  core=(255, 200, 120), intensity=1.0, max_px=16),
                         layer=_fx.FX_LAYER)
        r.add_sprite((p[0], 0.02, p[2]), td.shadow(0.16, alpha=120), layer=0)
    for b in STATE.bullets:
        head = to3(b["x"], b["y"], AIM_H)
        tail = to3(b.get("prev_x", b["x"] - b["dx"]), b.get("prev_y", b["y"] - b["dy"]), AIM_H)
        r.add_line3d(tail, head, (255, 220, 140), 2, layer=4)
        r.add_sprite(head, _fx.glow(C_BULLET, 0.12, tm, intensity=0.9, max_px=10), layer=_fx.FX_LAYER)
    for p in STATE.particles:
        r.add_sprite(to3(p.x, p.y, 0.25 + 0.03 * getattr(p, "life", 0)),
                     td.dot(tuple(p.color[:3]), getattr(p, "size", 2)), layer=_fx.FX_LAYER)
    for c in STATE.casings:
        r.add_sprite(to3(c.x, c.y, 0.03), td.dot((200, 160, 70), 2), layer=1)
    if STATE.notebook_collected and STATE.EXFIL_POS:
        x, z = _xz(*STATE.EXFIL_POS)
        pulse = 0.5 + 0.5 * math.sin(t * 3)
        col = td.mix((30, 120, 60), (60, 230, 120), pulse)
        td.ring(r, x, z, 1.0, col, n=24, width=2)
        td.ring(r, x, z, 0.75, col, n=20)


# ── drop-off film ──────────────────────────────────────────────────────

VAN_LEN = 3.6
VAN_COL = (58, 62, 66)
KRAP_VAN_M = 7.18                # krap_van.glb nose to tail, as walk3d measures it


def _krap_van_mesh():
    """krap_van.glb scaled to the drop-off footprint (VAN_LEN), nose +x; the
    block van stands in when the asset is missing."""
    from engine3d import Mesh
    try:
        from game.render3d_bridge import load_mesh_asset
        verts, faces = load_mesh_asset("krap_van")
    except (OSError, ValueError, KeyError):
        return _van(VAN_COL)
    s = VAN_LEN / KRAP_VAN_M
    m = Mesh()
    m.verts = [(x * s, y * s, z * s) for x, y, z in verts]
    for idx, col, grp in faces:
        m.faces.append((tuple(idx), tuple(col), 3 if grp == 9 else 2, False, grp in (1, 2)))
    return m


def dropoff(surface, t, zoom=1.0, locked=False):
    """One drop-off take in 3D: the van brakes at the curb, Biribel climbs
    out and walks to the side door. Timing, positions and the camera path
    are the 2D film's (``draw._dropoff_*``); ``zoom`` is the punch-in of the
    follow (1.5) and entry (2.1) beats. False when the renderer failed."""
    t = max(0, min(_d._DROPOFF_MS, int(t)))
    bx, by, facing, moving, _under = _d._dropoff_biribel(t)
    if zoom > 1.0:
        fx, fy = _d.M1_SPAWN_POS if locked else (bx, by)
        cam = td.Cam(56.0, CAM.dist / zoom, CAM.fov, CAM.res, look_h=1.0)
    else:
        cx, cy = _d._dropoff_cam(t)
        fx, fy, cam = cx + WIDTH / 2.0, cy + HEIGHT / 2.0, CAM
    v = td.View(cam, fx, fy)

    def actors(r, flashes, tm):
        from engine3d import POSES, pose_run
        T = TILE_SIZE
        for e in getattr(STATE, "enemies", ()):
            if e.rect.centery < M1_STREET_ROW * T:
                hum, rig = _enemy_hum(e)
                pose = td.held(hum, dict(POSES["stand"]), rig, "ready")
                r.add_sprite(to3(e.rect.centerx, e.rect.centery, 0.02), td.shadow(0.42), layer=0)
                r.add_humanoid(hum, pose, to3(e.rect.centerx, e.rect.centery), td.yaw_rad(e.angle))
        hum, rig = player_hum()
        base = pose_run(t * 0.009, lean=3) if moving else dict(POSES["stand"])
        r.add_sprite(to3(bx, by, 0.02), td.shadow(0.42), layer=0)
        r.add_humanoid(hum, td.held(hum, base, rig, "ready"), to3(bx, by), td.yaw_rad(facing))
        van = _d._dropoff_van(t)
        if van is None:
            return
        rear, vy = van
        x, _, z = to3(rear + VAN_LEN / 2.0 / K, vy)
        r.add_sprite((x, 0.02, z), td.shadow(2.0, 0.95, 150), layer=0)
        _put(r, _mesh("dropoff_van", _krap_van_mesh), (x, 0.0, z))
        hot = t < _d._DROPOFF_ARRIVE_MS + 300 or t > _d._DROPOFF_LEAVE_MS
        tail = (x - VAN_LEN / 2.0 - 0.1, 0.65, z)
        flashes.append({"pos": tail, "color": (230, 40, 32), "intensity": 0.9 if hot else 0.4,
                        "range": 3.0})
        flashes.append({"pos": (x + VAN_LEN / 2.0 + 3.0, 0.25, z), "color": (255, 228, 170),
                        "intensity": 1.1, "range": 7.0})

    return render_world(surface, v, actors)


# ── screen space ───────────────────────────────────────────────────────

def _at(v, x, y, h):
    p = v.screen_sim(x, y, h)
    return None if p is None else (int(p[0]), int(p[1]))


def _near(pos, dist):
    p = STATE.player
    return (p is not None and not STATE.player_dead
            and math.hypot(p.rect.centerx - pos[0], p.rect.centery - pos[1]) <= dist)


def _blit_c(s, img, pt, dy=0):
    s.blit(img, (pt[0] - img.get_width() // 2, pt[1] + dy))


def _labels(s, v):
    """World-anchored text, prompts and stealth meters, projected."""
    for desk in STATE.desks:
        pt = _at(v, desk["x"], desk["y"], 0.0)
        if pt and -50 < pt[0] < WIDTH + 50 and -50 < pt[1] < HEIGHT + 50:
            _blit_c(s, font_terminal_small.render(_T("m1.desk"), True, (150, 140, 120)), pt, 14)
    T = TILE_SIZE
    bay = _at(v, 15 * T + 32, 29 * T + 32, BAY_H + 0.6)
    if bay:
        _blit_c(s, font_terminal_small.render(_T("m1.bay_door"), True, (150, 140, 120)), bay)
    for d in STATE.doors:
        if _near(d.rect.center, DOOR_INTERACT_RANGE):
            if d.is_bay:
                bays = [b for b in STATE.doors if b.is_bay]
                if d is min(bays, key=lambda b: b.rect.x):
                    pt = _at(v, d.rect.x + T * 1.5, d.rect.centery, BAY_H + 0.3)
                else:
                    pt = _at(v, d.rect.centerx, d.rect.centery, BAY_H + 0.3)
            else:
                pt = _at(v, d.rect.centerx, d.rect.centery, DOOR_H + 0.4)
            if pt:
                _blit_c(s, font_terminal_small.render(_T("m1.e"), True, C_TERMINAL), pt)
    if STATE.firefight_triggered and not STATE.notebook_collected and STATE.NOTEBOOK_POS:
        if _near(STATE.NOTEBOOK_POS, 80):
            nearby = [e for e in STATE.enemies
                      if math.hypot(e.rect.centerx - STATE.NOTEBOOK_POS[0],
                                    e.rect.centery - STATE.NOTEBOOK_POS[1]) < 300]
            txt = (font_prompt.render(_T("m1.walk_over_to_collect"), True, (255, 220, 100))
                   if not nearby else
                   font_prompt.render(_T("m1.clear_hostiles_first"), True, (220, 60, 60)))
            pt = _at(v, STATE.NOTEBOOK_POS[0], STATE.NOTEBOOK_POS[1], 1.2)
            if pt:
                _blit_c(s, txt, pt)
    if STATE.notebook_collected and STATE.EXFIL_POS:
        pt = _at(v, STATE.EXFIL_POS[0], STATE.EXFIL_POS[1], 2.8)
        if pt:
            _blit_c(s, font_prompt.render(_T("m1.exfil"), True, (50, 200, 100)), pt)
            if _near(STATE.EXFIL_POS, 80) and not STATE.truck_hotwiring:
                if STATE.enemies:
                    txt = font_prompt.render(_T("m1.clear_hostiles", n=len(STATE.enemies)), True,
                                             (230, 80, 60))
                else:
                    txt = font_prompt.render(_T("m1.e_open_ignition_panel"), True, (100, 255, 100))
                _blit_c(s, txt, pt, -16)
    if not getattr(STATE, "_m1_standoff", None):
        _meters(s, v)


def _meters(s, v):
    """``stealth.draw_meters`` over each guard's head, projected."""
    if STATE.firefight_triggered:
        return
    minds = getattr(STATE, "_m1_stealth", {})
    steps, rad = _st._METER_STEPS, _st._METER_R
    for e in STATE.enemies:
        m = minds.get(e.uid)
        if m is None or m["s"] <= 0.0:
            continue
        pt = _at(v, e.rect.centerx, e.rect.centery, 2.3)
        if pt is None:
            continue
        cx, cy = pt
        lit = int(round(m["s"] * steps))
        col = _st.meter_color(m)
        for i in range(steps + 1):
            a = math.pi + math.pi * i / steps
            x = cx + int(round(math.cos(a) * rad)) - 1
            y = cy + int(round(math.sin(a) * rad)) - 1
            s.fill(col if i <= lit and lit > 0 else _st._METER_BACK, (x, y, 2, 2))
        if m["call_t"] > 0:
            s.fill(_st._METER_RED, (cx - 1, cy - 9, 2, 6))
            s.fill(_st._METER_RED, (cx - 1, cy - 1, 2, 2))


def _overlay(q, v):
    """``draw._submit_overlay`` with world anchors projected; the muzzle
    flash is a 3D light now, but its timer still runs down here."""
    ch_x, ch_y = get_scaled_mouse()
    unpinned = [ft for ft in STATE.floating_texts if not (len(ft) >= 6 and ft[5] == "pin")]

    def texts(s):
        for ft in unpinned:
            pt = _at(v, ft[0], ft[1], 1.8)
            if pt:
                _blit_c(s, font_terminal_small.render(ft[2], True, ft[3]), pt)
    q.submit(_UiPassDraw(texts, "m1.texts3d"), _L.OVERLAY_WORLD, sort_key=(0, 0))
    if not getattr(STATE, "_m1_standoff", None):
        from ui.hud import draw_pinned_radio
        q.submit(_UiPassDraw(lambda s: draw_pinned_radio(s), "m1.dialogue"),
                 _L.OVERLAY_WORLD, sort_key=(1, 0))
        q.submit(_UiPassDraw(lambda s: _d._draw_m1_reticle(s, ch_x, ch_y), "m1.reticle"),
                 _L.OVERLAY_WORLD, sort_key=(2, 0))
    if STATE.muzzle_flash_timer > 0:
        STATE.muzzle_flash_timer -= 1
    if STATE.player_dead:
        def tinnitus(s):
            try:
                from missions import m2
                if hasattr(m2, "_draw_tinnitus_overlay"):
                    m2._draw_tinnitus_overlay(s)
            except Exception:
                pass
        q.submit(_UiPassDraw(tinnitus, "m1.death"), _L.OVERLAY_WORLD, sort_key=(4, 0))
    if STATE.gc_flash_timer > 0 and not getattr(STATE, "reduced_motion", False):
        def flash(s):
            f = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
            f.fill((255, 255, 255, min(255, STATE.gc_flash_timer * 22)))
            s.blit(f, (0, 0))
        q.submit(_UiPassDraw(flash, "m1.flash"), _L.OVERLAY_WORLD, sort_key=(5, 0))
    if STATE.breach_stage in (3, 4):
        q.submit(_UiPassDraw(_d._draw_m1_breach_wash, "m1.wash"), _L.OVERLAY_WORLD, sort_key=(6, 0))
    q.submit(_UiPassDraw(lambda s: draw_scanlines(s), "m1.scanlines"), _L.OVERLAY_WORLD, sort_key=(7, 0))
    q.submit(_UiPassDraw(_grade.vignette, "m1.vignette"), _L.OVERLAY_WORLD, sort_key=(8, 0))
