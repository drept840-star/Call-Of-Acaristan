"""Mission 5 - part module. See __init__.py for the package facade.

Render pipeline for Mission 5 (game_draw). Z-order ported from
missions.m4.draw: tiles -> blood -> corpses -> pickups -> Guard troopers
-> Maru -> player -> muzzle -> bullets -> FX -> floating texts ->
vignette -> rain -> scanlines -> death overlay -> HUD -> dialogue ->
reticle. Reuses the M4 tile grammar through core.artpack (C/B walls,
./d/O/L/F floors); M5-only tiles (H press, S stair, W water) and the
markers are procedural. Ported, NOT imported from m4 (mission-scoped).
"""

import math

import pygame

from core.config import (C_BG_GAME, C_BULLET, C_ENEMY_SKIN, C_KRAP_BLUE, C_TERMINAL, C_WHITE, HEIGHT, MUZZLE_FLASH, TILE_SIZE, WIDTH, bullet_glow as _bullet_glow, draw_scanlines, draw_vignette, font_dialogue, font_speaker, font_terminal_small, screen)
from core.state import STATE
from entities import corpse
from entities.enemy_ai import _enemy_shadow
from entities.art_cache import get_blood_decal, get_fullscreen_overlay, get_panel_bg, get_plate_bg
from core import artpack, render_util
from core import config as _config
from core import outfits as _outfits
from core.camera import draw_bullets
from ui.hud import THEME, draw_combat_reticle, draw_objective_panel, draw_pinned_radio
from engine.text import T as _T  # T is TILE_SIZE in this module - do not shadow
from engine.ui import health_bar as _hud_health_bar, hostiles as _hud_hostiles, weapon_panel as _hud_weapon_panel

from missions.m5 import maps as _m5_maps  # live MISSION5_MAP/_objective/_last_keys
from missions.m5.meta import (
    M5_RAID_SECONDS, M5_MARU_MAX_HP,
    STAGE_HQ, STAGE_QUARTER, STAGE_PRINTWORKS, STAGE_RAID, STAGE_TUNNEL,
    STAGE_DONE, C_MARU, C_GUARD, C_VASILE,
)
from missions.m5.world import (
    _movement_locked, _solid_walls, friendly_npcs,
    _printworks_door_pos, _maru_office_pos, _stair_pos, _river_gate_pos,
    _vasile_desk_pos,
)
from missions.m5 import flow as _m5_flow  # live view of _m5_dlg
from missions.m5 import decor as _m5_decor
from missions.m5 import inspect_fpv as _m5_fpv
from missions.m5 import quarter as _m5_quarter
from missions.m5 import water as _m5_water
from missions.m5 import render as _m5_render  # RENDER_SUBMIT systems (GuardRenderSystem)
from engine.core import now_ms as _now_ms  # RPE6 B-001 timebase
import game.world as _gw  # RPE6 Phase 5 (D4): mission data lives in components
import game.render as _gr  # RPE6 Phase 6: the frame is submitted to the render queue
from game.render import adapters as _adapt  # RPE6 Phase 6: drawable builders for shared legacy classes
from engine.render2d import (CircleDraw as _CircleDraw, SurfaceBatchDraw as _SurfaceBatchDraw, CustomDraw as _CustomDraw, FillDraw as _FillDraw, Layer as _L,
                             RecordingPen as _RecordingPen,
                             LineDraw as _LineDraw, OverlayDraw as _OverlayDraw, RectDraw as _RectDraw,
                             SCREEN as _SCREEN, StaticLayerDraw as _StaticLayerDraw, SurfaceDraw as _SurfaceDraw,
                             TextDraw as _TextDraw, UiPassDraw as _UiPassDraw,
                             soft_shadow_surface as _soft_shadow_surface)
from missions.m5.components import M5Guard as _M5Guard


def _m5g(e):
    """Declared M5 data of an enemy (replaces the ad hoc ``e.m5_*`` attributes)."""
    return _gw.ensure(e, _M5Guard)


# Night palette (procedural fallback; matches the hud MiniMap "m4" palette).
M5_TILE_BASE = {
    "C": (44, 46, 52), "B": (64, 58, 48), "H": (52, 54, 58),
    ".": (30, 31, 34), "d": (40, 41, 45), "O": (29, 34, 40),
    "L": (34, 40, 46), "F": (38, 34, 30), "D": (52, 54, 62),
    "S": (46, 44, 40), "W": (22, 34, 42),
}
_ART_FLOOR_CODES = (".", "O", "L", "d", "F")
# Marker -> the floor it is drawn as.
_MARKER_FLOOR = {"P": "F", "E": ".", "M": ".", "N": "O", "X": "O",
                 "G": "L", "I": "O", "D": "O", "S": "L", "W": "L"}

# Guard trooper look (black kit + red armband).
C_M5_ARMBAND = (200, 30, 30)
# Field kit, drawn in the shared enemy grammar (see _draw_m5_guard).
C_M5_GUARD_KIT = (58, 58, 68)      # black tunic, lifted so it reads on night floors
C_M5_GUARD_SEAM = (76, 76, 88)
C_M5_GUARD_BELT = (30, 28, 30)
C_M5_BERET = (18, 18, 22)
C_M5_HELMET = (40, 42, 46)


def _grid():
    return _m5_maps.MISSION5_MAP


def _is_quarter():
    return _grid() is _m5_maps.MISSION5_QUARTER_MAP


def _floor_code(ch):
    if ch in _ART_FLOOR_CODES:
        return ch
    code = _MARKER_FLOOR.get(ch, ".")
    if ch == "D" and _is_quarter():
        return "d"
    return code


# ─────────────────────────────────────────────
# Tiles
# ─────────────────────────────────────────────
def _blit_floor(target, ch, col, row, sx, sy):
    code = _floor_code(ch)
    art = artpack.tile(code, col, row)
    if art is not None:
        target.blit(art, (sx, sy))
    else:
        pygame.draw.rect(target, M5_TILE_BASE.get(code, (30, 31, 34)),
                         (sx, sy, TILE_SIZE, TILE_SIZE))


def _blit_tile(target, ch, col, row, sx, sy):
    T = TILE_SIZE
    if ch in ("C", "B"):
        spr = artpack.wall(ch, col, row)
        if spr is not None:
            target.blit(spr, (sx, sy))
        else:
            base = M5_TILE_BASE[ch]
            pygame.draw.rect(target, base, (sx, sy, T, T))
            pygame.draw.line(target, tuple(min(255, c + 14) for c in base),
                             (sx, sy), (sx + T - 1, sy))
        return

    _blit_floor(target, ch, col, row, sx, sy)

    if ch == "H":   # printing press: heavy steel bed + rollers
        pygame.draw.rect(target, (34, 36, 40), (sx + 4, sy + 8, T - 8, T - 16),
                         border_radius=3)
        pygame.draw.rect(target, (72, 76, 82), (sx + 4, sy + 8, T - 8, T - 16),
                         2, border_radius=3)
        for i in range(3):
            ry = sy + 16 + i * 12
            pygame.draw.line(target, (110, 112, 116), (sx + 10, ry), (sx + T - 10, ry), 3)
        pygame.draw.rect(target, (160, 150, 120), (sx + T // 2 - 8, sy + 12, 16, 6))
    elif ch == "D":
        pygame.draw.rect(target, (16, 16, 20), (sx + 3, sy, T - 6, T), 3, border_radius=2)
    elif ch == "S":  # stair down: treads darkening toward the bottom
        for i in range(6):
            shade = max(8, 70 - i * 11)
            pygame.draw.rect(target, (shade, shade - 2, shade - 6),
                             (sx + 6, sy + 6 + i * 9, T - 12, 8))
        pygame.draw.rect(target, (200, 170, 60), (sx + 4, sy + 4, T - 8, T - 8), 2)
    elif ch == "W":
        pass  # connected flood surface is drawn after interior decor
    elif ch == "G":  # anchored gate, open onto the riverside landing
        for yy in (sy + 3, sy + T - 13):
            pygame.draw.rect(target, (74, 70, 62), (sx + 4, yy, T - 8, 10))
            pygame.draw.line(target, (110, 104, 90), (sx + 4, yy), (sx + T - 4, yy), 1)
        pygame.draw.line(target, (116, 118, 108), (sx + 8, sy + 13), (sx + T - 8, sy + 13), 3)
        for xx in range(sx + 12, sx + T - 8, 9):
            pygame.draw.line(target, (86, 92, 88), (xx, sy + 6), (xx, sy + 20), 2)


def _draw_tiles(surface, cam_x, cam_y):
    g = _grid()
    h = len(g)
    w = len(g[0]) if h else 0
    x0 = max(0, cam_x // TILE_SIZE)
    y0 = max(0, cam_y // TILE_SIZE)
    x1 = min(w, (cam_x + WIDTH) // TILE_SIZE + 1)
    y1 = min(h, (cam_y + HEIGHT) // TILE_SIZE + 1)
    for row in range(y0, y1):
        grow = g[row]
        for col in range(x0, x1):
            _blit_tile(surface, grow[col], col, row,
                       col * TILE_SIZE - cam_x, row * TILE_SIZE - cam_y)


# RPE6 Phase 6: the tile grid is a static layer (chunked bake, re-painted only when the grid
# changes). Tiles paint strictly inside their own 64x64 cell (art and procedural fallbacks
# alike), so chunk seams compose exactly like the per-frame per-tile blits did.
_M5_TILE_CHUNK = 512


def _tiles_signature():
    g = _grid()
    return (id(g), len(g), len(g[0]) if g else 0, hash(tuple(g)), _is_quarter())


def _paint_tiles_chunk(target, ox, oy, w, h):
    g = _grid()
    T = TILE_SIZE
    rows = len(g)
    cols = len(g[0]) if rows else 0
    c0, r0 = max(0, ox // T), max(0, oy // T)
    c1 = min(cols, (ox + w + T - 1) // T)
    r1 = min(rows, (oy + h + T - 1) // T)
    for row in range(r0, r1):
        grow = g[row]
        for col in range(c0, c1):
            _blit_tile(target, grow[col], col, row, col * T - ox, row * T - oy)


def _submit_tiles(q, key):
    g = _grid()
    rows = len(g)
    cols = len(g[0]) if rows else 0
    layers = _gr.static_layers()
    layers.define("m5.tiles", painter=_paint_tiles_chunk, world_size=(cols * TILE_SIZE, rows * TILE_SIZE),
                  signature=_tiles_signature(), fill=C_BG_GAME, chunk=_M5_TILE_CHUNK)
    q.submit(_StaticLayerDraw(layers, "m5.tiles", (WIDTH, HEIGHT)), _L.FLOOR, sort_key=key)


def _objective_world_pos():
    stage = getattr(STATE, "mission5_stage", None)
    if stage == STAGE_HQ:
        return _vasile_desk_pos()
    if stage == STAGE_QUARTER:
        return _printworks_door_pos()
    if stage == STAGE_PRINTWORKS:
        return _maru_office_pos()
    if stage == STAGE_RAID and not getattr(STATE, "m5_raid_active", False):
        return _stair_pos()
    if stage == STAGE_TUNNEL:
        return _river_gate_pos()
    return None


def _draw_beacon(surface, cam_x, cam_y):
    pos = _objective_world_pos()
    if pos is None:
        return
    t = _now_ms() / 1000.0
    r = 18 + int(6 * (0.5 + 0.5 * math.sin(t * 3)))
    x, y = int(pos[0] - cam_x), int(pos[1] - cam_y)
    pygame.draw.circle(surface, (220, 190, 70), (x, y), r, 2)


# ─────────────────────────────────────────────
# Actors
# ─────────────────────────────────────────────
def _draw_m5_guard(surface, e, cam_x, cam_y):
    """Presidential Guard trooper, drawn in the same top-down grammar as every
    other enemy family (entities.enemy_ai.Enemy.draw: flat uniform torso,
    sleeve arms, skin hands, skin head with headgear + eyes). Guard identity
    comes from the black kit, red armband and Guard headgear - not from a
    different body plan (the old capsule/dome read as a robot)."""
    x = e.rect.centerx - cam_x
    y = e.rect.centery - cam_y
    if not (-50 < x < WIDTH + 50 and -50 < y < HEIGHT + 50):
        return
    a = e.angle
    dx, dy = math.cos(a), math.sin(a)
    px, py = math.cos(a + math.pi / 2), math.sin(a + math.pi / 2)
    kind = _m5g(e).kind

    # walk sway: same displacement-driven phase as Enemy.draw
    moved = e.walk.advance(e.rect.centerx, e.rect.centery)
    ph = e.walk.phase
    sway = math.sin(ph) * 1.6 if moved > 0.4 else math.sin(ph * 0.25) * 0.5
    x += px * sway
    y += py * sway

    def L(f, sd):            # local (forward, side) -> screen
        return (x + f * dx + sd * px, y + f * dy + sd * py)

    def I(p):
        return (int(p[0]), int(p[1]))

    surface.blit(_enemy_shadow, (int(x - 17), int(y - 5)))
    spr = _guard_rot(kind, a)
    if spr is not None:                       # baked sprite (src/game/art/m5/m5_guard.py)
        surface.blit(spr, spr.get_rect(center=(int(x), int(y))))
        head = L(2, 0)
        if kind == "raider":                  # dome catchlight stays upper-left (key light)
            pygame.draw.circle(surface, (66, 68, 72), (int(head[0] - 3), int(head[1] - 3)), 2)
        face = L(4, 0)
        for off in (-0.25, 0.25):
            pygame.draw.circle(surface, (40, 25, 15), (int(face[0] + math.cos(a + off) * 3),
                                                       int(face[1] + math.sin(a + off) * 3)), 1)
        if getattr(e, "hit_flash", 0) > 0 or getattr(e, "flash_timer", 0) > 0:
            pygame.draw.circle(surface, (255, 255, 255), I(head), 10, 1)
        return
    uni, seam, skin = C_M5_GUARD_KIT, C_M5_GUARD_SEAM, C_ENEMY_SKIN

    # torso: same 20x13 block as the other troopers, black Guard tunic
    torso = [L(-6.5, -10), L(6.5, -10), L(6.5, 10), L(-6.5, 10)]
    pygame.draw.polygon(surface, uni, torso)
    pygame.draw.line(surface, seam, L(-4, 0), L(4, 0), 2)                  # tunic seam
    pygame.draw.line(surface, C_M5_GUARD_BELT, L(-1, -10), L(-1, 10), 2)   # cross belt
    # arms to the weapon, skin hands on the grip
    arm_len = 15
    hand = L(arm_len, 0)
    pygame.draw.line(surface, uni, L(0, 11), (hand[0] - px * 3, hand[1] - py * 3), 5)
    pygame.draw.line(surface, uni, L(0, -11), (hand[0] + px * 3, hand[1] + py * 3), 5)
    # red armband on the left sleeve - the faction mark, IPA placement
    pygame.draw.line(surface, C_M5_ARMBAND, I(L(0, 9)), I(L(4, 9)), 3)
    grip = L(arm_len + 4, 0)
    glen = 26 if kind == "marksman" else 20
    pygame.draw.circle(surface, skin, I(grip), 4)
    pygame.draw.line(surface, (30, 28, 26), L(arm_len + 6, 0), L(arm_len + 4 + glen, 0), 3)
    pygame.draw.circle(surface, (52, 50, 48), I(L(arm_len + 4 + glen, 0)), 2)
    if kind == "marksman":
        pygame.draw.line(surface, (20, 20, 22), L(arm_len + 7, 0), L(arm_len + 13, 0), 5)   # scope

    # head: skin, then headgear pushed to the back so the face stays visible
    head = L(2, 0)
    hr = 8
    pygame.draw.circle(surface, skin, I(head), hr)
    if kind == "raider":
        # steel helmet: covers crown + sides, face crescent left open
        pygame.draw.circle(surface, C_M5_HELMET, I(L(-1, 0)), hr + 1)
        pygame.draw.circle(surface, skin, I(L(4, 0)), hr - 3)
        pygame.draw.circle(surface, (66, 68, 72), I(L(-3, -3)), 2)          # lit dome
        pygame.draw.line(surface, (20, 20, 22), L(3, -hr + 1), L(3, hr - 1), 1)   # chin strap
    else:
        # black Guard beret, slouched to one side, red cockade
        pygame.draw.circle(surface, C_M5_BERET, I(L(-2, -1)), hr)
        pygame.draw.circle(surface, skin, I(L(3, 1)), hr - 3)
        pygame.draw.circle(surface, C_M5_ARMBAND, I(L(-5, -5)), 2)        # cockade, on the slouch
    face = L(4, 0)
    for off in (-0.25, 0.25):
        ex = face[0] + math.cos(a + off) * 3
        ey = face[1] + math.sin(a + off) * 3
        pygame.draw.circle(surface, (40, 25, 15), (int(ex), int(ey)), 1)
    if getattr(e, "hit_flash", 0) > 0 or getattr(e, "flash_timer", 0) > 0:
        pygame.draw.circle(surface, (255, 255, 255), I(head), 10, 1)


_GUARD_ROT = {}
_GUARD_BUCKETS = 64


def _guard_rot(kind, a):
    """Guard sprite rotated to the nearest of 64 headings (cached)."""
    v = {"marksman": 1, "raider": 2}.get(kind, 0)
    b = int(round(a / (2 * math.pi) * _GUARD_BUCKETS)) % _GUARD_BUCKETS
    key = (v, b)
    spr = _GUARD_ROT.get(key)
    if spr is None:
        base = _m5art("m5_guard", v)
        if base is None:
            return None
        spr = pygame.transform.rotate(base, -b * 360.0 / _GUARD_BUCKETS)
        _GUARD_ROT[key] = spr
    return spr


def _draw_enemies(surface, cam_x, cam_y):
    for e in STATE.enemies:
        if _m5g(e).guard:
            _draw_m5_guard(surface, e, cam_x, cam_y)
        else:
            e.draw(surface, cam_x, cam_y)


_M5_KIT_SS = 3               # supersample factor; scaled down once into the pose cache
_M5_KIT_SCALE = 0.232        # ~58 px tall (foot y+22 -> crown y-36), matches M4's kit NPCs
_M5_POSE = (84, 84)
_M5_ANCHOR = (42, 48)
# Two identical skins except the coat hue strobes red on a hit.
_M5_WARDROBE_OFF = [{"coat": (26, 28, 34)}, {"coat": (150, 46, 42)}]


# Guard HQ cast looks: (figure_kit cast member, wardrobe overrides).
_HQ_LOOKS = {
    "OLD SQUADMATE": ("krap", {}),
    "DESK SERGEANT": ("krap", {"hair": (96, 90, 84), "bulk": 1.12, "height": 252,
                               "stubble": False, "shirt": (170, 168, 156)}),
    "RECRUIT": ("krap", {"hair": (112, 82, 52), "stubble": False, "height": 246,
                         "bulk": 0.94, "skin": (204, 168, 138)}),
    "ARMORER": ("civilian", {"long_coat": False, "coat": (58, 66, 74),
                             "lapel": (46, 52, 60), "shirt": (52, 70, 104),
                             "trousers": (38, 44, 52), "glove": (46, 40, 32),
                             "bulk": 1.1, "belt": (40, 30, 20)}),
    "VASILE": ("vasile", {}),
}
_HQ_FACE_RADIUS = TILE_SIZE * 3.2


def _draw_hq_figure(s, who, wardrobe, right, armband):
    """One HQ squadmate as a figure_kit body (same rig/scale as Maru), with
    the new Guard armband painted on the near upper arm."""
    from cutscenes.figure_kit import SPECS, draw_character
    ss = _M5_KIT_SS
    x, foot = _M5_ANCHOR[0], _M5_ANCHOR[1] + 22
    big = pygame.Surface((s.get_width() * ss, s.get_height() * ss), pygame.SRCALPHA)
    draw_character(big, who, x * ss, foot * ss, _M5_KIT_SCALE * ss, right,
                   wardrobe=wardrobe or None)
    if armband:
        spec = {**SPECS[who], **(wardrobe or {})}
        k = _M5_KIT_SCALE * ss * spec["height"] / 296.0
        f = 1 if right else -1
        bulk = spec["bulk"]
        ax = x * ss + f * 38 * bulk * k
        ay = foot * ss + (-258 + 51) * k + 34 * k
        w, h = 22 * bulk * k, 13 * k
        band = pygame.Rect(0, 0, max(3, round(w)), max(2, round(h)))
        band.center = (round(ax), round(ay))
        pygame.draw.rect(big, (10, 10, 12), band.inflate(ss, ss))
        pygame.draw.rect(big, C_M5_ARMBAND, band)
    s.blit(pygame.transform.smoothscale(big, s.get_size()), (0, 0))


def _hq_pose(name, right, armband):
    who, wardrobe = _HQ_LOOKS.get(name, ("krap", {}))
    key = ("m5hq_v1", name, bool(right), bool(armband))
    return artpack.pose(key, _M5_POSE,
                        lambda s: _draw_hq_figure(s, who, wardrobe, right, armband))


def _m5art(name, variant=0):
    """Cached M5 sprite or None (callers keep their procedural fallback)."""
    try:
        from art import m5 as _art
        return _art.get(name, variant)
    except Exception:
        return None


def _draw_hq_locker(surface, x, y):
    """Steel locker, name strip taped over in black."""
    render_util.soft_shadow(surface, (x - 16, y + 12, 32, 10), alpha=80)
    spr = _m5art("hq_locker", 0)
    if spr is not None:                       # baked sprite (src/game/art/m5/hq_locker.py)
        surface.blit(spr, (x - 13, y - 26))
        return
    body = pygame.Rect(x - 13, y - 26, 26, 44)
    pygame.draw.rect(surface, (62, 68, 74), body)
    pygame.draw.rect(surface, (84, 90, 98), (body.x, body.y, 4, body.h))
    pygame.draw.rect(surface, (40, 44, 50), (body.right - 4, body.y, 4, body.h))
    pygame.draw.line(surface, (34, 36, 40), (x, body.y + 2), (x, body.bottom - 2), 1)
    for vy in range(body.y + 6, body.y + 16, 3):
        pygame.draw.line(surface, (30, 32, 36), (body.x + 6, vy), (x - 3, vy), 1)
        pygame.draw.line(surface, (30, 32, 36), (x + 3, vy), (body.right - 6, vy), 1)
    pygame.draw.rect(surface, (12, 12, 14), (body.x + 5, body.y + 20, body.w - 10, 6))
    pygame.draw.rect(surface, (150, 150, 140), (x - 6, body.y + 30, 3, 6))
    pygame.draw.rect(surface, (24, 26, 30), body, 1)


def _draw_hq_npcs(surface, cam_x, cam_y):
    """Guard HQ walk: squadmates (figure_kit KRAP bodies, most wearing the
    new red armband), Vasile behind the flag desk, the taped-over locker.
    People turn to look at Biribel when he walks close."""
    if getattr(STATE, "mission5_stage", None) != STAGE_HQ:
        return
    ppos = None
    if STATE.player:
        ppos = (STATE.player.rect.centerx, STATE.player.rect.centery)
    for n in getattr(STATE, "m5_hq_npcs", []) or []:
        x, y = int(n["x"] - cam_x), int(n["y"] - cam_y)
        if not (-60 < x < WIDTH + 60 and -60 < y < HEIGHT + 60):
            continue
        if n["prop"]:
            _draw_hq_locker(surface, x, y)
            continue
        if n["vasile"]:
            # The flag on the desk: Guard black over red.
            fx, fy = x + 34, y - 8
            pygame.draw.line(surface, (180, 170, 140), (fx, fy - 26), (fx, fy + 18), 2)
            pygame.draw.rect(surface, (20, 20, 24), (fx + 1, fy - 26, 22, 8))
            pygame.draw.rect(surface, (190, 30, 30), (fx + 1, fy - 18, 22, 8))
        right = n.get("face_right", n["x"] % 2 < 1)
        if ppos is not None and math.hypot(ppos[0] - n["x"], ppos[1] - n["y"]) < _HQ_FACE_RADIUS:
            right = ppos[0] >= n["x"]
            n["face_right"] = right
        surface.blit(_hq_pose(n["name"], right, n["armband"] and not n["vasile"]),
                     (x - _M5_ANCHOR[0], y - _M5_ANCHOR[1]))
        col = C_VASILE if n["vasile"] else (170, 180, 195)
        tag = font_terminal_small.render(n["name"], True, col)
        surface.blit(tag, (x - tag.get_width() // 2, y - 40 - tag.get_height()))




def _m5_dim(col, k):
    return (int(col[0] * k), int(col[1] * k), int(col[2] * k))


def _draw_maru_figure(s, x, y, a, flash):
    """Maru as the cutscenes.figure_kit cast member - the same black-hoodie,
    backpack-strap rig M4 draws at the station meet and W5 will use in the
    ending cutscene. The good arm points the pistol (M4's armed-pose math);
    the wounded arm hangs in a white sling on the body's left side, so it
    reads from every facing. Rotates with facing like any other top-down
    body; cached per angle through artpack.pose."""
    from cutscenes.figure_kit import SPECS, draw_character
    ss = _M5_KIT_SS
    spec = SPECS["maru"]
    dx, dy = math.cos(a), math.sin(a)
    right = dx >= 0
    foot = y + 22
    big = pygame.Surface((s.get_width() * ss, s.get_height() * ss), pygame.SRCALPHA)

    # Pistol rig: foreshortened 3/4 view, magazine always hanging down
    # (m4.draw._m4_draw_npc_kit idiom).
    ang = math.atan2(dy * 0.55, dx)
    shrink = 0.62 + 0.38 * abs(dx)
    ux, uy = math.cos(ang) * shrink, math.sin(ang)
    nx, ny = -math.sin(ang), math.cos(ang)
    if not right:
        nx, ny = -nx, -ny
    behind = dy < -0.35
    side = 7.0 * (0.55 + 0.45 * abs(dx)) + (3.0 if behind else 0.0)
    gx, gy = x + (side if right else -side) + ux * 4, y - 13 + uy * 3

    def G(px_, py_):
        return ((gx + ux * px_ + nx * py_) * ss, (gy + uy * px_ + ny * py_) * ss)

    slide = int(flash) % 2          # hit-flash strobe between two skins
    parts = [
        ("dark", [(-0.6, 0.6), (2.2, 0.6), (1.4, 5.0), (-1.4, 4.6)]),      # grip
        ("metal", [(-1.2, -1.6), (9.6, -1.6), (9.6, 0.8), (-1.2, 0.8)]),   # slide
        ("dark", [(2.4, 0.8), (4.6, 0.8), (4.0, 2.2), (2.4, 2.2)]),        # trigger guard
    ]
    cols = {"dark": (22, 23, 25), "metal": (58, 60, 64)}

    def draw_gun():
        for kind, pts in parts:
            poly = [G(*p_) for p_ in pts]
            pygame.draw.polygon(big, cols[kind], poly)
            pygame.draw.polygon(big, (8, 8, 9), poly, max(1, ss // 2))
        pygame.draw.line(big, (150, 145, 132), G(-0.6, -1.2), G(9.0, -1.2),
                         max(1, ss // 2))

    k = _M5_KIT_SCALE * ss * spec["height"] / 296.0
    f = 1 if right else -1
    bulk = spec["bulk"]
    sh_y = foot * ss + (-258 + 51) * k
    near_sh = (x * ss + f * 36 * bulk * k, sh_y)
    far_sh = (x * ss - f * 30 * bulk * k, sh_y)
    grip_h, front_h = G(0.6, 1.2), G(1.8, 1.8)
    sleeve = spec["coat"]
    hand_col = spec["skin"]
    w_arm = max(2, round(15 * bulk * k))

    def hand_dot(hand):
        r = max(2, round(6.5 * k))
        pygame.draw.circle(big, (10, 10, 12), (round(hand[0]), round(hand[1])), r + 1)
        pygame.draw.circle(big, hand_col, (round(hand[0]), round(hand[1])), r)

    def arm(sh, hand, col):
        mx, my = (sh[0] + hand[0]) / 2, (sh[1] + hand[1]) / 2
        el = (mx - f * 3 * k * 4, my + 9 * k * 2.2)
        pygame.draw.line(big, (10, 10, 12), sh, el, w_arm + 2)
        pygame.draw.line(big, (10, 10, 12), el, hand, w_arm + 2)
        pygame.draw.line(big, col, sh, el, w_arm)
        pygame.draw.line(big, col, el, hand, w_arm)
        pygame.draw.circle(big, col, (round(el[0]), round(el[1])), w_arm // 2)
        hand_dot(hand)

    if behind:                       # gun carried up-screen, behind the body
        draw_gun()
        arm(far_sh, front_h, _m5_dim(sleeve, 0.78))
        arm(near_sh, grip_h, _m5_dim(sleeve, 0.78))
        draw_character(big, "maru", x * ss, foot * ss, _M5_KIT_SCALE * ss,
                       right, arms=False, wardrobe=_M5_WARDROBE_OFF[slide])
    else:
        arm(far_sh, front_h, _m5_dim(sleeve, 0.78))
        draw_character(big, "maru", x * ss, foot * ss, _M5_KIT_SCALE * ss,
                       right, arms=False, wardrobe=_M5_WARDROBE_OFF[slide])
        draw_gun()
        hand_dot(front_h)
        arm(near_sh, grip_h, tuple(min(255, int(c * 1.25 + 8)) for c in sleeve))

    # Wounded arm: hangs from Maru's LEFT shoulder (figure-local X -40, which
    # flips with facing like the kit's own limbs), sleeve down to the wrist,
    # bandaged hand. The good (right) arm carries the pistol, so the near-side
    # gun pose never crosses the sling.
    left_sx = x * ss - f * 40 * bulk * k
    elbow_y = foot * ss - 171 * k
    wrist_y = foot * ss - 145 * k
    pygame.draw.line(big, (10, 10, 12), (left_sx, sh_y), (left_sx, elbow_y),
                     w_arm + 2)
    pygame.draw.line(big, (10, 10, 12), (left_sx, elbow_y), (left_sx, wrist_y),
                     w_arm + 2)
    pygame.draw.line(big, _m5_dim(sleeve, 0.78), (left_sx, sh_y),
                     (left_sx, elbow_y), w_arm)
    pygame.draw.line(big, _m5_dim(sleeve, 0.78), (left_sx, elbow_y),
                     (left_sx, wrist_y), w_arm)
    hand_r = max(2, round(6.5 * k))
    pygame.draw.circle(big, (10, 10, 12), (round(left_sx), round(wrist_y)),
                       hand_r + 1)
    pygame.draw.circle(big, (228, 226, 218), (round(left_sx), round(wrist_y)),
                       hand_r)
    s.blit(pygame.transform.smoothscale(big, s.get_size()), (0, 0))


def _maru_pose(angle, flash):
    try:                                      # baked sprite (src/game/art/m5/maru.py)
        from art.m5 import maru as _maru_art
        spr = _m5art("maru", _maru_art.variant_for(angle, flash))
    except Exception:
        spr = None
    if spr is not None and spr.get_size() == _M5_POSE:
        return spr
    key = ("m5maru_v5", int(round(math.degrees(angle))), bool(flash))
    return artpack.pose(key, _M5_POSE,
                        lambda s: _draw_maru_figure(s, _M5_ANCHOR[0],
                                                    _M5_ANCHOR[1], angle, flash))


def _draw_maru(surface, cam_x, cam_y):
    """Maru (figure_kit cast look, wounded-arm sling) + name tag; HP bar in
    raid/tunnel."""
    stage = getattr(STATE, "mission5_stage", None)
    m = getattr(STATE, "m5_maru", None)
    for name, (wx, wy), color, facing, _weapon in friendly_npcs():
        x, y = int(wx - cam_x), int(wy - cam_y)
        if not (-60 < x < WIDTH + 60 and -60 < y < HEIGHT + 60):
            continue
        flash = m.get("hit_flash", 0) if m else 0
        surface.blit(_maru_pose(facing, flash),
                     (x - _M5_ANCHOR[0], y - _M5_ANCHOR[1]))
        if m and m.get("muzzle", 0) > 0:
            mx_ = x + math.cos(facing) * 20
            my_ = y - 13 + math.sin(facing) * 12
            pygame.draw.circle(surface, (255, 214, 120), (int(mx_), int(my_)), 6)
            pygame.draw.circle(surface, (255, 250, 220), (int(mx_), int(my_)), 3)
        tag = font_terminal_small.render(name, True, color)
        ty = y - 38 - tag.get_height()
        surface.blit(tag, (x - tag.get_width() // 2, ty))
        if m and stage in (STAGE_RAID, STAGE_TUNNEL):
            bw = 34
            frac = max(0.0, min(1.0, m["hp"] / max(1, m["max_hp"])))
            bx, by = x - bw // 2, ty + tag.get_height() + 2
            pygame.draw.rect(surface, (28, 28, 28), (bx, by, bw, 4))
            fill = (120, 220, 150) if frac > 0.35 else (220, 80, 70)
            pygame.draw.rect(surface, fill, (bx, by, int(bw * frac), 4))
            if m.get("waiting"):
                w = font_terminal_small.render(_T("draw.waiting"), True, (220, 200, 120))
                surface.blit(w, (x - w.get_width() // 2, by + 6))


_MAG_SPRITES = {}


def _mag_sprite(kind):
    """Thrown magazine art: K-9 stick mag (as M3's Volkov throw) or a
    short 9mm pistol mag. Cached per kind."""
    s = _MAG_SPRITES.get(kind)
    if s is not None:
        return s
    s = _m5art("mag", 0 if kind == "k9" else 1)   # baked sprite (src/game/art/m5/mag.py)
    if s is not None:
        _MAG_SPRITES[kind] = s
        return s
    if kind == "k9":
        s = pygame.Surface((12, 29), pygame.SRCALPHA)
        body = [(2, 4), (10, 4), (9, 25), (3, 25)]
        pygame.draw.polygon(s, (25, 32, 30), body)
        pygame.draw.polygon(s, (82, 98, 90), body, 1)
        pygame.draw.line(s, (48, 60, 56), (4, 6), (4, 23), 1)
        for ry in (10, 15, 20):
            pygame.draw.line(s, (56, 68, 63), (4, ry), (8, ry), 1)
        for wy in (8, 14, 20):
            pygame.draw.circle(s, (166, 137, 55), (7, wy), 1)
        pygame.draw.line(s, (132, 145, 138), (3, 3), (5, 1), 1)
        pygame.draw.line(s, (132, 145, 138), (9, 3), (7, 1), 1)
        pygame.draw.rect(s, (12, 16, 15), (2, 24, 8, 4), border_radius=1)
    else:
        s = pygame.Surface((10, 19), pygame.SRCALPHA)
        pygame.draw.rect(s, (30, 32, 34), (2, 3, 6, 13), border_radius=1)
        pygame.draw.rect(s, (92, 96, 100), (2, 3, 6, 13), 1, border_radius=1)
        pygame.draw.circle(s, (176, 142, 60), (5, 3), 2)       # top round
        pygame.draw.rect(s, (14, 15, 16), (1, 15, 8, 3), border_radius=1)
    _MAG_SPRITES[kind] = s
    return s


def _draw_maru_mags(surface, cam_x, cam_y):
    """Maru's resupply throw (world.py _update_maru_mags): mags in flight
    with a short trail and a ground shadow so the arc reads top-down."""
    for mag in getattr(STATE, "m5_maru_mags", None) or ():
        if mag["age"] < mag.get("delay", 0):
            continue
        sx, sy = mag["x"] - cam_x, mag["y"] - cam_y
        dur = max(1, mag.get("duration", 42))
        t = max(0.0, min(1.0, (mag["age"] - mag.get("delay", 0)) / dur))
        lift = math.sin(math.pi * t) * mag.get("arc_height", 76.0)
        # Shadow on the ground path (under the arc).
        sh = pygame.Surface((14, 6), pygame.SRCALPHA)
        pygame.draw.ellipse(sh, (0, 0, 0, max(30, 90 - int(lift))), sh.get_rect())
        surface.blit(sh, (sx - 7, sy + lift - 3))
        spr = _mag_sprite(mag.get("kind", "k9"))
        rot = pygame.transform.rotate(spr, math.degrees(mag.get("rot", 0.0)))
        for i in (2, 1):
            ghost = rot.copy()
            ghost.set_alpha(50 - i * 15)
            surface.blit(ghost, (sx - mag["vx"] * i * 1.5 - rot.get_width() // 2,
                                 sy - mag["vy"] * i * 1.5 - rot.get_height() // 2))
        surface.blit(rot, (sx - rot.get_width() // 2, sy - rot.get_height() // 2))


def _submit_maru(q, key):
    """Queue twin of ``_draw_maru`` (same numbers, screen space; ADR-017)."""
    stage = getattr(STATE, "mission5_stage", None)
    m = getattr(STATE, "m5_maru", None)
    cam_x, cam_y = q.cam_x, q.cam_y
    sub = q.submit
    L = _L.ENTITIES
    for name, (wx, wy), color, facing, _weapon in friendly_npcs():
        x, y = int(wx - cam_x), int(wy - cam_y)
        if not (-60 < x < WIDTH + 60 and -60 < y < HEIGHT + 60):
            continue
        flash = m.get("hit_flash", 0) if m else 0
        sub(_SurfaceDraw(_maru_pose(facing, flash), (x - _M5_ANCHOR[0], y - _M5_ANCHOR[1]), space=_SCREEN), L,
            sort_key=key)
        if m and m.get("muzzle", 0) > 0:
            mx_ = x + math.cos(facing) * 20
            my_ = y - 13 + math.sin(facing) * 12
            sub(_CircleDraw((int(mx_), int(my_)), 6, (255, 214, 120), space=_SCREEN), L, sort_key=key)
            sub(_CircleDraw((int(mx_), int(my_)), 3, (255, 250, 220), space=_SCREEN), L, sort_key=key)
        tag = font_terminal_small.render(name, True, color)
        ty = y - 38 - tag.get_height()
        sub(_SurfaceDraw(tag, (x - tag.get_width() // 2, ty), space=_SCREEN), L, sort_key=key)
        if m and stage in (STAGE_RAID, STAGE_TUNNEL):
            bw = 34
            frac = max(0.0, min(1.0, m["hp"] / max(1, m["max_hp"])))
            bx, by = x - bw // 2, ty + tag.get_height() + 2
            sub(_RectDraw((bx, by, bw, 4), (28, 28, 28), space=_SCREEN), L, sort_key=key)
            fill = (120, 220, 150) if frac > 0.35 else (220, 80, 70)
            sub(_RectDraw((bx, by, int(bw * frac), 4), fill, space=_SCREEN), L, sort_key=key)
            if m.get("waiting"):
                sub(_TextDraw(_T("draw.waiting"), font_terminal_small, (x, by + 6), (220, 200, 120), anchor="midtop"),
                    L, sort_key=key)


def _submit_maru_mags(q, key):
    """Queue twin of ``_draw_maru_mags``: shadow, two ghost trails, the mag."""
    cam_x, cam_y = q.cam_x, q.cam_y
    sub = q.submit
    L = _L.ENTITIES
    for mag in getattr(STATE, "m5_maru_mags", None) or ():
        if mag["age"] < mag.get("delay", 0):
            continue
        sx, sy = mag["x"] - cam_x, mag["y"] - cam_y
        dur = max(1, mag.get("duration", 42))
        t = max(0.0, min(1.0, (mag["age"] - mag.get("delay", 0)) / dur))
        lift = math.sin(math.pi * t) * mag.get("arc_height", 76.0)
        sh = pygame.Surface((14, 6), pygame.SRCALPHA)
        pygame.draw.ellipse(sh, (0, 0, 0, max(30, 90 - int(lift))), sh.get_rect())
        sub(_SurfaceDraw(sh, (sx - 7, sy + lift - 3), space=_SCREEN), L, sort_key=key)
        spr = _mag_sprite(mag.get("kind", "k9"))
        rot = pygame.transform.rotate(spr, math.degrees(mag.get("rot", 0.0)))
        for i in (2, 1):
            ghost = rot.copy()
            ghost.set_alpha(50 - i * 15)
            sub(_SurfaceDraw(ghost, (sx - mag["vx"] * i * 1.5 - rot.get_width() // 2,
                                     sy - mag["vy"] * i * 1.5 - rot.get_height() // 2), space=_SCREEN), L, sort_key=key)
        sub(_SurfaceDraw(rot, (sx - rot.get_width() // 2, sy - rot.get_height() // 2), space=_SCREEN), L, sort_key=key)


def _submit_pickups(q, key):
    """Queue twin of ``_draw_pickup`` (icon or the procedural fallback, kept)."""
    cam_x, cam_y = q.cam_x, q.cam_y
    sub = q.submit
    L = _L.ENTITIES
    for pu in STATE.pickups:
        x, y = int(pu[0] - cam_x), int(pu[1] - cam_y)
        if not (-40 < x < WIDTH + 40 and -40 < y < HEIGHT + 40):
            continue
        kind = pu[2] if len(pu) > 2 else "bandage"
        if kind == "bandage":
            spr = artpack.icon("bandage")
            if spr is not None:
                sub(_SurfaceDraw(spr, (x - spr.get_width() // 2, y - spr.get_height() // 2), space=_SCREEN), L,
                    sort_key=key)
                continue
            sub(_RectDraw((x - 9, y - 7, 18, 14), (222, 226, 224), border_radius=3, space=_SCREEN), L, sort_key=key)
            sub(_RectDraw((x - 2, y - 6, 4, 12), (200, 70, 70), space=_SCREEN), L, sort_key=key)
            sub(_RectDraw((x - 6, y - 2, 12, 4), (200, 70, 70), space=_SCREEN), L, sort_key=key)
            continue
        body = pygame.Rect(x - 6, y - 12, 12, 24)
        sub(_RectDraw(body, (34, 40, 42), border_radius=2, space=_SCREEN), L, sort_key=key)
        sub(_RectDraw(body, (96, 120, 116), 1, border_radius=2, space=_SCREEN), L, sort_key=key)
        for ri in range(4):
            sub(_CircleDraw((x, body.y + 4 + ri * 5), 2, (210, 178, 70), space=_SCREEN), L, sort_key=key)


def _submit_hq_npcs(q, key):
    """Queue twin of ``_draw_hq_npcs`` (locker, Vasile's flag, figure poses, name tags)."""
    if getattr(STATE, "mission5_stage", None) != STAGE_HQ:
        return
    cam_x, cam_y = q.cam_x, q.cam_y
    sub = q.submit
    L = _L.ENTITIES
    ppos = None
    if STATE.player:
        ppos = (STATE.player.rect.centerx, STATE.player.rect.centery)
    for n in getattr(STATE, "m5_hq_npcs", []) or []:
        x, y = int(n["x"] - cam_x), int(n["y"] - cam_y)
        if not (-60 < x < WIDTH + 60 and -60 < y < HEIGHT + 60):
            continue
        if n["prop"]:
            spr = _m5art("hq_locker", 0)
            if spr is None:                     # procedural locker stays whole (fallback kept)
                sub(_CustomDraw(lambda s, cx, cy, x=x, y=y: _draw_hq_locker(s, x, y), "m5.hq_locker_fallback"), L,
                    sort_key=key)
                continue
            made = _soft_shadow_surface((x - 16, y + 12, 32, 10), alpha=80)
            if made is not None:
                sub(_SurfaceDraw(made[0], made[1], space=_SCREEN), L, sort_key=key)
            sub(_SurfaceDraw(spr, (x - 13, y - 26), space=_SCREEN), L, sort_key=key)
            continue
        if n["vasile"]:
            fx, fy = x + 34, y - 8
            sub(_LineDraw([(fx, fy - 26), (fx, fy + 18)], (180, 170, 140), 2, space=_SCREEN), L, sort_key=key)
            sub(_RectDraw((fx + 1, fy - 26, 22, 8), (20, 20, 24), space=_SCREEN), L, sort_key=key)
            sub(_RectDraw((fx + 1, fy - 18, 22, 8), (190, 30, 30), space=_SCREEN), L, sort_key=key)
        right = n.get("face_right", n["x"] % 2 < 1)
        if ppos is not None and math.hypot(ppos[0] - n["x"], ppos[1] - n["y"]) < _HQ_FACE_RADIUS:
            right = ppos[0] >= n["x"]
            n["face_right"] = right
        sub(_SurfaceDraw(_hq_pose(n["name"], right, n["armband"] and not n["vasile"]),
                         (x - _M5_ANCHOR[0], y - _M5_ANCHOR[1]), space=_SCREEN), L, sort_key=key)
        col = C_VASILE if n["vasile"] else (170, 180, 195)
        tag = font_terminal_small.render(n["name"], True, col)
        sub(_SurfaceDraw(tag, (x - tag.get_width() // 2, y - 40 - tag.get_height()), space=_SCREEN), L, sort_key=key)


def _melee_progress():
    """0..1 swing progress (M1/M2 hard-code 18; M5 uses the real swing length)."""
    if not getattr(STATE, "melee_active", False) or getattr(STATE, "melee_timer", 0) <= 0:
        return 0.0
    dur = max(1.0, float(getattr(STATE, "melee_duration", 18)))
    return max(0.0, min(1.0, 1.0 - STATE.melee_timer / dur))


def _submit_player(q, key):
    """The player through the recording Pen (B-033): Player.draw's primitives as drawables,
    same call, same numbers - `pen.items` in call order on the entities layer."""
    if not STATE.player:
        return
    from entities import death_anim as _da  # lazy: as _draw_player had it
    if _da.should_skip_player_draw():
        return
    cam_x, cam_y = q.cam_x, q.cam_y
    k = _m5_maps._last_keys
    is_moving = bool(k) and (k[pygame.K_w] or k[pygame.K_s] or k[pygame.K_a]
                             or k[pygame.K_d]) and not _movement_locked()
    cw = getattr(STATE, "current_weapon", "")
    dur = 90 if cw == "os12" else (72 if cw == "k9_smg" else 60)
    prog = (1.0 - STATE.reload_timer / dur
            if STATE.is_reloading and STATE.reload_timer > 0 else 0.0)
    STATE.player.story_outfit = _outfits.gameplay_outfit(STATE)  # Guard black + KRAP-blue yoke
    pen = _RecordingPen()
    STATE.player.draw(None, cam_x, cam_y, walls=_solid_walls(),
                      reload_active=STATE.is_reloading,
                      reload_progress=max(0.0, min(1.0, prog)),
                      melee_active=getattr(STATE, "melee_active", False),
                      melee_progress=_melee_progress(), is_moving=is_moving, pen=pen)
    for d in pen.items:
        q.submit(d, _L.ENTITIES, sort_key=key)


def _draw_player(surface, cam_x, cam_y):
    if not STATE.player:
        return
    from entities import death_anim as _da
    if _da.should_skip_player_draw():
        return
    k = _m5_maps._last_keys
    is_moving = bool(k) and (k[pygame.K_w] or k[pygame.K_s] or k[pygame.K_a]
                             or k[pygame.K_d]) and not _movement_locked()
    cw = getattr(STATE, "current_weapon", "")
    dur = 90 if cw == "os12" else (72 if cw == "k9_smg" else 60)
    prog = (1.0 - STATE.reload_timer / dur
            if STATE.is_reloading and STATE.reload_timer > 0 else 0.0)
    STATE.player.story_outfit = _outfits.gameplay_outfit(STATE)  # Guard black + KRAP-blue yoke
    STATE.player.draw(surface, cam_x, cam_y, walls=_solid_walls(),
                      reload_active=STATE.is_reloading,
                      reload_progress=max(0.0, min(1.0, prog)),
                      melee_active=getattr(STATE, "melee_active", False),
                      melee_progress=_melee_progress(), is_moving=is_moving)


def _draw_pickup(surface, pu, cam_x, cam_y):
    x, y = int(pu[0] - cam_x), int(pu[1] - cam_y)
    if not (-40 < x < WIDTH + 40 and -40 < y < HEIGHT + 40):
        return
    kind = pu[2] if len(pu) > 2 else "bandage"
    if kind == "bandage":
        spr = artpack.icon("bandage")
        if spr is not None:
            surface.blit(spr, (x - spr.get_width() // 2, y - spr.get_height() // 2))
            return
        pygame.draw.rect(surface, (222, 226, 224), (x - 9, y - 7, 18, 14), border_radius=3)
        pygame.draw.rect(surface, (200, 70, 70), (x - 2, y - 6, 4, 12))
        pygame.draw.rect(surface, (200, 70, 70), (x - 6, y - 2, 12, 4))
        return
    body = pygame.Rect(x - 6, y - 12, 12, 24)
    pygame.draw.rect(surface, (34, 40, 42), body, border_radius=2)
    pygame.draw.rect(surface, (96, 120, 116), body, 1, border_radius=2)
    for ri in range(4):
        pygame.draw.circle(surface, (210, 178, 70), (x, body.y + 4 + ri * 5), 2)


# ─────────────────────────────────────────────
# Dialogue / HUD
# ─────────────────────────────────────────────
def _wrap(text, font, max_w):
    out = []
    for para in text.split("\n"):
        line = ""
        for word in para.split(" "):
            test = (line + " " + word).strip()
            if font.size(test)[0] <= max_w or not line:
                line = test
            else:
                out.append(line)
                line = word
        out.append(line)
    return out


def _draw_dialogue(surface):
    dlg = _m5_flow._m5_dlg
    if not dlg["active"]:
        return
    beat = _m5_flow._current_beat()
    if beat is None:
        return
    t = _now_ms()
    speaker = beat.get("speaker", "")
    color = tuple(beat.get("color", C_WHITE))[:3]
    system = speaker == "SYSTEM"
    body = font_dialogue
    line_h = body.get_height() + 3
    shown = beat["text"][:dlg["char_idx"]]
    typed = _m5_flow._line_fully_typed()

    # Cinematic bars while a conversation is on screen.
    bar = 46
    bars = pygame.Surface((WIDTH, bar), pygame.SRCALPHA)
    bars.fill((0, 0, 0, 170))
    surface.blit(bars, (0, 0))
    surface.blit(bars, (0, HEIGHT - bar))

    panel_w = min(WIDTH - 90, 820)
    port = 0 if system else 104
    pad = 20
    text_w = panel_w - pad * 2 - (port + 16 if port else 0)
    full_lines = _wrap(beat["text"], body, text_w) or [""]
    lines = _wrap(shown, body, text_w) if shown else [""]
    panel_h = max(port + 24, len(full_lines) * line_h + 58)  # sized to the FULL line: no jumping
    px = (WIDTH - panel_w) // 2
    py = HEIGHT - bar - panel_h - 14

    bg = pygame.Surface((panel_w, panel_h), pygame.SRCALPHA)
    for i in range(panel_h):  # vertical gradient
        a = 236 - int(30 * i / panel_h)
        pygame.draw.line(bg, (10 + i // 18, 12 + i // 18, 18 + i // 14, a), (0, i), (panel_w, i))
    pygame.draw.rect(bg, (*color, 90), bg.get_rect(), 1, border_radius=8)
    pygame.draw.line(bg, (*color, 230), (10, 0), (panel_w - 10, 0), 2)
    msk = pygame.Surface((panel_w, panel_h), pygame.SRCALPHA)
    pygame.draw.rect(msk, (255, 255, 255, 255), msk.get_rect(), border_radius=8)
    bg.blit(msk, (0, 0), special_flags=pygame.BLEND_RGBA_MIN)
    drop = pygame.Surface((panel_w + 12, panel_h + 12), pygame.SRCALPHA)
    pygame.draw.rect(drop, (0, 0, 0, 110), drop.get_rect(), border_radius=12)
    surface.blit(drop, (px - 6, py + 2))
    surface.blit(bg, (px, py))

    tx = px + pad
    if not system:
        pr = pygame.Rect(px + pad, py + 12, port, port)
        surface.blit(_dialogue_portrait(speaker, color, port), pr.topleft)
        pygame.draw.rect(surface, color, pr, 2, border_radius=6)
        tx = pr.right + 16
        # Name tab.
        name = font_speaker.render(speaker, True, (14, 14, 18))
        tab = pygame.Rect(tx - 2, py - name.get_height() // 2 - 2, name.get_width() + 22,
                          name.get_height() + 6)
        pygame.draw.rect(surface, color, tab, border_radius=4)
        surface.blit(name, (tab.x + 11, tab.y + 3))
    y = py + (22 if not system else 18)
    for ln in lines:
        img = body.render(ln, True, (234, 236, 240) if not system else (200, 210, 220))
        lx = tx if not system else px + (panel_w - img.get_width()) // 2
        surface.blit(img, (lx, y))
        y += line_h
    if not typed and (t // 260) % 2 == 0:  # typing caret
        last = body.render(lines[-1], True, (0, 0, 0))
        lx = tx if not system else px + (panel_w + last.get_width()) // 2
        if not system:
            lx += last.get_width()
        pygame.draw.rect(surface, color, (lx + 2, y - line_h + 4, 8, line_h - 8))

    # Footer: progress pips + continue hint.
    n = max(1, len(dlg.get("beats", [])))
    idx = dlg.get("index", 0)
    fy = py + panel_h - 16
    for i in range(min(n, 24)):
        c = color if i <= idx else (60, 64, 74)
        pygame.draw.circle(surface, c, (tx + 4 + i * 11, fy), 3 if i != idx else 4)
    hint_col = (170, 176, 190) if typed else (90, 96, 108)
    hint = font_terminal_small.render(_T("draw.enter_e"), True, hint_col)
    hx = px + panel_w - hint.get_width() - pad - (18 if typed else 0)
    surface.blit(hint, (hx, fy - hint.get_height() // 2))
    if typed:
        bob = int(2 * math.sin(t * 0.008))
        ax, ay = px + panel_w - pad - 6, fy + bob
        pygame.draw.polygon(surface, color, [(ax - 6, ay - 4), (ax + 6, ay - 4), (ax, ay + 4)])


_PORTRAITS = {}
_PORTRAIT_WHO = {"MARU": "maru", "VASILE": "vasile", "BIRIBEL": "biribel",
                 "UCILEV": "ucilev", "GUARD": "krap"}


def _dialogue_portrait(speaker, color, size):
    # Biribel's portrait follows his M5 kit (Guard black collar, bare head);
    # the outfit is part of the key so a KRAP portrait can never leak through
    outfit = _outfits.gameplay_outfit(STATE) if "BIRIBEL" in speaker.upper() else None
    key = (speaker, size, color, outfit)
    if key in _PORTRAITS:
        return _PORTRAITS[key]
    out = pygame.Surface((size, size), pygame.SRCALPHA)
    for i in range(size):  # backdrop gradient tinted by the speaker colour
        k = i / size
        pygame.draw.line(out, (int(14 + color[0] * 0.18 * (1 - k)), int(16 + color[1] * 0.18 * (1 - k)),
                               int(24 + color[2] * 0.18 * (1 - k))), (0, i), (size, i))
    who = None
    up = speaker.upper()
    for k, v in _PORTRAIT_WHO.items():
        if k in up:
            who = v
            break
    try:
        from cutscenes import figure_kit  # lazy: cutscene module, heavy
        tmp = pygame.Surface((size * 4, size * 6), pygame.SRCALPHA)
        # fit the whole figure (~300 units tall) in the canvas: at a fixed 2.6x the
        # head was drawn above the surface and the crop landed on the chin
        figure_kit.draw_character(tmp, who or "civilian", size * 2, size * 6 - 8,
                                  (size * 6 - 24) / 300.0, True,
                                  wardrobe=_outfits.biribel_2d(outfit) if outfit else None)
        bb = tmp.get_bounding_rect()
        if bb.w > 4 and bb.h > 4:
            head_h = int(bb.h * 0.36)
            crop = pygame.Rect(0, bb.y, head_h, head_h)
            crop.centerx = bb.centerx
            crop = crop.clip(tmp.get_rect())
            face = pygame.transform.smoothscale(tmp.subsurface(crop), (size - 8, size - 8))
            out.blit(face, (4, 8))
    except Exception:
        initial = font_speaker.render(up[:1] or "?", True, color)
        out.blit(initial, ((size - initial.get_width()) // 2, (size - initial.get_height()) // 2))
    shade = pygame.Surface((size, size // 3), pygame.SRCALPHA)
    for i in range(size // 3):
        pygame.draw.line(shade, (0, 0, 0, int(150 * i / (size // 3))), (0, i), (size, i))
    out.blit(shade, (0, size - size // 3))
    _PORTRAITS[key] = out
    return out


def _draw_m5_mag_icon(surface, mx, my, kind, rounds, cap, is_active):
    """One magazine icon - stick mag (K-9 / OS-12, ribbed witness holes) or a
    tapered sidearm box mag. Ported from the M4 HUD (values local, m4 not
    imported) so the weapon panel reads identically across missions."""
    rounds = max(0, int(rounds))
    cap = max(1, int(cap))
    state = 0 if rounds <= 0 else (1 if is_active else 2)
    shell = _m5art("mag_icon", (0 if kind == "stick" else 3) + state)
    if shell is not None:                     # baked shell (src/game/art/m5/mag_icon.py)
        if kind == "stick":
            surface.blit(shell, (mx, my - 3))
            bx, bottom = mx + 5, my + 52
            filled = int(round(rounds / cap * 12))
            col = (220, 190, 70) if is_active else (150, 128, 58)
            for row_i in range(min(12, filled)):
                for wx_off in (5, 9):
                    pygame.draw.circle(surface, col, (bx + wx_off, bottom - 8 - row_i * 3), 1)
        else:
            surface.blit(shell, (mx, my))
            for bi in range(min(12, int(round(rounds / cap * 12)))):
                pygame.draw.circle(surface, (220, 185, 45), (mx + 12, my + 8 + bi * 3), 2)
        return
    if kind == "stick":
        mag_w, mag_h = 14, 52
        body = pygame.Rect(mx + 5, my, mag_w, mag_h)
        if rounds <= 0:
            base, rim, hi = (24, 28, 28), (52, 62, 58), (36, 42, 40)
        elif is_active:
            base, rim, hi = (36, 48, 44), (120, 230, 180), (70, 92, 84)
        else:
            base, rim, hi = (32, 38, 36), (86, 112, 102), (54, 66, 62)
        poly = [(body.x + 1, body.y), (body.right - 1, body.y + 1),
                (body.right - 3, body.bottom), (body.x + 3, body.bottom)]
        pygame.draw.polygon(surface, base, poly)
        pygame.draw.polygon(surface, rim if is_active else (64, 70, 66), poly, 1)
        pygame.draw.line(surface, hi, (body.x + 4, body.y + 4),
                         (body.x + 5, body.bottom - 5), 1)
        pygame.draw.rect(surface, (80, 86, 78),
                         (body.x + 2, body.y - 3, mag_w - 2, 4), border_radius=1)
        pygame.draw.rect(surface, (18, 20, 20),
                         (body.x + 1, body.bottom - 4, mag_w - 1, 5), border_radius=1)
        filled = int(round(rounds / cap * 12))
        for row_i in range(12):
            wy = body.bottom - 8 - row_i * 3
            on = row_i < filled
            for wx_off in (5, 9):
                col = ((220, 190, 70) if is_active else (150, 128, 58)) if on else (18, 20, 20)
                pygame.draw.circle(surface, col, (body.x + wx_off, wy), 1)
        if is_active:
            pygame.draw.line(surface, (120, 230, 180), (body.right + 3, body.y + 4),
                             (body.right + 3, body.bottom - 4), 2)
    else:
        top_w, bot_w, h = 24, 20, 46
        taper = (top_w - bot_w) // 2
        pts = [(mx, my), (mx + top_w, my),
               (mx + taper + bot_w, my + h), (mx + taper, my + h)]
        empty = rounds <= 0
        if empty:
            base, hl, rim = (45, 42, 38), (55, 52, 48), (55, 50, 45)
        elif is_active:
            base, hl, rim = (90, 86, 78), (115, 110, 100), (70, 66, 58)
        else:
            base, hl, rim = (72, 68, 62), (92, 88, 80), (60, 56, 50)
        pygame.draw.polygon(surface, base, pts)
        pygame.draw.polygon(surface, hl, [
            (mx + 1, my + 2), (mx + 5, my + 2),
            (mx + taper + 3, my + h - 3), (mx + taper + 1, my + h - 3)])
        pygame.draw.polygon(surface, C_TERMINAL if is_active else rim, pts, 1)
        gold = (220, 185, 45)
        dark = (55, 52, 48) if not empty else (40, 38, 35)
        fill = min(12, int(round(rounds / cap * 12)))
        for bi in range(12):
            pygame.draw.circle(surface, gold if bi < fill else dark,
                               (mx + top_w // 2, my + 8 + bi * 3), 2)


# Status-plate slot: the free top strip between the HOSTILES box (x 20-200)
# and the minimap (x >= ~830), above the objective banner (y ~90). Convoy
# (quarter) and raid clock (print works) never coexist, so they share it.
M5_PLATE_X, M5_PLATE_Y, M5_PLATE_W, M5_PLATE_H = 214, 16, 340, 46


def _plate_text(surface, x, y, w, title, title_col, pips, pips_max):
    """Live part of the status plate: title and the HEAT pips."""
    surface.blit(font_terminal_small.render(title, True, title_col), (x + 12, y + 6))
    if not pips_max:
        return
    lbl = font_terminal_small.render(_T("hud.heat"), True, (150, 160, 170))
    px0 = x + w - 12 - pips_max * 11
    surface.blit(lbl, (px0 - lbl.get_width() - 6, y + 6))
    for i in range(pips_max):
        r = pygame.Rect(px0 + i * 11, y + 9, 8, 10)
        pygame.draw.rect(surface, (44, 46, 52), r)
        f = max(0.0, min(1.0, pips - i))
        if f > 0:
            fh = max(1, int(round(r.h * f)))
            pygame.draw.rect(surface, (220, 70, 50) if f >= 1 else (200, 120, 60),
                             (r.x, r.bottom - fh, r.w, fh))
        pygame.draw.rect(surface, (110, 116, 126), r, 1)


def _draw_m5_plate(surface, title, title_col, frac, fill_col, right_text,
                   right_col=(220, 226, 236), pips=0, pips_max=0):
    """M4 hold-bar plate look (dark glass, steel rim, bar + right readout)."""
    x, y, w, h = M5_PLATE_X, M5_PLATE_Y, M5_PLATE_W, M5_PLATE_H
    frame = _m5art("plate", 0)
    if frame is not None and frame.get_size() == (w, h):  # baked frame (src/game/art/m5/plate.py)
        surface.blit(frame, (x, y))
    else:
        surface.blit(get_plate_bg(w, h), (x, y))
    _plate_text(surface, x, y, w, title, title_col, pips, pips_max)
    bx, by, bw, bh = x + 12, y + 28, w - 76, 10
    fw = int((bw - 2) * max(0.0, min(1.0, frac)))
    if fw > 0:
        pygame.draw.rect(surface, fill_col, (bx + 1, by + 1, fw, bh - 2))
    rt = font_terminal_small.render(right_text, True, right_col)
    surface.blit(rt, (x + w - 12 - rt.get_width(), y + 25))


def _draw_raid_timer(surface):
    if not (getattr(STATE, "mission5_stage", None) == STAGE_RAID
            and getattr(STATE, "m5_raid_active", False)):
        return
    total = int(M5_RAID_SECONDS * 60)
    left = max(0, total - getattr(STATE, "m5_raid_timer", 0))
    secs = left // 60
    frac = 1.0 - left / max(1, total)
    _draw_m5_plate(surface, _T("hud.raid_title"), (232, 196, 120), frac,
                   (220, 160, 40), _T("hud.clock", m=secs // 60, s="{:02d}".format(secs % 60)))


def _draw_hud(surface, cam_x, cam_y):
    """M5 gameplay HUD - same panel grammar as the M4 HUD (objective banner,
    pinned radio, HP strip, 84px magazine-icon weapon panel, HOSTILES box,
    minimap) plus one M5 status plate in the free top strip (convoy / raid).
    Drawn after vignette + scanlines so nothing here gets darkened."""
    draw_objective_panel(surface, _m5_maps._objective)
    draw_pinned_radio(surface)
    if not STATE.player:
        return

    # Phase 4: the duplicated M4/M5 panel bodies are engine.ui.std widgets now;
    # this HUD only gathers the data (hostiles count / minimap enemies differ).
    _hud_health_bar.draw(surface, THEME, STATE.player.hp, STATE.player.max_hp,
                         panel_bg=get_panel_bg)

    _hud_weapon_panel.draw(surface, THEME, _hud_weapon_panel.WeaponInfo.from_state(STATE),
                           panel_bg=get_panel_bg, mag_icon=_draw_m5_mag_icon)

    # ── Hostiles counter (same box + wording as M4) ──
    _hud_hostiles.draw(surface, THEME,
                       sum(e.hp > 0 and not _m5g(e).passive
                           for e in STATE.enemies))

    if STATE.show_minimap and STATE.minimap:
        STATE.minimap.draw(surface, STATE.player,
                           [e for e in STATE.enemies if e.hp > 0 and not _m5g(e).passive],
                           cam_x, cam_y,
                           notebook_pos=_objective_world_pos())

    # ── M5 status plate (one slot, never under the minimap) ──
    _m5_quarter.draw_hud(surface, _draw_m5_plate)
    _draw_raid_timer(surface)


# ─────────────────────────────────────────────
# Frame driver
# ─────────────────────────────────────────────
def _draw_fill(surface, cam_x, cam_y):
    surface.fill(C_BG_GAME)


def _draw_water(surface, cam_x, cam_y):
    actors = [STATE.player.rect.center] if STATE.player else []
    maru = getattr(STATE, "m5_maru", None)
    if maru:
        actors.append((maru["x"], maru["y"]))
    _m5_water.draw(surface, _grid(), cam_x, cam_y, _now_ms(),
                   actors, getattr(STATE, "reduced_motion", False))


def _submit_water(q, key):
    actors = [STATE.player.rect.center] if STATE.player else []
    maru = getattr(STATE, "m5_maru", None)
    if maru:
        actors.append((maru["x"], maru["y"]))
    for img, pos in _m5_water.render(tuple(q.viewport), _grid(), q.cam_x, q.cam_y, _now_ms(), actors,
                                     getattr(STATE, "reduced_motion", False)):
        q.submit(_SurfaceDraw(img, pos, space=_SCREEN), _L.DECALS_DYNAMIC, sort_key=key)


def _submit_blood_decals(q, key):
    """Blood decals as surface draws; the fade/removal bookkeeping stays in the draw path (submit time)."""
    for decal in STATE.blood_decals[:]:
        q.submit(_SurfaceDraw(get_blood_decal(decal[3]), (decal[0] - decal[3], decal[1] - decal[3]),
                              alpha=int(decal[2])), _L.DECALS_DYNAMIC, sort_key=key)
        decal[2] -= 0.25
        if decal[2] <= 0:
            STATE.blood_decals.remove(decal)


def _submit_beacon(q, key):
    pos = _objective_world_pos()
    if pos is None:
        return
    t = _now_ms() / 1000.0
    r = 18 + int(6 * (0.5 + 0.5 * math.sin(t * 3)))
    q.submit(_CircleDraw((pos[0], pos[1]), r, (220, 190, 70), 2), _L.DECALS_DYNAMIC, sort_key=key)


def _draw_pickups(surface, cam_x, cam_y):
    for pu in STATE.pickups:
        _draw_pickup(surface, pu, cam_x, cam_y)


def _submit_muzzle(q, key):
    if STATE.muzzle_flash_timer > 0 and STATE.player:
        if hasattr(STATE.player, "barrel_tip"):
            tx, ty = STATE.player.barrel_tip()
        else:
            tx = STATE.player.rect.centerx + math.cos(STATE.player.angle) * 39
            ty = STATE.player.rect.centery + math.sin(STATE.player.angle) * 39
        q.submit(_SurfaceDraw(MUZZLE_FLASH, (tx - 40, ty - 40)), _L.FX_WORLD, sort_key=key)
        STATE.muzzle_flash_timer -= 1


def _draw_bullets_fx(surface, cam_x, cam_y):
    draw_bullets(surface, STATE.bullets, cam_x, cam_y, with_glow=True)


def _draw_particles(surface, cam_x, cam_y):
    for p in STATE.particles:
        p.draw(surface, cam_x, cam_y)


def _draw_casings(surface, cam_x, cam_y):
    for c in STATE.casings:
        c.draw(surface, cam_x, cam_y)


def _draw_fire_zones(surface, cam_x, cam_y):
    for fz in getattr(STATE, "fire_zones", []):
        fz.draw(surface, cam_x, cam_y)


def _submit_floating_texts(q, key):
    for ft in STATE.floating_texts:
        if len(ft) >= 6 and ft[5] == "pin":
            continue
        q.submit(_TextDraw(ft[2], font_terminal_small, (ft[0], ft[1]), ft[3], anchor="midtop", space="world"),
                 _L.OVERLAY_WORLD, sort_key=key)


def _rain_items(drops):
    return _config.rain_drawables(drops)


def _submit_rain(q, key):
    """Rain as drawables. ``core.config.rain_drawables`` steps the drops and respawns them from
    the legacy rng stream exactly like ``draw_rain``; every other legacy-rng consumer of the
    frame (tram FX step, fire-zone wisps) now also runs at submit time, so the per-frame rng
    order is the authored one (B-032)."""
    if _is_quarter():
        drops = getattr(STATE, "rain_drops", None)
        if drops:
            # one pass over the drops: surface streaks batch into one queue item,
            # fallback line streaks (no rain art) stay individual - same blit order
            items = []
            for d in _rain_items(drops):
                if d.kind == "surface":
                    items.append((d.surface, d.pos))
                else:
                    if items:
                        q.submit(_SurfaceBatchDraw(items, space=_SCREEN), _L.UI, sort_key=key)
                        items = []
                    q.submit(d, _L.UI, sort_key=key)
            if items:
                q.submit(_SurfaceBatchDraw(items, space=_SCREEN), _L.UI, sort_key=key)


def _draw_rain(surface, cam_x, cam_y):
    if _is_quarter():
        drops = getattr(STATE, "rain_drops", None)
        if drops:
            _config.draw_rain(surface, drops)


def _draw_death_overlay(surface, cam_x, cam_y):
    if STATE.player_dead:
        from entities import death_anim
        death_anim.draw_death_overlay(surface, cam_x, cam_y)


def _submit_gc_flash(q, key):
    if STATE.gc_flash_timer > 0 and not getattr(STATE, "reduced_motion", False):
        q.submit(_OverlayDraw(get_fullscreen_overlay((255, 255, 255, 255)), alpha=min(255, STATE.gc_flash_timer * 22)),
                 _L.UI, sort_key=key)


def _submit_scanlines(q, key):
    # Honor the Graphics -> Scanlines toggle exactly like core.config.draw_scanlines.
    try:
        from core.user_settings import SETTINGS  # lazy: config <-> user_settings cycle
        if not SETTINGS.scanlines:
            return
    except Exception:
        pass
    q.submit(_OverlayDraw(_config.SCANLINES), _L.UI, sort_key=key)


def _draw_reticle_ui(surface):
    # Reticle in every playable stage, Guard HQ walk included (it used to be
    # skipped there, leaving the first section with no cursor at all).
    if (getattr(STATE, "mission5_stage", None) != STAGE_DONE
            and not getattr(STATE, "m5_dialogue_active", False)):
        draw_combat_reticle(surface)


def submit_frame(q, fcx, fcy):
    """RPE6 Phase 6: submit Mission 5's frame to the render queue.

    Authored z-order (module docstring) is kept exactly: every step sits on the
    layer that corresponds to its place in the legacy sequence and carries an
    explicit sort key, so the queue flushes in the same order the old
    ``_game_draw_inner``/``game_draw`` painted. Steps that still paint through a
    legacy painter are ``CustomDraw`` items (counted by ``tools/ae_d6_gate.py``);
    the Phase 6 peel-off replaces them one by one with real drawables.
    """
    cam_x, cam_y = int(round(fcx)), int(round(fcy))
    sub = q.submit
    C = _CustomDraw
    _m5_render.ensure_installed()      # RENDER_SUBMIT systems of this mission (idempotent)
    # ── floor / static decor ──────────────────────────────────────────────
    sub(_FillDraw(C_BG_GAME), _L.FLOOR, sort_key=-1)
    _submit_tiles(q, 0)
    _m5_decor.submit_under(q, 0)
    # ── dynamic decals ────────────────────────────────────────────────────
    if getattr(STATE, "mission5_stage", None) == STAGE_TUNNEL:
        _submit_water(q, 0)
    _submit_beacon(q, 1)
    _submit_blood_decals(q, 2)
    # ── entities (authored order, not y-sorted: ADR-017) ──────────────────
    for d in _adapt.corpse_drawables(corpse._corpses(), cam_x, cam_y):
        sub(d, _L.ENTITIES, sort_key=(0, 0))
    _submit_pickups(q, (1, 0))
    for d in _m5_quarter.world_drawables(cam_x, cam_y, q.viewport):
        sub(d, _L.ENTITIES, sort_key=(2, 0))
    # enemies: GuardRenderSystem (missions/m5/render.py) submits them at key (3, index) during RENDER_SUBMIT
    _submit_hq_npcs(q, (4, 0))
    _submit_maru(q, (5, 0))
    _submit_player(q, (6, 0))
    _submit_maru_mags(q, (7, 0))
    # ── world FX ──────────────────────────────────────────────────────────
    _submit_muzzle(q, 0)
    for d in _adapt.bullet_drawables(STATE.bullets, cam_x, cam_y, _bullet_glow, C_BULLET):
        sub(d, _L.FX_WORLD, sort_key=1)
    for d in _adapt.particle_drawables(STATE.particles, cam_x, cam_y):
        sub(d, _L.FX_WORLD, sort_key=2)
    for d in _adapt.casing_drawables(STATE.casings, cam_x, cam_y):
        sub(d, _L.FX_WORLD, sort_key=3)
    for fz in getattr(STATE, "fire_zones", None) or ():
        for d in fz.drawables(cam_x, cam_y):      # legacy-rng wisps: submit order == painter order (B-032)
            sub(d, _L.FX_WORLD, sort_key=4)
    # ── world overlays (texts, decor over, prompt) then the vignette ──────
    _submit_floating_texts(q, (0, 0))
    _m5_decor.submit_over(q, (1,))               # smoke, light map (engine.lighting), tram fire, sheen
    _m5_decor.submit_prompt(q, (2, 0))
    sub(_OverlayDraw(_config.VIGNETTE), _L.OVERLAY_WORLD, sort_key=(3, 0))  # authored: vignette over the world overlays
    # ── screen-space: weather, CRT, death, flash, HUD, dialogue, FPV, reticle ──
    _submit_rain(q, 0)
    _submit_scanlines(q, 1)
    if STATE.player_dead:
        from entities import death_anim  # lazy: as the painter did
        sub(_UiPassDraw(lambda s: death_anim.draw_death_overlay(s, cam_x, cam_y), "m5.death_overlay"), _L.UI,
            sort_key=2)
    _submit_gc_flash(q, 3)
    sub(_UiPassDraw(lambda s: _draw_hud(s, cam_x, cam_y), "m5.hud"), _L.UI, sort_key=4)
    sub(_UiPassDraw(_draw_dialogue, "m5.dialogue"), _L.UI, sort_key=5)
    if _m5_fpv.active():          # first-person look sits over everything, HUD included
        sub(_UiPassDraw(_m5_fpv.draw, "m5.fpv"), _L.UI, sort_key=6)
    else:
        sub(_UiPassDraw(_draw_reticle_ui, "m5.reticle"), _L.UI, sort_key=7)


def game_draw(fcx, fcy):
    """Paint one Mission 5 frame. Hosted by ``core.game_core.game_draw`` through the render
    queue; callable on its own (tools, smoke checks) - then it runs a whole queue frame itself."""
    if not _gr.installed():
        _gr.install(WIDTH, HEIGHT)
    if _gr.in_frame():                       # hosted: the frame is open, just submit
        submit_frame(_gr.queue(), fcx, fcy)
        return
    if not _gw.installed():
        _gw.install(STATE)
    _gr.frame(screen, fcx, fcy, submitter=submit_frame, name="m5.game_draw", submit_hook=_gw.render_submit)
