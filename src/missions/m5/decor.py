"""decor.py - Mission 5 set dressing, lighting and inspectables (round 2).

Draw-only layer over the tile grid; the runtime maps stay untouched, so
collision, MiniMap, A* and the smoke-test tiles all read the same grid.

    build_decor(stage)        after a world build: adds solid prop rects
    draw_under(s, cx, cy)     after tiles, before people (props, roofs)
    draw_over(s, cx, cy)      after people: night/indoor light + fire/smoke
    draw_prompt(s, cx, cy)    "[E] look" over the nearest inspectable
    inspect()                 E-key: first-person look (inspect_fpv) for the
                              nearest inspectable; radio line when headless
"""
import math
import random

import pygame

from core.config import (TILE_SIZE)
from core.state import STATE

from missions.m5 import maps as _m5_maps  # live MISSION5_MAP owner
from missions.m5.meta import (STAGE_HQ, STAGE_QUARTER, STAGE_PRINTWORKS, STAGE_RAID,
                              STAGE_TUNNEL, C_SYSTEM, C_VASILE)
from missions.m5 import decor_paint as _paint
from missions.m5 import decor_interior as _interior
from missions.m5 import tram_wreck as _tram
from missions.m5 import inspect_fpv as _fpv
from engine.core import now_ms as _now_ms  # RPE6 B-001 timebase
import engine.lighting as _lighting  # RPE6 Phase 6: lamp falloff / bloom sprites + LightMapDraw
from engine.render2d import SCREEN as _SCREEN, Layer as _Layer, SurfaceDraw as _SurfaceDraw  # RPE6 Phase 6

T = TILE_SIZE
_layers = {}     # stage -> world-size static prop surface
_glows = {}      # (radius, colour) -> additive glow sprite
_holes = {}      # radius -> alpha-sub light hole
_seen = set()    # inspectables already read this run
_SMOKE = []      # live smoke puffs [x, y, r, alpha, vx]

# Inspectables: stage, world pos, radio text (headless fallback), colour,
# inspect_fpv shot key.
INSPECTABLES = [
    (STAGE_HQ, (int(16.8 * T), 10 * T + 34),
     "NOTICE BOARD: 'KRAP SQUAD 4 - TRANSFERRED.' Every name on the list has a red line "
     "through it. Yours is still there. For now.", C_SYSTEM, "notice"),
    (STAGE_HQ, (int(3.2 * T), 14 * T + 30),
     "TV: '...the Republican Guard thanks KRAP for its years of service. Patriots will be "
     "welcomed into the new structure...' Somebody turned the volume down.", C_SYSTEM, "hq_tv"),
    (STAGE_HQ, (int(17.4 * T), 12 * T + 20),
     "PORTRAIT: Retardovici, new frame, old smile. The nail holes underneath are where "
     "the KRAP crest used to hang.", C_SYSTEM, "portrait"),
    (STAGE_HQ, (int(18.3 * T), 11 * T + 20),
     "PAINT TINS: 'GUARD BLACK - 40 LITRES.' They ordered enough for the whole building.",
     C_SYSTEM, "paint"),
    (STAGE_QUARTER, (17 * T, int(13.4 * T)),
     "SHOP TV: '...curfew in the Lower Quarter is for your protection. MAG publications "
     "are now classified as foreign agitation...' The shopkeeper pulled the shutter halfway.",
     C_SYSTEM, "shop_tv"),
    (STAGE_QUARTER, (int(24 * T), int(16.2 * T)),
     "THE TRAM: still warm. Somebody wrote 'PROVOCATEURS' on the side in Guard paint. "
     "Nobody was on it when it burned. Probably.", C_SYSTEM, "tram"),
]

# Lights per stage: (x, y, radius, colour, flicker-kind)
_HQ_LIGHTS = (
    [(int((2 + i * 2.2) * T), int(11.6 * T), 150, (236, 236, 226), "") for i in range(3)]
    + [(int(c * T), int(11.5 * T), 130, (236, 236, 226), "bad" if c == 19.5 else "")
       for c in (10.5, 13.5, 16.5, 19.5, 22.5)]
    + [(int(14.5 * T), int(4.6 * T), 230, (210, 225, 255), ""),
       (int(23.8 * T), int(4.8 * T), 200, (255, 214, 160), ""),
       (int(25.8 * T), int(11.8 * T), 150, (255, 230, 190), "")]
)
_Q_LIGHTS = (
    [(c * T + 32, 13 * T + 36, 170, (255, 176, 92), "") for c in range(6, 33, 5)]
    + [(c * T + 8, 18 * T - 36, 170, (255, 176, 92), "bad" if c == 21 else "")
       for c in range(6, 33, 5)]
    + [(int(25.5 * T), int(14.45 * T), 300, (196, 88, 32), "fire"),
       (int(32.7 * T), int(13.45 * T), 150, (255, 90, 80), ""),        # blade sign
       (int(33.4 * T), int(15.5 * T), 120, (255, 200, 130), ""),       # door lamp
       (int(2 * T), int(15 * T), 200, (220, 230, 255), "")]            # depot yard
    + [(int(36.5 * T), r * T + 32, 120, (255, 200, 120), "") for r in (11, 14, 17)]
)
_DARK = {STAGE_HQ: 70, STAGE_QUARTER: 150, STAGE_PRINTWORKS: 110, STAGE_RAID: 125,
         STAGE_TUNNEL: 140}
# night-blue outside, warm sodium-brown indoors (blue indoors read as 'cold grey')
_TINT = {STAGE_HQ: (9, 10, 14), STAGE_PRINTWORKS: (14, 10, 6), STAGE_RAID: (14, 8, 8),
         STAGE_TUNNEL: (8, 10, 10)}
_STAGE_LIGHTS = {STAGE_HQ: _HQ_LIGHTS, STAGE_QUARTER: _Q_LIGHTS,
                 STAGE_PRINTWORKS: _interior.PRINT_LIGHTS, STAGE_RAID: _interior.RAID_LIGHTS,
                 STAGE_TUNNEL: _interior.TUNNEL_LIGHTS}


def _stage():
    return getattr(STATE, "mission5_stage", None)


def reset_run():
    _seen.clear()
    _fpv.reset()
    _SMOKE.clear()
    _tram.reset()


def build_decor(stage):
    rects = (_paint.HQ_SOLIDS if stage == STAGE_HQ
             else _paint.Q_SOLIDS if stage == STAGE_QUARTER else ())
    for r in rects:
        STATE.walls.append(pygame.Rect(r))
    _SMOKE.clear()


def _layer(stage):
    if stage in _layers:
        return _layers[stage]
    if stage not in _DARK:
        return None
    grid = getattr(_m5_maps, "MISSION5_MAP", None) or []
    w = max((len(r) for r in grid), default=40) * T
    h = max(len(grid), 1) * T
    surf = pygame.Surface((w, h), pygame.SRCALPHA)
    if stage == STAGE_HQ:
        _interior._floors(surf, grid, office=(20, 2, 8, 6))
        _paint.paint_hq(surf)
    elif stage == STAGE_QUARTER:
        _paint.paint_quarter(surf)
    elif stage in (STAGE_PRINTWORKS, STAGE_RAID):
        _interior.paint_print(surf, alarm=stage == STAGE_RAID, grid=grid)
    elif stage == STAGE_TUNNEL:
        _interior.paint_tunnel(surf, grid=grid)
    else:
        return None
    _layers[stage] = surf
    return surf


def draw_under(surface, cam_x, cam_y):
    st = _stage()
    if st not in _DARK:
        return
    layer = _layer(st)
    if layer is not None:
        sw, sh = surface.get_size()
        surface.blit(layer, (0, 0), pygame.Rect(cam_x, cam_y, sw, sh))
    if st == STAGE_QUARTER:
        _draw_tram_fire(surface, cam_x, cam_y)


# ── live FX ──
# Multiplicative light map: scene * (ambient + sum of lamp falloffs). Keeps the
# painted colours saturated inside pools and lets the gaps go properly dark,
# instead of the old grey alpha wash with banded 'target ring' holes.
_AMBIENT = {STAGE_HQ: (176, 178, 186), STAGE_QUARTER: (50, 58, 94),
            STAGE_PRINTWORKS: (124, 106, 90), STAGE_RAID: (112, 76, 76),
            STAGE_TUNNEL: (86, 84, 88)}
_LIGHT_REACH = 1.05          # lamp radius in the table -> falloff radius


def _torch_col(st):
    """The player's torch, white-balanced against a blue-dominant ambient so
    the light ON the player is neutral: black cloth stays black instead of
    multiplying into navy (Quarter night). Warm/neutral interiors keep the
    plain torch and their mood."""
    base = (76, 76, 72)
    amb = _AMBIENT.get(st, (40, 48, 78))
    if amb[2] <= amb[0]:
        return base
    top = max(amb)
    return tuple(min(255, b + (top - a) // 2) for b, a in zip(base, amb))


def _light(radius, col):
    """Smooth falloff lamp pool - the body moved verbatim to ``engine.lighting.falloff_sprite``
    (RPE6 Phase 6); the cache lives there too."""
    return _lighting.falloff_sprite(radius, col)


def _glow(radius, col):
    """Faint additive bloom around the bulb itself (``engine.lighting.bloom_sprite``)."""
    return _lighting.bloom_sprite(radius, col)


def _hole(radius):
    if radius not in _holes:
        g = pygame.Surface((radius * 2, radius * 2), pygame.SRCALPHA)
        for f, a in ((1.0, 60), (0.8, 120), (0.6, 180), (0.4, 235)):   # hard light bands
            pygame.draw.circle(g, (0, 0, 0, a), (radius, radius), max(2, int(radius * f)))
        _holes[radius] = g
    return _holes[radius]


def _flicker(kind, i):
    t = _now_ms()
    if kind == "fire":
        return 0.8 + 0.2 * math.sin(t * 0.017 + i) * math.sin(t * 0.031)
    if kind == "bad":
        return 0.15 if (t // 90) % 23 in (0, 3, 4, 11) else 1.0
    if kind in ("sirenA", "sirenB"):
        on = (t // 260) % 2 == (0 if kind == "sirenA" else 1)
        return 1.0 if on else 0.0
    return 1.0


def _draw_tram_fire(s, cam_x, cam_y):
    """Steps the tram wreck FX + the Print Works chimney smoke (drawn later)."""
    _tram.update()
    t = _now_ms()
    if (t // 16) % 3 == 0 and len(_SMOKE) < 30:
        _SMOKE.append([37.85 * T, 9.8 * T, 8, 90, 0.7])
    for p in _SMOKE[:]:
        p[0] += p[4]
        p[1] -= 0.8
        p[2] += 0.25
        p[3] -= 0.9
        if p[3] <= 0:
            _SMOKE.remove(p)

def _draw_smoke(s, cam_x, cam_y):
    for d in _smoke_drawables(cam_x, cam_y):
        d.draw(s, 0, 0)


def _light_pass(st, cam_x, cam_y, size):
    """Sample lamps/flicker/torch for this frame -> ``LightMapDraw`` (map stored at half scale
    and doubled after the multiply -> lamps can push the painted floor up to 2x its colour)."""
    sw, sh = size
    lights = _STAGE_LIGHTS[st]
    lamps, blooms = [], []
    for i, (x, y, r, col, kind) in enumerate(lights):
        R = int(r * _LIGHT_REACH)
        sx, sy = x - cam_x, y - cam_y
        if -R < sx < sw + R and -R < sy < sh + R:
            if _flicker(kind, i) > 0.5:
                if kind != "fire":                  # the tram draws its own flames
                    gr = max(24, r // 3)            # bulb bloom on top
                    blooms.append((_glow(gr, col), (sx - gr, sy - gr)))
                lamps.append((_light(R, col), (sx - R, sy - R)))
    # the player's own low torch so the dark never hides threats
    if STATE.player is not None:
        px, py = STATE.player.rect.centerx - cam_x, STATE.player.rect.centery - cam_y
        lamps.append((_light(180, _torch_col(st)), (px - 180, py - 180)))
    return _lighting.LightMapDraw(_AMBIENT.get(st, (40, 48, 78)), lamps, blooms)


def draw_over(surface, cam_x, cam_y):
    st = _stage()
    if st not in _DARK:
        return
    if st == STAGE_QUARTER:
        _draw_smoke(surface, cam_x, cam_y)
        _tram.draw_smoke(surface, cam_x, cam_y)
    _light_pass(st, cam_x, cam_y, surface.get_size()).draw(surface, 0, 0)
    if st == STAGE_QUARTER:
        _tram.draw_fire(surface, cam_x, cam_y)       # emissive: after the light multiply
        _draw_rain_sheen(surface)


def _smoke_drawables(cam_x, cam_y):
    for x, y, r, a, _vx in _SMOKE:
        r = int(r)
        r = max(4, r)
        a = max(0, min(255, int(a)))
        puff = pygame.Surface((r * 2, r * 2), pygame.SRCALPHA)   # soft layered puff
        pygame.draw.circle(puff, (34, 32, 32, a * 2 // 5), (r, r), r)
        pygame.draw.circle(puff, (44, 42, 42, a * 3 // 5), (r - r // 5, r - r // 5), r * 2 // 3)
        pygame.draw.circle(puff, (58, 54, 52, a * 2 // 3), (r - r // 3, r - r // 3), r // 3)
        yield _SurfaceDraw(puff, (int(x - r - cam_x), int(y - r - cam_y)), space=_SCREEN)


def _sheen_drawables(size):
    from engine.render2d import LineDraw as _LineDraw  # lazy: only the quarter uses it
    t = _now_ms()
    rnd = random.Random(t // 40)
    for _ in range(26):
        x, y = rnd.randint(0, size[0]), rnd.randint(0, size[1])
        yield _LineDraw([(x, y), (x - 3, y + 12)], (120, 140, 170), 1, space=_SCREEN)


def submit_under(q, key, layer=_Layer.DECOR_STATIC):
    """Queue twin of ``draw_under``: the painted stage layer (viewport cut) + the tram/smoke step."""
    st = _stage()
    if st not in _DARK:
        return
    layer_surf = _layer(st)
    if layer_surf is not None:
        sw, sh = q.viewport
        q.submit(_SurfaceDraw(layer_surf, (0, 0), area=pygame.Rect(q.cam_x, q.cam_y, sw, sh), space=_SCREEN),
                 layer, sort_key=key)
    if st == STAGE_QUARTER:
        _draw_tram_fire(None, q.cam_x, q.cam_y)      # FX step (no pixels); same order as the painter


def submit_over(q, key, layer=_Layer.OVERLAY_WORLD):
    """Queue twin of ``draw_over``: smoke, the light map, emissive tram fire, rain sheen.
    ``key`` is a prefix; the steps take ``key + (n,)`` so the authored sequence survives sorting."""
    st = _stage()
    if st not in _DARK:
        return
    cam_x, cam_y = q.cam_x, q.cam_y
    size = tuple(q.viewport)
    k = tuple(key) if isinstance(key, tuple) else (key,)
    if st == STAGE_QUARTER:
        for d in _smoke_drawables(cam_x, cam_y):
            q.submit(d, layer, sort_key=k + (0,))
        for d in _tram.smoke_drawables(cam_x, cam_y, size):
            q.submit(d, layer, sort_key=k + (1,))
    q.submit(_light_pass(st, cam_x, cam_y, size), layer, sort_key=k + (2,))
    if st == STAGE_QUARTER:
        for d in _tram.fire_drawables(cam_x, cam_y, size):
            q.submit(d, layer, sort_key=k + (3,))
        for d in _sheen_drawables(size):
            q.submit(d, layer, sort_key=k + (4,))


def _draw_rain_sheen(s):
    for d in _sheen_drawables(s.get_size()):
        d.draw(s, 0, 0)


# ── inspectables ──
def nearest_inspectable(radius=70):
    if STATE.player is None:
        return None
    st = _stage()
    px, py = STATE.player.rect.center
    best, bd = None, radius * radius
    for i, item in enumerate(INSPECTABLES):
        if item[0] != st:
            continue
        d = (item[1][0] - px) ** 2 + (item[1][1] - py) ** 2
        if d < bd:
            best, bd = i, d
    return best


def inspect():
    """Returns True if an inspectable consumed the E press."""
    i = nearest_inspectable()
    if i is None:
        return False
    _stage_, _pos, txt, col, key = INSPECTABLES[i]
    _seen.add(i)
    if _fpv.can_play(key):          # look at it; game_update freezes meanwhile
        _fpv.start(key)
        return True
    from missions.m5.world import _radio  # lazy: world imports nothing from decor
    _radio(txt, color=col, duration=420)
    return True


def draw_prompt(surface, cam_x, cam_y):
    if getattr(STATE, "m5_dialogue_active", False) or _fpv.active():
        return
    i = nearest_inspectable()
    if i is None:
        return
    for img, pos in _prompt_parts(i, cam_x, cam_y, surface.get_size()):
        surface.blit(img, pos)


def _prompt_parts(i, cam_x, cam_y, size):
    from engine.text import T as _T              # lazy: engine.text facade
    from engine.ui import prompt as _hud_prompt  # lazy: engine.ui facade
    x, y = INSPECTABLES[i][1]
    label = _T("m5.look") if i not in _seen else _T("m5.look_again")
    # Phase 4: the body is engine.ui.std.prompt (chrome knobs = M5's look,
    # clamp off: M5 never clamped the tag; sy carries the -3 plate offset).
    return _hud_prompt.build(size, x - cam_x, y - cam_y - 3, label, (240, 230, 200),
                             y_off=-46, font=_paint.font(13), fill=(10, 12, 18, 200),
                             rim=(200, 170, 90, 220), radius=5, pad=(6, 3),
                             clamp=False)


def submit_prompt(q, key, layer=_Layer.OVERLAY_WORLD):
    """Queue twin of ``draw_prompt``."""
    if getattr(STATE, "m5_dialogue_active", False) or _fpv.active():
        return
    i = nearest_inspectable()
    if i is None:
        return
    for img, pos in _prompt_parts(i, q.cam_x, q.cam_y, tuple(q.viewport)):
        q.submit(_SurfaceDraw(img, pos, space=_SCREEN), layer, sort_key=key)
