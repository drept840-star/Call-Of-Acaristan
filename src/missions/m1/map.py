
"""Mission 1 map - authored with core.MapBuilder, baked to list[str].

Authoring layers (edit these, not the baked strings):
  M1_STRUCTURE_MAP  collision + visuals only (C/W/D/.), built by
                    _build_m1_structure() with readable rect/room calls.
  M1_SPAWNS         entity markers as (char, col, row):
                    P player, E enemy, K commander, V volkov,
                    N notebook, X exfil.

Runtime contract (unchanged):
  mission1_map      baked ``list[str]`` with spawns overlaid, so every
                    existing consumer (main.py world build, draw.py,
                    MiniMap, level_editor, tools/*) works untouched.

To redesign the layout: change the builder calls, keep M1_SPAWNS where
they are (or move them as plain tuples - no more counting chars inside
string literals to find the 'P' you deleted).
"""
import math
import time
import pygame
from core.config import (TILE_SIZE)
from core.mapbuilder import MapBuilder
import game.levels as _levels  # RPE6 P7: level data access
from entities.art_cache import get_blood_decal, get_glow, get_shadow
from entities.enemy_ai import Enemy, enemy_hear_shot
from core.state import STATE
from ui.hud import MiniMap, draw_objective_panel, draw_pinned_radio
from entities.player import Player, resolve_melee
from core.interactions import (
    Door,
    trigger_alarm_early,
    trigger_radio_chatter,
)
from entities.weapons import (
    spawn_molotov_fire as _spawn_molotov_fire,
    _wall_blocks_line,
    MOLOTOV_RADIUS,
    MOLOTOV_DURATION,
    MOLOTOV_ENEMY_DAMAGE,
    MOLOTOV_PLAYER_DAMAGE,
)
from cutscenes import draw_volkov, draw_commander, draw_biribel
from missions import walking_sim
from fx import effects
from core.camera import update_camera, reset_camera_state, collide_bullet_walls, draw_bullets

M1_W, M1_H = 28, 33

# Row anchors. Rows 0-9 are the street band; row 10 is the stockroom north wall.
M1_STREET_ROW = 10
M1_STOCK_DOOR_ROW = 20
M1_GATE_ROW = 25
M1_BAY_ROW = 29

# -- Split layer 1: entity markers (char, col, row) ------------------
M1_PLAYER_SPAWN = ("P", 1, 1)
M1_STREET_ENEMY_SPAWNS = [
    ("E", 19, 4),
    ("E", 23, 8),
    ("E", 25, 8),
]
M1_ENEMY_SPAWNS = [
    ("E", 22, 15),
    ("E", 7, 17),
    ("E", 16, 17),
    ("E", 11, 21),
    ("E", 19, 22),
    ("E", 5, 23),
    ("E", 15, 23),
]
M1_COMMANDER_SPAWN = ("K", 10, 24)
M1_VOLKOV_SPAWN = ("V", 15, 27)
M1_NOTEBOOK_SPAWN = ("N", 15, 28)
M1_EXFIL_SPAWN = ("X", 22, 31)

M1_SPAWNS = (
    [M1_PLAYER_SPAWN]
    + M1_STREET_ENEMY_SPAWNS
    + M1_ENEMY_SPAWNS
    + [M1_COMMANDER_SPAWN, M1_VOLKOV_SPAWN, M1_NOTEBOOK_SPAWN, M1_EXFIL_SPAWN]
)

# Level-data extras, read by tools/ae_level_export.py (pure data).
M1_TRIGGERS = [
    {"id": "street_exit", "kind": "zone", "rect": [0, 10, 28, 2]},
    {"id": "volkov_standoff", "kind": "zone", "rect": [11, 26, 9, 3]},
    {"id": "exfil_van", "kind": "zone", "rect": [18, 30, 9, 2]},
]
M1_LIGHTS = [
    {"id": "street_lamp_a", "kind": "street_lamp", "tile": [6, 2], "radius": 150, "color": [190, 210, 255]},
    {"id": "street_lamp_b", "kind": "street_lamp", "tile": [15, 2], "radius": 150, "color": [190, 210, 255]},
    {"id": "shutter_floodlight", "kind": "floodlight", "tile": [23, 9], "radius": 120, "color": [225, 235, 255]},
]

# Street band rows 0-9 and the stockroom's north wall row 10. Glyphs: C wall,
# L lamp, T truck, f fence, r rubble, F fire barrel, d side door, S shutter.
# P and E are spawn markers, overlaid from M1_SPAWNS (floor in the structure).
_M1_STREET_ROWS = (
    "CCCCCCCCCCCCCCCCCCCCCCCCCCCC",
    "CP.........................C",
    "C.....L........L...........C",
    "C.......TTT................C",
    "C.......TTT........E.......C",
    "C....r.....................C",
    "C.....................TTTT.C",
    "Cffffff.ffffffffffffff.ffffC",
    "C......................E.E.C",
    "C...........r..........F...C",
    "CCCdCCCCCCCCCCCCCCCCCCSSSCCC",
)


def _build_m1_structure():
    """Collision/visual layer, top to bottom.

    Rows 0-9    street band (C outer wall, props, open apron)
    Rows 10-20  north stockroom (C shell, 2x2 CC shelving, door row 20 col 8)
    Rows 21-25  middle warehouse (W shell, gate door row 25 col 14)
    Rows 26-29  south yard (W shell, bay doors row 29 cols 14-16)
    Rows 30-32  exfil corridor (C side walls, solid cap)
    """
    b = MapBuilder(M1_W, M1_H, fill=".")

    # Stockroom shell rows 10-20: C walls, south door at relative (8, 10).
    b.room(0, M1_STREET_ROW, M1_W, 11, wall="C", floor=".", doors=[(8, 10)])
    for r, line in enumerate(_M1_STREET_ROWS):
        for c, ch in enumerate(line):
            b.set(c, r, "." if ch in "PE" else ch)
    # Shelving blocks (2x2 CC pillars at cols 5-6 and 15-16, rows 14-15).
    b.block(5, 14)
    b.block(15, 14)

    # Middle warehouse shell rows 21-25 (W walls, gate door row 25 col 14).
    b.rect(0, 21, 1, 4, "W")          # west wall rows 21-24
    b.rect(M1_W - 1, 21, 1, 4, "W")   # east wall rows 21-24
    b.h_wall(0, M1_GATE_ROW, M1_W, wall="W", doors=(14,))

    # South shell rows 26-29 (W walls, triple bay doors row 29).
    b.rect(0, 26, 1, 3, "W")          # west wall rows 26-28
    b.rect(M1_W - 1, 26, 1, 3, "W")   # east wall rows 26-28
    b.h_wall(0, M1_BAY_ROW, M1_W, wall="W", doors=(14, 15, 16))

    # Exfil corridor rows 30-32: open hallway with C side walls, solid cap.
    b.rect(0, 30, 1, 2, "C")
    b.rect(M1_W - 1, 30, 1, 2, "C")
    b.rect(0, 32, M1_W, 1, "C")

    return b


_M1_BUILDER = _build_m1_structure()

# Collision-only layer (no entities) - for audits / minimap variants.
M1_STRUCTURE_MAP = _M1_BUILDER.to_strings()

# Runtime layer: structure + spawns. This is what the game loads.
mission1_map = _levels.grid("m1.warehouse", _M1_BUILDER.with_spawns(M1_SPAWNS).to_strings())  # RPE6 P7: data by default

# Mission 1 map dimensions in tiles. Used by camera.update_camera() for the
# map-bounds clamp so the camera cannot run past the warehouse edge.
MAP_W = len(mission1_map[0].strip('"')) if mission1_map else 0
MAP_H = len(mission1_map)

def _tc(col, row):
    """Tile center in world pixels."""
    return col * TILE_SIZE + TILE_SIZE // 2, row * TILE_SIZE + TILE_SIZE // 2
def _lerp(a, b, t):
    t = max(0.0, min(1.0, t))
    return a + (b - a) * t
