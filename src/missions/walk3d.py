"""Walking sim in 2.5D: the harbour alley drawn in 3D over the 2D rules.

``walking_sim.draw_walking_sim`` hands the world pass here while
``game.topdown3d`` is on. Movement, collision, interaction, the dialogue and
every timer stay in ``walking_sim``; this module only changes what the world
looks like, the same split as ``missions.m1.draw3d``. Screen-space passes
(rain, vignette, scanlines, letterbox, HUD, dialogue, reticle) are the 2D ones.

Set: the ``C`` tiles are shipping containers (``walking_sim._walk_containers``
merges them into boxes); the floor, props, lamps and wall dressing are one
static batch. Containers between the camera and the player sink to a stub
(the cutaway). The KRAP van is the real ``krap_van`` mesh.

Any renderer error turns 2.5D off for the rest of the run (``td.disable``)
and the next frame is the 2D painter.
"""
import math

import pygame

from core.config import C_ORANGE, HEIGHT, TILE_SIZE, WIDTH, font_terminal_small
from engine.core import now_ms as _now_ms
from game import topdown3d as td
from game.topdown3d import K, to3

CAM = td.Cam(64.0, 25.0, 50.0)
CONTAINER_H = 2.6
STUB_H = 0.45
CUT_CAP = (26, 27, 31)
CUT_BACK = 2.4                   # tiles south of the player a box may hide him
CUT_SIDE = 3.0
CUT_STEP = 0.125                 # a box sinks or rises in 8 frames
WALK_RAD_PER_M = 2.6

NIGHT = dict(direction=(-0.30, 0.85, -0.42), ambient=0.42, diffuse=0.5, sky=0.12,
             tint=(0.82, 0.90, 1.05))
VOID = (8, 9, 12)
FLOOR = (62, 58, 52)
LAMP_RANGE_M = 5.5
VAN_MODEL_M = 7.18               # krap_van.glb nose to tail
WINDOW_FILL = (190, 205, 230)

_cache = {"view": None, "meshes": {}, "packed": {}, "motion": {}, "cut": {}, "cut_at": None,
          "hum": {}, "face": {}}


# ── frame ──────────────────────────────────────────────────────────────

def view():
    """The last frame's camera, or None (the 2D painter drew it)."""
    return _cache["view"]


def aim(mouse, render_x, render_y, h=0.9):
    """Sim pixel under ``mouse`` seen from the follow camera, or None in 2D."""
    if not td.enabled():
        return None
    v = td.View(CAM, render_x + WIDTH / 2.0, render_y + HEIGHT / 2.0)
    return v.ground(mouse, h)


def head_point(x, y, h=1.9):
    """Canvas pixel above sim point (x, y) in this frame's 3D view, or None."""
    v = _cache["view"]
    return None if v is None else v.screen_sim(x, y, h)


def draw(ws, surface, fcx, fcy):
    """Draw the walking-sim world through the 2.5D camera. True when drawn;
    False leaves the frame to the 2D painter."""
    if not td.enabled():
        _cache["view"] = None
        return False
    from cutscenes import m6fx3d as _fx
    from cutscenes import m6world3d as _w
    from engine3d import Light
    from missions.m1 import grade3d as _grade
    v = td.View(CAM, fcx + WIDTH / 2.0, fcy + HEIGHT / 2.0)
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
        first = _w.static_scene(r, ("walk_td3d", id(ws.walk_map)))
        ok = False
        try:
            if first:
                _build_set(ws, r)
            ok = True
        finally:
            _w.static_end(r, ok)
        flashes = []
        _draw_walls(ws, r)
        _draw_cast(ws, r, flashes, tm)
        _lights(ws, r, v, flashes, tm)
        r.flush(buf)
    except Exception:
        import traceback
        traceback.print_exc()
        td.disable()
        _cache["view"] = None
        return False
    finally:
        r.light, r.fog, r.fog_start, r.fog_end, r.light_cap = saved
    _cache["view"] = v
    _fx.present_crisp(buf, surface)
    _grade.apply(surface, v, _grade_lights(ws), ambient=_ambient(ws))
    _labels(ws, surface, v)
    return True


def _ambient(ws):
    """The 2D night map's ambient (alley to harbour), the 3D
    pass already lights the set."""
    prog = min(1.0, max(0.0, ws.walk_player.rect.centerx / float(len(ws.walk_map[0]) * TILE_SIZE)))
    return tuple(int((a + (b - a) * prog) * 1.0)
                 for a, b in zip(ws._WALK_AMBIENT_START, ws._WALK_AMBIENT_END))


# ── helpers ────────────────────────────────────────────────────────────

def _h(col, row, n):
    """A stable 0..n-1 hash of a tile."""
    return ((col * 73856093) ^ (row * 19349663) ^ (n * 83492791)) % n


def _put(r, mesh, pos, yaw=0.0, scale=1.0):
    td.put(r, mesh, pos, yaw, 0.0, scale, cache=_cache["packed"])


def _mesh(key, build):
    m = _cache["meshes"].get(key)
    if m is None:
        m = _cache["meshes"][key] = build()
    return m


def _floor_tex(col, k=1.0):
    from engine3d import tex
    return tex("pavement", like=tuple(max(0, min(255, int(c * k))) for c in col), tint=True)


def _barrel(x, z, col, h=0.9, rad=0.3):
    from engine3d import Mesh, prism, rot_x
    prof = [(math.cos(a) * rad, math.sin(a) * rad) for a in
            [2 * math.pi * i / 8 for i in range(8)]]
    m = prism(prof, h, col, z0=0.0, cols={"back": td.mix(col, (0, 0, 0), 0.4)})
    out = Mesh()
    out.add(m, m=rot_x(-90.0), t=(x, 0.0, z))
    return out


# ── set (static batch) ─────────────────────────────────────────────────

def _props(ws):
    if ws.WALK_PROPS is None:
        ws.WALK_PROPS = ws._gen_walk_props()
    return ws.WALK_PROPS


def _lamps(ws):
    return [(x, y) for kind, x, y in _props(ws) if kind == "lamp"]


def _lamp_head(x, y):
    px, _, pz = to3(x, y)
    return (px, 3.4, pz - 0.9)


def _build_set(ws, r):
    from cutscenes import m6world3d as _w
    from engine3d import quad_xz
    T = TILE_SIZE
    rows, cols = len(ws.walk_map), len(ws.walk_map[0])
    for row in range(rows):
        for col in range(cols):
            k = 1.0 + (_h(col, row, 9) - 4) * 0.011
            lean = (_h(col + 3, row + 11, 5) - 2) * 0.006
            base = (FLOOR[0] * k * (1.0 + lean), FLOOR[1] * k, FLOOR[2] * k * (1.0 - lean))
            _w.add(r, quad_xz(col * T * K, -(row + 1) * T * K, (col + 1) * T * K, -row * T * K,
                              0.0, _floor_tex(base), layer=0))
    _contact_shadows(ws, r)
    for kind, x, y in _props(ws):
        _prop(r, kind, x, y)
    for sx, sy, key, _label, _text in ws.walk_story_points:
        _story(r, key, sx, sy)


def _contact_shadows(ws, r):
    """Dark bands on the floor where a container meets it."""
    from cutscenes import m6world3d as _w
    from engine3d import quad_xz
    T = TILE_SIZE
    steps, step = (0.55, 0.72, 0.87), 7
    for c, row, w, h in ws._walk_containers():
        x0, y0, x1, y1 = c * T, row * T, (c + w) * T, (row + h) * T
        for i, k in enumerate(steps):
            a, b = i * step, (i + 1) * step
            for ya, yb, xa, xb in ((y1 + a, y1 + b, x0 - b, x1 + b), (y0 - b, y0 - a, x0 - b, x1 + b),
                                   (y0 - a, y1 + a, x0 - b, x0 - a), (y0 - a, y1 + a, x1 + a, x1 + b)):
                _w.add(r, quad_xz(xa * K, -yb * K, xb * K, -ya * K, 0.003, _floor_tex(FLOOR, k), layer=1))


def _prop(r, kind, x2, y2):
    from cutscenes import m6world3d as _w
    from engine3d import box, disc_xz, tex
    x, _, z = to3(x2, y2)
    n = int(x2 * 7 + y2 * 3)
    if kind == "lamp":
        metal = (30, 31, 34)
        h, arm = 3.4, 0.9
        _w.add(r, box(0.12, h, 0.12, metal, center=(x, h / 2.0, z)))
        _w.add(r, box(0.08, 0.08, arm, metal, center=(x, h, z - arm / 2.0)))
        _w.add(r, box(0.36, 0.12, 0.24, metal, center=(x, h - 0.04, z - arm)))
        _w.add(r, box(0.28, 0.03, 0.18, (150, 108, 58), center=(x, h - 0.11, z - arm), emissive=True))
    elif kind == "drum":
        col = ((52, 74, 60), (96, 54, 36), (60, 64, 70))[n % 3]
        _w.add(r, _barrel(x, z, col))
    elif kind == "trash":
        _w.add(r, box(0.7, 0.5, 0.5, (40, 54, 44), center=(x, 0.25, z)))
        _w.add(r, box(0.74, 0.06, 0.54, (28, 36, 30), center=(x, 0.53, z)))
        _w.add(r, box(0.2, 0.1, 0.16, (110, 104, 90), center=(x + 0.4, 0.05, z + 0.2)))
    elif kind == "pallet":
        wood = tex("crate", like=(96, 74, 48))
        for i in range(3):
            _w.add(r, box(1.1, 0.04, 0.2, wood, center=(x, 0.12, z - 0.4 + i * 0.4)))
        for i in range(3):
            _w.add(r, box(0.12, 0.1, 1.0, (70, 54, 36), center=(x - 0.45 + i * 0.45, 0.05, z)))
    elif kind == "puddle":
        _w.add(r, disc_xz(x, z, 0.5 + 0.1 * (n % 3), 0.006, (34, 40, 52), n=9, layer=1))
    elif kind == "pipe":
        _w.add(r, box(1.1, 0.12, 0.12, (70, 72, 74), center=(x, 0.1, z)))
        _w.add(r, box(0.14, 0.16, 0.16, (50, 52, 54), center=(x + 0.3, 0.1, z)))
    elif kind == "cable":
        for i in range(4):
            _w.add(r, box(0.3, 0.03, 0.05, (20, 20, 22), center=(x - 0.45 + i * 0.3, 0.02, z + 0.06 * (i % 2))))
    elif kind == "debris":
        for i in range(4):
            s = 0.1 + 0.05 * ((n + i) % 3)
            _w.add(r, box(s, s * 0.6, s, (84, 78, 70), center=(x + (i - 1.5) * 0.18, s * 0.3, z + 0.1 * ((n + i) % 3 - 1))))
    elif kind in ("wall_graffiti", "wall_poster", "wall_pipe", "wall_stain"):
        zf = -(y2 // TILE_SIZE) * TILE_SIZE * K - 0.02       # the wall's south face
        if kind == "wall_graffiti":
            col = ((170, 60, 60), (60, 140, 170), (200, 180, 70))[n % 3]
            _w.add(r, box(0.9, 0.5, 0.02, col, center=(x, 1.5, zf)))
            _w.add(r, box(0.5, 0.3, 0.02, td.mix(col, (0, 0, 0), 0.4), center=(x + 0.1, 1.5, zf - 0.01)))
        elif kind == "wall_poster":
            _w.add(r, box(0.5, 0.7, 0.02, (200, 190, 160), center=(x, 1.5, zf)))
            _w.add(r, box(0.3, 0.4, 0.02, (90, 70, 60), center=(x, 1.55, zf - 0.01)))
        elif kind == "wall_pipe":
            _w.add(r, box(0.12, 2.3, 0.12, (46, 48, 50), center=(x, 1.15, zf - 0.05)))
        else:
            _w.add(r, box(0.7, 1.0, 0.015, (36, 32, 28), center=(x, 1.0, zf)))


def _story(r, key, x2, y2):
    """Static dressing for a story point (the people are in ``_draw_cast``)."""
    from cutscenes import m6world3d as _w
    from engine3d import box, tex
    x, _, z = to3(x2, y2)
    crate = tex("crate", like=(118, 92, 60))
    if key == "poster":
        zf = -(y2 // TILE_SIZE) * TILE_SIZE * K - 0.02
        _w.add(r, box(0.7, 1.0, 0.02, (186, 176, 150), center=(x, 1.5, zf)))
        _w.add(r, box(0.4, 0.5, 0.02, (110, 70, 60), center=(x, 1.6, zf - 0.01)))
    elif key == "laundry":
        for sx in (-1.4, 1.4):
            _w.add(r, box(0.08, 2.4, 0.08, (60, 56, 50), center=(x + sx, 1.2, z)))
        _w.add(r, box(2.8, 0.02, 0.02, (150, 146, 130), center=(x, 2.2, z)))
        for i, col in enumerate(((150, 90, 80), (90, 110, 140), (190, 184, 170), (120, 130, 80))):
            _w.add(r, box(0.4, 0.6, 0.03, col, center=(x - 1.0 + i * 0.66, 1.88, z)))
    elif key == "checkpoint":
        _w.add(r, _barrel(x, z, (96, 54, 36)))
        _w.add(r, box(0.8, 0.04, 0.8, (60, 64, 70), center=(x, 0.92, z)))
        for dx, dz in ((-1.1, 0.4), (1.0, -0.5)):
            _w.add(r, box(0.5, 0.5, 0.5, crate, center=(x + dx, 0.25, z + dz)))
    elif key == "fish":
        for i in range(3):
            _w.add(r, box(0.8, 0.4, 0.55, crate, center=(x - 0.9 + i * 0.9, 0.2, z)))
            _w.add(r, box(0.66, 0.02, 0.4, (150, 160, 166), center=(x - 0.9 + i * 0.9, 0.41, z)))
    elif key == "overlook":
        for i in range(3):
            _w.add(r, box(0.08, 1.0, 0.08, (60, 62, 64), center=(x, 0.5, z - 1.2 + i * 1.2)))
        _w.add(r, box(0.06, 0.06, 2.4, (70, 72, 74), center=(x, 1.0, z)))


# ── walls (per frame, cutaway) ─────────────────────────────────────────

def _wall_mesh(w, d, hgt, ci, cols):
    key = ("wall", round(w, 3), round(d, 3), hgt, ci)
    m = _cache["meshes"].get(key)
    if m is not None:
        return m
    from engine3d import Mesh, box, tex
    m = Mesh()
    col = cols[ci]
    cut = hgt < CONTAINER_H - 0.01
    side = tex("metal_rib", like=col)
    cap = CUT_CAP if cut else td.mix(col, (0, 0, 0), 0.25)
    m.add(box(w, hgt, d, side, center=(0.0, hgt / 2.0, 0.0), cols={"top": cap}, seg=3.2))
    for y0, y1, k in ((0.0, 0.32, 0.6), (0.32, 0.8, 0.8)):
        y1 = min(y1, hgt - 0.02)
        if y1 > y0:
            shade = tex("metal_rib", like=tuple(int(c * k) for c in col))
            m.add(box(w + 0.02, y1 - y0, d + 0.02, shade, center=(0.0, (y0 + y1) / 2.0, 0.0),
                      skip=("top", "bottom")))
    if hgt > STUB_H:
        for sx in (-1, 1):
            m.add(box(0.12, hgt, 0.12, td.mix(col, (0, 0, 0), 0.4),
                      center=(sx * (w / 2.0 - 0.05), hgt / 2.0, -d / 2.0 + 0.05)))
    _cache["meshes"][key] = m
    return m


def _cut_snap(ws):
    p = ws.walk_player
    at = (p.rect.centerx, p.rect.centery)
    last, _cache["cut_at"] = _cache["cut_at"], at
    return last is None or math.hypot(at[0] - last[0], at[1] - last[1]) > 3 * TILE_SIZE


def _draw_walls(ws, r):
    """Each container at full height, except the ones between the camera and
    the player: those sink to a stub over a few frames and rise behind him."""
    T = TILE_SIZE
    p = ws.walk_player
    x, y = p.rect.centerx, p.rect.centery
    zone = (x - CUT_SIDE * T, y, x + CUT_SIDE * T, y + CUT_BACK * T)
    snap = _cut_snap(ws)
    cols = ws._WALK_CONTAINER_COLS
    for c, row, w, h in ws._walk_containers():
        x0, y0, x1, y1 = c * T, row * T, (c + w) * T, (row + h) * T
        hides = (x1 > zone[0] and x0 < zone[2] and y1 > zone[1] and y0 < zone[3]
                 and y0 > zone[1] - T * 0.5)
        want = 0.0 if hides else 1.0
        k = _cache["cut"].get((c, row), 1.0)
        k = want if snap else (min(want, k + CUT_STEP) if want > k else max(want, k - CUT_STEP))
        _cache["cut"][(c, row)] = k
        hgt = STUB_H + (CONTAINER_H - STUB_H) * round(k * 8) / 8.0
        cx, _, cz = to3((x0 + x1) / 2.0, (y0 + y1) / 2.0)
        _put(r, _wall_mesh(w * T * K, h * T * K, hgt, _h(c, row, len(cols)), cols), (cx, 0.0, cz))


# ── cast ───────────────────────────────────────────────────────────────

def _hum(who, **overrides):
    key = (who, tuple(sorted(overrides.items())))
    h = _cache["hum"].get(key)
    if h is None:
        from engine3d import Humanoid
        from cutscenes.cast3d import spec3d
        s = spec3d(who, **overrides)
        h = Humanoid(s)
        h._gl_spec_key = repr(sorted(s.items())) + "|walk"
        _cache["hum"][key] = h
    return h


def _motion(key, x, y, angle):
    """Walk phase from how far an actor moved since last frame."""
    m = _cache["motion"].get(key)
    if m is None:
        m = _cache["motion"][key] = [x, y, 0.0, 0.0]
    step = math.hypot(x - m[0], y - m[1]) * K
    if step > 1.0:
        step = 0.0
    fwd = math.cos(angle) * (x - m[0]) + math.sin(angle) * (y - m[1])
    m[3] = m[3] * 0.8 + step * 60.0 * 0.2
    m[2] += step * WALK_RAD_PER_M * (1.0 if fwd >= 0.0 else -1.0)
    m[0], m[1] = x, y
    return m[2], m[3] > 0.5


def _face(key, want, rate=0.15):
    """Ease a heading (radians) toward ``want`` along the short way round."""
    cur = _cache["face"].get(key, want)
    cur += ((want - cur + math.pi) % (2 * math.pi) - math.pi) * rate
    _cache["face"][key] = cur
    return cur


def _person(r, hum, x, y, angle, key, moving=None):
    from engine3d import POSES, pose_run
    phase, walking = _motion(key, x, y, angle)
    pose = pose_run(phase, lean=4) if (walking if moving is None else moving) else dict(POSES["stand"])
    r.add_sprite(to3(x, y, 0.02), td.shadow(0.42, 0.42, 120), layer=0)
    r.add_humanoid(hum, pose, to3(x, y), td.yaw_rad(angle), rifle_on=False)


def _van_mesh(lit):
    def build():
        from engine3d import Mesh
        from game.render3d_bridge import load_mesh_asset
        verts, faces = load_mesh_asset("krap_van")
        m = Mesh()
        m.verts = [tuple(v) for v in verts]
        for idx, col, grp in faces:
            m.faces.append((tuple(idx), tuple(col), 3 if grp == 9 else 2, False,
                            bool(lit and grp in (1, 2))))
        return m
    return _mesh(("van", bool(lit)), build)


def _van_scale(ws):
    return ws._WALK_VAN_W * K / VAN_MODEL_M


def _draw_cast(ws, r, flashes, tm):
    T = TILE_SIZE
    px, py = ws.walk_player.rect.centerx, ws.walk_player.rect.centery
    if ws.walk_after_firefight or ws.STATE.walk_after_firefight:
        rect = ws._walk_van_rect()
        cx, _, cz = to3(rect.centerx, rect.centery)
        r.add_sprite((cx, 0.02, cz), td.shadow(2.3, 1.0, 150), layer=0)
        try:
            _put(r, _van_mesh(ws._walk_van_lit()), (cx, 0.0, cz), 0.0, _van_scale(ws))
        except (OSError, ValueError, KeyError):
            from engine3d import box
            from cutscenes import m6world3d as _w
            _w.add(r, box(rect.w * K, 1.8, rect.h * K, (34, 36, 40), center=(cx, 0.9, cz)))
    for stash in ws.walk_stashes:
        _stash(r, stash)
    hover = ws.walk_active_hover
    if hover:
        pulse = 0.5 + 0.5 * math.sin(tm * 0.005)
        r.add_sprite(to3(hover["x"], hover["y"], 0.02),
                     td.tac_ring(0.7 + 0.1 * pulse, (255, 214, 96)), layer=0)
    for npc in ws.walk_npcs:
        sprite = npc.get("sprite")
        who = ("hungry_kid", {}) if sprite == "hungry_kid" else (
            "civilian", {"jacket": (78, 64, 52), "hair": (196, 196, 190), "scale": 0.92})
        near = math.hypot(px - npc["x"], py - npc["y"]) < 3.2 * T
        ang = math.atan2(py - npc["y"], px - npc["x"]) if near else math.pi * 0.5
        _person(r, _hum(who[0], **who[1]), npc["x"], npc["y"], _face(("n", npc["name"]), ang),
                ("n", npc["name"]), moving=False)
    for sx, sy, key, _label, _text in ws.walk_story_points:
        if key == "checkpoint":
            for i, dx in enumerate((-30, 34)):
                _person(r, _hum("krap"), sx + dx, sy + 6, math.pi * (0.0 if i else 1.0),
                        ("cp", i), moving=False)
        elif key == "overlook" and not ws.walk_firefight_triggered:
            fx, fy = ws.walk_fisherman_pos
            _person(r, _hum("fisherman"), fx, fy, _face(("f",), math.atan2(py - fy, px - fx), 0.08),
                    ("f",), moving=False)
    p = ws.walk_player
    _person(r, _hum("biribel"), px, py, p.angle, "player", moving=ws._walk_player_moving)
    flashes.append({"pos": to3(px, py, 1.7), "color": (190, 205, 230), "intensity": 0.9, "range": 3.0})


def _stash(r, stash):
    from cutscenes import m6world3d as _w
    from engine3d import box, tex
    x, _, z = to3(stash["x"], stash["y"])
    wood = tex("crate", like=(96, 72, 46))
    _w.add(r, box(0.9, 0.5, 0.6, wood, center=(x, 0.25, z)))
    lid_up = stash["searched"]
    _w.add(r, box(0.94, 0.06, 0.64, (60, 44, 28), center=(x, 0.53 if not lid_up else 0.62, z + (0.0 if not lid_up else 0.3))))
    _w.add(r, box(0.12, 0.1, 0.04, (180, 150, 80), center=(x, 0.4, z - 0.31)))


# ── lights ─────────────────────────────────────────────────────────────

def _lights(ws, r, v, flashes, tm):
    """Lit lamp pools light the floor; the lamps nearest the camera focus
    (plus the player's fill) are the eight per-frame lights."""
    fx, fz = v.tgt[0], v.tgt[2]
    pools, near = [], []
    col = ws._WALK_LAMP_COL
    for x2, y2 in _lamps(ws):
        if not ws._walk_lamp_lit(x2, y2):
            continue
        head = _lamp_head(x2, y2)
        pools.append({"pos": head, "range": LAMP_RANGE_M, "color": col, "intensity": 2.2,
                      "hot": td.mix(col, (255, 250, 235), 0.5)})
        near.append(((head[0] - fx) ** 2 + (head[2] - fz) ** 2,
                     {"pos": head, "color": col, "intensity": 0.45, "range": LAMP_RANGE_M}))
    if ws.walk_after_firefight or ws.STATE.walk_after_firefight:
        rect = ws._walk_van_rect()
        if ws._walk_van_lit():
            cx, _, cz = to3(rect.centerx, rect.centery)
            hx = cx + rect.w * K / 2.0
            for head, c, rng in (((hx + 1.8, 0.9, cz), (150, 140, 104), 4.5),
                                 ((cx - rect.w * K / 2.0 - 0.6, 1.0, cz), (120, 62, 44), 3.0)):
                pools.append({"pos": head, "range": rng, "color": c, "intensity": 1.4})
    near.sort(key=lambda e: e[0])
    r.set_pools(pools)
    r.set_lights(flashes + [e[1] for e in near[:max(0, 8 - len(flashes))]], cap=8)


def _grade_lights(ws):
    """Screen-space night map lights: ``grade3d`` tuples."""
    out = []
    col = ws._WALK_LAMP_COL
    for x2, y2 in _lamps(ws):
        if not ws._walk_lamp_lit(x2, y2):
            continue
        head = _lamp_head(x2, y2)
        out.append(("pool", (head[0], 0.0, head[2]), col, 4.6, 0.8))
        out.append(("glow", head, col, 0.9, 0.9))
    if ws.walk_after_firefight or ws.STATE.walk_after_firefight:
        rect = ws._walk_van_rect()
        if ws._walk_van_lit():
            cx, _, cz = to3(rect.centerx, rect.centery)
            hx = cx + rect.w * K / 2.0
            out.append(("pool", (hx + 1.6, 0.0, cz), (150, 140, 104), 3.6, 0.9))
            out.append(("glow", (hx, 0.7, cz - 0.5), (255, 236, 170), 0.8, 0.9))
            out.append(("glow", (hx, 0.7, cz + 0.5), (255, 236, 170), 0.8, 0.9))
            out.append(("pool", (cx - rect.w * K / 2.0 - 0.8, 0.0, cz), (120, 62, 44), 2.4, 0.8))
    p = ws.walk_player.rect
    x, _, z = to3(p.centerx, p.centery)
    out.append(("pool", (x, 0.0, z), (44, 44, 50), 3.4, 1.0))
    return out


def _labels(ws, surface, v):
    """The boarding cue over the van's rear doors."""
    if not (ws.walk_after_firefight or ws.STATE.walk_after_firefight) or ws.walk_return_timer > 0:
        return
    rect = ws._walk_van_rect()
    cx, _, cz = to3(rect.centerx, rect.centery)
    pt = v.screen((cx - rect.w * K / 2.0 - 0.4, 2.5, cz))
    if pt is None:
        return
    x, y = int(pt[0]), int(pt[1] + 3 * math.sin(_now_ms() * 0.006))
    pygame.draw.polygon(surface, C_ORANGE, [(x - 7, y), (x + 7, y), (x, y + 9)])
    lab = font_terminal_small.render("KRAP EXTRACTION", True, (214, 204, 180))
    bg = pygame.Surface((lab.get_width() + 12, lab.get_height() + 4), pygame.SRCALPHA)
    bg.fill((0, 0, 0, 150))
    surface.blit(bg, (x - bg.get_width() // 2, y - bg.get_height() - 3))
    surface.blit(lab, (x - lab.get_width() // 2, y - bg.get_height() - 1))
