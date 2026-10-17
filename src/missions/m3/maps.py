
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
import time

import pygame

import core.config  # noqa: F401  boot side effect (A-001/B-007); removed in P4-1
import game.levels as _levels  # RPE6 P7: level data access
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

from missions.m3.meta import MAP_W, MAP_H, BCAST_MAP_W, BCAST_MAP_H, PLAYER_START_TILE

def _set_tile(g, col, row, tile):
    if 0 <= col < MAP_W and 0 <= row < MAP_H:
        g[row][col] = tile


def _paint_tiles(g, rect, tile):
    for row in range(rect.y, rect.y + rect.h):
        for col in range(rect.x, rect.x + rect.w):
            _set_tile(g, col, row, tile)


def _outline_building(g, col, row, w, h, interior="O", door_tiles=()):
    """Draw a rectangular building perimeter with a door gap.

    Mirrors mission2._outline_building so door punches read the same way.
    """
    for yy in range(row, row + h):
        for xx in range(col, col + w):
            border = xx in (col, col + w - 1) or yy in (row, row + h - 1)
            _set_tile(g, xx, yy, "C" if border else interior)
    for dx, dy in door_tiles:
        _set_tile(g, col + dx, row + dy, interior)


# Tile chars the player can stand on (or open a door into).  Exterior ground
# is deliberately absent: in the maps that call _seal_exterior_shell, "g" is
# collision-solid filler (world._build_broadcast_world turns both "C" and "g"
# into STATE.walls).
_WALKABLE_TILES = ".EPDBXKOYMLS"


def _seal_exterior_shell(g):
    """Wall off out-of-bounds ground tiles that touch walkable floor.

    In the Broadcast (and Comms) maps every "g" tile is collision-solid while
    the tile art paints it as open compound gravel, so any "g" sharing an edge
    with floor read as a way out of the play area - and the player then walked
    into an invisible wall one tile later (owner report: "a part in Slice 6
    that looks like you can go out the playing area, but it's invisible").

    Swapping those tiles to the wall char is collision-neutral - "C" and "g"
    are both solid in these maps - so the walkable shape is byte-identical and
    only the art changes: the rooms and corridors grow the wall they were
    always missing instead of opening onto gravel they cannot reach.
    """
    h = len(g)
    w = len(g[0]) if h else 0
    for y in range(h):
        row = g[y]
        for x in range(w):
            if row[x] != "g":
                continue
            if ((y > 0 and g[y - 1][x] in _WALKABLE_TILES)
                    or (y < h - 1 and g[y + 1][x] in _WALKABLE_TILES)
                    or (x > 0 and row[x - 1] in _WALKABLE_TILES)
                    or (x < w - 1 and row[x + 1] in _WALKABLE_TILES)):
                row[x] = "C"


def _generate_map():
    """Build the Stabilization Center tilemap - a real prison block.

    Layout (48x48 tiles):
      - Cell block: 4 cells (north side), each 8 wide x 8 tall, rows 5-12
      - Main corridor: rows 14-16, east-west artery
      - Guard room: rows 18-24, central monitoring station
      - Kitchen / utility: west side, rows 20-24
      - Exit double doors: east side of main corridor
      - Player spawn: southernmost cell (32, 9)
    """
    g = [["g" for _ in range(MAP_W)] for _ in range(MAP_H)]

    # World border (concrete perimeter - keeps the player inside).
    for x in range(MAP_W):
        g[0][x] = g[MAP_H - 1][x] = "C"
    for y in range(MAP_H):
        g[y][0] = g[y][MAP_W - 1] = "C"

    # --- Cell block (north side, rows 5-12) ---
    # 4 cells, each 8 tiles wide, door gap at the south wall.
    for cell in range(4):
        cx = 6 + cell * 8
        for y in range(5, 13):
            for x in range(cx, cx + 8):
                if y == 5 or y == 12 or x == cx or x == cx + 7:
                    if y == 12 and cx + 3 <= x <= cx + 4:
                        g[y][x] = "D"
                    else:
                        g[y][x] = "C"
                else:
                    g[y][x] = "."

    # --- Cell-block approach hallway (row 13, cols 6-39) ---
    # 1-tile strip directly south of the four cell doors. Gives Volkov a
    # real, visible space to approach through during the breach cutscene
    # (instead of spawning in undefined exterior ground) and gives the
    # player a natural threshold to step onto when leaving the cell in
    # STAGE_BREAKOUT. Connects the cell doors (row 12) to the main
    # corridor (rows 14-16) without any map gaps.
    for x in range(6, 40):
        g[13][x] = "."

    # --- Main corridor (rows 14-16, cols 6-40) ---
    for y in range(14, 17):
        for x in range(6, 40):
            g[y][x] = "."

    # --- Guard room (south side, rows 18-24, cols 10-35) ---
    for y in range(18, 25):
        for x in range(10, 36):
            if y == 18 or y == 24 or x == 10 or x == 35:
                g[y][x] = "C"
            else:
                g[y][x] = "O"

    # Connect the guard room to the main corridor. Without this north-wall
    # door, Guard 3 spawned inside a sealed room and could never be reached.
    # Row 17 is a short approach strip between the corridor and the room.
    for x in range(21, 24):
        g[17][x] = "."
    g[18][22] = "D"

    # --- Kitchen / utility room (west, rows 20-24, cols 2-6) ---
    for y in range(20, 25):
        for x in range(2, 7):
            if y == 20 or y == 24 or x == 2 or x == 6:
                g[y][x] = "C"
            else:
                g[y][x] = "K"

    # Punch a door in the east wall of the kitchen so the player can exit
    g[22][6] = "D"

    # --- Armory (east of guard room, locked-down weapon cage) ---
    # This is where the K-9 suppressed SMG is mounted on the north wall. The
    # room connects to the guard/control room through a normal openable door.
    for y in range(18, 25):
        for x in range(36, 45):
            if y == 18 or y == 24 or x == 36 or x == 44:
                g[y][x] = "C"
            else:
                g[y][x] = "O"
    # Door gap between guard room and armory.
    g[21][35] = "D"
    g[21][36] = "D"

    # --- Lower service wing (optional space, not objective-critical) ---
    # A coherent lower branch: guard room -> service spine -> laundry / yard /
    # maintenance. This fills the dead lower map with believable facility space
    # instead of loose props glued onto the floor.
    for y in range(25, 31):
        for x in range(3, 46):
            border = y in (25, 30) or x in (3, 45)
            g[y][x] = "C" if border else "."

    # South exit from the guard room down into the service spine.
    g[24][22] = "D"
    g[24][23] = "D"
    g[25][22] = "."
    g[25][23] = "."

    # Three doors along the lower service spine.
    for x in (10, 11):
        g[30][x] = "D"       # laundry
    for x in (23, 24):
        g[30][x] = "D"       # exercise yard
    for x in (36, 37):
        g[30][x] = "D"       # maintenance wing

    # Laundry / uniform processing room (west).
    for y in range(31, 43):
        for x in range(4, 18):
            border = y in (31, 42) or x in (4, 17)
            if border and not (y == 31 and x in (10, 11)):
                g[y][x] = "C"
            else:
                g[y][x] = "L"

    # Exercise yard / concrete rec cage (middle). It is indoor-visible optional
    # space: fenced concrete, workout lines, no story payload.
    for y in range(31, 44):
        for x in range(18, 31):
            border = y in (31, 43) or x in (18, 30)
            if border and not (y == 31 and x in (23, 24)):
                g[y][x] = "C"
            else:
                g[y][x] = "Y"

    # Maintenance / boiler wing (east).
    for y in range(31, 43):
        for x in range(31, 45):
            border = y in (31, 42) or x in (31, 44)
            if border and not (y == 31 and x in (36, 37)):
                g[y][x] = "C"
            else:
                g[y][x] = "M"

    # --- Exit double doors (east side of main corridor) ---
    # Aligned with the cell-block road/corridor rows (14-16). The previous
    # 15-17 placement sat one tile too low, so the service exit looked off the
    # corridor's Y-axis.
    for y in range(14, 17):
        for x in range(40, 43):
            g[y][x] = "E"

    # --- Player spawn in the southernmost cell (cell 3, centre floor) ---
    pc, pr = PLAYER_START_TILE
    _set_tile(g, pc, pr, "P")

    return ["".join(row) for row in g]


def _generate_comms_map():
    """Build the second Mission 3 map: service/comms wing.

    This is a separate playable map loaded after the service-exit transition
    cutscene. It is intentionally compact: service corridor, relay room,
    server cage, side utility room, and an east archive-access door for the
    next slice.
    """
    g = [["g" for _ in range(MAP_W)] for _ in range(MAP_H)]

    # World border.
    for x in range(MAP_W):
        g[0][x] = g[MAP_H - 1][x] = "C"
    for y in range(MAP_H):
        g[y][0] = g[y][MAP_W - 1] = "C"

    # Service arrival corridor.
    for y in range(22, 28):
        for x in range(3, 45):
            border = y in (22, 27) or x in (3, 44)
            g[y][x] = "C" if border else "."

    # West service airlock / spawn area.
    for y in range(18, 29):
        for x in range(3, 11):
            border = y in (18, 28) or x in (3, 10)
            if border and not (x == 10 and y in (24, 25)):
                g[y][x] = "C"
            else:
                g[y][x] = "."
    g[24][10] = "D"
    g[25][10] = "D"
    g[24][6] = "P"

    # Security booth / access desk just east of the airlock. This makes the
    # spawn area feel like a connected checkpoint instead of an empty hallway.
    for y in range(17, 23):
        for x in range(11, 16):
            border = y in (17, 22) or x in (11, 15)
            if border and not (y == 22 and x in (12, 13)):
                g[y][x] = "C"
            else:
                g[y][x] = "O"
    g[22][12] = "D"
    g[22][13] = "D"

    # Main comms relay room, north of corridor.
    for y in range(10, 22):
        for x in range(15, 33):
            border = y in (10, 21) or x in (15, 32)
            if border and not (y == 21 and x in (23, 24)):
                g[y][x] = "C"
            else:
                g[y][x] = "O"
    g[21][23] = "D"
    g[21][24] = "D"
    # Short threshold through the service-corridor north wall.
    g[22][23] = "."
    g[22][24] = "."

    # Server cage / equipment bay to the east.
    for y in range(13, 30):
        for x in range(34, 45):
            border = y in (13, 29) or x in (34, 44)
            if border and not (x == 34 and y in (23, 24)):
                g[y][x] = "C"
            else:
                g[y][x] = "S" if x in (35, 36, 42, 43) and 15 <= y <= 27 else "O"
    g[23][34] = "D"
    g[24][34] = "D"
    # East archive-access door out of the server cage.
    g[24][44] = "D"

    # South utility / battery backup room.
    for y in range(29, 40):
        for x in range(13, 31):
            border = y in (29, 39) or x in (13, 30)
            if border and not (y == 29 and x in (21, 22)):
                g[y][x] = "C"
            else:
                g[y][x] = "M"
    # Vertical access from the service spine into utility.
    g[27][21] = "D"
    g[27][22] = "D"
    g[28][21] = "."
    g[28][22] = "."
    g[29][21] = "D"
    g[29][22] = "D"

    # East archive-access transition marker (next slice).
    for y in range(23, 26):
        for x in range(45, 47):
            g[y][x] = "E"
    g[24][46] = "X"

    # Seal the shell: the archive-access lane (cols 45-46) used to be flanked
    # by solid 'g' gravel, so its north/south edges were invisible walls.
    _seal_exterior_shell(g)

    return ["".join(row) for row in g]


def _generate_archives_map():
    """Build the third Mission 3 map: IPA Central Archives.

    Deliberately NOT a reskin of the Comms Wing. Comms is a horizontal
    service corridor (west airlock → relay → east exit). Archives is a
    vertical research stack:

        SOUTH  service elevator lobby (spawn, sealed shaft behind)
        CENTER multi-floor atrium with mezzanine pillars
        WEST   long parallel catalog stacks
        EAST   research cubicles / microfilm booths
        NW     Maru's dead-drop (hidden clerk office)
        NE     cold-storage vault with the Vostral pedestal
        NORTH  kill-order stairwell exit (opens after file)

    All doorways are SINGLE-TILE-THICK (one row/col of D only).
    """
    g = [["g" for _ in range(MAP_W)] for _ in range(MAP_H)]

    # World border.
    for x in range(MAP_W):
        g[0][x] = g[MAP_H - 1][x] = "C"
    for y in range(MAP_H):
        g[y][0] = g[y][MAP_W - 1] = "C"

    def fill_floor(x0, y0, x1, y1, floor="."):
        for y in range(y0, y1 + 1):
            for x in range(x0, x1 + 1):
                g[y][x] = floor

    def wall_rect(x0, y0, x1, y1):
        for y in range(y0, y1 + 1):
            for x in range(x0, x1 + 1):
                if y in (y0, y1) or x in (x0, x1):
                    g[y][x] = "C"

    def doorway_h(x0, x1, row):
        """Horizontal doorway opening on a wall row - single thickness."""
        for x in range(x0, x1 + 1):
            g[row][x] = "D"

    def doorway_v(col, y0, y1):
        """Vertical doorway opening on a wall column - single thickness."""
        for y in range(y0, y1 + 1):
            g[y][col] = "D"

    # ── SOUTH: elevator lobby ───────────────────────────────────────
    wall_rect(18, 38, 30, 45)
    fill_floor(19, 39, 29, 44, ".")
    doorway_h(23, 25, 38)          # north into atrium
    g[42][24] = "P"
    for x in (20, 21, 22, 26, 27, 28):
        g[44][x] = "S"             # sealed elevator panels

    # ── CENTER: vertical atrium ─────────────────────────────────────
    # Walls only on the long sides; north/south ends open into vestibule/lobby
    # via explicit doorways (not double-thick).
    for y in range(13, 38):
        g[y][20] = "C"
        g[y][28] = "C"
        for x in range(21, 28):
            g[y][x] = "."
    # Mezzanine pillars (cover).
    for y in (22, 30):
        for x in (22, 26):
            g[y][x] = "B"
    # South atrium already meets lobby doors at row 38.
    # North atrium meets vestibule doors at row 12 (set below).

    # ── WEST: catalog stacks ────────────────────────────────────────
    wall_rect(4, 18, 20, 36)
    fill_floor(5, 19, 19, 35, "L")
    doorway_v(20, 24, 25)          # into atrium (east wall of stacks)
    # Interior aisle walls.
    for y in range(20, 35):
        for x in (7, 10, 13, 16):
            if y not in (24, 25, 30, 31):
                g[y][x] = "C"
    # Cross-aisles.
    for x in range(5, 20):
        for y in (24, 25, 30, 31):
            if g[y][x] == "C" and x not in (4, 20):
                g[y][x] = "L"
    # Re-assert atrium connection floor east of doorway.
    g[24][21] = "."
    g[25][21] = "."

    # ── NW: Maru clerk office ───────────────────────────────────────
    wall_rect(6, 8, 16, 18)
    fill_floor(7, 9, 15, 17, "O")
    doorway_h(10, 11, 18)          # south into stacks
    # Floor immediately south of doorway (stacks side) - NOT a second door.
    g[19][10] = "L"
    g[19][11] = "L"

    # ── EAST: research cubicles ─────────────────────────────────────
    wall_rect(28, 18, 43, 36)
    fill_floor(29, 19, 42, 35, "O")
    doorway_v(28, 24, 25)          # into atrium
    g[24][27] = "."
    g[25][27] = "."
    # Cubicle partitions.
    for y in range(20, 34):
        if y in (24, 25, 29, 30):
            continue
        for x in (32, 36, 40):
            g[y][x] = "C"
    for x in range(30, 42):
        for y in (24, 25, 29, 30):
            if g[y][x] == "C" and x not in (28, 43):
                g[y][x] = "O"

    # ── NORTH-CENTER: vault vestibule ───────────────────────────────
    wall_rect(20, 6, 36, 12)
    fill_floor(21, 7, 35, 11, ".")
    doorway_h(23, 25, 12)          # south into atrium
    g[13][23] = "."
    g[13][24] = "."
    g[13][25] = "."
    # Vestibule east wall door into vault.
    doorway_v(36, 8, 9)

    # ── NE: Vostral cold vault ──────────────────────────────────────
    wall_rect(36, 4, 46, 14)
    fill_floor(37, 5, 45, 13, "O")
    doorway_v(36, 8, 9)            # west wall - vault doors (LOCKED in build)
    # Ensure BOTH door rows are D (wall_rect may have left only one open).
    g[8][36] = "D"
    g[9][36] = "D"
    # No bypass tiles around the door.
    g[7][36] = "C"
    g[10][36] = "C"
    g[8][37] = "O"
    g[9][37] = "O"
    # Frosted glass side panels.
    for y in range(6, 13):
        g[y][38] = "S"
        g[y][44] = "S"
    g[9][42] = "X"                 # pedestal

    # ── NORTH: kill-order stairwell ─────────────────────────────────
    wall_rect(22, 2, 28, 6)
    fill_floor(23, 3, 27, 5, "E")
    doorway_h(24, 25, 6)           # south into vestibule - EXIT (LOCKED)
    g[7][24] = "."
    g[7][25] = "."
    g[5][24] = "E"
    g[5][25] = "E"
    g[3][24] = "X"

    # Final pass: collapse 2×2 door blocks only (double-thick doorways).
    # Valid doorways are 1-deep strips: horizontal (same row, adjacent cols)
    # or vertical (same col, adjacent rows). A 2×2 block is always wrong.
    for y in range(1, MAP_H - 1):
        for x in range(1, MAP_W - 1):
            if (g[y][x] == "D" and g[y][x + 1] == "D"
                    and g[y + 1][x] == "D" and g[y + 1][x + 1] == "D"):
                g[y + 1][x] = "."
                g[y + 1][x + 1] = "."

    return ["".join(row) for row in g]


# ── Slice 5: Kill Order ground floor ────────────────────────────────
# Layout (40x40, same grammar as the other M3 maps):
#   NW      stairwell tower down from the Archives north door
#   WEST    service corridor (vertical spine, drains INTO the lobby -
#           no direct south exit: the dock run must cross the lobby pin)
#   CENTER  central lobby with pillar cover + SE mezzanine (marksman nest, 5c)
#   W-in    two lobby closets (pickups; east doors are breacher shortcuts, 5b)
#   EAST    service corridor
#   SOUTH   three insertion corridors (sweep routes, 5b) - all fed FROM the
#           lobby, so the stairwell rush can't bypass the crossfire
#   BOTTOM  loading dock (exfil van, holdout set-piece 5d)
def _generate_kill_order_map():
    """Build the fourth Mission 3 map: Kill Order ground floor.

    One floor below the Archives. Corridors are >=3 tiles wide so shield-point
    fireteams can form (Slice 5 plan §2); every 6-or-so corridor tiles has a
    cover pocket or doorway recess so the marksman pin (5c) stays fair.
    All doorways SINGLE-TILE-THICK except deliberate 2-tile junctions.
    """
    g = [["g" for _ in range(MAP_W)] for _ in range(MAP_H)]

    for x in range(MAP_W):
        g[0][x] = g[MAP_H - 1][x] = "C"
    for y in range(MAP_H):
        g[y][0] = g[y][MAP_W - 1] = "C"

    def fill_floor(x0, y0, x1, y1, floor="."):
        for y in range(y0, y1 + 1):
            for x in range(x0, x1 + 1):
                g[y][x] = floor

    def wall_rect(x0, y0, x1, y1):
        for y in range(y0, y1 + 1):
            for x in range(x0, x1 + 1):
                if y in (y0, y1) or x in (x0, x1):
                    g[y][x] = "C"

    def doorway_h(x0, x1, row):
        for x in range(x0, x1 + 1):
            g[row][x] = "D"

    def doorway_v(col, y0, y1):
        for y in range(y0, y1 + 1):
            g[y][col] = "D"

    # ── NW stairwell tower (entry from Archives) ──
    wall_rect(2, 1, 10, 8)
    fill_floor(3, 2, 9, 7, "E")
    g[3][6] = "P"

    # ── West service corridor ──
    wall_rect(2, 8, 8, 27)
    fill_floor(3, 9, 7, 26, ".")
    doorway_h(5, 6, 8)   # after both rings exist (shared wall row)

    # ── Central lobby ──
    wall_rect(8, 8, 29, 27)
    fill_floor(9, 9, 28, 26, "E")
    doorway_v(8, 12, 13)
    doorway_v(8, 20, 21)
    for bx, by in ((15, 13), (15, 20), (19, 16), (24, 12), (21, 24)):
        g[by][bx] = "B"          # pillar cover pockets

    # ── SE mezzanine (marksman nest in 5c; assaultable via its doorway) ──
    wall_rect(23, 21, 28, 26)
    fill_floor(24, 22, 27, 25, "E")
    doorway_h(25, 26, 21)

    # ── Lobby closets (pickups; east wall doors = breacher shortcuts) ──
    wall_rect(10, 11, 13, 14)
    fill_floor(11, 12, 12, 13, ".")
    doorway_h(11, 12, 11)
    g[12][13] = "D"              # locked, m3_ko_breach (5b)
    wall_rect(10, 19, 13, 22)
    fill_floor(11, 20, 12, 21, ".")
    doorway_h(11, 12, 22)
    g[20][13] = "D"              # locked, m3_ko_breach (5b)

    # ── East service corridor ──
    wall_rect(29, 8, 35, 27)
    fill_floor(30, 9, 34, 26, ".")
    doorway_v(29, 16, 17)

    # ── South insertion corridors (sweep routes, 5b) ──
    wall_rect(2, 28, 12, 32)
    fill_floor(3, 29, 11, 31, ".")
    wall_rect(14, 28, 25, 32)
    fill_floor(15, 29, 24, 31, ".")
    wall_rect(27, 28, 37, 32)
    fill_floor(28, 29, 36, 31, ".")
    doorway_h(9, 10, 27)         # lobby -> south 1 (west flank)
    doorway_h(19, 20, 27)        # lobby -> south 2 (center)
    doorway_h(31, 32, 27)        # east corridor -> south 3
    # The lobby/south junctions are DOUBLE walls (lobby bottom ring row 27 +
    # south top ring row 28): punch the second layer too, else the doors
    # open into solid rock (playability-audit finding 2026-09-19). The 2x2
    # collapse pass below turns these into clean 2-wide openings.
    # (No west-corridor -> south link: the stairwell rush must cross the
    # lobby pin - a direct west/south backdoor let players stroll to the
    # dock without ever meeting the sweep.)
    g[28][9] = "D"
    g[28][10] = "D"
    g[28][19] = "D"
    g[28][20] = "D"
    g[28][31] = "D"
    g[27][32] = "D"
    g[28][32] = "D"

    # ── Loading dock (exfil) ──
    wall_rect(2, 32, 37, 38)
    fill_floor(3, 33, 36, 37, "E")
    doorway_h(6, 7, 32)
    doorway_h(19, 20, 32)
    doorway_h(31, 32, 32)        # dock side door - locked, breach charge (5d)

    # Final pass: collapse 2x2 door blocks (double-thick doorways).
    for y in range(1, MAP_H - 1):
        for x in range(1, MAP_W - 1):
            if (g[y][x] == "D" and g[y][x + 1] == "D"
                    and g[y + 1][x] == "D" and g[y + 1][x + 1] == "D"):
                g[y + 1][x] = "."
                g[y + 1][x + 1] = "."

    return ["".join(row) for row in g]


MISSION3_KILL_ORDER_MAP = _levels.grid("m3.kill_order", _generate_kill_order_map())


# ── Slice 6: Broadcast Wing studio floor ─────────────────────────────
# Layout (32x32, compact studio wing):
#   N      entry vestibule (P, from exfil ride fade)
#   SPINE  cable corridor (vertical, 3 wide, runs S from vestibule)
#   W      green room (cover, med pickup)
#   E      control room (cover, ammo pickup)
#   GATE   studio door row (locked until wave 2 clears)
#   S      big studio floor (E tiles, cameras, uplink desk at far end)
def _generate_broadcast_map():
    """Build the fifth Mission 3 map: Broadcast Wing studio floor.

    32x32 compact layout. The spine forces a linear gauntlet: wave 1 in the
    corridor, wave 2 at the studio gate, holdout in the studio during upload.
    """
    W, H = BCAST_MAP_W, BCAST_MAP_H
    g = [["g" for _ in range(W)] for _ in range(H)]

    for x in range(W):
        g[0][x] = g[H - 1][x] = "C"
    for y in range(H):
        g[y][0] = g[y][W - 1] = "C"

    def fill_floor(x0, y0, x1, y1, floor="."):
        for y in range(y0, y1 + 1):
            for x in range(x0, x1 + 1):
                g[y][x] = floor

    def wall_rect(x0, y0, x1, y1):
        for y in range(y0, y1 + 1):
            for x in range(x0, x1 + 1):
                if y in (y0, y1) or x in (x0, x1):
                    g[y][x] = "C"

    def doorway_h(x0, x1, row):
        for x in range(x0, x1 + 1):
            g[row][x] = "D"

    # ── N entry vestibule ──
    wall_rect(12, 1, 19, 5)
    fill_floor(13, 2, 18, 4, ".")
    g[2][15] = "P"
    # Vestibule exit: 2-wide doorway in the row-5 border linking spawn to
    # the cable corridor (rows 6+). Without this the slice softlocks: the
    # wave-0 trigger needs py > 6 tiles and the player can never get there.
    doorway_h(15, 16, 5)

    # ── Cable corridor spine (rows 6-14, cols 14-17) ──
    fill_floor(14, 6, 17, 14, ".")

    # ── Green room (W, rows 6-10, cols 3-11) ──
    wall_rect(3, 6, 11, 10)
    fill_floor(4, 7, 10, 9, ".")
    # The north wall carries no hatch.  The band above it is solid rock, so a
    # doorway punched here opened onto out-of-bounds ground: the player saw a
    # door that looked like a way out and then walked into an invisible wall
    # one tile past it (removed with the Slice 6 boundary fix - the corridor
    # flanks and the studio apron are sealed by _seal_exterior_shell for the
    # same reason).
    g[8][6] = "B"
    g[8][9] = "B"
    # West link: side passage (cols 12-13) + door in the east wall joining
    # the green room to the corridor.
    fill_floor(12, 7, 13, 9, ".")
    g[8][11] = "D"

    # ── Control room (E, rows 6-10, cols 20-28) ──
    wall_rect(20, 6, 28, 10)
    fill_floor(21, 7, 27, 9, ".")
    # No north hatch here either - same solid-rock band as the green room
    # above, and the console divider below is what made the west leaf of the
    # old 2-wide hatch unreachable (audit: "door leads nowhere").
    # Micro-rooms: divider stubs split the floor into three console bays
    # (west 21-22, mid 24, east 26-27), each open at row 8 so Biribel and
    # Volkov's A* flow through. The upload PC lives in the mid bay (24,7).
    g[7][23] = "C"
    g[9][23] = "C"
    g[7][25] = "C"
    g[9][25] = "C"
    # Cover consoles sit in dead-end corners so no bay passage is blocked:
    # (21,8)->(22,8)->(23,8) west entry and (25,8)->(26,8) east entry stay open.
    g[9][21] = "B"
    g[9][27] = "B"
    # East link: mirror of the west passage joining control to the corridor.
    fill_floor(18, 7, 19, 9, ".")
    g[8][20] = "D"

    # ── Studio approach apron off the corridor (row 15) ──
    fill_floor(14, 15, 17, 15, ".")

    # ── Studio floor (rows 16-29, cols 3-28) ──
    wall_rect(3, 16, 28, 29)
    fill_floor(4, 17, 27, 28, "E")

    # ── Studio door gate (studio north wall, row 16) ──
    # Punched AFTER wall_rect (which would clobber it) so the locked doors
    # open onto studio floor, not rock.
    doorway_h(14, 17, 16)

    # Studio cover blocks
    for bx, by in ((12, 19), (19, 19), (11, 24), (20, 24), (24, 28), (27, 28)):
        g[by][bx] = "B"

    # ── South suite: the PC lives in the SE room, not out in the open ──
    #   west store  : cols 4-7,  rows 23-28, one door at (8,26)
    #   east suite  : cols 24-27, rows 21-28, split into two micro-rooms
    #                   antechamber  rows 21-24, door from the floor at (23,23)
    #                   PC vault     rows 26-28, door at (25,25), PC at (25,27)
    #   centre lane : cols 9-22 stays open from the gate down to row 28, so the
    #                 arena is never bisected - the first attempt ran walls
    #                 along cols 12/18 and turned the whole studio into a
    #                 corridor with one chokepoint.
    for r in range(22, 29):
        g[r][8] = "C"
    for c in range(4, 8):
        g[22][c] = "C"
    g[26][8] = "D"

    # East suite shell: west wall (col 23) and north wall (row 20).
    for r in range(21, 29):
        g[r][23] = "C"
    for c in range(24, 28):
        g[20][c] = "C"
    g[23][23] = "D"          # studio floor -> antechamber
    # Cross wall: antechamber -> PC vault, with the vault's own door.
    for c in range(24, 28):
        g[25][c] = "C"
    g[25][25] = "D"

    # Final pass: collapse 2x2 door blocks
    for y in range(1, H - 1):
        for x in range(1, W - 1):
            if (g[y][x] == "D" and g[y][x + 1] == "D"
                    and g[y + 1][x] == "D" and g[y + 1][x + 1] == "D"):
                g[y + 1][x] = "."
                g[y + 1][x + 1] = "."

    # Final pass: seal the shell.  Every 'g' in this map is collision-solid,
    # so the corridor flanks (cols 13/18), the studio apron, and the two
    # decorative north hatches used to show open gravel the player could not
    # walk into.  See _seal_exterior_shell.
    _seal_exterior_shell(g)

    return ["".join(row) for row in g]


MISSION3_BROADCAST_MAP = _levels.grid("m3.broadcast", _generate_broadcast_map())

MISSION3_CELL_MAP = _levels.grid("m3.cell", _generate_map())
MISSION3_COMMS_MAP = _levels.grid("m3.comms", _generate_comms_map())
MISSION3_ARCHIVES_MAP = _levels.grid("m3.archives", _generate_archives_map())
MISSION3_MAP = MISSION3_CELL_MAP


def _live_map_dims():
    """(width, height) of the currently-bound MISSION3_MAP, in tiles.

    Four of the five Mission 3 maps are 48x48 but the Broadcast Wing map is
    32x32. Render loops and camera clamps must derive their bounds from this,
    never from the MAP_W/MAP_H constants, or the broadcast slice reads past
    the end of a row (IndexError: string index out of range).
    """
    grid = MISSION3_MAP
    h = len(grid)
    w = len(grid[0]) if h else 0
    return w, h

# Module-level draw/update scratch.
_last_keys = None
_objective = "Survive the interrogation."
_radio_marks = set()
