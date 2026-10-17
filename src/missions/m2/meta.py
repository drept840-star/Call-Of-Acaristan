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
import time

import pygame

from core.config import (TILE_SIZE)
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

# ─────────────────────────────────────────────
# Public mission metadata / cutscene lists
# ─────────────────────────────────────────────
MISSION2_ID = "MISSION_2"
MISSION2_KEY = "MISSION2"
MISSION2_TITLE = "Quiet on Route 12"
MISSION2_LOCATION = "Route 12 / Checkpoint 12 Highway Corridor"
MISSION2_PRIMARY_STYLE = "Slow-burn thriller into focused action set-piece"

MISSION2_STORY_FLAGS = {
    "initial_assumption": "KRAP initially believes Route 12 was a MAG bombing.",
    "real_enemy": "IPA forces acting under Balaceanu and President Sebastian Retardovici.",
    "president_role": "President Sebastian Retardovici is openly complicit in the frame-up.",
    "mag_presence": "MAG is mentioned and blamed, but MAG soldiers never appear.",
    "krap_squadmates": "Gabi, Seby, and Darius are scripted KRAP squad actors who die in the sniper kill-box.",
    "vasile_contact": "Vasile loses contact after the tanker blast.",
}

# Keep these names: acaristan.py uses them.
import game.timelines as _timelines  # RPE6 P8: timeline data access
mission2_intro_shots = [
    {
        "scene": "route12_black",
        "speaker": "VASILE",
        "text": "Volkov's file mentions Route 12 before the attack was reported.",
        "lighting": (3, 4, 7),
    },
    {
        "scene": "route12_files",
        "speaker": "VASILE",
        "text": "Checkpoint 12 was marked unstable before the first bomb went off.",
        "lighting": (8, 13, 20),
        # Let the dossier shot reach its close-up/finger beat before advancing.
        "min_ms": 3200,
    },
    {
        "scene": "route12_mag_alert",
        "speaker": "VASILE",
        "text": "Official line says MAG bombing. The timestamps say otherwise.",
        "lighting": (18, 17, 15),
        "min_ms": 1900,
    },
    {
        "scene": "route12_checkpoint",
        "speaker": "VASILE",
        "text": "We go in quiet. We verify the scene. We do not repeat their lie.",
        "lighting": (11, 14, 16),
    },
    {
        "scene": "title_card",
        "speaker": "",
        "text": "MISSION 2\nQUIET ON ROUTE 12",
        "lighting": (5, 5, 8),
    },
]
mission2_intro_shots = _timelines.shots("m2.intro", mission2_intro_shots)  # RPE6 P8: timeline data

mission2_ending_shots = [
    {
        "scene": "route12_aftermath",
        "speaker": "SYSTEM",
        "text": "TRANSMISSION SENT / ARCHIVE PARTIALLY CORRUPTED",
        "lighting": (12, 10, 8),
    },
    {
        "scene": "route12_broadcast",
        "speaker": "PRESIDENT RETARDOVICI",
        "text": "Route 12 will be remembered as the day KRAP discipline failed the nation.",
        "lighting": (18, 14, 12),
    },
    {
        "scene": "route12_broadcast",
        "speaker": "BALACEANU",
        "text": "Effective immediately, KRAP operations in the highway corridor fall under government review.",
        "lighting": (18, 14, 12),
    },
    {
        "scene": "route12_aftermath",
        "speaker": "VASILE",
        "radio": True,  # heard over comms -> radio VO filter
        "text": "Biribel... tell me you got out.",
        "lighting": (10, 10, 12),
    },
    {
        "scene": "route12_aftermath",
        "speaker": "BIRIBEL",
        "text": "They framed KRAP.",
        "lighting": (10, 10, 12),
    },
    {
        "scene": "route12_black",
        "speaker": "VASILE",
        "radio": True,  # heard over comms -> radio VO filter
        "text": "No. They framed you first.",
        "lighting": (2, 2, 4),
    },
    # ── NEW: capture bridge (M2 -> M3 transition) ──
    # IPA dispatches the order to grab Biribel. The regime's framing
    # has shifted the blame to the operator (Biribel), so KRAP's
    # victory on Route 12 was always going to end this way. These
    # three shots show the immediate aftermath: dispatch, kick-in,
    # and the last thing Biribel hears before the lights go out.
    {
        "scene": "ipa_radio_chatter",
        "speaker": "IPA DISPATCH",
        "text": "All units. The KRAP operator is the primary suspect. Bring him in. Authorization IPA-Code Omega.",
        "lighting": (10, 15, 22),  # cold IPA blue
    },
    {
        "scene": "krap_door_kickin",
        "speaker": None,
        "text": None,
        "lighting": (8, 12, 20),  # blue IPA lights
        "is_transition": True,
    },
    # ── MOVED FROM M3: the moment of capture, Vasile's voice fading. ──
    # Was the last shot of mission3.py INTRO_SHOTS. Moving it to
    # M2 ending completes the M2 arc on the moment Biribel is taken
    # rather than starting the M3 cold open there (the M3 cold open
    # now picks up 3 days later in a cell).
    {
        "scene": "biribel_blackout",
        "speaker": "VASILE",
        "radio": True,  # heard over comms -> radio VO filter
        "text": "Biribel? ...Biribel?!",
        "lighting": (2, 2, 4),
    },
]
mission2_ending_shots = _timelines.shots("m2.ending", mission2_ending_shots)  # RPE6 P8: timeline data

seby_pickup_shots = [
    {
        "scene": "seby_pickup_body",
        "speaker": "",
        "text": "",
        "lighting": (10, 10, 12),
        "min_ms": 2200,
        "hide_caption": True,
    },
    {
        "scene": "seby_pickup_reach",
        "speaker": "",
        "text": "",
        "lighting": (12, 12, 14),
        "min_ms": 2400,
        "hide_caption": True,
    },
    {
        "scene": "seby_pickup_raise",
        "speaker": "",
        "text": "",
        "lighting": (14, 14, 16),
        "min_ms": 2600,
        "hide_caption": True,
    },
]
seby_pickup_shots = _timelines.shots("m2.seby_pickup", seby_pickup_shots)  # RPE6 P8: timeline data

OPENING_CINEMATIC = [
    {"speaker": s["speaker"], "text": s["text"]}
    for s in mission2_intro_shots
    if s.get("speaker")
]

SQUADMATE_DEATH_CUTSCENE = [
    {"speaker": "GABI", "text": "No MAG banners. No claim. Just a scene waiting for us."},
    {"speaker": "VASILE", "text": "Stop. Everybody down."},
    {"speaker": "SEBY", "text": "Sniper! Highway sign!"},
    {"speaker": "VASILE", "text": "That is IPA fire discipline. Biribel, survive the kill-box."},
]

MISSION_PHASES = [
    {"phase": 1, "name": "Investigation", "objective": "Inspect staged Route 12 evidence."},
    {"phase": 2, "name": "Sniper Kill-Box", "objective": "Witness the squad ambush."},
    {"phase": 3, "name": "IPA Reveal", "objective": "Clear a small authored IPA team."},
    {"phase": 4, "name": "Tanker Run", "objective": "Run before the hidden detonator fires."},
    {"phase": 5, "name": "Comms Blackout", "objective": "Process the blast and move alone."},
    {"phase": 6, "name": "Evidence", "objective": "Collect and upload proof of the frame-up."},
]

# ─────────────────────────────────────────────
# Map / authored layout
# ─────────────────────────────────────────────
# Final-build Mission 2 uses a much larger route/checkpoint space.  The map is
# still generated as a tilemap so the existing renderer, minimap, wall builder,
# and collision systems keep working.
MAP_W, MAP_H = 70, 80

STAGE_INVESTIGATE = "investigate"
STAGE_SNIPER = "sniper"
STAGE_COMBAT = "combat"
STAGE_TRUCK = "truck"
STAGE_TANKER = "tanker"
STAGE_RUN = "tanker_run"
STAGE_BLACKOUT = "blackout"
STAGE_EVIDENCE = "evidence"
STAGE_UPLOAD = "upload"
STAGE_EXFIL = "exfil"
STAGE_DONE = "done"

# Five investigation clues are available; four are required so the player gets
# a fuller detective beat without being hard-stuck on one missed prop.
REQUIRED_INVESTIGATION_CLUES = 4

# Named regions are the backbone for final-build level scripting.  Each zone has
# a tile-space rect and a generated world-space rect.  Clues, travel-buffer
# triggers, ambient events, and camera logic can all reference these names.
ZONE_DEFS = {
    "approach": {
        "label": "West Approach Road",
        "tile_rect": pygame.Rect(2, 66, 30, 12),
        "floor": ".",
        "color": (38, 37, 34),
    },
    "blast_scene": {
        "label": "Blast Scene / Staged MAG Evidence",
        "tile_rect": pygame.Rect(10, 52, 40, 15),
        "floor": ".",
        "color": (37, 35, 32),
    },
    "south_ditch": {
        "label": "South Drainage Ditch",
        "tile_rect": pygame.Rect(3, 43, 25, 21),
        "floor": "d",
        "color": (30, 35, 34),
    },
    "north_service": {
        "label": "North Service Road",
        "tile_rect": pygame.Rect(43, 36, 25, 20),
        "floor": "s",
        "color": (33, 36, 35),
    },
    "toll_plaza": {
        "label": "Checkpoint 12 Toll Plaza / Kill-Box",
        "tile_rect": pygame.Rect(18, 28, 39, 16),
        "floor": ".",
        "color": (34, 34, 33),
    },
    "east_control": {
        "label": "East Control Building / Upload Sector",
        "tile_rect": pygame.Rect(39, 7, 29, 23),
        "floor": "O",
        "color": (29, 36, 38),
    },
}


def _tc(col, row):
    return col * TILE_SIZE + TILE_SIZE // 2, row * TILE_SIZE + TILE_SIZE // 2


def _tile_rect(col, row, w=1, h=1):
    return pygame.Rect(col * TILE_SIZE, row * TILE_SIZE, w * TILE_SIZE, h * TILE_SIZE)


def _zone_world_rect(zone_name):
    tr = ZONE_DEFS[zone_name]["tile_rect"]
    return _tile_rect(tr.x, tr.y, tr.w, tr.h)


ZONE_WORLD_RECTS = {name: _zone_world_rect(name) for name in ZONE_DEFS}


def get_zone_for_world_pos(pos):
    """Return the authored zone name for a world-space point, or None."""
    for name, rect in ZONE_WORLD_RECTS.items():
        if rect.collidepoint(pos):
            return name
    return None


# Final build authored points.
PLAYER_START = _tc(8, 74)

# Building footprints as (col, row, w, h), wall ring included.  These are the
# single source of truth for both the map generator (which outlines them) and
# the renderer (which needs to know which floor tiles are INTERIOR so it can
# grade them differently from the exterior asphalt - an interior painted the
# same value as the road reads as a hole in the map, not as a room).
MISSION2_BUILDINGS = (
    (51, 9, 17, 17),   # control building
    (41, 18, 9, 8),    # security hut / checkpoint utility room
)

KILL_ZONE = _tc(36, 34)
FIELD_RADIO_POS = _tc(39, 36)  # Local panic prop for Darius; not the distant clue radio.
SNIPER_NEST_POS = _tc(58, 26)  # Highway sign gantry / overpass platform.
SNIPER_CLOSE_KILL_TEXT = "TOO CLOSE - SNIPER EXECUTION"

# Sniper cutscene camera anchors - designed compositions, not dynamic tracking.
SNIPER_ARENA_CAM = _tc(36, 36)
SNIPER_ARENA_CAM_2 = _tc(34, 38)  # frames the drag toward cover (SW of CAM)
SNIPER_PLAYER_CAM = _tc(38, 40)

# Authored try-to-save window. These remain as module-level constants for
# any code that wants to read them outside of the beat clock. The runtime
# values come from SNIPER_BEAT_CLOCK["movement_one"]["tried_to_save_window_*"].
SNIPER_TRY_SAVE_WINDOW_START = 320
SNIPER_TRY_SAVE_WINDOW_END = 360

# Fixed cinematic anchors - the camera holds these, not midpoints.
CAM_SQUAD_WIDE    = _tc(35, 36)  # establishes all three squadmates
CAM_GABI_BODY     = _tc(35, 35)  # tight on Gabi where he falls
CAM_GANTRY_REVEAL = (SNIPER_NEST_POS[0], SNIPER_NEST_POS[1] + 140)  # low-angle hero shot of the gantry
CAM_SEBY_DRAG     = _tc(34, 36)  # frames Seby and Gabi during the drag
CAM_DARIUS_RADIO  = _tc(36, 36)  # tight on Darius reaching for the radio

IPA_TRUCK_POS = _tc(48, 32)
# Interaction point at the valve assembly on the SOUTH side of the tanker.
# The valve/pipe/hand-wheel is drawn at tank_rect.centerx, ~30px below the
# tank's south edge. _tc(45, 40) lands right on top of the hand-wheel so
# the marker circle and the [E] prompt sit on the actual valve the player
# is inspecting - not on the side of the tank.
TANKER_POS = _tc(45, 40)
SAFE_ZONE = _tc(29, 47)
CONTROL_ROOM = _tc(58, 18)
UPLOAD_TERMINAL_POS = _tc(61, 16)
EXFIL_POS = _tc(64, 12)

# ── Officers' leisure garden (behind the control building) ──────────────
# The control building's north wall (row 9) is solid - no door on the
# garden side. The garden is a decorated area the player can wander into
# by walking around the NW corner (col 50) or NE corner (col 68) of the
# building. It's an environmental storytelling beat: a manicured officers'
# garden behind a building used for framing MAG creates a contrast that
# makes the IPA feel more human and more monstrous at the same time.
#
# Layout (top-down, N=up, building south wall at row 9):
#   r1:  [tree]  flowers  flowers  flowers  flowers  flowers  [tree]
#   r2:  flowers  flowers  flowers  flowers  flowers  flowers  flowers
#   r3:  [hedge NW]              path           [hedge NE]
#   r4:  [hedge NW]  [bench] [fountain] [bench] [hedge NE]
#   r5:  [hedge NW]              path           [hedge NE]
#   r6:  [hedge SW]              path           [hedge SE]
#   r7:  flowers  flowers  flowers  flowers  flowers  flowers  flowers
#   r8:  flowers  flowers  flowers  flowers  flowers  flowers  flowers
#         c51      c53      c55-63      c65      c67
#
# The 4 hedges (NW/NE/SW/SE quadrants) have collision - they force the
# player to use the central E-W path. Flowers, benches, and trees are
# walkable (low props). The fountain has collision (it's a solid stone
# basin). Lamp posts have collision (thin poles).
GARDEN_CENTER = _tc(59, 4)        # fountain centerpiece
GARDEN_PATH_NORTH_Y = _tc(0, 3)[1]  # y of path row 3
GARDEN_PATH_SOUTH_Y = _tc(0, 6)[1]  # y of path row 6
# Hedge quadrant rects (world-space pygame.Rects). Each is a 3x2-tile block
# leaving a 3-tile-wide path gap in the middle (cols 55-63).
_HEDGE_W = 3 * TILE_SIZE  # 3 tiles wide
_HEDGE_H = 3 * TILE_SIZE  # 3 tiles tall (rows 3-5 for N hedges, row 6 only would be too thin)
# North hedges: rows 3-5, cols 51-53 (NW) and 65-67 (NE)
# South hedges: row 6, cols 51-53 (SW) and 65-67 (SE) - shorter, just 1 tile
# Actually, let's make all 4 hedges the same size for symmetry: 3x2 tiles
# NW hedge: cols 51-53, rows 3-4
# NE hedge: cols 65-67, rows 3-4
# SW hedge: cols 51-53, rows 5-6
# SE hedge: cols 65-67, rows 5-6
# Path gap: cols 54-64 (11 tiles = 704px wide), rows 3-6 - plenty of room
GARDEN_HEDGE_RECTS = [
    pygame.Rect(51 * TILE_SIZE, 3 * TILE_SIZE, 3 * TILE_SIZE, 2 * TILE_SIZE),  # NW
    pygame.Rect(65 * TILE_SIZE, 3 * TILE_SIZE, 3 * TILE_SIZE, 2 * TILE_SIZE),  # NE
    pygame.Rect(51 * TILE_SIZE, 5 * TILE_SIZE, 3 * TILE_SIZE, 2 * TILE_SIZE),  # SW
    pygame.Rect(65 * TILE_SIZE, 5 * TILE_SIZE, 3 * TILE_SIZE, 2 * TILE_SIZE),  # SE
]
# Fountain collision (circular basin approximated as a rect, ~2 tiles wide)
GARDEN_FOUNTAIN_RECT = pygame.Rect(
    GARDEN_CENTER[0] - TILE_SIZE, GARDEN_CENTER[1] - TILE_SIZE,
    2 * TILE_SIZE, 2 * TILE_SIZE,
)
# Lamp post collision (thin poles flanking the fountain, on the path)
# NOTE: lamps are placed at cols 55 and 63 (just outside the fountain's
# 2-tile radius), NOT at the path entrances (cols 54/64). The hedges
# already gate the entrances - putting lamps there too would over-block.
# These lamps read as path lighting, framing the fountain from both sides.
GARDEN_LAMP_RECTS = [
    pygame.Rect(_tc(55, 3)[0] - 4, _tc(55, 3)[1] - 4, 8, 8),   # NW of fountain
    pygame.Rect(_tc(63, 5)[0] - 4, _tc(63, 5)[1] - 4, 8, 8),   # SE of fountain
]
# Ornamental trees (corners) - collision as small rects (trunk)
GARDEN_TREE_RECTS = [
    pygame.Rect(_tc(51, 1)[0] - 6, _tc(51, 1)[1] - 6, 12, 12),  # NW corner
    pygame.Rect(_tc(67, 1)[0] - 6, _tc(67, 1)[1] - 6, 12, 12),  # NE corner
    pygame.Rect(_tc(51, 8)[0] - 6, _tc(51, 8)[1] - 6, 12, 12),  # SW corner
    pygame.Rect(_tc(67, 8)[0] - 6, _tc(67, 8)[1] - 6, 12, 12),  # SE corner
]
# Benches (on the path, east and west of fountain) - collision as rect.
# Benches are 64x24 (a full tile wide, 3/8 tile deep) so they're clearly
# recognizable furniture, not tiny wood blocks. They sit perpendicular to
# the path: the west bench's backrest faces west (away from the fountain)
# so the seat faces the centerpiece; the east bench mirrors it.
GARDEN_BENCH_RECTS = [
    pygame.Rect(_tc(56, 4)[0] - 32, _tc(56, 4)[1] - 12, 64, 24),  # west bench (faces E toward fountain)
    pygame.Rect(_tc(62, 4)[0] - 32, _tc(62, 4)[1] - 12, 64, 24),  # east bench (faces W toward fountain)
]

# Post-ambush gameplay anchors.  These turn the cutscene's promise (the road is
# a sniper kill-box) into playable objectives: get cover, survive sightlines,
# then flank the gantry.
KILLBOX_COVER_POSITIONS = [
    _tc(34, 40), _tc(40, 41), _tc(30, 43), _tc(42, 34), _tc(28, 37)
]
KILLBOX_FLANK_POSITIONS = [
    _tc(22, 47),  # south ditch route
    _tc(55, 45),  # north service route
]
SNIPER_FLANK_POS = _tc(54, 28)
KILLBOX_DANGER_RECT = _tile_rect(27, 30, 20, 15)
SNIPER_MAX_LOS_RANGE = 1900          # sniper sees far down Route 12
# Flank cutscene timing (in frames @ 60fps). Total = 540 = 9 seconds.
# Pacing is deliberately slow on the tension beats (push-in, hold+aim,
# stamp hold) and fast on the reaction beats (startle, scramble).
FLANK_CUTSCENE_DURATION     = 540
FLANK_BEAT_PUSH_IN_END      = 90    # 1.5s - slow dolly-in completes
FLANK_BEAT_STARTLE          = 180   # 3.0s - sniper spots the flanker
FLANK_BEAT_SCRAMBLE_BEGIN   = 220   # 3.66s - silhouette drops rifle, crawls away
FLANK_BEAT_BURST            = 300   # 5.0s - big dust + debris + casing scatter
FLANK_BEAT_STAMP_FADE_IN    = 330   # 5.5s - "NEST ABANDONED" stamp begins appearing
FLANK_BEAT_STAMP_FULL       = 390   # 6.5s - stamp fully visible
FLANK_BEAT_LETTERBOX_OUT    = 510   # 8.5s - letterbox bars start retracting
# Unified close-range radius. The old code had two thresholds
# (SNIPER_POINT_BLANK_RANGE = 520 and SNIPER_CLOSE_KILL_RADIUS = 170) which
# produced confusing overlap. 170px = walking right under the gantry.
SNIPER_POINT_BLANK_RANGE = 170
SNIPER_AIM_FRAMES = 34               # normal exposed aim time
SNIPER_CLOSE_AIM_FRAMES = 8          # close-range snap shot
SNIPER_DAMAGE = 75                   # normal sniper hit
SNIPER_EXECUTION_DAMAGE = 9999       # too close = dead
REGROUP_ENTRY_POSITIONS = [
    _tc(33, 38),   # Gabi - clear path north
    _tc(35, 38),   # Seby
    _tc(37, 38),   # Darius
]
REGROUP_TARGET_POSITIONS = [
    _tc(33, 35),   # Gabi forward
    _tc(35, 35),   # Seby center
    _tc(37, 35),   # Darius right
]

# Post-cutscene sniper pressure tuning.
SNIPER_GRACE_FRAMES = 90        # time after cutscene before sniper starts lethal tracking
SNIPER_LOCK_FRAMES = 105        # exposed frames before instant kill
SNIPER_LOCK_DECAY = 5           # how quickly lock drains in cover
SNIPER_WARN_THRESHOLDS = (35, 65, 90)

# Reinforcement spawn anchors for the kill-box.  These are perimeter positions
# (service-road gate, ditch culvert, toll-booth alleys, gantry support) where
# IPA shooters can plausibly pour in once the player commits to cover.  Each
# is a world-space anchor; spawns are placed near these with small jitter.
KILLBOX_REINFORCEMENT_SPAWNS = [
    (58, 32),  # north service road, east of gantry
    (54, 41),  # north service road, behind toll booths
    (46, 28),  # gantry support, drops onto road
    (20, 41),  # south ditch culvert, west flank
    (26, 44),  # south ditch, closer push
    (50, 34),  # toll booth alley, mid-right
    (30, 30),  # toll booth alley, mid-left
]

# Flanker spawns - INSIDE the control building, behind where the player
# typically camps during the evidence phase. Used by waves 2 and 3 so the
# player can't just hold one doorway; they have to watch their back.
# Positions are interior tiles with validated wall clearance (the spawn
# function tries 5 nearby positions if the first is blocked).
KILLBOX_FLANK_SPAWNS = [
    (55, 13),  # NW control building interior - behind player entering from south
    (63, 14),  # NE control building interior - flanks the upload terminal approach
    (58, 20),  # SW control building interior - cuts off retreat to the tanker area
]


MISSION2_CLUE_DEFS = [
    {
        "id": "paint",
        "zone": "blast_scene",
        "kind": "mag_paint",
        "name": "MAG PAINT",
        "pos": _tc(20, 59),
        "title": "FRESH MAG PAINT",
        "lines": [
            "The stencil is wet.",
            "There is soot under the paint, not over it.",
            "Someone marked this after the blast.",
        ],
    },
    {
        "id": "timer",
        "zone": "toll_plaza",
        "kind": "timer_fragment",
        "name": "TIMER FRAGMENT",
        "pos": _tc(33, 40),
        "title": "TIMING RELAY FRAGMENT",
        "lines": [
            "A burned timing board is lodged under the barrier.",
            "The relay uses checkpoint-grade parts, not scavenged MAG hardware.",
            "This was delayed, measured, and clean.",
        ],
    },
    {
        "id": "radio",
        "zone": "south_ditch",
        "kind": "radio",
        "name": "BROKEN RADIO",
        "pos": _tc(13, 50),
        "title": "BROKEN KRAP RADIO",
        "lines": [
            "The alert code loops before the first bomb report.",
            "The official MAG story was queued too early.",
        ],
    },
    {
        "id": "bootprints",
        "zone": "north_service",
        "kind": "bootprints",
        "name": "BOOTPRINTS",
        "pos": _tc(55, 45),
        "title": "CLEAN BOOTPRINTS",
        "lines": [
            "The prints cross over soot and broken glass.",
            "Heavy square tread. Steel heel plate.",
            "MAG patrols do not wear checkpoint-issue boots.",
        ],
    },
    {
        "id": "range_card",
        "zone": "toll_plaza",
        "kind": "range_card",
        "name": "RANGE MARKS",
        "pos": _tc(38, 33),
        "title": "SCRATCHED RANGE MARKS",
        "lines": [
            "Numbers are scratched into the concrete: 180, 220, 260.",
            "They line up with the toll barrier and the KRAP regroup point.",
            "Someone measured this kill-box before you arrived.",
        ],
    },
]


MISSION2_TRIGGER_DEFS = [
    {
        "id": "arrival_flares",
        "zone": "approach",
        "rect": _tile_rect(5, 69, 21, 7),
        "dialogue": 'VASILE: "Route 12 opens into the checkpoint corridor. Stay slow."',
        "sound": "radio_static",
        "volume": 0.18,
        "props": [
            {"kind": "flare", "pos": _tc(12, 70)},
            {"kind": "flare", "pos": _tc(19, 67)},
        ],
    },
    {
        "id": "blast_overlook",
        "zone": "blast_scene",
        "rect": _tile_rect(15, 61, 25, 5),
        "dialogue": 'GABI: "Blast pattern is too clean for a panic bombing."',
        "sound": "water_drip",
        "volume": 0.16,
        "props": [
            {"kind": "soot", "pos": _tc(23, 60)},
            {"kind": "flare", "pos": _tc(30, 61)},
        ],
    },
    {
        "id": "ditch_static",
        "zone": "south_ditch",
        "rect": _tile_rect(6, 47, 17, 10),
        "dialogue": 'DARIUS: "Static is pooling down here. Something jammed the channel."',
        "sound": "radio_static",
        "volume": 0.28,
        "props": [
            {"kind": "broken_camera", "pos": _tc(17, 52)},
        ],
    },
    {
        "id": "service_gate",
        "zone": "north_service",
        "rect": _tile_rect(48, 41, 17, 9),
        "dialogue": 'VASILE: "Government tread, checkpoint equipment... keep your heads down."',
        "sound": "menu_hover",
        "volume": 0.14,
        "props": [
            {"kind": "spark_box", "pos": _tc(61, 43)},
        ],
    },
    {
        "id": "gantry_glint_preview",
        "zone": "toll_plaza",
        "rect": _tile_rect(28, 31, 18, 8),
        "dialogue": 'SEBY: "Did anyone else see that flash above the gantry?"',
        "sound": "menu_hover",
        "volume": 0.18,
        "props": [
            {"kind": "glint", "pos": SNIPER_NEST_POS},
        ],
    },
]


# Reordered cutscene per the 12-point rework.
#
# - "wrong_scan": squad looks the WRONG way (west cars / south ditch).  This
#   widens the gap between what the audience knows and what the squad knows.
# - "gabi_shot" is now SHORT and has NO laser telegraph for the first kill -
#   he dies mid-sentence to maximize shock.
# - "dead_air" is a held silent beat after Gabi falls (no music, ducked ambience,
#   tinnitus, dripping radio).  The squad is frozen in disbelief.
# - "origin_reveal" now happens AFTER the first death: muzzle flash, brief
#   silhouette of the shooter on the gantry, then he hides again.
# - Seby's death is long and physical (he drags Gabi, shouts at the gantry).
# - Darius's death is mid-radio-call: he reaches for the field radio handset
#   and dies whispering a mayday into it.
# - "biribel_near_miss" freezes player input, slams camera to impact, etc.
# - "handoff": single hard black frame at the very end before gameplay.
SNIPER_PHASES = [
    {"name": "regroup",        "duration": 100},
    {"name": "movement_one",   "duration": 720},
    {"name": "movement_two",   "duration": 600},
    {"name": "movement_three", "duration": 600},
]

SNIPER_BEAT_CLOCK = {
    "regroup": {
        "spread_line": 80,
    },
    "movement_one": {
        "regroup_line":                70,
        "scan_west":                  170,
        "gabi_crack":                 300,
        "tried_to_save_window_start": 320,
        "tried_to_save_window_end":   360,
        "silence_start":              302,
        "silence_frames":             110,
        "vasile_down":                320,
        "origin_flash":               440,
        "muzzle_flash":               440,
        "gantry_hold":                460,
        "seby_react":                 660,
    },
    "movement_two": {
        "seby_breaks":             70,
        "seby_arrives":            190,
        "seby_drag_to_cover_end":  460,
        "seby_crack":              430,
        "vasile_cover":            100,
        "vasile_hold":             450,
        "darius_reaches":          500,
        "darius_crack":            570,
    },
    "movement_three": {
        "near_miss": 110,
        "weapon_pickup": 180,
        "hard_black": 320,
    },
}


def _beat(phase, event, default=0):
    return SNIPER_BEAT_CLOCK.get(phase, {}).get(event, default)

def _beat_now(phase, pt, event):
    f = SNIPER_BEAT_CLOCK.get(phase, {}).get(event)
    return f is not None and pt == f
