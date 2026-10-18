"""Mission 6 - floodlight stealth for no-man's-land and the rail yard.

Doc contract (``docs/MISSION6_PLOT.md``): the crossing is watched by
sweeping floodlights; stand in a beam for 0.4 s and the Guard comes.  The
lights are real geometry here - a tower position, a sweep clock, a cone
test and a tile raycast so walls actually hide Biribel.

Determinism: the sweep clock is a dt accumulator owned by this module and
reset on every stage entry (never the wall clock), so tests and paused
frames agree.  Detection never kills or teleports the player; it latches
an alarm once per stage and turns the stealth beat into a firefight.
"""
import math

import pygame

from core.config import WIDTH, HEIGHT, TILE_SIZE, font_terminal_small
from core.state import STATE

from . import maps as _maps
from .meta import (
    M6_SOLID_CHARS, STAGE_NOMAN, STAGE_RAIL, STAGE_BOXCAR, STAGE_TRAIN,
    NOMAN_TOWER_TILES, RAIL_DETECTOR_TILES, MAX_ALARM_ENEMIES,
    ALARM_WAVE_DELAYS, ALARM_WAVE_SIZE, ALARM_FIRST_WAVE,
)

T = TILE_SIZE
EXPOSURE_ALARM_S = 0.4
EXPOSURE_DECAY = 2.5
BODY_RADIUS = 10


class Floodlight:
    """One sweeping searchlight.  ``angle0``/``amp`` are radians."""

    __slots__ = ("pos", "angle0", "amp", "period_s", "phase", "half_angle",
                 "range_px", "tower_h", "label", "ignore")

    def __init__(self, pos, angle0, amp, period_s, phase=0.0,
                 half_angle=0.30, range_px=780, tower_h=230, label="",
                 ignore=()):
        self.pos = (float(pos[0]), float(pos[1]))
        self.angle0 = float(angle0)
        self.amp = float(amp)
        self.period_s = max(0.001, float(period_s))
        self.phase = float(phase)
        self.half_angle = float(half_angle)
        self.range_px = float(range_px)
        self.tower_h = tower_h
        self.label = label
        # Solid tiles the lamp is bolted to; a ray must not be stopped by
        # the tower/shack it originates from.
        self.ignore = frozenset(ignore)

    def angle_at(self, t):
        return self.angle0 + self.amp * math.sin(
            2.0 * math.pi * (t / self.period_s) + self.phase)


def _tower_center(tile):
    return (tile[0] * T + T // 2, tile[1] * T + T)


def _tower_footprint(tile):
    x, y = tile
    return frozenset(((x, y), (x, y + 1)))


_NOMAN_LIGHTS = (
    Floodlight(_tower_center(NOMAN_TOWER_TILES[0]), 0.32, 0.66, 8.4, 0.0,
               half_angle=0.30, range_px=800, label="west-north",
               ignore=_tower_footprint(NOMAN_TOWER_TILES[0])),
    Floodlight(_tower_center(NOMAN_TOWER_TILES[1]), math.pi - 0.35, 0.60, 9.6, 2.2,
               half_angle=0.30, range_px=800, label="east-north",
               ignore=_tower_footprint(NOMAN_TOWER_TILES[1])),
    Floodlight(_tower_center(NOMAN_TOWER_TILES[2]), -0.17, 0.62, 8.9, 1.2,
               half_angle=0.30, range_px=800, label="west-south",
               ignore=_tower_footprint(NOMAN_TOWER_TILES[2])),
    Floodlight(_tower_center(NOMAN_TOWER_TILES[3]), math.pi + 0.18, 0.66, 10.4, 3.1,
               half_angle=0.30, range_px=800, label="east-south",
               ignore=_tower_footprint(NOMAN_TOWER_TILES[3])),
)

_RAIL_LIGHTS = (
    Floodlight((RAIL_DETECTOR_TILES[0][0] * T + T // 2,
                RAIL_DETECTOR_TILES[0][1] * T),
               math.pi / 2, 0.78, 12.0, 0.4, half_angle=0.26,
               range_px=11 * T, label="signal",
               ignore=frozenset((x, y) for x in range(39, 43)
                                for y in range(7, 11))),
    Floodlight((RAIL_DETECTOR_TILES[1][0] * T + T // 2,
                RAIL_DETECTOR_TILES[1][1] * T),
               0.92, 0.72, 14.0, 2.6, half_angle=0.24,
               range_px=9 * T, label="platform"),
)

_LIGHTS = {STAGE_NOMAN: _NOMAN_LIGHTS, STAGE_RAIL: _RAIL_LIGHTS}

_t = 0.0
_stage = None
_lights = ()
_last_visible = False
_alarm_clock = 0.0
_pending_waves = []
_pending_sizes = []
_cone_clock = 0.0

_CONE_SURF = None


def init_stage(stage):
    """Bind the stage, reset the sweep clock and clear the alarm."""
    global _t, _stage, _lights, _last_visible, _alarm_clock, _pending_waves
    global _pending_sizes
    _stage = stage
    _lights = _LIGHTS.get(stage, ())
    _t = 0.0
    _alarm_clock = 0.0
    _pending_waves = []
    _pending_sizes = []
    _last_visible = False
    STATE.m6_exposure = 0.0
    STATE.m6_alarm = False
    STATE.m6_alarm_triggered = False
    STATE.m6_wave_count = 0


def reset():
    init_stage(_stage)


def clock():
    return _t


def lights():
    return _lights


def visible():
    return _last_visible


def alarm_active():
    return bool(getattr(STATE, "m6_alarm", False))


def exposure():
    return float(getattr(STATE, "m6_exposure", 0.0))


# ─────────────────────────────────────────────
# Geometry
# ─────────────────────────────────────────────
def _ang_diff(a, b):
    d = (a - b) % (2.0 * math.pi)
    if d > math.pi:
        d -= 2.0 * math.pi
    return d


def _blocked(ax, ay, bx, by, grid, step=16, ignore=frozenset()):
    dist = math.hypot(bx - ax, by - ay)
    if dist < 1:
        return False
    h, w = len(grid), len(grid[0])
    steps = int(dist // step)
    for i in range(1, steps + 1):
        f = min(1.0, (i * step) / dist)
        x = int((ax + (bx - ax) * f) // T)
        y = int((ay + (by - ay) * f) // T)
        if not (0 <= x < w and 0 <= y < h):
            return True
        if grid[y][x] in M6_SOLID_CHARS and (x, y) not in ignore:
            return True
    return False


def clear_distance(light, angle, grid=None):
    """Distance a beam reaches before the first solid tile."""
    grid = grid or _maps.M6_STRUCTURE_MAP
    ax, ay = light.pos
    step = 16.0
    reach = 24.0
    while reach < light.range_px:
        x = int((ax + math.cos(angle) * reach) // T)
        y = int((ay + math.sin(angle) * reach) // T)
        if not (0 <= y < len(grid) and 0 <= x < len(grid[0])):
            return max(0.0, reach - step)
        if grid[y][x] in M6_SOLID_CHARS and (x, y) not in light.ignore:
            return max(0.0, reach - step)
        reach += step
    return light.range_px


def point_in_cone(light, x, y, t, grid=None):
    """Pure centre test (occlusion included). Used by tests and by HUD."""
    grid = grid or _maps.M6_STRUCTURE_MAP
    ax, ay = light.pos
    dx, dy = x - ax, y - ay
    dist = math.hypot(dx, dy)
    if dist > light.range_px or dist < 1.0:
        return False
    if abs(_ang_diff(math.atan2(dy, dx), light.angle_at(t))) > light.half_angle:
        return False
    return not _blocked(ax, ay, x, y, grid, ignore=light.ignore)


def in_cone(light, x, y, t, grid=None, body=BODY_RADIUS):
    """Player-sized test: the centre plus a small body disc."""
    grid = grid or _maps.M6_STRUCTURE_MAP
    if point_in_cone(light, x, y, t, grid):
        return True
    for i in range(4):
        a = math.pi / 2 * i
        if point_in_cone(light, x + math.cos(a) * body,
                         y + math.sin(a) * body, t, grid):
            return True
    return False


def detected_at(x, y, t=None, grid=None):
    """Any current-stage light currently covers this world point."""
    t = _t if t is None else t
    return any(in_cone(light, x, y, t, grid) for light in _lights)


# ─────────────────────────────────────────────
# Exposure / alarm / waves
# ─────────────────────────────────────────────
def trigger_alarm():
    """Latch the alarm.  Idempotent; called by exposure or by tests."""
    if getattr(STATE, "m6_alarm_triggered", False):
        return False
    STATE.m6_alarm = True
    STATE.m6_alarm_triggered = True
    STATE.m6_exposure = EXPOSURE_ALARM_S
    global _alarm_clock, _pending_waves, _pending_sizes
    _alarm_clock = 0.0
    delays = list(ALARM_WAVE_DELAYS.get(_stage, (2.5,)))
    _pending_waves = delays
    sizes = [ALARM_WAVE_SIZE.get(_stage, 2)] * len(delays)
    if sizes:
        sizes[0] = ALARM_FIRST_WAVE.get(_stage, sizes[0])
    _pending_sizes = sizes
    from . import world as _world
    _world.on_alarm(_stage)
    _world.radio(
        "MARU: Light caught you - they're coming from the gates. Move!",
        color=(222, 120, 92), duration=420, mark="alarm_" + str(_stage),
        priority=1)
    _world.sfx("mission3_alarm_loop", 0.35)
    return True


def _spawn_scheduled_wave():
    if not _pending_waves:
        return
    _pending_waves.pop(0)
    size = _pending_sizes.pop(0) if _pending_sizes else 2
    living = sum(1 for e in getattr(STATE, "enemies", []) if getattr(e, "hp", 0) > 0)
    if living >= MAX_ALARM_ENEMIES:
        return
    from . import world as _world
    _world.spawn_alarm_wave(min(size, MAX_ALARM_ENEMIES - living))


def update(dt):
    """Advance the sweep clock and exposure.  Returns 'detected' this frame."""
    global _t, _alarm_clock, _last_visible
    stage = getattr(STATE, "mission6_stage", None)
    if stage != _stage:
        init_stage(stage)
    if not _lights:
        _last_visible = False
        return False
    _t += max(0.0, float(dt))
    p = getattr(STATE, "player", None)
    alive = bool(p) and not getattr(STATE, "player_dead", False)
    locked = (getattr(STATE, "request_m6_cutscene", None) is not None
              or getattr(STATE, "m6_train_active", False))
    seen = False
    if alive and not locked:
        seen = detected_at(p.rect.centerx, p.rect.centery, _t)
    _last_visible = seen
    if seen:
        STATE.m6_exposure = min(EXPOSURE_ALARM_S + 0.2,
                                exposure() + max(0.0, float(dt)))
    else:
        STATE.m6_exposure = max(0.0, exposure() - EXPOSURE_DECAY * max(0.0, float(dt)))
    if exposure() >= EXPOSURE_ALARM_S and not getattr(STATE, "m6_alarm_triggered", False):
        trigger_alarm()
    if getattr(STATE, "m6_alarm", False):
        _alarm_clock += max(0.0, float(dt))
        while _pending_waves and _alarm_clock >= _pending_waves[0]:
            _spawn_scheduled_wave()
    return seen


# ─────────────────────────────────────────────
# Rendering
# ─────────────────────────────────────────────
def _cone_overlay(size):
    global _CONE_SURF
    if _CONE_SURF is None or _CONE_SURF.get_size() != size:
        _CONE_SURF = pygame.Surface(size)
    _CONE_SURF.fill((0, 0, 0))
    return _CONE_SURF


def _scale(col, k):
    return (max(0, min(255, int(col[0] * k))),
            max(0, min(255, int(col[1] * k))),
            max(0, min(255, int(col[2] * k))))


def _draw_beam(overlay, light, cam_x, cam_y, alarmed):
    ang = light.angle_at(_t)
    base = (255, 128, 66) if alarmed else (132, 178, 224)
    pulse = 0.78 + 0.22 * math.sin(_t * 9.0) if alarmed else 1.0
    origin = (light.pos[0] - cam_x, light.pos[1] - cam_y)
    spread = max(4, int(light.half_angle * 2 * 9))
    rays = []
    for i in range(spread + 1):
        a = ang - light.half_angle + (2 * light.half_angle) * (i / spread)
        rays.append((a, clear_distance(light, a)))
    for frac, strength in ((1.0, 0.070), (0.66, 0.105), (0.33, 0.165)):
        pts = [origin]
        for a, d in rays:
            r = min(d, light.range_px * frac)
            pts.append((origin[0] + math.cos(a) * r,
                        origin[1] + math.sin(a) * r))
        if len(pts) >= 3:
            pygame.draw.polygon(overlay, _scale(base, strength * pulse), pts)
    # Hot core near the tower.
    core = []
    for a, d in rays:
        if abs(_ang_diff(a, ang)) <= light.half_angle * 0.38:
            r = min(d, light.range_px * 0.5)
            core.append((origin[0] + math.cos(a) * r,
                         origin[1] + math.sin(a) * r))
    if len(core) >= 2:
        pygame.draw.polygon(overlay, _scale(base, 0.19 * pulse), [origin] + core)
    pool = (origin[0] + math.cos(ang) * min(light.range_px * 0.92,
                                             clear_distance(light, ang)),
            origin[1] + math.sin(ang) * min(light.range_px * 0.92,
                                            clear_distance(light, ang)))
    pygame.draw.ellipse(overlay, _scale(base, 0.10 * pulse),
                        (pool[0] - 46, pool[1] - 16, 92, 32))
    pygame.draw.circle(overlay, _scale((255, 236, 196), 0.55 * pulse),
                       (int(origin[0]), int(origin[1])), 4)


def draw_cones(surface, cam_x, cam_y):
    """Additive ground beams.  Called after actors so light washes over them."""
    if not _lights:
        return
    overlay = _cone_overlay(surface.get_size())
    alarmed = alarm_active()
    for light in _lights:
        if (light.pos[0] - cam_x < -light.range_px
                or light.pos[0] - cam_x > WIDTH + light.range_px
                or light.pos[1] - cam_y < -light.range_px
                or light.pos[1] - cam_y > HEIGHT + light.range_px):
            continue
        _draw_beam(overlay, light, cam_x, cam_y, alarmed)
    surface.blit(overlay, (0, 0), special_flags=pygame.BLEND_RGB_ADD)


def draw_hud(surface):
    """Exposure / alarm chip; only present while it means something."""
    if _stage not in (STAGE_NOMAN, STAGE_RAIL):
        return
    exp = exposure()
    alarmed = alarm_active()
    if not alarmed and exp <= 0.005:
        return
    w, h = 236, 44
    x = (WIDTH - w) // 2
    y = 18
    panel = pygame.Surface((w, h), pygame.SRCALPHA)
    panel.fill((8, 10, 14, 214))
    pygame.draw.rect(panel, (196, 128, 58) if not alarmed else (206, 74, 58),
                     panel.get_rect(), 1)
    label = "ALARM - GUARD INBOUND" if alarmed else "IN THE LIGHT"
    col = (236, 148, 74) if not alarmed else (240, 96, 78)
    txt = font_terminal_small.render(label, True, col)
    panel.blit(txt, (10, 5))
    bar_x, bar_y, bar_w = 10, 24, w - 20
    pygame.draw.rect(panel, (26, 28, 32), (bar_x, bar_y, bar_w, 8))
    frac = 1.0 if alarmed else max(0.0, min(1.0, exp / EXPOSURE_ALARM_S))
    pygame.draw.rect(panel, col, (bar_x, bar_y, int(bar_w * frac), 8))
    for i in range(1, 8):
        bx = bar_x + int(bar_w * i / 8)
        pygame.draw.line(panel, (8, 10, 14), (bx, bar_y), (bx, bar_y + 7), 1)
    surface.blit(panel, (x, y))
