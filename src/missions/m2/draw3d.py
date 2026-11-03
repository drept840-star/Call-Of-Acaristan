"""Mission 2 in 2.5D: Route 12 drawn in 3D over the 2D rules.

``draw.game_draw`` hands the frame here while ``game.topdown3d`` is on
(``CAMS["MISSION2"]``). The sim, the sniper, the blast timers and every
collision rect stay where they were; this module only changes what the
world looks like. The 2D painter's world-anchored passes (clue props and
markers, gantry labels, the flank-cutscene letterbox, the shelter arrow)
run on top through ``draw._PROJ``, which makes ``draw._world`` project
through this frame's ``td.View``; the screen passes (reticle, flashes,
blackout, HUD, cards, upload OS, fades, death tilt) are
``draw._draw_screen_passes``.

Set: the map glyphs and the 2D painter's own tables are the source. ``C``
is split by where it stands (map border, control building, security hut,
gantry legs, toll booths), ``B`` is a jersey barrier, the garden and the
shelter come from the meta rects and ``STATE.mission2_shelter_walls``.
Walls are drawn per frame with the M1 cutaway; floor, paint, garden,
barriers, lamps and dressing are one static batch.

The lamps, colours and grade follow the 2D night (``draw._M2_LAMPS``,
``_m2_lamp_visible``, the truck headlight cone and the cool sky wash).
The tanker blast is a real 3D fireball and shockwave lit by the 2D blast
light's radii; the white flash and the blackout stay screen overlays.

Any renderer error turns 2.5D off for the rest of the run (``td.disable``)
and the frame falls back to the 2D painter.
"""
import math

import pygame

from core.config import HEIGHT, TILE_SIZE, WIDTH, font_terminal_small, screen
from core.state import STATE
from engine.core import now_ms as _now_ms, now_s as _now_s
from game import topdown3d as td
from game.topdown3d import K, to3
from missions.m1 import draw3d as _m1
from missions.m1 import grade3d as _grade
from missions.m2 import draw as _d
from missions.m2.meta import (GARDEN_BENCH_RECTS, GARDEN_FOUNTAIN_RECT, GARDEN_HEDGE_RECTS,
                              GARDEN_LAMP_RECTS, GARDEN_TREE_RECTS, MAP_H, MAP_W,
                              MISSION2_BUILDINGS, SAFE_ZONE, SNIPER_NEST_POS, STAGE_EVIDENCE,
                              STAGE_INVESTIGATE, STAGE_SNIPER, STAGE_TRUCK, STAGE_UPLOAD,
                              UPLOAD_TERMINAL_POS)
from missions.m2.world import MISSION2_MAP

CAM = td.CAMS["MISSION2"]
T = TILE_SIZE
AIM_H = _m1.AIM_H
STUB_H = _m1.STUB_H
CUT_CAP = _m1.CUT_CAP
DECK_H = _d.GANTRY_DECK_H
WALL_H = {"border": 2.6, "facade": 3.2, "hut": 2.8, "booth": 2.4, "tower": DECK_H}
BARRIER_H = 0.8
SHELTER_H = 1.4

ASPHALT = (34, 36, 37)
LOT = (68, 76, 77)                 # the concrete lot round the control building
GRASS = (56, 80, 48)
LANE = (145, 130, 60)
STOP = (150, 145, 120)
SHOULDER = (120, 115, 90)
GLASS = (31, 51, 56)
LIT_GLASS = (150, 118, 66)
FACADE = (55, 64, 69)
FACADE_CAP = (105, 119, 121)
FRAME = (91, 117, 121)
WALL = (72, 70, 64)
WALL_CAP = (112, 109, 100)
STEEL = (58, 62, 64)
SIGN = (38, 55, 52)
CHAR = ((26, 22, 20), 0.85)
TANK = (150, 146, 132)
FIRE = (255, 140, 56)
BLAST = (255, 170, 90)
VOID = _m1.VOID
AMBIENT = (176, 176, 180)        # grade floor: the 2D night is greyer and brighter than M1's blue
NIGHT = dict(_m1.NIGHT, ambient=0.40, diffuse=0.50, tint=(0.92, 0.95, 1.02))  # the 2D Route 12 night is greyer than M1

_BUILD = pygame.Rect(MISSION2_BUILDINGS[0])
_HUT = pygame.Rect(MISSION2_BUILDINGS[1])
_GARDEN = pygame.Rect(51, 1, 17, 8)
_PATH = pygame.Rect(54, 3, 11, 4)
_TOWERS = ((56, 27), (59, 27))
_LIT_WINDOWS = (55, 60, 64)
_LANE_COLS = (28, 36, 44)
_POSTS = ((16, 25), (16, 29), (16, 41), (16, 45), (16, 53), (16, 61), (16, 69),
          (54, 25), (54, 30), (54, 41), (54, 46), (54, 54), (54, 62), (54, 70),
          (12, 70), (22, 68))
_FLOODS = ((27, 34), (47, 34), (28, 46))

_cache = {"walls": None, "packed": {}, "meshes": {}, "night": None}


# ── frame ──────────────────────────────────────────────────────────────

def game_draw3d(fcx, fcy):
    """Draw one Mission 2 gameplay frame in 2.5D onto ``screen``. False
    when the renderer failed (2.5D is off now; the caller draws 2D)."""
    cam_x, cam_y = int(round(fcx)), int(round(fcy))
    _d._M2_CAM[0], _d._M2_CAM[1] = cam_x, cam_y
    v = td.View(CAM, fcx + WIDTH / 2.0, fcy + HEIGHT / 2.0)
    _tick()
    if not render_world(screen, v):
        return False
    _d._PROJ[0] = v
    try:
        _d._draw_interactables(screen, cam_x, cam_y, props=False)
        _d._draw_gantry_dynamic(screen, cam_x, cam_y, figure=False)
        _d._draw_flank_cutscene(screen, cam_x, cam_y, figure=False)
    finally:
        _d._PROJ[0] = None
    _labels(screen, v)
    p = STATE.player
    if p is not None:
        pt = v.screen_sim(p.rect.centerx, p.rect.centery)
        if pt is not None:
            _d._draw_shelter_arrow(screen, p.rect.centerx - pt[0], p.rect.centery - pt[1])
    if STATE.muzzle_flash_timer > 0:
        STATE.muzzle_flash_timer -= 1
    _d._draw_screen_passes(cam_x, cam_y, world3d=True,
                           proj=lambda x, y: v.screen_sim(x, y))
    return True


def _tick():
    """The timers the 2D world passes age: blood fade and the abandoned
    nest's glow. The 3D frame ages them the same."""
    for decal in STATE.blood_decals[:]:
        decal[2] -= 0.25
        if decal[2] <= 0:
            STATE.blood_decals.remove(decal)
    nest = getattr(STATE, "mission2_abandoned_nest", None)
    if nest:
        nest["age"] = nest.get("age", 0) + 1


def render_world(surface, v):
    """Draw the M2 set and cast through view ``v`` onto ``surface``."""
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
        first = _w.static_scene(r, ("m2_td3d", id(MISSION2_MAP)))
        ok = False
        try:
            if first:
                _build_set(r)
            ok = True
        finally:
            _w.static_end(r, ok)
        flashes = []
        _draw_walls(r)
        _draw_vehicles(r, flashes, tm)
        _draw_tanker(r, flashes, tm)
        _draw_blast(r, flashes, tm)
        _draw_story_props(r, flashes, tm)
        _draw_evidence_props(r, tm)
        _draw_gantry_cast(r, flashes, tm)
        _draw_cast(r, flashes, tm)
        _draw_fx(r, flashes, tm)
        dyn = _m1._flash_lights(flashes, tm) + _blast_lights()
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
    _grade.apply(surface, v, _night_lights() + dyn, ambient=AMBIENT)
    return True


# ── helpers ────────────────────────────────────────────────────────────

def _glyph(col, row):
    if 0 <= row < MAP_H and 0 <= col < len(MISSION2_MAP[row]):
        return MISSION2_MAP[row][col]
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


def _tinted(m, tint, glow_ok=False):
    """A copy of mesh ``m`` mixed toward ``tint`` = (colour, amount); the
    emissive faces go dark unless ``glow_ok``."""
    from engine3d import Mesh
    col, k = tint
    out = Mesh()
    out.verts = list(m.verts)
    out.faces = [(f[0], td.mix(f[1], col, k), f[2], f[3], f[4] and glow_ok) for f in m.faces]
    return out


def _moved(m, x, z):
    """Mesh ``m`` shifted to (x, 0, z), for static batches that take world meshes."""
    from engine3d import Mesh
    out = Mesh()
    out.add(m, t=(x, 0.0, z))
    return out


def _floor_tex(col, name="pavement"):
    from engine3d import tex
    return tex(name, like=tuple(max(0, min(255, int(c))) for c in col), tint=True)


def _tile_col(col, row, base):
    k = 1.0 + (_hash(col, row, 9) - 4) * 0.011
    lean = (_hash(col + 3, row + 11, 5) - 2) * 0.006
    return (base[0] * k * (1.0 + lean), base[1] * k, base[2] * k * (1.0 - lean))


def _floor_at(col, row):
    """(colour, texture name) of the ground tile."""
    if _GARDEN.collidepoint(col, row) and row <= 6:
        if _PATH.collidepoint(col, row):
            wear = 1.0 - abs(col - 59) / 5.0
            b = 118 + int(wear * 14)
            return (b, b, b - 6), "concrete"
        return GRASS, "m7_grass"
    if _glyph(col, row) == "O":
        return LOT, "concrete"
    return ASPHALT, "pavement"


# ── static set ─────────────────────────────────────────────────────────

def _build_set(r):
    from cutscenes import m6world3d as _w
    from engine3d import quad_xz
    for row in range(MAP_H):
        for col in range(MAP_W):
            base, name = _floor_at(col, row)
            _w.add(r, quad_xz(col * T * K, -(row + 1) * T * K, (col + 1) * T * K, -row * T * K, 0.0,
                              _floor_tex(_tile_col(col, row, base), name), layer=0))
    _paint(r)
    for row in range(MAP_H):
        for col in range(MAP_W):
            if _glyph(col, row) == "B":
                _barrier(r, col, row)
    _garden(r)
    _shelter(r)
    _gantry(r)
    for kind, ptx, pty, arg in _d._M2_DRESSING_PROPS:
        if _d._m2_prop_overlaps_solid(kind, ptx, pty, arg):
            continue
        x2, y2 = ptx * T + T / 2.0, pty * T + T / 2.0
        if kind in ("crates", "barrels", "coil"):
            _m1._dressing(r, kind, x2, y2, arg)
        else:
            _w.add(r, _cart_mesh(kind, *_tc(ptx, pty)[::2]))
    for col, row in _POSTS:
        _street_lamp(r, col, row)
    for col, row in _FLOODS:
        x, _, z = _tc(col, row)
        col3 = (255, 230, 180) if row == 34 else (220, 230, 255)
        _m1._lamp_fixture(r, "fl_m2", col * T + T / 2.0, row * T + T / 2.0 + 0.9 / K, col3)


def _paint(r):
    """Lane dashes, toll stop bars, shoulder ticks, the lot's seams."""
    from cutscenes import m6world3d as _w
    from engine3d import quad_xz
    y = 0.006
    for col in _LANE_COLS:
        x = col * T + 32
        for y0 in range(0, MAP_H * T, 150):
            row = (y0 + 36) // T
            if _glyph(col, row) not in (".", "s", "d", "g"):
                continue
            _w.add(r, quad_xz((x - 2.5) * K, -(y0 + 72) * K, (x + 2.5) * K, -y0 * K, y, LANE, layer=1))
    for row in (31, 36):
        for col in range(20, 54):
            if _glyph(col, row) != ".":
                continue
            bx, by = col * T + 6, row * T + 50
            _w.add(r, quad_xz(bx * K, -(by + 4) * K, (bx + 52) * K, -by * K, y, STOP, layer=1))
    for row in range(MAP_H):
        for col, odd, ox, oy in ((17, 0, 2, 6), (53, 1, 59, 24)):
            if row % 2 == odd and _glyph(col, row) == ".":
                x0, y0 = col * T + ox, row * T + oy
                _w.add(r, quad_xz(x0 * K, -(y0 + 34) * K, (x0 + 3) * K, -y0 * K, y, SHOULDER, layer=1))
    for col in range(_PATH.left, _PATH.right + 1):     # garden path slabs, one per tile
        _w.add(r, quad_xz(col * T * K - 0.015, -_PATH.bottom * T * K, col * T * K + 0.015,
                          -_PATH.top * T * K, y, (84, 84, 80), layer=1))
    for row in range(_PATH.top, _PATH.bottom + 1):
        _w.add(r, quad_xz(_PATH.left * T * K, -row * T * K - 0.015, _PATH.right * T * K,
                          -row * T * K + 0.015, y, (84, 84, 80), layer=1))
    seam = (51, 60, 62)
    for row in range(MAP_H):
        for col in range(MAP_W):
            if _glyph(col, row) != "O" or col % 2 or row % 2:
                continue
            x0, y0 = col * T * K, -row * T * K
            _w.add(r, quad_xz(x0 - 0.012, y0 - 2 * T * K, x0 + 0.012, y0, 0.004, seam, layer=1))
            _w.add(r, quad_xz(x0, y0 - 0.012, x0 + 2 * T * K, y0 + 0.012, 0.004, seam, layer=1))


def _barrier(r, col, row):
    """Jersey barrier on the 2D collision rect (x+4, y+12, 56, 40)."""
    from cutscenes import m6world3d as _w
    from engine3d import box, tex
    x, _, z = to3(col * T + 32, row * T + 32)
    w, d = 56 * K, 40 * K
    shade = 60 + _hash(col, row, 34)
    body = tex("concrete", like=(shade, shade, shade - 4))
    _w.add(r, box(w, 0.3, d, body, center=(x, 0.15, z)))
    _w.add(r, box(w, BARRIER_H - 0.3, d * 0.55, body, center=(x, 0.3 + (BARRIER_H - 0.3) / 2.0, z),
                  cols={"top": (98, 96, 88)}))
    if col in (16, 54):
        _w.add(r, box(0.2, 1.1, 0.2, (40, 42, 40), center=(x, 0.55, z)))
        ref = (200, 60, 50) if row % 2 else (220, 220, 210)
        _w.add(r, box(0.08, 0.08, 0.02, ref, center=(x, 0.95, z - 0.11), emissive=True))


def _street_lamp(r, col, row):
    """Guardrail lamp post with the arm out over its light tile."""
    from cutscenes import m6world3d as _w
    from engine3d import box
    metal = (30, 31, 34)
    x, _, z = _tc(col, row)
    hx = x + (0.9 if col == 16 else -0.9 if col == 54 else 0.0)
    h = 3.6
    _w.add(r, box(0.12, h, 0.12, metal, center=(x, h / 2.0, z)))
    if hx != x:
        _w.add(r, box(abs(hx - x), 0.08, 0.08, metal, center=((x + hx) / 2.0, h, z)))
    _w.add(r, box(0.36, 0.12, 0.24, metal, center=(hx, h - 0.04, z)))
    _w.add(r, box(0.28, 0.03, 0.18, (210, 225, 255), center=(hx, h - 0.11, z), emissive=True))


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


def _garden(r):
    """Hedges, fountain, benches, lanterns, trees and the iron fence."""
    from cutscenes import m6world3d as _w
    from engine3d import Mesh, box, disc_xz, rot_y, tex
    leaf = tex("m7_leaf", like=(34, 68, 34))
    for rect in GARDEN_HEDGE_RECTS:
        x, _, z = to3(*rect.center)
        w, d = rect.w * K - 0.2, rect.h * K - 0.2
        _w.add(r, box(w, 1.0, d, leaf, center=(x, 0.5, z), cols={"top": (50, 92, 46)}))
        _w.add(r, box(w - 0.3, 0.12, d - 0.3, (62, 108, 56), center=(x, 1.06, z)))
    x, _, z = to3(*GARDEN_FOUNTAIN_RECT.center)
    rad = GARDEN_FOUNTAIN_RECT.w * K / 2.0
    stone = tex("m7_stone", like=(128, 124, 116))
    _w.add(r, disc_xz(x, z, rad * 1.12, 0.012, (70, 72, 70), n=16, layer=1))
    _w.add(r, disc_xz(x, z, rad * 0.9, 0.3, (52, 118, 160), n=16, layer=2))
    rim = Mesh()
    for i in range(16):                               # basin rim, one stone block per side
        rim.add(box(rad * 0.4, 0.5, 0.24, stone, center=(rad * 0.94, 0.25, 0.0),
                    cols={"top": (150, 146, 138)}), m=rot_y(i * 22.5))
    _w.add(r, _moved(rim, x, z))
    _w.add(r, box(0.3, 1.1, 0.3, stone, center=(x, 0.55, z)))
    _w.add(r, disc_xz(x, z, 0.55, 1.1, stone, n=10, layer=2))
    _w.add(r, disc_xz(x, z, 0.45, 1.11, (60, 120, 160), n=10, layer=2))
    for rect in GARDEN_BENCH_RECTS:
        x, _, z = to3(*rect.center)
        wood = tex("crate", like=(110, 80, 50))
        _w.add(r, box(rect.w * K, 0.06, 0.45, wood, center=(x, 0.45, z)))
        _w.add(r, box(rect.w * K, 0.4, 0.06, wood, center=(x, 0.7, z + 0.22)))
        for sx in (-0.65, 0.65):
            _w.add(r, box(0.06, 0.45, 0.45, (40, 40, 44), center=(x + sx, 0.22, z)))
    for rect in GARDEN_LAMP_RECTS:
        x, _, z = to3(*rect.center)
        _w.add(r, box(0.1, 2.3, 0.1, (30, 30, 34), center=(x, 1.15, z)))
        _w.add(r, box(0.26, 0.32, 0.26, (30, 30, 34), center=(x, 2.4, z)))
        _w.add(r, box(0.18, 0.22, 0.18, (255, 230, 170), center=(x, 2.4, z), emissive=True))
    bark = tex("m7_bark", like=(70, 52, 36))
    for rect in GARDEN_TREE_RECTS:
        x, _, z = to3(*rect.center)
        _w.add(r, box(0.26, 2.0, 0.26, bark, center=(x, 1.0, z)))
        for i, (s, y) in enumerate(((1.7, 2.3), (1.3, 2.9), (0.8, 3.4))):
            _w.add(r, box(s, 0.6, s, tex("m7_leaf", like=td.mix((28, 60, 30), (54, 96, 48), i / 2.0)),
                          center=(x, y, z)))
    iron = (55, 55, 60)
    x0, x1 = 51 * T * K, 68 * T * K
    z0, z1 = -9 * T * K, -1 * T * K
    fh = 1.1
    for zz in (z0, z1):
        _w.add(r, box(x1 - x0, 0.04, 0.04, iron, center=((x0 + x1) / 2.0, fh, zz)))
        _w.add(r, box(x1 - x0, fh, 0.01, tex("metal_rib", like=(44, 44, 48)),
                      center=((x0 + x1) / 2.0, fh / 2.0, zz)))
    for xx in (x0, x1):
        _w.add(r, box(0.04, 0.04, z1 - z0, iron, center=(xx, fh, (z0 + z1) / 2.0)))
        _w.add(r, box(0.01, fh, z1 - z0, tex("metal_rib", like=(44, 44, 48)),
                      center=(xx, fh / 2.0, (z0 + z1) / 2.0)))
    for xx in (x0, x1):
        for zz in (z0, z1):
            _w.add(r, box(0.15, fh + 0.2, 0.15, (70, 68, 64), center=(xx, (fh + 0.2) / 2.0, zz)))
    for i in range(24):                               # flower beds along the north and south rows
        col = ((200, 60, 70), (230, 200, 70), (190, 120, 220), (240, 240, 230))[i % 4]
        fx = (51.5 + i * 0.7) * T
        for fy in (1.4 * T, 7.4 * T):
            x, _, z = to3(fx + _hash(i, int(fy), 20), fy + _hash(int(fy), i, 24))
            _w.add(r, box(0.14, 0.18, 0.14, col, center=(x, 0.09, z)))


def _shelter(r):
    """Concrete pad, the crescent blast wall on its collision rects, sandbags."""
    from cutscenes import m6world3d as _w
    from engine3d import box, quad_xz, tex
    sx, sy = SAFE_ZONE
    _w.add(r, quad_xz((sx - 56) * K, -(sy + 48) * K, (sx + 56) * K, -(sy - 48) * K, 0.008,
                      _floor_tex((88, 85, 78), "concrete"), layer=1))
    for x0, x1, y0, y1 in ((sx - 56, sx + 56, sy - 48, sy - 46), (sx - 56, sx + 56, sy + 46, sy + 48),
                           (sx - 56, sx - 54, sy - 48, sy + 48), (sx + 54, sx + 56, sy - 48, sy + 48)):
        _w.add(r, quad_xz(x0 * K, -y1 * K, x1 * K, -y0 * K, 0.01, (60, 58, 54), layer=1))
    wall = tex("concrete", like=(130, 124, 114))
    for rect in getattr(STATE, "mission2_shelter_walls", ()):
        x, _, z = to3(*rect.center)
        _w.add(r, box(rect.w * K + 0.04, SHELTER_H, rect.h * K + 0.04, wall,
                      center=(x, SHELTER_H / 2.0, z), cols={"top": (150, 144, 132)}))
    for i in range(5):
        x, _, z = to3(sx - 44 + i * 9, sy + 30)
        _w.add(r, box(0.34, 0.2, 0.22, (95, 80, 55), center=(x, 0.1 + 0.18 * (i % 2), z)))
    x, _, z = to3(sx - 30, sy - 20)
    _w.add(r, box(0.6, 0.5, 0.5, tex("crate", like=(110, 88, 52)), center=(x, 0.25, z)))
    _w.add(r, box(0.5, 0.04, 0.06, (100, 160, 220), center=(x, 0.4, z - 0.26), emissive=True))


def _gantry(r):
    """Sign gantry over the lot: two steel legs on the C tiles of row 27,
    the deck at ``DECK_H`` across cols 55-61, rails and two route signs."""
    from cutscenes import m6world3d as _w
    from engine3d import box, tex
    steel = tex("steel", like=STEEL)
    for col, row in _TOWERS:
        x, _, z = _tc(col, row)
        for dx in (-0.25, 0.25):
            _w.add(r, box(0.14, DECK_H, 0.14, steel, center=(x + dx, DECK_H / 2.0, z)))
        for k in range(1, 5):
            _w.add(r, box(0.5, 0.05, 0.05, steel, center=(x, DECK_H * k / 5.0, z)))
    x0, x1 = 55 * T * K, 62 * T * K
    zc = -(26.5 + 0.5) * T * K
    deck = 1.4
    _w.add(r, box(x1 - x0, 0.12, deck, tex("metal_rib", like=(70, 74, 76)),
                  center=((x0 + x1) / 2.0, DECK_H, zc)))
    for dz in (-deck / 2.0, deck / 2.0):
        _w.add(r, box(x1 - x0, 0.04, 0.04, steel, center=((x0 + x1) / 2.0, DECK_H + 0.9, zc + dz)))
        for i in range(8):
            _w.add(r, box(0.04, 0.9, 0.04, steel, center=(x0 + i * (x1 - x0) / 7.0, DECK_H + 0.45, zc + dz)))
    for cx in (56.6, 59.8):
        x = cx * T * K
        _w.add(r, box(2.6, 1.0, 0.08, SIGN, center=(x, DECK_H - 0.7, zc - deck / 2.0 - 0.05)))
        for i, w in enumerate((1.8, 1.1)):
            _w.add(r, box(w, 0.14, 0.01, (220, 226, 220), center=(x, DECK_H - 0.5 - i * 0.36,
                                                                     zc - deck / 2.0 - 0.095)))


# ── walls (per frame) ──────────────────────────────────────────────────

def _wall_kind(col, row):
    if _glyph(col, row) != "C":
        return None
    if row in (0, MAP_H - 1) or col in (0, MAP_W - 1):
        return "border"
    if (col, row) in _TOWERS:
        return "tower"
    if _BUILD.collidepoint(col, row):
        return "facade"
    if _HUT.collidepoint(col, row):
        return "hut"
    return "booth"


def _wall_boxes():
    """Merged wall boxes (col, row, w, h, kind, var) in tiles: horizontal
    runs, then identical runs stacked down."""
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
            runs[(row, col)] = [kind, col, row, end + 1 - col, 1]
            col = end + 1
    out = []
    for row in range(MAP_H):
        for key in sorted(k for k in runs if k[0] == row):
            run = runs.pop(key, None)
            if run is None:
                continue
            kind, c0, r0, w, h = run
            while True:
                below = runs.get((r0 + h, c0))
                if below is None or below[0] != kind or below[3] != w:
                    break
                runs.pop((r0 + h, c0))
                h += 1
            out.append((c0, r0, w, h, kind, 0))
    _cache["walls"] = out
    return out


_LOOK = {"border": ("concrete", (96, 92, 86), (70, 68, 64)),
         "facade": ("concrete", FACADE, FACADE_CAP),
         "hut": ("concrete", WALL, WALL_CAP),
         "booth": ("concrete", WALL, WALL_CAP),
         "tower": ("steel", STEEL, (40, 42, 44))}


def _wall_mesh(kind, w, d, hgt):
    key = ("wall", kind, round(w, 3), round(d, 3), hgt)
    m = _cache["meshes"].get(key)
    if m is not None:
        return m
    from engine3d import Mesh, box, tex
    name, body, cap = _LOOK[kind]
    cut = hgt < WALL_H[kind] - 0.01
    m = Mesh()
    if kind == "tower":
        if not cut:
            return m                                  # the static gantry legs stand here
        m.add(box(0.6, hgt, 0.6, tex(name, like=body), center=(0.0, hgt / 2.0, 0.0),
                  cols={"top": CUT_CAP}))
        _cache["meshes"][key] = m
        return m
    m.add(box(w, hgt, d, tex(name, like=body), center=(0.0, hgt / 2.0, 0.0),
              cols={"top": CUT_CAP if cut else cap}))
    for y0, y1, k in _m1.WALL_SHADE:
        y1 = min(y1, hgt - 0.02)
        if y1 > y0:
            m.add(box(w + 0.02, y1 - y0, d + 0.02, tex(name, like=_shade(body, k)),
                      center=(0.0, (y0 + y1) / 2.0, 0.0), skip=("top", "bottom")))
    if not cut:
        m.add(box(w + 0.06, 0.14, d + 0.06, _shade(cap, 0.8), center=(0.0, hgt - 0.07, 0.0)))
        if kind == "booth":
            m.add(box(w + 0.03, 0.7, d + 0.03, GLASS, center=(0.0, 1.45, 0.0), skip=("top", "bottom")))
            m.add(box(w + 0.4, 0.12, d + 0.4, (60, 62, 60), center=(0.0, hgt + 0.06, 0.0)))
    _cache["meshes"][key] = m
    return m


def _draw_walls(r):
    """Wall boxes at full height, except the stretch between the camera
    and Biribel, which sinks to a stub (the M1 cutaway)."""
    zone = _m1._cut_zone()
    snap = _m1._cut_snap()

    def level(c, row):
        k = _m1._cut_level(("m2", c, row), _m1._hides(zone, c * T, row * T, (c + 1) * T, (row + 1) * T),
                           snap)
        return round(k * 8) / 8.0

    for c0, r0, w, h, kind, _var in _wall_boxes():
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
            full = WALL_H[kind]
            hgt = STUB_H + (full - STUB_H) * levels[i]
            cx, _, cz = to3((sc + sw / 2.0) * T, (sr + sh / 2.0) * T)
            m = _wall_mesh(kind, sw * T * K, sh * T * K, hgt)
            if m.faces:
                _put(r, m, (cx, 0.0, cz))
            if levels[i] >= 1.0 and kind == "facade":
                for tc in range(sc, sc + sw):
                    for tr in range(sr, sr + sh):
                        _facade_window(r, tc, tr)
            i = j + 1


def _facade_window(r, col, row):
    """Glass on the control building's outer faces: the south row (three
    lit), the north row and the side columns (bar the side door)."""
    south, north = row == _BUILD.bottom - 1, row == _BUILD.top
    side = col in (_BUILD.left, _BUILD.right - 1) and not (south or north)
    if not (south or north or side) or col in (56, 59) and south:
        return
    lit = south and col in _LIT_WINDOWS
    x, _, z = _tc(col, row)
    s = T * K / 2.0
    if south:
        pos, yaw = (x, 0.0, z - s - 0.02), 0.0
    elif north:
        pos, yaw = (x, 0.0, z + s + 0.02), 0.0
    else:
        pos, yaw = (x + (s + 0.02) * (-1 if col == _BUILD.left else 1), 0.0, z), 90.0
    _put(r, _mesh(("win", lit), lambda: _window_mesh(lit)), pos, yaw=yaw)


def _window_mesh(lit):
    from engine3d import Mesh, box
    m = Mesh()
    m.add(box(1.1, 0.9, 0.04, LIT_GLASS if lit else GLASS, center=(0.0, 1.85, 0.0), emissive=lit))
    m.add(box(1.24, 0.07, 0.08, FRAME, center=(0.0, 1.37, 0.0)))
    m.add(box(1.24, 0.07, 0.08, FRAME, center=(0.0, 2.33, 0.0)))
    return m


# ── vehicles and the tanker ────────────────────────────────────────────

CAR_LEN = 2.97                     # car_m2 nose to tail at its import scale


def _car_mesh(pal, burned=0.0):
    """car_m2 with the paint faces recoloured to palette ``pal`` (index into
    ``draw._CIVILIAN_CAR_PALETTES``), ``burned`` 0..1 toward a charred shell."""
    key = ("car", pal, round(burned, 1))
    m = _cache["meshes"].get(key)
    if m is not None:
        return m
    from engine3d import Mesh
    try:
        from game.render3d_bridge import load_mesh_asset
        verts, faces = load_mesh_asset("car_m2")
    except (OSError, ValueError):
        m = _m1._sedan(_d._CIVILIAN_CAR_PALETTES[pal]["body"])
        _cache["meshes"][key] = m
        return m
    body = _d._CIVILIAN_CAR_PALETTES[pal]["body"]
    paint = [sum(f[1]) for f in faces if f[2] == 3]
    base = (sum(paint) / float(len(paint))) if paint else 1.0
    m = Mesh()
    m.verts = [tuple(v) for v in verts]
    burned = round(burned, 1)
    for idx, col, grp in faces:
        col = tuple(col)
        if grp == 3:
            col = _shade(body, sum(col) / base)
        if burned:
            col = td.mix(col, CHAR[0], CHAR[1] * burned)
        m.faces.append((tuple(idx), col, 2, True, grp in (1, 2) and burned < 0.5))
    _cache["meshes"][key] = m
    return m


def _draw_vehicles(r, flashes, tm):
    for veh in STATE.mission2_vehicles:
        rect = veh["rect"]
        ox, oy = veh.get("blast_offset", (0, 0)) if veh.get("blast_charred") else (0, 0)
        x, _, z = to3(rect.centerx + ox, rect.centery + oy)
        kind = veh["kind"]
        r.add_sprite((x, 0.02, z), td.shadow(rect.w * K / 2.0 + 0.1, rect.h * K / 2.0 + 0.1, 150), layer=0)
        if kind == "ipa_truck":
            truck = _mesh("truck_ipa", lambda: _tinted(_m1._truck(), ((104, 78, 58), 0.5), True))
            if veh.get("blast_charred"):
                truck = _mesh("truck_charred", lambda: _tinted(_m1._truck(), CHAR))
            _put(r, truck, (x, 0.0, z))
            continue
        pal = _d._CIVILIAN_CAR_PALETTES.index(_d._car_palette(rect))
        burn = 1.0 if kind == "burned" else veh.get("burn_progress", 0.0) if veh.get("burning") else 0.0
        _put(r, _car_mesh(pal, burn), (x, 0.0, z), scale=rect.w * K / CAR_LEN)
        if veh.get("burning") and burn < 1.0:
            seed = rect.x
            for i in range(3):
                _m1._fire(r, (x - 0.9 + i * 0.9, 0.8, z), tm, seed + i, 0.25 + 0.35 * burn)
            flashes.append({"pos": (x, 1.2, z), "color": FIRE, "intensity": 0.6 + 0.6 * burn,
                            "range": 4.0})
        elif kind != "burned":
            for side in (-1, 1):
                p = (x - rect.w * K / 2.0 - 0.05, 0.7, z + side * 0.45)
                r.add_sprite(p, _glow((226, 44, 32), 0.08, tm, 0.6, 6), layer=_fx_layer())


def _glow(col, size, tm, k=0.8, px=16, **kw):
    from cutscenes import m6fx3d as _fx
    return _fx.glow(col, size, tm, intensity=k, max_px=px, **kw)


def _fx_layer():
    from cutscenes import m6fx3d as _fx
    return _fx.FX_LAYER


def _tanker_mesh(inspected_led=False):
    """IPA fuel tanker, nose west like the 2D sprite: a cab on the west 18%
    of the rect and an octagonal tank on a chassis."""
    from engine3d import Mesh, box, prism, rot_y
    tk = STATE.mission2_tanker_rect
    L, W = tk.w * K, tk.h * K * 0.62
    m = Mesh()
    cab_l = L * 0.18
    x_cab = -L / 2.0 + cab_l / 2.0
    m.add(box(L, 0.35, W * 0.8, (28, 28, 30), center=(0.0, 0.55, 0.0)))
    m.add(box(cab_l, 1.9, W, (96, 72, 56), center=(x_cab, 1.25, 0.0),
              cols={"top": (100, 78, 64)}))
    m.add(box(0.04, 0.6, W * 0.8, GLASS, center=(-L / 2.0 - 0.01, 1.7, 0.0)))
    rad = W * 0.5
    ring = [(math.cos(a) * rad, math.sin(a) * rad) for a in
            [math.pi / 8 + i * math.pi / 4 for i in range(8)]]
    tank_l = L - cab_l - 0.3
    tank = prism([(x, y + 0.8 + rad) for x, y in ring], tank_l, TANK,
                 z0=-tank_l / 2.0, cols={"front": (96, 94, 88), "back": (96, 94, 88)})
    m.add(tank, m=rot_y(90.0), t=(cab_l / 2.0 + 0.15, 0.0, 0.0))
    for i in range(4):
        m.add(box(0.08, rad * 2 + 0.06, W + 0.04, (80, 78, 72),
                  center=(-L / 2.0 + cab_l + 0.6 + i * (tank_l - 0.9) / 3.0, 0.8 + rad, 0.0),
                  skip=("bottom",)))
    m.add(box(1.4, 0.5, 0.01, (220, 160, 60), center=(cab_l / 2.0, 0.8 + rad, -W / 2.0 - 0.03)))
    for wx in (-L / 2.0 + cab_l * 0.5, L * 0.12, L * 0.36):
        for side in (-1, 1):
            m.add(box(0.8, 0.8, 0.3, (16, 16, 18), center=(wx, 0.4, side * (W * 0.42))))
    if inspected_led:
        m.add(box(0.1, 0.1, 0.02, (90, 255, 120), center=(x_cab + 0.3, 1.5, -W / 2.0 - 0.02),
                  emissive=True))
    return m


def _wreck_mesh():
    """The burnt-out tanker: chassis, split lower shell, ribs standing up
    from ``mission2_tanker_wreckage_ribs``."""
    from engine3d import Mesh, box
    tk = STATE.mission2_tanker_rect
    L, W = tk.w * K, tk.h * K * 0.62
    m = Mesh()
    black, rust = (24, 21, 19), (60, 34, 24)
    m.add(box(L * 0.95, 0.35, W * 0.8, black, center=(0.0, 0.45, 0.0)))
    m.add(box(L * 0.16, 1.1, W * 0.9, (34, 28, 24), center=(-L * 0.4, 0.95, 0.0)))
    for side in (-1, 1):
        m.add(box(L * 0.66, 0.6, 0.12, rust, center=(L * 0.1, 0.95, side * W * 0.42)))
    ribs = getattr(STATE, "mission2_tanker_wreckage_ribs", ()) or [(0, 4)] * 8
    for i, (dx, top) in enumerate(ribs):
        x = -L * 0.22 + i * (L * 0.66) / max(1, len(ribs) - 1) + dx * K
        h = 0.8 + top * 0.12
        for side in (-1, 1):
            m.add(box(0.1, h, 0.1, td.mix(black, rust, (i % 3) / 3.0),
                      center=(x, 0.6 + h / 2.0, side * W * 0.36)))
        m.add(box(0.1, 0.1, W * 0.72, black, center=(x, 0.6 + h, 0.0)))
    return m


def _draw_tanker(r, flashes, tm):
    tk = STATE.mission2_tanker_rect
    x, _, z = to3(tk.centerx, tk.centery)
    if getattr(STATE, "mission2_tanker_destroyed", False) or getattr(STATE, "mission2_tanker_exploded", False):
        _put(r, _mesh(("wreck", id(getattr(STATE, "mission2_tanker_wreckage_ribs", None))), _wreck_mesh),
             (x, 0.0, z))
        return
    if tk not in STATE.walls:
        return
    r.add_sprite((x, 0.02, z), td.shadow(tk.w * K / 2.0, tk.h * K * 0.36, 150), layer=0)
    led = (getattr(STATE, "mission2_tanker_inspected", False) and (tm // 400) % 2 == 0)
    _put(r, _mesh(("tanker", led), lambda: _tanker_mesh(led)), (x, 0.0, z))


# ── tanker blast ───────────────────────────────────────────────────────

def _blast_k():
    """(timer, light radius px, light intensity) of the 2D blast light, or None."""
    if not getattr(STATE, "mission2_tanker_exploded", False):
        return None
    bt = getattr(STATE, "mission2_tanker_blast_timer", 0)
    if bt < 40:
        return bt, 520, 1.2
    if bt < 130:
        return bt, 360, 0.6
    return bt, 170, 0.28


def _scorch_mesh(cx, cy, rad):
    """Ground burn: a charred disc, the 2D radial streaks and cracks."""
    from engine3d import Mesh, disc_xz
    m = Mesh()
    x, _, z = to3(cx, cy)
    rr = rad * K
    for k, col, y in ((1.0, (26, 24, 23), 0.006), (0.62, (18, 16, 15), 0.007), (0.3, (12, 10, 10), 0.008)):
        m.add(disc_xz(x, z, rr * k * 0.55, y, col, n=24, layer=1,
                      wobble=[0.82 + 0.18 * math.sin(i * 2.7 + k * 5) for i in range(24)]))
    for ang, r0, r1, w in getattr(STATE, "mission2_tanker_blast_streaks", ()):
        ca, sa = math.cos(ang), math.sin(ang)
        nx, ny = -sa, ca
        pts = []
        for rr0, ww in ((r0, w), (r1, 1.5)):
            for s in (-1, 1):
                px, py = cx + ca * rr0 + nx * ww * 0.5 * s, cy + sa * rr0 * 0.85 + ny * ww * 0.5 * s
                pts.append(to3(px, py, 0.009))
        m.face([pts[0], pts[1], pts[3], pts[2]], (20, 18, 17), 1, True)
    for segs in getattr(STATE, "mission2_tanker_asphalt_cracks", ()):
        prev = None
        for ang, rr0, jit in segs:
            p = (cx + math.cos(ang) * rr0 + jit, cy + math.sin(ang) * rr0 * 0.85)
            if prev is not None:
                a, b = to3(prev[0], prev[1], 0.01), to3(p[0], p[1], 0.01)
                dx, dz = b[0] - a[0], b[2] - a[2]
                n = math.hypot(dx, dz) or 1.0
                ox, oz = -dz / n * 0.02, dx / n * 0.02
                m.face([(a[0] - ox, 0.01, a[2] - oz), (a[0] + ox, 0.01, a[2] + oz),
                        (b[0] + ox, 0.01, b[2] + oz), (b[0] - ox, 0.01, b[2] - oz)], (58, 56, 52), 1, True)
            prev = p
    from engine3d import box
    for piece in (list(getattr(STATE, "mission2_tanker_debris_field", ())) +
                  list(getattr(STATE, "mission2_tanker_outer_debris", ()))):
        s = piece.get("size", 4) * K * 1.6
        px, _, pz = to3(piece["x"], piece["y"])
        m.add(box(s, s * 0.5, s * 0.7, piece.get("color", (40, 35, 30)), center=(px, s * 0.25, pz)))
    return m


def _draw_blast(r, flashes, tm):
    bk = _blast_k()
    if bk is None:
        return
    bt, rad_px, k = bk
    tk = STATE.mission2_tanker_rect
    cx, cy = tk.centerx, tk.centery
    x, _, z = to3(cx, cy)
    sc = getattr(STATE, "mission2_tanker_scorch", None)
    if sc:
        key = ("scorch", sc, id(getattr(STATE, "mission2_tanker_blast_streaks", None)))
        _put(r, _mesh(key, lambda: _scorch_mesh(*sc)), (0.0, 0.0, 0.0))
    from cutscenes import m6fx3d as _fx
    fb = getattr(STATE, "mission2_tanker_fireball_radius", 0) * K
    if bt < 250 and fb > 0:                           # the 2D fireball burns 250 frames
        fade = 1.0 if bt < 45 else max(0.0, 1.0 - (bt - 45) / 205.0)
        lift = 1.0 + bt * 0.05
        r.add_sprite((x, lift + fb * 0.25, z),
                     _fx.glow((255, 150, 60), fb * 0.55, tm, core=(255, 246, 214), flicker=0.1,
                              seed=7, intensity=1.4 * fade, max_px=520), layer=_fx.FX_LAYER)
        n = 10
        for i in range(n):
            a = i * math.tau / n + bt * 0.01
            d = fb * 0.45 * (0.6 + 0.4 * ((i * 7) % 5) / 4.0)
            _m1._fire(r, (x + math.cos(a) * d, lift * 0.5, z + math.sin(a) * d * 0.85), tm, 90 + i,
                      min(1.7, 0.6 + fb * 0.08) * fade, glow=False)
        _m1._fire(r, (x, 0.2, z), tm, 89, min(2.2, 1.0 + fb * 0.1) * fade)
    sw = getattr(STATE, "mission2_tanker_shockwave_radius", 0) * K
    if 0 < bt <= 60 and sw > 0:
        a = max(0.0, 1.0 - bt / 60.0)
        col = td.mix((40, 30, 24), (255, 220, 170), a)
        td.ring(r, x, z, sw, col, n=48, width=3, y=0.2)
        td.ring(r, x, z, sw * 0.92, td.mix((30, 24, 20), (255, 160, 80), a), n=40, width=2, y=0.1)
    from engine3d import box
    for ch in getattr(STATE, "mission2_tanker_debris_chunks", ()):
        gy = ch.get("ground_y", ch["y"])
        h = max(0.05, (gy - ch["y"]) * K)
        px, _, pz = to3(ch["x"], gy)
        s = ch.get("size", 6) * K * 1.4
        col = tuple(ch.get("color", (40, 35, 30)))[:3]
        _put(r, _mesh(("chunk", round(s, 2), col), lambda s=s, col=col: box(s, s * 0.6, s * 0.8, col,
                                                                            center=(0.0, 0.0, 0.0))),
             (px, h, pz), yaw=(ch.get("age", 0) * 17) % 360, pitch=(ch.get("age", 0) * 23) % 360)
        if ch.get("age", 0) < 50:
            r.add_sprite((px, h, pz), _glow((255, 150, 60), 0.18, tm, 0.9, 12), layer=_fx.FX_LAYER)
    if bt > 20:
        for i, sf in enumerate(getattr(STATE, "mission2_tanker_spot_fires", ())):
            _m1._fire(r, to3(sf["x"], sf["y"]), tm, 200 + i, 0.18 + sf.get("size", 18) * 0.012)
        heat = 1.0 if bt < 400 else max(0.45, 1.0 - (bt - 400) / 1200.0)
        for i in range(5):
            a = i * 1.26
            _m1._fire(r, (x + math.cos(a) * 1.6, 0.6, z + math.sin(a) * 0.9), tm, 300 + i, 0.55 * heat,
                      glow=i == 0)
    flashes.append({"pos": (x, 2.5, z), "color": BLAST, "intensity": 2.0 * k, "range": rad_px * K * 1.2})


def _blast_lights():
    """The 2D blast light (radius and intensity by blast timer) for the grade."""
    bk = _blast_k()
    if bk is None:
        return []
    bt, rad_px, k = bk
    tk = STATE.mission2_tanker_rect
    x, _, z = to3(tk.centerx, tk.centery)
    rad = rad_px * K
    out = [("pool", (x, 0.0, z), BLAST, rad, min(1.0, 0.7 * k)),
           ("glow", (x, 2.0, z), BLAST, rad * 0.5, min(1.0, 0.6 * k))]
    if bt > 20:
        for sf in getattr(STATE, "mission2_tanker_spot_fires", ()):
            fx, _, fz = to3(sf["x"], sf["y"])
            out.append(("pool", (fx, 0.0, fz), FIRE, 1.8, 0.32))
    return out


# ── story props ────────────────────────────────────────────────────────

def _cone_mesh():
    from engine3d import Mesh, box
    m = Mesh()
    m.add(box(0.4, 0.04, 0.4, (40, 36, 30), center=(0.0, 0.02, 0.0)))
    for i, (w, col) in enumerate(((0.26, (232, 110, 30)), (0.2, (230, 230, 220)), (0.14, (232, 110, 30)),
                                  (0.08, (232, 110, 30)))):
        m.add(box(w, 0.14, w, col, center=(0.0, 0.11 + i * 0.14, 0.0)))
    return m


def _prop_mesh(kind):
    from engine3d import Mesh, box
    m = Mesh()
    if kind == "cone":
        return _cone_mesh()
    if kind == "barrel":
        return _m1._barrel(0.0, 0.0, (96, 54, 36))
    if kind == "spark_box":
        m.add(box(0.5, 0.7, 0.3, (82, 86, 88), center=(0.0, 0.35, 0.0), cols={"top": (110, 112, 112)}))
        m.add(box(0.36, 0.4, 0.01, (50, 52, 54), center=(0.0, 0.4, -0.16)))
    elif kind == "broken_camera":
        m.add(box(0.08, 1.6, 0.08, (40, 42, 44), center=(0.0, 0.8, 0.0)))
        m.add(box(0.36, 0.16, 0.18, (30, 30, 32), center=(0.12, 1.5, 0.0)))
        m.add(box(0.03, 0.1, 0.1, (60, 70, 80), center=(0.31, 1.5, 0.0)))
    elif kind == "field_radio":
        m.add(box(0.42, 0.28, 0.24, (64, 70, 52), center=(0.0, 0.14, 0.0), cols={"top": (80, 86, 64)}))
        m.add(box(0.02, 0.7, 0.02, (30, 30, 30), center=(0.16, 0.6, 0.08)))
        m.add(box(0.08, 0.04, 0.02, (90, 220, 120), center=(-0.1, 0.22, -0.13), emissive=True))
    elif kind == "sign":
        m.add(box(0.07, 1.4, 0.07, (50, 52, 54), center=(0.0, 0.7, 0.0)))
        m.add(box(0.8, 0.5, 0.04, (190, 180, 120), center=(0.0, 1.3, -0.04)))
        m.add(box(0.6, 0.08, 0.01, (40, 40, 40), center=(0.0, 1.3, -0.065)))
    elif kind == "flare":
        m.add(box(0.26, 0.05, 0.05, (190, 30, 24), center=(0.0, 0.03, 0.0)))
        m.add(box(0.05, 0.06, 0.06, (255, 120, 90), center=(0.15, 0.03, 0.0), emissive=True))
    return m


def _draw_story_props(r, flashes, tm):
    from engine3d import disc_xz
    for prop in getattr(STATE, "mission2_story_props", ()):
        kind = prop.get("kind")
        x, _, z = to3(*prop["pos"])
        seed = int(prop["pos"][0] * 0.37 + prop["pos"][1])
        if kind in ("soot", "puddle"):
            dark = prop.get("scorched") or prop.get("charred")
            col = (20, 18, 18) if kind == "soot" else (24, 26, 30) if dark else (36, 44, 58)
            rad = 0.6 if kind == "soot" else 0.75
            _put(r, _mesh(("decal", kind, col), lambda col=col, rad=rad: disc_xz(
                0.0, 0.0, rad, 0.006, col, n=12, layer=1,
                wobble=[0.75 + 0.25 * math.sin(i * 2.1) for i in range(12)])), (x, 0.0, z))
            continue
        if kind == "glint":
            p = 0.5 + 0.5 * math.sin(tm * 0.006 + seed)
            r.add_sprite((x, 0.1, z), _glow((255, 240, 200), 0.1, tm, 0.4 + 0.6 * p, 10), layer=_fx_layer())
            continue
        mesh = _mesh(("prop", kind), lambda k=kind: _prop_mesh(k))
        if prop.get("charred"):
            mesh = _mesh(("prop_c", kind), lambda k=kind: _tinted(_prop_mesh(k), CHAR))
        tip = (prop.get("tip_dx", 0), prop.get("tip_dy", 0))
        if tip != (0, 0) and kind in ("cone", "barrel", "sign"):
            yaw = td.yaw_of(math.degrees(math.atan2(tip[1], tip[0])))
            _put(r, mesh, (x, 0.15, z), yaw=yaw, roll=-90.0, scale=1.4 if kind == "cone" else 1.0)
        else:
            _put(r, mesh, (x, 0.0, z), yaw=(seed * 37) % 360 if kind != "sign" else 0.0,
                 scale=1.4 if kind == "cone" else 1.0)
        if kind == "flare":
            f = _m1._flicker(tm, seed)
            r.add_sprite((x + 0.15, 0.08, z), _glow((255, 70, 50), 0.3, tm, 0.9 * f, 22), layer=_fx_layer())
            flashes.append({"pos": (x, 0.4, z), "color": (255, 60, 40), "intensity": 0.9 * f, "range": 4.0})
        elif kind == "spark_box" and (tm // 90 + seed) % 7 == 0:
            r.add_sprite((x, 0.6, z - 0.17), _glow((255, 230, 160), 0.12, tm, 1.0, 12), layer=_fx_layer())
            flashes.append({"pos": (x, 0.6, z), "color": (255, 220, 150), "intensity": 0.7, "range": 2.5})


# ── evidence props: real objects in the 2.5D set ──────────────────────

_EV_PAPER = (214, 204, 172)
_EV_ENVELOPE = (186, 170, 130)
_EV_GREEN = (90, 220, 130)
_EV_WOOD = (104, 78, 48)


def _ev_table(h, w=0.62, d=0.5, wood=_EV_WOOD):
    """Trestle table, top surface at height ``h``, origin on the floor."""
    from engine3d import Mesh, box
    m = Mesh()
    m.add(box(w, 0.05, d, wood, center=(0.0, h, 0.0), cols={"top": _shade(wood, 1.3)}))
    for sx in (-1.0, 1.0):
        for sz in (-1.0, 1.0):
            m.add(box(0.05, h, 0.05, _shade(wood, 0.7),
                      center=(sx * (w / 2.0 - 0.06), h / 2.0, sz * (d / 2.0 - 0.06))))
    return m


def _ev_paper(m, kind, y):
    """The sheet / envelope / card itself, lying at height ``y``."""
    from engine3d import box
    if kind == "range_card":
        m.add(box(0.24, 0.006, 0.18, (185, 174, 132), center=(0.0, y, 0.0)))
        m.add(box(0.2, 0.002, 0.006, (155, 35, 30), center=(0.0, y + 0.004, 0.03)))
        return
    w, d = (0.34, 0.24) if kind == "packet" else (0.3, 0.42)
    m.add(box(w, 0.012, d, _EV_ENVELOPE if kind == "packet" else _EV_PAPER,
              center=(0.0, y, 0.0)))
    if kind == "decree":
        m.add(box(w - 0.04, 0.004, 0.07, (165, 40, 34),
                  center=(0.0, y + 0.007, -d / 2.0 + 0.09)))
    elif kind == "packet":
        m.add(box(0.05, 0.004, 0.05, (158, 32, 30),
                  center=(w / 2.0 - 0.06, y + 0.007, 0.0)))
        m.add(box(w - 0.06, 0.002, 0.004, (120, 108, 78),
                  center=(0.0, y + 0.007, -d / 2.0 + 0.06)))
    elif kind == "manifest":
        m.add(box(0.2, 0.03, 0.05, (70, 55, 35), center=(0.0, y + 0.02, -d / 2.0 + 0.02)))
    for i in range(4):
        m.add(box(w - 0.08, 0.002, 0.005, (95, 82, 62),
                  center=(0.0, y + 0.007, -0.08 + i * 0.055)))


def _ev_ground_paper(kind):
    """A sheet lying straight on the ground (the truck manifest)."""
    from engine3d import Mesh
    m = Mesh()
    _ev_paper(m, kind, 0.02)
    return m


def _ev_mesh(kind):
    """One clue/evidence prop as geometry (origin on the floor)."""
    from engine3d import Mesh, box, disc_xz
    m = Mesh()
    if kind == "bootprints":
        for ox, oz in ((-0.11, -0.10), (0.10, 0.11)):
            m.add(box(0.13, 0.012, 0.3, (26, 24, 21), center=(ox, 0.006, oz)))
            for j in range(4):
                m.add(box(0.11, 0.003, 0.02, (74, 68, 54),
                          center=(ox, 0.014, oz - 0.1 + j * 0.066)))
        return m
    if kind == "timer_fragment":
        m.add(box(0.3, 0.03, 0.22, (40, 92, 56), center=(0.0, 0.05, 0.0)))
        for i, c in enumerate(((20, 50, 28), (58, 120, 70), (20, 35, 28))):
            m.add(box(0.07, 0.02, 0.06, c, center=(-0.09 + i * 0.09, 0.075, 0.0)))
        for i, c in enumerate(((120, 45, 35), (30, 30, 30))):
            m.add(box(0.16, 0.008, 0.008, c, center=(-0.1 + i * 0.2, 0.075, 0.2)))
        return m
    if kind == "mag_paint":
        m.add(box(0.07, 0.24, 0.2, (95, 90, 75), center=(-0.12, 0.12, 0.0)))
        m.add(box(0.07, 0.05, 0.2, (25, 25, 25), center=(-0.12, 0.27, 0.0)))
        m.add(box(0.18, 0.17, 0.18, (150, 40, 34), center=(0.13, 0.085, 0.0),
                  cols={"top": (176, 56, 46)}))
        m.add(disc_xz(0.3, 0.24, 0.14, 0.014, (120, 30, 28), n=10, layer=1))
        return m
    if kind == "radio":
        m.add(box(0.44, 0.3, 0.4, (86, 68, 44), center=(0.0, 0.15, 0.0),
                  cols={"top": (108, 86, 56)}))
        m.add(_prop_mesh("field_radio"), t=(0.0, 0.3, 0.0))
        return m
    if kind == "terminal":
        m.add(_ev_table(0.72, w=0.7, d=0.55))
        m.add(box(0.4, 0.34, 0.32, (40, 60, 45), center=(0.0, 0.915, -0.05),
                  cols={"top": (52, 74, 55)}))
        m.add(box(0.32, 0.24, 0.01, (8, 26, 18), center=(0.0, 0.915, 0.115)))
        m.add(box(0.28, 0.18, 0.004, _EV_GREEN, center=(0.0, 0.915, 0.122), emissive=True))
        return m
    m.add(_ev_table(0.42))
    _ev_paper(m, kind, 0.451)
    return m


def _upload_pc_mesh():
    """The upload terminal: beige desk PC with a green phosphor screen."""
    from engine3d import Mesh, box
    beige = (192, 182, 152)
    m = Mesh()
    m.add(box(1.05, 0.05, 0.6, _EV_WOOD, center=(0.0, 0.74, 0.0),
              cols={"top": _shade(_EV_WOOD, 1.3)}))
    for sx in (-0.44, 0.44):
        for sz in (-0.22, 0.22):
            m.add(box(0.05, 0.74, 0.05, (78, 58, 36), center=(sx, 0.37, sz)))
    m.add(box(0.42, 0.36, 0.34, beige, center=(0.0, 0.95, -0.08),
              cols={"top": _shade(beige, 1.1)}))
    m.add(box(0.34, 0.26, 0.01, (8, 26, 18), center=(0.0, 0.95, 0.092)))
    m.add(box(0.3, 0.2, 0.004, _EV_GREEN, center=(0.0, 0.95, 0.099), emissive=True))
    m.add(box(0.2, 0.44, 0.4, (148, 138, 110), center=(0.36, 0.98, -0.05),
              cols={"top": _shade(beige, 0.9)}))
    m.add(box(0.06, 0.03, 0.01, (90, 220, 120), center=(0.36, 0.84, 0.155), emissive=True))
    m.add(box(0.42, 0.03, 0.16, _shade(beige, 0.86), center=(0.0, 0.775, 0.24)))
    return m


def _draw_evidence_props(r, tm):
    """The clue / evidence props as real objects in the 2.5D set.

    The 2D frame draws them as flat top-down icons (``draw._draw_world_prop``);
    blitted over the 3D set those read as decals lying on the floor. The stage
    gating mirrors ``draw._draw_interactables`` exactly, including the upload
    PC that is visible from the moment the player enters the control room.
    """
    from cutscenes import m6fx3d as _fx
    stage = getattr(STATE, "mission2_stage", "")
    items = ()
    if stage == STAGE_INVESTIGATE:
        items = [(c, (245, 190, 65)) for c in getattr(STATE, "mission2_clues", ())]
    elif stage == STAGE_TRUCK:
        truck = getattr(STATE, "mission2_truck_manifest", None)
        items = [(truck, (255, 190, 90))] if truck else []
    elif stage == STAGE_EVIDENCE:
        items = [(e, _EV_GREEN) for e in getattr(STATE, "mission2_evidence", ())]
    for item, col in items:
        x, _, z = to3(*item["pos"])
        kind = item.get("kind") or item.get("id") or "document"
        if stage == STAGE_TRUCK:
            mesh = _mesh(("evprop_ground", kind), lambda k=kind: _ev_ground_paper(k))
        else:
            mesh = _mesh(("evprop", kind), lambda k=kind: _ev_mesh(k))
        _put(r, mesh, (x, 0.0, z), yaw=float((_hash(int(x * 100), int(z * 100), 7) - 3) * 4))
        if not item.get("done"):
            h = 0.95 if kind == "terminal" else 0.62 if kind in ("radio", "mag_paint") else 0.55
            r.add_sprite((x, h, z), _glow(col, 0.12, tm, 0.55, 18), layer=_fx.FX_LAYER)
    if stage in (STAGE_EVIDENCE, STAGE_UPLOAD):
        x, _, z = to3(*UPLOAD_TERMINAL_POS)
        _put(r, _mesh("evprop_upload_pc", _upload_pc_mesh), (x, 0.0, z))
        done = sum(1 for e in getattr(STATE, "mission2_evidence", ()) if e.get("done")) >= 3
        pulse = 0.5 + 0.5 * math.sin(tm * 0.005)
        r.add_sprite((x, 1.05, z),
                     _glow(_EV_GREEN, 0.12, tm, (0.55 + 0.35 * pulse) if done else 0.3, 20),
                     layer=_fx.FX_LAYER)


# ── gantry cast: sniper, nest, lasers, traces ──────────────────────────

def _deck_h(pos):
    return DECK_H if tuple(pos) == tuple(SNIPER_NEST_POS) else 0.0


def _cutscene_sniper(r):
    """The gantry sniper during the flank cutscene, as a real 3D actor.

    ``draw._draw_flank_cutscene`` hand-builds him as a top-down pygame
    silhouette for the 2D frame; blitted over the 3D set that read as a
    sprite standing on real geometry. Same beats (aim hold, startle,
    scramble, dust burst), same deck, but a humanoid: prone and held on the
    scope, head pulling off it, then crawling west along the deck behind the
    route sign and gone as the burst's dust covers the nest.
    """
    from engine3d import POSES, blend
    from engine3d.rig import pose_crawl
    from missions.m2.meta import FLANK_BEAT_BURST, FLANK_BEAT_SCRAMBLE_BEGIN, FLANK_BEAT_STARTLE
    t = getattr(STATE, "mission2_flank_cutscene_timer", 0)
    tmax = getattr(STATE, "mission2_flank_cutscene_max", 0) or 0
    el = tmax - t
    nx, ny = SNIPER_NEST_POS
    if el < FLANK_BEAT_BURST:
        hum = td.armed("ipa", "os12", jacket=(34, 38, 30), pants=(32, 34, 28))
        p = STATE.player
        ang = math.atan2(p.rect.centery - ny, p.rect.centerx - nx) if p is not None else math.pi / 2
        prone = dict(POSES["prone"])
        x = nx
        rifle = el < FLANK_BEAT_SCRAMBLE_BEGIN
        if el < FLANK_BEAT_STARTLE:
            pose = td.held(hum, prone, "os12", "aim")
        elif el < FLANK_BEAT_SCRAMBLE_BEGIN:
            k = (el - FLANK_BEAT_STARTLE) / float(max(1, FLANK_BEAT_SCRAMBLE_BEGIN - FLANK_BEAT_STARTLE))
            pose = td.held(hum, dict(prone, head_p=-34 - 14 * k, head_y=14 * k, spine=-6 + 12 * k),
                           "os12", "aim")
        else:
            k = (el - FLANK_BEAT_SCRAMBLE_BEGIN) / float(max(1, FLANK_BEAT_BURST - FLANK_BEAT_SCRAMBLE_BEGIN))
            pose = blend(prone, pose_crawl(k * 9.0), min(1.0, k * 2.2))
            x = nx - 1.6 * T * k              # west along the deck, behind the route sign
            ang = math.pi
        r.add_humanoid(hum, pose, to3(x, ny, DECK_H + 0.07), td.yaw_rad(ang), rifle_on=rifle)
    if getattr(STATE, "mission2_flank_cutscene_rifle_dropped", False):
        rp = getattr(STATE, "mission2_flank_cutscene_rifle_pos", None)
        if rp:
            from ui import mp3d
            mesh, _mz = mp3d.gun("os12")
            _put(r, mesh, to3(rp[0], rp[1], DECK_H + 0.1), yaw=30.0, roll=90.0)


def _draw_gantry_cast(r, flashes, tm):
    from cutscenes import m6fx3d as _fx
    from engine3d import POSES
    stage = getattr(STATE, "mission2_stage", "")
    suppressed = getattr(STATE, "mission2_sniper_suppressed", False)
    cut = getattr(STATE, "mission2_flank_cutscene_timer", 0) > 0
    nx, ny = SNIPER_NEST_POS
    if cut:
        _cutscene_sniper(r)
    elif not suppressed:
        hum = td.armed("ipa", "os12", jacket=(34, 38, 30), pants=(32, 34, 28))
        p = STATE.player
        ang = math.atan2(p.rect.centery - ny, p.rect.centerx - nx) if p is not None else math.pi / 2
        pose = td.held(hum, dict(POSES["prone"]), "os12", "aim")
        j = r.add_humanoid(hum, pose, to3(nx, ny, DECK_H + 0.07), td.yaw_rad(ang))
        if stage == STAGE_SNIPER:
            mz = (j or {}).get("muzzle") or to3(nx, ny, DECK_H + 0.3)
            pulse = 0.5 + 0.5 * math.sin(tm * 0.01)
            r.add_sprite(mz, _glow((255, 60, 40), 0.14, tm, 0.5 + 0.5 * pulse, 14), layer=_fx.FX_LAYER)
    nest = getattr(STATE, "mission2_abandoned_nest", None)
    if nest:
        px, py = nest["pos"]
        for ox, oy in nest.get("casings", ()):
            r.add_sprite(to3(px + ox, py + oy, DECK_H + 0.08), td.dot((200, 160, 70), 2), layer=1)
        rp = nest.get("rifle_pos")
        if rp:
            from ui import mp3d
            mesh, _mz = mp3d.gun("os12")
            _put(r, mesh, to3(rp[0], rp[1], DECK_H + 0.1), yaw=30.0, roll=90.0)
        age = nest.get("age", 0)
        if age < 150:
            r.add_sprite(to3(px, py, DECK_H + 0.2),
                         _glow((255, 240, 200), 0.12, tm, 1.0 - age / 150.0, 12), layer=_fx.FX_LAYER)
    for laser in getattr(STATE, "mission2_sniper_lasers", ()):
        a = max(0.0, min(1.0, laser.get("life", 0) * 4 / 190.0))
        if a <= 0.02:
            continue
        p0 = to3(laser["from"][0], laser["from"][1], _deck_h(laser["from"]) + 0.3)
        p1 = to3(laser["to"][0], laser["to"][1], AIM_H)
        r.add_line3d(p0, p1, td.mix((40, 6, 4), (255, 35, 22), a), 2, layer=4)
        r.add_sprite(p1, _glow((255, 45, 30), 0.1, tm, a, 10), layer=_fx.FX_LAYER)
    for tr in getattr(STATE, "mission2_sniper_traces", ()):
        k = max(0.0, min(1.0, tr["life"] / float(max(tr.get("max_life", 1), 1))))
        kind = tr.get("kind", "body")
        col = {"near_miss": (255, 220, 180), "concrete": (200, 185, 160)}.get(kind, (220, 180, 170))
        p0 = to3(tr["from"][0], tr["from"][1], _deck_h(tr["from"]) + 0.3)
        p1 = to3(tr["to"][0], tr["to"][1], AIM_H if kind != "concrete" else 0.4)
        r.add_line3d(p0, p1, td.mix((20, 20, 20), col, k), 2 if k > 0.5 else 1, layer=4)
        if k > 0.6:
            r.add_sprite(p1, _glow((255, 200, 150), 0.12, tm, (k - 0.6) / 0.4, 12), layer=_fx.FX_LAYER)
    for fl in getattr(STATE, "mission2_sniper_muzzle_flashes", ()):
        pos = fl.get("pos", SNIPER_NEST_POS)
        k = max(0.0, min(1.0, fl.get("life", 1) / float(max(1, fl.get("max_life", 16)))))
        p = to3(pos[0], pos[1], _deck_h(pos) + 0.35)
        r.add_sprite(p, _glow((255, 245, 190), 0.5, tm, 1.4 * k, 40, core=(255, 255, 240)),
                     layer=_fx.FX_LAYER)
        flashes.append({"pos": p, "color": (255, 190, 110), "intensity": 1.6 * k, "range": 7.0})


# ── cast ───────────────────────────────────────────────────────────────

_SQUAD = {"GABI": ("gabi", "os12"), "SEBY": ("seby", "os12"), "DARIUS": ("darius", "os12")}


def _squad_hum(name):
    from missions.m2.sniper3d import SPECS
    key, rig = _SQUAD.get(name, ("gabi", "os12"))
    spec = {k: v for k, v in SPECS[key].items() if k != "rifle"}
    return td.armed("krap", rig, **spec), rig


def _draw_actor(r, actor, tm):
    from engine3d import POSES, blend
    name = actor.get("name", "")
    act = (actor.get("activity") or "standing").lower()
    x, y = actor["pos"][0], actor["pos"][1]
    hum, rig = _squad_hum(name)
    key = ("sq", name)
    m = _m1._cache["motion"].get(key)
    if m is not None and math.hypot(x - m[0], y - m[1]) > 0.3:
        ang = math.atan2(y - m[1], x - m[0])
    else:
        p = STATE.player
        ang = math.atan2(p.rect.centery - y, p.rect.centerx - x) if p is not None else math.pi / 2
        ang = actor.setdefault("_face3d", ang) if "down" in act or "dead" in act else ang
    if "down" in act or "dead" in act:
        at = to3(x, y)
        r.add_sprite((at[0], 0.02, at[2]), td.blood_pool(0.8), layer=0)
        r.add_humanoid(hum, dict(POSES["dead_back"]), at, td.yaw_rad(ang), rifle_on=False)
        return
    crouch = any(w in act for w in ("drag", "reach", "radio", "frozen", "shock", "crouch", "cover"))
    if crouch:
        base = dict(POSES["kneel" if ("reach" in act or "radio" in act) else "crouch"])
        mode = "ready"
        pose = td.held(hum, base, rig, mode)
        _m1._motion(key, x, y, ang)
        r.add_sprite(to3(x, y, 0.02), td.shadow(0.5), layer=0)
        r.add_humanoid(hum, pose, to3(x, y), td.yaw_rad(ang))
        return
    r.add_sprite(to3(x, y, 0.02), td.shadow(0.45), layer=0)
    _m1._body(r, hum, x, y, ang, rig, "ready", key)


def _draw_cast(r, flashes, tm):
    for actor in STATE.mission2_squad:
        _draw_actor(r, actor, tm)
    _m1._draw_corpses(r, flashes, tm)
    for e in STATE.enemies:
        hum, rig = _m1._enemy_hum(e)
        mode = "aim" if e.state in ("CHASE", "ATTACK") else "ready"
        burn = getattr(e, "burn", 0)
        tint = _m1.CHAR if burn else (e.body_tint, 0.55) if getattr(e, "body_tint", None) else None
        _m1._feet(r, e.rect.centerx, e.rect.centery, _m1.RING_FOE.get(e.state, _m1.RING_FOE_CALM))
        _m1._body(r, hum, e.rect.centerx, e.rect.centery, e.angle, rig, mode, ("e", e.uid), tint=tint)
        _m1._burning(r, e.rect.centerx, e.rect.centery, min(1.0, burn / 40.0), tm, e.uid * 5, flashes)
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


def _draw_fx(r, flashes, tm):
    from cutscenes import m6fx3d as _fx
    from core.config import C_BULLET
    from engine3d import m_apply, m_mul, rot_x, rot_y
    t = _now_s()
    for pu in STATE.pickups:
        x, _, z = to3(pu[0], pu[1])
        bob = 0.06 * math.sin(t * 3 + pu[0])
        kind = "bandage" if pu[2] == "bandage" else "mag"
        _put(r, _mesh(("pickup", kind), lambda k=kind: _m1._pickup_mesh(k)), (x, 0.25 + bob, z),
             yaw=(t * 60.0 + pu[0]) % 360.0)
        r.add_sprite((x, 0.3, z), _glow(_m1._PICKUP_COL.get(kind, (255, 210, 40)), 0.28, tm, 0.7, 16),
                     layer=_fx.FX_LAYER)
    for decal in STATE.blood_decals:
        k = max(0.0, min(1.0, decal[2] / 255.0))
        if k > 0.05:
            r.add_sprite(to3(decal[0], decal[1], 0.015),
                         td.blood_pool(min(1.0, decal[3] / 24.0) * k, (80, 12, 14)), layer=0)
    fx0, fz0 = _cache.get("tgt") or (0.0, 0.0)
    lit = []
    for fz in STATE.fire_zones:
        x, _, z = to3(fz.x, fz.y)
        if abs(x - fx0) > 22.0 or abs(z - fz0) > 18.0:
            continue
        life = fz.life / float(max(1, fz.max_life))
        heat = min(1.0, life * 4.0)
        rad = fz.radius * K
        r.add_sprite((x, 0.02, z), td.blood_pool(min(1.0, rad / 2.0), (26, 18, 14)), layer=0)
        _m1._fuel_pool_at(r, x, z, rad * (0.55 + 0.45 * heat), fz.x * 0.37 + fz.y * 0.11)
        n = 1 + min(9, int(rad / 0.3))
        # zones heaped on one spot (the tanker leaves 23) read as one fire: past
        # the first, a zone inside another's radius keeps three flames, no light
        near = any((x - px) ** 2 + (z - pz) ** 2 < rad * rad for px, pz in lit)
        if near:
            n = min(n, 3)
        else:
            lit.append((x, z))
        for i in range(n):
            a = i * 2.39996 + fz.x * 0.013
            d = 0.0 if i == 0 else rad * 0.8 * math.sqrt(i / float(n))
            size = (0.5 if i == 0 else 0.34) * min(1.2, 0.4 + rad * 0.35) * heat
            _m1._fire(r, (x + math.cos(a) * d, 0.0, z + math.sin(a) * d), tm, int(fz.x) + i, size,
                      glow=i == 0)
        flashes.append({"pos": (x, 1.0, z), "color": FIRE, "intensity": 1.0 * heat, "range": 4.0 + rad})
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
    """World position of the light of a ``_M2_LAMPS`` entry."""
    x, _, z = _tc(col, row)
    if key.startswith("st_"):
        return (x, 3.45, z)
    if key.startswith("toll") or key == "shl":
        return (x, 4.0, z - 0.9 + 0.9)
    if key.startswith("grd"):
        return (x, 2.4, z)
    if key.startswith("win"):
        return (x, 1.85, z + 0.6)
    if key == "nest":
        return (x, DECK_H + 0.4, z)
    if key == "tnk":
        return (x, 1.7, z)
    return (x, 2.4, z)


def _lamps():
    for col, row, rad, color, key in _d._M2_LAMPS:
        if _d._m2_lamp_visible(key):
            yield col, row, rad, color, key


def _lamp_lights(r, v, flashes, tm):
    """Lamp pools light the baked floor; the lamps nearest the camera focus
    plus the flashes are the eight per-frame lights."""
    from cutscenes import m6fx3d as _fx
    fx, fz = v.tgt[0], v.tgt[2]
    _cache["tgt"] = (fx, fz)
    pools, near = [], []
    for col, row, rad, color, key in _lamps():
        head = _lamp_head(col, row, key)
        reach = rad * K * 1.6
        pools.append({"pos": head, "range": reach, "color": color, "intensity": 2.0,
                      "hot": td.mix(color, (255, 250, 235), 0.5)})
        near.append(((head[0] - fx) ** 2 + (head[2] - fz) ** 2,
                     {"pos": head, "color": color, "intensity": 0.45, "range": reach}))
        if key.startswith(("st_", "toll", "shl", "grd")) or key == "nest":
            r.add_sprite(head, _fx.glow(color, 0.3, tm, intensity=0.9, max_px=18), layer=_fx.FX_LAYER)
    hx, _, hz = to3(49 * T + 32, 32 * T + 32)
    flashes.append({"pos": (hx + 1.5, 0.8, hz), "color": (255, 230, 170), "intensity": 0.8, "range": 6.0})
    p = STATE.player
    if p is not None:
        flashes.append({"pos": to3(p.rect.centerx, p.rect.centery, 1.7), "color": (190, 205, 230),
                        "intensity": 0.9, "range": 3.0})
    near.sort(key=lambda e: e[0])
    lights = [e[1] for e in near[:max(0, 8 - len(flashes))]]
    r.set_pools(pools)
    r.set_lights(flashes[:8] + lights, cap=8)


_POOL_K = {"st": 0.6, "toll": 0.68, "win": 0.42, "term": 0.4, "hut": 0.4, "tnk": 0.55, "shl": 0.6,
           "grd": 0.5, "nest": 0.5, "trk": 0.45}


def _night_lights():
    """Fixed lights for the grade: lamp throws and bulbs (only the ones
    ``_m2_lamp_visible`` passes), wet-road reflections, the truck's
    headlight cone, the lit windows and the cool sky wash."""
    vis = tuple(key for *_x, key in _lamps())
    hit = _cache["night"]
    if hit is not None and hit[0] == vis:
        return hit[1]
    out = []
    for col, row, rad, color, key in _lamps():
        fam = key.split("_")[0]
        hx, hy, hz = _lamp_head(col, row, key)
        reach = rad * K * 1.6
        out.append(("pool", (hx, 0.0, hz), color, reach * 0.72, _POOL_K.get(fam, 0.45)))
        if fam in ("st", "toll", "shl", "grd", "nest", "win", "term"):
            out.append(("glow", (hx, hy, hz), color, 0.7, 0.55))
        if fam in ("st", "toll"):
            out.append(("reflect", (hx, 0.0, hz - 0.3), color, 0.55, 0.3))
    hx, _, hz = to3(49 * T + 32, 32 * T + 32)
    for i in range(1, 5):
        out.append(("pool", (hx + i * 1.2, 0.0, hz), (255, 230, 170), 0.6 + i * 0.35, 0.32 - i * 0.04))
    for side in (-0.5, 0.5):
        out.append(("glow", (hx, 0.9, hz + side), (255, 230, 170), 0.35, 0.6))
    _cache["night"] = (vis, out)
    return out


# ── screen space ───────────────────────────────────────────────────────

def _labels(s, v):
    """Squad names over their heads, as the 2D actor pass labels them."""
    for actor in STATE.mission2_squad:
        name = actor.get("name", "")
        if not name:
            continue
        down = any(w in (actor.get("activity") or "").lower() for w in ("down", "dead"))
        pt = v.screen_sim(actor["pos"][0], actor["pos"][1], 0.6 if down else 2.15)
        if pt is None or not (-40 < pt[0] < WIDTH + 40 and -40 < pt[1] < HEIGHT + 40):
            continue
        col = (150, 185, 230) if actor.get("alive", True) else (130, 80, 80)
        img = font_terminal_small.render(name, True, col)
        s.blit(img, (int(pt[0]) - img.get_width() // 2, int(pt[1]) - img.get_height()))
