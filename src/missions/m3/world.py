"""Split from mission3.py - see mission3.py (shim) for the map."""
"""Mission 3: The Vostral - dialogue-driven cold open into action.

This is the third campaign mission, picking up 3 days after Mission 2's
Route 12 frame-up. Biribel wakes in an IPA black-site cell (the
"Stabilization Center") facing Prime Minister Balaceanu's long-promised
vendetta. The mission's spine is the Vostral - the buried rumor that
Balaceanu's decorated military career is fabricated. The only copy of
the service record that can prove it is held in the regime's own
Archives, so the engine of the mission is: break out of the cell, reach
the Archives, steal the file, and get it onto a live state broadcast
before Balaceanu finishes his 22:00 address pinning Route 12 on Biribel
personally.

Story posture (per the project bible): KRAP is STILL an organization -
disavowed, under siege, fighting for its survival and credibility. So
this is not Vasile-as-lone-wolf feeding floor plans out of guilt; KRAP
mobilizes as a resistance. Vasile brings real assets (an off-book
extraction element, a stolen IPA comms relay). The trust tension is
organizational, not personal.

This module keeps the existing game integration intact:
    - game_core.start_mission3()
    - game_core.game_update()/game_draw() routing (MISSION3 is checked
      BEFORE MISSION2 - see game_core.game_update)
    - acaristan.py Mission 3 intro and ending cutscenes (shot-lists
      exposed as module-level names below)
    - save as MISSION_3
    - dev command: python acaristan.py --dev-mission3

Scaffolding note: acaristan.py already routes ALL Mission 3 input
through mission3.handle_event(event) (arrow keys to pick choices,
ENTER to confirm) - this was purpose-built for the dialogue-driven
interrogation cold open that is Phase 1. Action phases (STAGE_BREAKOUT
onward) later relax that gate in acaristan.py so normal mouse-shoot
input falls through.
"""

import math
import random
from engine.core import LEGACY_RNG as _rng_legacy  # RPE6 R6: named 'legacy' rng stream
import time

import pygame

from core.config import (ENEMY_ATTACK_RANGE, ENEMY_DAMAGE, ENEMY_FIRE_COOLDOWN, HEIGHT, TILE_SIZE, WIDTH, font_terminal_small, screen)
from entities.art_cache import get_blood_decal, get_fullscreen_overlay, get_panel_bg
from core.state import STATE
from entities.player import Player, resolve_melee
from entities.enemy_ai import Enemy, enemy_hear_shot, _astar
from ui.hud import MiniMap, draw_objective_panel, draw_pinned_radio
from missions.m1 import _draw_molotov_icon
from fx import effects
import cutscenes
from core.camera import update_camera, reset_camera_state, draw_bullets, collide_bullet_walls
from entities.weapons import _wall_blocks_line
from core import config as _config
audio = _config.audio

from missions.m3 import maps as _m3_maps
from missions.m3.maps import MISSION3_KILL_ORDER_MAP  # _m3_maps.MISSION3_MAP/_m3_maps._objective/_m3_maps._radio_marks owner
from missions.m3.meta import C_SYSTEM, MAP_W, MAP_H, PLAYER_START_TILE, STAGE_BROADCAST, STAGE_INTERROGATION, _CELL_COL_EAST, _CELL_COL_WEST, _CELL_ROW_NORTH, _CELL_ROW_SOUTH, _DOOR_TILE_COL, _DOOR_TILE_ROW, _MONITOR_TILE_COL, _MONITOR_TILE_ROW
from missions.m3.maps import MISSION3_CELL_MAP, MISSION3_COMMS_MAP, MISSION3_ARCHIVES_MAP, MISSION3_BROADCAST_MAP
import game.world as _gw  # RPE6 Phase 5 (D4): mission data lives in components
from engine.world import Label as _Label
from missions.m3.components import M3Door as _M3Door, M3Guard as _M3Guard


def _m3d(door):
    """Declared M3 data of a door (replaces the ad hoc ``door.m3_*`` attributes)."""
    return _gw.ensure(door, _M3Door)



def _m3g(e):
    """Declared M3 data of an enemy (replaces the ad hoc ``e.m3_*`` attributes)."""
    return _gw.ensure(e, _M3Guard)


def _m3l(e):
    """Shared ``Label`` component of an enemy: ``kind`` = enemy type, ``text`` = spawn label."""
    return _gw.ensure(e, _Label)


# The interrogation chair's collision rect. Set in _build_world, filtered out
# by _solid_walls once the chair breaks. Stored module-level (not as an attr
# on the Rect itself) because pygame.Rect is a C type without __dict__.
_CHAIR_RECT = None

def _dist(a, b):
    return math.hypot(a[0] - b[0], a[1] - b[1])


def _player_pos():
    if not STATE.player:
        return (0, 0)
    return STATE.player.rect.centerx, STATE.player.rect.centery


def _interrogation_chair_pos():
    """World-space center of the restraint chair used during Phase 1.

    The map spawn tile is just a fallback marker. During the interrogation
    Biribel is physically cuffed into the chair under the monitor, so camera
    framing and the eventual breakout should originate from this prop.
    """
    return (
        int((_MONITOR_TILE_COL + 0.5) * TILE_SIZE),
        int((_CELL_ROW_NORTH + 1) * TILE_SIZE + TILE_SIZE // 2),
    )


def _near(pos, radius=80):
    return STATE.player and _dist(_player_pos(), pos) <= radius


def _camera_offset_for_target(target):
    tx, ty = target
    mw, mh = _m3_maps._live_map_dims()
    max_x = max(0, mw * TILE_SIZE - WIDTH)
    max_y = max(0, mh * TILE_SIZE - HEIGHT)
    cam_x = tx - WIDTH // 2
    cam_y = ty - HEIGHT // 2
    cam_x = max(0, min(max_x, cam_x))
    cam_y = max(0, min(max_y, cam_y))
    return cam_x, cam_y


def _snap_camera_to(target=None):
    if target is None:
        target = _player_pos()
    cam_x, cam_y = _camera_offset_for_target(target)
    STATE.camera_x = cam_x
    STATE.camera_y = cam_y
    STATE.cam_kick_x = 0.0
    STATE.cam_kick_y = 0.0
    # NOTE: screen_shake is deliberately NOT cleared here (time-based, not
    # positional - a teleport shouldn't eat an in-flight shake). Mission
    # starts zero it explicitly instead.


def _solid_walls():
    """All solid collision rects for this frame.

    Includes STATE.walls + STATE.mission3_barriers, with two dynamic tweaks:
      - If the chair is broken, its barrier rect is filtered out (it's rubble).
      - If the player hasn't crafted a shiv yet, a temporary rect blocks the
        doorway (mandatory crafting - Volkov holds the door until the shiv
        is done).
    """
    out = list(STATE.walls)
    barriers = list(getattr(STATE, "mission3_barriers", []))
    # Remove the chair's collision rect once the chair is broken. pygame.Rect
    # is a C type without __dict__, so we can't tag the rect with an attribute
    # - instead we filter by identity against the module-level _CHAIR_RECT.
    #
    # Also drop it while Biribel's own body overlaps it: he spawns strapped
    # INTO the chair, so its rect sits inside his. If movement unlocks for
    # even one frame before the chair-broken flag lands (e.g. the last
    # interrogation beat is skipped with Enter, which flips the stage inside
    # handle_event before the app consumes the chair-break request), the
    # axis-snap in Player.move() would shove him up into the north wall, and
    # the next step snaps him clean through it - outside the cell, softlocked.
    if _CHAIR_RECT is not None and (
            getattr(STATE, "mission3_chair_broken", False)
            or (STATE.player is not None
                and STATE.player.rect.colliderect(_CHAIR_RECT))):
        barriers = [b for b in barriers if b is not _CHAIR_RECT]
    out.extend(barriers)
    # Doorway blocked until the shiv is crafted (mandatory crafting lock).
    # The blasted cell doorway is TWO tiles wide (_DOOR_TILE_COL and +1);
    # the block must span both, or the player slips out through the east
    # tile with just the chair leg and skips the mandatory craft.
    if getattr(STATE, "mission3_doorway_blocked", False):
        out.append(pygame.Rect(
            _DOOR_TILE_COL * TILE_SIZE + 4,
            _DOOR_TILE_ROW * TILE_SIZE + 4,
            TILE_SIZE * 2 - 8, TILE_SIZE - 8))

    for d in getattr(STATE, "doors", []):
        if getattr(d, "collision_rect", None):
            out.append(d.collision_rect)

    return out


def _m3_cell_door_pair_for_col(row, col):
    """Return the two D-tile columns for a Mission 3 cell door.

    Cell doors are row 12, two tiles wide:
    cell 0: cols 9-10
    cell 1: cols 17-18
    cell 2: cols 25-26
    cell 3: cols 33-34
    """
    if row != _DOOR_TILE_ROW:
        return None

    for cell_idx in range(4):
        base = 6 + cell_idx * 8
        a = base + 3
        b = base + 4
        if col in (a, b):
            return (a, b)

    return None


def _m3_door_obj_at(col, row):
    wx = col * TILE_SIZE
    wy = row * TILE_SIZE
    for d in getattr(STATE, "doors", []):
        if d.rect.x == wx and d.rect.y == wy:
            return d
    return None


def _m3_cell_door_pair_objects(row, col):
    pair = _m3_cell_door_pair_for_col(row, col)
    if pair is None:
        return []

    out = []
    for pair_col in pair:
        d = _m3_door_obj_at(pair_col, row)
        if d is not None:
            out.append(d)
    return out


def _m3_open_cell_door_pair(row, col):
    """Force-open both tiles of a cell door."""
    doors = _m3_cell_door_pair_objects(row, col)
    if not doors:
        return

    for d in doors:
        d.locked = False
        d.target_open = True
        d.anim_progress = 1.0
        d.collision_disabled = True
        d.manual_timer = 9999
        _m3d(d).forced_open = True
        _m3d(d).shot_hits = _m3d(d).required_shots

    # Feedback at the door center.
    pair = _m3_cell_door_pair_for_col(row, col)
    if pair:
        wx = (pair[0] + pair[1] + 1) * TILE_SIZE // 2
        wy = row * TILE_SIZE + TILE_SIZE // 2
    else:
        wx = col * TILE_SIZE + TILE_SIZE // 2
        wy = row * TILE_SIZE + TILE_SIZE // 2

    STATE.floating_texts.append([
        wx,
        wy - 32,
        "CELL DOOR UNLOCKED",
        (120, 220, 150),
        90,
    ])

    try:
        audio.play("door_open", volume=0.45)
    except Exception:
        pass


def _m3_damage_cell_door_with_bullet(b):
    """Handle player bullets damaging locked Mission 3 cell doors.

    Returns True if the bullet hit a door and should be removed.
    """
    if b.get("owner") != "player":
        return False

    prev = (b.get("prev_x", b["x"]), b.get("prev_y", b["y"]))
    cur = (b["x"], b["y"])

    for d in getattr(STATE, "doors", []):
        if not _m3d(d).cell_door:
            continue

        col = d.rect.x // TILE_SIZE
        row = d.rect.y // TILE_SIZE

        # Do not use this system on Biribel's breached starting cell door.
        if row == _DOOR_TILE_ROW and col in (_DOOR_TILE_COL, _DOOR_TILE_COL + 1):
            continue

        # Already open / collision disabled: bullet passes this door logic.
        if getattr(d, "collision_disabled", False) or d.collision_rect is None:
            continue

        if d.rect.clipline(prev, cur):
            doors = _m3_cell_door_pair_objects(row, col)
            if not doors:
                return True

            required = max(_m3d(x).required_shots for x in doors)
            current_hits = max(_m3d(x).shot_hits for x in doors)
            new_hits = min(required, current_hits + 1)

            for x in doors:
                _m3d(x).shot_hits = new_hits

            hit_x, hit_y = cur

            try:
                effects.burst(hit_x, hit_y, (120, 118, 108), 10, speed_mul=1.3)
            except Exception:
                pass
            try:
                effects.shake(3)
            except Exception:
                pass

            try:
                audio.play("bullet_impact", volume=0.35)
            except Exception:
                pass

            if new_hits >= required:
                _m3_open_cell_door_pair(row, col)
                try:
                    effects.burst(hit_x, hit_y, (200, 180, 120), 18, speed_mul=1.8)
                except Exception:
                    pass
            else:
                STATE.floating_texts.append([
                    hit_x,
                    hit_y - 20,
                    f"LOCK DAMAGE {new_hits}/{required}",
                    (220, 180, 90),
                    42,
                ])

            return True

    return False


def _set_objective(text):
    _m3_maps._objective = text


def _movement_locked():
    # Phase 1 (interrogation): Biribel is cuffed to the chair, no movement.
    if getattr(STATE, "mission3_stage", STAGE_INTERROGATION) == STAGE_INTERROGATION:
        return True
    # Relay tuning is an interact/hold moment at the terminal.
    if getattr(STATE, "m3_relay_active", False):
        return True
    # Maru dead-drop contact locks movement while the message plays.
    if getattr(STATE, "m3_maru_contact_active", False):
        return True
    return False


def _radio(text, color=C_SYSTEM, duration=320, mark=None, priority=0):
    """Pinned-radio helper, mirroring mission2._radio's signature.

    The interrogation cold open does NOT use this (its dialogue is a
    bespoke full-screen panel). It's here so Phase 3 (KRAP re-contact)
    and onward can drop radio beats in without re-deriving the helper.
    """
    if mark and mark in _m3_maps._radio_marks:
        return
    if mark:
        _m3_maps._radio_marks.add(mark)
    try:
        from core.interactions import trigger_radio_chatter
        trigger_radio_chatter(text, color=color, duration=duration,
                              priority=max(priority, 0.5) if mark else priority)
    except Exception:
        # Audio/interactions are optional in headless test harnesses.
        pass


def _start_m3_alarm():
    """Start the Mission 3 lockdown alarm: quiet loop + state flag."""
    if getattr(STATE, "m3_alarm_active", False):
        return

    STATE.m3_alarm_active = True
    STATE.m3_alarm_timer = 0

    try:
        if hasattr(audio, "play_mission3_alarm"):
            audio.play_mission3_alarm(volume=0.18)
        else:
            audio.play("alarm", volume=0.12, loops=-1, channel="m3_alarm")
    except Exception:
        pass


def _stop_m3_alarm(force=False):
    """Stop the Mission 3 lockdown alarm."""
    if not force and not getattr(STATE, "m3_alarm_active", False):
        return

    STATE.m3_alarm_active = False
    STATE.m3_alarm_timer = 0

    try:
        if hasattr(audio, "stop_mission3_alarm"):
            audio.stop_mission3_alarm()
        else:
            audio.stop("alarm")
            audio.stop(channel="m3_alarm")
    except Exception:
        pass


def _draw_m3_alarm_effect(surface):
    """Prison lockdown alarm: hard red flash on/off cycle.

    Like real emergency lighting - the overhead strips snap red, hold
    for half a second, go dark, repeat. Simple, readable, not annoying.
    """
    if not getattr(STATE, "m3_alarm_active", False):
        return

    timer = getattr(STATE, "m3_alarm_timer", 0)

    # Hard on/off cycle: 40 frames on, 30 frames off (~1.2s period at 60fps).
    cycle = timer % 70
    on = cycle < 40

    if not on:
        return

    # Fade within the ON phase so it's not a flat rectangle.
    # Ramps up fast (10 frames), holds, ramps down fast (10 frames).
    if cycle < 10:
        strength = cycle / 10.0
    elif cycle > 30:
        strength = (40 - cycle) / 10.0
    else:
        strength = 1.0

    alpha = int(45 * strength)

    flash = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    flash.fill((200, 15, 10, alpha))
    surface.blit(flash, (0, 0))


def _update_volkov_escape_route():
    """After Volkov gets Biribel out, he sprints away to draw attention.

    This only starts after the interrogation handoff flips into STAGE_BREAKOUT.
    """
    if not getattr(STATE, "m3_volkov_run_active", False):
        return
    if getattr(STATE, "m3_volkov_run_done", False):
        return

    STATE.m3_volkov_run_timer = getattr(STATE, "m3_volkov_run_timer", 0) + 1

    # Running footstep foley.
    if STATE.m3_volkov_run_timer % 16 == 0:
        try:
            audio.play("volkov_step", volume=0.50)
        except Exception:
            pass

    # Once he reaches the east/service-exit side, fade him out and remove him.
    # Shorter than the old 520-frame wait so he does not stand around at the
    # edge of the map after his run is visually over.
    if STATE.m3_volkov_run_timer > 240:
        STATE.m3_volkov_run_done = True


def _volkov_escape_path_points():
    """World-space path Volkov runs after freeing Biribel.

    Route:
    doorway -> main corridor -> east/service-exit side.
    """
    door_wx = _DOOR_TILE_COL * TILE_SIZE + TILE_SIZE
    door_wy = _DOOR_TILE_ROW * TILE_SIZE
    doorway_y = door_wy + TILE_SIZE // 2
    corridor_y = 15 * TILE_SIZE + TILE_SIZE // 2

    return [
        (door_wx, doorway_y),
        (door_wx, corridor_y),
        (37 * TILE_SIZE + TILE_SIZE // 2, corridor_y),
        (41 * TILE_SIZE + TILE_SIZE // 2, corridor_y),
        (44 * TILE_SIZE + TILE_SIZE // 2, corridor_y),
    ]


def _sample_volkov_escape_path(timer, speed=5.4):
    """Return (x, y, facing_angle, running) for Volkov's escape route."""
    pts = _volkov_escape_path_points()
    if len(pts) < 2:
        return None

    remaining = timer * speed

    for i in range(len(pts) - 1):
        x1, y1 = pts[i]
        x2, y2 = pts[i + 1]
        seg_len = math.hypot(x2 - x1, y2 - y1)

        if remaining <= seg_len:
            t = remaining / max(1.0, seg_len)
            x = x1 + (x2 - x1) * t
            y = y1 + (y2 - y1) * t
            angle = math.atan2(y2 - y1, x2 - x1)
            return (x, y, angle, True)

        remaining -= seg_len

    # Arrived at final point.
    x, y = pts[-1]
    prev_x, prev_y = pts[-2]
    angle = math.atan2(y - prev_y, x - prev_x)
    return (x, y, angle, False)


def _volkov_world_pose():
    """Return Volkov's full world pose.

    Returns:
      (x, y, facing_angle, running)

    Or None if Volkov should not be drawn.
    """
    from missions.m3 import flow as _m3_flow  # lazy: _volkov_breach_t owner (flow loads later)
    if getattr(STATE, "m3_volkov_run_done", False):
        return None

    door_wx = _DOOR_TILE_COL * TILE_SIZE + TILE_SIZE
    door_wy = _DOOR_TILE_ROW * TILE_SIZE
    t = _m3_flow._volkov_breach_t

    if t < 0:
        return None

    corridor_y = door_wy + TILE_SIZE * 3
    doorway_y = door_wy + TILE_SIZE // 2

    # After breakout begins, Volkov runs away to draw attention.
    if getattr(STATE, "m3_volkov_run_active", False):
        run_t = getattr(STATE, "m3_volkov_run_timer", 0)
        return _sample_volkov_escape_path(run_t)

    # Original breach choreography.
    if t <= 90:
        p = t / 90.0
        return (door_wx, corridor_y + (doorway_y - corridor_y) * p, -math.pi / 2, False)
    elif t <= 210:
        return (door_wx, doorway_y, -math.pi / 2, False)
    elif t <= 300:
        p = (t - 210) / 90.0
        return (door_wx, doorway_y + (corridor_y - doorway_y) * p, math.pi / 2, False)
    elif t <= 306:
        return (door_wx, corridor_y, -math.pi / 2, False)
    elif t <= 390:
        p = (t - 306) / 84.0
        return (door_wx, corridor_y + (doorway_y - corridor_y) * p, -math.pi / 2, False)

    return (door_wx, doorway_y, -math.pi / 2, False)


def _volkov_world_pos():
    """Compatibility wrapper used by the camera."""
    pose = _volkov_world_pose()
    if pose is None:
        return None
    return (pose[0], pose[1])


# ─────────────────────────────────────────────
# Slice 2 - Breakout: guard spawns
# ─────────────────────────────────────────────
# IPA guards patrol the prison block. They start UNAWARE (alerted=False)
# so the player can use the shiv for silent takedowns. Once one fires or
# hears a shot, the others aggro via enemy_hear_shot().

# Guard posts (tile coords) for the new 48x48 layout:
#   1 - Main corridor east (patrols east-west)
#   2 - Guard room entrance (stationary, watching the corridor)
#   3 - Guard room interior (patrols the room)
#   4 - Kitchen area (stationary, by the vent)
#   5 - Main corridor centre (patrols mid-section)
_GUARD_POST_1_TILE = (34, 15)   # main corridor east end
_GUARD_POST_2_TILE = (22, 15)   # main corridor centre
_GUARD_POST_3_TILE = (22, 21)   # guard room interior, facing door
_GUARD_POST_4_TILE = (4, 22)    # kitchen area
_GUARD_POST_5_TILE = (15, 15)   # main corridor west
_GUARD_POST_6_TILE = (40, 22)   # armory interior patrol
_GUARD_POST_7_TILE = (41, 15)   # service-exit checkpoint
_GUARD_POST_8_TILE = (30, 21)   # guard room east patrol

# Patrol routes (world-space (x, y) tuples).
_PATROL_ROUTE_1 = [
    (_GUARD_POST_1_TILE[0] * TILE_SIZE + TILE_SIZE // 2,
     _GUARD_POST_1_TILE[1] * TILE_SIZE + TILE_SIZE // 2),
    (22 * TILE_SIZE + TILE_SIZE // 2,
     _GUARD_POST_1_TILE[1] * TILE_SIZE + TILE_SIZE // 2),
]
_PATROL_ROUTE_2 = []  # stationary - no patrol
_PATROL_ROUTE_3 = [
    (_GUARD_POST_3_TILE[0] * TILE_SIZE + TILE_SIZE // 2,
     _GUARD_POST_3_TILE[1] * TILE_SIZE + TILE_SIZE // 2),
    (14 * TILE_SIZE + TILE_SIZE // 2,
     _GUARD_POST_3_TILE[1] * TILE_SIZE + TILE_SIZE // 2),
]
_PATROL_ROUTE_4 = []  # stationary - kitchen guard
_PATROL_ROUTE_5 = [
    (8 * TILE_SIZE + TILE_SIZE // 2,
     _GUARD_POST_5_TILE[1] * TILE_SIZE + TILE_SIZE // 2),
    (22 * TILE_SIZE + TILE_SIZE // 2,
     _GUARD_POST_5_TILE[1] * TILE_SIZE + TILE_SIZE // 2),
]
_PATROL_ROUTE_6 = [
    (38 * TILE_SIZE + TILE_SIZE // 2,
     _GUARD_POST_6_TILE[1] * TILE_SIZE + TILE_SIZE // 2),
    (42 * TILE_SIZE + TILE_SIZE // 2,
     _GUARD_POST_6_TILE[1] * TILE_SIZE + TILE_SIZE // 2),
]
_PATROL_ROUTE_7 = []  # stationary - service-exit checkpoint guard
_PATROL_ROUTE_8 = [
    (26 * TILE_SIZE + TILE_SIZE // 2,
     _GUARD_POST_8_TILE[1] * TILE_SIZE + TILE_SIZE // 2),
    (33 * TILE_SIZE + TILE_SIZE // 2,
     _GUARD_POST_8_TILE[1] * TILE_SIZE + TILE_SIZE // 2),
]

# Cell-block exit tile - reaching the centre E tile triggers STAGE_COMMS.
_EXIT_TILE_COL, _EXIT_TILE_ROW = 41, 15

# Volkov's escape destination - he runs east/right toward the service-exit
# side of the map after the breach instead of sprinting away from the objective.
_VOLKOV_ESCAPE_TARGET = (
    43 * TILE_SIZE + TILE_SIZE // 2,
    15 * TILE_SIZE + TILE_SIZE // 2,
)

# Vent shaft - secondary exit from Biribel's cell to the kitchen.
# The grate is at the SW corner of the cell (drawn in _draw_cell_details).
# Player can pry it open with the shiv, then crawl through to the kitchen.
_VENT_GRATE_COL, _VENT_GRATE_ROW = 31, 10   # inside cell, SW area
_VENT_EXIT_COL, _VENT_EXIT_ROW = 4, 22       # kitchen area
_K9_STAND_COL, _K9_STAND_ROW = 41, 19        # armory north-wall weapon stand
_RELAY_TILE_COL, _RELAY_TILE_ROW = 24, 19         # Comms Wing relay terminal
_ARCHIVE_EXIT_COL, _ARCHIVE_EXIT_ROW = 46, 24     # Comms Wing archive access marker
# Archives Wing interactables (Phase 4).
_MARU_TERMINAL_COL, _MARU_TERMINAL_ROW = 11, 12   # dead-drop terminal in NW clerk office
_VOSTRAL_FILE_COL, _VOSTRAL_FILE_ROW = 42, 9      # classified file pedestal (NE vault)
_ARCHIVES_SPAWN_COL, _ARCHIVES_SPAWN_ROW = 24, 42 # south elevator lobby
_ARCHIVES_EXIT_COL, _ARCHIVES_EXIT_ROW = 24, 4    # north stairwell → Kill Order
_VOSTRAL_DOOR_COLS = (36,)                        # vault door column (rows 8-9)
_VOSTRAL_DOOR_ROWS = (8, 9)
_EXIT_DOOR_COLS = (24, 25)
_EXIT_DOOR_ROWS = (6,)


def _spawn_m3_guard(col, row, *, hp=90, speed=1.6, patrol=None,
                    facing=None, label="IPA_GUARD", enemy_type="guard"):
    """Spawn a Mission 3 IPA cell-block guard.

    Mirrors mission2._spawn_enemy but tuned for stealth-first gameplay:
      - Lower HP (90 vs 115) so a shiv backstab two-shots them.
      - Slower speed (1.6 vs 2.0) so the player can break LOS.
      - Starts UNAWARE (alerted=False). state="PATROL" if a patrol route
        is provided, else "IDLE".
      - `facing` (radians, optional) sets the initial sight-cone
        direction so designers can angle guards away from the breach
        route.
      - `label` is stashed on the enemy for pickup-drop logic and
        death-event tracking (e.g. "guard_post_1_down").
    """
    x = col * TILE_SIZE + TILE_SIZE // 2
    y = row * TILE_SIZE + TILE_SIZE // 2
    e = Enemy(x - 16, y - 16)
    e.hp = hp
    e.speed = speed
    e.alerted = False
    e.state = "PATROL" if patrol else "IDLE"
    e.fire_cooldown = _rng_legacy.randint(30, 90)
    g = _m3g(e)                       # declared M3 data (components), not attributes on the Enemy
    g.ipa = True
    lab = _m3l(e)
    lab.text = label
    lab.kind = enemy_type
    # Broadcast Wing (Slice 6): studio security protects the uplink PC and
    # always knows Biribel's position - the last leg is a holdout, not a
    # stealth puzzle. ``alerted`` alone only wakes them; ``m3_always_alert``
    # is what makes them engage without line of sight (systems
    # ._m3_choose_enemy_target).
    if getattr(STATE, "mission3_stage", None) == STAGE_BROADCAST:
        g.always_alert = True
        e.alerted = True

    # Per-type combat tuning. These feed Mission 3's custom shooting path and
    # visual overlay. Values are modest so new types add texture without
    # turning the slice into a bullet sponge wall.
    type_stats = {
        "guard":      {"damage": ENEMY_DAMAGE, "cooldown": ENEMY_FIRE_COOLDOWN, "spread": 0.06,  "bullet_speed": 18, "attack_range": ENEMY_ATTACK_RANGE},
        "breacher":   {"damage": 15,           "cooldown": 38,                  "spread": 0.12,  "bullet_speed": 17, "attack_range": 145},
        "shield":     {"damage": 12,           "cooldown": 68,                  "spread": 0.08,  "bullet_speed": 16, "attack_range": 175},
        "technician": {"damage": 10,           "cooldown": 76,                  "spread": 0.10,  "bullet_speed": 16, "attack_range": 215},
        "marksman":   {"damage": 30,           "cooldown": 92,                  "spread": 0.025, "bullet_speed": 22, "attack_range": 430},
    }
    stats = type_stats.get(enemy_type, type_stats["guard"])
    g.damage = stats["damage"]
    g.fire_cooldown = stats["cooldown"]
    g.spread = stats["spread"]
    g.bullet_speed = stats["bullet_speed"]
    g.attack_range = stats["attack_range"]
    if enemy_type == "shield":
        g.shield_angle_width = math.radians(78)
    if patrol:
        e.patrol_points = list(patrol)
        e.patrol_idx = 0
    if facing is not None:
        e.angle = facing
        e.idle_angle = facing
    STATE.enemies.append(e)
    return e


# ─────────────────────────────────────────────
# World build
# ─────────────────────────────────────────────
def _build_world():
    """Parse _m3_maps.MISSION3_MAP into STATE entities, then register furniture
    collision rects for the cell's solid fixtures (chair, cot, sink).

    The furniture rects are added to STATE.mission3_barriers (which
    _solid_walls() includes), so the player collides with them. Each
    rect is inset slightly from the drawn sprite so the player's collision
    feels fair (they stop at the visible edge of the object, not at a
    larger invisible box).

    Spawns IPA guards across the prison block (corridor, guard room, kitchen,
    armory, exit checkpoint). They start unaware so the player can use the shiv for
    silent takedowns before any gunfire escalates the situation.
    """
    from missions.m3 import systems as _m3s  # lazy: breaks world<->systems cycle
    global _CHAIR_RECT
    STATE.walls = []
    STATE.enemies = []
    STATE.pickups = []
    STATE.blood_decals = []
    STATE.bullets = []
    STATE.casings = []
    STATE.particles = []
    STATE.floating_texts = []
    STATE.mission3_barriers = []
    STATE.doors = []
    STATE.player = None

    for row_idx, row in enumerate(_m3_maps.MISSION3_MAP):
        for col_idx, tile in enumerate(row):
            x, y = col_idx * TILE_SIZE, row_idx * TILE_SIZE
            if tile == "C":
                STATE.walls.append(pygame.Rect(x, y, TILE_SIZE, TILE_SIZE))
            elif tile == "B":
                r = pygame.Rect(x + 4, y + 12, TILE_SIZE - 8, TILE_SIZE - 24)
                STATE.walls.append(r)
                STATE.mission3_barriers.append(r)
            elif tile == "D":
                from core.interactions import Door
                new_door = Door(x, y, is_bay=False)

                # Mission 3 cell doors stay locked and can be shot open after
                # 6 hits. Utility/guard-room doors are normal unlocked doors;
                # locking every D tile made some guards unreachable and could
                # trap the player in side rooms.
                _m3d(new_door).cell_door = (row_idx == _DOOR_TILE_ROW)
                is_armory_door = (row_idx == 21 and col_idx in (35, 36))
                new_door.locked = bool(_m3d(new_door).cell_door)
                _m3d(new_door).shot_hits = 0
                _m3d(new_door).required_shots = 6
                _m3d(new_door).forced_open = False

                # The armory entrance is a double security doorway between two
                # wall columns. If both halves behave like normal automatic
                # doors, the player can be stopped by the second panel before
                # getting close enough to open it. Keep it visually present but
                # forced open/collisionless so the room is actually reachable.
                if is_armory_door:
                    new_door.locked = False
                    new_door.target_open = True
                    new_door.anim_progress = 1.0
                    new_door.collision_disabled = True
                    new_door.collision_rect = None
                    new_door.manual_timer = 9999

                STATE.doors.append(new_door)
            elif tile == "P":
                STATE.player = Player(x + 16, y + 16, max_hp=115)
            # "S", "K", "E", "X" are passable visual tiles - no collision.
            # "O", ".", "g" are floor variants - no collision.

    if STATE.player is None:
        # Fallback spawn if the map ever loses its "P".
        sx, sy = PLAYER_START_TILE
        STATE.player = Player(sx * TILE_SIZE + 16, sy * TILE_SIZE + 16, max_hp=115)

    # ── Furniture collision rects ──
    # Each rect matches the drawn sprite's footprint (inset slightly for
    # fair collision). Coordinates must match _draw_cell_details exactly.
    # Interrogation chair (tile 7, 6): 24x18 seat, inset 2px.
    # Stored in the module-level _CHAIR_RECT so _solid_walls can filter it
    # out by identity once the chair breaks (during the breach). We can't
    # tag the Rect itself because pygame.Rect is a C type without __dict__.
    chair_cx = (_MONITOR_TILE_COL + 0.5) * TILE_SIZE
    chair_cy = 6 * TILE_SIZE + TILE_SIZE // 2
    chair_rect = pygame.Rect(
        int(chair_cx) - 10, int(chair_cy) - 6, 20, 14)
    _CHAIR_RECT = chair_rect
    STATE.mission3_barriers.append(chair_rect)
    # Metal cot (west wall, tiles 5, rows 9-12): 22 wide, 3 tiles tall.
    cot_x = int((_CELL_COL_WEST + 0.5) * TILE_SIZE) - 2
    cot_y_top = 9 * TILE_SIZE
    cot_y_bot = 12 * TILE_SIZE
    STATE.mission3_barriers.append(pygame.Rect(
        cot_x - 9, cot_y_top + 2, 18, cot_y_bot - cot_y_top - 4))
    # Stainless sink (NE corner, tile 14, 5): oval basin ~24x16, inset.
    sink_cx = int((_CELL_COL_EAST + 0.5) * TILE_SIZE) - 4
    sink_cy = (_CELL_ROW_NORTH + 0.5) * TILE_SIZE + 2
    STATE.mission3_barriers.append(pygame.Rect(
        sink_cx - 9, int(sink_cy) - 6, 18, 12))

    # ── Kitchen collision rects ──
    # Fridge (tile 3, 21)
    fridge_x = int((3 + 0.5) * TILE_SIZE)
    fridge_y = int((21 + 0.5) * TILE_SIZE)
    STATE.mission3_barriers.append(pygame.Rect(
        fridge_x - 12, fridge_y - 16, 24, 32))

    # Stove (tile 5, 21)
    stove_x = int((5 + 0.5) * TILE_SIZE)
    stove_y = int((21 + 0.5) * TILE_SIZE)
    STATE.mission3_barriers.append(pygame.Rect(
        stove_x - 14, stove_y - 14, 28, 28))

    # Counter (tiles 3-5, row 23)
    counter_x = int((4 + 0.5) * TILE_SIZE)
    counter_y = int((23 + 0.5) * TILE_SIZE)
    STATE.mission3_barriers.append(pygame.Rect(
        counter_x - 30, counter_y - 8, 60, 16))

    # ── Guard-room prop collision rects ──
    # Keep these to wall-hugging fixtures so Guard 3's patrol route remains
    # clean, but the player no longer walks through consoles/lockers/racks.
    # IMPORTANT: do NOT use one long north-wall collision strip. It blocked the
    # guard-room doorway at (22,18), making the room unreachable and causing the
    # guard inside to jitter while trying to path out.
    for _tx in (13, 17, 21, 25, 29, 33):
        STATE.mission3_barriers.append(pygame.Rect(
            _tx * TILE_SIZE + 8,
            19 * TILE_SIZE + 8,
            44, 22))  # individual north console
    STATE.mission3_barriers.append(pygame.Rect(
        13 * TILE_SIZE + 4, 23 * TILE_SIZE + 18,
        3 * TILE_SIZE - 8, 40))  # south lockers
    STATE.mission3_barriers.append(pygame.Rect(
        31 * TILE_SIZE + 4, 23 * TILE_SIZE + 24,
        2 * TILE_SIZE - 8, 24))  # weapon rack

    # ── Background/set-dressing prop collision rects ──
    # Only the larger props get collision. Small stains, pipes, vents, mops,
    # and paper clutter stay cosmetic so traversal remains smooth.
    # Anchors must stay in sync with _M3_DRESSING_PROPS["cell"] in m3/draw.py
    # (a stale anchor here is an invisible wall where nothing is drawn).
    for _cx, _cy, _w, _h in [
        (3.6, 17.7, 76, 42),   # west crate stack
        (44.2, 26.5, 66, 38),  # east crate stack
        (30.2, 28.5, 78, 42),  # hall service crates
        (37.5, 27.2, 72, 34),  # service cart
        (5.8, 44.0, 72, 34),   # south service cart
        (42.9, 13.7, 56, 30),  # barrel cluster near exit background
        (4.6, 28.3, 56, 30),   # west barrel cluster
        (39.5, 44.5, 58, 30),  # south barrel cluster
    ]:
        STATE.mission3_barriers.append(pygame.Rect(
            int(_cx * TILE_SIZE - _w / 2),
            int(_cy * TILE_SIZE - _h / 2),
            int(_w), int(_h)))

    # ── Lower service-wing prop collisions ──
    # Laundry: machine bank, folding table, two carts.
    # Washer bank: five machines at (5.0 + i*1.15) * T, 44px wide each -
    # the rect must span the whole bank (old width missed machine 5).
    STATE.mission3_barriers.append(pygame.Rect(
        5 * TILE_SIZE, 33 * TILE_SIZE, int(4.6 * TILE_SIZE) + 44, 42))
    STATE.mission3_barriers.append(pygame.Rect(int(10.2 * TILE_SIZE), int(36.0 * TILE_SIZE), 176, 40))
    STATE.mission3_barriers.append(pygame.Rect(int(6.1 * TILE_SIZE - 22), int(41.0 * TILE_SIZE - 12), 44, 30))
    STATE.mission3_barriers.append(pygame.Rect(int(15.2 * TILE_SIZE - 22), int(34.9 * TILE_SIZE - 12), 44, 30))
    # Exercise yard: benches + pull-up frames.
    STATE.mission3_barriers.append(pygame.Rect(int(21.5 * TILE_SIZE - 38), int(41.0 * TILE_SIZE - 7), 76, 16))
    STATE.mission3_barriers.append(pygame.Rect(int(27.1 * TILE_SIZE - 38), int(41.0 * TILE_SIZE - 7), 76, 16))
    for _tx, _ty in ((20.4, 35.8), (27.8, 35.8)):
        STATE.mission3_barriers.append(pygame.Rect(int(_tx * TILE_SIZE - 26), int(_ty * TILE_SIZE - 34), 52, 70))
    # Maintenance: boilers, generator.
    # NOTE: the north-wall pipe manifold is drawn inside wall row 31
    # (y ~= 31.4 tiles), which is already solid via STATE.walls - it gets
    # no extra barrier. A thin strip at y ~= 33.0 used to sit ~1.5 tiles
    # south in open "M" floor and read as a ghost pipe wall just inside
    # the door.
    STATE.mission3_barriers.append(pygame.Rect(int(34.0 * TILE_SIZE - 32), int(35.0 * TILE_SIZE - 62), 64, 124))
    STATE.mission3_barriers.append(pygame.Rect(int(42.0 * TILE_SIZE - 36), int(35.4 * TILE_SIZE - 42), 72, 84))
    STATE.mission3_barriers.append(pygame.Rect(int(37.3 * TILE_SIZE), int(38.1 * TILE_SIZE), 128, 58))

    # Guards intentionally do NOT spawn during the interrogation / Volkov breach
    # sequence. They are spawned later, after the chair-leg crafting lock is
    # cleared and the breakout becomes real gameplay.
    _m3s._security_camera = None


def _build_comms_world():
    """Switch to the second Mission 3 map and rebuild world entities.

    Keeps campaign/combat state (HP, K-9 ammo, etc.) but replaces the cell-block
    geometry with the Comms Wing geometry.
    """
    from missions.m3 import systems as _m3s  # lazy: breaks world<->systems cycle
    global _CHAIR_RECT
    _m3_maps.MISSION3_MAP = MISSION3_COMMS_MAP
    _CHAIR_RECT = None
    _m3s._security_camera = None

    old_player = STATE.player
    old_hp = old_player.hp if old_player else 115
    old_max_hp = old_player.max_hp if old_player else 115

    STATE.walls = []
    STATE.enemies = []
    STATE.pickups = []
    STATE.blood_decals = []
    STATE.bullets = []
    STATE.casings = []
    STATE.particles = []
    STATE.floating_texts = []
    STATE.mission3_barriers = []
    STATE.doors = []
    STATE.mission3_detainees = []

    spawn_pos = None
    from core.interactions import Door
    for row_idx, row in enumerate(_m3_maps.MISSION3_MAP):
        for col_idx, tile in enumerate(row):
            x, y = col_idx * TILE_SIZE, row_idx * TILE_SIZE
            if tile in ("C", "g"):
                # In the Comms Wing, ``g`` is outside the authored building,
                # not playable ground. Treating it as walkable let the player
                # squeeze through any visual seam beside a doorway and roam
                # outside the facility shell.
                STATE.walls.append(pygame.Rect(x, y, TILE_SIZE, TILE_SIZE))
            elif tile == "D":
                d = Door(x, y, is_bay=False)
                # Archive access is physically sealed until the relay handshake
                # succeeds. Other Comms Wing doors remain automatic.
                _m3d(d).archive_access = (col_idx == 44 and row_idx == 24)
                d.locked = bool(_m3d(d).archive_access)
                STATE.doors.append(d)
            elif tile == "P":
                spawn_pos = (x + TILE_SIZE // 2, y + TILE_SIZE // 2)

    if old_player is None:
        STATE.player = Player(0, 0, max_hp=old_max_hp)
    else:
        STATE.player = old_player
    STATE.player.hp = min(old_hp, old_max_hp)
    STATE.player.max_hp = old_max_hp
    if spawn_pos is None:
        spawn_pos = (6 * TILE_SIZE + TILE_SIZE // 2, 24 * TILE_SIZE + TILE_SIZE // 2)
    STATE.player.rect.center = spawn_pos

    # Volkov enters this slice as a temporary ally. He stays near Biribel and
    # takes controlled shots at visible guards instead of being a full companion
    # system. This makes the Comms Wing feel like a joint breakout without
    # introducing escort jank.
    STATE.m3_volkov_ally_active = True
    STATE.m3_volkov_ally_x = float(spawn_pos[0] - 54)
    STATE.m3_volkov_ally_y = float(spawn_pos[1] + 22)
    STATE.m3_volkov_ally_angle = 0.0
    STATE.m3_volkov_ally_cooldown = 45
    STATE.m3_volkov_ally_shots = []
    STATE.m3_volkov_ally_max_hp = 220
    STATE.m3_volkov_ally_hp = 220
    STATE.m3_volkov_ally_hit_flash = 0
    STATE.m3_volkov_path = []
    STATE.m3_volkov_path_timer = 0
    STATE.m3_volkov_path_goal = None
    STATE.m3_volkov_stuck_timer = 0
    STATE.m3_volkov_last_pos = (
        float(spawn_pos[0] - 54), float(spawn_pos[1] + 22))
    STATE.m3_relay_active = False
    STATE.m3_relay_timer = 0
    STATE.m3_relay_tuned = False
    STATE.m3_comms_power_restored = False
    STATE.m3_comms_auth_acquired = False
    STATE.m3_comms_ambience_timer = 0

    # Relay/server room collision props. Keep only large fixtures solid.
    for _cx, _cy, _w, _h in [
        (19.8, 16.4, 140, 42),   # relay console bank
        (28.2, 16.4, 140, 42),   # relay console bank
        (24.0, 19.2, 118, 52),   # central table / tuning desk
        (36.0, 18.0, 58, 230),   # server rack west row
        (42.0, 18.0, 58, 230),   # server rack east row
        (17.0, 35.0, 70, 118),   # battery stack
        (27.2, 35.0, 70, 118),   # battery stack
        (37.5, 25.0, 128, 42),   # server workbench
    ]:
        STATE.mission3_barriers.append(pygame.Rect(
            int(_cx * TILE_SIZE - _w / 2), int(_cy * TILE_SIZE - _h / 2), int(_w), int(_h)
        ))

    # Comms-wing guards - separate from cell-block slice.
    _spawn_m3_guard(12, 24, hp=145, speed=1.35,
                    patrol=[(12*TILE_SIZE+32, 24*TILE_SIZE+32), (20*TILE_SIZE+32, 24*TILE_SIZE+32)],
                    facing=0.0, label="comms_corridor_guard", enemy_type="guard")
    _spawn_m3_guard(24, 18, hp=135, speed=1.2,
                    patrol=None, facing=math.pi * 0.5, label="relay_technician", enemy_type="technician")
    _spawn_m3_guard(39, 23, hp=145, speed=1.3,
                    patrol=[(36*TILE_SIZE+32, 23*TILE_SIZE+32), (42*TILE_SIZE+32, 26*TILE_SIZE+32)],
                    facing=math.pi, label="server_marksman", enemy_type="marksman")
    _spawn_m3_guard(22, 35, hp=135, speed=1.75,
                    patrol=[(16*TILE_SIZE+32, 35*TILE_SIZE+32), (28*TILE_SIZE+32, 35*TILE_SIZE+32)],
                    facing=0.0, label="utility_breacher", enemy_type="breacher")
    _spawn_m3_guard(13, 19, hp=130, speed=1.25,
                    patrol=None, facing=math.pi * 0.5, label="security_technician", enemy_type="technician")
    _spawn_m3_guard(36, 21, hp=230, speed=1.0,
                    patrol=[(36*TILE_SIZE+32, 21*TILE_SIZE+32), (36*TILE_SIZE+32, 26*TILE_SIZE+32)],
                    facing=math.pi, label="server_shield", enemy_type="shield")
    _spawn_m3_guard(43, 24, hp=155, speed=1.25,
                    patrol=None, facing=math.pi, label="archive_marksman", enemy_type="marksman")
    _spawn_m3_guard(28, 18, hp=130, speed=1.75,
                    patrol=[(20*TILE_SIZE+32, 18*TILE_SIZE+32), (29*TILE_SIZE+32, 18*TILE_SIZE+32)],
                    facing=math.pi, label="relay_breacher", enemy_type="breacher")

    STATE.minimap = MiniMap(_m3_maps.MISSION3_MAP, palette="m3")
    reset_camera_state()
    _snap_camera_to(STATE.player.rect.center)



# ── Slice 5: Kill Order ground floor constants ──────────────────────
_KO_SPAWN_COL, _KO_SPAWN_ROW = 6, 3
_KO_EXFIL_COL, _KO_EXFIL_ROW = 33, 36          # Volkov's van (dock)
_KO_INSERT_TILES = ((6, 29), (19, 29), (31, 29))   # sweep routes (5b)
_KO_MEZZ_TILE = (26, 24)                        # marksman nest (5c)
# (col, row) doors that start locked and open to breacher charges / holdout:
_KO_BREACH_DOORS = ((13, 12), (13, 20), (31, 32), (32, 32))
# (col, row) -> wave index that must clear before the gate blows open.
# The lobby->south row (wave 0 = stair ambush) and the south->dock row
# (wave 1 = lobby marksman + probes) stay sealed until the player has
# actually fought the authored beat - a stairwell->van sprint must cross
# the action, not skip it (playability fix 2026-09-27: the sprint used to
# hit an empty dock and park on "HOLDOUT LOCKED" while the sweep hunted
# ghosts). The (31,32)/(32,32) dock side door is deliberately NOT here:
# the 5d holdout owns it.
_KO_BEAT_GATES = {
    (9, 27): 0, (10, 27): 0,
    (19, 27): 0, (20, 27): 0,
    (31, 27): 0, (32, 27): 0,
    (6, 32): 1, (7, 32): 1,
    (19, 32): 1, (20, 32): 1,
}
_KO_PICKUPS = (
    (11, 13, "mag"), (12, 13, "bandage"),
    (11, 20, "sidearm"), (12, 21, "bandage"),
    (26, 23, "mag"),
    (6, 36, "bandage"),
)


def _exfil_pos():
    return (
        _KO_EXFIL_COL * TILE_SIZE + TILE_SIZE // 2,
        _KO_EXFIL_ROW * TILE_SIZE + TILE_SIZE // 2,
    )


def _build_kill_order_world():
    """Switch to the Kill Order ground floor and rebuild world entities.

    Keeps the combat loadout and the Vostral flag from the Archives. Volkov
    (if still up as ally) descends with Biribel - re-anchored beside the
    player so his follow-A* restarts cleanly on the new map.
    """
    from missions.m3 import systems as _m3s  # lazy: breaks world<->systems cycle
    global _CHAIR_RECT
    _m3_maps.MISSION3_MAP = MISSION3_KILL_ORDER_MAP
    _CHAIR_RECT = None
    _m3s._security_camera = None

    old_player = STATE.player
    old_hp = old_player.hp if old_player else 115
    old_max_hp = old_player.max_hp if old_player else 115

    STATE.walls = []
    STATE.enemies = []
    STATE.pickups = []
    STATE.blood_decals = []
    STATE.corpses = []
    STATE.bullets = []
    STATE.casings = []
    STATE.particles = []
    STATE.floating_texts = []
    STATE.mission3_barriers = []
    STATE.doors = []
    STATE.mission3_detainees = []
    STATE.m3_volkov_ally_shots = []
    STATE.m3_volkov_path = []
    STATE.m3_volkov_path_timer = 0
    STATE.m3_volkov_path_goal = None
    STATE.m3_volkov_stuck_timer = 0
    STATE.m3_volkov_mags = []

    spawn_pos = None
    from core.interactions import Door
    for row_idx, row in enumerate(_m3_maps.MISSION3_MAP):
        for col_idx, tile in enumerate(row):
            x, y = col_idx * TILE_SIZE, row_idx * TILE_SIZE
            if tile in ("C", "g"):
                STATE.walls.append(pygame.Rect(x, y, TILE_SIZE, TILE_SIZE))
            elif tile == "B":
                inset = 10
                STATE.mission3_barriers.append(pygame.Rect(
                    x + inset, y + inset, TILE_SIZE - inset * 2, TILE_SIZE - inset * 2))
            elif tile == "D":
                d = Door(x, y, is_bay=False)
                is_breach = (col_idx, row_idx) in _KO_BREACH_DOORS
                _m3d(d).ko_breach = is_breach
                _m3d(d).ko_beat_gate = _KO_BEAT_GATES.get((col_idx, row_idx))
                d.locked = bool(is_breach or _m3d(d).ko_beat_gate is not None)
                STATE.doors.append(d)
            elif tile == "P":
                spawn_pos = (x + TILE_SIZE // 2, y + TILE_SIZE // 2)

    if spawn_pos is None:
        spawn_pos = (
            _KO_SPAWN_COL * TILE_SIZE + TILE_SIZE // 2,
            _KO_SPAWN_ROW * TILE_SIZE + TILE_SIZE // 2,
        )

    if old_player is None:
        STATE.player = Player(0, 0, max_hp=old_max_hp)
    else:
        STATE.player = old_player
    STATE.player.hp = min(old_hp, old_max_hp)
    STATE.player.max_hp = old_max_hp
    STATE.player.rect.center = spawn_pos

    for pc, pr, kind in _KO_PICKUPS:
        STATE.pickups.append([
            pc * TILE_SIZE + TILE_SIZE // 2,
            pr * TILE_SIZE + TILE_SIZE // 2, kind])

    # Volkov descends with you if he is still on his feet.
    if getattr(STATE, "m3_volkov_ally_active", False):
        STATE.m3_volkov_ally_x = float(spawn_pos[0] - 40)
        STATE.m3_volkov_ally_y = float(spawn_pos[1] + 24)

    from core.camera import reset_camera_state
    reset_camera_state()
    STATE.m3_ko_world_built = True


# ── Slice 6: Broadcast Wing constants ────────────────────────────────
_BCAST_SPAWN_COL, _BCAST_SPAWN_ROW = 15, 2
_BCAST_UPLINK_COL, _BCAST_UPLINK_ROW = 15, 26
_BCAST_GATE_DOORS = ((14, 16), (15, 16), (16, 16), (17, 16))
# Upload PC station: inside the PC vault of the east suite (the micro-room
# behind the antechamber), so the upload is fought for inside a real space.
_BCAST_PC_COL, _BCAST_PC_ROW = 25, 27
# The suite the PC lives in, for the "protectors know where you are" spawn.
_BCAST_PC_ROOM = (24, 21, 27, 28)
# Studio arena - everything from the gate down to the booth walls.
_BCAST_STUDIO_RECT = (3, 16, 28, 29)
_BCAST_PICKUPS = (
    (7, 8, "bandage"),
    (24, 8, "mag"),
    (10, 22, "bandage"),
    (22, 22, "mag"),
)


def _bcast_uplink_pos():
    return (
        _BCAST_UPLINK_COL * TILE_SIZE + TILE_SIZE // 2,
        _BCAST_UPLINK_ROW * TILE_SIZE + TILE_SIZE // 2,
    )


def _bcast_pc_pos():
    return (
        _BCAST_PC_COL * TILE_SIZE + TILE_SIZE // 2,
        _BCAST_PC_ROW * TILE_SIZE + TILE_SIZE // 2,
    )


def _build_broadcast_world():
    """Switch to the Broadcast Wing studio floor and rebuild world entities.

    Keeps combat loadout (HP, K-9, etc.) from the Kill Order. Volkov is gone
    (bailed or committed in KO). This slice is Biribel alone against studio
    security, racing the 22:00 address clock.
    """
    from missions.m3 import systems as _m3s  # lazy: breaks world<->systems cycle
    global _CHAIR_RECT
    _m3_maps.MISSION3_MAP = MISSION3_BROADCAST_MAP
    _CHAIR_RECT = None
    _m3s._security_camera = None

    old_player = STATE.player
    old_hp = old_player.hp if old_player else 115
    old_max_hp = old_player.max_hp if old_player else 115

    STATE.walls = []
    STATE.enemies = []
    STATE.pickups = []
    STATE.blood_decals = []
    STATE.corpses = []
    STATE.bullets = []
    STATE.casings = []
    STATE.particles = []
    STATE.floating_texts = []
    STATE.mission3_barriers = []
    STATE.doors = []
    STATE.mission3_detainees = []
    STATE.m3_volkov_ally_shots = []
    STATE.m3_volkov_path = []
    STATE.m3_volkov_path_timer = 0
    STATE.m3_volkov_path_goal = None
    STATE.m3_volkov_stuck_timer = 0
    STATE.m3_volkov_mags = []

    spawn_pos = None
    from core.interactions import Door
    for row_idx, row in enumerate(_m3_maps.MISSION3_MAP):
        for col_idx, tile in enumerate(row):
            x, y = col_idx * TILE_SIZE, row_idx * TILE_SIZE
            if tile in ("C", "g"):
                STATE.walls.append(pygame.Rect(x, y, TILE_SIZE, TILE_SIZE))
            elif tile == "B":
                inset = 10
                STATE.mission3_barriers.append(pygame.Rect(
                    x + inset, y + inset, TILE_SIZE - inset * 2, TILE_SIZE - inset * 2))
            elif tile == "D":
                d = Door(x, y, is_bay=False)
                is_gate = (col_idx, row_idx) in _BCAST_GATE_DOORS
                _m3d(d).bcast_gate = is_gate
                d.locked = is_gate
                STATE.doors.append(d)
            elif tile == "P":
                spawn_pos = (x + TILE_SIZE // 2, y + TILE_SIZE // 2)

    if spawn_pos is None:
        spawn_pos = (
            _BCAST_SPAWN_COL * TILE_SIZE + TILE_SIZE // 2,
            _BCAST_SPAWN_ROW * TILE_SIZE + TILE_SIZE // 2,
        )

    if old_player is None:
        STATE.player = Player(0, 0, max_hp=old_max_hp)
    else:
        STATE.player = old_player
    STATE.player.hp = min(old_hp, old_max_hp)
    STATE.player.max_hp = old_max_hp
    STATE.player.rect.center = spawn_pos

    # Volkov rejoins for the finale beside Biribel in the entry vestibule:
    # same follow-and-cover-fire ally as Comms/Archives. Bail flags from
    # Kill Order are cleared so he holds the floor through the upload.
    STATE.m3_volkov_ally_active = True
    STATE.m3_volkov_bailed = False
    STATE.m3_volkov_bail_timer = 0
    STATE.m3_volkov_ally_x = float(spawn_pos[0] - 54)
    STATE.m3_volkov_ally_y = float(spawn_pos[1] + 22)
    STATE.m3_volkov_ally_angle = 0.0
    STATE.m3_volkov_ally_cooldown = 30
    STATE.m3_volkov_ally_max_hp = 220
    STATE.m3_volkov_ally_hp = 220
    STATE.m3_volkov_ally_hit_flash = 0
    STATE.m3_volkov_path = []
    STATE.m3_volkov_path_timer = 0
    STATE.m3_volkov_path_goal = None
    STATE.m3_volkov_stuck_timer = 0
    STATE.m3_volkov_last_pos = (
        float(spawn_pos[0] - 54), float(spawn_pos[1] + 22))
    STATE.m3_volkov_mags_thrown_count = 0

    for pc, pr, kind in _BCAST_PICKUPS:
        STATE.pickups.append([
            pc * TILE_SIZE + TILE_SIZE // 2,
            pr * TILE_SIZE + TILE_SIZE // 2, kind])

    STATE.minimap = MiniMap(_m3_maps.MISSION3_MAP, palette="m3")
    from core.camera import reset_camera_state
    reset_camera_state()
    STATE.m3_bcast_world_built = True


def _build_archives_world():
    """Switch to the Archives Wing map and rebuild world entities.

    Keeps combat loadout (HP, K-9, etc.) from the Comms Wing. Volkov stays
    behind to hold the relay - this slice is Biribel alone with Maru's ghost
    in the system and the Vostral file under glass.
    """
    from missions.m3 import systems as _m3s  # lazy: breaks world<->systems cycle
    global _CHAIR_RECT
    _m3_maps.MISSION3_MAP = MISSION3_ARCHIVES_MAP
    _CHAIR_RECT = None
    _m3s._security_camera = None

    old_player = STATE.player
    old_hp = old_player.hp if old_player else 115
    old_max_hp = old_player.max_hp if old_player else 115

    STATE.walls = []
    STATE.enemies = []
    STATE.pickups = []
    STATE.blood_decals = []
    STATE.bullets = []
    STATE.casings = []
    STATE.particles = []
    STATE.floating_texts = []
    STATE.mission3_barriers = []
    STATE.doors = []
    STATE.mission3_detainees = []

    # Volkov comes through with Biribel - same temporary ally as Comms.
    STATE.m3_volkov_ally_shots = []
    STATE.m3_volkov_path = []
    STATE.m3_volkov_path_timer = 0
    STATE.m3_volkov_path_goal = None
    STATE.m3_volkov_stuck_timer = 0
    STATE.m3_volkov_mags = []

    spawn_pos = None
    from core.interactions import Door
    for row_idx, row in enumerate(_m3_maps.MISSION3_MAP):
        for col_idx, tile in enumerate(row):
            x, y = col_idx * TILE_SIZE, row_idx * TILE_SIZE
            if tile in ("C", "g"):
                STATE.walls.append(pygame.Rect(x, y, TILE_SIZE, TILE_SIZE))
            elif tile == "B":
                # Atrium pillar cover - solid inset barrier, not full wall tile.
                inset = 10
                STATE.mission3_barriers.append(pygame.Rect(
                    x + inset, y + inset, TILE_SIZE - inset * 2, TILE_SIZE - inset * 2))
            elif tile == "D":
                d = Door(x, y, is_bay=False)
                is_vault = (
                    col_idx in _VOSTRAL_DOOR_COLS
                    and row_idx in _VOSTRAL_DOOR_ROWS
                )
                is_kill_order_exit = (
                    col_idx in _EXIT_DOOR_COLS
                    and row_idx in _EXIT_DOOR_ROWS
                )
                _m3d(d).vostral_vault = is_vault
                _m3d(d).kill_order_exit = is_kill_order_exit
                d.locked = bool(is_vault or is_kill_order_exit)
                STATE.doors.append(d)
            elif tile == "P":
                spawn_pos = (x + TILE_SIZE // 2, y + TILE_SIZE // 2)

    if old_player is None:
        STATE.player = Player(0, 0, max_hp=old_max_hp)
    else:
        STATE.player = old_player
    STATE.player.hp = min(old_hp, old_max_hp)
    STATE.player.max_hp = old_max_hp
    if spawn_pos is None:
        spawn_pos = (
            _ARCHIVES_SPAWN_COL * TILE_SIZE + TILE_SIZE // 2,
            _ARCHIVES_SPAWN_ROW * TILE_SIZE + TILE_SIZE // 2,
        )
    STATE.player.rect.center = spawn_pos
    # Face north into the atrium on arrival.
    STATE.player.angle = -math.pi / 2

    # Volkov spawns beside Biribel in the elevator lobby.
    STATE.m3_volkov_ally_active = True
    STATE.m3_volkov_ally_x = float(spawn_pos[0] - 54)
    STATE.m3_volkov_ally_y = float(spawn_pos[1] + 28)
    STATE.m3_volkov_ally_angle = -math.pi / 2
    STATE.m3_volkov_ally_cooldown = 30
    STATE.m3_volkov_ally_max_hp = 220
    STATE.m3_volkov_ally_hp = 220
    STATE.m3_volkov_ally_hit_flash = 0
    STATE.m3_volkov_last_pos = (
        float(spawn_pos[0] - 54), float(spawn_pos[1] + 28))
    STATE.m3_volkov_mags_thrown_count = 0

    # Phase-4 progress flags (fresh on each world build).
    STATE.m3_archives_cleared = False
    STATE.m3_maru_contacted = False
    STATE.m3_maru_contact_active = False
    STATE.m3_maru_contact_timer = 0
    STATE.m3_vostral_acquired = False
    STATE.m3_archives_ambience_timer = 0
    STATE.m3_archives_alarm = False

    # Furniture / shelf collision - placed to match the new vertical layout.
    for _cx, _cy, _w, _h in [
        # Elevator lobby desk
        (24.0, 44.0, 140, 36),
        # West catalog end-caps (extra cover at aisle mouths)
        (8.5, 22.0, 40, 90),
        (14.5, 22.0, 40, 90),
        (8.5, 33.0, 40, 90),
        (14.5, 33.0, 40, 90),
        # Maru clerk desk
        (11.0, 12.0, 96, 48),
        # Research cubicle desks
        (34.0, 22.0, 70, 40),
        (38.0, 22.0, 70, 40),
        (34.0, 32.0, 70, 40),
        (38.0, 32.0, 70, 40),
        # Vault pedestal base
        (42.0, 9.0, 70, 70),
        # Vestibule card-catalog island
        (28.0, 9.0, 120, 40),
    ]:
        STATE.mission3_barriers.append(pygame.Rect(
            int(_cx * TILE_SIZE - _w / 2),
            int(_cy * TILE_SIZE - _h / 2),
            int(_w), int(_h),
        ))

    # Archives security - placed for the vertical atrium layout.
    _spawn_m3_guard(
        24, 34, hp=150, speed=1.35,
        patrol=[(24 * TILE_SIZE + 32, 34 * TILE_SIZE + 32),
                (24 * TILE_SIZE + 32, 18 * TILE_SIZE + 32)],
        facing=-math.pi / 2, label="atrium_patrol", enemy_type="guard",
    )
    _spawn_m3_guard(
        12, 26, hp=140, speed=1.2,
        patrol=[(6 * TILE_SIZE + 32, 26 * TILE_SIZE + 32),
                (18 * TILE_SIZE + 32, 26 * TILE_SIZE + 32)],
        facing=0.0, label="stacks_clerk_guard", enemy_type="technician",
    )
    _spawn_m3_guard(
        8, 32, hp=155, speed=1.3,
        patrol=[(8 * TILE_SIZE + 32, 21 * TILE_SIZE + 32),
                (8 * TILE_SIZE + 32, 34 * TILE_SIZE + 32)],
        facing=math.pi / 2, label="stacks_marksman", enemy_type="marksman",
    )
    _spawn_m3_guard(
        11, 14, hp=145, speed=1.25,
        patrol=None, facing=math.pi / 2,
        label="maru_office_guard", enemy_type="guard",
    )
    _spawn_m3_guard(
        34, 26, hp=150, speed=1.75,
        patrol=[(30 * TILE_SIZE + 32, 26 * TILE_SIZE + 32),
                (41 * TILE_SIZE + 32, 26 * TILE_SIZE + 32)],
        facing=math.pi, label="research_breacher", enemy_type="breacher",
    )
    _spawn_m3_guard(
        38, 21, hp=160, speed=1.3,
        patrol=None, facing=math.pi,
        label="cubicle_marksman", enemy_type="marksman",
    )
    # Vestibule shield - NEVER inside the locked vault (that soft-locked
    # "clear hostiles" because the player could not reach the last enemy).
    _spawn_m3_guard(
        33, 9, hp=240, speed=1.0,
        patrol=[(30 * TILE_SIZE + 32, 9 * TILE_SIZE + 32),
                (35 * TILE_SIZE + 32, 9 * TILE_SIZE + 32)],
        facing=0.0, label="vault_shield", enemy_type="shield",
    )
    _spawn_m3_guard(
        24, 10, hp=155, speed=1.4,
        patrol=[(22 * TILE_SIZE + 32, 10 * TILE_SIZE + 32),
                (32 * TILE_SIZE + 32, 10 * TILE_SIZE + 32)],
        facing=0.0, label="vestibule_guard", enemy_type="guard",
    )

    STATE.minimap = MiniMap(_m3_maps.MISSION3_MAP, palette="m3")
    reset_camera_state()
    _snap_camera_to(STATE.player.rect.center)


def _spawn_m3_guards_once(force=False):
    """Spawn Mission 3 guards only after Volkov's scripted breach is over.

    They used to exist from mission start, which meant they could gather around
    Biribel's cell during the in-game Volkov cutscene and jitter against the
    locked doorway. Spawning here keeps the cinematic clean and starts combat
    only once the player has a shiv / the doorway is no longer blocked.

    ``force=True`` re-arms the cell block for a checkpoint restart. Death
    restarts call ``start_mission3()``, whose ``STATE.reset()`` puts every
    checkpoints' flags back to False while KEEPING ``m3_volkov_run_done``
    satisfied - so the normal gate below would refuse to spawn and the player
    would respawn into an empty map with nothing to kill and no pistol drop.
    """
    from missions.m3.systems import SecurityCamera, _CAMERA_TILE_COL, _CAMERA_TILE_ROW  # lazy: breaks world<->systems cycle
    from missions.m3 import systems as _m3s  # lazy: _security_camera writes
    if force:
        STATE.mission3_guards_spawned = False
    if getattr(STATE, "mission3_guards_spawned", False):
        return
    # Do not spawn while Volkov is still visibly running/fading out. Otherwise
    # guards can appear during his scripted distraction and start colliding with
    # the cell/doorway beats. Checkpoint restarts have already played his run
    # (m3_volkov_run_done is set and run_active is False), so they skip the wait.
    if not getattr(STATE, "m3_volkov_run_done", False):
        return
    STATE.mission3_guards_spawned = True
    STATE.enemies = []
    # ── Spawn the five IPA cell-block guards ──
    # Guard 1 - main corridor east, east-west patrol.
    _spawn_m3_guard(
        *_GUARD_POST_1_TILE,
        hp=140, speed=1.4,
        patrol=_PATROL_ROUTE_1,
        facing=math.pi,          # facing west (toward corridor)
        label="guard_post_1",
        enemy_type="guard",
    )
    # Guard 2 - main corridor centre, stationary, looking north toward cells.
    _spawn_m3_guard(
        *_GUARD_POST_2_TILE,
        hp=135, speed=1.4,
        patrol=None,
        facing=math.pi * 1.5,    # facing north
        label="guard_post_2",
        enemy_type="marksman",
    )
    # Guard 3 - guard room interior, patrols east-west inside the room.
    _spawn_m3_guard(
        *_GUARD_POST_3_TILE,
        hp=150, speed=1.4,
        patrol=_PATROL_ROUTE_3,
        facing=0.0,              # facing east
        label="guard_post_3",
        enemy_type="guard",
    )
    # Guard 4 - kitchen area, stationary, facing the vent.
    _spawn_m3_guard(
        *_GUARD_POST_4_TILE,
        hp=130, speed=1.2,
        patrol=None,
        facing=math.pi * 0.5,    # facing south
        label="guard_post_4",
        enemy_type="breacher",
    )
    # Guard 5 - main corridor west, east-west patrol.
    _spawn_m3_guard(
        *_GUARD_POST_5_TILE,
        hp=135, speed=1.4,
        patrol=_PATROL_ROUTE_5,
        facing=0.0,              # facing east
        label="guard_post_5",
        enemy_type="guard",
    )
    # Guard 6 - armory patrol. Makes the K-9 pickup feel earned.
    _spawn_m3_guard(
        *_GUARD_POST_6_TILE,
        hp=165, speed=1.35,
        patrol=_PATROL_ROUTE_6,
        facing=math.pi,          # facing west across the rack room
        label="guard_armory",
        enemy_type="shield",
    )
    # Guard 7 - service-exit checkpoint. Blocks the final sprint unless cleared.
    _spawn_m3_guard(
        *_GUARD_POST_7_TILE,
        hp=160, speed=1.35,
        patrol=None,
        facing=math.pi,          # facing west into the corridor
        label="guard_exit_checkpoint",
        enemy_type="marksman",
    )
    # Guard 8 - second guard-room patrol so the big room is not empty.
    _spawn_m3_guard(
        *_GUARD_POST_8_TILE,
        hp=145, speed=1.4,
        patrol=_PATROL_ROUTE_8,
        facing=math.pi,          # facing west
        label="guard_room_east",
        enemy_type="technician",
    )
    # Guard 9 - lower service spine breacher, makes the expanded wing matter.
    _spawn_m3_guard(
        24, 27,
        hp=135, speed=1.75,
        patrol=[(18*TILE_SIZE+32, 27*TILE_SIZE+32), (31*TILE_SIZE+32, 27*TILE_SIZE+32)],
        facing=math.pi,
        label="guard_service_breacher",
        enemy_type="breacher",
    )
    # Guard 10 - maintenance shield guard, slow pressure enemy.
    _spawn_m3_guard(
        38, 37,
        hp=230, speed=1.0,
        patrol=[(36*TILE_SIZE+32, 37*TILE_SIZE+32), (42*TILE_SIZE+32, 37*TILE_SIZE+32)],
        facing=math.pi,
        label="guard_maintenance_shield",
        enemy_type="shield",
    )

    # ── Security camera in the kitchen ──
    _m3s._security_camera = SecurityCamera(_CAMERA_TILE_COL, _CAMERA_TILE_ROW,
                                      angle=math.radians(100))  # looking SW



# ─────────────────────────────────────────────
# Ambient detainees - non-combat life in the black-site
# ─────────────────────────────────────────────
def _init_m3_detainees():
    """Populate non-combat prisoners/workers.

    These are not Enemy objects: no minimap dots, no aim-assist target, no
    collision. They exist to make the prison feel inhabited without adding an
    escort/quest system.
    """
    def _w(tx, ty):
        return tx * TILE_SIZE + TILE_SIZE // 2, ty * TILE_SIZE + TILE_SIZE // 2

    specs = [
        # Neighbor cells - quiet silhouettes that make the decorated cells feel occupied.
        ("cell_bars", 9.4, 8.2, "bars", "cell", 101, "..."),
        ("cell_sit", 17.5, 8.8, "sit", "cell", 102, "keep moving"),
        ("cell_huddle", 26.0, 10.2, "cower", "cell", 103, "don't look back"),

        # Laundry - forced-labor / uniform processing, not story-critical.
        ("laundry_fold", 12.2, 36.6, "fold", "laundry", 201, "they check the carts"),
        ("laundry_cart", 6.7, 40.4, "lean", "laundry", 202, "go"),
        ("laundry_wall", 15.3, 38.5, "stand", "laundry", 203, "not me"),

        # Rec yard - most visible ambient population.
        ("yard_pacer", 21.2, 35.7, "pace_x", "yard", 301, "door's open?"),
        ("yard_fence", 28.4, 40.2, "bars", "yard", 302, "quiet"),
        ("yard_sit", 22.2, 41.1, "sit", "yard", 303, "please"),
        ("yard_push", 24.5, 38.2, "pushup", "yard", 304, ""),
        ("yard_stand", 27.0, 35.3, "stand", "yard", 305, "don't shoot"),

        # Maintenance - forced-labor silhouettes.
        ("maint_worker", 33.5, 38.8, "worker", "maintenance", 401, "valve's stuck"),
        ("maint_crouch", 41.0, 39.6, "cower", "maintenance", 402, ""),
    ]

    STATE.mission3_detainees = []
    for name, tx, ty, pose, room, seed, line in specs:
        x, y = _w(tx, ty)
        STATE.mission3_detainees.append({
            "name": name,
            "x": x,
            "y": y,
            "base_x": x,
            "base_y": y,
            "pose": pose,
            "room": room,
            "seed": seed,
            "line": line,
            "line_timer": 0,
            "cooldown": 90 + (seed % 160),
            "state": "idle",
            "timer": 0,
        })


def _update_m3_detainees():
    detainees = getattr(STATE, "mission3_detainees", [])
    if not detainees:
        return

    threat = bool(getattr(STATE, "m3_alarm_active", False))
    threat = threat or any(getattr(e, "state", "") in ("CHASE", "ATTACK") or getattr(e, "alerted", False)
                           for e in getattr(STATE, "enemies", []))
    threat = threat or any(b.get("owner") in ("player", "enemy") for b in getattr(STATE, "bullets", []))

    px = STATE.player.rect.centerx if STATE.player else 0
    py = STATE.player.rect.centery if STATE.player else 0

    for d in detainees:
        if d.get("dead"):
            d["line_timer"] = 0
            continue
        d["timer"] = d.get("timer", 0) + 1
        d["state"] = "cower" if threat else "idle"
        if d.get("line_timer", 0) > 0:
            d["line_timer"] -= 1
        d["cooldown"] = max(0, d.get("cooldown", 0) - 1)

        # ── Foley: shuffle on pose change, plus a rare idle weight-shift ──
        pose_now = d.get("pose", "stand")
        if STATE.player is not None and (
                pose_now != d.get("_last_pose", pose_now)
                or _rng_legacy.random() < 0.004):
            audio.play_3d(
                "detainee_shuffle",
                (d.get("base_x", 0), d.get("base_y", 0)),
                (STATE.player.rect.centerx, STATE.player.rect.centery),
                max_dist=420,
                base_volume=0.28,
            )
        d["_last_pose"] = pose_now

        # Very light, local barks when the player passes close. No global quest,
        # no pinned radio spam.
        if (not threat and d.get("line") and d.get("cooldown", 0) <= 0
                and math.hypot(px - d["base_x"], py - d["base_y"]) < 130):
            d["line_timer"] = 115
            d["cooldown"] = 520 + (d.get("seed", 0) % 180)


def _detainee_draw_pos(d):
    x, y = d.get("base_x", d.get("x", 0)), d.get("base_y", d.get("y", 0))
    if d.get("state") != "cower" and d.get("pose") == "pace_x":
        x += math.sin(d.get("timer", 0) * 0.025 + d.get("seed", 0)) * 28
    return x, y


def _detainee_palette(seed, room="yard"):
    """Readable prisoner palette.

    Previous detainees were too muted/round and read like floor props. These
    colors make them identifiable as people in facility clothing without
    making them look like enemies.
    """
    rng = random.Random(seed)
    if room == "maintenance":
        cloth = rng.choice([(62, 72, 68), (70, 76, 64), (56, 66, 66)])
        stripe = (178, 138, 55)  # work-detail armband/stripe
    elif room == "laundry":
        cloth = rng.choice([(76, 88, 88), (66, 82, 86), (82, 82, 72)])
        stripe = (155, 176, 170)
    elif room == "cell":
        cloth = rng.choice([(74, 66, 52), (68, 72, 66), (78, 70, 58)])
        stripe = (160, 126, 68)
    else:
        cloth = rng.choice([(86, 76, 56), (92, 82, 60), (72, 78, 70), (82, 72, 54)])
        stripe = (190, 145, 64)  # dirty prison-orange accent
    cloth_dark = (max(0, cloth[0] - 30), max(0, cloth[1] - 30), max(0, cloth[2] - 30))
    cloth_hi = (min(255, cloth[0] + 22), min(255, cloth[1] + 22), min(255, cloth[2] + 18))
    skin = rng.choice([(158, 118, 88), (176, 132, 96), (122, 90, 70),
                       (194, 152, 112), (144, 102, 78)])
    hair = rng.choice([(18, 14, 12), (32, 24, 18), (48, 38, 26), (70, 58, 42)])
    outline = (8, 9, 9)
    cuff = (36, 38, 36)
    return cloth, cloth_dark, cloth_hi, stripe, skin, hair, outline, cuff


def _draw_detainee_shadow(surface, sx, sy, w=30, h=10, alpha=62):
    sh = pygame.Surface((w, h), pygame.SRCALPHA)
    pygame.draw.ellipse(sh, (0, 0, 0, alpha), sh.get_rect())
    surface.blit(sh, (int(sx - w // 2), int(sy + 11)))


def _poly_rot(cx, cy, angle, pts):
    ca, sa = math.cos(angle), math.sin(angle)
    return [(cx + x * ca - y * sa, cy + x * sa + y * ca) for x, y in pts]


def _draw_rot_line(surface, color, cx, cy, angle, p1, p2, width=1):
    a = _poly_rot(cx, cy, angle, [p1, p2])
    pygame.draw.line(surface, color, a[0], a[1], width)


def _draw_prisoner_core(surface, sx, sy, d, *, facing=None, crouched=False, seated=False):
    """Draw an articulated prisoner-shaped top-down sprite.

    Uses the same scale language as player/enemy sprites: visible head, torso,
    arms, feet, clothing stripe, cuffs. This should read as a person, not a
    decorative blob.
    """
    seed = d.get("seed", 0)
    room = d.get("room", "yard")
    cloth, cloth_dark, cloth_hi, stripe, skin, hair, outline, cuff = _detainee_palette(seed, room)
    if facing is None:
        facing = (seed % 628) / 100.0
    if d.get("state") == "cower":
        crouched = True
    sway = 0 if crouched or seated else math.sin(d.get("timer", 0) * 0.035 + seed) * 0.8
    sy += sway
    ca, sa = math.cos(facing), math.sin(facing)
    px, py = -sa, ca

    if seated:
        _draw_detainee_shadow(surface, sx, sy, 36, 12, 54)
        # Bent legs, torso and head clearly separate.
        torso = _poly_rot(sx, sy, facing, [(-10, -7), (9, -7), (10, 8), (0, 13), (-11, 8)])
        pygame.draw.polygon(surface, outline, torso)
        inner = _poly_rot(sx, sy, facing, [(-7, -5), (7, -5), (8, 6), (0, 10), (-8, 6)])
        pygame.draw.polygon(surface, cloth, inner)
        _draw_rot_line(surface, stripe, sx, sy, facing, (-7, -1), (7, -1), 2)
        # Legs forward in a V.
        for side in (-1, 1):
            hip = _poly_rot(sx, sy, facing, [(side * 5, 8)])[0]
            knee = (hip[0] - ca * 10 + px * side * 6, hip[1] - sa * 10 + py * side * 6)
            foot = (knee[0] - ca * 7 + px * side * 5, knee[1] - sa * 7 + py * side * 5)
            pygame.draw.line(surface, outline, hip, foot, 5)
            pygame.draw.line(surface, cloth_dark, hip, foot, 3)
            pygame.draw.ellipse(surface, outline, (int(foot[0] - 4), int(foot[1] - 2), 8, 5))
        # Head tucked near chest.
        hx, hy = _poly_rot(sx, sy, facing, [(0, -16)])[0]
        pygame.draw.circle(surface, outline, (int(hx), int(hy)), 7)
        pygame.draw.circle(surface, skin, (int(hx), int(hy)), 6)
        pygame.draw.arc(surface, hair, (int(hx - 6), int(hy - 8), 12, 11), math.pi, math.tau, 3)
        return

    if crouched:
        # Compact, but still person-shaped: head + back + arms over head.
        _draw_detainee_shadow(surface, sx, sy, 32, 12, 68)
        torso = _poly_rot(sx, sy, facing, [(-13, -6), (10, -8), (15, 5), (3, 13), (-13, 9)])
        pygame.draw.polygon(surface, outline, torso)
        inner = _poly_rot(sx, sy, facing, [(-10, -4), (7, -6), (11, 4), (2, 10), (-10, 7)])
        pygame.draw.polygon(surface, cloth_dark, inner)
        hx, hy = _poly_rot(sx, sy, facing, [(-4, -13)])[0]
        pygame.draw.circle(surface, outline, (int(hx), int(hy)), 7)
        pygame.draw.circle(surface, skin, (int(hx), int(hy)), 6)
        pygame.draw.arc(surface, hair, (int(hx - 6), int(hy - 8), 12, 11), math.pi, math.tau, 3)
        # Forearms over head.
        a1 = _poly_rot(sx, sy, facing, [(-12, -5), (-3, -15)])[0]
        a2 = _poly_rot(sx, sy, facing, [(7, -4), (-2, -15)])[0]
        pygame.draw.line(surface, outline, a1, a2, 4)
        pygame.draw.line(surface, cloth_hi, a1, a2, 2)
        return

    _draw_detainee_shadow(surface, sx, sy, 28, 10, 55)

    # Legs / shoes first.
    for side in (-1, 1):
        hip = _poly_rot(sx, sy, facing, [(side * 5, -5)])[0]
        foot = _poly_rot(sx, sy, facing, [(side * 6, -17)])[0]
        pygame.draw.line(surface, outline, hip, foot, 5)
        pygame.draw.line(surface, cloth_dark, hip, foot, 3)
        pygame.draw.ellipse(surface, outline, (int(foot[0] - 4), int(foot[1] - 2), 8, 5))

    # Torso/shoulders.
    torso = _poly_rot(sx, sy, facing, [(-9, -7), (9, -7), (11, 7), (0, 13), (-11, 7)])
    pygame.draw.polygon(surface, outline, torso)
    inner = _poly_rot(sx, sy, facing, [(-7, -5), (7, -5), (8, 6), (0, 10), (-8, 6)])
    pygame.draw.polygon(surface, cloth, inner)
    _draw_rot_line(surface, cloth_hi, sx, sy, facing, (-5, -4), (5, -4), 1)
    _draw_rot_line(surface, stripe, sx, sy, facing, (-7, 0), (7, 0), 2)
    # Tiny ID patch / wrist cuffs.
    patch = _poly_rot(sx, sy, facing, [(4, 4)])[0]
    pygame.draw.rect(surface, stripe, (int(patch[0] - 1), int(patch[1] - 1), 3, 2))

    # Arms hang low, no weapons.
    for side in (-1, 1):
        shoulder = _poly_rot(sx, sy, facing, [(side * 9, -3)])[0]
        hand = _poly_rot(sx, sy, facing, [(side * 13, 8)])[0]
        pygame.draw.line(surface, outline, shoulder, hand, 5)
        pygame.draw.line(surface, cloth_dark, shoulder, hand, 3)
        pygame.draw.circle(surface, skin, (int(hand[0]), int(hand[1])), 2)
        pygame.draw.circle(surface, cuff, (int(hand[0] - side * 2), int(hand[1])), 2, 1)

    # Head/neck forward.
    hx, hy = _poly_rot(sx, sy, facing, [(0, 17)])[0]
    pygame.draw.circle(surface, outline, (int(hx), int(hy)), 8)
    pygame.draw.circle(surface, skin, (int(hx), int(hy)), 7)
    pygame.draw.arc(surface, hair, (int(hx - 7), int(hy - 8), 14, 11), 0, math.pi, 4)
    # Face tick so head reads as a head at small size.
    pygame.draw.line(surface, (70, 46, 34), (int(hx - 3), int(hy + 3)), (int(hx + 3), int(hy + 3)), 1)


def _draw_detainee_stand(surface, sx, sy, d, cower=False):
    if cower or d.get("state") == "cower":
        _draw_prisoner_core(surface, sx, sy, d, crouched=True)
        return
    facing = (d.get("seed", 0) % 628) / 100.0
    if STATE.player:
        dx = STATE.player.rect.centerx - d.get("base_x", d.get("x", 0))
        dy = STATE.player.rect.centery - d.get("base_y", d.get("y", 0))
        if math.hypot(dx, dy) < 180:
            facing = math.atan2(dy, dx)
    _draw_prisoner_core(surface, sx, sy, d, facing=facing)


def _draw_detainee_sit(surface, sx, sy, d):
    """Consistent seated prisoner pose.

    Cross-legged / slumped, but still built from the same head-torso-limb
    language as standing detainees. The older variant looked like loose debris.
    """
    if d.get("state") == "cower":
        _draw_detainee_cower(surface, sx, sy, d)
        return
    cloth, cloth_dark, cloth_hi, stripe, skin, hair, outline, cuff = _detainee_palette(d.get("seed", 0), d.get("room", "yard"))
    _draw_detainee_shadow(surface, sx, sy, 34, 10, 48)
    facing = -math.pi / 2
    # Torso upright but low.
    torso = _poly_rot(sx, sy, facing, [(-9, -6), (9, -6), (10, 6), (0, 11), (-10, 6)])
    pygame.draw.polygon(surface, outline, torso)
    inner = _poly_rot(sx, sy, facing, [(-7, -4), (7, -4), (8, 5), (0, 8), (-8, 5)])
    pygame.draw.polygon(surface, cloth, inner)
    _draw_rot_line(surface, stripe, sx, sy, facing, (-7, 0), (7, 0), 2)
    # Crossed legs as two clear dark strokes in front.
    for side in (-1, 1):
        hip = _poly_rot(sx, sy, facing, [(side * 5, 7)])[0]
        knee = (sx + side * 12, sy + 13)
        foot = (sx + side * 20, sy + 11)
        pygame.draw.line(surface, outline, hip, knee, 5)
        pygame.draw.line(surface, cloth_dark, hip, knee, 3)
        pygame.draw.line(surface, outline, knee, foot, 4)
        pygame.draw.line(surface, cloth_dark, knee, foot, 2)
    # Hands on knees.
    for side in (-1, 1):
        pygame.draw.circle(surface, skin, (int(sx + side * 9), int(sy + 7)), 2)
    # Head and hair.
    hx, hy = sx, sy - 14
    pygame.draw.circle(surface, outline, (int(hx), int(hy)), 8)
    pygame.draw.circle(surface, skin, (int(hx), int(hy)), 7)
    pygame.draw.arc(surface, hair, (int(hx - 7), int(hy - 8), 14, 11), math.pi, math.tau, 3)


def _draw_detainee_cower(surface, sx, sy, d):
    _draw_prisoner_core(surface, sx, sy, d, crouched=True)


def _draw_detainee_pushup(surface, sx, sy, d):
    """Exercise-yard detainee pose.

    Instead of a prone push-up silhouette (which read like a dropped prop/body),
    use a kneeling stretch/rest pose that keeps the prisoner anatomy readable.
    """
    if d.get("state") == "cower":
        _draw_detainee_cower(surface, sx, sy, d)
        return
    cloth, cloth_dark, cloth_hi, stripe, skin, hair, outline, cuff = _detainee_palette(d.get("seed", 0), d.get("room", "yard"))
    bounce = math.sin(d.get("timer", 0) * 0.055) * 1.2
    _draw_detainee_shadow(surface, sx, sy, 34, 10, 45)
    # Kneeling body.
    torso = [(sx - 10, sy - 6 + bounce), (sx + 9, sy - 7 + bounce),
             (sx + 11, sy + 7 + bounce), (sx, sy + 13 + bounce),
             (sx - 12, sy + 7 + bounce)]
    pygame.draw.polygon(surface, outline, torso)
    pygame.draw.polygon(surface, cloth, [(sx - 7, sy - 4 + bounce), (sx + 7, sy - 5 + bounce),
                                         (sx + 8, sy + 5 + bounce), (sx, sy + 10 + bounce),
                                         (sx - 8, sy + 5 + bounce)])
    pygame.draw.line(surface, stripe, (int(sx - 7), int(sy + 1 + bounce)), (int(sx + 7), int(sy + 1 + bounce)), 2)
    # Knees/feet on the floor.
    for side in (-1, 1):
        pygame.draw.line(surface, outline, (int(sx + side * 5), int(sy + 9 + bounce)), (int(sx + side * 14), int(sy + 19)), 5)
        pygame.draw.line(surface, cloth_dark, (int(sx + side * 5), int(sy + 9 + bounce)), (int(sx + side * 14), int(sy + 19)), 3)
        pygame.draw.ellipse(surface, outline, (int(sx + side * 14 - 4), int(sy + 18), 8, 5))
    # Hands braced on floor, like stretching/resting.
    pygame.draw.line(surface, outline, (int(sx - 8), int(sy - 1 + bounce)), (int(sx - 21), int(sy + 7)), 4)
    pygame.draw.line(surface, cloth_dark, (int(sx - 8), int(sy - 1 + bounce)), (int(sx - 21), int(sy + 7)), 2)
    pygame.draw.line(surface, outline, (int(sx + 8), int(sy - 1 + bounce)), (int(sx + 19), int(sy + 7)), 4)
    pygame.draw.line(surface, cloth_dark, (int(sx + 8), int(sy - 1 + bounce)), (int(sx + 19), int(sy + 7)), 2)
    pygame.draw.circle(surface, skin, (int(sx - 22), int(sy + 7)), 2)
    pygame.draw.circle(surface, skin, (int(sx + 20), int(sy + 7)), 2)
    # Head.
    pygame.draw.circle(surface, outline, (int(sx), int(sy - 14 + bounce)), 8)
    pygame.draw.circle(surface, skin, (int(sx), int(sy - 14 + bounce)), 7)
    pygame.draw.arc(surface, hair, (int(sx - 7), int(sy - 22 + bounce), 14, 11), math.pi, math.tau, 3)


def _draw_detainee_bars(surface, sx, sy, d):
    """Prisoner at bars/fence, with the same body language as others."""
    cloth, cloth_dark, cloth_hi, stripe, skin, hair, outline, cuff = _detainee_palette(d.get("seed", 0), d.get("room", "cell"))
    _draw_detainee_shadow(surface, sx, sy, 28, 8, 32)
    facing = math.pi / 2
    # Draw a full small prisoner first so it reads human, then put bars over it.
    _draw_prisoner_core(surface, sx, sy, d, facing=facing)
    # Hands on/through the bars.
    pygame.draw.circle(surface, skin, (int(sx - 12), int(sy - 7)), 3)
    pygame.draw.circle(surface, skin, (int(sx + 12), int(sy - 7)), 3)
    # Bars/fence overlay; this is what makes the pose make sense.
    for bx in (-18, -9, 0, 9, 18):
        pygame.draw.line(surface, (80, 84, 78), (int(sx + bx), int(sy - 30)), (int(sx + bx), int(sy + 18)), 2)
        pygame.draw.line(surface, (26, 28, 26), (int(sx + bx + 2), int(sy - 30)), (int(sx + bx + 2), int(sy + 18)), 1)
    pygame.draw.line(surface, (92, 96, 88), (int(sx - 24), int(sy - 20)), (int(sx + 24), int(sy - 20)), 2)
    pygame.draw.line(surface, (92, 96, 88), (int(sx - 24), int(sy + 6)), (int(sx + 24), int(sy + 6)), 2)


def _draw_detainee_worker(surface, sx, sy, d):
    if d.get("state") == "cower":
        _draw_detainee_cower(surface, sx, sy, d)
        return
    _draw_prisoner_core(surface, sx, sy, d, facing=-0.3)
    pygame.draw.line(surface, (124, 118, 92), (int(sx + 10), int(sy - 1)), (int(sx + 24), int(sy - 8)), 2)
    pygame.draw.circle(surface, (76, 76, 66), (int(sx + 26), int(sy - 9)), 3, 1)


def _draw_prisoner_sprite_v2(surface, sx, sy, d, bars=False, cower=False, _scaled=False):
    if not _scaled:
        scale = 0.96
        pad = 68
        temp = pygame.Surface((pad * 2, pad * 2), pygame.SRCALPHA)
        _draw_prisoner_sprite_v2(temp, pad, pad, d, bars=bars, cower=cower, _scaled=True)
        sw, sh = int(temp.get_width() * scale), int(temp.get_height() * scale)
        temp = pygame.transform.smoothscale(temp, (sw, sh))
        surface.blit(temp, (int(sx - sw // 2), int(sy - sh // 2)))
        return

    seed = d.get("seed", 0)
    room = d.get("room", "yard")
    pose = d.get("pose", "stand")
    rng = random.Random(seed)
    if room in ("yard", "cell"):
        suit = rng.choice([(158, 88, 35), (142, 78, 32), (174, 102, 44)])
        suit_dark = (74, 43, 24); suit_hi = (214, 134, 62)
    elif room == "laundry":
        suit = rng.choice([(88, 110, 108), (78, 98, 104), (96, 106, 92)])
        suit_dark = (42, 54, 56); suit_hi = (150, 174, 166)
    else:
        suit = rng.choice([(84, 98, 78), (76, 92, 84), (92, 94, 70)])
        suit_dark = (38, 50, 42); suit_hi = (182, 144, 64)
    skin = rng.choice([(158, 118, 88), (176, 132, 96), (122, 90, 70),
                       (194, 152, 112), (144, 102, 78)])
    skin_sh = (max(0, skin[0] - 45), max(0, skin[1] - 45), max(0, skin[2] - 45))
    hair = rng.choice([(18, 14, 12), (32, 24, 18), (48, 38, 26), (70, 58, 42)])
    outline = (8, 9, 9)
    cuff = (36, 38, 36)
    id_patch = (226, 190, 118)
    shoe = (24, 22, 20)
    timer = d.get("timer", 0)
    bob = 0.0 if cower or d.get("state") == "cower" else math.sin(timer * 0.035 + seed) * 0.8
    sy += bob
    facing = -1 if seed % 2 else 1
    def I(v): return int(round(v))
    def shadow(w=34, h=11, a=58, dy=18):
        _draw_detainee_shadow(surface, sx, sy + dy - 11, w, h, a)
    def limb(p1, p2, col, width=5, inner=None, inner_w=3):
        pygame.draw.line(surface, outline, (I(p1[0]), I(p1[1])), (I(p2[0]), I(p2[1])), width)
        pygame.draw.line(surface, inner or col, (I(p1[0]), I(p1[1])), (I(p2[0]), I(p2[1])), inner_w)
    def arm2(sh_, el, hand, w=5):
        limb(sh_, el, suit_dark, w, suit_dark, w - 2)
        limb(el, hand, suit_dark, w - 1, suit_dark, w - 3)
        pygame.draw.circle(surface, outline, (I(hand[0]), I(hand[1])), 3)
        pygame.draw.circle(surface, skin, (I(hand[0]), I(hand[1])), 2)
    def head(cx, cy, r=7, look=0):
        pygame.draw.circle(surface, outline, (I(cx), I(cy)), r + 1)
        pygame.draw.circle(surface, skin, (I(cx), I(cy)), r)
        # hair styles
        st = seed % 4
        cap = pygame.Rect(I(cx - r), I(cy - r - 1), r * 2, r + 2)
        if st == 0:      # shaved
            pygame.draw.arc(surface, skin_sh, cap, math.pi, math.tau, 2)
        elif st == 1:    # buzz
            pygame.draw.arc(surface, hair, cap, math.pi, math.tau, 3)
        elif st == 2:    # full crop + sides
            pygame.draw.arc(surface, hair, cap, math.pi, math.tau, 4)
            pygame.draw.line(surface, hair, (I(cx - r), I(cy - 2)), (I(cx - r), I(cy + 2)), 2)
            pygame.draw.line(surface, hair, (I(cx + r), I(cy - 2)), (I(cx + r), I(cy + 2)), 2)
        else:            # curly
            pygame.draw.arc(surface, hair, cap, math.pi, math.tau, 3)
            for k in (-4, 0, 4):
                pygame.draw.circle(surface, hair, (I(cx + k), I(cy - r + 1)), 2)
        # face: brows, eyes, mouth - small but human
        ex = I(cx + look * 1.5)
        pygame.draw.line(surface, (40, 26, 18), (ex - 3, I(cy - 2)), (ex - 1, I(cy - 2)), 1)
        pygame.draw.line(surface, (40, 26, 18), (ex + 1, I(cy - 2)), (ex + 3, I(cy - 2)), 1)
        pygame.draw.line(surface, (28, 18, 12), (ex - 2, I(cy)), (ex - 2, I(cy)), 1)
        pygame.draw.line(surface, (28, 18, 12), (ex + 2, I(cy)), (ex + 2, I(cy)), 1)
        pygame.draw.line(surface, (95, 58, 42), (ex - 1, I(cy + 3)), (ex + 2, I(cy + 3)), 1)
        # chin shadow / neck
        pygame.draw.arc(surface, skin_sh, (I(cx - 4), I(cy + 2), 8, 6), 0, math.pi, 1)
    def torso(cx, cy, hunch=0, crouch=False):
        if crouch:
            outer = [(cx-14, cy-6+hunch), (cx+9, cy-9+hunch), (cx+16, cy+2), (cx+6, cy+13), (cx-13, cy+9)]
            inner = [(cx-11, cy-4+hunch), (cx+6, cy-6+hunch), (cx+12, cy+2), (cx+4, cy+9), (cx-10, cy+6)]
        else:
            outer = [(cx-11, cy-12+hunch), (cx+11, cy-12+hunch), (cx+13, cy-2),
                     (cx+9, cy+12), (cx-9, cy+12), (cx-13, cy-2)]
            inner = [(cx-8, cy-9+hunch), (cx+8, cy-9+hunch), (cx+10, cy-2),
                     (cx+6, cy+9), (cx-6, cy+9), (cx-10, cy-2)]
        pygame.draw.polygon(surface, outline, [(I(x), I(y)) for x, y in outer])
        pygame.draw.polygon(surface, suit, [(I(x), I(y)) for x, y in inner])
        # shoulder caps
        for s in (-1, 1):
            pygame.draw.circle(surface, outline, (I(cx + s * 10), I(cy - 10 + hunch)), 5)
            pygame.draw.circle(surface, suit, (I(cx + s * 10), I(cy - 10 + hunch)), 4)
            pygame.draw.arc(surface, suit_hi, (I(cx + s * 10 - 4), I(cy - 14 + hunch), 8, 8),
                            math.radians(200), math.radians(340), 1)
        # collar V + zip
        pygame.draw.line(surface, suit_dark, (I(cx - 4), I(cy - 10 + hunch)), (I(cx), I(cy - 6 + hunch)), 1)
        pygame.draw.line(surface, suit_dark, (I(cx + 4), I(cy - 10 + hunch)), (I(cx), I(cy - 6 + hunch)), 1)
        pygame.draw.line(surface, suit_dark, (I(cx), I(cy - 6 + hunch)), (I(cx), I(cy + 8)), 1)
        # chest stripe + ID patch + belt
        pygame.draw.line(surface, suit_hi, (I(cx - 8), I(cy - 1)), (I(cx + 8), I(cy - 1)), 2)
        pygame.draw.rect(surface, id_patch, (I(cx + 3), I(cy - 6 + hunch), 4, 3))
        pygame.draw.line(surface, suit_dark, (I(cx - 7), I(cy + 8)), (I(cx + 7), I(cy + 8)), 2)
        # side shade
        pygame.draw.line(surface, suit_dark, (I(cx - 9), I(cy - 6)), (I(cx - 7), I(cy + 8)), 2)

    if cower or d.get("state") == "cower":
        shadow(40, 13, 78, dy=18)
        variant = seed % 3
        if variant == 0:      # curled, arms over head
            torso(sx, sy + 4, hunch=2, crouch=True)
            for side in (-1, 1):
                arm2((sx + side * 12, sy + 2), (sx + side * 10, sy - 10), (sx - side * 2, sy - 16))
            head(sx - 6, sy - 10, 7)
            for side in (-1, 1):
                limb((sx + side * 5, sy + 12), (sx + side * 16, sy + 21), suit_dark, 5, suit_dark, 3)
                pygame.draw.ellipse(surface, shoe, (I(sx + side * 16 - 4), I(sy + 19), 9, 5))
        elif variant == 1:    # kneeling, hands on floor
            torso(sx, sy + 2, hunch=1, crouch=True)
            head(sx + 3, sy - 13, 7)
            for side in (-1, 1):
                arm2((sx + side * 10, sy + 2), (sx + side * 20, sy + 8), (sx + side * 26, sy + 12))
                limb((sx + side * 5, sy + 12), (sx + side * 13, sy + 23), suit_dark, 5, suit_dark, 3)
        else:                 # side huddle
            pygame.draw.ellipse(surface, outline, (I(sx - 19), I(sy - 8), 38, 24))
            pygame.draw.ellipse(surface, suit_dark, (I(sx - 16), I(sy - 6), 32, 19))
            pygame.draw.arc(surface, suit, (I(sx - 12), I(sy - 5), 24, 14), math.radians(200), math.radians(340), 2)
            head(sx - 12, sy - 12, 7)
            arm2((sx - 4, sy - 4), (sx - 12, sy - 12), (sx - 17, sy - 15))
        return

    if bars:
        shadow(34, 10, 45, dy=16)
        torso(sx, sy, hunch=1)
        for side in (-1, 1):
            arm2((sx + side * 10, sy - 8), (sx + side * 16, sy - 12), (sx + side * 19, sy - 16))
            pygame.draw.circle(surface, cuff, (I(sx + side * 19), I(sy - 14)), 3, 1)
        head(sx, sy - 21, 7)
        for bx in (-24, -12, 0, 12, 24):
            pygame.draw.line(surface, (105, 110, 102), (I(sx + bx), I(sy - 42)), (I(sx + bx), I(sy + 26)), 2)
            pygame.draw.line(surface, (18, 20, 19), (I(sx + bx + 2), I(sy - 42)), (I(sx + bx + 2), I(sy + 26)), 1)
        pygame.draw.line(surface, (120, 124, 112), (I(sx - 30), I(sy - 24)), (I(sx + 30), I(sy - 24)), 2)
        pygame.draw.line(surface, (120, 124, 112), (I(sx - 30), I(sy + 8)), (I(sx + 30), I(sy + 8)), 2)
        # hands grip over the bars
        for side in (-1, 1):
            pygame.draw.circle(surface, skin, (I(sx + side * 19), I(sy - 16)), 3)
        return

    if pose == "sit":
        shadow(42, 12, 56, dy=20)
        # crossed legs first
        for side in (-1, 1):
            limb((sx + side * 4, sy + 12), (sx + side * 18, sy + 22), suit_dark, 6, suit_dark, 4)
            limb((sx + side * 18, sy + 22), (sx - side * 6, sy + 25), suit_dark, 5, suit_dark, 3)
            pygame.draw.ellipse(surface, shoe, (I(sx - side * 6 - 5), I(sy + 23), 10, 5))
        torso(sx, sy - 1, hunch=2)
        for side in (-1, 1):
            arm2((sx + side * 10, sy - 8), (sx + side * 13, sy + 2), (sx + side * 8, sy + 9))
        head(sx, sy - 21, 7, look=facing * 0.5)
        return

    if pose == "pushup":
        shadow(40, 11, 50, dy=20)
        for side in (-1, 1):
            limb((sx + side * 5, sy + 12), (sx + side * 12, sy + 24), suit_dark, 6, suit_dark, 4)
            pygame.draw.ellipse(surface, shoe, (I(sx + side * 12 - 4), I(sy + 22), 9, 5))
        torso(sx, sy - 1, hunch=3)
        for side in (-1, 1):
            arm2((sx + side * 10, sy - 6), (sx + side * 20, sy + 2), (sx + side * 24, sy + 9))
        head(sx, sy - 20, 7)
        return

    # standing family
    shadow(32, 10, 58, dy=18)
    lean = 0
    if pose == "lean": lean = -4 * facing
    elif pose == "fold": lean = 2 * facing
    elif pose == "worker": lean = 3 * facing
    bx = sx + lean
    hunch = 1 if pose in ("worker", "fold") else 0
    step = math.sin(timer * 0.06 + seed) * (2.0 if pose == "pace_x" else 0.5)
    for side in (-1, 1):
        hip = (bx + side * 5, sy + 10)
        knee = (bx + side * 6, sy + 20)
        foot = (bx + side * (7 + step * side), sy + 29)
        limb(hip, knee, suit_dark, 6, suit_dark, 4)
        limb(knee, foot, suit_dark, 5, suit_dark, 3)
        pygame.draw.ellipse(surface, outline, (I(foot[0] - 5), I(foot[1] - 2), 11, 6))
        pygame.draw.ellipse(surface, shoe, (I(foot[0] - 4), I(foot[1] - 1), 9, 4))
        pygame.draw.line(surface, (58, 54, 48), (I(foot[0] - 3), I(foot[1] - 1)), (I(foot[0] + 3), I(foot[1] - 1)), 1)
    torso(bx, sy - 1, hunch=hunch)
    if pose == "fold":
        pygame.draw.rect(surface, (190, 196, 184), (I(bx - 17), I(sy + 7), 34, 8), border_radius=2)
        pygame.draw.line(surface, (160, 166, 156), (I(bx - 15), I(sy + 9)), (I(bx + 15), I(sy + 9)), 1)
        for side in (-1, 1):
            arm2((bx + side * 10, sy - 8), (bx + side * 14, sy + 0), (bx + side * 12, sy + 8))
    elif pose == "worker":
        arm2((bx - 10, sy - 8), (bx - 14, sy + 2), (bx - 17, sy + 12))
        arm2((bx + 10, sy - 8), (bx + 20, sy - 10), (bx + 28, sy - 13))
        pygame.draw.line(surface, (142, 130, 92), (I(bx + 25), I(sy - 14)), (I(bx + 40), I(sy - 21)), 2)
        pygame.draw.circle(surface, (72, 74, 66), (I(bx + 42), I(sy - 22)), 4, 1)
    elif pose == "lean":
        arm2((bx - facing * 10, sy - 8), (bx - facing * 18, sy - 4), (bx - facing * 24, sy - 1))
        arm2((bx + facing * 10, sy - 7), (bx + facing * 13, sy + 3), (bx + facing * 14, sy + 12))
    else:
        for side in (-1, 1):
            arm2((bx + side * 10, sy - 8), (bx + side * 13, sy + 2), (bx + side * 14, sy + 11))
            pygame.draw.circle(surface, cuff, (I(bx + side * 14 - side), I(sy + 12)), 3, 1)
    head(bx, sy - 22, 7, look=facing * 0.5 + math.sin(timer * 0.012 + seed) * 0.5)
    if room in ("yard", "maintenance") and seed % 2 == 1:
        tag = font_terminal_small.render(str(seed)[-2:], True, (70, 66, 54))
        tag.set_alpha(115)
        surface.blit(tag, (I(bx - tag.get_width() // 2), I(sy + 34)))


def _draw_prisoner_player_sprite(surface, sx, sy, d, *, bars=False, cower=False, _scaled=False):
    """Readable ambient prisoner sprite (v2 anatomy pass).

    Detainees are non-combat world dressing, but they need to read instantly as
    people. v2 replaces the v1 cone-torso / floating-head / stick-limb
    silhouette with connected anatomy: neck + head with brows/eyes/mouth and
    hairstyle variants, shoulder caps, collar/zip/belt/ID-patch jumpsuit,
    two-segment arms with real hands, knee-bent legs with shoes, and per-pose
    silhouettes (stand/pace/fold/worker/lean/sit/stretch/bars/cower).
    """
    return _draw_prisoner_sprite_v2(surface, sx, sy, d, bars=bars, cower=cower, _scaled=_scaled)


def _draw_detainee_dead(surface, sx, sy, d):
    """Fallen detainee body; still clearly human, not a loot prop."""
    cloth, cloth_dark, cloth_hi, stripe, skin, hair, outline, cuff = _detainee_palette(d.get("seed", 0), d.get("room", "yard"))
    angle = 0.35 + (d.get("seed", 0) % 5) * 0.18
    _draw_detainee_shadow(surface, sx, sy, 46, 11, 65)
    # Blood under/near torso, subtle but readable.
    blood = pygame.Surface((48, 34), pygame.SRCALPHA)
    pygame.draw.ellipse(blood, (58, 6, 6, 120), (4, 8, 38, 20))
    pygame.draw.ellipse(blood, (35, 3, 3, 150), (14, 12, 20, 12))
    surface.blit(blood, (int(sx - 24), int(sy - 8)))
    # Prone body line.
    body_pts = _poly_rot(sx, sy, angle, [(-17, -6), (12, -7), (18, 4), (6, 10), (-17, 7)])
    pygame.draw.polygon(surface, outline, body_pts)
    inner = _poly_rot(sx, sy, angle, [(-14, -4), (10, -5), (14, 3), (5, 7), (-14, 5)])
    pygame.draw.polygon(surface, cloth_dark, inner)
    # Head to one side.
    hx, hy = _poly_rot(sx, sy, angle, [(22, -2)])[0]
    pygame.draw.circle(surface, outline, (int(hx), int(hy)), 8)
    pygame.draw.circle(surface, skin, (int(hx), int(hy)), 7)
    pygame.draw.arc(surface, hair, (int(hx - 7), int(hy - 8), 14, 11), 0, math.pi, 3)
    # Limbs.
    for p1, p2 in [((-8, 5), (-22, 15)), ((5, 6), (20, 15)), ((-10, -5), (-24, -12)), ((8, -5), (20, -13))]:
        a, b = _poly_rot(sx, sy, angle, [p1, p2])
        pygame.draw.line(surface, outline, a, b, 4)
        pygame.draw.line(surface, cloth_dark, a, b, 2)



def _draw_volkov_mags(cam_x, cam_y):
    """Draw the flying magazines from Volkov (with motion trail for visibility)."""
    mags = getattr(STATE, "m3_volkov_mags", [])
    if not mags:
        return

    for mag in mags:
        if mag.get("caught"):
            continue

        sx = mag["x"] - cam_x
        sy = mag["y"] - cam_y

        # Compact motion trail. Keep it narrower than the actual mag so the
        # trail reads as speed rather than making the object look oversized.
        trail_alpha = 58
        for i in range(2):
            tx = sx - mag.get("vx", 0) * (i + 1) * 1.5
            ty = sy - mag.get("vy", 0) * (i + 1) * 1.5
            trail = pygame.Surface((7, 19), pygame.SRCALPHA)
            pygame.draw.rect(
                trail, (68, 82, 76, trail_alpha - i * 22),
                (1, 1, 5, 17), border_radius=1,
            )
            rot_trail = pygame.transform.rotate(
                trail, math.degrees(mag.get("rot", 0)))
            screen.blit(rot_trail, (tx - rot_trail.get_width() // 2,
                                    ty - rot_trail.get_height() // 2))

        # K-9 24-round straight stick magazine. This matches the SMG/HUD art:
        # slim, dark parkerized body, slight perspective taper, witness holes,
        # metal feed lips, and a dark base plate. The old 22x40 sprite with a
        # big gold base looked like an oversized rifle/box magazine.
        surf = pygame.Surface((12, 29), pygame.SRCALPHA)
        body = [(2, 4), (10, 4), (9, 25), (3, 25)]
        pygame.draw.polygon(surf, (25, 32, 30), body)
        pygame.draw.polygon(surf, (82, 98, 90), body, 1)
        # Subtle stamped spine and horizontal ribs.
        pygame.draw.line(surf, (48, 60, 56), (4, 6), (4, 23), 1)
        for ry in (10, 15, 20):
            pygame.draw.line(surf, (56, 68, 63), (4, ry), (8, ry), 1)
        # Tiny brass witness holes identify it as the K-9's loaded stick mag.
        for wy in (8, 14, 20):
            pygame.draw.circle(surf, (166, 137, 55), (7, wy), 1)
        # Feed lips and slim reinforced base plate.
        pygame.draw.line(surf, (132, 145, 138), (3, 3), (5, 1), 1)
        pygame.draw.line(surf, (132, 145, 138), (9, 3), (7, 1), 1)
        pygame.draw.rect(surf, (12, 16, 15), (2, 24, 8, 4), border_radius=1)
        pygame.draw.line(surf, (70, 82, 76), (3, 24), (9, 24), 1)

        rot = pygame.transform.rotate(surf, math.degrees(mag.get("rot", 0)))
        screen.blit(rot, (sx - rot.get_width() // 2,
                          sy - rot.get_height() // 2))


def _draw_m3_detainees(cam_x, cam_y):
    detainees = getattr(STATE, "mission3_detainees", [])
    if not detainees:
        return
    for d in detainees:
        wx, wy = _detainee_draw_pos(d)
        sx, sy = wx - cam_x, wy - cam_y
        if sx < -80 or sx > WIDTH + 80 or sy < -80 or sy > HEIGHT + 80:
            continue
        if d.get("dead"):
            _draw_detainee_dead(screen, sx, sy, d)
            continue
        pose = d.get("pose", "stand")
        cower = (d.get("state") == "cower")
        bars = pose == "bars"
        # Use a single consistent prisoner sprite for all ambient detainees.
        # Minor pose differences are contextual (bars/cower), not totally
        # different silhouettes that read as props.
        _draw_prisoner_player_sprite(screen, sx, sy, d, bars=bars, cower=cower)

        if d.get("line_timer", 0) > 0 and d.get("line"):
            alpha = min(220, int(d["line_timer"] * 3))
            txt = font_terminal_small.render(d["line"], True, (190, 204, 184))
            txt.set_alpha(alpha)
            bg = pygame.Surface((txt.get_width() + 16, txt.get_height() + 8), pygame.SRCALPHA)
            pygame.draw.rect(bg, (2, 4, 4, min(162, alpha)), bg.get_rect(), border_radius=5)
            pygame.draw.rect(bg, (90, 104, 88, min(90, alpha)), bg.get_rect(), 1, border_radius=5)
            # Small pointer tail makes this read as a whispered bark from the
            # detainee rather than detached UI text.
            pygame.draw.polygon(bg, (2, 4, 4, min(162, alpha)), [
                (bg.get_width() // 2 - 4, bg.get_height() - 1),
                (bg.get_width() // 2 + 4, bg.get_height() - 1),
                (bg.get_width() // 2, bg.get_height() + 5),
            ])
            screen.blit(bg, (int(sx - bg.get_width() // 2), int(sy - 54)))
            screen.blit(txt, (int(sx - txt.get_width() // 2), int(sy - 50)))
