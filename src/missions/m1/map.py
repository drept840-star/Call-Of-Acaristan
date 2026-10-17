
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

M1_W, M1_H = 28, 23

# -- Split layer 1: entity markers (char, col, row) ------------------
# Positions are byte-identical to the legacy hand-drawn strings.
M1_PLAYER_SPAWN = ("P", 3, 2)
M1_ENEMY_SPAWNS = [
    ("E", 22, 5),
    ("E", 7, 7),
    ("E", 16, 7),
    ("E", 11, 11),
    ("E", 19, 12),
    ("E", 5, 13),
    ("E", 15, 13),
]
M1_COMMANDER_SPAWN = ("K", 10, 14)
M1_VOLKOV_SPAWN = ("V", 15, 17)
M1_NOTEBOOK_SPAWN = ("N", 15, 18)
M1_EXFIL_SPAWN = ("X", 22, 21)

M1_SPAWNS = (
    [M1_PLAYER_SPAWN]
    + M1_ENEMY_SPAWNS
    + [M1_COMMANDER_SPAWN, M1_VOLKOV_SPAWN, M1_NOTEBOOK_SPAWN, M1_EXFIL_SPAWN]
)


def _build_m1_structure():
    """Collision/visual layer: warehouse in three horizontal bands.

    Rows 0-10   north stockroom  (C shell, 2x2 CC shelving blocks)
    Rows 11-15  middle warehouse (W shell, gate door row 15 col 14)
    Rows 16-22  south yard + exfil (W shell, bay doors row 19 cols 14-16)
    """
    b = MapBuilder(M1_W, M1_H, fill=".")

    # North stockroom shell: C walls, door punched at col 8 of row 10.
    b.room(0, 0, M1_W, 11, wall="C", floor=".", doors=[(8, 10)])
    # Shelving blocks (2x2 CC pillars at cols 5-6 and 15-16, rows 4-5).
    b.block(5, 4)
    b.block(15, 4)

    # Middle warehouse shell rows 11-15 (W walls, gate door row 15 col 14).
    b.rect(0, 11, 1, 4, "W")          # west wall rows 11-14
    b.rect(M1_W - 1, 11, 1, 4, "W")   # east wall rows 11-14
    b.h_wall(0, 15, M1_W, wall="W", doors=(14,))

    # South shell rows 16-19 (W walls, triple bay doors row 19).
    b.rect(0, 16, 1, 3, "W")          # west wall rows 16-18
    b.rect(M1_W - 1, 16, 1, 3, "W")   # east wall rows 16-18
    b.h_wall(0, 19, M1_W, wall="W", doors=(14, 15, 16))

    # Exfil corridor rows 20-22: open hallway with C side walls, solid cap.
    # Legacy row 20/21 are "C..........................C" (X at 22,21).
    b.rect(0, 20, 1, 2, "C")
    b.rect(M1_W - 1, 20, 1, 2, "C")
    b.rect(0, 22, M1_W, 1, "C")

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
