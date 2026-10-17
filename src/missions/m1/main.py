"""Split from mission.py - see mission.py (shim) for the map."""
"""Mission 1B gameplay: warehouse infiltrate/firefight/escape."""
import math
from engine.core import LEGACY_RNG as _rng_legacy  # RPE6 R6: named 'legacy' rng stream
import time
import pygame
from core.config import (SCENE_BOT, SCENE_TOP, TILE_SIZE, WIDTH)
from entities.art_cache import get_blood_decal, get_glow, get_shadow
from entities.enemy_ai import Enemy, enemy_hear_shot
from core.state import STATE
from core import save_system
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

from missions.m1.map import mission1_map, MAP_W, MAP_H
from engine.core import now_ms as _now_ms  # RPE6 B-001 timebase

_walk_footstep_timer = 0
rain_drops = [
    (
        _rng_legacy.randint(0, WIDTH),
        _rng_legacy.randint(SCENE_TOP, SCENE_BOT),
        _rng_legacy.randint(10, 20),
    )
    for _ in range(200)
]

def start_mission(preserve_timer=False):
    STATE.active_mission = "MISSION1"
    STATE.active_mission_id = "MISSION_1"
    STATE.active_mission_title = "Black Notebook"
    STATE.active_mission_operation = "WAREHOUSE RAID - BLACK NOTEBOOK"
    STATE.active_mission_outcome = "Target escaped  ·  Notebook recovered  ·  Questions remain"
    STATE.active_mission_quote_attr = "Vasile, after a long pause:"
    STATE.active_mission_quote = '"Bring it straight to me. Don\'t read it."'
    save_system.set_slot_progress("m1")
    STATE.player_dead = False
    STATE.death_timer = 0
    STATE.request_death_screen = False
    STATE.request_escape_cutscene = False
    STATE.notebook_collected = False
    STATE.exfil_reached = False
    STATE.mission_phase = "infiltrate"
    STATE.firefight_triggered = False
    STATE.volkov_escape_timer = 0
    STATE.mag_spawn_done = False
    STATE.radio_chatter_stage = 0
    STATE.volkov_escape_pos = None
    STATE.commander_escape_pos = None
    STATE.volkov_escaped = False
    STATE.commander_escaped = False
    STATE.breach_markers = []
    STATE.show_notebook_inspect = False
    STATE.notebook_inspect_timer = 0
    STATE.request_notebook_inspect = False
    STATE.show_minimap = True
    STATE.minimap = MiniMap(mission1_map, palette="m1")
    STATE.hostiles_killed = 0
    STATE.shots_fired = 0
    STATE.shots_hit = 0
    if not preserve_timer or not STATE.mission_start_time:
        STATE.mission_start_time = _now_ms()
    STATE.mission_end_time = 0
    STATE.player = None
    STATE.enemies = []
    STATE.bullets = []
    STATE.walls = []
    STATE.particles = []
    STATE.casings = []
    STATE.doors = []
    STATE.warehouse_walls_set = set()
    STATE.melee_active = False
    STATE.melee_timer = 0
    STATE.melee_hit_done = False
    STATE.camera_x = STATE.camera_y = 0
    STATE.cam_kick_x = STATE.cam_kick_y = 0.0
    STATE.camera_initialized = False  # forces camera.update_camera to snap on first frame
    STATE.screen_shake = 0
    STATE.blood_decals = []
    STATE.muzzle_flash_timer = 0
    STATE.ammo_in_mag = 12
    STATE.spare_mags = 3 + walking_sim.warehouse_mag_bonus
    STATE.gc_flash_timer = 0
    STATE.shot_cooldown = 0
    STATE.is_reloading = False
    STATE.reload_timer = 0
    STATE.floating_texts = []
    STATE.pickups = []
    STATE.volkov_pos = None
    STATE.commander_pos = None
    STATE.NOTEBOOK_POS = None
    STATE.EXFIL_POS = None
    STATE.has_keycard = False
    STATE.gate_hacking = False
    STATE.gate_hack_progress = 0.0
    STATE.safe_keypad_active = False
    STATE.safe_keypad_code = ""
    STATE.safe_keypad_wrong_attempts = 0
    STATE.truck_hotwiring = False
    STATE.truck_hotwire_progress = 0.0
    STATE.escape_reinforcement_timer = 0
    STATE.escape_reinforcement_count = 0
    STATE.active_read_note = None
    STATE.stealth_failed = False
    STATE.quiet_entry = True
    STATE.volkov_sighting_done = False
    STATE.volkov_sighting_timer = 0
    STATE.volkov_sighting_played = False
    STATE.volkov_sighted = False
    STATE.volkov_visible = False
    STATE.volkov_display_pos = None
    STATE.civilian_payoff_done = False
    STATE.breach_stage = 0
    STATE.breach_stage_timer = 0
    STATE.hotwire_radio_said = False
    STATE._footstep_timer = 0
    STATE.player_bottles = 2
    STATE.thrown_bottles = []
    STATE.molotov_fires = []
    STATE.fire_zones = []
    STATE.floating_texts.append([
        7 * TILE_SIZE + 32,
        3 * TILE_SIZE + 32,
        "[G] or RIGHT-CLICK to throw a molotov - burns an area",
        (140, 200, 150),
        360,
    ])
    STATE.desks = [
        {
            "x": 13 * TILE_SIZE + 32,
            "y": 12 * TILE_SIZE + 32,
            "clue": (
                "GUARD ROTATION MEMO:\n"
                "Commander holds the gate keycard.\n"
                "Use last three digits only for safe access.\n"
                "Destroy after reading."
            ),
            "read": False,
        },
        {
            "x": 20 * TILE_SIZE + 32,
            "y": 12 * TILE_SIZE + 32,
            "clue": (
                "LOGISTICS LOG:\n"
                "Shipment #7742 cleared by IPA command.\n"
                "Safe codes follow last three digits\n"
                "of primary shipment."
            ),
            "read": False,
        },
        {
            "x": 6 * TILE_SIZE + 32,
            "y": 17 * TILE_SIZE + 32,
            "clue": (
                "OFFICER MEMO:\n"
                "Codes rotated this month.\n"
                "Active code: last 3 of shipment #7742.\n"
                "Do NOT write the full code."
            ),
            "read": False,
        },
        {
            "x": 22 * TILE_SIZE + 32,
            "y": 18 * TILE_SIZE + 32,
            "clue": "__CRUMPLED_SAFE_SCRAP__",
            "read": False,
        },
        # Optional lore desk (inner warehouse corner)
        {
            "x": 24 * TILE_SIZE + 32,
            "y": 16 * TILE_SIZE + 32,
            "clue": (
                "WEAPON SHIPMENT MANIFEST\n"
                "FT-7742 / FT-7743 / FT-7744\n"
                "Recipient: IPA Regional Command\n"
                "KRAP ref #8841 - filed 6 months ago.\n"
                "Courier: S. Volkov."
            ),
            "read": False,
            "optional": True,
        },
    ]
    for row_idx, row in enumerate(mission1_map):
        for col_idx, tile in enumerate(row):
            x, y = col_idx * TILE_SIZE, row_idx * TILE_SIZE
            if tile == "W":
                STATE.walls.append(pygame.Rect(x, y, TILE_SIZE, TILE_SIZE))
                STATE.warehouse_walls_set.add((col_idx, row_idx))
            elif tile == "C":
                STATE.walls.append(pygame.Rect(x, y, TILE_SIZE, TILE_SIZE))
            elif tile == "D":
                is_bay = row_idx == 19
                is_gate = row_idx == 15
                new_door = Door(x, y, is_bay)
                new_door.is_gate = is_gate
                new_door.locked = is_gate
                STATE.doors.append(new_door)
            elif tile == "P":
                STATE.player = Player(x + 16, y + 16, max_hp=100 + walking_sim.warehouse_hp_bonus)
            elif tile == "E":
                STATE.enemies.append(Enemy(x + 16, y + 16))
            elif tile == "V":
                STATE.volkov_pos = (x + 32, y + 32)
            elif tile == "K":
                commander_enemy = Enemy(x + 16, y + 16)
                commander_enemy.hp = 250
                commander_enemy.is_commander = True
                commander_enemy.speed = 2.2
                STATE.enemies.append(commander_enemy)
                STATE.commander_pos = None
    for e in STATE.enemies:
        col = e.rect.centerx // TILE_SIZE
        row = e.rect.centery // TILE_SIZE
        if row < 11:
            e.state = "PATROL"
            e.speed = 1.5
            if col == 6:
                e.patrol_points = [
                    (6 * TILE_SIZE + 32, 7 * TILE_SIZE + 32),
                    (12 * TILE_SIZE + 32, 7 * TILE_SIZE + 32),
                ]
            elif col == 15:
                e.patrol_points = [
                    (15 * TILE_SIZE + 32, 7 * TILE_SIZE + 32),
                    (15 * TILE_SIZE + 32, 3 * TILE_SIZE + 32),
                ]
            elif col == 22:
                e.patrol_points = [
                    (22 * TILE_SIZE + 32, 5 * TILE_SIZE + 32),
                    (22 * TILE_SIZE + 32, 9 * TILE_SIZE + 32),
                ]
        elif 11 <= row <= 14:
            e.state = "PATROL"
            e.speed = 1.5
            if e.is_commander:
                e.patrol_points = [
                    (9 * TILE_SIZE + 32, 18 * TILE_SIZE + 32),
                    (14 * TILE_SIZE + 32, 18 * TILE_SIZE + 32),
                    (14 * TILE_SIZE + 32, 17 * TILE_SIZE + 32),
                ]
            elif col <= 12:
                e.patrol_points = [
                    (e.rect.centerx, e.rect.centery),
                    (e.rect.centerx + 5 * TILE_SIZE, e.rect.centery),
                ]
            else:
                e.patrol_points = [
                    (e.rect.centerx, e.rect.centery),
                    (e.rect.centerx - 5 * TILE_SIZE, e.rect.centery),
                ]
        elif 16 <= row <= 18:
            e.state = "PATROL"
            e.speed = 1.5
            e.patrol_points = [
                (e.rect.centerx, e.rect.centery),
                (e.rect.centerx + 4 * TILE_SIZE, e.rect.centery),
            ]
    miniboss = Enemy(10 * TILE_SIZE + 16, 17 * TILE_SIZE + 16)
    miniboss.hp = 400
    miniboss.is_miniboss = True
    miniboss.speed = 1.8
    STATE.enemies.append(miniboss)
    STATE.NOTEBOOK_POS = None
    STATE.EXFIL_POS = None
def _init_mission_specials():
    STATE.NOTEBOOK_POS = None
    STATE.EXFIL_POS = None
    for row_idx, row in enumerate(mission1_map):
        for col_idx, tile in enumerate(row):
            x, y = col_idx * TILE_SIZE, row_idx * TILE_SIZE
            if tile == "N":
                STATE.NOTEBOOK_POS = (x + 32, y + 32)
            elif tile == "X":
                STATE.EXFIL_POS = (x + 32, y + 32)
def _trigger_civilian_payoff():
    """One quiet payoff line based on walking sim choices."""
    kid_helped = any(
        n.get("has_given") and n.get("reward") == "kevlar"
        for n in walking_sim.walk_npcs
    )
    woman_helped = any(
        n.get("has_given") and n.get("reward") == "intel"
        for n in walking_sim.walk_npcs
    )
    if kid_helped:
        trigger_radio_chatter(
            'VASILE: "Where\'d you get the plate? Keep it on."'
        )
    elif woman_helped:
        trigger_radio_chatter(
            'VASILE: "If that civilian was right, the code\'s already in your head."'
        )
    else:
        trigger_radio_chatter('VASILE: "No local help. Search the desks."')
