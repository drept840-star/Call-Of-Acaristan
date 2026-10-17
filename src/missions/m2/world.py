
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
import game.levels as _levels  # RPE6 P7: level data access

from core.config import (C_TERMINAL, C_VASILE, HEIGHT, TILE_SIZE, WIDTH, audio)
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

from missions.m2.meta import FIELD_RADIO_POS, IPA_TRUCK_POS, MAP_H, MAP_W, MISSION2_BUILDINGS, MISSION2_CLUE_DEFS, MISSION2_TRIGGER_DEFS, PLAYER_START, SAFE_ZONE, STAGE_EVIDENCE, STAGE_EXFIL, STAGE_SNIPER, STAGE_TANKER, TANKER_POS, ZONE_DEFS, _tc
import game.world as _gw  # RPE6 Phase 5 (D4): mission data lives in components
from missions.m2.components import M2Role as _M2Role


def _m2g(e):
    """Declared M2 data of an enemy (replaces the ad hoc ``e.m2_*`` attributes)."""
    return _gw.ensure(e, _M2Role)


def _set_tile(g, col, row, tile):
    if 0 <= col < MAP_W and 0 <= row < MAP_H:
        g[row][col] = tile


def _paint_tiles(g, rect, tile):
    for row in range(rect.y, rect.y + rect.h):
        for col in range(rect.x, rect.x + rect.w):
            _set_tile(g, col, row, tile)


def _outline_building(g, col, row, w, h, interior="O", door_tiles=()):
    for yy in range(row, row + h):
        for xx in range(col, col + w):
            border = xx in (col, col + w - 1) or yy in (row, row + h - 1)
            _set_tile(g, xx, yy, "C" if border else interior)
    for dx, dy in door_tiles:
        _set_tile(g, col + dx, row + dy, interior)


def _generate_map():
    g = [["g" for _ in range(MAP_W)] for _ in range(MAP_H)]

    # Paint authored regions first.  Collidable structure is added after.
    for zone in ZONE_DEFS.values():
        _paint_tiles(g, zone["tile_rect"], zone["floor"])

    # Continuous highway spine and shoulders.  These broad open sightlines are
    # intentional: the sniper ambush later weaponizes this road geometry.
    _paint_tiles(g, pygame.Rect(17, 23, 37, 55), ".")
    _paint_tiles(g, pygame.Rect(12, 54, 42, 13), ".")
    _paint_tiles(g, pygame.Rect(7, 70, 25, 8), ".")

    # Feather the shoulder/asphalt seam.  Painting the spine as plain
    # rectangles leaves a dead-straight edge running dozens of tiles, which
    # reads as a texture seam rather than terrain - most obvious where the
    # open verge meets the road with nothing else in frame.  Both tiles are
    # walkable, so this is purely cosmetic and cannot alter collision or the
    # sniper sightline.
    for row in range(MAP_H):
        for col in range(MAP_W):
            ch = g[row][col]
            if ch not in (".", "g"):
                continue
            n = ((col * 73856093) ^ (row * 19349663)) & 0xFFFFFFFF
            if (n >> 7) % 5:
                continue
            up = g[row - 1][col] if row > 0 else ch
            left = g[row][col - 1] if col > 0 else ch
            if ch == "." and (up == "g" or left == "g"):
                g[row][col] = "g"
            elif ch == "g" and (up == "." or left == "."):
                g[row][col] = "."
    _paint_tiles(g, pygame.Rect(4, 47, 23, 15), "d")
    _paint_tiles(g, pygame.Rect(45, 38, 23, 15), "s")
    _paint_tiles(g, pygame.Rect(39, 12, 28, 16), "O")

    # World border.
    for x in range(MAP_W):
        g[0][x] = g[MAP_H - 1][x] = "C"
    for y in range(MAP_H):
        g[y][0] = g[y][MAP_W - 1] = "C"

    # Control building and offices, then the smaller security hut.  Both
    # footprints come from MISSION2_BUILDINGS so the renderer can find the
    # interiors without re-declaring the geometry.
    for idx, (bcol, brow, bw, bh) in enumerate(MISSION2_BUILDINGS):
        doors = ((6, 16), (7, 16), (0, 9)) if idx == 0 else ((4, 7),)
        _outline_building(g, bcol, brow, bw, bh, interior="O", door_tiles=doors)

    # Toll booths and gantry supports.
    for bx, by in [(23, 32), (30, 32), (44, 32), (51, 32), (24, 37), (45, 37)]:
        for yy in range(by, by + 2):
            for xx in range(bx, bx + 2):
                _set_tile(g, xx, yy, "C")
    for sx, sy in [(56, 25), (59, 25), (56, 27), (59, 27)]:
        _set_tile(g, sx, sy, "C")

    # Barriers / cover.  These break up travel without deleting the long sniper
    # sightline through the center lane.
    barriers = [
        (12, 72), (13, 72), (21, 69), (22, 69),
        (18, 61), (19, 61), (27, 60), (28, 60), (37, 58),
        (10, 51), (11, 51), (20, 47), (21, 47),
        (29, 40), (30, 40), (34, 39), (35, 39), (40, 40),
        (47, 45), (48, 45), (62, 47), (63, 47),
        (44, 27), (45, 27), (49, 28), (50, 28),
        (57, 21), (58, 21), (62, 18), (63, 18),
    ]
    for col, row in barriers:
        _set_tile(g, col, row, "B")

    # Final-build density pass: guardrails, broken dividers, service-road clutter,
    # and ditch obstructions.  These are intentionally staggered so the map has
    # shape without blocking the central sniper sightline.
    for row in range(25, 76, 4):
        if row not in (32, 33, 34, 35, 36, 37, 38, 39):
            _set_tile(g, 16, row, "B")
            _set_tile(g, 54, row + (row // 4) % 2, "B")
    for row in range(55, 66, 3):
        for col in (14, 41, 46, 51):
            _set_tile(g, col, row, "B")
    for col in range(6, 26, 4):
        _set_tile(g, col, 46, "B")
        _set_tile(g, col + 1, 59, "B")
    for col in range(46, 66, 4):
        _set_tile(g, col, 40, "B")
        _set_tile(g, col + 1, 51, "B")
    for col in range(21, 53, 7):
        _set_tile(g, col, 30, "B")
        _set_tile(g, col + 2, 42, "B")
    # Interior partitions in the control building so it no longer reads as one
    # empty rectangle.  Door gaps keep all evidence reachable.
    for col in range(53, 67):
        if col not in (57, 62):
            _set_tile(g, col, 17, "C")
    for row in range(11, 25):
        if row not in (15, 21):
            _set_tile(g, 60, row, "C")

    # Tanker footprint.  The actual collision uses mission2_tanker_rect.
    for row in range(36, 39):
        for col in range(43, 48):
            _set_tile(g, col, row, "T")

    _set_tile(g, 8, 74, "P")
    _set_tile(g, 64, 12, "X")
    return ["".join(row) for row in g]


MISSION2_MAP = _levels.grid("m2.city", _generate_map())  # RPE6 P7: data by default

# Module-level draw/update scratch.
_last_keys = None
_objective = "Inspect staged evidence markers with [E]"
_radio_marks = set()

# ─────────────────────────────────────────────
# Utility helpers
# ─────────────────────────────────────────────
def _dist(a, b):
    return math.hypot(a[0] - b[0], a[1] - b[1])


def _player_pos():
    if not STATE.player:
        return (0, 0)
    return STATE.player.rect.centerx, STATE.player.rect.centery


def _near(pos, radius=80):
    return STATE.player and _dist(_player_pos(), pos) <= radius


def _camera_offset_for_target(target):
    tx, ty = target
    max_x = max(0, MAP_W * TILE_SIZE - WIDTH)
    max_y = max(0, MAP_H * TILE_SIZE - HEIGHT)
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
    # NOTE: screen_shake is deliberately NOT cleared here. Shake is a
    # time-based effect, not a positional one - a teleport shouldn't eat an
    # in-flight shake (e.g. snapping right after a blast). Mission starts
    # and checkpoint respawns zero it explicitly instead.


def _solid_walls():
    return (
        list(STATE.walls)
        + list(getattr(STATE, "mission2_vehicle_walls", []))
        + list(getattr(STATE, "mission2_prop_walls", []))
        + list(getattr(STATE, "mission2_shelter_walls", []))
        + list(getattr(STATE, "mission2_garden_walls", []))
    )


def _build_shelter_walls():
    """Build collision rects for the shelter's crescent blast wall.

    The blast wall is drawn (in _draw_shelter) as a filled polygon following
    an arc from N (0°) to E (90°) on the NE side of SAFE_ZONE, with outer
    radius 66 and inner radius 50 (16px thick). This function approximates
    that crescent with a series of small axis-aligned rectangles - one per
    arc segment - so the player and enemies collide with the wall and
    cannot walk through it (or off the pad on the NE side, which would
    defeat the shelter's purpose during the tanker blast).

    Each segment rect spans the angular slice [a, a+step] and the radial
    range [inner_r, outer_r]. The rect is the axis-aligned bounding box of
    that slice's 4 corners - slightly conservative (the AABB is a bit larger
    than the actual arc slice), but that's the right direction for a wall:
    better to block a touch too much than let the player clip through.

    The rects are stored on STATE.mission2_shelter_walls and included in
    _solid_walls() above. Call this once from start_mission2() after
    STATE.reset() has cleared the list; the dev-args shortcuts
    (--m2-truck, --m2-flank, etc.) inherit it via start_mission2() so they
    don't need their own call.
    """
    sx, sy = SAFE_ZONE
    wall_outer_r = 66   # MUST match _draw_shelter's wall_outer_r
    wall_inner_r = 50   # MUST match _draw_shelter's wall_inner_r
    # Number of arc segments. More = smoother collision, more rects.
    # 12 segments = 7.5° per segment - feels solid without bloating the
    # wall list (the player rect is 32x32, so 7.5° slices are well below
    # the player's footprint and there are no gap-through exploits).
    num_segments = 12
    walls = []
    for i in range(num_segments):
        a0 = math.radians(90.0 * i / num_segments)        # start angle
        a1 = math.radians(90.0 * (i + 1) / num_segments)  # end angle
        # 4 corners of this arc slice (outer0, outer1, inner1, inner0)
        # Screen coords: x = cos(angle) * r, y = -sin(angle) * r
        # (negative sin because screen y goes down but "north" is up)
        corners = [
            (sx + math.cos(a0) * wall_outer_r, sy - math.sin(a0) * wall_outer_r),
            (sx + math.cos(a1) * wall_outer_r, sy - math.sin(a1) * wall_outer_r),
            (sx + math.cos(a1) * wall_inner_r, sy - math.sin(a1) * wall_inner_r),
            (sx + math.cos(a0) * wall_inner_r, sy - math.sin(a0) * wall_inner_r),
        ]
        xs = [c[0] for c in corners]
        ys = [c[1] for c in corners]
        rx = int(min(xs))
        ry = int(min(ys))
        rw = int(max(xs) - min(xs)) + 1  # +1 to avoid 1px gaps between segments
        rh = int(max(ys) - min(ys)) + 1
        walls.append(pygame.Rect(rx, ry, rw, rh))
    STATE.mission2_shelter_walls = walls


def _set_objective(text):
    global _objective
    _objective = text


def _radio(text, color=C_VASILE, duration=300, mark=None, allow_when_cut=False,
           priority=None):
    """Small radio helper. Used sparingly; cards do most story work."""
    if mark and mark in _radio_marks:
        return
    if mark:
        _radio_marks.add(mark)

    # Sniper subtitles need reading time (~4 seconds minimum).
    if getattr(STATE, "mission2_stage", "") == STAGE_SNIPER:
        duration = max(duration, 240)

    if getattr(STATE, "mission2_comms_cut", False) and not allow_when_cut:
        text = "RADIO: <static>"
        color = (125, 125, 135)
        duration = min(duration, 140)
    # Muffled radio after the near-miss: drop letters, insert ellipses, fade
    # color so it visually reads as "underwater" without needing a real
    # low-pass filter.
    if getattr(STATE, "mission2_radio_muffle_timer", 0) > 0 and not text.startswith("RADIO:"):
        text = _muffle_radio_text(text)
        color = tuple(max(70, int(c * 0.62)) for c in color)
        if getattr(STATE, "mission2_stage", "") == STAGE_SNIPER:
            duration = max(duration, 240)
        else:
            duration = max(160, int(duration * 0.75))
    # Once-guarded (marked) lines are story beats: priority 0.5 so a cutscene
    # or dialogue box holds them instead of dropping them (radio_allowed).
    if priority is None:
        priority = 0.5 if mark else 0
    trigger_radio_chatter(text, color=color, duration=duration, priority=priority)


def _muffle_radio_text(text):
    """Drop syllables and insert ellipses so a radio line reads as ear-ringing.

    Ramps the muffle severity based on mission2_radio_muffle_timer so the
    effect fades out gradually as the player's hearing returns.
    """
    timer = getattr(STATE, "mission2_radio_muffle_timer", 0)
    if timer <= 0:
        return text
    if ":" in text:
        speaker, _, spoken = text.partition(":")
        spoken = spoken.strip().strip('"')
        words = spoken.split()
        if len(words) <= 2:
            return text
        intensity = min(0.6, timer / 180.0)
        keep = []
        for i, w in enumerate(words):
            if i == 0 or _rng_legacy.random() > intensity:
                keep.append(w)
        return f'{speaker}: "{" . . . ".join(keep)}"'
    return text


# _burst is now an alias for the shared effects.burst. Both missions use the
# same particle-burst parameters (life 18-50, jitter ±8, speed_mul scaling,
# respects SETTINGS.particle_density) so blood / sparks / debris look the
# same across the campaign.
_burst = effects.burst


def _open_card(title, lines, color=C_TERMINAL, after=None, kind="document"):
    """Open a readable inspection/intel card. It stays until the player presses E."""
    if isinstance(lines, str):
        lines = [lines]
    STATE.mission2_card = {
        "title": title,
        "lines": list(lines),
        "color": color,
        "age": 0,
        "after": after,
        "kind": kind,
    }
    audio.play("terminal_glitch", volume=0.24)


def _close_card():
    from missions.m2.sniper import _spawn_control_cleanup  # lazy: breaks world<->sniper cycle
    card = getattr(STATE, "mission2_card", None)
    if not card:
        return
    after = card.get("after")
    STATE.mission2_card = None
    audio.play("menu_click", volume=0.24)
    if after == "truck_done":
        STATE.mission2_stage = STAGE_TANKER
        STATE.mission_phase = "m2_tanker"
        _set_objective("Approach the fuel tanker - inspect with [E]")
        _radio('VASILE: "Balaceanu logistics. Not MAG. Move to the tanker - slow. Confirm what we\'re dealing with."',
               color=(255, 170, 80), mark="truck_done")
    elif after == "tanker_inspected":
        _radio('VASILE: "Biribel, get back! That\'s a remote-detonated cleanup charge - same frequency as the sniper. They\'re going to blow it!"',
               color=(255, 110, 70), mark="tanker_trap_revealed")
    elif after == "blast_done":
        STATE.mission2_stage = STAGE_EVIDENCE
        STATE.mission_phase = "m2_evidence"
        # ── Checkpoint reached (belt-and-suspenders re-set) ──
        # The checkpoint flag is now set inside _explode_tanker() itself, so
        # it's active the moment the tanker blows - regardless of whether
        # the player survives the blast. This re-set here is idempotent and
        # kept as a safety net in case some future code path reaches
        # _explode_tanker() without setting the flag (e.g. a dev-args shortcut
        # that skips the explosion and jumps straight to the card). The
        # canonical set is in _explode_tanker(); see the comment there for
        # the full rationale.
        # The evidence phase is a long, difficult fight (16 enemies across
        # 3 waves + persistent fire zones) - forcing a full mission restart
        # on death would be punishing in a way that feels unfair, not
        # challenging.
        STATE.mission2_checkpoint_reached = True
        # Release the cinematic blast-camera lock so the camera returns to
        # the player. Without this, mission2_camera_focus stays pinned to
        # TANKER_POS forever (set in _explode_tanker, never auto-cleared),
        # so the camera stays glued to the blast site for the entire rest
        # of the mission. Mirrors the flank-cutscene fix at the bottom of
        # _update_flank_cutscene.
        STATE.mission2_camera_focus = None
        STATE.mission2_camera_focus_timer = 0
        _set_objective("Enter the control building and inspect green evidence terminals")
        _spawn_control_cleanup()
    elif after == "evidence_ready":
        # ── Completion cinematic (Option E) ──
        # When the 3rd evidence item is read, trigger a 5-second cinematic
        # before the upload objective appears. The cinematic has 4 shots:
        #   1. White flash (camera flash) - 0.3s
        #   2. Evidence wall zoom - 1.5s
        #   3. Vasile radio line - 2.0s
        #   4. Upload terminal punch-in - 1.2s
        # The cinematic is driven in _update_evidence_cinematic() and drawn
        # in _draw_evidence_cinematic().
        STATE.mission2_evidence_cinematic_active = True
        STATE.mission2_evidence_cinematic_timer = 0
        STATE.mission2_evidence_cinematic_shot = 0
        STATE.mission2_evidence_cinematic_flash = 255  # full white at start
    elif after == "upload_done":
        STATE.mission2_stage = STAGE_EXFIL
        STATE.mission_phase = "m2_exfil"
        STATE.mission2_camera_focus = None
        _set_objective("Reach the green exfil marker")
        _radio('SYSTEM: Evidence transmitted. Move to extraction.', color=C_TERMINAL, mark="exfil", allow_when_cut=True)


def _spawn_enemy(col, row, hp=115, speed=2.0, sniper=False):
    """Spawn a Mission 2 IPA grunt (or the kill-box sniper marker).

    The sniper enemy is a facing/HP marker only - the kill-box pressure
    system in _update_sniper_pressure drives actual fire. Speed and HP
    are forced for the sniper regardless of caller args because the
    sniper is an authored fixed-position actor.
    """
    x, y = _tc(col, row)
    e = Enemy(x - 16, y - 16)
    if sniper:
        e.hp = 90
    else:
        e.hp = hp
        e.speed = speed
    e.alerted = True
    e.state = "CHASE"
    e.last_seen_pos = _player_pos()
    e.fire_cooldown = _rng_legacy.randint(18, 75)
    _m2g(e).ipa = True
    _m2g(e).sniper = sniper
    STATE.enemies.append(e)
    return e


# ─────────────────────────────────────────────
# Initialization
# ─────────────────────────────────────────────
def _build_world():
    from missions.m2.draw import _build_garden_walls  # lazy: breaks world<->draw cycle
    STATE.walls = []
    STATE.doors = []
    STATE.enemies = []
    STATE.pickups = []
    STATE.blood_decals = []
    STATE.bullets = []
    STATE.casings = []
    STATE.particles = []
    STATE.thrown_bottles = []
    STATE.molotov_fires = []
    STATE.fire_zones = []
    STATE.floating_texts = []
    STATE.mission2_barriers = []
    STATE.mission2_vehicle_walls = []
    STATE.mission2_prop_walls = []
    # Shelter blast-wall collision rects. Built by _build_shelter_walls()
    # below - a series of small rects approximating the crescent blast wall
    # on the NE side of SAFE_ZONE. Included in _solid_walls() so the player
    # and enemies cannot walk through the wall. Reset to empty here so a
    # mission restart doesn't accumulate stale rects from a previous run.
    STATE.mission2_shelter_walls = []
    # Garden collision rects (hedges, fountain, lamps, trees, benches).
    # Built by _build_garden_walls() - a fixed set of rects that never
    # changes during play, so we could inline them, but keeping them on
    # STATE for symmetry with the other wall lists and so a future
    # dynamic garden feature (e.g. destroyable hedges) has a place to
    # mutate state.
    STATE.mission2_garden_walls = []
    STATE.player = None

    for row_idx, row in enumerate(MISSION2_MAP):
        for col_idx, tile in enumerate(row):
            x, y = col_idx * TILE_SIZE, row_idx * TILE_SIZE
            if tile == "C":
                STATE.walls.append(pygame.Rect(x, y, TILE_SIZE, TILE_SIZE))
            elif tile == "B":
                r = pygame.Rect(x + 4, y + 12, TILE_SIZE - 8, TILE_SIZE - 24)
                STATE.walls.append(r)
                STATE.mission2_barriers.append(r)
            elif tile == "P":
                STATE.player = Player(x + 16, y + 16, max_hp=115)

    if STATE.player is None:
        STATE.player = Player(PLAYER_START[0] - 16, PLAYER_START[1] - 16, max_hp=115)
    # Player speed is set every frame by _update_player based on stage,
    # so we don't need to set it here.  Leaving a value here was dead -
    # it was overwritten on the first frame anyway.

    STATE.mission2_tanker_rect = pygame.Rect(43 * TILE_SIZE + 6, 36 * TILE_SIZE + 8, TILE_SIZE * 5 - 12, TILE_SIZE * 3 - 16)
    STATE.walls.append(STATE.mission2_tanker_rect)

    # Build the shelter blast-wall collision rects. Must happen AFTER
    # STATE.reset() (which clears mission2_shelter_walls) and after the
    # tilemap walls are appended. The dev-args shortcuts (--m2-truck,
    # --m2-flank, --m2-checkpoint, --m2-evidence) all call start_mission2()
    # first, so they inherit the shelter walls automatically.
    _build_shelter_walls()
    # Build the garden collision rects (hedges, fountain, lamps, trees,
    # benches behind the control building). Same inheritance note as above.
    _build_garden_walls()

    # NOTE: No gantry wall. The gantry is purely visual - it shows the
    # crossbeam and catwalk where the sniper sits. Earlier versions added
    # collision under/around it, but that blocked the sniper's downward
    # line of sight to the road. Walking under the gantry IS dangerous:
    # the sniper fires straight down and the kill-box pressure system
    # reads LOS from SNIPER_NEST_POS to the player. Without the wall,
    # the sniper can actually shoot at you.

    # Vehicles are visual props and collision/LOS blockers, but are not drawn as
    # wall tiles.  Vehicle collision is returned by _solid_walls().
    # All cars start INTACT. The Route 12 bombing scene is staged
    # (planted evidence, no real blast damage - see Gabi's "blast
    # pattern is too clean" line), so having pre-burned cars would
    # contradict the narrative. The ONLY source of fire damage on this
    # map is the tanker explosion later in the mission, which chars
    # nearby civilian cars via _explode_tanker.
    STATE.mission2_vehicles = [
        {"kind": "civilian", "rect": pygame.Rect(9 * TILE_SIZE + 8, 70 * TILE_SIZE + 14, 118, 44)},
        {"kind": "civilian", "rect": pygame.Rect(18 * TILE_SIZE + 8, 60 * TILE_SIZE + 10, 126, 48)},
        {"kind": "civilian", "rect": pygame.Rect(31 * TILE_SIZE + 5, 57 * TILE_SIZE + 16, 110, 42)},
        {"kind": "civilian", "rect": pygame.Rect(12 * TILE_SIZE + 8, 48 * TILE_SIZE + 14, 112, 44)},
        {"kind": "civilian", "rect": pygame.Rect(49 * TILE_SIZE + 5, 45 * TILE_SIZE + 12, 116, 44)},
        {"kind": "ipa_truck", "rect": pygame.Rect(46 * TILE_SIZE + 8, 31 * TILE_SIZE + 12, 160, 54)},
        {"kind": "civilian", "rect": pygame.Rect(41 * TILE_SIZE + 6, 26 * TILE_SIZE + 8, 126, 46)},
        # North-west overflow yard.  These three are parked OFF the road on
        # shoulder soil (cols 8-32, rows 14-21) and give the empty verge
        # readable mass at play scale - crates and barrels alone are too
        # small to register across a 22x37-tile field.  The IPA truck is
        # consistent with the corridor being occupied, and it doubles as
        # hard cover if the player wanders west.  Nothing here intersects
        # the sniper nest (col 58) or the kill-box lanes (cols 27-47).
        {"kind": "ipa_truck", "rect": pygame.Rect(8 * TILE_SIZE + 8, 15 * TILE_SIZE + 12, 160, 54)},
        {"kind": "civilian", "rect": pygame.Rect(24 * TILE_SIZE + 8, 20 * TILE_SIZE + 14, 118, 44)},
        {"kind": "civilian", "rect": pygame.Rect(30 * TILE_SIZE + 6, 17 * TILE_SIZE + 12, 112, 42)},
    ]
    for v in STATE.mission2_vehicles:
        # Initialize per-vehicle burn state. A car starts burning when a
        # molotov fire overlaps it; after the burn completes it becomes
        # a permanent "burned" wreck. See _update_molotovs + _draw_vehicle.
        v["burn_progress"] = 0.0   # 0.0 = intact, 1.0 = fully burned
        v["burning"] = False
        STATE.mission2_vehicle_walls.append(v["rect"].inflate(-12, -10))

    STATE.pickups.extend([
        [12 * TILE_SIZE + 32, 68 * TILE_SIZE + 32, "bandage"],
        [24 * TILE_SIZE + 32, 57 * TILE_SIZE + 32, "mag"],
        [54 * TILE_SIZE + 32, 43 * TILE_SIZE + 32, "bandage"],
        [57 * TILE_SIZE + 32, 24 * TILE_SIZE + 32, "mag"],
    ])


def _spawn_mission2_clues():
    """Create mutable clue state from the static clue definitions."""
    STATE.mission2_clues = []
    STATE.mission2_clues_found = set()
    for definition in MISSION2_CLUE_DEFS:
        clue = dict(definition)
        clue["done"] = False
        clue["world_zone"] = definition.get("zone")
        STATE.mission2_clues.append(clue)


def _setup_travel_triggers():
    """Build one-shot environmental story triggers for the larger map."""
    STATE.mission2_triggers = []
    STATE.mission2_story_props = []
    for definition in MISSION2_TRIGGER_DEFS:
        trig = dict(definition)
        trig["triggered"] = False
        STATE.mission2_triggers.append(trig)


# Only props that visually imply mass should block movement/line-of-sight.  Flares,
# soot, puddles, and glints stay decorative; cones/barrels/signs/electrical boxes
# get compact collision so they feel grounded without making navigation annoying.
STORY_PROP_COLLISION_SIZES = {
    "cone": (22, 18),
    "barrel": (30, 30),
    "sign": (34, 18),
    "spark_box": (30, 32),
    "field_radio": (24, 18),
    "broken_camera": (28, 18),
}


def _story_prop_collision_rect(prop):
    size = STORY_PROP_COLLISION_SIZES.get(prop.get("kind"))
    if not size:
        return None
    x, y = prop.get("pos", (0, 0))
    w, h = size
    return pygame.Rect(int(x - w // 2), int(y - h // 2), w, h)


_M2_PROP_SOLID_TILES = ("C", "B", "T")


def _nudge_props_off_solid():
    """Slide any story prop whose anchor lands in solid geometry out of it.

    Trigger-spawned dressing (tanker blast debris, wave beats) is authored
    against tile coords that later map edits can turn into wall/barrier
    tiles; a prop left embedded in a barrier reads as a placement bug.
    A deterministic spiral search (list order, fixed neighbour order) picks
    the nearest open tile within 4 tiles so the fix never shuffles props
    between runs.  Props with no open tile nearby are left alone.
    """
    grid = MISSION2_MAP

    def blocked(col, row):
        if not (0 <= row < len(grid) and 0 <= col < len(grid[0])):
            return True
        return grid[row][col] in _M2_PROP_SOLID_TILES

    for prop in getattr(STATE, "mission2_story_props", []):
        x, y = prop.get("pos", (0, 0))
        col, row = int(x) // 64, int(y) // 64
        if not blocked(col, row):
            continue
        placed = False
        for radius in range(1, 5):
            cand = [(col + dc, row + dr)
                    for dc in range(-radius, radius + 1)
                    for dr in range(-radius, radius + 1)
                    if max(abs(dc), abs(dr)) == radius]
            cand.sort(key=lambda cr: (abs(cr[0] - col) + abs(cr[1] - row), cr))
            for cc, rr in cand:
                if not blocked(cc, rr):
                    prop["pos"] = (cc * 64 + 32, rr * 64 + 32)
                    placed = True
                    break
            if placed:
                break


def _sync_story_prop_collisions():
    _nudge_props_off_solid()
    STATE.mission2_prop_walls = []
    for prop in getattr(STATE, "mission2_story_props", []):
        rect = _story_prop_collision_rect(prop)
        if rect is not None:
            STATE.mission2_prop_walls.append(rect)


def _init_scripted_props():
    _spawn_mission2_clues()
    _setup_travel_triggers()
    # Baseline non-interactive set dressing.  Trigger props still add more
    # moment-to-moment story beats, but these make the larger map feel occupied
    # immediately instead of waiting for trigger activation.
    STATE.mission2_story_props.extend([
        {"kind": "flare", "pos": _tc(9, 72), "life": -1, "age": 0},
        {"kind": "cone", "pos": _tc(15, 69), "life": -1, "age": 0},
        {"kind": "cone", "pos": _tc(24, 66), "life": -1, "age": 0},
        {"kind": "soot", "pos": _tc(19, 60), "life": -1, "age": 0},
        {"kind": "soot", "pos": _tc(32, 58), "life": -1, "age": 0},
        {"kind": "barrel", "pos": _tc(27, 55), "life": -1, "age": 0},
        {"kind": "puddle", "pos": _tc(10, 53), "life": -1, "age": 0},
        {"kind": "puddle", "pos": _tc(21, 49), "life": -1, "age": 0},
        {"kind": "sign", "pos": _tc(34, 43), "life": -1, "age": 0},
        {"kind": "field_radio", "pos": FIELD_RADIO_POS, "life": -1, "age": 0},
        {"kind": "cone", "pos": _tc(40, 35), "life": -1, "age": 0},
        {"kind": "barrel", "pos": _tc(49, 42), "life": -1, "age": 0},
        {"kind": "puddle", "pos": _tc(58, 48), "life": -1, "age": 0},
        {"kind": "spark_box", "pos": _tc(61, 43), "life": -1, "age": 0},
        {"kind": "sign", "pos": _tc(55, 29), "life": -1, "age": 0},
        {"kind": "barrel", "pos": _tc(56, 22), "life": -1, "age": 0},
        {"kind": "barrel", "pos": _tc(64, 20), "life": -1, "age": 0},
        {"kind": "puddle", "pos": _tc(59, 15), "life": -1, "age": 0},
    ])
    # Repeating low-cost dressing across long travel lanes.  These are small
    # enough not to distract from clues, but frequent enough to break up empty
    # asphalt/shoulder screens.
    for col, row, kind in [
        (18, 72, "cone"), (27, 72, "puddle"), (33, 70, "barrel"),
        (18, 65, "puddle"), (36, 64, "cone"), (44, 62, "barrel"),
        (17, 57, "cone"), (39, 55, "puddle"), (49, 56, "sign"),
        (8, 56, "barrel"), (23, 54, "puddle"), (6, 49, "cone"),
        (52, 50, "cone"), (65, 50, "barrel"), (47, 47, "puddle"),
        (23, 43, "sign"), (31, 42, "cone"), (50, 39, "barrel"),
        (22, 34, "puddle"), (42, 34, "cone"), (53, 34, "sign"),
        (43, 24, "barrel"), (48, 23, "cone"), (65, 24, "puddle"),
        (54, 13, "cone"), (66, 14, "barrel"), (53, 19, "puddle"),
    ]:
        STATE.mission2_story_props.append({"kind": kind, "pos": _tc(col, row), "life": -1, "age": 0})

    # ── North-west verge: the checkpoint overflow yard ────────────────
    # The whole cols 1-37 / rows 1-22 block sits outside every ZONE_DEFS
    # region, so nothing was ever placed there and it rendered as a large
    # empty field of shoulder soil.  It is walkable, so it reads as an
    # unfinished map rather than as deliberate wilderness.  The fix is
    # dressing, NOT new geometry: the sniper nest is at col 58 and the
    # kill-box lanes are cols 27-47, so clusters stay west of col 36 and
    # below row 23 - this cannot touch the ambush sightline.
    #
    # Laid out as six loose supply/kit clusters with gaps between them
    # rather than an even scatter: a uniform grid of props would read as
    # decoration, and evenly-spread clutter is what made the earlier
    # asphalt pass look over-clustered.
    for col, row, kind in [
        # Cluster A - supply dump (rows 8-13, cols 6-13)
        (7, 9, "barrel"), (8, 11, "barrel"), (6, 8, "sign"),
        (12, 10, "cone"), (13, 12, "cone"), (10, 13, "puddle"),
        # Cluster B - kit line (rows 15-20, cols 17-25)
        (18, 16, "barrel"), (20, 18, "barrel"), (17, 19, "cone"),
        (24, 15, "cone"), (22, 17, "puddle"), (19, 20, "sign"),
        # Cluster C - fuel dump (rows 4-9, cols 24-32)
        (25, 6, "barrel"), (27, 8, "barrel"), (30, 5, "cone"),
        (31, 9, "cone"), (26, 7, "puddle"), (28, 4, "soot"),
        # Cluster D - kit line, west (rows 19-22, cols 6-14)
        (7, 20, "barrel"), (9, 22, "barrel"), (13, 19, "cone"),
        (11, 21, "sign"), (8, 21, "puddle"),
        # Cluster E - long stores row (rows 10-15, cols 28-36)
        (30, 12, "barrel"), (33, 14, "barrel"), (35, 11, "cone"),
        (29, 15, "cone"), (32, 13, "puddle"), (34, 10, "soot"),
        # Cluster F - northern edge (rows 1-5, cols 16-24)
        (18, 3, "barrel"), (22, 2, "cone"), (20, 4, "puddle"),
        (16, 5, "soot"),
    ]:
        STATE.mission2_story_props.append({"kind": kind, "pos": _tc(col, row), "life": -1, "age": 0})

    # ── Thin map margins ──────────────────────────────────────────────
    # One-tile strips (row 78 south, col 1 west, col 68 east) and the
    # south-east block (rows 56-78, cols 58-67) were all bare.  These sit
    # outside every zone and off every lane, so they are pure dressing.
    for col, row, kind in [
        # South edge strip (row 78)
        (14, 78, "barrel"), (30, 78, "barrel"), (47, 78, "barrel"),
        (60, 78, "barrel"), (22, 78, "cone"), (38, 78, "cone"),
        (54, 78, "cone"), (18, 78, "puddle"), (44, 78, "puddle"),
        # West edge strip (col 1-2, rows 28-42)
        (1, 32, "barrel"), (2, 36, "barrel"), (1, 40, "cone"),
        (2, 30, "puddle"), (1, 38, "soot"), (2, 34, "cone"),
        # South-east block (rows 56-78, cols 58-67)
        (60, 58, "barrel"), (62, 60, "barrel"), (65, 62, "barrel"),
        (61, 64, "cone"), (66, 70, "cone"), (63, 68, "puddle"),
        (60, 72, "sign"), (65, 75, "barrel"), (59, 70, "soot"),
        (67, 66, "cone"), (64, 77, "puddle"),
    ]:
        STATE.mission2_story_props.append({"kind": kind, "pos": _tc(col, row), "life": -1, "age": 0})
    _sync_story_prop_collisions()

    STATE.mission2_truck_manifest = {
        "kind": "manifest",
        "name": "IPA MANIFEST",
        "pos": IPA_TRUCK_POS,
        "done": False,
        "title": "IPA TRUCK MANIFEST",
        "lines": [
            "Cargo cleared by Balaceanu infrastructure office.",
            "Destination: Checkpoint 12.",
            "Timestamp: before the bombing report.",
        ],
    }
    # Tanker inspection card - opened when the player presses [E] at the
    # leaking tanker. The inspection reveals a hidden detonator wired to a
    # remote trigger, which reframes the "approach the tanker" objective
    # from a scripted trap into a scripted discovery. After closing the
    # card, the run-to-shelter phase begins.
    STATE.mission2_tanker_inspection = {
        "kind": "document",
        "name": "TANKER INSPECTION",
        "pos": TANKER_POS,
        "done": False,
        "title": "TANKER - SECONDARY DEVICE",
        "lines": [
            "Connection: Fuel valve has been bypassed - leak is intentional.",
            "Trigger: Remote detonator wired to the manifold. Armed.",
            "Signal source: Same frequency as the sniper's radio.",
            "Conclusion: This truck is the IPA's cleanup charge.",
        ],
    }
    STATE.mission2_evidence = [
        {
            "id": "decree",
            "kind": "decree",
            "name": "DECREE",
            # Position: southern control building, first thing the player
            # encounters when entering from the shelter (south). The player's
            # natural path through the building guides them to this first.
            "pos": _tc(55, 23),
            "done": False,
            "order": 1,
            "title": "PRESIDENTIAL DECREE",
            "lines": [
                "DECREE NO. 47",
                "",
                "By the authority vested in the Office of the President,",
                "the Regional Coalition for Defense and Peace (KRAP) is",
                "hereby authorized to conduct stabilization operations",
                "along the Route 12 corridor.",
                "",
                "All liability for collateral outcomes shall be attributed",
                "to non-state actors. This decree is effective immediately",
                "and supersedes all prior determinations.",
                "",
                "Sebastian Retardovici",
                "President of Acaristan",
            ],
        },
        {
            "id": "balaceanu",
            "kind": "terminal",
            "name": "AUTH CHAIN",
            # Position: middle of control building, encountered after the
            # decree as the player moves north through the building.
            "pos": _tc(63, 19),
            "done": False,
            "order": 2,
            "title": "BALACEANU AUTHORIZATION CHAIN",
            "lines": [
                "> ACCESSING AUTHORIZATION CHAIN...",
                "> DECRYPTING... DONE",
                "",
                "SOURCE:      Presidential Decree No. 47",
                "ROUTED VIA:  Office of the Prime Minister",
                "AUTHORIZED:  PM Balaceanu",
                "CLASSIFY:    Infrastructure Repair (COVER)",
                "",
                "TIMESTAMP:   03:47 - 4 hours before incident",
                "",
                "WARNING: Authorization predates the checkpoint sweep.",
                "WARNING: Cover designation masks cleanup operation.",
            ],
        },
        {
            "id": "mag_packet",
            "kind": "packet",
            "name": "MAG PACKET",
            # Position: northern control building, furthest from the entrance.
            # The player reaches this last, completing the conspiracy reveal.
            "pos": _tc(59, 14),
            "done": False,
            "order": 3,
            "title": "MAG BLAME PACKET",
            "lines": [
                "IPA PRESS OFFICE - DRAFT",
                "FOR IMMEDIATE RELEASE (HOLD)",
                "",
                "The Independent Party of Acaristan attributes the",
                "Route 12 checkpoint incident to MAG operatives.",
                "",
                "Evidence recovered at the scene confirms MAG",
                "responsibility for the detonation. IPA cleanup",
                "teams were dispatched to secure the corridor.",
                "",
                "Prepared: 04:12 - 3 hours before investigators arrived.",
            ],
        },
    ]
    # Scripted actors. They do not pathfind and cannot phase through walls.
    # `reaction` drives draw posture during the sniper sequence:
    #   standing  - default upright
    #   breaking  - leaning toward a run, the veteran response (sideways escape)
    #   frozen    - paralysed mid-decision (hands half-raised)
    #   ducked    - crouched (the instinctive, futile response from a steep angle)
    #   down      - prone / dead
    STATE.mission2_squad = [
        {"name": "GABI",   "pos": list(_tc(31, 41)), "alive": True, "activity": "regrouping", "reaction": "standing"},
        {"name": "SEBY",   "pos": list(_tc(29, 42)), "alive": True, "activity": "regrouping", "reaction": "standing"},
        {"name": "DARIUS", "pos": list(_tc(32, 42)), "alive": True, "activity": "regrouping", "reaction": "standing"},
    ]
