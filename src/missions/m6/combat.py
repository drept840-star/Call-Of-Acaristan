"""Mission 6 - loud combat arenas for the three top-down stages.

Each stage opens with a squad dug in behind cover (the map's ``E`` tiles),
then ``meta.ARENA_WAVES`` feeds scripted waves in: a wave comes when the
living count drops to its threshold, or ``after`` seconds into a loud fight.
Fuel drums (``meta.ARENA_DRUMS``) and the customs tanker blow up when shot
and chain into each other.  The exit opens only when ``cleared()``.

State is module-owned and rebuilt on every ``init_stage`` so a checkpoint
reload or stage retry always starts the arena fresh.
"""
import math
import random

import pygame

from core.config import TILE_SIZE, WIDTH, HEIGHT
from core.state import STATE
from core import artpack
from fx import effects

from .meta import (
    STAGE_CUSTOMS, STAGE_NOMAN, STAGE_RAIL, ARENA_WAVES, ARENA_DRUMS,
    ARENA_MAX_LIVING, M6_ROLE_TUNING,
)

T = TILE_SIZE
DRUM_SIZE = 28
DRUM_RADIUS = 120
TANKER_RADIUS = 230
TANKER_HITS = 6
TANKER_RECT = (23, 12, 5, 3)         # customs tiles, matches the map footprint
CHAIN_DELAY = 0.16

# The burning pool a drum leaves behind is NOT the M2 molotov patch: a drum
# is 30 litres of fuel going up, so it burns wide, hot and briefly, and the
# tanker (a road tanker) burns much wider.  (radius px, life frames, damage
# tick: near / far)
DRUM_FIRE = (96, 210, (26, 13))
TANKER_FIRE = (150, 300, (30, 15))
TANKER_RING = 5          # satellite pools flung around a tanker blast

_stage = None
_waves = ()
_next = 0
_clock = 0.0
_loud = False
_drums = []
_tanker = None
_pending = []           # [delay_s, x, y, radius, power]
_scorch = []            # (x, y, radius, big)
_events = set()
_t = 0.0
_peak = 0               # most hostiles seen at once: the plate's bar is 1 - left/peak


def init_stage(stage):
    """Bind the arena: waves, drums (solid rects in STATE.walls), tanker."""
    global _stage, _waves, _next, _clock, _loud, _tanker, _t, _peak
    _stage = stage
    _peak = 0
    _waves = ARENA_WAVES.get(stage, ())
    _next = 0
    _clock = 0.0
    _loud = False
    _t = 0.0
    _pending.clear()
    _scorch.clear()
    _events.clear()
    _drums.clear()
    for c, r in ARENA_DRUMS.get(stage, ()):
        x, y = c * T + T // 2, r * T + T // 2
        rect = pygame.Rect(0, 0, DRUM_SIZE, DRUM_SIZE)
        rect.center = (x, y)
        _drums.append({"x": x, "y": y, "rect": rect, "alive": True})
        if hasattr(STATE, "walls"):
            STATE.walls.append(rect)
    _tanker = None
    if stage == STAGE_CUSTOMS:
        c, r, w, h = TANKER_RECT
        _tanker = {"rect": pygame.Rect(c * T, r * T, w * T, h * T),
                   "hits": TANKER_HITS, "alive": True, "flash": 0.0}


def stage():
    return _stage


def loud():
    return _loud


def go_loud():
    """The fight starts: every Guard converges and the wave clock runs."""
    global _loud, _clock
    if _loud or not _waves:
        _loud = True
        return
    _loud = True
    _clock = 0.0
    from . import world as _world
    _world._arm_everyone()


def wave_progress():
    """(waves spawned, waves total)."""
    return _next, len(_waves)


def remaining():
    """Living Guards plus every unit still to come."""
    from . import world as _world
    left = sum(len(w["units"]) for w in _waves[_next:])
    return _world.living_guards() + left


def cleared():
    return remaining() <= 0


def spend_waves():
    """Test helper: mark every wave as already fought."""
    global _next
    _next = len(_waves)


def drums():
    return [d for d in _drums if d["alive"]]


def events():
    return frozenset(_events)


# ─────────────────────────────────────────────
# Waves
# ─────────────────────────────────────────────
def _player_pos():
    p = getattr(STATE, "player", None)
    if p is None:
        return (0.0, 0.0)
    return float(p.rect.centerx), float(p.rect.centery)


def apply_role(enemy, kind):
    """Give a Guard his role: tuning plus the M5 sprite variant."""
    tune = M6_ROLE_TUNING.get(kind, M6_ROLE_TUNING["guard"])
    enemy.hp = tune["hp"]
    enemy.speed = tune["speed"]
    try:
        import game.world as _gw
        from missions.m5.components import M5Guard
        g = _gw.ensure(enemy, M5Guard)
        g.guard = True
        g.kind = "" if kind == "guard" else kind
    except Exception:
        pass
    return enemy


def _spawn_wave(wave):
    from . import world as _world
    px, py = _player_pos()
    units = list(wave["units"])
    tiles = [(c, r) for _k, c, r in units]
    far = max(tiles, key=lambda t: math.hypot(t[0] * T - px, t[1] * T - py))
    for i, (kind, c, r) in enumerate(units):
        x, y = c * T + T // 2, r * T + T // 2
        if math.hypot(x - px, y - py) < 200:
            # Never drop boots on top of Biribel: reuse the far tile.
            x = far[0] * T + T // 2 + (i % 3 - 1) * 22
            y = far[1] * T + T // 2
            c, r = far
        e = _world._spawn_guard(x, y, _stage, tile=(c, r), aware=True, entry=True)
        apply_role(e, kind)
        try:
            effects.burst(x, y, (198, 212, 228), 10, speed_mul=0.7)
        except Exception:
            pass
    STATE.m6_wave_count = int(getattr(STATE, "m6_wave_count", 0)) + len(units)
    if wave.get("event"):
        _events.add(wave["event"])
    who, line = wave.get("radio", (None, None))
    if line:
        _world.radio("%s: %s" % (who, line), color=(222, 150, 96), duration=360,
                     mark="m6_wave_%s_%d" % (_stage, _next), priority=1)
    _world.sfx("door_break", 0.35)


def _update_waves(dt):
    global _next, _clock
    from . import world as _world
    if _next >= len(_waves):
        return
    if _loud:
        _clock += dt
    wave = _waves[_next]
    living = _world.living_guards()
    room = living + len(wave["units"]) <= ARENA_MAX_LIVING
    if living <= wave["living"] or (_loud and _clock >= wave["after"] and room):
        _spawn_wave(wave)
        _next += 1
        _clock = 0.0
        go_loud()


def _check_loud():
    if _loud:
        return
    if any(b.get("owner") == "player" for b in getattr(STATE, "bullets", [])):
        go_loud()
        return
    for e in getattr(STATE, "enemies", []):
        if getattr(e, "hp", 0) > 0 and getattr(e, "alerted", False):
            go_loud()
            return


# ─────────────────────────────────────────────
# Drums / tanker
# ─────────────────────────────────────────────
def bullet_hit(bullet):
    """Consume a bullet that hit a drum or the tanker.  True when consumed."""
    x, y = bullet.get("x", 0), bullet.get("y", 0)
    for d in _drums:
        if d["alive"] and d["rect"].inflate(6, 6).collidepoint(x, y):
            _detonate_drum(d, 0.0)
            return True
    if (_tanker and _tanker["alive"] and bullet.get("owner") == "player"
            and _tanker["rect"].collidepoint(x, y)):
        _tanker["hits"] -= 1
        _tanker["flash"] = 0.08
        effects.burst(x, y, (255, 214, 140), 6, speed_mul=0.8)
        if _tanker["hits"] <= 0:
            _tanker["alive"] = False
            cx, cy = _tanker["rect"].center
            _pending.append([0.0, cx, cy, TANKER_RADIUS, 2.2])
            from . import world as _world
            _world.radio("MARU: The tanker! Get down!", color=(222, 120, 92),
                         duration=260, mark="m6_tanker", priority=1)
        return True
    return False


def _detonate_drum(d, delay):
    if not d["alive"]:
        return
    d["alive"] = False
    try:
        STATE.walls.remove(d["rect"])
    except (AttributeError, ValueError):
        pass
    _pending.append([delay, d["x"], d["y"], DRUM_RADIUS, 1.0])


def _explode(x, y, radius, power):
    from entities.weapons import FireZone
    for e in getattr(STATE, "enemies", []):
        if e.hp <= 0:
            continue
        dist = math.hypot(e.rect.centerx - x, e.rect.centery - y)
        if dist < radius:
            e.hp -= (160 * (1.0 - dist / radius) + 40) * power
            e.alerted = True
            try:
                e.on_hit(x, y)
            except Exception:
                pass
    p = getattr(STATE, "player", None)
    if p is not None and not getattr(STATE, "player_dead", False):
        dist = math.hypot(p.rect.centerx - x, p.rect.centery - y)
        if dist < radius:
            p.take_damage(int((55 * (1.0 - dist / radius) + 10) * min(power, 1.4)))
    for d in _drums:
        if d["alive"] and math.hypot(d["x"] - x, d["y"] - y) < radius * 0.9:
            _detonate_drum(d, CHAIN_DELAY)
    fires = getattr(STATE, "fire_zones", None)
    if fires is not None:
        radius_f, life_f, dmg_f = TANKER_FIRE if power > 1.5 else DRUM_FIRE
        fires.append(FireZone(x, y, radius=radius_f, life=life_f, damage=dmg_f,
                              outline=False))
        if power > 1.5:
            # Fuel thrown clear: pools around the tanker, sized off its own
            # fire rather than M2's molotov spread, and nudged off the
            # cardinal axes so it reads as a splash and not a plus sign.
            step = radius_f * 0.62
            for a in range(TANKER_RING):
                ang = a * (math.pi * 2 / TANKER_RING) + 0.4
                fires.append(FireZone(
                    x + math.cos(ang) * step, y + math.sin(ang) * step * 0.72,
                    radius=int(radius_f * 0.5), life=int(life_f * 0.62),
                    damage=dmg_f, outline=False))
    _scorch.append((x, y, radius, power > 1.5))
    effects.shake(14 if power > 1.5 else 8)
    effects.burst(x, y, (255, 168, 72), 26 if power > 1.5 else 16, speed_mul=1.6)
    effects.burst(x, y, (60, 56, 52), 12, speed_mul=0.9)
    try:
        from core import config as _config
        _config.audio.play_3d("explosion", (x, y), _player_pos(),
                              base_volume=0.9 if power > 1.5 else 0.6)
    except Exception:
        pass
    go_loud()


def _update_blasts(dt):
    if _tanker and _tanker["flash"] > 0:
        _tanker["flash"] = max(0.0, _tanker["flash"] - dt)
    if not _pending:
        return
    due = []
    for item in _pending:
        item[0] -= dt
        if item[0] <= 0:
            due.append(item)
    for item in due:
        _pending.remove(item)
        _explode(item[1], item[2], item[3], item[4])


def update(dt):
    global _t
    if getattr(STATE, "mission6_stage", None) != _stage or not _stage:
        return
    dt = max(0.0, float(dt))
    _t += dt
    _update_blasts(dt)
    _check_loud()
    _update_waves(dt)


# ─────────────────────────────────────────────
# Rendering
# ─────────────────────────────────────────────
_DRUM_ART = {}


def _drum_surface(charred=False):
    key = "charred" if charred else "fuel"
    if key in _DRUM_ART:
        return _DRUM_ART[key]
    surf = artpack.prop("barrel_charred" if charred else "barrel")
    if surf is not None and not charred:
        surf = surf.copy()
        tint = pygame.Surface(surf.get_size(), pygame.SRCALPHA)
        tint.fill((255, 118, 92, 255))
        surf.blit(tint, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
        # Hazard band, only on the drum's own pixels.
        w, h = surf.get_size()
        y0 = h // 2 - 2
        for y in range(y0, y0 + 5):
            for x in range(w):
                if surf.get_at((x, y)).a > 160:
                    stripe = ((x + y) // 3) % 2 == 0
                    surf.set_at((x, y), (230, 196, 64) if stripe else (28, 24, 20))
    if surf is None:
        surf = pygame.Surface((30, 36), pygame.SRCALPHA)
        body = (60, 52, 46) if charred else (168, 52, 40)
        pygame.draw.rect(surf, (14, 12, 12), (1, 3, 28, 32))
        pygame.draw.rect(surf, body, (2, 4, 26, 30))
        pygame.draw.ellipse(surf, (14, 12, 12), (1, 0, 28, 10))
        pygame.draw.ellipse(surf, (90, 34, 28) if not charred else (40, 36, 34), (2, 1, 26, 8))
        if not charred:
            pygame.draw.rect(surf, (230, 196, 64), (2, 17, 26, 5))
    _DRUM_ART[key] = surf
    return surf


def drawables(cam_x, cam_y):
    """(sort_y, draw) pairs for live drums and drum stubs."""
    out = []
    for d in _drums:
        sx, sy = d["x"] - cam_x, d["y"] - cam_y
        if not (-50 < sx < WIDTH + 50 and -60 < sy < HEIGHT + 60):
            continue
        img = _drum_surface(not d["alive"])
        w, h = img.get_size()
        pos = (int(sx - w // 2), int(sy + DRUM_SIZE // 2 - h))
        out.append((d["y"] + DRUM_SIZE // 2,
                    lambda s, i=img, p=pos: s.blit(i, p)))
    if _tanker:
        out.append(_tanker_drawable(cam_x, cam_y))
    return out


def _tanker_drawable(cam_x, cam_y):
    """The yard fuel tank, painted by ``decor`` (M6's own art, not M2's)."""
    r = _tanker["rect"]
    from . import decor as _decor
    img = _decor.fuel_tank_surface(r.w, r.h, alive=_tanker["alive"])
    flash = _tanker["flash"] > 0

    def draw(s):
        pos = (int(r.centerx - cam_x - img.get_width() // 2),
               int(r.bottom - cam_y - img.get_height()))
        s.blit(img, pos)
        if flash:
            s.blit(img, pos, special_flags=pygame.BLEND_RGB_ADD)
    return (r.bottom, draw)


_SCORCH_CACHE = {}


_MASK = {}


def _radial_mask(size):
    """Soft oval alpha falloff, cached per size."""
    mask = _MASK.get(size)
    if mask is not None:
        return mask
    w, h = size
    mask = pygame.Surface(size, pygame.SRCALPHA)
    cx, cy = w / 2.0, h / 2.0
    steps = 18
    for i in range(steps, 0, -1):
        k = i / float(steps)
        a = int(255 * (k ** 2.6))
        rect = pygame.Rect(0, 0, int(w * k), int(h * k))
        rect.center = (int(cx), int(cy))
        pygame.draw.ellipse(mask, (255, 255, 255, a), rect)
    _MASK[size] = mask
    return mask


SCORCH_SPAN = 2.4        # scorch width, in blast radii


def _scorch_surface(radius, big):
    """Burnt ground sized off the blast, not off the art it was cut from.

    ``artpack.fx("scorch")`` is a full-screen M2 decal (1458 px, a dark oval
    with its own rim).  Stamped at 1x under a drum whose damaging radius is
    120 px it drew a burn four screen-widths across - which is what made a
    drum going up read as an M2 molotov, not an M6 blast.  A drum's burn is
    now drawn procedural at the blast radius: an irregular, feathered patch
    with grit around it, in the same flat language as the rest of M6.
    """
    key = (int(radius) // 8, big)
    img = _SCORCH_CACHE.get(key)
    if img is not None:
        return img
    span = max(48, int(radius * SCORCH_SPAN) // 8 * 8)
    h = max(24, int(span * 0.62))
    ss = 2                                   # build big, shrink once: soft edge
    surf = pygame.Surface((span * ss, h * ss), pygame.SRCALPHA)
    rng = random.Random((int(radius) * 31) ^ (1 if big else 0))
    cx, cy = surf.get_width() / 2.0, surf.get_height() / 2.0
    rx, ry = surf.get_width() * 0.46, surf.get_height() * 0.44

    def blob(k):
        pts = []
        for i in range(22):
            ang = i / 22.0 * math.pi * 2
            j = 1.0 + rng.uniform(-0.22, 0.22)
            pts.append((cx + math.cos(ang) * rx * k * j,
                        cy + math.sin(ang) * ry * k * j))
        return pts

    for i in range(6):                       # nested low-alpha: soft edge
        k = 1.0 - i * 0.09
        pygame.draw.polygon(surf, (12, 11, 12, 22), blob(k))
    pygame.draw.polygon(surf, (7, 6, 7, 30), blob(0.5))
    for _ in range(26):                      # grit and embers thrown clear
        ang = rng.uniform(0, math.pi * 2)
        rr = rng.uniform(0.62, 0.96)
        px = cx + math.cos(ang) * rx * rr
        py = cy + math.sin(ang) * ry * rr
        n = rng.choice((2, 2, 3, 4)) * ss
        pygame.draw.rect(surf, (14, 12, 12, rng.randrange(90, 190)),
                         (int(px), int(py), n, max(2, n // 2)))
    surf.blit(_radial_mask(surf.get_size()), (0, 0),
              special_flags=pygame.BLEND_RGBA_MULT)
    img = pygame.transform.smoothscale(surf, (span, h))
    _SCORCH_CACHE[key] = img
    return img


def draw_ground(surface, cam_x, cam_y):
    """Blast scorches, under actors."""
    for x, y, radius, big in _scorch:
        img = _scorch_surface(radius, big)
        w, h = img.get_size()
        surface.blit(img, (int(x - cam_x - w // 2), int(y - cam_y - h // 2)))


def extra_lamps():
    """Event lights for decor's light pass: (x_px, y_px, radius, colour)."""
    out = []
    flick = 0.82 + 0.18 * math.sin(_t * 23.0) * math.sin(_t * 7.0)
    if "truck" in _events:
        out.append((14.6 * T, 2.6 * T, 210, (255, 232, 180)))
        out.append((16.4 * T, 2.6 * T, 210, (255, 232, 180)))
    if "flare" in _events:
        out.append((20.0 * T, 8.0 * T, int(560 * flick) // 20 * 20, (255, 92, 70)))
    if "train" in _events:
        for c in (6, 14, 22, 30, 38):
            out.append((c * T, 4.6 * T, 170, (255, 214, 150)))
    for fire in getattr(STATE, "fire_zones", [])[-10:]:
        k = max(0.0, min(1.0, fire.life / float(fire.max_life or 1)))
        if k > 0.05:
            out.append((fire.x, fire.y, int((90 + 70 * k) * flick) // 10 * 10, (255, 150, 70)))
    return out


def draw_hud(surface):
    """Wave status in M5's status plate (top strip), only on arena stages."""
    global _peak
    if not _waves:
        return
    from missions.m5.draw import _draw_m5_plate  # lazy: the campaign's shared plate
    done, total = wave_progress()
    left = remaining()
    _peak = max(_peak, left)
    if left <= 0:
        title, col, fill, right, frac = ("AREA CLEAR  -  MOVE OUT", (150, 214, 150),
                                         (96, 190, 120), "0", 1.0)
    else:
        if done == 0 and not _loud:
            title, col = "SQUAD DUG IN  -  WAVE 0/%d" % total, (214, 196, 150)
        else:
            title, col = "WAVE %d/%d" % (done, total), (236, 148, 74)
        fill, right = (220, 160, 40), str(left)
        frac = 1.0 - left / float(max(1, _peak))
    _draw_m5_plate(surface, title, col, frac, fill, right)


ARENA_STAGES = (STAGE_CUSTOMS, STAGE_NOMAN, STAGE_RAIL)
