"""Mission 6 - world construction, Guard spawns and shared helpers.

Every stage binds its own authored grid through ``maps.bind_stage`` and
rebuilds collision/spawns from it.  ``B`` props are solid tiles (their art
lives in ``decor``), ``D`` is a walkable threshold, and ``E``/``V`` spawn a
Guard or Volkov.  Alarm waves are spawned here too so stealth stays pure
geometry + timing.
"""
import math

import pygame

from core.config import TILE_SIZE
from core.state import STATE
from core import config as _config
from entities.player import Player
from entities.enemy_ai import Enemy
from fx import effects
from ui.hud import MiniMap

from . import maps as _maps
from . import decor as _decor
from . import stealth as _stealth
from .meta import (
    M6_SOLID_CHARS, STAGE_CUSTOMS, STAGE_NOMAN, STAGE_RAIL, STAGE_BOXCAR,
    STAGE_TRAIN, STAGE_SPAWNS, STAGE_ANCHORS,
    QUEUE_ANCHOR, QUEUE_RADIUS, ALARM_SPAWN_TILES, MAX_ALARM_ENEMIES,
    VOLKOV_BOXCAR_TILE, ALARM_ENTRY_DIST, ALARM_ENTRY_S, ALARM_WAVE_DELAYS,
    ALARM_FIRST_WAVE,
)

audio = _config.audio
T = TILE_SIZE
PLAYER_MAX_HP = 115
M6_PLAYER_SPEED = 3.6

_volkov = None
_wave_cursor = 0

# Patrol loops, keyed by spawn tile.  Every waypoint is open floor.
_PATROLS = {
    STAGE_NOMAN: {
        (4, 6): ((4, 6), (4, 14)),
        (34, 12): ((31, 12), (37, 12)),
        (20, 2): ((14, 2), (26, 2)),
    },
    STAGE_RAIL: {
        (12, 15): ((10, 15), (16, 15)),
        (32, 15): ((29, 15), (36, 15)),
        (38, 6): ((33, 6), (42, 6)),
        (16, 7): ((14, 7), (18, 7)),
        (35, 18): ((35, 18), (40, 18)),
    },
}


def _tile_world(col, row):
    return (col * T + T // 2, row * T + T // 2)


def _player_pos():
    if not STATE.player:
        return (0, 0)
    return STATE.player.rect.centerx, STATE.player.rect.centery


def _dist(a, b):
    return math.hypot(a[0] - b[0], a[1] - b[1])


def near(pos, radius=80):
    return bool(STATE.player) and _dist(_player_pos(), pos) <= radius


def near_tile(col, row, radius=80):
    return near(_tile_world(col, row), radius)


def solid_walls():
    return list(getattr(STATE, "walls", []))


def _set_objective(text):
    _maps._objective = text


def _movement_locked():
    if getattr(STATE, "player_dead", False):
        return True
    if getattr(STATE, "death_anim_phase", 0):
        return True
    if getattr(STATE, "request_m6_cutscene", None) is not None:
        return True
    return bool(getattr(STATE, "m6_train_active", False))


def radio(text, color=(100, 160, 220), duration=340, mark=None, priority=1):
    """Deduped mission radio.  M6 lines are all story-critical."""
    if mark and mark in _maps._radio_marks:
        return False
    if mark:
        _maps._radio_marks.add(mark)
    try:
        from core.interactions import trigger_radio_chatter
        trigger_radio_chatter(text, color=color, duration=duration,
                              priority=priority)
        return True
    except Exception:
        return False


def sfx(name, volume=0.4):
    try:
        audio.play(name, volume=volume)
    except Exception:
        pass


def volkov():
    return _volkov


def friendly_npcs():
    """Named NPCs for the top-down rail stage (3D owns the train)."""
    stage = getattr(STATE, "mission6_stage", None)
    if stage not in (STAGE_RAIL, STAGE_BOXCAR) or not _volkov:
        return []
    v = _volkov
    return [("VOLKOV", (v["x"], v["y"]), (212, 186, 140), v["angle"], "pistol")]


def _reset_world_lists():
    for name in ("walls", "doors", "enemies", "bullets", "pickups",
                 "particles", "blood_decals", "casings", "floating_texts",
                 "fire_zones", "thrown_bottles", "molotov_fires", "corpses"):
        if hasattr(STATE, name):
            setattr(STATE, name, [])
    STATE.player = None


def _guard_patrol(stage, tile):
    return _PATROLS.get(stage, {}).get(tile)


def _floor_at(stage, x, y):
    """True when the tile under a world point is walkable in ``stage``."""
    grid = _maps.grid_for(stage)
    col, row = int(x) // T, int(y) // T
    if not (0 <= row < len(grid) and 0 <= col < len(grid[0])):
        return False
    return grid[row][col] not in M6_SOLID_CHARS


def _clear_line(stage, a, b, samples=6):
    for i in range(samples + 1):
        k = i / float(samples)
        if not _floor_at(stage, a[0] + (b[0] - a[0]) * k,
                         a[1] + (b[1] - a[1]) * k):
            return False
    return True


_ENTRY_DIRS = (
    (0.0, -1.0), (-0.7071, -0.7071), (1.0, 0.0), (0.7071, -0.7071),
    (-1.0, 0.0), (-0.7071, 0.7071), (0.0, 1.0), (0.7071, 0.7071),
)
_ENTRY_REACH = (ALARM_ENTRY_DIST, 96.0, 72.0, 48.0, 24.0)


def entry_origin(stage, x, y):
    """Where a wave Guard comes *from*: a walk-in point outside his tile.

    Candidates are the eight compass directions ranked by how much they
    point away from the map centre (spawn tiles hug the borders, so "out"
    is the way in), and each is tried at decreasing reach until both the
    point and the straight line back to the tile are open floor.  The
    longest clear approach wins.  ``None`` when the tile is boxed in - the
    Guard then simply arrives on the spot.
    """
    grid = _maps.grid_for(stage)
    if not grid:
        return None
    h, w = len(grid), len(grid[0])
    dx, dy = x - w * T * 0.5, y - h * T * 0.5
    dist = math.hypot(dx, dy) or 1.0
    ux, uy = dx / dist, dy / dist
    dirs = sorted(_ENTRY_DIRS, key=lambda d: -(d[0] * ux + d[1] * uy))
    for reach in _ENTRY_REACH:
        for vx, vy in dirs:
            ox = max(T * 0.5, min(w * T - T * 0.5, x + vx * reach))
            oy = max(T * 0.5, min(h * T - T * 0.5, y + vy * reach))
            if (abs(ox - x) < 8.0 and abs(oy - y) < 8.0):
                continue
            if _clear_line(stage, (ox, oy), (x, y)):
                return (ox, oy)
    return None


def _spawn_guard(x, y, stage, tile=None, aware=False, entry=False):
    e = Enemy(x, y)
    e.hp = 70
    e.speed = 1.8 if stage in (STAGE_RAIL, STAGE_BOXCAR, STAGE_TRAIN) else 1.65
    e.alerted = bool(aware)
    patrol = _guard_patrol(stage, tile) if tile else None
    if patrol:
        e.patrol_points = [_tile_world(c, r) for c, r in patrol]
        e.patrol_idx = 0
        e.state = "PATROL"
    if aware and STATE.player is not None:
        e.state = "CHASE"
        e.last_seen_pos = _player_pos()
        e.combat_alert_timer = 600
    if entry:
        origin = entry_origin(stage, x, y)
        # Never walk a Guard in on top of the player: the walk-in point is
        # further out than the tile, so it can be closer to him than the
        # tile was.  In that case he simply arrives on the spot.
        if origin is not None and STATE.player is not None:
            px, py = _player_pos()
            if math.hypot(origin[0] - px, origin[1] - py) < 130:
                origin = None
        if origin is not None:
            # Only the attribute exists while he is walking in: Enemy.__init__
            # stays untouched, so the replay state hash is unchanged.
            e.m6_entry_from = origin
            e.m6_entry_to = (float(x), float(y))
            e.m6_entry_total = ALARM_ENTRY_S
            e.m6_entry_t = ALARM_ENTRY_S
            e.rect.center = (int(origin[0]), int(origin[1]))
            e.angle = math.atan2(y - origin[1], x - origin[0])
            e.state = "ENTRY"
    STATE.enemies.append(e)
    return e


def entering(enemy):
    """Seconds left of this Guard's walk-in beat (0 = planted)."""
    return max(0.0, float(getattr(enemy, "m6_entry_t", 0.0)))


def tick_entry(enemy, dt):
    """Advance a walking-in Guard.  True while he is still arriving."""
    left = entering(enemy)
    if left <= 0.0:
        return False
    total = float(getattr(enemy, "m6_entry_total", ALARM_ENTRY_S) or ALARM_ENTRY_S)
    fx, fy = getattr(enemy, "m6_entry_from", (enemy.rect.centerx, enemy.rect.centery))
    tx, ty = getattr(enemy, "m6_entry_to", (enemy.rect.centerx, enemy.rect.centery))
    left = max(0.0, left - max(0.0, float(dt)))
    enemy.m6_entry_t = left
    k = 1.0 - left / total
    k = 1.0 - (1.0 - k) * (1.0 - k)          # fast step in, settling stop
    enemy.rect.center = (int(fx + (tx - fx) * k), int(fy + (ty - fy) * k))
    enemy.angle = math.atan2(ty - fy, tx - fx)
    if left > 0.0:
        return True
    enemy.rect.center = (int(tx), int(ty))
    enemy.state = "CHASE"
    enemy.last_seen_pos = _player_pos()
    enemy.combat_alert_timer = 600
    return False


def _parse_grid(grid, stage):
    for row, line in enumerate(grid):
        for col, ch in enumerate(line):
            x, y = col * T, row * T
            if ch in M6_SOLID_CHARS:
                STATE.walls.append(pygame.Rect(x, y, T, T))
            elif ch == "P":
                STATE.player = Player(x + 16, y + 16, max_hp=PLAYER_MAX_HP)
            elif ch == "E":
                _spawn_guard(x + T // 2, y + T // 2, stage, tile=(col, row))
    return STATE.player


def _place_volkov(stage):
    global _volkov
    if stage not in (STAGE_RAIL, STAGE_BOXCAR, STAGE_TRAIN):
        _volkov = None
        return
    ax, ay = STAGE_ANCHORS[STAGE_RAIL]
    _volkov = {
        "x": float(ax * T + T // 2),
        "y": float(ay * T + T // 2 + 10),
        "angle": -math.pi / 2,
        "dead": bool(getattr(STATE, "m6_volkov_dead", False)),
    }


def build_world(stage):
    """Bind the stage map and rebuild collision, actors and dressing."""
    global _wave_cursor
    _reset_world_lists()
    grid = _maps.bind_stage(stage)
    STATE.mission6_stage = stage
    STATE.mission_phase = "m6_" + stage
    STATE.show_minimap = True
    STATE.minimap = MiniMap(grid, palette="m6")
    _parse_grid(grid, stage)
    if STATE.player is None:
        spawn = STAGE_SPAWNS.get(stage, STAGE_SPAWNS[STAGE_CUSTOMS])
        STATE.player = Player(spawn[0] * T + 16, spawn[1] * T + 16,
                              max_hp=PLAYER_MAX_HP)
    STATE.player.hp = STATE.player.max_hp
    STATE.player.angle = -math.pi / 2
    _wave_cursor = 0
    _place_volkov(stage)
    _decor.build_decor(stage)
    _stealth.init_stage(stage)
    return STATE.player


def alarm_spawn_tiles(stage=None):
    stage = stage or getattr(STATE, "mission6_stage", None)
    return ALARM_SPAWN_TILES.get(stage, ())


def living_guards():
    return sum(1 for e in getattr(STATE, "enemies", [])
               if getattr(e, "hp", 0) > 0)


def spawn_alarm_wave(count, entry=True):
    """Spawn up to ``count`` Guards from the stage's authored entry tiles.

    Tiles are consumed in pairs so a wave arrives from both ends of the
    crossing, never one conga line.  The living cap keeps the fight fair.
    Each Guard walks in from ``entry_origin`` (see ``tick_entry``) so a wave
    is never a pop-in.
    """
    global _wave_cursor
    stage = getattr(STATE, "mission6_stage", None)
    tiles = list(alarm_spawn_tiles(stage))
    if not tiles:
        return 0
    slots = min(int(count), MAX_ALARM_ENEMIES - living_guards())
    if slots <= 0:
        return 0
    px, py = _player_pos()
    spawned = 0
    attempts = 0
    while spawned < slots and attempts < len(tiles) * 2:
        c, r = tiles[_wave_cursor % len(tiles)]
        _wave_cursor += 1
        attempts += 1
        x, y = _tile_world(c, r)
        if math.hypot(x - px, y - py) < 150:
            continue
        _spawn_guard(x, y, stage, tile=(c, r), aware=True, entry=entry)
        try:
            effects.burst(x, y, (198, 212, 228), 10, speed_mul=0.7)
        except Exception:
            pass
        spawned += 1
    STATE.m6_wave_count = int(getattr(STATE, "m6_wave_count", 0)) + spawned
    if spawned:
        sfx("door_break", 0.35)
    return spawned


def on_alarm(stage):
    """Arm the yard: everyone converges, then the gates disgorge a wave.

    Nothing spawns on the alarm frame itself - the siren, the radio line and
    the alarm chip need a beat to land before the first boots are in the
    yard.  ``stealth`` owns that schedule and calls ``spawn_alarm_wave``.
    """
    _arm_everyone()


def _arm_everyone():
    px, py = _player_pos()
    for e in getattr(STATE, "enemies", []):
        if getattr(e, "hp", 0) <= 0:
            continue
        e.alerted = True
        e.state = "CHASE"
        e.last_seen_pos = (px, py)
        e.combat_alert_timer = 720
        if hasattr(e, "path"):
            e.path = []
            e.path_timer = 0


def _queue_bark():
    if getattr(STATE, "mission6_stage", None) != STAGE_CUSTOMS:
        return
    if near(_tile_world(*QUEUE_ANCHOR), QUEUE_RADIUS):
        radio("MARU: That queue hasn't moved since Y-2. Don't look at it too long.",
              color=(146, 196, 206), duration=420, mark="customs_queue")


def _rail_bark():
    if getattr(STATE, "mission6_stage", None) != STAGE_RAIL:
        return
    if _volkov and near((_volkov["x"], _volkov["y"]), 220):
        radio("VASILE: The car with the red stripe. Volkov. Move quiet.",
              color=(212, 178, 120), duration=360, mark="rail_volkov_seen")


def update_world():
    """Mission dressing beats driven by proximity (called by flow)."""
    _queue_bark()
    _rail_bark()
