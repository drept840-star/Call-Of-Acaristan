"""Mission 6 in 2.5D: the customs post, no-man's-land and the rail yard.

``draw.game_draw`` hands the frame here while ``game.topdown3d`` is on
(``CAMS["MISSION6"]``; the yard and the train keep their own 3D hosts). The
sim, the AI and every collision rect stay 2D; only the look changes.

The point of this port is that M6 keeps its own colours. Nothing here is
re-lit into a grey 3D gradient; every surface shows the 2D painter's pixels:

* the floor is the baked 2D ground (snow, ruts, banks, AO, prop shadows,
  scorch, blood, pickups, particles) gathered per pixel onto the ground
  plane and painted into the frame before the 3D pass;
* wall tops, wall faces and prop faces are drawn with key colours and then
  replaced by the 2D art at the exact point each pixel's ray hits: wall
  crowns and roofs from the ground bake (faces repainted as crowns), the
  south faces from the 2D face tiles, the props' south faces (or tops) from
  their own 2D sprites;
* the 2D light pass (cold ambient, sodium and floodlight pools, the torch,
  event lamps) is built in sim space exactly as ``decor.draw_over`` does
  and applied per pixel at the point that pixel shows, then the floodlight
  beams, blasts and pickup marks are added the same way;
* the hard lamp halos, lamp housings, IFF lamps, exit lamps, falling snow
  and the HUD are drawn on the presented frame at 2D size.

Any renderer error turns 2.5D off for the run (``td.disable``) and the
frame falls back to the 2D painter.
"""
import math
import weakref

import numpy as np
import pygame

from core import outfits as _outfits
from core.config import HEIGHT, TILE_SIZE, WIDTH, font_terminal_small
from core.state import STATE
from engine.core import now_ms as _now_ms, now_s as _now_s
from game import topdown3d as td
from game.topdown3d import K, to3
from missions.m1 import draw3d as _m1

from . import combat as _combat
from . import decor as _decor
from . import maps as _maps
from . import night_fx as _nfx
from . import stealth as _stealth
from . import world as _world
from .meta import (NOMAN_TOWER_TILES, STAGE_BOXCAR, STAGE_CUSTOMS, STAGE_NOMAN, STAGE_RAIL,
                   STAGE_TRAIN, VOLKOV_BOXCAR_TILE)

CAM = td.CAMS["MISSION6"]
T = TILE_SIZE
VOID = (8, 9, 12)
AIM_H = _m1.AIM_H
STUB_H = _m1.STUB_H
FIRE = (255, 140, 56)

# Sides only: tops and south faces are keyed and repainted from the 2D art,
# so the key light just separates the east/west faces from the snow.
LIGHT = dict(direction=(-0.252, 0.756, -0.605), ambient=0.6, diffuse=0.4, sky=0.0,
             tint=(1.0, 1.0, 1.0))

WALL_H = {"C": 2.6, "W": 2.2, "band": 3.0}
WALL_SIDE = {"C": (34, 40, 52), "W": (42, 48, 58), "band": (42, 48, 58)}

# Props whose 2D sprite is a side view go on the box's south face; the few
# drawn from above go on its top. (height m, depth fraction of the footprint)
FACE = {"guard_truck": (1.9, 0.9), "truck_burnt": (1.7, 0.9), "plough": (1.9, 0.9),
        "sedan": (1.4, 0.85),
        "apc": (1.8, 0.9), "boxcar": (2.7, 0.86), "container": (2.6, 0.9),
        "booth": (2.4, 0.8), "shack": (2.6, 0.8), "snow_fence": (1.1, 0.22), "pallet": (0.9, 0.85),
        "sleeper_stack": (0.8, 0.85), "jersey": (0.8, 0.55), "sandbag": (0.75, 0.75)}
FACE_SPLIT = {"booth": 0.20}
TOP = {"counter": 1.0, "terminal": 1.1, "cabinet": 1.7, "crate": 0.9, "crates": 1.1,
       "barrels": 0.95, "coil": 0.6}
CAST_LIFT = 2.2                    # bodies take this much more of the 2D light
CUT_MIN = 1.3                      # props taller than this sink near Biribel too

_cache = {"rays": None, "atlas": {}, "gl_atlas": {}, "props": {}, "walls": {}, "meshes": {}, "packed": {},
          "scratch": {}, "heights": {}, "corpse_meshes": weakref.WeakKeyDictionary(), "gl_ground_sig": {}}

# key colours (R, G, B): the GL pass writes emissive faces verbatim
K_TOP, K_FACE, K_PFACE, K_PTOP = 254, 253, 252, 251


def _hidx(h):
    return max(0, min(250, int(round(h * 20.0))))


# ── frame ──────────────────────────────────────────────────────────────

def _gl_atlas(stage):
    """Build GPU textures (top_surf, ground_surf, props_surf) and prop UV rects."""
    hit = _cache["gl_atlas"].get(stage)
    grid = _grid(stage)
    ground0 = _decor._ground_surface(stage)
    gw, gh = ground0.get_size()
    sc_sig = (len(getattr(_combat, "_scorch", ())),
              getattr(_combat, "_tanker", {}).get("alive") if getattr(_combat, "_tanker", None) else None)
    if hit is not None and _cache["gl_ground_sig"].get(stage) == sc_sig:
        return hit
    if hit is None:
        top_surf = _top_map(stage, grid, ground0).convert(24)
        props = _props(stage)
        keyed = [(i, p) for i, p in enumerate(props) if p["mode"] in ("face", "top")]
        aw = max(64, max([p["art"].w for _, p in keyed], default=64))
        # Pack prop sprites onto a compact 2D shelf (width <= 2048)
        shelf_w = min(2048, max(512, (aw + 3) & ~3))
        cx = cy = row_h = 0
        places = {}
        for i, p in keyed:
            rect = p["art"]
            if cx + rect.w > shelf_w and cx > 0:
                cx = 0
                cy += row_h
                row_h = 0
            places[i] = (cx, cy, rect.w, rect.h)
            cx += rect.w + 1
            row_h = max(row_h, rect.h + 1)
        ph = max(64, cy + row_h)
        psurf = pygame.Surface((shelf_w, ph))
        psurf.fill((60, 60, 60))
        p_uvs = {}
        for i, p in keyed:
            rect = p["art"]
            px, py, pw, ph_i = places[i]
            tile = pygame.Surface(rect.size)
            tile.fill(p["side"] if p["mode"] == "top" else p["top"])
            tile.blit(p["surf"], (0, 0), rect)
            psurf.blit(tile, (px, py))
            p_uvs[i] = (px / float(shelf_w), py / float(ph),
                        (px + pw - 0.01) / float(shelf_w), (py + ph_i - 0.01) / float(ph))
    else:
        top_surf, _gs, psurf, p_uvs, _gver = hit

    gsurf = ground0.copy()
    if getattr(_combat, "_scorch", None) or getattr(_combat, "_blasts", None):
        _tiles(gsurf, 0, 0, lambda s, cx, cy: _combat.draw_ground(s, cx, cy))
    g_ver = _cache["gl_ground_sig"].get((stage, "ver"), 0) + 1
    _cache["gl_ground_sig"][(stage, "ver")] = g_ver
    _cache["gl_ground_sig"][stage] = sc_sig
    res = (top_surf, gsurf, psurf, p_uvs, g_ver)
    _cache["gl_atlas"][stage] = res
    return res


def _uv_box(w, d, hgt, side, top_uvs=None, top_slot=-2.0, front_uvs=None, front_slot=-3.0):
    """Lit box with explicit UVs on top/front faces for GPU M6 rendering."""
    from engine3d import Mesh, box
    hw, hd = w * 0.5, d * 0.5
    skip = ["bottom"]
    if top_uvs is not None:
        skip.append("top")
    if front_uvs is not None:
        skip.append("front")
    m = Mesh()
    m.add(box(w, hgt, d, side, center=(0.0, hgt * 0.5, 0.0), skip=tuple(skip)))
    if top_uvs is not None:
        i0 = len(m.verts)
        m.verts.extend(((-hw, hgt, hd), (hw, hgt, hd), (hw, hgt, -hd), (-hw, hgt, -hd)))
        u0, v0, u1, v1 = top_uvs
        m.faces.append(((i0, i0 + 1, i0 + 2, i0 + 3), (255, 255, 255), 2, False, False, 0.0,
                        ("uv", top_slot, ((u0, v0), (u1, v0), (u1, v1), (u0, v1)))))
    if front_uvs is not None:
        i0 = len(m.verts)
        m.verts.extend(((-hw, hgt, -hd), (hw, hgt, -hd), (hw, 0.0, -hd), (-hw, 0.0, -hd)))
        u0, v0, u1, v1 = front_uvs
        m.faces.append(((i0, i0 + 1, i0 + 2, i0 + 3), (255, 255, 255), 2, False, False, 0.0,
                        ("uv", front_slot, ((u0, v0), (u1, v0), (u1, v1), (u0, v1)))))
    return m


def _floor_quad_mesh(gw, gh):
    from engine3d import Mesh
    m = Mesh()
    x1, z1 = gw * K, -gh * K
    m.verts = [(0.0, 0.0, 0.0), (x1, 0.0, 0.0), (x1, 0.0, z1), (0.0, 0.0, z1)]
    m.faces.append(((0, 1, 2, 3), (255, 255, 255), 0, False, False, 0.0,
                    ("uv", -3.0, ((0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)))))
    return m


def _gl_fx(r, stage, tm):
    """Submit M6 blood decals, pickups, bottles, bullets, smoke & particles on GPU."""
    from cutscenes import m6fx3d as _fx
    from core.config import C_BULLET
    from engine3d.particles import PKIND_SMOKE, pack_blood_decals
    t = _now_s()
    for decal in getattr(STATE, "blood_decals", [])[:]:
        decal[2] -= 0.5
        if decal[2] <= 0 and decal in STATE.blood_decals:
            STATE.blood_decals.remove(decal)
    if getattr(STATE, "blood_decals", None):
        d_arr = pack_blood_decals(STATE.blood_decals, to3, (80, 12, 14))
        if d_arr is not None:
            r.add_decals(d_arr)
    for pu in getattr(STATE, "pickups", []):
        x, _, z = to3(pu[0], pu[1])
        bob = 0.06 * math.sin(t * 3 + pu[0])
        kind = "bandage" if (len(pu) > 2 and pu[2] == "bandage") else "mag"
        _put(r, _mesh(("m6pu", kind), lambda k=kind: _m1._pickup_mesh(k)), (x, 0.25 + bob, z),
             yaw=(t * 60.0 + pu[0]) % 360.0)
        r.add_sprite((x, 0.3, z), _fx.glow(_m1._PICKUP_COL.get(kind, (255, 210, 40)), 0.28, tm,
                                           intensity=0.7, max_px=16), layer=_fx.FX_LAYER)
    for b in getattr(STATE, "bullets", []):
        head = to3(b["x"], b["y"], AIM_H)
        tail = to3(b.get("prev_x", b["x"] - b["dx"]), b.get("prev_y", b["y"] - b["dy"]), AIM_H)
        r.add_line3d(tail, head, (255, 220, 140), 2, layer=4)
        r.add_sprite(head, _fx.glow(C_BULLET, 0.14, tm, intensity=0.95, max_px=12), layer=_fx.FX_LAYER)
    if getattr(STATE, "particles", None):
        td.dots(r, [(to3(p.x, p.y, 0.25 + 0.03 * getattr(p, "life", 0)), p.color, getattr(p, "size", 2))
                    for p in STATE.particles], layer=_fx.FX_LAYER)
    if getattr(STATE, "casings", None):
        td.dots(r, [(to3(c.x, c.y, 0.03), (200, 160, 70), 2) for c in STATE.casings], layer=1)
    smoke = getattr(_combat, "_smoke", None)
    if smoke:
        ct = getattr(_combat, "_t", 0.0)
        rows = []
        for p in smoke:
            age = (ct - p["t0"]) / max(0.01, p["life"])
            if age >= 1.0:
                continue
            wp = to3(p["x"], p["y"], 1.0 + 0.8 * age)
            rad = p["r"] * K * (1.0 + 0.9 * age)
            sh = p.get("shade", 90) / 255.0
            rows.append((wp[0], wp[1], wp[2], 0.0, 0.4, 0.0, sh, sh, sh,
                         0.45 * (1.0 - age), rad, float(PKIND_SMOKE), age, p["x"] * 0.17))
        if rows:
            r.add_particles(np.asarray(rows, dtype=np.float32))
    if stage in (STAGE_RAIL, STAGE_BOXCAR):
        bx, by = (VOLKOV_BOXCAR_TILE[0] + 0.5) * T, (VOLKOV_BOXCAR_TILE[1] + 0.5) * T
        pulse = 0.5 + 0.5 * math.sin(t * 3.0)
        r.add_sprite(to3(bx, by, 0.02), td.tac_ring(0.75 + 0.1 * pulse, (160, 214, 240)), layer=0)


def _gl_grade_lights(stage, tm):
    """Build GPU grade3d light tuples for M6 from stage lamps, searchlights & fires."""
    out = []
    for i, (tx, ty, radius, colour, kind) in enumerate(_decor._STAGE_LAMPS.get(stage, ())):
        if kind.startswith("tower") and _decor._light_dead(int(kind[5:])):
            continue
        k = _decor._lamp_on("steady" if kind.startswith("tower") else kind, i)
        if k <= 0.05:
            continue
        wx, wy = tx * T, ty * T
        wp = to3(wx, wy, 0.0)
        out.append(("pool", wp, colour, radius * K * 0.9, 0.65 * k))
    for fz in getattr(STATE, "fire_zones", []):
        heat = min(1.0, fz.life / float(max(1, fz.max_life)) * 4.0)
        x, _, z = to3(fz.x, fz.y)
        out.append(("fire", (x, 1.0, z), FIRE, fz.radius * K + 1.0, heat))
    p = STATE.player
    if p is not None and not STATE.player_dead:
        out.append(("cone", to3(p.rect.centerx, p.rect.centery), p.angle, (218, 236, 248), 5.8, 0.68))
    return out


def _gl_local_lights(stage, flashes, tm):
    """Collect stage lamps & floodlights as real 3D local lights (up to 64)."""
    out = list(flashes)
    for i, (tx, ty, radius, colour, kind) in enumerate(_decor._STAGE_LAMPS.get(stage, ())):
        tower = kind.startswith("tower")
        if tower and _decor._light_dead(int(kind[5:])):
            continue
        k = _decor._lamp_on("steady" if tower else kind, i)
        if k <= 0.05:
            continue
        hh = 6.8 if tower else 2.5
        out.append({
            "pos": to3(tx * T, ty * T, hh), "color": colour,
            "intensity": 0.45 * k, "range": max(3.5, radius * K * 1.15),
        })
    return out[:64]

def render_world(surface, fcx, fcy):
    """Draw the live M6 stage through the follow camera onto ``surface``."""
    from cutscenes import m6fx3d as _fx
    from cutscenes import m6world3d as _w
    from engine3d import Light
    stage = _stage()
    # whole sim pixels, as the 2D painter (int(cam)): the floor lookups stay constant
    fx, fy = float(int(math.floor(fcx)) + WIDTH // 2), float(int(math.floor(fcy)) + HEIGHT // 2)
    v = td.View(CAM, fx, fy)
    is_gl = False
    r, buf = _w.rend(*td.buffer_res(CAM), hdr=True)
    is_gl = (getattr(r, "backend", "") == "gl")
    saved = (r.light, r.fog, r.fog_start, r.fog_end, r.light_cap,
             getattr(r, "light_albedo", False), getattr(r, "light_gain", 1.0),
             getattr(r, "hdr", False), getattr(r, "dither", False),
             getattr(r, "ps1_snap", False))
    tm = _now_ms()
    try:
        if is_gl:
            top_s, gnd_s, prp_s, p_uvs, g_ver = _gl_atlas(stage)
            gw, gh = gnd_s.get_size()
            r.set_extra_textures(
                ("m6_top_%s" % stage, top_s),
                ("m6_gnd_%s_%d" % (stage, g_ver), gnd_s),
                ("m6_prp_%s" % stage, prp_s),
            )
            r.light = Light(**LIGHT)
            r.fog, r.fog_start, r.fog_end = VOID, 40.0, 90.0
            r.light_cap = 64
            r.light_albedo = True
            r.light_gain = 1.1
            r.wetness = 0.45
            r.height_fog = (0.024, 0.0, 1.4, (14, 18, 28))
            v.apply(r)
            r.begin()
            first = _w.static_scene(r, ("m6_td3d_gl", stage))
            ok = False
            try:
                if first:
                    _build_static(r, stage)
                ok = True
            finally:
                _w.static_end(r, ok)
            r.shadow_boxes = ()
            _put(r, _mesh(("m6_floor", stage, gw, gh), lambda: _floor_quad_mesh(gw, gh)), (0.0, 0.0, 0.0))
            flashes = []
            _draw_walls(r, stage, gl_dims=(gw, gh))
            _draw_props(r, stage, tm, gl_uvs=p_uvs)
            _draw_combat(r, gl_uvs=p_uvs)
            _draw_cast(r, flashes, tm, v)
            _draw_fires(r, flashes, tm, v)
            _gl_fx(r, stage, tm)
            r.set_pools([])
            r.set_lights(_gl_local_lights(stage, flashes, tm), cap=64)
            td.cast_shadows(r)
            lp = _decor._light_pass(stage, 0, 0, (64, 64))
            r.flush_to(surface, bg=VOID, post={
                "bloom": 0.24, "bloom_knee": 0.98,
                "grade3d": (v, _gl_grade_lights(stage, tm), lp.ambient),
                "char_lift": 0.85,
            })
            _emissives(surface, v, stage)
            _decor._snow(surface, 40 if stage == STAGE_CUSTOMS else 70)
            if STATE.player_dead:
                _death_edge(surface)
            return True

        if hasattr(r, "hdr"):
            r.hdr = False
            r.dither = False
            r.ps1_snap = False
        R = _rays(v)
        cx0, cy0, bw, bh = R["crop"]
        bx0, by0 = int(fx) + cx0, int(fy) + cy0
        crop = _scratch("crop", (bw, bh), buf)
        _paint_ground(crop, stage, bx0, by0)
        flat = _flat(crop)
        lin0 = R["lin0"]
        floor2 = flat[lin0]           # packed pixels
        del flat
        r.light = Light(**LIGHT)
        r.fog, r.fog_start, r.fog_end = VOID, 900.0, 1000.0
        r.light_cap = 8
        v.apply(r)
        px = _fv(buf)
        px[...] = floor2
        del px
        r.begin()
        first = _w.static_scene(r, ("m6_td3d", stage))
        ok = False
        try:
            if first:
                _build_static(r, stage)
            ok = True
        finally:
            _w.static_end(r, ok)
        r.shadow_boxes = ()           # the 2D bake already carries the set's shadows
        flashes = []
        _draw_walls(r, stage)
        _draw_props(r, stage, tm)
        _draw_combat(r)
        _draw_cast(r, flashes, tm, v)
        _draw_fires(r, flashes, tm, v)
        r.set_pools([])
        r.set_lights(flashes[:8], cap=8)
        td.cast_shadows(r)
        r.flush(buf)
        _draw_smoke(buf, v)
        _draw_bullets(buf, v)
        nf, lin, other = _decode(buf, floor2, R, stage, fx, fy, bx0, by0, bw, bh)
        body, feet = _cast_mask(v, buf.get_size())
        # only the cast's own pixels can be lifted: test the blob shadow there
        body = body[nf] & other
        lift = body & ~_shaded_floor(buf, floor2, nf, feet[nf] & body)
        _light(buf, stage, nf, lin, lin0, crop, bx0, by0, bw, bh, lift, tm)
    except Exception:
        import traceback
        traceback.print_exc()
        td.disable()                  # next frame is the 2D painter
        return False
    finally:
        r.light, r.fog, r.fog_start, r.fog_end, r.light_cap, sla, slg, shdr, sdith, ssnap = saved
        r.light_albedo, r.light_gain = sla, slg
        if hasattr(r, "hdr"):
            r.hdr, r.dither, r.ps1_snap = shdr, sdith, ssnap
    _fx.present_crisp(buf, surface)
    _emissives(surface, v, stage)
    _decor._snow(surface, 40 if stage == STAGE_CUSTOMS else 70)
    if STATE.player_dead:
        _death_edge(surface)
    return True


def _stage():
    s = getattr(STATE, "mission6_stage", STAGE_CUSTOMS)
    return STAGE_RAIL if s == STAGE_BOXCAR else s


def _grid(stage):
    return _maps.grid_for(stage)


def _scratch(name, size, like):
    s = _cache["scratch"].get(name)
    if s is None or s.get_size() != size or s.get_bitsize() != like.get_bitsize():
        s = _cache["scratch"][name] = pygame.Surface(size, 0, like)
    return s


def _mesh(key, build):
    m = _cache["meshes"].get(key)
    if m is None:
        if len(_cache["meshes"]) > 3000:
            _cache["meshes"].clear()
            _cache["packed"].clear()
        m = _cache["meshes"][key] = build()
    return m


def _put(r, mesh, pos, yaw=0.0, roll=0.0):
    td.put(r, mesh, pos, yaw, roll, 1.0, cache=_cache["packed"])


def _shade(col, k):
    return tuple(max(0, min(255, int(c * k))) for c in col)


def _death_edge(surface):
    red = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    for i in range(6):
        pygame.draw.rect(red, (120, 0, 0, 70 - i * 10),
                         (i * 6, i * 6, WIDTH - i * 12, HEIGHT - i * 12), 6)
    surface.blit(red, (0, 0))


# ── rays: every buffer pixel against the planes it can show ────────────

def _rays(v):
    """Per-pixel ray directions of the follow camera (it only translates,
    so they are constant), and the sim offsets from the focus at which the
    rays meet the floor and the 1 m plane.

    Every per-pixel array in this pass is flat and row-major (index
    y * w + x, the buffer's own memory order): flat ``flatnonzero`` and 1-D
    gathers are several times faster than 2-D ``nonzero`` and tuple indexing."""
    key = (v.w, v.h, CAM.pitch, CAM.dist, CAM.fov, CAM.look_h)
    hit = _cache["rays"]
    if hit is not None and hit[0] == key:
        return hit[1]
    w, h = v.w, v.h
    i, j = np.meshgrid(np.arange(w, dtype=np.float64) + 0.5,
                       np.arange(h, dtype=np.float64) + 0.5, indexing="xy")
    i, j = i.reshape(-1), j.reshape(-1)
    xs = (i - w / 2.0) / v.focal
    ys = (h / 2.0 - j) / v.focal
    d = [v.fwd[k] + v.right[k] * xs + v.up[k] * ys for k in range(3)]
    dy = np.minimum(d[1], -1e-4)
    R = {"dx": d[0], "dy": dy, "dz": np.maximum(d[2], 1e-4), "ey": v.eye[1],
         "ez": v.eye[2] - v.tgt[2], "ax": d[0] / dy / K, "az": d[2] / dy / K}
    for k in ("dx", "dy", "dz", "ax", "az"):
        R[k] = R[k].astype(np.float32)
    R["o0"] = tuple(a.astype(np.float32) for a in _plane(R, 0.0))
    R["o1"] = tuple(a.astype(np.float32) for a in _plane(R, 1.0))
    hi = _plane(R, 3.4)
    R["bb"] = (min(R["o0"][0].min(), hi[0].min()), min(R["o0"][1].min(), hi[1].min()),
               max(R["o0"][0].max(), hi[0].max()), max(R["o0"][1].max(), hi[1].max()))
    # the ground crop round a whole-pixel focus, and where the floor and the
    # 1 m plane fall in it: constant while the camera only translates
    mnx, mny, mxx, mxy = R["bb"]
    cx0, cy0 = int(math.floor(mnx)) - 2, int(math.floor(mny)) - 2
    bw, bh = int(mxx - mnx) + 6, int(mxy - mny) + 6
    R["crop"] = (cx0, cy0, bw, bh)
    R["lin0"] = _lin(R["o0"], -cx0, -cy0, bw, bh)
    R["lin1"] = _lin(R["o1"], -cx0, -cy0, bw, bh)
    _cache["rays"] = (key, R)
    return R


def _plane(R, h, sel=None):
    """Sim offsets (dx, dy) from the focus where rays meet the plane at h m."""
    ax, az = (R["ax"], R["az"]) if sel is None else (R["ax"][sel], R["az"][sel])
    dh = h - R["ey"]
    return ax * dh, -R["ez"] / K - az * dh


def _lin(off, ox, oy, w, h):
    """Flat (row-major) indices into a w x h surface at ``off`` + (ox, oy)."""
    ix = np.clip((off[0] + ox).astype(np.int32), 0, w - 1)
    iy = np.clip((off[1] + oy).astype(np.int32), 0, h - 1)
    # native intp: an int32 index is converted on every gather (2x the cost)
    return (iy * w + ix).astype(np.intp)


def _flat(surf):
    """The surface's packed pixels as one flat row-major array (locks it
    until the array is gone)."""
    a = pygame.surfarray.pixels2d(surf).T
    return a.reshape(-1) if a.flags.c_contiguous else np.ascontiguousarray(a).reshape(-1)


def _fv(surf):
    """Writable flat row-major view of the packed pixels (locks ``surf``)."""
    a = pygame.surfarray.pixels2d(surf).T
    if not a.flags.c_contiguous:
        raise ValueError("padded surface rows")
    return a.reshape(-1)


def _f3(surf):
    """Writable (w * h, 3) row-major view of the RGB channels (locks ``surf``)."""
    a = pygame.surfarray.pixels3d(surf).transpose(1, 0, 2)
    if a.strides[0] != a.strides[1] * a.shape[1]:
        raise ValueError("padded surface rows")
    f = a.reshape(-1, 3)
    if not np.may_share_memory(f, a):
        raise ValueError("pixel copy")
    return f


def _rgb(v, surf, dtype=np.uint8):
    """Packed pixels -> (..., 3) channels in ``surf``'s format."""
    sh = surf.get_shifts()
    return np.stack([(v >> sh[i]) & 255 for i in range(3)], -1).astype(dtype)


# ── ground: the 2D bake plus everything 2D paints flat on it ───────────

def _tiles(surf, bx0, by0, fn):
    """Run a 2D painter that culls to WIDTH x HEIGHT over a bigger crop."""
    bw, bh = surf.get_size()
    for oy in range(0, bh, HEIGHT):
        for ox in range(0, bw, WIDTH):
            sub = surf.subsurface((ox, oy, min(WIDTH, bw - ox), min(HEIGHT, bh - oy)))
            fn(sub, bx0 + ox, by0 + oy)


def _paint_ground(crop, stage, bx0, by0):
    from entities import weapons as _weapons
    from entities.art_cache import get_blood_decal
    from . import draw as _draw
    void = _decor.void_surface()
    vw, vh = void.get_size()
    bw, bh = crop.get_size()
    for y in range(-(by0 % vh), bh, vh):
        for x in range(-(bx0 % vw), bw, vw):
            crop.blit(void, (x, y))
    crop.blit(_decor._ground_surface(stage), (-bx0, -by0))
    for decal in getattr(STATE, "blood_decals", [])[:]:
        try:
            d_surf = get_blood_decal(decal[3])
            d_surf.set_alpha(int(decal[2]))
            crop.blit(d_surf, (decal[0] - decal[3] - bx0, decal[1] - decal[3] - by0))
            decal[2] -= 0.5
            if decal[2] <= 0 and decal in STATE.blood_decals:
                STATE.blood_decals.remove(decal)
        except Exception:
            if decal in getattr(STATE, "blood_decals", []):
                STATE.blood_decals.remove(decal)

    def flat(s, cx, cy):
        _combat.draw_ground(s, cx, cy)
        _draw._draw_beacon(s, cx, cy)
        for pu in getattr(STATE, "pickups", []):
            _draw._draw_pickup(s, pu, cx, cy)
        _weapons.draw_thrown_bottles(s, cx, cy)
        for p in getattr(STATE, "particles", []):
            p.draw(s, cx, cy)
        for c in getattr(STATE, "casings", []):
            c.draw(s, cx, cy)
    _tiles(crop, bx0, by0, flat)


# ── atlas: the 2D art the key colours are replaced with ────────────────

def _top_map(stage, grid, ground):
    """The ground bake seen from above the walls: face tiles become crowns
    (the face art goes on the 3D south faces instead)."""
    top = ground.copy()
    h, w = len(grid), len(grid[0])
    faces = [(c, r) for r in range(h) for c in range(w) if _decor._face_tile(grid, c, r)]
    g2 = [list(row) for row in grid]
    for c, r in faces:
        if r + 1 < h:
            g2[r + 1][c] = "C"
    g2 = ["".join(row) for row in g2]
    outdoor = _decor._outdoor_tiles(stage)
    for c, r in faces:
        _decor._paint_wall(top, stage, c, r, grid[r][c], g2, outdoor)
    return top


def _mean(surf, rect=None):
    a = pygame.surfarray.pixels_alpha(surf)
    c = pygame.surfarray.pixels3d(surf)
    if rect is not None:
        x, y, w, h = rect
        a, c = a[x:x + w, y:y + h], c[x:x + w, y:y + h]
    m = a > 40
    out = tuple(int(v) for v in c[m].mean(axis=0)) if m.any() else (60, 60, 60)
    del a, c
    return out


def _props(stage):
    """Static props as 3D boxes: (dict per prop). Built once per stage."""
    hit = _cache["props"].get(stage)
    if hit is not None:
        return hit
    out = []
    for row, (kind, c0, r0, tw, th) in zip(_decor._prop_rows(stage), _decor._stage_props(stage)):
        surf, fh = row["surf"], row["fh"]
        x0, y0, x1, y1 = c0 * T, r0 * T, (c0 + tw) * T, (r0 + th) * T
        p = {"kind": kind, "c": c0, "r": r0, "x0": x0, "y0": y0, "x1": x1, "y1": y1, "surf": surf, "fh": fh}
        if kind in FACE:
            hgt, depth = FACE[kind]
            rect = surf.get_bounding_rect(min_alpha=40)
            mid = (y0 + y1) / 2.0
            d = (y1 - y0) * depth
            p.update(mode="face", h=hgt, art=rect, x0=x0 + rect.x, x1=x0 + rect.right,
                     y0=mid - d / 2.0, y1=mid + d / 2.0, side=_shade(_mean(surf, rect), 0.82),
                     top=_mean(surf, (rect.x, rect.y, rect.w, min(4, rect.h))))
        elif kind in TOP:
            rect = surf.get_bounding_rect(min_alpha=40)
            p.update(mode="top", h=TOP[kind], art=rect, x0=x0 + 3, x1=x1 - 3, y0=y0 + 3, y1=y1 - 3,
                     side=_shade(_mean(surf, rect), 0.7))
        else:
            p.update(mode=kind, h=0.0)
        out.append(p)
    # the yard fuel tank (combat owns it): drawn from above, whole and wrecked
    for kind, c0, r0, tw, th in _maps.props_for(stage):
        if kind != "fuel_tank":
            continue
        for alive in (True, False):
            surf = _decor.fuel_tank_surface(tw * T, th * T, alive=alive)
            rect = surf.get_bounding_rect(min_alpha=40)
            x0, y0 = c0 * T, r0 * T
            out.append({"kind": kind, "tank": alive, "c": c0, "r": r0, "surf": surf, "fh": th * T,
                        "mode": "top", "h": 1.7 if alive else 0.8, "art": rect,
                        "x0": x0 + rect.x, "x1": x0 + rect.right, "y0": y0 + rect.y,
                        "y1": y0 + rect.bottom, "side": _shade(_mean(surf, rect), 0.7)})
    _cache["props"][stage] = out
    return out


def _atlas(stage, like):
    """One array holding the top map, the face bake and every keyed prop's
    sprite (composited on its own mean colour), plus per-prop lookup rows."""
    hit = _cache["atlas"].get(stage)
    if hit is not None:
        return hit
    grid = _grid(stage)
    ground = _decor._ground_surface(stage)
    gw, gh = ground.get_size()
    props = _props(stage)
    keyed = [p for p in props if p["mode"] in ("face", "top")]
    aw = max([gw] + [p["art"].w for p in keyed])
    ah = gh * 2 + sum(p["art"].h for p in keyed)
    atl = pygame.Surface((aw, ah))
    atl.fill((60, 60, 60))
    atl.blit(_top_map(stage, grid, ground), (0, 0))
    atl.blit(ground, (0, gh))
    n = len(props)
    tab = {k: np.zeros(max(1, n), np.float64) for k in
           ("x0", "x1", "y0", "y1", "h", "ax", "ay", "aw", "ah", "face", "ytop", "split")}
    cp, sp = math.cos(math.radians(CAM.pitch)), math.sin(math.radians(CAM.pitch))
    y = gh * 2
    for i, p in enumerate(props):
        if p["mode"] not in ("face", "top"):
            continue
        rect = p["art"]
        tile = pygame.Surface(rect.size)
        tile.fill(p["side"] if p["mode"] == "top" else p["top"])
        tile.blit(p["surf"], (0, 0), rect)
        atl.blit(tile, (0, y))
        for k in ("x0", "x1", "y0", "y1", "h"):
            tab[k][i] = p[k]
        tab["ax"][i], tab["ay"][i], tab["aw"][i], tab["ah"][i] = 0, y, rect.w, rect.h
        tab["ytop"][i] = p["r"] * T + p["fh"] - p["surf"].get_height() + rect.y
        if p["mode"] == "face":
            # share of the sprite's height the roof takes, by projected size
            dp, hp = (p["y1"] - p["y0"]) * K * sp, p["h"] * cp
            tab["face"][i] = 1.0
            tab["split"][i] = FACE_SPLIT.get(p["kind"], dp / (dp + hp))
        y += rect.h
    conv = pygame.Surface(atl.get_size(), 0, like)
    conv.blit(atl, (0, 0))
    arr = pygame.surfarray.array2d(conv)                                  # packed
    out = {"arr": arr, "flat": np.ascontiguousarray(arr.T).reshape(-1), "gh": gh, "tab": tab}
    _cache["atlas"][stage] = out
    return out


# ── key decode ─────────────────────────────────────────────────────────

# green of the floor under the shared cast shadow, per floor green (as _decode used to compute it)
_SHADOW_G_LUT = (np.arange(256) * (1.0 - 100 / 255.0)
                 + td.SHADOW_COL[1] * (100 / 255.0)).astype(np.int16)

# per-pixel work in L2-sized slices: whole-frame temporaries ran ~2x slower
_CHUNK = 16384


def _decode(buf, floor2, R, stage, fx, fy, bx0, by0, bw, bh):
    """Swap the key colours for the 2D art. Returns ``nf``, the flat indices
    of the pixels the 3D pass touched (the rest is untouched floor), and per
    ``nf`` pixel the crop index of the sim point whose 2D light it takes (the
    floor point, the wall/prop point, or, for everything else: bodies and
    sides, the 1 m plane point) and whether it is ``other`` (neither floor
    nor 2D art). Only ``nf`` is worked on: it is about a third of the frame."""
    atl = _atlas(stage, buf)
    p2 = _fv(buf)
    nf = np.flatnonzero(p2 != floor2)
    lin = np.empty(nf.shape, np.intp)
    other = np.empty(nf.shape, bool)
    shifts = buf.get_shifts()[:3]
    for i in range(0, nf.size, _CHUNK):
        j = slice(i, i + _CHUNK)
        _decode_part(p2, floor2, nf[j], lin[j], other[j], buf, shifts, atl, R, fx, fy, bx0, by0, bw, bh)
    del p2
    return nf, lin, other


def _decode_part(p2, floor2, nf, lin, other, buf, shifts, atl, R, fx, fy, bx0, by0, bw, bh):
    """``_decode`` for one slice of ``nf``: fills that slice's ``lin`` and
    ``other`` and writes the 2D art into ``p2``. Pixels are independent."""
    arr, gh, tab = atl["arr"], atl["gh"], atl["tab"]
    aw, ah = arr.shape[0], arr.shape[1]
    q = p2[nf]
    f2 = floor2[nf]
    sr, sg, sb = shifts
    gg = (q >> sg) & 255
    # the shared cast shadow is the floor darkened: light it as floor
    a = 100 / 255.0
    # green first: most non-floor pixels fail it, the rest get all three
    eg = _SHADOW_G_LUT[(f2 >> sg) & 255]
    sh = np.flatnonzero(np.abs(gg.astype(np.int16) - eg) <= 3)
    shade = _rgb(f2[sh], buf, np.float32) * (1.0 - a) + np.array(td.SHADOW_COL, np.float32) * a
    hit = (np.abs(_rgb(q[sh], buf, np.float32) - shade) <= 3.0).all(axis=1)
    sh = sh[hit]
    np.take(R["lin1"], nf, out=lin)
    lin[sh] = R["lin0"][nf[sh]]
    other[...] = True
    other[sh] = False
    rr = (q >> sr) & 255
    sel = np.flatnonzero((rr >= K_PTOP) & (rr <= K_TOP) & (gg <= 70) & other)
    if sel.size:
        r_, g_ = rr[sel], gg[sel].astype(np.float32)
        b_ = ((q[sel] >> sb) & 255).astype(np.int32)
        loc, sel = sel, nf[sel]           # positions in nf, and in the frame
        sx = np.empty(r_.shape, np.float32); sy = np.empty(r_.shape, np.float32)
        ax_ = np.zeros(r_.shape, np.int64); ay_ = np.zeros(r_.shape, np.int64)
        good = np.zeros(r_.shape, bool)
        # wall tops: the plane at h = B/20
        # each class as indices, once: a bool mask is re-scanned on every use
        m = np.flatnonzero((r_ == K_TOP) & (g_ == 1))
        if m.size:
            s = sel[m]
            ox, oy = _plane(R, b_[m] / 20.0, s)
            X, Y = (ox + fx).astype(np.float32), (oy + fy).astype(np.float32)
            sx[m], sy[m] = X, Y
            ax_[m], ay_[m] = X, Y
            good[m] = True
        # wall south faces: row B, full height (G-2)/20
        m = np.flatnonzero((r_ == K_FACE) & (g_ >= 2))
        if m.size:
            s = sel[m]
            Y = (b_[m] + 1) * T
            t = (-(Y - fy) * K - R["ez"]) / R["dz"][s]
            hh = R["ey"] + R["dy"][s] * t
            fv = np.clip(1.0 - hh / np.maximum(0.05, (g_[m] - 2) / 20.0), 0.0, 0.999)
            X = (fx + R["dx"][s] * t / K).astype(np.float32)
            Y = (b_[m] * T + fv * T).astype(np.float32)
            sx[m], sy[m] = X, Y
            ax_[m], ay_[m] = X, gh + Y
            good[m] = True
        # prop south faces: prop B's sprite across its width and height
        m = np.flatnonzero((r_ == K_PFACE) & (g_ >= 2))
        if m.size:
            s = sel[m]
            e = np.clip(b_[m], 0, len(tab["h"]) - 1)
            Y = tab["y1"][e]
            t = (-(Y - fy) * K - R["ez"]) / R["dz"][s]
            hh = R["ey"] + R["dy"][s] * t
            x = fx + R["dx"][s] * t / K
            u = np.clip((x - tab["x0"][e]) / np.maximum(1.0, tab["x1"][e] - tab["x0"][e]), 0, 0.999)
            fv = np.clip(1.0 - hh / np.maximum(0.05, tab["h"][e]), 0.0, 0.999)
            sp_ = tab["split"][e]
            fv = sp_ + fv * (1.0 - sp_)
            ax_[m] = tab["ax"][e] + u * tab["aw"][e]
            ay_[m] = tab["ay"][e] + fv * tab["ah"][e]
            sx[m], sy[m] = x, tab["ytop"][e] + fv * tab["ah"][e]
            good[m] = True
        # prop tops: prop B's sprite across its footprint, plane (G-2)/20
        m = np.flatnonzero((r_ == K_PTOP) & (g_ >= 2))
        if m.size:
            s = sel[m]
            e = np.clip(b_[m], 0, len(tab["h"]) - 1)
            ox, oy = _plane(R, (g_[m] - 2) / 20.0, s)
            x, y = ox + fx, oy + fy
            u = np.clip((x - tab["x0"][e]) / np.maximum(1.0, tab["x1"][e] - tab["x0"][e]), 0, 0.999)
            w = np.clip((y - tab["y0"][e]) / np.maximum(1.0, tab["y1"][e] - tab["y0"][e]), 0, 0.999)
            face = tab["face"][e] > 0.5
            w = np.where(face, w * tab["split"][e], w)
            ax_[m] = tab["ax"][e] + u * tab["aw"][e]
            ay_[m] = tab["ay"][e] + w * tab["ah"][e]
            sx[m], sy[m] = x, np.where(face, tab["ytop"][e] + w * tab["ah"][e], y)
            good[m] = True
        if good.any():
            good = slice(None) if good.all() else good   # usually all: skip the mask copies
            s = sel[good]
            # in place (out=): fresh temporaries this size cost more than the maths
            ai, ax = ay_[good], ax_[good]
            np.clip(ai, 0, ah - 1, out=ai)
            ai *= aw
            ai += np.clip(ax, 0, aw - 1, out=ax)
            p2[s] = atl["flat"][ai]
            s = loc[good]
            ty, tx = sy[good] - by0, sx[good] - bx0
            li = np.clip(ty, 0, bh - 1, out=ty).astype(np.int32)
            li *= bw
            li += np.clip(tx, 0, bw - 1, out=tx).astype(np.int32)
            lin[s] = li
            other[s] = False


# ── the 2D light pass, per pixel ───────────────────────────────────────

def _shaded_floor(buf, floor2, nf, where):
    """Which of the ``nf`` pixels flagged in ``where`` are the floor
    darkened (blob shadows at the feet)."""
    out = np.zeros(where.shape, bool)
    loc = np.flatnonzero(where)
    if not loc.size:
        return out
    sel = nf[loc]
    a = _f3(buf)
    px = a[sel].astype(np.float32)
    del a
    f = _rgb(floor2[sel], buf, np.float32)
    k = px.sum(axis=1) / np.maximum(1.0, f.sum(axis=1))
    out[loc] = (k > 0.25) & (k <= 1.0) & (np.abs(px - f * k[:, None]) <= 4.0).all(axis=1)
    return out


def _cast_mask(v, size):
    """Buffer pixels that can hold a body (a box from feet to head round
    every living actor) and the box of each one's blob shadow."""
    w, h = size
    m = np.zeros((h, w), bool)
    f = np.zeros((h, w), bool)
    pts = [(e.rect.centerx, e.rect.centery) for e in getattr(STATE, "enemies", [])
           if getattr(e, "hp", 1) > 0]
    if STATE.player is not None:
        pts.append(STATE.player.rect.center)
    vk = _world.volkov()
    if vk and not vk.get("dead"):
        pts.append((vk["x"], vk["y"]))
    for x, y in pts:
        foot, head = _bpt(v, x, y + 12, 0.0), _bpt(v, x, y, 2.1)
        if foot is None or head is None:
            continue
        hw = int(abs(foot[1] - head[1]) * 0.45) + 2
        x0, x1 = max(0, int(foot[0]) - hw), min(w, int(foot[0]) + hw)
        y0, y1 = max(0, int(head[1]) - 2), min(h, int(foot[1]) + 2)
        if x0 < x1 and y0 < y1:
            m[y0:y1, x0:x1] = True
        n, s_ = _bpt(v, x, y - 0.32 / K, 0.0), _bpt(v, x, y + 0.32 / K, 0.0)
        if n is not None and s_ is not None:
            bw = int(abs(s_[1] - n[1]) * 0.6) + 3
            cx = int((n[0] + s_[0]) / 2)
            f[max(0, int(n[1]) - 1):min(h, int(s_[1]) + 2), max(0, cx - bw):min(w, cx + bw)] = True
    return m.reshape(-1), f.reshape(-1)


def _m6_fire_grad(col, rad):
    rad = max(8, min(240, int(rad) // 4 * 4))
    cq = tuple(max(0, min(255, int(c) // 8 * 8)) for c in col)
    key = ("m6fg", cq, rad)
    hit = _cache["meshes"].get(key)
    if hit is not None:
        return hit
    from cutscenes import fire3d as _f3d
    s = _f3d._soft_halo(cq, rad)
    _cache["meshes"][key] = s
    return s


def _light(buf, stage, nf, lin, lin0, crop, bx0, by0, bw, bh, lift, tm=0):
    """The 2D light pass. Bare floor takes the crop lit exactly as
    ``LightMap.apply`` lights it; every ``nf`` pixel (see ``_decode``) is
    multiplied by the light at its own sim point."""
    lp = _decor._light_pass(stage, bx0, by0, (bw, bh))
    lm = _scratch("lm", (bw, bh), buf)
    lm.fill(tuple(c // 2 for c in lp.ambient))
    add = pygame.BLEND_RGB_ADD
    for spr, pos in lp.lamps:
        lm.blit(spr, pos, special_flags=add)
    ov = _additive(stage, bx0, by0, bw, bh, buf)
    fzones = getattr(STATE, "fire_zones", [])
    if fzones:
        if ov is None:
            ov = _scratch("add", (bw, bh), buf)
            ov.fill((0, 0, 0))
        for fz in fzones:
            fx_c, fy_c = int(fz.x - bx0), int(fz.y - by0)
            if fx_c < -160 or fx_c > bw + 160 or fy_c < -160 or fy_c > bh + 160:
                continue
            heat = min(1.0, fz.life / float(max(1, fz.max_life)) * 4.0)
            flick = _m1._flicker(tm, fz.x * 0.7 + fz.y)
            k = min(1.25, heat * flick)
            g_spill = _m6_fire_grad((int(175 * k), int(78 * k), int(20 * k)), fz.radius * 2.3)
            g_core = _m6_fire_grad((int(138 * min(1.15, k)), int(134 * min(1.15, k)), int(124 * min(1.15, k))), fz.radius * 0.95)
            g_bloom = _m6_fire_grad((int(116 * k), int(46 * k), int(10 * k)), fz.radius * 1.45)
            lm.blit(g_spill, (fx_c - g_spill.get_width() // 2, fy_c - g_spill.get_height() // 2), special_flags=add)
            lm.blit(g_core, (fx_c - g_core.get_width() // 2, fy_c - g_core.get_height() // 2), special_flags=add)
            ov.blit(g_bloom, (fx_c - g_bloom.get_width() // 2, fy_c - g_bloom.get_height() // 2), special_flags=add)
    lit = _scratch("lit", (bw, bh), buf)
    tmp = _scratch("lit2", (bw, bh), buf)
    lit.blit(crop, (0, 0))
    lit.blit(lm, (0, 0), special_flags=pygame.BLEND_RGB_MULT)
    tmp.blit(lit, (0, 0))
    lit.blit(tmp, (0, 0), special_flags=add)
    if stage in (STAGE_CUSTOMS, STAGE_NOMAN, STAGE_RAIL) and _nfx._quality() > 0:
        for patch, wx, wy in _nfx.wet_puddle_patches(stage, _grid(stage)):
            px_, py_ = wx - bx0, wy - by0
            if px_ + patch.get_width() > 0 and px_ < bw and py_ + patch.get_height() > 0 and py_ < bh:
                lit.blit(patch, (px_, py_), special_flags=add)
    if ov is not None:
        lit.blit(ov, (0, 0), special_flags=add)
    # packed pixels and 1-D gathers throughout: (N, 3) channel views cost
    # several times more to gather and scatter
    p2 = _fv(buf)
    src = p2[nf]                      # the 3D pass's pixels, before the floor goes over them
    flat = _flat(lit)
    np.take(flat, lin0, out=p2, mode="clip")   # the whole frame as lit floor
    del flat
    if not nf.size:
        return
    lmf = _flat(lm)
    ovf = _flat(ov) if ov is not None else None
    rgb = 0
    for m in buf.get_masks()[:3]:
        rgb |= m
    spare = np.uint32(~rgb & 0xFFFFFFFF)
    shifts = buf.get_shifts()[:3]
    for i in range(0, nf.size, _CHUNK):
        j = slice(i, i + _CHUNK)
        li = lin[j]
        p2[nf[j]] = _light_part(src[j], lmf[li], None if ovf is None else ovf[li],
                                np.flatnonzero(lift[j]), spare, shifts)


def _light_part(src, mul, add, up, spare, shifts):
    """One ``_CHUNK`` of ``_light``: packed source times its light map value."""
    out = src & spare   # the spare byte stays as it was
    for sh in shifts:
        k = (mul >> sh) & 255
        if up.size:
            # the 3D cast is darker than the 2D sprites before the light pass
            k[up] = np.minimum(k[up] * CAST_LIFT, 255).astype(np.uint32)
        c = (((src >> sh) & 255) * k) >> 7
        if add is not None:
            c += (add >> sh) & 255
        np.minimum(c, 255, out=c)
        out |= c << sh
    return out
    del p2


def _additive(stage, bx0, by0, bw, bh, like):
    """Floodlight beams, blasts and pickup marks: added after the multiply,
    exactly where the 2D painter adds them."""
    from . import draw as _draw
    beams = _stealth.lights()
    blasts = bool(getattr(_combat, "_blasts", None))
    pickups = getattr(STATE, "pickups", [])
    if not (beams or blasts or pickups):
        return None
    ov = _scratch("add", (bw, bh), like)
    ov.fill((0, 0, 0))
    alarmed = _stealth.alarm_active()
    for light in beams:
        _stealth._draw_beam(ov, light, bx0, by0, alarmed)

    def emit(s, cx, cy):
        for pu in pickups:
            _draw._draw_pickup_mark(s, pu, cx, cy)
        _combat.draw_blasts(s, cx, cy)
    if blasts or pickups:
        _tiles(ov, bx0, by0, emit)
    return ov


# ── walls ──────────────────────────────────────────────────────────────

def _wall_kind(grid, c, r):
    ch = grid[r][c]
    if ch == "C":
        return "C"
    if ch == "W":
        return "band" if _decor._band_tile(grid, c, r) else "W"
    return None


def _wall_boxes(stage):
    """Merged wall boxes (col, row, w, h, kind) in tiles."""
    hit = _cache["walls"].get(stage)
    if hit is not None:
        return hit
    grid = _grid(stage)
    mh, mw = len(grid), len(grid[0])
    runs = {}
    for row in range(mh):
        col = 0
        while col < mw:
            kind = _wall_kind(grid, col, row)
            if kind is None:
                col += 1
                continue
            end = col
            while end + 1 < mw and _wall_kind(grid, end + 1, row) == kind:
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
    _cache["walls"][stage] = out
    return out


def _cut(zone, snap, key, x0, y0, x1, y1):
    k = _m1._cut_level(key, _m1._hides(zone, x0, y0, x1, y1), snap)
    return round(k * 8) / 8.0


def _keyed_box(w, d, hgt, side, keys, cols=None):
    """A lit box whose ``keys`` faces ({side: key colour}) are emissive."""
    from engine3d import Mesh, box
    every = ("top", "bottom", "left", "right", "front", "back")
    c = (0.0, hgt / 2.0, 0.0)
    m = Mesh()
    m.add(box(w, hgt, d, side, center=c, cols=cols, skip=("bottom",) + tuple(keys)))
    for face, col in keys.items():
        m.add(box(w, hgt, d, col, center=c, emissive=True,
                  skip=tuple(f for f in every if f != face)))
    return m


def _draw_walls(r, stage, gl_dims=None):
    """Wall boxes at full height, except the stretch between the camera
    and Biribel, which sinks to a stub (the M1 cutaway)."""
    from engine3d import tex
    zone = _m1._cut_zone()
    snap = _m1._cut_snap()
    for c0, r0, w, h, kind in _wall_boxes(stage):
        along_x = w >= h
        n = w if along_x else h

        def lv(c, rw):
            return _cut(zone, snap, ("m6", c, rw), c * T, rw * T, (c + 1) * T, (rw + 1) * T)
        levels = [min(lv(c0 + i, r0 + j) for j in range(h)) if along_x else
                  min(lv(c0 + j, r0 + i) for j in range(w)) for i in range(n)]
        full = WALL_H[kind]
        i = 0
        while i < n:
            j = i
            while j + 1 < n and levels[j + 1] == levels[i]:
                j += 1
            if along_x:
                sc, sr, sw, sh = c0 + i, r0, j - i + 1, h
            else:
                sc, sr, sw, sh = c0, r0 + i, w, j - i + 1
            hgt = _hidx(STUB_H + (full - STUB_H) * levels[i]) / 20.0
            row = sr + sh - 1
            cx, _, cz = to3((sc + sw / 2.0) * T, (sr + sh / 2.0) * T)
            if gl_dims is not None:
                gw, gh = gl_dims
                sx0, sx1 = sc * T, (sc + sw) * T
                sy0, sy1 = sr * T, (sr + sh) * T
                fv_top = max(0.0, 1.0 - hgt / max(0.05, full))
                top_uv = (sx0 / gw, sy0 / gh, sx1 / gw, sy1 / gh)
                front_uv = (sx0 / gw, (row + fv_top) * T / gh, sx1 / gw, (row + 1) * T / gh)
                key = ("w_gl", kind, sc, sr, sw, sh, hgt, row)
                mesh = _mesh(key, lambda sw=sw, sh=sh, hgt=hgt, tuv=top_uv, fuv=front_uv: _uv_box(
                    sw * T * K, sh * T * K, hgt, tex("concrete", like=WALL_SIDE[kind], tint=True),
                    top_uvs=tuv, top_slot=-2.0, front_uvs=fuv, front_slot=-3.0))
            else:
                key = ("w", kind, sw, sh, hgt, row)
                mesh = _mesh(key, lambda sw=sw, sh=sh, hgt=hgt, row=row: _keyed_box(
                    sw * T * K, sh * T * K, hgt, tex("concrete", like=WALL_SIDE[kind], tint=True),
                    {"top": (K_TOP, 1, _hidx(hgt)), "front": (K_FACE, 2 + _hidx(full), row)}))
            _put(r, mesh, (cx, 0.0, cz))
            i = j + 1


# ── props ──────────────────────────────────────────────────────────────

_SEDAN_MESH = {"init": False, "mesh": None}


def _sedan_mesh():
    if not _SEDAN_MESH["init"]:
        _SEDAN_MESH["init"] = True
        try:
            from game.scenery3d import prop
            _SEDAN_MESH["mesh"] = prop("car_m2")
        except Exception:
            import traceback
            traceback.print_exc()
            _SEDAN_MESH["mesh"] = None
    return _SEDAN_MESH["mesh"]


def _draw_props(r, stage, tm, gl_uvs=None):
    from engine3d import tex
    zone = _m1._cut_zone()
    snap = _m1._cut_snap()
    for i, p in enumerate(_props(stage)):
        mode = p["mode"]
        if "tank" in p:
            continue
        if p["kind"] == "sedan" and _sedan_mesh() is not None:
            continue
        if mode not in ("face", "top"):
            if mode == "tower":
                _tower(r, p, stage)
            continue
        full = p["h"]
        hgt = full
        if full > CUT_MIN:
            lvl = _cut(zone, snap, ("m6p", stage, i), p["x0"], p["y0"], p["x1"], p["y1"])
            hgt = STUB_H + (full - STUB_H) * lvl
        hgt = _hidx(hgt) / 20.0
        w, d = (p["x1"] - p["x0"]) * K, (p["y1"] - p["y0"]) * K
        cx, _, cz = to3((p["x0"] + p["x1"]) / 2.0, (p["y0"] + p["y1"]) / 2.0)
        if mode == "face":
            if gl_uvs is not None and i in gl_uvs:
                u0, v0, u1, v1 = gl_uvs[i]
                cp, sp = math.cos(math.radians(CAM.pitch)), math.sin(math.radians(CAM.pitch))
                dp, hp = (p["y1"] - p["y0"]) * K * sp, p["h"] * cp
                split = FACE_SPLIT.get(p["kind"], dp / (dp + hp))
                vmid = v0 + (v1 - v0) * split
                vtop = v0 + (v1 - v0) * (split + max(0.0, 1.0 - hgt / max(0.05, p["h"])) * (1.0 - split))
                mesh = _mesh(("pf_gl", stage, i, hgt), lambda w=w, d=d, hgt=hgt, p=p,
                             tuv=(u0, v0, u1, vmid), fuv=(u0, vtop, u1, v1): _uv_box(
                    w, d, hgt, tex("steel", like=p["side"], tint=True),
                    top_uvs=tuv, top_slot=-4.0, front_uvs=fuv, front_slot=-4.0))
            else:
                # sprite on the south face; the roof is a lit cap in its top-row colour
                # the 2D sprite unwraps over roof and south face, as the 2D view shows it
                mesh = _mesh(("pf", stage, i, hgt), lambda w=w, d=d, hgt=hgt, p=p, i=i: _keyed_box(
                    w, d, hgt, tex("steel", like=p["side"], tint=True),
                    {"top": (K_PTOP, 2 + _hidx(hgt), i), "front": (K_PFACE, 2 + _hidx(p["h"]), i)}))
        else:
            if gl_uvs is not None and i in gl_uvs:
                mesh = _mesh(("pt_gl", stage, i, hgt), lambda w=w, d=d, hgt=hgt, p=p, tuv=gl_uvs[i]: _uv_box(
                    w, d, hgt, tex("crate", like=p["side"], tint=True),
                    top_uvs=tuv, top_slot=-4.0))
            else:
                mesh = _mesh(("pt", stage, i, hgt), lambda w=w, d=d, hgt=hgt, p=p, i=i: _keyed_box(
                    w, d, hgt, tex("crate", like=p["side"], tint=True),
                    {"top": (K_PTOP, 2 + _hidx(hgt), i)}, cols={"front": _shade(p["side"], 0.9)}))
        _put(r, mesh, (cx, 0.0, cz))


def _build_static(r, stage):
    """Thin props that never sink: booms, hedgehogs, masts, the water tower
    and the signal shack."""
    from cutscenes import m6world3d as _w
    from engine3d import box, tex
    for p in _props(stage):
        kind = p["kind"]
        cx, _, cz = to3((p["x0"] + p["x1"]) / 2.0, (p["y0"] + p["y1"]) / 2.0)
        if kind == "boom":
            px_, _, pz = to3(p["x0"] + 12, p["y0"] + 40)
            _w.add(r, box(0.30, 1.15, 0.30, (76, 82, 90), center=(px_, 0.575, pz)))
            _w.add(r, box(0.42, 0.36, 0.36, (48, 52, 58), center=(px_, 0.95, pz)))
            _w.add(r, box(0.28, 0.24, 0.26, (214, 156, 48), center=(px_ - 0.22, 0.98, pz)))
            for k in range(8):
                col = (188, 62, 48) if k % 2 else (208, 206, 196)
                _w.add(r, box(0.28, 0.10, 0.10, col, center=(px_ + 0.22 + k * 0.28, 1.02, pz)))
            for lx in (0.92, 1.76, 2.34):
                _w.add(r, box(0.09, 0.09, 0.09, (245, 58, 46), center=(px_ + lx, 1.03, pz), emissive=True))
        elif kind == "hedgehog":
            from engine3d import Mesh, rot_y, rot_z
            m = Mesh()
            beam = box(1.35, 0.12, 0.12, (96, 62, 44), center=(0.0, 0.0, 0.0))
            for yaw, roll in ((0.0, 45.0), (0.0, -45.0), (90.0, 45.0)):
                m.add(beam, m=_mul(rot_y(yaw), rot_z(roll)), t=(cx, 0.48, cz))
            _w.add(r, m)
        elif kind == "mast":
            _w.add(r, box(0.18, 4.6, 0.18, (64, 68, 74), center=(cx, 2.3, cz)))
            _w.add(r, box(0.5, 0.16, 0.3, (74, 78, 86), center=(cx, 4.6, cz)))
        elif kind == "water_tower":
            for dx in (-0.9, 0.9):
                for dz in (-0.9, 0.9):
                    _w.add(r, box(0.14, 3.2, 0.14, (64, 66, 70), center=(cx + dx, 1.6, cz + dz)))
            _w.add(r, box(2.5, 1.8, 2.5, tex("rust", like=(84, 82, 74), tint=True),
                          center=(cx, 4.1, cz), cols={"top": (176, 178, 182)}))
            _w.add(r, box(2.7, 0.14, 2.7, (66, 64, 58), center=(cx, 5.07, cz),
                          cols={"top": (176, 178, 182)}))
        elif kind == "shack":
            # the hut is a face-mode prop; this is the signal mast on its roof
            mx, _, mz = to3(41.5 * T, 7.0 * T + 44)
            _w.add(r, box(0.16, 2.2, 0.16, (64, 66, 70), center=(mx, 3.7, mz)))
        elif kind == "sedan":
            m_sedan = _sedan_mesh()
            if m_sedan is not None:
                from engine3d import Mesh
                scaled = Mesh(
                    [(v[0] * 0.76 + cx, v[1] * 0.76, v[2] * 0.76 + cz)
                     for v in m_sedan.verts],
                    m_sedan.faces)
                _w.add(r, scaled)
    if stage == STAGE_CUSTOMS:
        # Non-blocking reflective orange traffic cones along the lane & gate
        for tx_, ty_ in ((12.2, 3.6), (18.6, 3.6), (13.1, 6.2),
                         (17.9, 10.6), (12.6, 12.2), (17.6, 14.5)):
            kx, _, kz = to3(tx_ * T, ty_ * T)
            _w.add(r, box(0.38, 0.06, 0.38, (26, 28, 32), center=(kx, 0.03, kz)))
            _w.add(r, box(0.28, 0.24, 0.28, (238, 102, 26), center=(kx, 0.18, kz)))
            _w.add(r, box(0.22, 0.14, 0.22, (238, 242, 246), center=(kx, 0.37, kz), emissive=True))
            _w.add(r, box(0.14, 0.20, 0.14, (238, 102, 26), center=(kx, 0.54, kz)))
        # Checkpoint STOP / CUSTOMS signposts flanking the north gate apron
        for sx_, sy_, sign_col in ((12.0, 1.85, (192, 46, 42)), (19.0, 1.85, (38, 72, 122))):
            gx, _, gz = to3(sx_ * T, sy_ * T)
            _w.add(r, box(0.10, 1.9, 0.10, (88, 94, 104), center=(gx, 0.95, gz)))
            _w.add(r, box(0.68, 0.44, 0.08, (226, 230, 236), center=(gx, 1.95, gz)))
            _w.add(r, box(0.58, 0.34, 0.10, sign_col, center=(gx, 1.95, gz - 0.01)))


def _mul(a, b):
    from engine3d import m_mul
    return m_mul(a, b)


def _tower(r, p, stage):
    """Noman floodlight tower: lattice mast and a twin head, dark once shot."""
    from engine3d import box
    lights = _stealth.all_lights()
    try:
        idx = [tuple(t) for t in NOMAN_TOWER_TILES].index((p["c"], p["r"]))
    except ValueError:
        idx = -1
    dead = 0 <= idx < len(lights) and _stealth.dead(lights[idx])
    key = ("tower", dead)

    def build():
        from engine3d import Mesh
        m = Mesh()
        m.add(box(0.3, 6.6, 0.3, (72, 76, 82), center=(0.0, 3.3, 0.0)))
        for k in range(1, 7):
            m.add(box(0.5, 0.06, 0.06, (88, 92, 98), center=(0.0, k * 0.95, 0.0)))
        m.add(box(1.8, 0.12, 0.16, (64, 68, 74), center=(0.0, 6.6, 0.0)))
        lamp = (46, 48, 52) if dead else (246, 236, 196)
        for dx in (-0.7, 0.7):
            m.add(box(0.42, 0.3, 0.3, (40, 42, 46), center=(dx, 6.8, 0.0)))
            m.add(box(0.34, 0.22, 0.04, lamp, center=(dx, 6.8, -0.16), emissive=not dead))
        return m
    cx, _, cz = to3((p["x0"] + p["x1"]) / 2.0, (p["y0"] + p["y1"]) / 2.0)
    _put(r, _mesh(key, build), (cx, 0.0, cz))


# ── combat set: drums, the tanker, debris ──────────────────────────────

def _draw_combat(r, gl_uvs=None):
    from engine3d import Mesh, box, tex
    for dr in getattr(_combat, "_drums", ()):
        alive = dr["alive"]

        def build(alive=alive):
            m = Mesh()
            if alive:
                m.add(box(0.62, 0.86, 0.62, tex("rust", like=(168, 52, 40), tint=True),
                          center=(0.0, 0.43, 0.0), cols={"top": (90, 34, 28)}))
                m.add(box(0.64, 0.12, 0.64, (230, 196, 64), center=(0.0, 0.43, 0.0),
                          skip=("top", "bottom")))
            else:
                m.add(box(0.64, 0.5, 0.64, (96, 40, 32), center=(0.0, 0.25, 0.0),
                          cols={"top": (14, 12, 12)}))
            return m
        _put(r, _mesh(("drum", alive), build), to3(dr["x"], dr["y"]))
    tk = getattr(_combat, "_tanker", None)
    if tk:
        from engine3d import tex as _tex
        stage = _stage()
        for i, p in enumerate(_props(stage)):
            if p.get("tank") is not bool(tk["alive"]):
                continue
            hgt = _hidx(p["h"]) / 20.0
            w, d = (p["x1"] - p["x0"]) * K, (p["y1"] - p["y0"]) * K
            if gl_uvs is not None and i in gl_uvs:
                mesh = _mesh(("tank_gl", stage, i), lambda w=w, d=d, hgt=hgt, p=p, tuv=gl_uvs[i]: _uv_box(
                    w, d, hgt, _tex("steel", like=p["side"], tint=True),
                    top_uvs=tuv, top_slot=-4.0))
            else:
                mesh = _mesh(("tank", stage, i), lambda w=w, d=d, hgt=hgt, p=p, i=i: _keyed_box(
                    w, d, hgt, _tex("steel", like=p["side"], tint=True),
                    {"top": (K_PTOP, 2 + _hidx(hgt), i)}, cols={"front": _shade(p["side"], 0.9)}))
            _put(r, mesh, to3((p["x0"] + p["x1"]) / 2.0, (p["y0"] + p["y1"]) / 2.0))
    for c in getattr(_combat, "_debris", ()):
        cw, ch = int(c["w"]), int(c["h"])
        col = tuple(c["col"])[:3]
        mesh = _mesh(("chunk", cw, ch, col), lambda cw=cw, ch=ch, col=col: box(
            cw * K, 0.1, ch * K, col, center=(0.0, 0.05, 0.0)))
        x, y, z = to3(c["x"], c["y"])
        _put(r, mesh, (x, c.get("z", 0) * K, z), yaw=math.degrees(c.get("rot", 0.0)))


# ── cast ───────────────────────────────────────────────────────────────

def _in_view(x, y, v, bb):
    """Conservative world-space bounds for bodies and their ground shadows.

    The ray crop spans the floor and 3.4 m plane; another two tiles cover
    weapons, the fall pose and the cast shadow before mesh construction.
    """
    return (v.tgt[0] / K + bb[0] - 128 <= x <= v.tgt[0] / K + bb[2] + 128
            and -v.tgt[2] / K + bb[1] - 128 <= y <= -v.tgt[2] / K + bb[3] + 128)


def _draw_corpses(r, v, bb):
    """The M5 corpse pose, but skip bodies outside M6's camera before skinning."""
    from engine3d import SoftwareRenderer, blend
    from missions.m5 import draw3d as _m5
    hum = td.armed("ipa", "os12", **_m5._GUARD_KIT)
    software = type(r) is SoftwareRenderer
    for c in list(getattr(STATE, "corpses", ())):
        if not _in_view(c.x, c.y, v, bb):
            continue
        k = min(1.0, c.t / float(_m1.CORPSE_FALL))
        pose = blend("kneel", "dead_side", k) if k > 0.35 else blend("stand", "kneel", k / 0.35)
        at = to3(c.x, c.y)
        if k >= 1.0:
            r.add_sprite((at[0], 0.02, at[2]), td.blood_pool(min(1.0, (c.t - _m1.CORPSE_FALL) / 90.0)), layer=0)
        r.add_sprite((at[0], 0.02, at[2]), td.shadow(0.75, 0.55, 110), layer=1, bias=-0.8)
        yaw = td.yaw_rad(c.angle) + 90.0 * c.fall_dir
        tint = _m1.CHAR if hasattr(c, "burn") else None
        if software and k >= 1.0:
            # A settled corpse has an immutable pose. Software skinning rebuilds
            # hundreds of vertices each frame; cache those world vertices, but
            # still submit them with the current light and both live shadows.
            cache = _cache["corpse_meshes"]
            baked = cache.get(c)
            if baked is None or baked[:2] != (at, yaw):
                verts, faces, _ = hum.build(pose, at, yaw, rifle_on=False)
                baked = cache[c] = (at, yaw, verts, faces)
            r.actor_log.append(tuple(at))
            r.add_dynamic(baked[2], baked[3], tint=tint)
            r.add_blob_shadow((at[0], at[1] + 0.02, at[2]), 0.34, 0.30, 0.40, layer=1, bias=-0.5)
        else:
            r.add_humanoid(hum, pose, at, yaw, rifle_on=False, tint=tint, shadow=(1, -0.5))


def _draw_cast(r, flashes, tm, v):
    from missions.m5 import draw3d as _m5
    bb = _rays(v)["bb"]
    _draw_corpses(r, v, bb)
    for e in getattr(STATE, "enemies", []):
        if getattr(e, "hp", 1) <= 0:
            continue
        if not _in_view(e.rect.centerx, e.rect.centery, v, bb):
            # Keep walk phase continuous when a Guard enters the camera.
            _m1._motion(("e6", e.uid), e.rect.centerx, e.rect.centery, e.angle)
            continue
        hum, rig = _m5._guard_hum(e)
        mode = "aim" if e.state in ("CHASE", "ATTACK") else "ready"
        burn = getattr(e, "burn", 0)
        tint = _m1.CHAR if burn else (e.body_tint, 0.55) if getattr(e, "body_tint", None) else None
        x, y = e.rect.centerx, e.rect.centery
        r.add_sprite(to3(x, y, 0.02), td.shadow(0.46, 0.38, 100), layer=1, bias=-0.5)
        r.add_sprite(to3(x, y, 0.015), td.shadow(0.28, 0.22, 172), layer=1, bias=-0.3)
        _m1._body(r, hum, x, y, e.angle, rig, mode, ("e6", e.uid), tint=tint)
        _m1._burning(r, x, y, min(1.0, burn / 40.0), tm, e.uid * 5, flashes)
    vk = _world.volkov()
    if vk and not vk.get("dead") and _in_view(vk["x"], vk["y"], v, bb):
        r.add_sprite(to3(vk["x"], vk["y"], 0.02), td.shadow(0.46, 0.38, 100), layer=1, bias=-0.5)
        r.add_sprite(to3(vk["x"], vk["y"], 0.015), td.shadow(0.28, 0.22, 172), layer=1, bias=-0.3)
        _m5._unarmed(r, td.armed("volkov", "pistol"), vk["x"], vk["y"],
                     vk.get("angle", -math.pi / 2), "volkov")
    _draw_player(r, flashes)
    if getattr(STATE, "muzzle_flash_timer", 0) > 0:
        STATE.muzzle_flash_timer -= 1


def _draw_player(r, flashes):
    from missions.m5 import draw3d as _m5
    p = STATE.player
    if p is None:
        return
    outfit = _outfits.gameplay_outfit(STATE) or _outfits.OUTFIT_KRAP
    hum = td.armed("biribel", p.rig_weapon_name(), **_outfits.biribel_3d(outfit))
    if STATE.player_dead:
        _m1._draw_dead_player(r, hum)
        return
    x, y = p.rect.centerx, p.rect.centery
    # Crisp two-layer contact shadow so Biribel's boots sit grounded on the floor
    r.add_sprite(to3(x, y, 0.02), td.shadow(0.46, 0.38, 100), layer=1, bias=-0.5)
    r.add_sprite(to3(x, y, 0.015), td.shadow(0.28, 0.22, 174), layer=1, bias=-0.3)
    # Subtle cool rim light + forward tactical spot flashlight on GL rigs
    if hasattr(r, "add_packed"):
        px3, _, pz3 = to3(x, y)
        dx, dy = math.cos(p.angle), math.sin(p.angle)
        flashes.insert(0, {
            "pos": (px3 + dx * 0.35, 1.35, pz3 - dy * 0.35),
            "color": (218, 236, 255), "intensity": 1.15, "range": 7.5,
            "kind": "spot", "dir": (dx, -0.22, -dy), "cone": 0.86, "shadow": True,
        })
        flashes.insert(0, {
            "pos": (px3 - 0.50, 1.95, pz3 + 0.50),
            "color": (162, 212, 255), "intensity": 0.92, "range": 2.4,
        })
    rig = p.rig_weapon_name()
    if getattr(STATE, "player_disarmed", False):
        _m5._unarmed(r, hum, x, y, p.angle, "player")
        return
    melee = _m1._melee_progress()
    mode = "ready" if getattr(STATE, "is_reloading", False) else "aim"
    _m1._body(r, hum, x, y, p.angle, rig, mode, "player", flashes,
              STATE.muzzle_flash_timer > 0 and melee is None, melee=melee)


def _draw_fires(r, flashes, tm, v):
    fx0, fz0 = v.tgt[0], v.tgt[2]
    for fz in getattr(STATE, "fire_zones", []):
        x, _, z = to3(fz.x, fz.y)
        if abs(x - fx0) > 22.0 or abs(z - fz0) > 18.0:
            continue
        heat = min(1.0, fz.life / float(max(1, fz.max_life)) * 4.0)
        rad = fz.radius * K
        _m1._fuel_pool_at(r, x, z, rad * (0.65 + 0.35 * heat), fz.x * 0.37 + fz.y * 0.11, tm=tm, heat=heat)
        n = 1 + min(6, int(rad / 0.3))
        for i in range(n):
            a = i * 2.39996 + fz.x * 0.013
            d = 0.0 if i == 0 else rad * 0.72 * math.sqrt(i / float(n))
            size = (0.56 if i == 0 else 0.36) * min(1.25, 0.45 + rad * 0.35) * heat
            _m1._fire(r, (x + math.cos(a) * d, 0.0, z + math.sin(a) * d), tm, int(fz.x) + i, size,
                      glow=(i == 0), smoky=(i == 0), bed=False, embers=(i == 0), heat=heat)
        flashes.append({"pos": (x, 1.0, z), "color": FIRE, "intensity": heat, "range": 4.0 + rad})


# ── buffer-space fx, before the light pass (2D order) ──────────────────

def _bpt(v, x, y, h):
    p = v.screen_sim(x, y, h)
    if p is None:
        return None
    return p[0] * v.w / float(WIDTH), p[1] * v.h / float(HEIGHT)


def _draw_smoke(buf, v):
    s0 = v.focal * K / CAM.dist
    t = getattr(_combat, "_t", 0.0)
    for p in getattr(_combat, "_smoke", ()):
        age = (t - p["t0"]) / p["life"]
        pt = _bpt(v, p["x"], p["y"], 1.0 + 0.8 * age)
        if pt is None:
            continue
        rad = int(p["r"] * (1.0 + 0.9 * age) * s0) // 4 * 4
        if rad < 4:
            continue
        step = 0 if age < 0.4 else (1 if age < 0.75 else 2)
        buf.blit(_combat._smoke_surface(rad, p["shade"], step), (int(pt[0]) - rad, int(pt[1]) - rad))


def _draw_bullets(buf, v):
    for b in getattr(STATE, "bullets", []):
        head = _bpt(v, b["x"], b["y"], AIM_H)
        tail = _bpt(v, b.get("prev_x", b["x"] - b["dx"]), b.get("prev_y", b["y"] - b["dy"]), AIM_H)
        if head is None or tail is None:
            continue
        pygame.draw.line(buf, (255, 220, 140), tail, head, 2)
        pygame.draw.circle(buf, (255, 246, 210), (int(head[0]), int(head[1])), 1)


# ── canvas-space emissives, after the light pass ───────────────────────

def _heights(stage):
    """Tile heights (m) of walls and keyed props, for the occlusion test."""
    hit = _cache["heights"].get(stage)
    if hit is not None:
        return hit
    grid = _grid(stage)
    hm = {}
    for c0, r0, w, h, kind in _wall_boxes(stage):
        for c in range(c0, c0 + w):
            for rw in range(r0, r0 + h):
                hm[(c, rw)] = (WALL_H[kind], ("m6", c, rw))
    for i, p in enumerate(_props(stage)):
        if p.get("h", 0.0) <= 0.0:
            continue
        for c in range(int(p["x0"] // T), int((p["x1"] - 1) // T) + 1):
            for rw in range(int(p["y0"] // T), int((p["y1"] - 1) // T) + 1):
                hm.setdefault((c, rw), (p["h"], ("m6p", stage, i) if p["h"] > CUT_MIN else None))
    _cache["heights"][stage] = (len(grid), hm)
    return _cache["heights"][stage]


def _occluded(v, stage, x, y, h):
    """Does a wall or prop stand between the camera and sim point (x, y, h)?"""
    _, hm = _heights(stage)
    p = to3(x, y, h)
    e = v.eye
    cut = _m1._cache["cut"]
    start = (int(x // T), int(y // T))
    for i in range(1, 40):
        s = i / 40.0
        q = (p[0] + (e[0] - p[0]) * s, p[1] + (e[1] - p[1]) * s, p[2] + (e[2] - p[2]) * s)
        if q[1] > 3.2:
            return False
        tile = (int(q[0] / K // T), int(-q[2] / K // T))
        if tile == start:
            continue
        hit = hm.get(tile)
        if hit is None:
            continue
        full, key = hit
        k = cut.get(key, 1.0) if key is not None else 1.0
        if q[1] < STUB_H + (full - STUB_H) * k:
            return True
    return False


def _at(v, x, y, h):
    p = v.screen_sim(x, y, h)
    return None if p is None else (int(p[0]), int(p[1]))


def _on(pt, m=40):
    return pt is not None and -m < pt[0] < WIDTH + m and -m < pt[1] < HEIGHT + m


def _emissives(surface, v, stage):
    from . import draw as _draw
    t = _now_s()
    add = pygame.BLEND_RGB_ADD
    # lamp housings and their hard halos (the light pass's blooms)
    for i, (tx, ty, radius, colour, kind) in enumerate(_decor._STAGE_LAMPS.get(stage, ())):
        tower = kind.startswith("tower")
        if tower:
            if _decor._light_dead(int(kind[5:])):
                continue
            kind = "steady"
        k = _decor._lamp_on(kind, i)
        wx, wy = tx * T, ty * T
        hh = 6.8 if tower else 2.5
        pt = _at(v, wx, wy, hh)
        if not _on(pt, 80) or _occluded(v, stage, wx, wy, hh):
            continue
        if k > 0.2:
            gr = max(20, radius // 4)
            g = _decor._hard_bloom(gr, colour)
            surface.blit(g, (pt[0] - gr, pt[1] - gr), special_flags=add)
        if not tower and not _decor._under_prop(stage, wx, wy):
            surface.blit(_decor._lamp_head(colour, k > 0.5), (pt[0] - 9, pt[1] - 9))
    if stage == STAGE_CUSTOMS:
        # Subtle bloomed glow on customs booth windows & red barrier-arm LEDs
        for wx, wy, hh, rad, col in (
            (12.5 * T, 7.6 * T, 1.35, 22, (116, 242, 214)),
            (18.5 * T, 10.6 * T, 1.35, 22, (116, 242, 214)),
        ):
            pt = _at(v, wx, wy, hh)
            if _on(pt, 40) and not _occluded(v, stage, wx, wy, hh):
                g = _nfx.bulb_glow_sprite(rad, col)
                surface.blit(g, (pt[0] - rad, pt[1] - rad), special_flags=add)
        for bx_tile in (12, 18):
            for lx in (0.92, 1.76, 2.34):
                wx = bx_tile * T + 12 + lx / K
                wy = 2 * T + 40
                pt = _at(v, wx, wy, 1.03)
                if _on(pt, 20) and not _occluded(v, stage, wx, wy, 1.03):
                    g = _nfx.bulb_glow_sprite(11, (248, 62, 50))
                    surface.blit(g, (pt[0] - 11, pt[1] - 11), special_flags=add)
    if stage in (STAGE_RAIL, STAGE_BOXCAR, STAGE_TRAIN):
        pt = _at(v, 41.5 * T, 7.0 * T + 44, 4.8)
        if (int(t * 2) % 2) == 0 and not _decor._light_dead(0) and _on(pt):
            pygame.draw.circle(surface, (230, 70, 60), pt, 6)
            pygame.draw.circle(surface, (255, 170, 140), pt, 2)
    # exit lamps sit on the face tile's plate: lift them onto the 3D face
    if not getattr(STATE, "m6_train_active", False):
        opened = _combat.cleared()
        col = (110, 232, 150) if opened else (232, 70, 58)
        if not opened and int(_now_ms() / 420) % 2:
            col = (96, 32, 28)
        for wx, wy in _decor.exit_lamps(stage) or ():
            row = int(wy // T)
            hh = (1.0 - (wy - row * T) / float(T)) * WALL_H["C"]
            pt = _at(v, wx, (row + 1) * T, hh)
            if _on(pt, 10):
                pygame.draw.circle(surface, (10, 12, 16), pt, 5)
                pygame.draw.circle(surface, col, pt, 4)
                pygame.draw.circle(surface, (255, 244, 230) if opened else (255, 150, 130),
                                   (pt[0] - 1, pt[1] - 1), 1)
    # IFF lamps on the Guards' backs
    for e in getattr(STATE, "enemies", []):
        if e.hp <= 0 or _world.entering(e) > 0.0:
            continue
        x = e.rect.centerx - math.cos(e.angle) * 7
        y = e.rect.centery - math.sin(e.angle) * 7
        pt = _at(v, x, y, 1.45)
        if not _on(pt, 10) or _occluded(v, stage, x, y, 1.45):
            continue
        bright = int(_now_ms() / 600 + getattr(e, "uid", 0)) % 2 == 0
        pygame.draw.circle(surface, (10, 12, 16), pt, 3)
        pygame.draw.circle(surface, (232, 62, 52), pt, 2)
        if bright:
            pygame.draw.circle(surface, (255, 178, 150), pt, 1)
        if getattr(e, "alerted", False):
            hp = _at(v, e.rect.centerx, e.rect.centery, 2.15)
            if hp is not None:
                a = 0.55 + 0.45 * math.sin(t * 7.0)
                pygame.draw.circle(surface, (236, 176, 84), hp, max(1, int(round(1.2 + a))))
    vk = _world.volkov()
    if vk and not vk.get("dead"):
        pt = _at(v, vk["x"], vk["y"], 2.2)
        if _on(pt):
            tag = font_terminal_small.render("VOLKOV", True, (214, 188, 146))
            surface.blit(tag, (pt[0] - tag.get_width() // 2, pt[1] - tag.get_height()))
    del _draw