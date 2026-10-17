"""Split from mission2.py - see mission2.py (shim) for the map."""
# missions.m2 package
# ------------------------------------------------------------

"""Mission 2: Quiet on Route 12 - clean cinematic vertical slice.

This module keeps the existing game integration intact:
    - game_core.start_mission2()
    - game_core.game_update()/game_draw() routing
    - acaristan.py Mission 2 intro and ending cutscenes
    - save as MISSION_2
    - dev command: python acaristan.py --dev-mission2


"""

import math
from engine.core import LEGACY_RNG as _rng_legacy  # RPE6 R6: named 'legacy' rng stream
import time

import pygame

from core.config import (C_BLOOD, C_VASILE, Particle, audio, font_terminal)
from entities.art_cache import get_blood_decal, get_fullscreen_overlay, get_tinnitus_bar, get_panel_bg
from core.state import STATE
from entities.player import Player, resolve_melee
from entities.enemy_ai import Enemy
from ui.hud import MiniMap, draw_objective_panel, draw_pinned_radio
from core.interactions import trigger_radio_chatter
from entities.weapons import (
    spawn_molotov_fire as _spawn_molotov_fire,
    _wall_blocks_line,
    MOLOTOV_RADIUS,
    MOLOTOV_ENEMY_DAMAGE,
    MOLOTOV_PLAYER_DAMAGE,
    handle_shoot,
)
from fx import effects
from core.camera import update_camera, reset_camera_state, collide_bullet_walls, draw_bullets

from missions.m2 import world as _m2_world  # _last_keys reads
from missions.m2.meta import CAM_DARIUS_RADIO, CAM_GABI_BODY, CAM_GANTRY_REVEAL, CAM_SEBY_DRAG, CAM_SQUAD_WIDE, FIELD_RADIO_POS, KILLBOX_COVER_POSITIONS, KILLBOX_FLANK_POSITIONS, KILLBOX_FLANK_SPAWNS, KILLBOX_REINFORCEMENT_SPAWNS, KILL_ZONE, MAP_H, MAP_W, REGROUP_ENTRY_POSITIONS, REGROUP_TARGET_POSITIONS, SAFE_ZONE, SNIPER_ARENA_CAM, SNIPER_CLOSE_KILL_TEXT, SNIPER_DAMAGE, SNIPER_FLANK_POS, SNIPER_GRACE_FRAMES, SNIPER_LOCK_DECAY, SNIPER_LOCK_FRAMES, SNIPER_MAX_LOS_RANGE, SNIPER_NEST_POS, SNIPER_PHASES, SNIPER_POINT_BLANK_RANGE, SNIPER_WARN_THRESHOLDS, STAGE_BLACKOUT, STAGE_COMBAT, STAGE_DONE, STAGE_INVESTIGATE, STAGE_RUN, STAGE_SNIPER, TANKER_POS, UPLOAD_TERMINAL_POS, _beat, _beat_now, _tc, get_zone_for_world_pos
from missions.m2.world import _burst, _dist, _player_pos, _radio, _set_objective, _snap_camera_to, _solid_walls, _spawn_enemy, _sync_story_prop_collisions
from engine.core import now_ms as _now_ms  # RPE6 B-001 timebase
import game.world as _gw  # RPE6 Phase 5 (D4): mission data lives in components
from missions.m2.components import M2Role as _M2Role


def _m2g(e):
    """Declared M2 data of an enemy (replaces the ad hoc ``e.m2_*`` attributes)."""
    return _gw.ensure(e, _M2Role)


def _activate_travel_trigger(trigger):
    trigger["triggered"] = True
    sound = trigger.get("sound")
    if sound:
        audio.play(sound, volume=trigger.get("volume", 0.2))
    dialogue = trigger.get("dialogue")
    if dialogue:
        _radio(dialogue, color=trigger.get("color", C_VASILE), duration=trigger.get("duration", 260), mark=trigger["id"])
    for prop in trigger.get("props", []):
        story_prop = dict(prop)
        story_prop.setdefault("life", -1)
        story_prop.setdefault("age", 0)
        story_prop.setdefault("source", trigger["id"])
        STATE.mission2_story_props.append(story_prop)
    _sync_story_prop_collisions()


def _update_travel_triggers():
    """One-shot environmental story beats between clue zones."""
    if (not STATE.player or getattr(STATE, "mission2_stage", "") != STAGE_INVESTIGATE
            or getattr(STATE, "mission2_card", None) is not None):
        return
    player_pos = _player_pos()
    STATE.mission2_current_zone = get_zone_for_world_pos(player_pos)
    for trigger in getattr(STATE, "mission2_triggers", []):
        if trigger.get("triggered"):
            continue
        if trigger["rect"].collidepoint(player_pos):
            _activate_travel_trigger(trigger)


def _actor_collision_rect(x, y):
    return pygame.Rect(int(x - 12), int(y - 12), 24, 24)


def _actor_rect_collides(rect):
    for wall in _solid_walls():
        if rect.colliderect(wall):
            return True
    return False


def _try_actor_step(actor, dx, dy):
    if abs(dx) < 0.001 and abs(dy) < 0.001:
        return False
    moved = False
    x, y = actor["pos"]
    # X axis first.
    if abs(dx) > 0.001:
        nr = _actor_collision_rect(x + dx, y)
        if not _actor_rect_collides(nr):
            actor["pos"][0] = x + dx
            x = actor["pos"][0]
            moved = True
    # Y axis second.
    if abs(dy) > 0.001:
        nr = _actor_collision_rect(x, y + dy)
        if not _actor_rect_collides(nr):
            actor["pos"][1] = y + dy
            moved = True
    return moved


def _move_actor_towards(actor, target, rate=0.055, max_step=2.7):
    """Move scripted squad actors while respecting walls/vehicles/solid props.

    This is deliberately not full combat pathfinding.  It is a lightweight
    cinematic/ambient mover with axis collision and a small sidestep fallback so
    actors stop sliding through barriers but can still work around minor clutter.
    """
    if not actor.get("alive", True):
        return
    x, y = actor["pos"]
    dx = target[0] - x
    dy = target[1] - y
    dist = math.hypot(dx, dy)
    if dist < 1:
        return
    step = min(max_step, dist * rate)
    nx = dx / dist * step
    ny = dy / dist * step
    moved = _try_actor_step(actor, nx, ny)
    if not moved and dist > 8:
        # Try sliding around small props/barriers.  Alternating side preference
        # stops all three squadmates choosing the exact same detour.
        side = -1 if (hash(actor.get("name", "")) % 2) else 1
        px = -ny * side
        py = nx * side
        if not _try_actor_step(actor, px, py):
            _try_actor_step(actor, -px, -py)
    if not moved and dist > 8:
        # Broader escape - try multiple angles when stuck on adjacent barriers.
        for slide_angle in (0.5, -0.5, 1.0, -1.0, 1.5, -1.5):
            cs = math.cos(slide_angle)
            sn = math.sin(slide_angle)
            sx = nx * cs - ny * sn
            sy = nx * sn + ny * cs
            if _try_actor_step(actor, sx, sy):
                break


def _nearest_unfound_clue(max_dist=360):
    if not STATE.player:
        return None
    px, py = _player_pos()
    best = None
    best_d = max_dist
    for clue in getattr(STATE, "mission2_clues", []):
        if clue.get("done"):
            continue
        d = math.hypot(clue["pos"][0] - px, clue["pos"][1] - py)
        if d < best_d:
            best = clue
            best_d = d
    return best


def _update_squad_ambient():
    """Zone-post squad behavior: active, but not player-following.

    The team occupies authored posts in the same broad investigation zone instead
    of orbiting Biribel.  They still move, scan, and peel toward relevant clues,
    but they do not form a follow-the-player escort blob.
    """
    if not STATE.player or getattr(STATE, "mission2_stage", "") != STAGE_INVESTIGATE:
        return

    px, py = _player_pos()
    zone = getattr(STATE, "mission2_current_zone", None) or get_zone_for_world_pos((px, py)) or "approach"
    tick = _now_ms()
    patrol_step = (tick // 3600) % 2

    zone_posts = {
        "approach": [
            [(_tc(10, 72), _tc(14, 70)), (_tc(16, 74), _tc(21, 72)), (_tc(11, 75), _tc(18, 76))],
            ["scanning road", "covering rear", "radio check"],
            [SNIPER_NEST_POS, _tc(8, 74), _tc(12, 70)],
        ],
        "blast_scene": [
            [(_tc(20, 59), _tc(25, 58)), (_tc(31, 61), _tc(38, 60)), (_tc(28, 55), _tc(33, 56))],
            ["checking markings", "covering road", "checking timer"],
            [_tc(20, 59), SNIPER_NEST_POS, _tc(33, 40)],
        ],
        "south_ditch": [
            [(_tc(12, 50), _tc(18, 49)), (_tc(20, 47), _tc(23, 53)), (_tc(13, 50), _tc(17, 52))],
            ["watching bank", "covering ditch", "tracking signal"],
            [_tc(20, 47), _tc(6, 49), _tc(13, 50)],
        ],
        "north_service": [
            [(_tc(51, 43), _tc(58, 42)), (_tc(55, 45), _tc(62, 47)), (_tc(61, 43), _tc(56, 48))],
            ["checking gate", "checking tread", "comms diag"],
            [SNIPER_NEST_POS, _tc(55, 45), _tc(61, 43)],
        ],
        "toll_plaza": [
            [(_tc(38, 33), _tc(35, 34)), (_tc(34, 37), _tc(40, 35)), (_tc(39, 36), _tc(37, 37))],
            ["watching gantry", "covering lane", "checking radio"],
            [SNIPER_NEST_POS, SNIPER_NEST_POS, FIELD_RADIO_POS],
        ],
        "east_control": [
            [(_tc(55, 23), _tc(58, 20)), (_tc(63, 22), _tc(64, 18)), (_tc(61, 16), _tc(59, 15))],
            ["covering door", "watching hall", "terminal check"],
            [_tc(51, 25), _tc(67, 9), UPLOAD_TERMINAL_POS],
        ],
    }
    posts, activities, lookats = zone_posts.get(zone, zone_posts["approach"])

    # If Biribel is close to an unfound clue, the role-relevant teammate moves
    # to that clue, not to Biribel.
    clue = _nearest_unfound_clue(max_dist=380)
    chosen_posts = [post_pair[int(patrol_step)] for post_pair in posts]
    chosen_activities = list(activities)
    chosen_lookats = list(lookats)
    if clue:
        cx, cy = clue["pos"]
        kind = clue.get("kind")
        if kind in ("mag_paint", "range_card"):
            chosen_posts[0] = (cx - 38, cy + 26)
            chosen_activities[0] = "reading marks"
            chosen_lookats[0] = clue["pos"]
        elif kind in ("bootprints", "timer_fragment"):
            chosen_posts[1] = (cx + 38, cy + 22)
            chosen_activities[1] = "inspecting scene"
            chosen_lookats[1] = clue["pos"]
        elif kind == "radio":
            chosen_posts[2] = (cx + 34, cy + 18)
            chosen_activities[2] = "checking static"
            chosen_lookats[2] = clue["pos"]

    for actor, target, activity, look_at in zip(STATE.mission2_squad, chosen_posts, chosen_activities, chosen_lookats):
        actor["activity"] = activity
        actor["look_at"] = look_at
        _move_actor_towards(actor, target, rate=0.035, max_step=1.85)


def _sniper_phase_activity():
    """Per-frame activity pass for the cutscene squad.

    Only the second definition matters (the first was a leftover no-op stub
    from an earlier refactor). Any squadmate that has been killed during
    the cutscene is forced into the 'down' pose so the draw code picks the
    dead-sprite branch.
    """
    for a in STATE.mission2_squad:
        if not a.get("alive", True):
            a["activity"] = "down"


def _update_squad_actor_positions():
    squad = getattr(STATE, "mission2_squad", None)
    if not squad or len(squad) < 3:
        return

    gabi, seby, darius = squad[0], squad[1], squad[2]
    seby_activity = (seby.get("activity") or "").lower()
    darius_activity = (darius.get("activity") or "").lower()
    pt = int(getattr(STATE, "mission2_sniper_phase_timer", 0))

    # Seby has three phases: sprint (lunge to Gabi), drag (carry him to
    # cover), and post-drag. Capture sprint_origin ONLY when sprinting
    # begins, otherwise the drag interpolation starts from wherever Seby
    # happened to be when drag kicked in (not from the kneel pose).
    if "sprint" in seby_activity or "drag" in seby_activity or "kneel" in seby_activity:
        if "sprint" in seby_activity and "_sprint_origin" not in seby:
            seby["_sprint_origin"] = tuple(seby["pos"])
        if ("drag" in seby_activity or "kneel" in seby_activity) and "_corpse_origin" not in gabi:
            gabi["_corpse_origin"] = tuple(gabi["pos"])

        s_ox, s_oy = seby.get("_sprint_origin", seby["pos"])
        g_ox, g_oy = gabi.get("_corpse_origin", gabi["pos"])

        kneel_x, kneel_y = g_ox - 22, g_oy - 4
        cover_x, cover_y = g_ox - 70, g_oy + 18

        if "sprint" in seby_activity:
            start = _beat("movement_two", "seby_breaks", 80)
            end = _beat("movement_two", "seby_arrives", 180)
            t = max(0.0, min(1.0, (pt - start) / max(1, end - start)))
            t = 1.0 - (1.0 - t) ** 2
            seby["pos"] = [s_ox + (kneel_x - s_ox) * t,
                           s_oy + (kneel_y - s_oy) * t]

        elif "drag" in seby_activity or "kneel" in seby_activity:
            # Drag phase: lerp Seby from kneel pose to cover using the
            # phase timer, smoothstepped. The earlier code did a redundant
            # cover_lerp/drag_lerp read that was always None and got
            # overwritten on the next line.
            start = _beat("movement_two", "seby_arrives", 180)
            end = _beat("movement_two", "seby_drag_to_cover_end", 340)
            t = max(0.0, min(1.0, (pt - start) / max(1, end - start)))
            t = t * t * (3.0 - 2.0 * t)
            seby["pos"] = [kneel_x + (cover_x + 18 - kneel_x) * t,
                           kneel_y + (cover_y - 4 - kneel_y) * t]
            gabi["pos"] = [g_ox + (cover_x - g_ox) * t,
                           g_oy + (cover_y - g_oy) * t]

            if pt % 5 == 0:
                STATE.blood_decals.append([
                    gabi["pos"][0] + _rng_legacy.randint(-4, 4),
                    gabi["pos"][1] + _rng_legacy.randint(-2, 2),
                    90,
                    _rng_legacy.randint(8, 14),
                ])
    else:
        seby.pop("_sprint_origin", None)
        gabi.pop("_corpse_origin", None)

    if "reach" in darius_activity:
        if "_reach_origin" not in darius:
            darius["_reach_origin"] = tuple(darius["pos"])
        ox, oy = darius["_reach_origin"]
        darius["pos"] = [ox + 18, oy - 8]
    elif "_reach_origin" in darius and "down" not in darius_activity:
        ox, oy = darius["_reach_origin"]
        darius["pos"] = [ox, oy]


SNIPER_PHASE_NAMES = ["regroup", "movement_one", "movement_two", "movement_three"]


def _sniper_phase_index():
    name = getattr(STATE, "mission2_sniper_phase", "regroup")
    return SNIPER_PHASE_NAMES.index(name) if name in SNIPER_PHASE_NAMES else 0

def _sniper_phase():
    return SNIPER_PHASES[_sniper_phase_index()]

def _sniper_phase_name():
    return getattr(STATE, "mission2_sniper_phase", "")

def _sniper_phase_event(name):
    events = getattr(STATE, "mission2_sniper_events_fired", None)
    if events is None:
        events = set()
        STATE.mission2_sniper_events_fired = events
    if name in events:
        return False
    events.add(name)
    return True


def _sniper_actor_pos(index):
    try:
        return tuple(STATE.mission2_squad[index]["pos"])
    except Exception:
        return KILL_ZONE


def _midpoint(a, b, t=0.5):
    return (
        a[0] + (b[0] - a[0]) * t,
        a[1] + (b[1] - a[1]) * t,
    )


def _avg_points(points):
    if not points:
        return KILL_ZONE
    return (
        sum(p[0] for p in points) / len(points),
        sum(p[1] for p in points) / len(points),
    )


def _squad_focus(include_dead=True):
    pts = []
    for actor in getattr(STATE, "mission2_squad", []):
        if include_dead or actor.get("alive", True):
            pts.append(tuple(actor["pos"]))
    return _avg_points(pts) if pts else KILL_ZONE


def _sniper_camera_target(t, phase):
    """Anchor-based camera target - the camera holds fixed compositions."""
    if phase == "movement_one":
        if t < _beat("movement_one", "gabi_crack") - 25:
            return CAM_SQUAD_WIDE
        if t < _beat("movement_one", "gantry_hold"):
            return CAM_GABI_BODY          # hold completely still on the body
        if t < _beat("movement_one", "seby_react"):
            return CAM_GANTRY_REVEAL      # hold for ~200 frames on the gantry
        return CAM_SEBY_DRAG              # settle on Seby for the transition

    elif phase == "movement_two":
        if t < _beat("movement_two", "seby_crack") + 60:
            return CAM_SEBY_DRAG          # hold during the entire drag
        if t < _beat("movement_two", "darius_crack") + 40:
            return CAM_DARIUS_RADIO       # hold on Darius
        return CAM_DARIUS_RADIO

    elif phase == "movement_three":
        if STATE.player:
            return (STATE.player.rect.centerx, STATE.player.rect.centery - 20)
        return KILL_ZONE

    return KILL_ZONE


def _advance_sniper_phase():
    idx = _sniper_phase_index() + 1
    if idx >= len(SNIPER_PHASE_NAMES):
        _finish_sniper_sequence()
        return
    STATE.mission2_sniper_phase = SNIPER_PHASE_NAMES[idx]
    STATE.mission2_sniper_phase_timer = 0
    STATE.mission2_sniper_events_fired = set()


def _start_sniper_aftermath():
    STATE.mission2_stage = STAGE_COMBAT
    STATE.mission_phase = "m2_killbox_get_cover"
    STATE.mission2_post_sniper_phase = "get_cover"
    STATE.mission2_post_sniper_timer = 0

    STATE.mission2_grace_timer = SNIPER_GRACE_FRAMES

    STATE.mission2_sniper_pressure_timer = 0
    STATE.mission2_sniper_pending_timer = 0
    STATE.mission2_sniper_target = None
    STATE.mission2_sniper_suppressed = False

    STATE.mission2_sniper_lock = 0
    STATE.mission2_sniper_lock_max = SNIPER_LOCK_FRAMES
    STATE.mission2_sniper_warned = set()
    STATE.mission2_sniper_lethal_target = None
    STATE.mission2_sniper_kill_flash = 0
    STATE.mission2_cover_hold = 0

    STATE.mission2_input_freeze = 18
    STATE.mission2_camera_focus = None
    STATE.mission2_camera_focus_timer = 0

    _spawn_initial_ipa_team()

    _set_objective("GET TO COVER - sniper has the lane")


def _finish_sniper_sequence():
    STATE.mission2_fade_out = 60
    STATE.mission2_weapon_pickup_active = False
    STATE.mission2_weapon_pickup_ready = False
    _start_sniper_aftermath()


def grant_seby_os12(quiet=False):
    """Give Biribel Seby's OS-12 rifle and switch to it.
    Idempotent - safe to call more than once."""
    if getattr(STATE, "_seby_os12_granted", False):
        return
    STATE._seby_os12_granted = True
    STATE.mission2_os12_acquired = True
    STATE.os12_unlocked = True
    STATE.current_weapon = "os12"
    if not quiet:
        audio.play("rifle_handle", volume=0.6)
    STATE.mission2_heartbeat_active = False
    STATE.mission2_tinnitus_timer = min(getattr(STATE, "mission2_tinnitus_timer", 0), 30)
    STATE.mission2_radio_muffle_timer = min(getattr(STATE, "mission2_radio_muffle_timer", 0), 30)
    _m3_start_killbox_combat()


def _m3_start_killbox_combat():
    """Kick off the Route 12 kill-box wave after Biribel takes the OS-12."""
    if getattr(STATE, "_m3_killbox_started", False):
        return
    STATE._m3_killbox_started = True
    _set_objective("HOLD THE ROAD - Clear the Krap patrol")
    _start_sniper_aftermath()
    try:
        audio.play("combat_sting", volume=0.4)
    except Exception:
        pass


def _nearest_killbox_cover():
    if not STATE.player:
        return KILLBOX_COVER_POSITIONS[0]
    px, py = _player_pos()
    return min(KILLBOX_COVER_POSITIONS, key=lambda p: math.hypot(p[0] - px, p[1] - py))


def _nearest_flank_marker():
    if not STATE.player:
        return KILLBOX_FLANK_POSITIONS[0]
    px, py = _player_pos()
    return min(KILLBOX_FLANK_POSITIONS, key=lambda p: math.hypot(p[0] - px, p[1] - py))


def _sniper_alive():
    return any(_m2g(e).sniper and e.hp > 0 for e in STATE.enemies)


def _player_exposed_to_sniper():
    if (
        not STATE.player
        or not _sniper_alive()
        or getattr(STATE, "mission2_sniper_suppressed", False)
        or getattr(STATE, "mission2_stage", "") != STAGE_COMBAT
    ):
        return False

    px, py = _player_pos()
    sx, sy = SNIPER_NEST_POS

    dist = math.hypot(px - sx, py - sy)

    # The sniper should not shoot across the entire giant map,
    # but if you are anywhere near the checkpoint/gantry road and visible,
    # you are in danger.
    if dist > SNIPER_MAX_LOS_RANGE:
        return False

    # If nothing blocks line-of-sight, the sniper sees you.
    # No tiny killbox rectangle. No magic safety just because you walked past it.
    return not _wall_blocks_line(sx, sy, px, py, _solid_walls())


def _player_in_meaningful_cover():
    """Player has been in cover long enough to count as safe.

    Earlier this reset cover_hold to 0 the instant the player peeked out,
    which made peek-and-pop tactics impossible - a single exposed frame
    wiped any accumulated safe-time. The decay version drains the counter
    gracefully when exposed (so a quick peek only costs a small penalty)
    and ramps it back up while in cover.
    """
    if not STATE.player:
        return False
    if _player_exposed_to_sniper():
        STATE.mission2_cover_hold = max(
            0, getattr(STATE, "mission2_cover_hold", 0) - SNIPER_LOCK_DECAY
        )
        return False
    STATE.mission2_cover_hold = min(90, getattr(STATE, "mission2_cover_hold", 0) + 1)
    return STATE.mission2_cover_hold >= 30


def _cleanup_sniper_state():
    """Pure state cleanup for the kill-box sniper.

    Sets the suppressed flag, removes the sniper enemy from STATE.enemies,
    and clears the active fire state. Does NOT play audio, spawn particles,
    or set mission2_abandoned_nest - those are owned by either
    _suppress_or_remove_sniper() (non-cinematic path) or _start_flank_cutscene()
    (cinematic path), so the two paths don't double up on dust/radio.
    """
    if getattr(STATE, "mission2_sniper_suppressed", False):
        return
    STATE.mission2_sniper_suppressed = True
    STATE.enemies[:] = [
        e for e in STATE.enemies
        if not _m2g(e).sniper
    ]
    STATE.mission2_sniper_lasers = []
    STATE.mission2_sniper_pending_timer = 0
    STATE.mission2_sniper_target = None


def _suppress_or_remove_sniper():
    """Non-cinematic fallback: does the state cleanup + a minimal dust/radio
    pass so the sniper disappears even if the cinematic cutscene is skipped
    or fails to start. The flank route trigger should call _start_flank_cutscene()
    instead - that path owns the dust, radio, and abandoned_nest setup.
    """
    if getattr(STATE, "mission2_sniper_suppressed", False):
        return
    _cleanup_sniper_state()
    sx, sy = SNIPER_NEST_POS
    _burst(sx, sy, (90, 90, 85), 36, speed_mul=1.8)
    _burst(sx + 6, sy - 4, (130, 120, 100), 18, speed_mul=2.2)
    _burst(sx - 8, sy + 6, (70, 65, 60), 14, speed_mul=1.2)
    STATE.floating_texts.append([sx, sy - 40, "NEST ABANDONED", (220, 180, 110), 140])
    STATE.floating_texts.append([sx, sy - 22, "+ spent casings", (170, 150, 110), 120])
    STATE.mission2_abandoned_nest = {
        "pos": (sx, sy),
        "age": 0,
        "casings": [
            (_rng_legacy.randint(-18, 18), _rng_legacy.randint(-12, 12))
            for _ in range(7)
        ],
    }
    audio.play("radio_static", volume=0.24)
    _radio('VASILE: "Sniper is relocating. Clear the cleanup team."', color=C_VASILE, mark="sniper_suppressed")


def _sniper_close_execute_player():
    if getattr(STATE, "mission2_sniper_close_execute_done", False):
        return

    STATE.mission2_sniper_close_execute_done = True

    if not STATE.player:
        return

    px, py = _player_pos()

    _sniper_fire(
        (px, py),
        body=True,
        trace_life=70,
        shake=52,
    )

    _sniper_callout(
        SNIPER_CLOSE_KILL_TEXT,
        (px, py),
        color=(255, 55, 35),
        frames=120,
    )

    _burst(px, py, C_BLOOD, 70, speed_mul=2.0)
    STATE.blood_decals.append([px, py, 220, _rng_legacy.randint(20, 30)])

    STATE.player.hp = 0
    STATE.player_dead = True
    STATE.death_timer = 90
    STATE.screen_shake = max(STATE.screen_shake, 48)
    STATE.mission2_near_miss_flash = max(getattr(STATE, "mission2_near_miss_flash", 0), 50)
    STATE.mission2_tinnitus_timer = max(getattr(STATE, "mission2_tinnitus_timer", 0), 130)

    audio.play("sniper_crack", volume=1.0)
    audio.play("bullet_impact_enemy", volume=0.85)
    audio.schedule(8, "tinnitus", volume=0.55)

    STATE.floating_texts.append([
        px,
        py - 54,
        SNIPER_CLOSE_KILL_TEXT,
        (255, 70, 45),
        100,
    ])


def _update_sniper_pressure():
    if (
        STATE.mission2_stage != STAGE_COMBAT
        or not _sniper_alive()
        or getattr(STATE, "mission2_sniper_suppressed", False)
        or not STATE.player
        or STATE.player_dead
    ):
        return

    if getattr(STATE, "mission2_grace_timer", 0) > 0:
        # Grace timer countdown now happens in game_update() (main loop) so
        # it ticks down regardless of stage. Previously it was counted down
        # here, which meant it never expired during STAGE_EVIDENCE and
        # blocked all cleanup-team enemy damage. We still reset the sniper
        # lock here so the sniper doesn't acquire the player during grace.
        STATE.mission2_sniper_lock = 0
        return

    px, py = _player_pos()
    sx, sy = SNIPER_NEST_POS
    dist_to_sniper = math.hypot(px - sx, py - sy)
    exposed = _player_exposed_to_sniper()

    # Close-range instant execution
    if exposed and dist_to_sniper <= SNIPER_POINT_BLANK_RANGE:
        _sniper_close_execute_player()
        return

    if exposed:
        # Lock builds while exposed
        STATE.mission2_sniper_lock = min(
            STATE.mission2_sniper_lock_max,
            STATE.mission2_sniper_lock + 1
        )

        # Warning thresholds
        lock = STATE.mission2_sniper_lock
        lock_max = STATE.mission2_sniper_lock_max
        for thresh in SNIPER_WARN_THRESHOLDS:
            if lock == thresh and thresh not in STATE.mission2_sniper_warned:
                STATE.mission2_sniper_warned.add(thresh)
                # Add a laser snapshot at each threshold
                target = (px + _rng_legacy.randint(-12, 12), py + _rng_legacy.randint(-12, 12))
                _add_sniper_laser(target, life=55)
                audio.play("rifle_handle", volume=0.25 + 0.15 * (thresh / lock_max))

        # KILL: lock hit max
        if lock >= lock_max:
            # AEGIS Pass E: set-piece sniper shot - force=True bypasses i-frames
            # so the narrative hit always lands (the player cannot dodge the
            # intro sniper shot; that's the point of the set piece). The
            # subsequent i-frame window still applies, so the player gets a
            # breather to reposition after the hit lands.
            # AEGIS Pass F: 80ms hit-stop on the sniper hit. Longer than the
            # 50ms tactical default because the sniper shot is a set-piece
            # moment - the extra weight sells "you just got lit up by a
            # professional" and gives the player a beat to register what
            # happened before the screen resumes motion.
            STATE.player.take_damage(SNIPER_DAMAGE, force=True)
            effects.hit_stop(0.08)
            _burst(STATE.player.rect.centerx, STATE.player.rect.centery, C_BLOOD, 18, speed_mul=1.4)
            STATE.floating_texts.append([
                STATE.player.rect.centerx,
                STATE.player.rect.centery - 48,
                "SNIPER HIT",
                (255, 55, 35), 80,
            ])
            _sniper_fire_at(_player_pos(), body=True, trace_life=38, shake=26)
            # Reset for next cycle
            STATE.mission2_sniper_lock = 0
            STATE.mission2_sniper_warned = set()
            return

    else:
        # In cover: lock decays
        STATE.mission2_sniper_lock = max(0, STATE.mission2_sniper_lock - SNIPER_LOCK_DECAY)
        # If lock was partially built, slow decay gives player breathing room

def _update_post_sniper_gameplay():
    from missions.m2.draw import _start_flank_cutscene  # lazy: breaks sniper<->draw cycle
    if STATE.mission2_stage != STAGE_COMBAT:
        return
    phase = getattr(STATE, "mission2_post_sniper_phase", "")
    if not phase:
        return
    STATE.mission2_post_sniper_timer += 1
    _update_sniper_pressure()

    if phase == "get_cover":
        STATE.mission_phase = "m2_get_cover"
        if STATE.mission2_post_sniper_timer == 1:
            _spawn_initial_ipa_team()
            _set_objective("GET TO COVER - break the sniper line")
            _radio('VASILE: "Concrete blocks! Left side! Move now!"', color=(255, 170, 80), mark="post_cover")
        if _player_in_meaningful_cover() and STATE.mission2_post_sniper_timer > 45:
            STATE.mission2_post_sniper_phase = "survive"
            STATE.mission2_post_sniper_timer = 0
            STATE.mission2_sniper_pressure_timer = 70
            _radio('VASILE: "Hold there. Watch the glint. Move only between shots."', color=C_VASILE, mark="survive_killbox")
            # Player committed to cover -> IPA pours in from the flanks to
            # punish the static position.  First wave is immediate and a bit
            # bigger; follow-up waves are scheduled below in the survive phase.
            if not getattr(STATE, "mission2_reinforcement_triggered", False):
                STATE.mission2_reinforcement_triggered = True
                _spawn_reinforcement_wave(count=4, prefer_far=True)
                STATE.mission2_reinforcement_waves = 1
                STATE.mission2_reinforcement_timer = 360
                _radio('VASILE: "They saw you stop! Contacts moving in from both flanks!"',
                       color=(255, 130, 75), mark="reinforce_warn")
        elif STATE.mission2_post_sniper_timer > 360:
            # Fail-soft: if the player is confused but alive, advance to survival
            # instead of trapping the mission in a tutorial objective.
            STATE.mission2_post_sniper_phase = "survive"
            STATE.mission2_post_sniper_timer = 0
    elif phase == "survive":
        STATE.mission_phase = "m2_survive_killbox"
        _set_objective("SURVIVE THE KILL-BOX - stay behind cover")
        # Keep IPA pressure up while the player holds cover.  Waves taper
        # off in size, and stop entirely once a cap is reached so the fight
        # can actually be cleared.
        if getattr(STATE, "mission2_reinforcement_triggered", False):
            STATE.mission2_reinforcement_timer = max(0, STATE.mission2_reinforcement_timer - 1)
            if (STATE.mission2_reinforcement_timer <= 0
                    and STATE.mission2_reinforcement_waves < 3
                    and len(STATE.enemies) < 7):
                STATE.mission2_reinforcement_waves += 1
                wave_size = 3 if STATE.mission2_reinforcement_waves == 2 else 2
                _spawn_reinforcement_wave(count=wave_size, prefer_far=False)
                STATE.mission2_reinforcement_timer = 420
        if not getattr(STATE, "mission2_late_reveal_played", False) and STATE.mission2_post_sniper_timer > 480:
            STATE.mission2_late_reveal_played = True
            _radio('VASILE: "Biribel - the tanker manifest - it lists a second cargo..."', color=C_VASILE, mark="late_reveal")
        # Advance to CLEAR when any of: time-fail-safe, sniper dead,
        # or the player actually cleared the current reinforcement wave
        # (at least one wave must have spawned so this can't fire instantly).
        waves_done = (
            getattr(STATE, "mission2_reinforcement_triggered", False)
            and getattr(STATE, "mission2_reinforcement_waves", 0) >= 1
            and len(STATE.enemies) == 0
        )
        if STATE.mission2_post_sniper_timer > 520 or not _sniper_alive() or waves_done:
            STATE.mission2_post_sniper_phase = "clear"
            STATE.mission2_post_sniper_timer = 0
            _radio('VASILE: "They\'re falling back to regroup. Push through - the truck is ahead."', color=(255, 170, 80), mark="clear_ipa")
    elif phase == "clear":
        STATE.mission_phase = "m2_clear_ipa"
        # Don't count the sniper -- it's removed by the flank cutscene, not
        # by the player shooting it. Counting it here would softlock the
        # phase at "1 hostile left" forever.
        ground_enemies = [e for e in STATE.enemies if not _m2g(e).sniper]
        if ground_enemies:
            _set_objective(f"CLEAR REMAINING IPA CONTACTS ({len(ground_enemies)} left)")
        else:
            # All non-sniper IPA dead -> push player to flank the sniper.
            # This is the phase where the orange FLANK ROUTE circle appears.
            STATE.mission2_post_sniper_phase = "flank"
            STATE.mission2_post_sniper_timer = 0
            _radio('VASILE: "Center lane is death. Flank through the ditch or service road."', color=(255, 170, 80), mark="flank_sniper")
    elif phase == "flank":
        STATE.mission_phase = "m2_flank_sniper"
        _set_objective("SNIPER STILL ACTIVE - flank to the orange circle")
        # DEBUG: Press F6 to skip the flank cutscene and go directly to the
        # cleanup-team fight + truck inspection phase.
        if _m2_world._last_keys and _m2_world._last_keys[pygame.K_F6]:
            print("[DEBUG] F6 - skipping flank phase, jumping to cleanup team")
            _cleanup_sniper_state()
            # Force the cutscene to finish instantly so the "done" phase
            # spawns the cleanup team on the next frame.
            STATE.mission2_flank_cutscene_timer = 0
            STATE.mission2_flank_cutscene_max = 0
            STATE.player_locked = False
            STATE.mission2_camera_focus = None
            STATE.mission2_camera_focus_timer = 0
            STATE.mission2_post_sniper_phase = "done"
            STATE.mission2_post_sniper_timer = 0
            STATE.screen_shake = 0
            return
        px, py = _player_pos()
        d_flank = min(math.hypot(px - f[0], py - f[1]) for f in KILLBOX_FLANK_POSITIONS)
        d_nest = math.hypot(px - SNIPER_FLANK_POS[0], py - SNIPER_FLANK_POS[1])
        reached_flank = d_flank < 260
        reached_nest_angle = d_nest < 220
        if not hasattr(STATE, "_dbg_flank_tick"):
            STATE._dbg_flank_tick = 0
        STATE._dbg_flank_tick += 1
        if STATE._dbg_flank_tick % 30 == 0:
            print(f"[FLANK DEBUG] px={px:.0f} py={py:.0f} "
                  f"d_flank={d_flank:.0f} d_nest={d_nest:.0f} "
                  f"reached_flank={reached_flank} reached_nest={reached_nest_angle} "
                  f"sniper_alive={_sniper_alive()} "
                  f"suppressed={getattr(STATE, 'mission2_sniper_suppressed', False)} "
                  f"nest_pos={SNIPER_FLANK_POS} markers={KILLBOX_FLANK_POSITIONS}")
        if reached_flank or reached_nest_angle or not _sniper_alive():
            already = getattr(STATE, "mission2_sniper_suppressed", False)
            print(f"[FLANK TRIGGER] firing cutscene. already_suppressed={already} "
                  f"reached_flank={reached_flank} reached_nest={reached_nest_angle} "
                  f"sniper_alive={_sniper_alive()}")
            # Cleanup first (sets suppressed flag, removes sniper enemy,
            # clears active fire state). Then start the 180-frame cinematic:
            # letterbox, sniper silhouette ducking out, big "NEST ABANDONED"
            # stamp, camera focus on the gantry, player locked.
            _cleanup_sniper_state()
            _start_flank_cutscene()
            # _start_flank_cutscene() sets mission2_camera_focus to
            # CAM_GANTRY_REVEAL for 200 frames, so the previous
            # _sniper_set_focus(SNIPER_NEST_POS, frames=140) call here would
            # override the cutscene's camera and is now intentionally omitted.
            STATE.mission2_post_sniper_phase = "done"
            STATE.mission2_post_sniper_timer = 0
    elif phase == "done":
        STATE.mission_phase = "m2_clear_ipa"
        # Wait for the flank cutscene to finish before spawning the cleanup
        # team. The cutscene locks the player for 9 seconds - spawning
        # enemies during that window would let them shoot the player while
        # they can't fight back. The cutscene timer is set to 0 by
        # _update_flank_cutscene() when t reaches 1 (its final frame).
        if getattr(STATE, "mission2_flank_cutscene_timer", 0) > 0:
            return  # cutscene still playing, hold here
        # Cutscene has finished. Spawn the final "cleanup team" that Vasile's
        # radio line promised - a small authored squad between the player's
        # flank position and the IPA truck, so the player has to clear them
        # before they can inspect the manifest. The stage handler in
        # _update_mission2_stage gates the STAGE_TRUCK transition on
        # STATE.enemies being empty (and the cutscene timer being 0).
        if not getattr(STATE, "mission2_cleanup_team_spawned", False):
            STATE.mission2_cleanup_team_spawned = True
            # 3 IPA grunts south of the truck, blocking the approach from
            # both flank routes. Tiles chosen so they're visible from the
            # flank markers but not on top of the player.
            _spawn_enemy(44, 36, hp=110, speed=2.0)
            _spawn_enemy(50, 38, hp=110, speed=2.0)
            _spawn_enemy(48, 40, hp=110, speed=2.0)
            _set_objective("Clear the IPA cleanup team blocking the truck")
            _radio('VASILE: "Cleanup squad\'s between you and the truck. Drop them."',
                   color=C_VASILE, mark="cleanup_spawn")
            # OS-12 spare mags are capped at 2 from pickup - no mid-mission
            # reward. The cleanup team is a combat beat, not an ammo drop.


def _smoothstep(t):
    return t * t * (3 - 2 * t) if 0 < t < 1 else max(0, min(1, t))

def _ease_out_cubic_m2(t):
    return 1 - pow(1 - max(0, min(1, t)), 3)

def _pulse01(t, period=60):
    """Sawtooth 0→1 over `period` frames, resets at every multiple."""
    return max(0, min(1, (t % period) / period))

def _sniper_set_focus(pos, frames=90, snap=False):
    STATE.mission2_camera_focus = (pos[0], pos[1])
    STATE.mission2_camera_focus_timer = frames
    if snap:
        _snap_camera_to(pos)


def _sniper_callout(label, pos, color=(255, 70, 45), frames=105):
    STATE.mission2_death_callout = {
        "label": label, "pos": (pos[0], pos[1]),
        "color": color, "life": frames, "max_life": frames,
    }


def _sniper_fire(target_pos, body=False, concrete=False, near_miss=False,
                 trace_life=44, shake=30, dead_air=False):
    kind = "near_miss" if near_miss else "concrete" if concrete else "body"
    STATE.mission2_sniper_traces.append({
        "from": SNIPER_NEST_POS, "to": target_pos, "kind": kind,
        "life": trace_life, "max_life": trace_life,
    })
    STATE.mission2_sniper_muzzle_flashes.append({
        "pos": SNIPER_NEST_POS, "life": 16, "max_life": 16,
    })
    STATE.mission2_sniper_flash = max(getattr(STATE, "mission2_sniper_flash", 0),
                                      24 if near_miss else 16)
    STATE.screen_shake = max(STATE.screen_shake, shake)
    audio.play("bullet_snap", volume=0.9 if near_miss else 0.6)
    audio.schedule(2, "sniper_crack", volume=1.0)
    audio.play("rig_low_boom", volume=0.2)
    if body:
        audio.schedule(5, "bullet_impact_enemy", volume=0.86)
    if concrete or near_miss:
        audio.schedule(5, "concrete_impact", volume=0.95 if near_miss else 0.72)
    _burst(target_pos[0], target_pos[1], (220, 196, 128), 34 if near_miss else 22, speed_mul=2.3)
    _burst(target_pos[0], target_pos[1], (120, 118, 108), 26 if near_miss else 14, speed_mul=1.7)
    audio.schedule(12, "radio_static", volume=0.34 if near_miss else 0.20)
    if near_miss:
        STATE.mission2_near_miss_flash = max(getattr(STATE, "mission2_near_miss_flash", 0), 64)
        STATE.mission2_tinnitus_timer = max(getattr(STATE, "mission2_tinnitus_timer", 0), 150)
        audio.schedule(8, "tinnitus", volume=0.62)
    try:
        if dead_air:
            audio.duck_ambience(frames=_beat("movement_one", "silence_frames", 110), factor=0.0)
        else:
            audio.duck_ambience(frames=55 if not near_miss else 130,
                                factor=0.16 if not near_miss else 0.05)
    except Exception:
        pass


def _sniper_concrete_impact(pos, trace_life=32, shake=20):
    _sniper_fire(pos, concrete=True, trace_life=trace_life, shake=shake)


def _sniper_fire_at(target_pos, body=False, concrete=False, trace_life=44, shake=30):
    _sniper_fire(target_pos, body=body, concrete=concrete, trace_life=trace_life, shake=shake)


def _draw_sniper_callout(surface, fcx, fcy):
    from missions.m2.draw import _world  # lazy: breaks sniper<->draw cycle
    callout = getattr(STATE, "mission2_death_callout", None)
    if not callout:
        return
    sx, sy = _world(callout["pos"], fcx, fcy)
    life = callout.get("life", 0)
    max_life = max(1, callout.get("max_life", 1))
    t = max(0.0, min(1.0, life / max_life))
    color = callout.get("color", (255, 70, 45))
    alpha = int(255 * t)
    r = int(30 + (1.0 - t) * 34)
    m = pygame.Surface((190, 190), pygame.SRCALPHA)
    cx = cy = 95
    pygame.draw.circle(m, (*color, alpha), (cx, cy), r, 3)
    pygame.draw.circle(m, (*color, alpha // 2), (cx, cy), r + 10, 1)
    for ang in (0, 90, 180, 270):
        a = math.radians(ang)
        pygame.draw.line(m, (*color, alpha),
                         (cx + math.cos(a) * (r - 6), cy + math.sin(a) * (r - 6)),
                         (cx + math.cos(a) * (r + 14), cy + math.sin(a) * (r + 14)), 2)
    surface.blit(m, (sx - cx, sy - cy))
    lbl = font_terminal.render(callout["label"], True, color)
    lbl.set_alpha(alpha)
    bg = pygame.Surface((lbl.get_width() + 18, lbl.get_height() + 8), pygame.SRCALPHA)
    bg.fill((0, 0, 0, min(190, alpha)))
    pygame.draw.rect(bg, (*color, min(200, alpha)), bg.get_rect(), 1)
    surface.blit(bg, (sx - bg.get_width() // 2, sy - r - 52))
    surface.blit(lbl, (sx - lbl.get_width() // 2, sy - r - 48))


def _m0_regroup(pt):
    all_set = True
    for actor, target in zip(STATE.mission2_squad, REGROUP_TARGET_POSITIONS):
        actor["look_at"] = KILL_ZONE
        d = math.hypot(target[0] - actor["pos"][0], target[1] - actor["pos"][1])
        if d > 6:
            all_set = False
            actor["activity"] = "regrouping"
            _move_actor_towards(actor, target, rate=0.06, max_step=2.4)
        else:
            actor["pos"][0], actor["pos"][1] = target[0], target[1]
            actor["activity"] = "covering"
    if _beat_now("regroup", pt, "spread_line") and _sniper_phase_event("m0_spread"):
        _radio('VASILE: "Form up at the barrier. Eyes up."', mark="m0_spread", duration=120)


def _m1_regroup_wrong_scan(pt):
    """SHOCK - Gabi dies mid-sentence, no warning."""
    gabi, seby, darius = STATE.mission2_squad
    for actor, target in zip(STATE.mission2_squad, REGROUP_TARGET_POSITIONS):
        if actor.get("alive", True):
            d = math.hypot(target[0] - actor["pos"][0],
                           target[1] - actor["pos"][1])
            if d > 3:
                _move_actor_towards(actor, target, rate=0.10, max_step=2.0)
    if gabi.get("alive"):
        gabi["activity"] = "watching lane"; gabi["look_at"] = KILL_ZONE
    if seby.get("alive"):
        seby["activity"] = "covering west"; seby["look_at"] = _tc(18, 60)
    if darius.get("alive"):
        darius["activity"] = "holding radio"; darius["look_at"] = KILL_ZONE

    if _beat_now("movement_one", pt, "regroup_line") and _sniper_phase_event("m1_gabi1"):
        _radio('GABI: "Nobody likes this lane."', color=(220, 220, 205), mark="m1_gabi1", duration=120)
    if _beat_now("movement_one", pt, "scan_west") and _sniper_phase_event("m1_scan"):
        _radio("SEBY: \"West side's clear. Just burned-out cars.\"", color=(255, 210, 180), mark="m1_scan", duration=120)
    # If the player tried to save Gabi during the attempt window, fire a
    # Vasile line acknowledging it.  Otherwise stay silent - Vasile never
    # saw Biribel's attempt because he's focused on Gabi himself.
    if (getattr(STATE, "mission2_tried_to_save", False)
            and not getattr(STATE, "mission2_tried_to_save_acknowledged", False)
            and pt >= _beat("movement_one", "gabi_crack", 300) + 30):
        STATE.mission2_tried_to_save_acknowledged = True
        _radio('VASILE: "Biribel - stay back. Gabi is gone."',
               color=C_VASILE, mark="save_attempt_ack", duration=140)
    if _beat_now("movement_one", pt, "gabi_crack") and _sniper_phase_event("m1_crack"):
        _radio('GABI: "Vasile, I have-"', color=(220, 220, 205), mark="m1_last", duration=55)
        _kill_actor(0, SNIPER_NEST_POS, dead_air=True)
    if _beat_now("movement_one", pt, "vasile_down") and _sniper_phase_event("m1_vasile"):
        _radio('VASILE: "Everybody DOWN. Do not move."',
               color=C_VASILE, mark="m1_vasile", duration=140)
    if _beat_now("movement_one", pt, "origin_flash") and _sniper_phase_event("m1_origin"):
        STATE.mission2_sniper_origin_revealed = True
        STATE.mission2_sniper_flash = 12
        STATE.mission2_sniper_silhouette_flash = 14
        STATE.mission2_sniper_muzzle_flashes.append({"pos": SNIPER_NEST_POS, "life": 16, "max_life": 16})
        _sniper_set_focus(SNIPER_NEST_POS, frames=55)
        audio.play("sniper_crack", volume=0.5)
    if _beat_now("movement_one", pt, "gantry_hold") and _sniper_phase_event("m1_silhouette2"):
        STATE.mission2_sniper_silhouette_flash = 20
        STATE.mission2_sniper_muzzle_flashes.append({"pos": SNIPER_NEST_POS, "life": 16, "max_life": 16})
        audio.play("sniper_crack", volume=0.35)
    if _beat_now("movement_one", pt, "seby_react") and _sniper_phase_event("m1_react"):
        _radio('SEBY: "GABI! NO!"', color=(255, 210, 180), mark="m1_react", duration=120)
        if seby.get("alive"):
            seby["activity"] = "breaking"; seby["look_at"] = gabi["pos"]


def _m2_seby_darius_die(pt):
    """DESPERATION - Seby drags Gabi, both he and Darius die."""
    gabi, seby, darius = STATE.mission2_squad
    gabi["alive"] = False
    gabi["activity"] = "down"

    seby_breaks   = _beat("movement_two", "seby_breaks", 70)
    seby_arrives  = _beat("movement_two", "seby_arrives", 190)
    drag_end      = _beat("movement_two", "seby_drag_to_cover_end", 380)
    seby_shot     = _beat("movement_two", "seby_crack", 430)

    if pt < seby_breaks:
        if seby.get("alive"):   seby["activity"]   = "frozen shock"
        if darius.get("alive"): darius["activity"] = "frozen"
    elif pt < seby_arrives:
        if seby.get("alive"):   seby["activity"]   = "sprinting_to_gabi"
        if darius.get("alive"): darius["activity"] = "frozen"
    elif pt < drag_end:
        if seby.get("alive"):   seby["activity"]   = "dragging_body"
        if darius.get("alive"): darius["activity"] = "turning to radio"

    if _beat_now("movement_two", pt, "vasile_cover") and _sniper_phase_event("m2_vasile1"):
        _radio('VASILE: "Seby - stay low - do NOT go out there."',
               color=C_VASILE, mark="m2_vasile1", duration=120)
    if _beat_now("movement_two", pt, "vasile_hold") and _sniper_phase_event("m2_vasile2"):
        _radio('VASILE: "Biribel. Stay behind the barrier. Do not look up."',
               color=C_VASILE, mark="m2_vasile2", duration=160)
    if _beat_now("movement_two", pt, "seby_breaks") and _sniper_phase_event("m2_break"):
        _radio('SEBY: "Hold on - I got you - I GOT YOU-"', color=(255, 210, 180), mark="m2_break", duration=130)
    if _beat_now("movement_two", pt, "seby_crack") and _sniper_phase_event("m2_seby"):
        _kill_actor(1, SNIPER_NEST_POS)
    if pt >= seby_shot and darius.get("alive"):
        darius["activity"] = "reaching for radio"
    if _beat_now("movement_two", pt, "darius_reaches") and _sniper_phase_event("m2_dar_reach"):
        _radio('DARIUS: "Mayday, mayday, this is-"', color=(255, 190, 130), mark="m2_mayday", duration=90)
        _sniper_set_focus(_sniper_actor_pos(2), frames=130)
    if _beat_now("movement_two", pt, "darius_crack") and _sniper_phase_event("m2_dar"):
        _kill_actor(2, SNIPER_NEST_POS)


def _m3_near_miss_handoff(pt):
    """YOU'RE NEXT - near-miss, weapon pickup, then hard cut."""
    for actor in STATE.mission2_squad:
        actor["alive"] = False
        actor["activity"] = "down"

    # Beat: near_miss - sniper barely misses Biribel
    if _beat_now("movement_three", pt, "near_miss") and _sniper_phase_event("m3_miss"):
        target = ((STATE.player.rect.centerx + 40, STATE.player.rect.centery - 24)
                  if STATE.player else KILL_ZONE)
        _sniper_set_focus(target, frames=120, snap=True)
        _sniper_fire(target, concrete=True, near_miss=True, trace_life=60, shake=42)
        _sniper_callout("MISSED - YOU'RE NEXT", target, color=(255, 190, 90), frames=120)
        STATE.mission2_chromatic_timer = 90
        STATE.mission2_radio_muffle_timer = 200
        STATE.mission2_heartbeat_active = True
        STATE.mission2_heartbeat_timer = 0
        _radio('VASILE: "Biribel - MOVE!"', mark="m3_move", duration=120)

    # Beat: weapon_pickup - trigger the narrated cutscene, ease camera to Seby
    if _beat_now("movement_three", pt, "weapon_pickup") and _sniper_phase_event("m3_pickup"):
        seby_pos = tuple(STATE.mission2_squad[1].get("pos", _tc(35, 35)))
        _sniper_set_focus((seby_pos[0] + 20, seby_pos[1] - 30), frames=180, snap=False)
        STATE.mission2_weapon_pickup_ready = False
        STATE._m3_pickup_done = True
        STATE.request_seby_pickup_cutscene = True
        STATE.player_locked = True


# The sniper ambush plays as a low-poly 3D film (missions/m2/sniper3d.py).
# Set False to fall back to the old top-down in-engine sequence below.
SNIPER_3D = True


def _end_sniper3d():
    """3D film finished (or skipped): leave the 2D world in the state the
    old sequence produced. The film already shows Biribel taking Seby's
    OS-12, so grant it and go straight to the kill-box fight."""
    STATE.mission2_sniper3d = None
    squad = getattr(STATE, "mission2_squad", []) or []
    gabi_p = REGROUP_TARGET_POSITIONS[0]
    spots = [gabi_p, _midpoint(gabi_p, REGROUP_TARGET_POSITIONS[1], 0.55), FIELD_RADIO_POS]
    for actor, spot in zip(squad, spots):
        actor["alive"] = False
        actor["activity"] = "down"
        actor["reaction"] = "down"
        actor["pos"] = [spot[0], spot[1]]
        STATE.blood_decals.append([spot[0], spot[1], 190, _rng_legacy.randint(16, 24)])
    STATE.mission2_sniper_origin_revealed = True
    STATE.mission2_chromatic_timer = 90
    STATE.mission2_radio_muffle_timer = 200
    STATE.mission2_heartbeat_active = True
    STATE.mission2_heartbeat_timer = 0
    STATE._m3_pickup_done = True
    STATE.request_seby_pickup_cutscene = False
    STATE.mission2_fade_out = 60
    STATE.mission2_weapon_pickup_active = False
    STATE.mission2_weapon_pickup_ready = False
    grant_seby_os12(quiet=True)          # also starts the kill-box aftermath
    if STATE.mission2_stage != STAGE_COMBAT:
        _start_sniper_aftermath()        # already granted (e.g. a retry): still un-stick
    STATE.player_locked = False


def _update_sniper_sequence():
    cine = getattr(STATE, "mission2_sniper3d", None)
    if cine is not None:
        try:
            cine.update()
        except Exception as exc:          # never soft-lock the mission on a render bug
            print(f"[m2] 3D sniper film failed, skipping: {exc}")
            cine.done = True
        if cine.done:
            _end_sniper3d()
        return
    pt = int(getattr(STATE, "mission2_sniper_phase_timer", 0))
    phase = _sniper_phase_name()
    new_target = _sniper_camera_target(pt, phase)
    existing = STATE.mission2_camera_focus
    if existing is None:
        STATE.mission2_camera_focus = new_target
    else:
        cx, cy = existing
        nx, ny = new_target
        if math.hypot(nx - cx, ny - cy) > 4:
            STATE.mission2_camera_focus = new_target
    _sniper_phase_activity()
    if phase == "regroup":           _m0_regroup(pt)
    elif phase == "movement_one":    _m1_regroup_wrong_scan(pt)
    elif phase == "movement_two":    _m2_seby_darius_die(pt)
    elif phase == "movement_three":  _m3_near_miss_handoff(pt)
    _update_squad_actor_positions()
    STATE.mission2_sniper_phase_timer = pt + 1
    if STATE.mission2_sniper_phase_timer >= _sniper_phase().get("duration", 120):
        _advance_sniper_phase()


def _start_sniper_sequence():
    STATE.mission2_stage = STAGE_SNIPER
    STATE.mission_phase = "m2_sniper"
    STATE.mission2_sniper_phase = "regroup"
    STATE.mission2_sniper_phase_timer = 0
    STATE.mission2_sniper_events_fired = set()
    STATE.mission2_sniper_origin_revealed = False
    STATE.mission2_sniper_silhouette_flash = 0
    STATE.mission2_sniper_flash = 0
    STATE.mission2_death_callout = None
    STATE.mission2_camera_focus = SNIPER_ARENA_CAM
    STATE.mission2_camera_focus_timer = 0
    # Teleport the squad to REGROUP_ENTRY_POSITIONS so they are on-camera
    # for the cutscene. Without this they stay at their investigation
    # posts (around row 41-42) and are out of frame while the camera
    # holds on the kill-box at row 30-35.
    for actor, entry in zip(STATE.mission2_squad, REGROUP_ENTRY_POSITIONS):
        actor["alive"] = True
        actor["pos"] = list(entry)
        actor["activity"] = "regrouping"
        actor.pop("_sprint_origin", None)
        actor.pop("_corpse_origin", None)
        actor.pop("_reach_origin", None)
    _snap_camera_to(SNIPER_ARENA_CAM)
    _set_objective("")
    STATE.mission2_sniper3d = None
    if SNIPER_3D:
        try:
            from missions.m2.sniper3d import SniperCinematic
            STATE.mission2_sniper3d = SniperCinematic()
        except Exception as exc:
            print(f"[m2] 3D sniper film unavailable, using in-engine version: {exc}")
            STATE.mission2_sniper3d = None
    if STATE.mission2_sniper3d is None:
        audio.play("radio_static", volume=0.2)


def _kill_actor(index, origin_pos, dead_air=False):
    actor = STATE.mission2_squad[index]
    if not actor.get("alive", True):
        return
    actor["alive"] = False
    actor["activity"] = "down"
    pos = tuple(actor.get("pos", (0, 0)))
    name = actor.get("name", "SQUAD")
    _sniper_callout(f"{name} DOWN", pos, color=(255, 70, 45), frames=110)
    _sniper_fire(pos, body=True, trace_life=60, shake=22, dead_air=dead_air)
    _burst(pos[0], pos[1], C_BLOOD, 46, speed_mul=1.2)
    STATE.blood_decals.append([pos[0], pos[1], 190, _rng_legacy.randint(16, 24)])
    STATE.mission2_chromatic_timer = max(getattr(STATE, "mission2_chromatic_timer", 0), 28)


def _add_sniper_laser(target_pos, life=55):
    STATE.mission2_sniper_lasers.append({"from": SNIPER_NEST_POS, "to": target_pos, "life": life})


def _spawn_initial_ipa_team():
    if "initial_ipa_team" in STATE.mission2_events:
        return
    STATE.mission2_events.add("initial_ipa_team")
    # Sniper enemy is a facing/HP marker only (the kill-box pressure system
    # drives actual fire using SNIPER_NEST_POS). Place the sniper actor AT
    # SNIPER_NEST_POS so it visually sits on the gantry catwalk where the
    # gantry drawing shows the silhouette. The gantry wall is now only the
    # lower supports so LOS is clear from the catwalk down to the road.
    spawned = [
        _spawn_enemy(58, 26, hp=90, speed=0.0, sniper=True),
        _spawn_enemy(47, 35, hp=115, speed=1.85),
        _spawn_enemy(52, 41, hp=115, speed=1.85),
        _spawn_enemy(42, 31, hp=105, speed=1.75),
    ]
    for e in spawned:
        e.fire_cooldown = 150 + _rng_legacy.randint(0, 80)
    _radio('VASILE: "IPA rifles from the gantry. Not MAG. Clear the lanes."', color=(255, 170, 80), mark="ipa_reveal")


def _spawn_reinforcement_wave(count=3, prefer_far=True):
    """Pour in IPA reinforcements from kill-box perimeter spawn anchors.

    Triggered when the player commits to cover during the kill-box.  The wave
    picks spawn anchors farther from the player so it reads as enemies closing
    in from the flanks rather than materializing on top of them.  Each spawn
    gets a small dust/spark burst so it doesn't pop in silently.
    """
    if not STATE.player:
        return
    px, py = _player_pos()
    anchors = list(KILLBOX_REINFORCEMENT_SPAWNS)
    # Sort by distance; pick from the far half if prefer_far, else random.
    anchors.sort(key=lambda a: math.hypot(_tc(*a)[0] - px, _tc(*a)[1] - py),
                 reverse=prefer_far)
    pool = anchors[: max(count + 2, 4)]
    _rng_legacy.shuffle(pool)
    spawned = []
    walls = list(STATE.walls)
    for col, row in pool[:count]:
        # Small tile jitter so successive waves don't stack identically.
        jc = col + _rng_legacy.randint(-1, 1)
        jr = row + _rng_legacy.randint(-1, 1)
        if not (0 <= jc < MAP_W and 0 <= jr < MAP_H):
            continue
        # Skip spawns whose 32x32 footprint would overlap a wall - leaving
        # the enemy stuck inside geometry. Try small offsets before giving up.
        placed = False
        for dx, dy in ((0, 0), (2, 0), (-2, 0), (0, 2), (0, -2)):
            tc = jc + dx
            tr_ = jr + dy
            if not (0 <= tc < MAP_W and 0 <= tr_ < MAP_H):
                continue
            wx, wy = _tc(tc, tr_)
            test_rect = pygame.Rect(wx - 16, wy - 16, 32, 32)
            if not any(test_rect.colliderect(w) for w in walls):
                e = _spawn_enemy(tc, tr_, hp=100, speed=2.05)
                e.fire_cooldown = 70 + _rng_legacy.randint(0, 50)
                spawned.append(e)
                ex, ey = e.rect.center
                _burst(ex, ey, (120, 110, 95), 14, speed_mul=1.6)
                _burst(ex, ey, (255, 200, 110), 4, speed_mul=2.1)
                placed = True
                break
        if not placed:
            continue
    if spawned:
        audio.play("radio_static", volume=0.18)
        audio.schedule(8, "footstep", volume=0.35)
    return spawned


def _spawn_control_cleanup():
    """Spawn the first wave of IPA cleanup troops in the control sector.

    Called once when the player closes the 'COMMS LOST' card and transitions
    into STAGE_EVIDENCE. This used to be the ONLY post-tanker enemy spawn -
    2 enemies, one-shot, never reinforced. The evidence phase felt empty and
    anticlimactic as a result.

    Now spawns wave 1 (4 enemies in the control building) and arms a 3-wave
    reinforcement schedule. _update_evidence_waves() in the stage update
    loop drips in waves 2 and 3 with OVERLAP - wave 2 fires while wave 1
    still has 1 enemy alive, wave 3 fires 6 seconds into wave 2 - so the
    player gets no breathing room between waves.

    Difficulty pass: HP raised (105→115), enemy count raised (2→4), and
    all evidence-wave enemies get the is_evidence_wave flag which gives
    them a faster fire cooldown (50 frames vs the global 60).
    """
    if "control_cleanup" in STATE.mission2_events:
        return
    STATE.mission2_events.add("control_cleanup")
    # Wave 1: 4 enemies in the control building (was 2). Mix of positions
    # so they don't all funnel through one door.
    for col, row in [(54, 20), (64, 22), (58, 18), (61, 24)]:
        e = _spawn_enemy(col, row, hp=115, speed=2.0)
        e.is_evidence_wave = True
    # Arm the reinforcement schedule. Wave 2 fires when wave 1 has ≤1 enemy
    # left (no breathing room) OR after 18 seconds. Wave 3 fires 6 seconds
    # into wave 2 regardless of clear state.
    STATE.mission2_evidence_wave = 1
    STATE.mission2_evidence_wave_timer = 18 * 60   # 18 seconds at 60fps
    STATE.mission2_evidence_wave_cleared = False
    _radio('SYSTEM: IPA cleanup team in control sector.', color=(255, 130, 75), mark="cleanup", allow_when_cut=True)


def _spawn_evidence_reinforcement_wave(wave_num):
    """Spawn a reinforcement wave during the evidence phase.

    Wave 2: 5 enemies - 3 from the nearest perimeter anchors + 2 flankers
    from inside the control building (behind the player).
    Wave 3: 7 enemies - 4 from the nearest perimeter + 3 flankers from
    the control building.

    Spawn anchors are sorted by NEAREST distance to the player (was farthest)
    so enemies appear close and apply pressure immediately, instead of
    walking toward the player for 2+ seconds while getting picked off.

    The orange telegraph burst was removed - only the brown dust kick
    remains, so spawns read as enemies appearing, not as warning flares.

    All evidence-wave enemies get the is_evidence_wave flag for faster
    fire cooldown (50 frames vs the global 60).
    """
    if not STATE.player:
        return
    px, py = _player_pos()

    # ── Determine wave composition ──
    if wave_num == 2:
        perimeter_count = 3
        flanker_count = 2
        hp = 120
        speed = 2.05
    else:  # wave 3
        perimeter_count = 4
        flanker_count = 3
        hp = 125
        speed = 2.1

    walls = list(STATE.walls)
    spawned = []

    # ── Perimeter spawns - NEAREST to player (was farthest) ──
    # Closest-first means enemies appear 1-2 tiles away and apply pressure
    # immediately. The player has to react, not snipe.
    anchors = list(KILLBOX_REINFORCEMENT_SPAWNS)
    anchors.sort(key=lambda a: math.hypot(_tc(*a)[0] - px, _tc(*a)[1] - py),
                 reverse=False)  # nearest first
    pool = anchors[: max(perimeter_count + 2, 4)]
    _rng_legacy.shuffle(pool)

    def _try_spawn(col, row):
        """Try to spawn at (col,row) or nearby. Returns enemy or None."""
        jc = col + _rng_legacy.randint(-1, 1)
        jr = row + _rng_legacy.randint(-1, 1)
        if not (0 <= jc < MAP_W and 0 <= jr < MAP_H):
            return None
        for dx, dy in ((0, 0), (2, 0), (-2, 0), (0, 2), (0, -2)):
            tc = jc + dx
            tr_ = jr + dy
            if not (0 <= tc < MAP_W and 0 <= tr_ < MAP_H):
                continue
            wx, wy = _tc(tc, tr_)
            test_rect = pygame.Rect(wx - 16, wy - 16, 32, 32)
            if not any(test_rect.colliderect(w) for w in walls):
                e = _spawn_enemy(tc, tr_, hp=hp, speed=speed)
                e.fire_cooldown = 70 + _rng_legacy.randint(0, 50)
                e.is_evidence_wave = True
                spawned.append(e)
                ex, ey = e.rect.center
                # Dust kick only - no orange telegraph burst (was removed
                # so spawns don't advertise themselves).
                _burst(ex, ey, (120, 110, 95), 14, speed_mul=1.6)
                return e
        return None

    # Spawn perimeter enemies.
    for col, row in pool[:perimeter_count]:
        _try_spawn(col, row)

    # ── Flanker spawns - from inside the control building ──
    # These come from BEHIND the player, forcing them to watch two directions.
    flank_anchors = list(KILLBOX_FLANK_SPAWNS)
    _rng_legacy.shuffle(flank_anchors)
    for col, row in flank_anchors[:flanker_count]:
        _try_spawn(col, row)

    if spawned:
        wave_label = "SECOND" if wave_num == 2 else "FINAL"
        _radio(
            f'SYSTEM: IPA {wave_label} WAVE INBOUND - {len(spawned)} HOSTILES',
            color=(255, 130, 75), mark=f"evidence_wave_{wave_num}",
            allow_when_cut=True,
        )
        audio.play("radio_static", volume=0.22)
        audio.schedule(8, "footstep", volume=0.35)


def _update_evidence_waves():
    """Drive the multi-wave reinforcement schedule during STAGE_EVIDENCE.

    Called every frame from the STAGE_EVIDENCE branch of the stage update.
    Waves now OVERLAP for sustained pressure:

      - Wave 2 fires when wave 1 has ≤1 enemy left (no breathing room)
        OR after 18 seconds (hard cap so campers can't stall forever).
      - Wave 3 fires 6 seconds (360 frames) into wave 2, regardless of
        how many wave-2 enemies are still alive. This is the "overwhelm"
        beat - the player has to deal with wave 2 survivors AND wave 3
        reinforcements simultaneously.

    A concurrent-alive cap of 8 prevents snowballing: if 8 enemies are
    already alive when a wave is supposed to fire, the wave waits until
    at least one dies. This keeps the fight intense without becoming
    impossible.
    """
    wave = getattr(STATE, "mission2_evidence_wave", 0)
    if wave >= 3:
        return   # all waves spent

    timer = getattr(STATE, "mission2_evidence_wave_timer", 0)
    alive_count = len(STATE.enemies)
    # "Cleared" threshold for wave 1 → wave 2 transition: ≤1 enemy left
    # (was 0). This removes the breathing room - wave 2 spawns while the
    # last wave-1 enemy is still being finished off.
    wave1_near_cleared = alive_count <= 1

    timer -= 1
    STATE.mission2_evidence_wave_timer = max(0, timer)

    # Concurrent alive cap - prevents snowballing when waves overlap.
    # If 8 enemies are already alive, hold the next wave until one dies.
    MAX_CONCURRENT = 8
    if alive_count >= MAX_CONCURRENT:
        return  # wait for the player to make progress

    # Wave 2 fires when:
    #   - timer expires (18s hard cap), OR
    #   - wave 1 has ≤1 enemy left (overlap - no breathing room)
    if wave == 1:
        if timer <= 0 or wave1_near_cleared:
            _spawn_evidence_reinforcement_wave(2)
            STATE.mission2_evidence_wave = 2
            # Arm wave 3 timer: 6 seconds (360 frames) into wave 2,
            # regardless of wave 2 clear state.
            STATE.mission2_evidence_wave_timer = 6 * 60
            STATE.mission2_evidence_wave_cleared = False

    # Wave 3 fires when:
    #   - timer expires (6s into wave 2), OR
    #   - wave 2 cleared early (player was fast)
    elif wave == 2:
        wave2_cleared = alive_count == 0
        if timer <= 0 or wave2_cleared:
            _spawn_evidence_reinforcement_wave(3)
            STATE.mission2_evidence_wave = 3
            STATE.mission2_evidence_wave_cleared = False


def _start_tanker_run():
    STATE.mission2_stage = STAGE_RUN
    STATE.mission_phase = "m2_tanker_run"
    STATE.mission2_timer = 0
    STATE.mission2_countdown = 420
    # ── Shelter-reveal camera pan (Task B) ───────────────────────────────
    # Briefly pan the camera to the shelter (~1.2 seconds / 72 frames) so
    # the player SEES where they need to run before the panic starts. The
    # existing mission2_camera_focus mechanic handles the pan + auto-return:
    #   - mission2_camera_focus = (x, y) pins the camera target
    #   - mission2_camera_focus_timer = N holds the focus for N frames
    #   - when the timer expires (decremented in _update_camera at line ~4774),
    #     the focus is cleared and the camera returns to the player.
    # The 72-frame hold (1.2s at 60 FPS) is short enough that the player
    # still has ~5.8 seconds of countdown left to actually run after the
    # pan completes. The camera eases (not snaps) per the existing focus
    # factor logic in _update_camera, so the pan reads as intentional
    # cinematic direction, not a glitch.
    STATE.mission2_camera_focus = SAFE_ZONE
    STATE.mission2_camera_focus_timer = 72
    STATE.mission2_tension_phase = 0   # NEW: drives the pre-blast wind-up
    _set_objective("RUN to the blue shelter marker before the tanker detonates")
    # Vasile's trap-reveal line ("remote-detonated cleanup charge - they're
    # going to blow it!") already played when the inspection card closed.
    # This line is the run command - focus on the countdown + direction,
    # not the trap (which the player already knows about).
    _radio('VASILE: "Seven seconds - GO! Blue marker - south - MOVE!"',
           color=(255, 150, 70), mark="run")
    audio.play("alarm", volume=0.45)


def _explode_tanker():
    if STATE.mission2_tanker_exploded:
        return
    STATE.mission2_tanker_exploded = True
    # ── Checkpoint reached (fix for "checkpoint doesn't fire on blast death") ──
    # Set the checkpoint flag the moment the tanker explodes, BEFORE the
    # damage block below. Previously this flag was only set in _close_card()
    # when the player closed the "blast_done" dialogue card - meaning a
    # player who DIED during the blast (lethal radius, or graze damage that
    # brought HP to 0) never closed the card, the flag stayed False, and
    # restart_current_mission() respawned them at the very start of Mission 2
    # instead of at the evidence-phase checkpoint.
    #
    # Setting it here means: whether the player survives (debris scrape) or
    # dies (lethal/graze), the checkpoint is active. On restart,
    # restart_current_mission() sees True and calls start_mission2_checkpoint(),
    # which itself calls _explode_tanker() to recreate the post-blast fire
    # zones - so the flag gets re-set idempotently on checkpoint respawn.
    #
    # The blast_done card-close handler in _close_card() still re-sets the
    # flag (harmless idempotent re-set, left as belt-and-suspenders).
    STATE.mission2_checkpoint_reached = True
    STATE.mission2_stage = STAGE_BLACKOUT
    STATE.mission_phase = "m2_blackout"
    STATE.mission2_timer = 0
    STATE.mission2_countdown = 0
    STATE.mission2_comms_cut = True
    STATE.mission2_camera_focus = TANKER_POS
    # Hold the camera on the blast for 8 seconds. The fireball alone burns
    # for 7.5s - the player needs to see the whole thing.
    STATE.mission2_camera_focus_timer = 480
    _set_objective("Comms lost")

    tanker = STATE.mission2_tanker_rect
    cx, cy = tanker.centerx, tanker.centery

    # --- Audio: full BLEVE symphony. Initial crack -> deep boom -> tinnitus
    # -> structure collapse -> FIVE secondary fuel-tank pops (was 2) ->
    # fireball whoosh -> sustained roar -> distant rumble tail. The
    # sustained roar is what was missing - a real BLEVE roars for 10+
    # seconds, not just a one-shot boom. ---
    audio.play("explosion", volume=1.0)                          # 0: detonator + vapor ignition
    audio.schedule(2, "rig_low_boom", volume=1.0)                # 2: primary shockwave
    audio.schedule(8, "tinnitus", volume=0.85)                   # 8: ringing ears
    audio.schedule(12, "explosion", volume=0.7)                  # 12: tanker structure rupturing
    audio.schedule(15, "rig_secondary_explosion", volume=0.9)    # 15: BLEVE secondary #1
    audio.schedule(28, "rig_metal_collapse", volume=0.65)        # 28: steel frame giving way
    audio.schedule(30, "rig_secondary_explosion", volume=0.75)   # 30: BLEVE secondary #2
    audio.schedule(50, "rig_secondary_explosion", volume=0.7)    # 50: BLEVE secondary #3
    audio.schedule(75, "rig_secondary_explosion", volume=0.65)   # 75: BLEVE secondary #4
    audio.schedule(105, "rig_secondary_explosion", volume=0.6)   # 105: BLEVE secondary #5
    audio.schedule(60, "rig_fire_burst", volume=0.7)             # 60: fireball ingesting air
    # Sustained fire roar - loop the fire burst for 8 seconds so the
    # blast keeps roaring instead of going silent after the initial boom.
    audio.play("rig_fire_burst", volume=0.5, loops=int(8.0 * 60 / 1.0))  # ~8s of sustained roar
    audio.schedule(180, "rig_low_boom", volume=0.5)              # 180: late shockwave tail
    audio.schedule(280, "rig_metal_collapse", volume=0.4)        # 280: late structure groans

    # --- Screen shake: 160 peak (was 130), decay over 240 frames (was 180).
    # A blast this big should keep the camera shuddering for 4 seconds. ---
    # effects.shake() max-clamps so this still fires even if a smaller shake
    # is in flight (it usually isn't at this point, but the discipline pays
    # off if a future trigger source fires mid-blast).
    effects.shake(160)
    STATE.mission2_tanker_shake_decay = 240

    # --- Hard camera kick - bigger than before. The world gets PUNCHED. ---
    STATE.cam_kick_x = _rng_legacy.uniform(-1.0, 1.0) * 45.0
    STATE.cam_kick_y = _rng_legacy.uniform(-1.0, 1.0) * 45.0

    # --- White-out flash: 130 frames (was 80). The first 40 frames are
    # pure white - the player's screen should be totally blown out for
    # ~2/3 of a second. ---
    STATE.gc_flash_timer = 130
    STATE.mission2_tanker_subflash_queue = [15, 30, 50, 75, 105]  # 5 BLEVE secondaries

    # --- Chromatic aberration / distortion flicker - longer and stronger. ---
    STATE.mission2_chromatic_timer = 240

    # --- Screen ripple distortion flag - driven in the update loop, drawn
    # as a horizontal wobble in _draw_blackout_overlay. ---
    STATE.mission2_tanker_ripple_timer = 40

    # --- Explosion cinematic timers ---
    STATE.mission2_tanker_blast_timer = 0
    STATE.mission2_tanker_shockwave_radius = 0
    STATE.mission2_tanker_fireball_radius = 0

    # --- Persistent scorch decal - MUCH bigger (520px radius, was 350) so
    # the blast site reads as a real crater that matches the 620px damage
    # radius, not a campfire stain. The drawing routine in
    # _draw_tanker_blast_fx adds oily layers + radial cracks on top of
    # this radius. ---
    STATE.mission2_tanker_scorch = (cx, cy, 520)

    # --- Tanker is GONE. Replace its rect with a blackened wreckage rect
    # so the blast site shows a destroyed hull instead of a pristine tanker. ---
    STATE.mission2_tanker_destroyed = True

    # --- Remove the tanker's collision wall so the player can walk over
    # the crater after the blast. The tanker sprite is gone (gated on
    # mission2_tanker_destroyed in _draw_tanker) and the wreckage + scorch
    # are purely visual, so the wall is no longer needed. Without this the
    # player bumps into an invisible wall where the tanker used to be. ---
    if STATE.mission2_tanker_rect in STATE.walls:
        STATE.walls.remove(STATE.mission2_tanker_rect)

    # --- Pre-computed wreckage rib positions. The previous drawing code
    # called random.randint(-3, 3) for every rib every frame, which made
    # the ribs visibly jitter. Storing them once keeps the wreckage stable
    # and lets us add more ribs (8, was 5) for a more shredded look. ---
    STATE.mission2_tanker_wreckage_ribs = []
    for i in range(8):
        rx_offset = _rng_legacy.randint(-3, 3)
        ry_top = _rng_legacy.randint(2, 8)
        STATE.mission2_tanker_wreckage_ribs.append((rx_offset, ry_top))

    # --- Pre-computed scorch crack lengths. Same jitter issue as the
    # wreckage ribs - the previous drawing code called random.randint(20,
    # 60) for every crack every frame, making the cracks visibly grow and
    # shrink. 12 cracks (was 8) for a more shattered-asphalt look. ---
    STATE.mission2_tanker_scorch_cracks = []
    for i in range(12):
        ang = i * (math.tau / 12) + 0.3
        end_r = _rng_legacy.randint(40, 110)
        STATE.mission2_tanker_scorch_cracks.append((ang, end_r))

    # --- Permanent scattered debris field. The 90 animated debris chunks
    # in mission2_tanker_debris_chunks only live 100-200 frames and then
    # vanish, so after ~3 seconds the blast site has no scattered metal
    # at all. This static field stamps ~70 small charred chunks in a
    # permanent ring around the crater so the aftermath reads as "something
    # exploded here" for the rest of the mission. ---
    STATE.mission2_tanker_debris_field = []
    for _ in range(70):
        angle = _rng_legacy.uniform(0, math.tau)
        # Bias toward the outer ring (110-340px) - the inner zone is
        # already covered by the scorch + wreckage, the outer ring is
        # where the visible thrown debris should rest.
        dist = _rng_legacy.uniform(110, 340)
        dx_off = math.cos(angle) * dist
        dy_off = math.sin(angle) * dist * 0.85  # slight horizontal stretch
        STATE.mission2_tanker_debris_field.append({
            "x": cx + dx_off,
            "y": cy + dy_off,
            "size": _rng_legacy.randint(3, 9),
            "color": _rng_legacy.choice([
                (40, 35, 30), (60, 55, 50), (95, 88, 76),
                (140, 40, 32), (75, 30, 25), (28, 24, 22),
            ]),
            "shape": _rng_legacy.choice(["rect", "tri", "rect"]),
            "rot": _rng_legacy.uniform(0, math.tau),
        })

    # --- OUTER debris ring - chunks thrown MUCH further (340-720px) by the
    # blast. Smaller pieces (they traveled further), sparser, but they sell
    # the scale: a real tanker blast throws shrapnel hundreds of feet. ---
    STATE.mission2_tanker_outer_debris = []
    for _ in range(60):
        angle = _rng_legacy.uniform(0, math.tau)
        dist = _rng_legacy.uniform(340, 720)
        dx_off = math.cos(angle) * dist
        dy_off = math.sin(angle) * dist * 0.85
        STATE.mission2_tanker_outer_debris.append({
            "x": cx + dx_off,
            "y": cy + dy_off,
            "size": _rng_legacy.randint(2, 6),   # smaller - they traveled further
            "color": _rng_legacy.choice([
                (40, 35, 30), (60, 55, 50), (95, 88, 76),
                (140, 40, 32), (75, 30, 25), (28, 24, 22),
            ]),
        })

    # --- Radial blast streaks - long tapering scorch marks radiating
    # OUTWARD from the blast, like the shockwave scorched the ground as it
    # expanded. These are the single biggest "something exploded HERE and
    # reached WAY out" visual. 16 streaks, pre-computed, drawn forever. ---
    STATE.mission2_tanker_blast_streaks = []
    for i in range(16):
        angle = (i / 16.0) * math.tau + _rng_legacy.uniform(-0.08, 0.08)
        start_r = _rng_legacy.uniform(180, 260)   # just outside the crater rim
        end_r = _rng_legacy.uniform(520, 780)     # reaches far out
        width = _rng_legacy.uniform(14, 26)       # wider at the base, tapering
        STATE.mission2_tanker_blast_streaks.append((angle, start_r, end_r, width))

    # --- Cracked-asphalt ring - thin lighter-colored crack lines radiating
    # outward BEYOND the scorch (out to ~750px), showing the blast wave
    # physically cracked the road surface far from the crater. Pre-computed,
    # drawn forever. 24 cracks, thinner and longer than the scorch cracks. ---
    STATE.mission2_tanker_asphalt_cracks = []
    for i in range(24):
        angle = (i / 24.0) * math.tau + _rng_legacy.uniform(-0.05, 0.05)
        start_r = _rng_legacy.uniform(280, 360)
        end_r = _rng_legacy.uniform(560, 780)
        # Each crack is 2-3 jagged segments, not a straight line.
        seg_count = _rng_legacy.randint(2, 3)
        segs = []
        for s in range(seg_count + 1):
            frac = s / seg_count
            r = start_r + (end_r - start_r) * frac
            jitter = _rng_legacy.uniform(-18, 18)
            segs.append((angle, r, jitter))
        STATE.mission2_tanker_asphalt_cracks.append(segs)

    # --- Persistent outer spot fires - ~12 small fires 250-600px from the
    # crater, simulating embers that were thrown out and ignited secondary
    # fires well away from the blast site. These burn FOREVER (purely
    # visual, no damage) so the wider scene keeps smoldering. Emitted as
    # particles in the aftermath update block + drawn as glowing patches. ---
    STATE.mission2_tanker_spot_fires = []
    for _ in range(12):
        angle = _rng_legacy.uniform(0, math.tau)
        dist = _rng_legacy.uniform(250, 600)
        sf_x = cx + math.cos(angle) * dist
        sf_y = cy + math.sin(angle) * dist * 0.85
        STATE.mission2_tanker_spot_fires.append({
            "x": sf_x,
            "y": sf_y,
            "size": _rng_legacy.randint(14, 26),
            "phase": _rng_legacy.uniform(0, math.tau),  # flicker offset
        })

    # --- Char nearby vehicles. The civilian car at col 49/row 45 is
    # ~587px from the tanker, the one at col 41/row 25 is ~798px, and the
    # IPA truck at col 46/row 31 is ~397px. All three are within the
    # 820px blast-char radius (was 520px - that threshold was calibrated to
    # an incorrect distance estimate and missed the two closest civilian
    # cars). A real blast of this size would torch them all. Civilian cars
    # get flipped to "burned" (which the drawing code already supports) +
    # the blast_charred overlay. The IPA truck keeps its kind (it has a
    # dedicated drawing function) but gets blast_charred=True so _draw_vehicle
    # routes to the wrecked variant. By the time the blast fires the player
    # has already inspected the truck manifest, so wrecking it is purely
    # visual. The 820px radius matches the outer debris field (720px) -
    # a car hit by flying debris at that range would absolutely catch fire. ---
    for v in getattr(STATE, "mission2_vehicles", []):
        vcx = v["rect"].centerx
        vcy = v["rect"].centery
        d = math.hypot(vcx - cx, vcy - cy)
        if d < 820:   # within blast-char range (was 520 - missed 2 nearby cars)
            # Don't change the IPA truck's kind - it has its own dedicated
            # drawing function. Just tag it so the drawing code renders a
            # wrecked variant. Civilian cars get flipped to "burned".
            if v.get("kind") != "ipa_truck":
                v["kind"] = "burned"
            v["blast_charred"] = True
            # Knock the vehicle slightly off its original position + rotation
            # to read as "blast pushed it". Store the offset; the drawing
            # code adds it.
            push_angle = math.atan2(vcy - cy, vcx - cx)
            push_dist = _rng_legacy.randint(14, 32) * (1.0 - d / 820.0)
            v["blast_offset"] = (
                math.cos(push_angle) * push_dist,
                math.sin(push_angle) * push_dist,
            )
            v["blast_rot"] = _rng_legacy.uniform(-0.18, 0.18)

    # --- Char / tip nearby story props. Barrels, cones, signs within ~380px
    # of the blast get blackened and knocked over. Puddles get a scorched
    # ring around them (evaporated edge). This makes the blast feel like it
    # wrecked the whole checkpoint, not just the tanker spot. ---
    for prop in getattr(STATE, "mission2_story_props", []):
        px, py = prop.get("pos", (0, 0))
        d = math.hypot(px - cx, py - cy)
        if d < 380 and prop.get("kind") in ("barrel", "cone", "sign"):
            prop["charred"] = True
            # Tip direction - away from the blast.
            tip_angle = math.atan2(py - cy, px - cx)
            prop["tip_dx"] = math.cos(tip_angle) * _rng_legacy.uniform(8, 16)
            prop["tip_dy"] = math.sin(tip_angle) * _rng_legacy.uniform(8, 16)
            prop["tip_rot"] = _rng_legacy.uniform(-0.5, 0.5)
        elif d < 260 and prop.get("kind") == "puddle":
            # Puddles close to the blast get a scorched/evaporated ring.
            prop["scorched"] = True

    # --- Heavy debris chunks (own physics + smoke trails). 90 chunks (was
    # 34) - a fuel tanker has a LOT of metal. ---
    STATE.mission2_tanker_debris_chunks = []

    # --- Wave 1: Initial hot core (700 particles, was 400). A blast this
    # size throws a wall of fire, not a puff. ---
    for _ in range(700):
        col = _rng_legacy.choice([
            (255, 255, 230), (255, 250, 200), (255, 220, 140),
            (255, 180, 70), (255, 160, 50), (255, 95, 20), (255, 70, 25),
        ])
        p = Particle(cx + _rng_legacy.randint(-50, 50), cy + _rng_legacy.randint(-30, 30), col)
        angle = _rng_legacy.uniform(0, math.tau)
        speed = _rng_legacy.uniform(4.0, 11.0)   # wider speed range for a bigger blast
        p.dx = math.cos(angle) * speed
        p.dy = math.sin(angle) * speed
        p.life = _rng_legacy.randint(40, 110)
        STATE.particles.append(p)

    # --- Wave 2: Secondary lightweight debris (350 particles, scheduled
    # for frame 12). ---
    def _spawn_debris():
        for _ in range(350):
            col = _rng_legacy.choice([
                (60, 55, 50), (40, 35, 30), (95, 88, 76),
                (140, 40, 32), (75, 30, 25),
            ])
            p = Particle(cx + _rng_legacy.randint(-70, 70), cy + _rng_legacy.randint(-40, 40), col)
            angle = _rng_legacy.uniform(0, math.tau)
            speed = _rng_legacy.uniform(2.0, 5.5)
            p.dx = math.cos(angle) * speed
            p.dy = math.sin(angle) * speed
            p.life = _rng_legacy.randint(60, 160)
            STATE.particles.append(p)
    audio._pending.append((12, _spawn_debris, None)) if hasattr(audio, "_pending") else None
    STATE.mission2_pending_debris_wave = 12

    # --- Wave 3: Initial smoke plume - massive (300 particles, was 140). ---
    for _ in range(300):
        col = _rng_legacy.choice([(18, 16, 14), (22, 20, 18), (35, 30, 28), (55, 48, 42)])
        p = Particle(cx + _rng_legacy.randint(-80, 80), cy + _rng_legacy.randint(-60, 20), col)
        p.dx = _rng_legacy.uniform(-1.8, 1.8)
        p.dy = _rng_legacy.uniform(-4.0, -1.5)  # smoke rises fast and high
        p.life = _rng_legacy.randint(150, 280)
        STATE.particles.append(p)

    # --- Fire patches: 18 (was 8), spread across a MUCH wider blast zone.
    # These are the ground fires that keep burning after the fireball rises. ---
    for ox, oy in [(-160, -70), (-110, -40), (-60, -10), (-20, 5), (10, 15),
                   (50, 30), (90, 50), (130, 70), (-140, 20), (-90, 60),
                   (-30, 90), (40, 100), (100, 90), (-180, 50), (170, 30),
                   (-50, -50), (70, -30), (-100, 100)]:
        _spawn_molotov_fire(cx + ox, cy + oy, _solid_walls())

    # --- PERSISTENT fire zones (Option F - environmental pressure) ---
    # These outlive the molotov fires (which expire after ~7s) and block
    # the direct path between the tanker blast site and the control building
    # throughout STAGE_EVIDENCE. The player has to navigate around them
    # while fighting the 3-wave cleanup team - no more camping in a straight
    # line from the blast to the upload terminal.
    #
    # FireZone life is set to 5400 frames (90 seconds), which is more than
    # enough to cover the entire evidence phase. Positions are placed in a
    # loose diagonal between the tanker (south) and the control building
    # (north), blocking the most direct route.
    from entities.weapons import FireZone as _FireZone
    persistent_fire_offsets = [
        (0, -120),    # directly north of blast, blocking the main road
        (40, -180),   # NE of blast, blocking the right detour
        (-40, -160),  # NW of blast, blocking the left detour
        (80, -240),   # further NE, near the control building approach
        (-60, -220),  # further NW, near the gantry support
    ]
    for ox, oy in persistent_fire_offsets:
        fz = _FireZone(cx + ox, cy + oy)
        fz.life = 5400       # 90 seconds - persists through the evidence phase
        fz.max_life = 5400
        fz.radius = 56       # slightly larger than default (48) for better blocking
        STATE.fire_zones.append(fz)

    # --- Player damage (lethal unless at the outpost shelter) ---
    # The safe zone (concrete shelter) is ~1118px from the tanker. A real
    # BLEVE this size would kill anything in the open within ~1000px. So:
    #   - If the player is inside the safe zone radius (~110px around
    #     SAFE_ZONE), they take a survivable scrape (20-40 HP) from debris.
    #   - If the player is NOT in the safe zone and within 1100px of the
    #     blast, they are KILLED. The player had a 7-second countdown to
    #     reach the shelter - failing to make it should be fatal, not a
    #     slap on the wrist.
    #   - Beyond 1100px (off-screen, unreachable in the run window) the
    #     player takes scaled damage down to 0 at 1400px.
    # Previously the blast radius was 620px with max 140 damage, which meant
    # a player standing in the open 700px from the tanker would take ZERO
    # damage - making the "run to the shelter" objective feel optional.
    if STATE.player:
        d = _dist(_player_pos(), (cx, cy))
        d_shelter = _dist(_player_pos(), SAFE_ZONE)
        shelter_radius = 110   # inside this = survived the blast
        lethal_radius = 1100   # outside shelter + inside this = dead
        graze_radius = 1400    # outside lethal but inside this = scaled damage

        if d_shelter < shelter_radius:
            # Made it to the shelter - survivable debris scrape.
            # AEGIS Pass E: set-piece tanker blast - force=True bypasses
            # i-frames so the scrape always lands (it's the "you barely
            # made it" narrative beat). Subsequent i-frames still apply.
            dmg = _rng_legacy.randint(20, 40)
            STATE.player.take_damage(dmg, force=True)
            STATE.floating_texts.append([
                STATE.player.rect.centerx, STATE.player.rect.centery - 48,
                f"-{dmg} HP DEBRIS", (255, 200, 100), 110
            ])
            STATE.mission2_input_freeze = 30   # half-second stun
        elif d < lethal_radius:
            # In the open within lethal range - instakill. The player was
            # told to RUN to the shelter; failing to make it is fatal.
            STATE.player.hp = 0
            STATE.floating_texts.append([
                STATE.player.rect.centerx, STATE.player.rect.centery - 48,
                "BLAST - LETHAL", (255, 50, 30), 130
            ])
            STATE.mission2_input_freeze = 90
        elif d < graze_radius:
            # Far edge of the blast - heavy but survivable damage.
            # AEGIS Pass E: set-piece tanker blast - force=True bypasses
            # i-frames so the blast always lands. The blast is a one-shot
            # scripted event, not tactical combat, so i-frames shouldn't
            # apply to the damage itself (but the post-blast i-frame window
            # still gives the player a breather).
            # AEGIS Pass F: 80ms hit-stop on the blast hit. Same set-piece
            # weighting as the sniper shot - the blast is a cinematic
            # moment and the freeze sells the shockwave.
            t = (d - lethal_radius) / (graze_radius - lethal_radius)
            dmg = int(120 * (1.0 - t))
            if dmg > 0:
                STATE.player.take_damage(dmg, force=True)
                effects.hit_stop(0.08)
                STATE.floating_texts.append([
                    STATE.player.rect.centerx, STATE.player.rect.centery - 48,
                    f"-{dmg} HP BLAST", (255, 75, 45), 110
                ])
            if d > 1:
                kx = (STATE.player.rect.centerx - cx) / d * 120
                ky = (STATE.player.rect.centery - cy) / d * 120
                STATE.player.rect.x += int(kx)
                STATE.player.rect.y += int(ky)
            STATE.mission2_input_freeze = 60
        # Else: player was far enough away (shouldn't happen in normal play
        # since the run window is only 7 seconds, but handle it gracefully).

    STATE.mission2_tinnitus_timer = max(getattr(STATE, "mission2_tinnitus_timer", 0), 320)
    STATE.mission2_radio_muffle_timer = max(getattr(STATE, "mission2_radio_muffle_timer", 0), 280)


def _complete_mission2():
    if getattr(STATE, "request_mission2_ending", False):
        return
    STATE.mission2_stage = STAGE_DONE
    STATE.mission2_evidence_uploaded = True
    STATE.mission_end_time = _now_ms()
    STATE.request_mission2_ending = True
    audio.play("terminal_glitch", volume=0.55)
