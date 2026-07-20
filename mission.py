# ------------------------------------------------------------
# mission.py
# ------------------------------------------------------------


"""Mission 1B gameplay: warehouse infiltrate/firefight/escape."""
import math
import random
import time
import pygame
from config import *
from art_cache import get_blood_decal, get_glow, get_shadow
from enemy_ai import Enemy, enemy_hear_shot
from state import STATE
from ui_hud import MiniMap, draw_objective_panel, draw_pinned_radio
from player import Player, resolve_melee
from interactions import (
    Door,
    trigger_alarm_early,
    trigger_radio_chatter,
)
from weapons import (
    spawn_molotov_fire as _spawn_molotov_fire,
    _wall_blocks_line,
    MOLOTOV_RADIUS,
    MOLOTOV_DURATION,
    MOLOTOV_ENEMY_DAMAGE,
    MOLOTOV_PLAYER_DAMAGE,
)
from cutscenes import draw_volkov, draw_commander, draw_biribel
import walking_sim
import effects
from camera import update_camera, reset_camera_state, collide_bullet_walls, draw_bullets
# ─────────────────────────────────────────────
# MISSION 1 PART B: "Black Notebook"
# ─────────────────────────────────────────────
mission1_map = [
    "CCCCCCCCCCCCCCCCCCCCCCCCCCCC",
    "C..........................C",
    "C..P.......................C",
    "C..........................C",
    "C....CC........CC..........C",
    "C....CC........CC.....E....C",
    "C..........................C",
    "C......E........E..........C",
    "C..........................C",
    "C..........................C",
    "CCCCCCCCDCCCCCCCCCCCCCCCCCCC",
    "W..........E...............W",
    "W..................E.......W",
    "W....E.........E...........W",
    "W.........K................W",
    "WWWWWWWWWWWWWWDWWWWWWWWWWWWW",
    "W..........................W",
    "W..............V...........W",
    "W..............N...........W",
    "WWWWWWWWWWWWWWDDDWWWWWWWWWWW",
    "C..........................C",
    "C.....................X....C",
    "CCCCCCCCCCCCCCCCCCCCCCCCCCCC",
]
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
# ─────────────────────────────────────────────
# GAME STATE
# ─────────────────────────────────────────────
_walk_footstep_timer = 0
rain_drops = [
    (
        random.randint(0, WIDTH),
        random.randint(SCENE_TOP, SCENE_BOT),
        random.randint(10, 20),
    )
    for _ in range(200)
]
def start_mission(preserve_timer=False):
    STATE.active_mission = "MISSION1"
    STATE.active_mission_id = "MISSION_1"
    STATE.active_mission_title = "Black Notebook"
    STATE.active_mission_operation = "WAREHOUSE RAID — BLACK NOTEBOOK"
    STATE.active_mission_outcome = "Target escaped  ·  Notebook recovered  ·  Questions remain"
    STATE.active_mission_quote_attr = "Vasile, after a long pause:"
    STATE.active_mission_quote = '"Bring it straight to me. Don\'t read it."'
    STATE.player_dead = False
    STATE.death_timer = 0
    STATE.request_death_screen = False
    STATE.request_mission_complete = False
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
    STATE.minimap = MiniMap(mission1_map)
    STATE.hostiles_killed = 0
    STATE.shots_fired = 0
    STATE.shots_hit = 0
    if not preserve_timer or not STATE.mission_start_time:
        STATE.mission_start_time = pygame.time.get_ticks()
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
        "[G] or RIGHT-CLICK to throw a molotov \u2014 burns an area",
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
                "KRAP ref #8841 \u2014 filed 6 months ago.\n"
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
            if getattr(e, "is_commander", False):
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
HOTWIRE_WIRES = [
    ("RED",    (215, 55, 45),   "POWER FEED"),
    ("YELLOW", (225, 190, 55),  "BATTERY RETURN"),
    ("BLUE",   (60, 130, 220),  "IGNITION BUS"),
    ("GREEN",  (70, 185, 95),   "COIL WAKE"),
    ("BLACK",  (35, 35, 38),    "GROUND"),
    ("WHITE",  (220, 220, 205), "STARTER"),
]
HOTWIRE_TARGET_PAIRS = {
    frozenset(("RED", "YELLOW")): "POWER",
    frozenset(("BLUE", "GREEN")): "IGNITION",
    frozenset(("BLACK", "WHITE")): "STARTER",
}
def _hotwire_wire_nodes():
    """Screen-space wire end nodes for the hotwire panel."""
    panel_w, panel_h = 640, 410
    panel_x = WIDTH // 2 - panel_w // 2
    panel_y = HEIGHT // 2 - panel_h // 2
    left_x = panel_x + 112
    right_x = panel_x + panel_w - 112
    ys = [panel_y + 118, panel_y + 206, panel_y + 294]
    # Scrambled layout: correct pairs are intentionally NOT side-by-side.
    return {
        "RED":    {"pos": (left_x, ys[0]),  "side": "L", "color": (215, 55, 45),   "label": "POWER FEED"},
        "BLACK":  {"pos": (left_x, ys[1]),  "side": "L", "color": (35, 35, 38),    "label": "GROUND"},
        "BLUE":   {"pos": (left_x, ys[2]),  "side": "L", "color": (60, 130, 220),  "label": "IGNITION BUS"},
        "GREEN":  {"pos": (right_x, ys[0]), "side": "R", "color": (70, 185, 95),   "label": "COIL WAKE"},
        "WHITE":  {"pos": (right_x, ys[1]), "side": "R", "color": (220, 220, 205), "label": "STARTER"},
        "YELLOW": {"pos": (right_x, ys[2]), "side": "R", "color": (225, 190, 55),  "label": "BATTERY RETURN"},
    }
def _reset_hotwire_minigame():
    STATE.hotwire_stage = 0
    STATE.hotwire_selected_wire = None
    STATE.hotwire_connections = []
    STATE.hotwire_wrong_attempts = 0
    STATE.hotwire_spark_timer = 0
    STATE.hotwire_fail_flash = 0
    STATE.hotwire_panel_timer = 0
    STATE.hotwire_message = "Panel open. Read the wire labels carefully."
def handle_hotwire_press():
    """Legacy E handler. The new hotwire is mouse-driven, so E just toggles a hint."""
    if not STATE.truck_hotwiring:
        return
    STATE.hotwire_message = "Click one wire, then the matching wire. ESC pauses."
    audio.play("menu_hover", volume=0.25)
def handle_hotwire_click(pos):
    if not STATE.truck_hotwiring:
        return
    if getattr(STATE, "hotwire_panel_timer", 0) < 28:
        return
    nodes = _hotwire_wire_nodes()
    clicked = None
    for name, data in nodes.items():
        x, y = data["pos"]
        if math.hypot(pos[0] - x, pos[1] - y) <= 24:
            clicked = name
            break
    if clicked is None:
        return
    # Already connected wires cannot be re-used.
    used = {w for pair in STATE.hotwire_connections for w in pair}
    if clicked in used:
        STATE.hotwire_message = f"{clicked} already bridged"
        audio.play("empty_click", volume=0.25)
        return
    if STATE.hotwire_selected_wire is None:
        STATE.hotwire_selected_wire = clicked
        STATE.hotwire_message = f"Selected {clicked}. Choose matching wire."
        audio.play("menu_click", volume=0.35)
        return
    first = STATE.hotwire_selected_wire
    if clicked == first:
        STATE.hotwire_selected_wire = None
        STATE.hotwire_message = "Selection cleared"
        audio.play("menu_hover", volume=0.22)
        return
    pair = frozenset((first, clicked))
    if pair in HOTWIRE_TARGET_PAIRS:
        # Store as a stable tuple for drawing.
        STATE.hotwire_connections.append(tuple(sorted(pair)))
        STATE.hotwire_stage = len(STATE.hotwire_connections)
        label = HOTWIRE_TARGET_PAIRS[pair]
        STATE.hotwire_message = f"{label} CIRCUIT LIVE"
        STATE.hotwire_selected_wire = None
        STATE.hotwire_spark_timer = 10
        audio.play("pickup", volume=0.45)
        audio.play("terminal_glitch", volume=0.12)
        STATE.floating_texts.append([
            STATE.player.rect.centerx, STATE.player.rect.centery - 50,
            f"{label} CONNECTED", C_TERMINAL, 45,
        ])
        if STATE.hotwire_stage >= 3:
            STATE.hotwire_message = "ENGINE STARTED"
            audio.play("door_open", volume=0.55)
            audio.schedule(8, "pickup", volume=0.45)
            STATE.exfil_reached = True
            STATE.request_escape_cutscene = True
            STATE.truck_hotwiring = False
    else:
        STATE.hotwire_wrong_attempts += 1
        STATE.hotwire_fail_flash = 18
        STATE.hotwire_spark_timer = 22
        STATE.hotwire_selected_wire = None
        STATE.hotwire_message = "SHORT! Wrong wire pair."
        audio.play("empty_click", volume=0.65)
        audio.play("terminal_glitch", volume=0.22)
        STATE.screen_shake = max(STATE.screen_shake, 6)
        if STATE.hotwire_connections and STATE.hotwire_wrong_attempts % 3 == 0:
            STATE.hotwire_connections.pop()
            STATE.hotwire_stage = len(STATE.hotwire_connections)
            STATE.hotwire_message = "SHORT! A bridge burned loose."
        STATE.floating_texts.append([
            STATE.player.rect.centerx, STATE.player.rect.centery - 50,
            "SHORTED OUT!", (220, 80, 60), 45,
        ])
def debug_jump_to_exfil():
    """Developer helper: jump straight to escape truck with hostiles cleared."""
    if STATE.player is None:
        return
    if STATE.EXFIL_POS is None or STATE.NOTEBOOK_POS is None:
        _init_mission_specials()
    STATE.notebook_collected = True
    STATE.mission_phase = "escape"
    STATE.firefight_triggered = True
    STATE.enemies.clear()
    STATE.bullets.clear()
    STATE.truck_hotwiring = False
    STATE.hotwire_stage = 0
    STATE.hotwire_selected_wire = None
    STATE.hotwire_connections = []
    STATE.hotwire_wrong_attempts = 0
    STATE.hotwire_panel_timer = 0
    if STATE.EXFIL_POS:
        STATE.player.rect.centerx = int(STATE.EXFIL_POS[0] - 42)
        STATE.player.rect.centery = int(STATE.EXFIL_POS[1])
        STATE.camera_x = STATE.player.rect.centerx - WIDTH // 2
        STATE.camera_y = STATE.player.rect.centery - HEIGHT // 2
    STATE.floating_texts.append([
        STATE.player.rect.centerx, STATE.player.rect.centery - 60,
        "DEBUG: EXFIL READY", C_TERMINAL, 90,
    ])
    audio.play("terminal_glitch", volume=0.2)
_last_keys = ()
def game_update(keys):
    global _last_keys
    _last_keys = keys
    # AEGIS Pass E: advance player i-frame timer + sprite blink every frame.
    # Must run BEFORE the death-trigger check below so the timer ticks down
    # even on the frame the player dies (otherwise a freshly-set i-frame
    # window would freeze the blink state on the death frame).
    if STATE.player:
        STATE.player.update_iframes(STATE.dt)
    if STATE.gc_flash_timer > 0:
        STATE.gc_flash_timer -= 1
    # ── Death animation trigger ──
    # Previously this block immediately set request_death_screen=True and
    # returned, which skipped the entire death animation (slow-mo, ragdoll,
    # blood pool, tinnitus, camera tilt). Now we trigger the death animation
    # and let it play out — the death_anim module will set request_death_screen
    # when the 2-second animation completes. We still return early so the rest
    # of the update logic (enemy AI, bullets, etc.) doesn't run on the frame
    # the player dies — subsequent frames will run update_death_anim() via the
    # block at line ~890.
    if STATE.player and STATE.player.hp <= 0 and not STATE.player_dead:
        import death_anim
        death_anim.trigger_death()
        if not STATE.mission_end_time:
            STATE.mission_end_time = pygame.time.get_ticks()
        return STATE.camera_x, STATE.camera_y
    if STATE.active_read_note or STATE.safe_keypad_active:
        return STATE.camera_x, STATE.camera_y
    player_hit_this_frame = False
    if STATE.NOTEBOOK_POS is None:
        _init_mission_specials()
    if STATE.player and not STATE.firefight_triggered:
        # Combat only starts from enemy detection — no position trigger
        for e in STATE.enemies:
            if e.alerted:
                trigger_alarm_early()
                break
        # ── Civilian payoff line (once, on warehouse entry) ──
        if (STATE.player.rect.centery > 11 * TILE_SIZE
                and not STATE.civilian_payoff_done):
            STATE.civilian_payoff_done = True
            _trigger_civilian_payoff()
    if STATE.firefight_triggered:
        if STATE.radio_chatter_stage == 1 and STATE.player.rect.centery > 15 * TILE_SIZE:
            STATE.radio_chatter_stage = 2
            trigger_radio_chatter(
                'VASILE: "Gate is open. Signatures ahead, watch the corners."'
            )
        if STATE.radio_chatter_stage == 2 and STATE.NOTEBOOK_POS:
            if (
                math.hypot(
                    STATE.player.rect.centerx - STATE.NOTEBOOK_POS[0],
                    STATE.player.rect.centery - STATE.NOTEBOOK_POS[1],
                )
                < 120
            ):
                STATE.radio_chatter_stage = 3
                trigger_radio_chatter(
                    'VASILE: "Safe is locked. Look for notes on desks for the code."'
                )
    # ── Staged breach (after notebook acquisition) ──
    if STATE.breach_stage > 0 and STATE.breach_stage < 6:
        STATE.breach_stage_timer += 1
        if STATE.breach_stage == 1:
            if STATE.breach_stage_timer % 40 == 0:
                audio.play("door_rattle", volume=0.2)
                STATE.screen_shake = max(STATE.screen_shake, 2)
            if STATE.breach_stage_timer >= 90:
                STATE.breach_stage = 2
                STATE.breach_stage_timer = 0
        elif STATE.breach_stage == 2:
            if STATE.breach_stage_timer == 1:
                trigger_radio_chatter(
                    'VASILE: "BRACE! They\'re breaching the bay doors!"'
                )
            if STATE.breach_stage_timer >= 90:
                STATE.breach_stage = 3
                STATE.breach_stage_timer = 0
        elif STATE.breach_stage == 3:
            if STATE.breach_stage_timer % 15 == 0:
                audio.play("door_rattle", volume=0.5)
                STATE.screen_shake = max(STATE.screen_shake, 5)
            if STATE.breach_stage_timer >= 120:
                STATE.breach_stage = 4
                STATE.breach_stage_timer = 0
        elif STATE.breach_stage == 4:
            STATE.screen_shake = max(STATE.screen_shake, 4)
            if STATE.breach_stage_timer % 6 == 0 and STATE.player:
                for _ in range(2):
                    px = 15 * TILE_SIZE + random.randint(-3 * TILE_SIZE, 3 * TILE_SIZE)
                    py = 19 * TILE_SIZE + random.randint(-TILE_SIZE, 0)
                    p = Particle(px, py, random.choice([(120, 110, 90), (90, 85, 70)]))
                    p.life = random.randint(30, 60)
                    p.dy = random.uniform(-0.5, 0.5)
                    p.dx = random.uniform(-0.3, 0.3)
                    STATE.particles.append(p)
            if STATE.breach_stage_timer >= 90:
                STATE.breach_stage = 5
                STATE.breach_stage_timer = 0
        elif STATE.breach_stage == 5:
            STATE.gc_flash_timer = 18
            effects.shake(28)
            STATE.mag_spawn_done = True
            STATE.breach_sequence_active = False
            # ═══════════════════════════════════════
            # OPEN BAY DOORS
            # ═══════════════════════════════════════
            for d in STATE.doors:
                if d.is_bay:
                    d.locked = False
                    d.target_open = True
                    d.anim_progress = 1.0
                    d.collision_disabled = True
                    d.manual_timer = 9999
            # ═══════════════════════════════════════
            # OPEN THE GATE (row 15) so rear enemies pour through
            # ═══════════════════════════════════════
            for d in STATE.doors:
                if getattr(d, "is_gate", False):
                    d.locked = False
                    d.target_open = True
                    d.anim_progress = 1.0
                    d.collision_disabled = True
                    d.manual_timer = 9999
            # ═══════════════════════════════════════
            # 8 ENEMIES FROM BAY DOORS (south side, row 20-21)
            # ═══════════════════════════════════════
            bay_spawns = [
                _tc(13, 20), _tc(14, 20), _tc(15, 20), _tc(16, 20),
                _tc(17, 20), _tc(14, 21), _tc(15, 21), _tc(16, 21),
            ]
            bay_targets = [
                _tc(12, 18), _tc(14, 18), _tc(16, 18), _tc(18, 18),
                _tc(13, 17), _tc(15, 17), _tc(17, 17), _tc(15, 16),
            ]
            for i, (mx, my) in enumerate(bay_spawns):
                tx, ty = bay_targets[i % len(bay_targets)]
                new_e = Enemy(mx, my)
                new_e.alerted = True
                new_e.state = "CHASE"
                new_e.last_seen_pos = (tx, ty)
                new_e.is_ambush_enemy = True
                new_e.is_breach_enemy = True
                new_e.fire_weakness = 1.15
                new_e.hp = 115
                new_e.fire_cooldown = 40 + i * 15 + random.randint(0, 30)
                new_e.speed = random.uniform(2.0, 2.7)
                STATE.enemies.append(new_e)
                for _ in range(20):
                    STATE.particles.append(Particle(mx, my, (150, 150, 150)))
                for _ in range(10):
                    STATE.particles.append(Particle(mx, my, (255, 120, 30)))
            # ═══════════════════════════════════════
            # 6 ENEMIES FROM COMMANDER ROOM (rows 11-14)
            # ═══════════════════════════════════════
            rear_spawns = [
                _tc(10, 11), _tc(18, 11),
                _tc(6,  12), _tc(20, 12),
                _tc(10, 13), _tc(15, 13),
            ]
            rear_targets = [
                _tc(10, 17), _tc(18, 17),
                _tc(8,  16), _tc(20, 16),
                _tc(12, 18), _tc(16, 18),
            ]
            for i, (mx, my) in enumerate(rear_spawns):
                tx, ty = rear_targets[i % len(rear_targets)]
                new_e = Enemy(mx, my)
                new_e.alerted = True
                new_e.state = "CHASE"
                new_e.last_seen_pos = (tx, ty)
                new_e.is_ambush_enemy = True
                new_e.is_breach_enemy = True
                new_e.fire_weakness = 1.15
                new_e.hp = 115
                new_e.fire_cooldown = 60 + i * 18 + random.randint(0, 25)
                new_e.speed = random.uniform(1.8, 2.4)
                STATE.enemies.append(new_e)
                for _ in range(15):
                    STATE.particles.append(Particle(mx, my, (200, 200, 200)))
            # ═══════════════════════════════════════
            # EFFECTS
            # ═══════════════════════════════════════
            audio.play("breach", volume=0.9)
            audio.play("explosion", volume=0.7)
            STATE.floating_texts.append([
                15 * TILE_SIZE + 32, 19 * TILE_SIZE,
                "BAY DOOR BREACH!",
                (255, 100, 30), 120,
            ])
            STATE.floating_texts.append([
                15 * TILE_SIZE + 32, 15 * TILE_SIZE,
                "CONTACTS FROM BEHIND!",
                (255, 70, 40), 120,
            ])
            trigger_radio_chatter(
                'VASILE: "They\'re coming from both sides! Get to the truck NOW!"',
                color=(220, 80, 60),
                duration=240,
            )
            STATE.breach_stage = 6
    # ── Volkov escape animation ──
    if STATE.volkov_escape_timer > 0:
        STATE.volkov_escape_timer -= 1
        bay_door_y = 19 * TILE_SIZE + 32
        if STATE.volkov_escape_pos and not STATE.volkov_escaped:
            dx = 15 * TILE_SIZE + 32 - STATE.volkov_escape_pos[0]
            dy = bay_door_y - STATE.volkov_escape_pos[1]
            dist = math.hypot(dx, dy)
            if dist > 5:
                STATE.volkov_escape_pos[0] += (dx / dist) * 2.5
                STATE.volkov_escape_pos[1] += (dy / dist) * 2.5
            else:
                STATE.volkov_escaped = True
        if STATE.commander_escape_pos and not STATE.commander_escaped:
            dx = 15 * TILE_SIZE + 32 - STATE.commander_escape_pos[0]
            dy = bay_door_y - STATE.commander_escape_pos[1]
            dist = math.hypot(dx, dy)
            if dist > 5:
                STATE.commander_escape_pos[0] += (dx / dist) * 2.5
                STATE.commander_escape_pos[1] += (dy / dist) * 2.5
            else:
                STATE.commander_escaped = True
        if STATE.volkov_escape_timer == 30:
            trigger_radio_chatter(
                'VASILE: "Volkov escaped! Get that notebook and get out."'
            )
        if STATE.volkov_escape_timer == 0:
            STATE.volkov_escaped = True
            STATE.commander_escaped = True
    solid_walls = STATE.walls[:]
    for d in STATE.doors:
        if d.collision_rect:
            solid_walls.append(d.collision_rect)
    gate_locked = any(d.locked for d in STATE.doors if getattr(d, "is_gate", False))
    if gate_locked and STATE.player:
        dist_to_console = math.hypot(
            STATE.player.rect.centerx - (13 * TILE_SIZE + 32),
            STATE.player.rect.centery - (15 * TILE_SIZE + 32),
        )
        if dist_to_console < 80:
            if STATE.has_keycard:
                # Keycard bypass — instant open, no minigame
                if keys[pygame.K_e]:
                    for d in STATE.doors:
                        if getattr(d, "is_gate", False):
                            d.locked = False
                            d.target_open = True
                            audio.play("door_open", volume=0.5)
                            STATE.floating_texts.append(
                                [
                                    d.rect.centerx,
                                    d.rect.centery - 20,
                                    "GATE OPENED — KEYCARD",
                                    C_TERMINAL,
                                    120,
                                ]
                            )
                    STATE.gate_hacking = False
                    STATE.gate_hack_progress = 0.0
            else:
                # No keycard — hack minigame
                if keys[pygame.K_e]:
                    STATE.gate_hacking = True
                    STATE.gate_hack_progress += 1.0 / 180.0
                    if (pygame.time.get_ticks() // 200) % 2 == 0:
                        audio.play("menu_hover", volume=0.2)
                    if STATE.gate_hack_progress >= 1.0:
                        for d in STATE.doors:
                            if getattr(d, "is_gate", False):
                                d.locked = False
                                d.target_open = True
                                audio.play("door_open", volume=0.5)
                                STATE.floating_texts.append(
                                    [
                                        d.rect.centerx,
                                        d.rect.centery - 20,
                                        "GATE HACKED",
                                        C_TERMINAL,
                                        120,
                                    ]
                                )
                        STATE.gate_hacking = False
                        STATE.gate_hack_progress = 0.0
                else:
                    STATE.gate_hacking = False
                    STATE.gate_hack_progress = 0.0
        else:
            if STATE.gate_hacking:
                STATE.gate_hacking = False
                STATE.gate_hack_progress = 0.0
    else:
        if STATE.gate_hacking:
            STATE.gate_hacking = False
            STATE.gate_hack_progress = 0.0
    for b in STATE.thrown_bottles[:]:
        prev_x, prev_y = b["x"], b["y"]
        b["t"] = min(1.0, b["t"] + b["speed"])
        new_x = b["start_x"] + (b["tx"] - b["start_x"]) * b["t"]
        new_y = b["start_y"] + (b["ty"] - b["start_y"]) * b["t"]
        hit_wall = False
        impact_x, impact_y = new_x, new_y
        # Molotov cannot pass through STATE.walls / closed STATE.doors
        for wall in solid_walls:
            clipped = wall.clipline((prev_x, prev_y), (new_x, new_y))
            if clipped:
                impact_x, impact_y = clipped[0]
                hit_wall = True
                break
        if b["t"] >= 1.0 or hit_wall:
            _spawn_molotov_fire(impact_x, impact_y, solid_walls)
            STATE.thrown_bottles.remove(b)
        else:
            b["x"] = new_x
            b["y"] = new_y
    # ── Molotov fire damage ──
    for fire in STATE.molotov_fires[:]:
        fire["life"] -= 1
        fx, fy = fire["x"], fire["y"]
        if random.random() < 0.75:
            px = fx + random.uniform(-MOLOTOV_RADIUS * 0.55, MOLOTOV_RADIUS * 0.55)
            py = fy + random.uniform(-MOLOTOV_RADIUS * 0.55, MOLOTOV_RADIUS * 0.55)
            if math.hypot(px - fx, py - fy) < MOLOTOV_RADIUS * 0.65:
                col = random.choice([(255, 95, 25), (255, 150, 40), (255, 210, 80), (80, 70, 65)])
                p = Particle(px, py, col)
                p.dy -= random.uniform(1.0, 2.4)
                p.dx *= 0.35
                p.life = random.randint(18, 34)
                STATE.particles.append(p)
        for e in STATE.enemies:
            dist = math.hypot(e.rect.centerx - fx, e.rect.centery - fy)
            if dist < MOLOTOV_RADIUS and not _wall_blocks_line(
                fx, fy, e.rect.centerx, e.rect.centery, solid_walls
            ):
                heat = 1.0 - dist / MOLOTOV_RADIUS
                fire_mult = getattr(e, "fire_weakness", 1.0)
                e.hp -= MOLOTOV_ENEMY_DAMAGE * (0.45 + heat) * fire_mult
                if getattr(e, "is_breach_enemy", False) and random.random() < 0.018:
                    STATE.particles.append(Particle(e.rect.centerx, e.rect.centery, (255, 190, 70)))
                e.alerted = True
                e.combat_alert_timer = max(getattr(e, "combat_alert_timer", 0), 300)
                # Fire should alert enemies, but it should NOT constantly overwrite
                # their target if they can already see the player.
                if STATE.player:
                    ptx = STATE.player.rect.centerx
                    pty = STATE.player.rect.centery
                    can_see_player = not _wall_blocks_line(
                        e.rect.centerx,
                        e.rect.centery,
                        ptx,
                        pty,
                        solid_walls,
                    )
                else:
                    can_see_player = False
                if can_see_player:
                    e.last_seen_pos = (ptx, pty)
                    # Don't constantly knock enemies out of ATTACK flow.
                    if e.state not in ("ATTACK", "CHASE"):
                        e.state = "CHASE"
                else:
                    # Fire is only a distraction if they are not already committed.
                    if e.state in ("IDLE", "PATROL"):
                        e.state = "SEARCH"
                        e.distraction_target = (fx, fy)
                        e.search_timer = max(getattr(e, "search_timer", 0), 120)
                if random.random() < 0.12:
                    STATE.particles.append(
                        Particle(e.rect.centerx, e.rect.centery, (255, 110, 30))
                    )
        if STATE.player and not STATE.player_dead:
            pdist = math.hypot(STATE.player.rect.centerx - fx, STATE.player.rect.centery - fy)
            player_burn_radius = MOLOTOV_RADIUS * 0.72
            if pdist < player_burn_radius and not _wall_blocks_line(fx, fy, STATE.player.rect.centerx, STATE.player.rect.centery, solid_walls):
                heat = 1.0 - pdist / player_burn_radius
                # AEGIS Pass E: route through take_damage() so i-frames apply.
                # Molotov burns tick every frame; without i-frames the player
                # could lose 100+ HP in a single step into a fire zone.
                if STATE.player.take_damage(MOLOTOV_PLAYER_DAMAGE * (0.35 + heat)):
                    player_hit_this_frame = True
        if fire["life"] <= 0:
            STATE.molotov_fires.remove(fire)
    # Process active fire zones
    if STATE.player and not STATE.player_dead:
        STATE.fire_zones[:] = [fz for fz in STATE.fire_zones if fz.update(
            STATE.enemies, STATE.player.rect, audio
        )]
    if STATE.mission_phase == "escape" and STATE.player:
        dist_to_truck = math.hypot(
            STATE.player.rect.centerx - STATE.EXFIL_POS[0],
            STATE.player.rect.centery - STATE.EXFIL_POS[1],
        )
        if dist_to_truck < 80:
            if STATE.enemies:
                if keys[pygame.K_e] and not STATE.hotwire_radio_said:
                    STATE.hotwire_radio_said = True
                    trigger_radio_chatter('VASILE: "Not yet. Clear the yard before you put your head under that dash."')
                STATE.truck_hotwiring = False
                STATE.hotwire_selected_wire = None
            elif not STATE.truck_hotwiring:
                if keys[pygame.K_e]:
                    STATE.truck_hotwiring = True
                    _reset_hotwire_minigame()
                    audio.play("door_creak", volume=0.35)
                    if not STATE.hotwire_radio_said:
                        STATE.hotwire_radio_said = True
                        trigger_radio_chatter('VASILE: "Open the panel. Red feeds yellow. Blue wakes green. Black bites white."')
            else:
                STATE.hotwire_panel_timer = min(60, STATE.hotwire_panel_timer + 1)
                if STATE.hotwire_spark_timer > 0:
                    STATE.hotwire_spark_timer -= 1
        else:
            STATE.truck_hotwiring = False
            STATE.hotwire_stage = 0
            STATE.hotwire_selected_wire = None
            STATE.hotwire_panel_timer = 0
        if STATE.hotwire_fail_flash > 0:
            STATE.hotwire_fail_flash -= 1
    if STATE.player:
        if STATE.player.hp <= 0 and not STATE.player_dead:
            # Death animation (Option B — Standard) handles the full sequence:
            # slow-mo, camera collapse, ragdoll, blood pool, tinnitus, radio cut.
            # Replaces the legacy single-burst + shake trigger.
            import death_anim
            death_anim.trigger_death()
        if STATE.player_dead:
            # update_death_anim() advances all 6 layers and returns the
            # number of game-logic ticks to run (slow-mo via accumulator).
            import death_anim
            ticks = death_anim.update_death_anim()
            # During slow-mo we want bullets/enemies to advance at the scaled
            # rate. The caller's existing per-frame logic runs once per tick.
            # We stash the tick count on STATE so the rest of game_update can
            # read it without restructuring the whole function.
            STATE._death_logic_ticks = ticks
        if not STATE.player_dead:
            STATE._death_logic_ticks = 1
        if not STATE.player_dead:
            dx, dy = 0, 0
            if not STATE.truck_hotwiring:
                # Delta-time aware: speed is in px/frame (e.g. 5), so
                # multiply by (60 * dt) to get px this frame at any FPS.
                # At 60 FPS dt=1/60, so 60*dt = 1 → identical to old behavior.
                _dt_mul = 60.0 * STATE.dt
                if keys[pygame.K_w]:
                    dy -= STATE.player.speed * _dt_mul
                if keys[pygame.K_s]:
                    dy += STATE.player.speed * _dt_mul
                if keys[pygame.K_a]:
                    dx -= STATE.player.speed * _dt_mul
                if keys[pygame.K_d]:
                    dx += STATE.player.speed * _dt_mul
            if dx != 0 and dy != 0:
                dx *= 0.707
                dy *= 0.707
            is_moving = dx != 0 or dy != 0
            STATE.player.move(dx, dy, solid_walls)
            if is_moving:
                STATE._footstep_timer -= 1
                if STATE._footstep_timer <= 0:
                    audio.play("footstep", volume=0.3)
                    STATE._footstep_timer = 25 + random.randint(0, 8)
            else:
                STATE._footstep_timer = 0
    # Unified camera: lerp + first-frame snap + map-bounds clamp + recoil kick + shake.
    # Both missions now use this same code path so the feel of "the camera
    # following the player" cannot drift between them.
    if STATE.player:
        fcx, fcy = update_camera(
            (STATE.player.rect.centerx, STATE.player.rect.centery),
            map_w=MAP_W, map_h=MAP_H,
        )
    else:
        fcx, fcy = STATE.camera_x, STATE.camera_y
    if STATE.shot_cooldown > 0:
        STATE.shot_cooldown -= 1
    if STATE.is_reloading:
        STATE.reload_timer -= 1
        if STATE.reload_timer <= 0:
            STATE.ammo_in_mag = STATE.mag_size
            STATE.spare_mags -= 1
            STATE.is_reloading = False
    if STATE.player:
        for d in STATE.doors:
            d.update(STATE.player.rect)
    if STATE.player and not STATE.player_dead:
        # Use raw mouse position for the angle, scaled mouse is for UI
        # but since we are in GAME state, the cursor is hidden and we
        # want the mouse to feel natural.
        # Actually, get_scaled_mouse is correct for the virtual screen coordinates.
        world_mx, world_my = get_scaled_mouse()
        world_mx += fcx
        world_my += fcy
        STATE.player.angle = math.atan2(
            world_my - STATE.player.rect.centery, world_mx - STATE.player.rect.centerx
        )
    if STATE.melee_active:
        STATE.melee_timer -= 1
        if not STATE.melee_hit_done and STATE.melee_timer <= 10:
            STATE.melee_hit_done = True
            if STATE.player and not STATE.player_dead:
                # Shared melee resolver: range, cone, LOS, damage, particles,
                # shake are all defined in player.resolve_melee.
                nearest = resolve_melee(
                    STATE.player, STATE.enemies, solid_walls, C_BLOOD,
                )
                if nearest:
                    STATE.shots_hit += 1
                    # Per-mission: if you meleed the commander, drop a keycard.
                    # (Commander death is handled in the enemy-death loop below;
                    # melee just damages.)
        if STATE.melee_timer <= 0:
            STATE.melee_active = False
            STATE.melee_hit_done = False  # reset so the next swing can hit
    for b in STATE.bullets[:]:
        b["prev_x"] = b["x"]
        b["prev_y"] = b["y"]
        # Delta-time aware: dx/dy are in px/frame, so multiply by (60*dt).
        _dt_mul = 60.0 * STATE.dt
        b["x"] += b["dx"] * _dt_mul
        b["y"] += b["dy"] * _dt_mul
        b["life"] -= 1
        # ── Entity hits checked BEFORE wall hits ──
        # Previously wall collision ran first (swept clipline check), which
        # meant a bullet that reached the player's hitbox (22px radius) but
        # was also inside a cover rect was absorbed as a "wall hit" and the
        # player took no damage. Now entity hits take priority — if a bullet
        # reaches an entity, it hits that entity, not the cover.
        hit = False
        if b["owner"] == "player":
            current_volkov_pos = None
            if STATE.volkov_pos and not STATE.volkov_escaped:
                current_volkov_pos = (
                    STATE.volkov_escape_pos
                    if (STATE.firefight_triggered and STATE.volkov_escape_pos)
                    else STATE.volkov_pos
                )
            if current_volkov_pos:
                if (
                    math.hypot(
                        b["x"] - current_volkov_pos[0], b["y"] - current_volkov_pos[1]
                    )
                    < 22
                ):
                    hit = True
                    effects.burst(b["x"], b["y"], (200, 180, 100), 6, jitter=2)
                    STATE.floating_texts.append(
                        [b["x"], b["y"] - 20, "NO EFFECT", (200, 150, 50), 30]
                    )
            if not hit and STATE.commander_pos and not STATE.commander_escaped:
                if (
                    math.hypot(b["x"] - STATE.commander_pos[0], b["y"] - STATE.commander_pos[1])
                    < 22
                ):
                    hit = True
                    effects.burst(b["x"], b["y"], (200, 180, 100), 6, jitter=2)
                    STATE.floating_texts.append(
                        [b["x"], b["y"] - 20, "NO EFFECT", (200, 150, 50), 30]
                    )
            if not hit:
                for e in STATE.enemies:
                    if (
                        math.hypot(b["x"] - e.rect.centerx, b["y"] - e.rect.centery)
                        < 22
                    ):
                        e.hp -= b.get("damage", 50)
                        hit = True
                        STATE.shots_hit += 1
                        if STATE.player:
                            e.on_hit(STATE.player.rect.centerx, STATE.player.rect.centery)
                        else:
                            e.alerted = True
                            e.state = "CHASE"
                        # Shared burst (was 12 raw Particle(); now 14 via effects.burst
                        # to match M2's count and richer life/jitter).
                        effects.burst(b["x"], b["y"], C_BLOOD, 14)
                        effects.play_impact(
                            "bullet_impact_enemy", (b["x"], b["y"]), base_volume=0.5,
                        )
                        STATE.blood_decals.append(
                            [b["x"], b["y"], 120, random.randint(8, 16)]
                        )
                        break
        if not hit and b["owner"] == "enemy" and STATE.player and not STATE.player_dead:
            if (
                math.hypot(b["x"] - STATE.player.rect.centerx, b["y"] - STATE.player.rect.centery)
                < 22
            ):
                damage = b.get("damage", ENEMY_DAMAGE)
                # AEGIS Pass E: route through take_damage() so i-frames apply.
                # If absorbed by i-frames, still mark the bullet as "hit" so
                # it gets cleaned up, but DO NOT trigger the player-hit feedback
                # (no blood, no shake, no hit-stop) — the player should not
                # receive damage feedback for a hit that did no damage.
                if STATE.player.take_damage(damage):
                    player_hit_this_frame = True
                hit = True
                # Shared max-clamp shake trigger (was direct assignment, which
                # could stomp a larger in-flight shake).
                effects.shake(6)
                effects.burst(b["x"], b["y"], C_BLOOD, 8)
                audio.play("bullet_impact_enemy", volume=0.6)
        # ── Wall hits checked LAST (only if no entity was hit) ──
        # Same fix as mission2.py: entity hits take priority over wall hits
        # so bullets that reach the player aren't absorbed by cover rects.
        if not hit:
            hit = collide_bullet_walls(b, solid_walls)
            if hit:
                effects.burst(b["x"], b["y"], (200, 180, 140), 5, jitter=2)
                effects.play_impact("bullet_impact", (b["x"], b["y"]), base_volume=0.4)
        if (
            hit
            or b["life"] <= 0
            or not (-1000 < b["x"] < 3000 and -1000 < b["y"] < 3000)
        ):
            STATE.bullets.remove(b)
    for e in STATE.enemies[:]:
        if STATE.player and not STATE.player_dead:
            e.update(
                STATE.player.rect.centerx,
                STATE.player.rect.centery,
                solid_walls,
                STATE.bullets,
                STATE.particles,
                STATE.enemies,
                STATE.fire_zones,
            )
        if e.hp <= 0:
            # Enemy death burst unified with M2 (was 25 raw Particle()).
            effects.burst(e.rect.centerx, e.rect.centery, C_BLOOD, 24)
            STATE.blood_decals.append(
                [e.rect.centerx, e.rect.centery, 160, random.randint(14, 22)]
            )
            if getattr(e, "is_commander", False):
                STATE.pickups.append([e.rect.centerx, e.rect.centery, "keycard"])
                STATE.floating_texts.append(
                    [
                        e.rect.centerx,
                        e.rect.centery - 20,
                        "KEYCARD DROPPED",
                        (255, 200, 100),
                        120,
                    ]
                )
                STATE.pickups.append([e.rect.centerx - 20, e.rect.centery + 10, "bandage"])
                STATE.pickups.append([e.rect.centerx + 20, e.rect.centery + 10, "bandage"])
                STATE.floating_texts.append(
                    [
                        e.rect.centerx,
                        e.rect.centery + 20,
                        "BANDAGES DROPPED",
                        (100, 220, 100),
                        120,
                    ]
                )
            else:
                is_warehouse_enemy = e.rect.centery > 11 * TILE_SIZE
                roll = random.random()
                if is_warehouse_enemy:
                    if roll < 0.30:
                        STATE.pickups.append([e.rect.centerx, e.rect.centery, "bandage"])
                    elif roll < 0.55 and STATE.spare_mags < 3 + walking_sim.warehouse_mag_bonus:
                        STATE.pickups.append([e.rect.centerx, e.rect.centery, "mag"])
                    elif roll < 0.75 and STATE.player_bottles < 4:
                        STATE.pickups.append([e.rect.centerx, e.rect.centery, "bottle"])
                else:
                    if roll < 0.40 and STATE.spare_mags < 3 + walking_sim.warehouse_mag_bonus:
                        STATE.pickups.append([e.rect.centerx, e.rect.centery, "mag"])
                    elif roll < 0.65 and STATE.player_bottles < 4:
                        STATE.pickups.append([e.rect.centerx, e.rect.centery, "bottle"])
            STATE.hostiles_killed += 1
            STATE.enemies.remove(e)
            if STATE.player and not STATE.player_dead:
                audio.play_3d(
                    "bullet_impact_enemy",
                    (e.rect.centerx, e.rect.centery),
                    (STATE.player.rect.centerx, STATE.player.rect.centery),
                    base_volume=0.4,
                )
            else:
                audio.play("bullet_impact_enemy", volume=0.4)
    for p in STATE.particles[:]:
        p.update()
        if p.life <= 0:
            STATE.particles.remove(p)
    for c in STATE.casings[:]:
        c.update(solid_walls)
        if c.life <= 0:
            STATE.casings.remove(c)
    for ft in STATE.floating_texts[:]:
        if len(ft) < 6 or ft[5] != "pin":
            ft[1] -= 1.0
        ft[4] -= 1
        if ft[4] <= 0:
            STATE.floating_texts.remove(ft)
    if STATE.player and not STATE.player_dead:
        for pu in STATE.pickups[:]:
            dx = pu[0] - STATE.player.rect.centerx
            dy = pu[1] - STATE.player.rect.centery
            if math.hypot(dx, dy) < 30:
                if pu[2] == "mag" and STATE.spare_mags < 3 + walking_sim.warehouse_mag_bonus:
                    STATE.spare_mags += 1
                    STATE.floating_texts.append([pu[0], pu[1] - 16, "+1 MAG", C_TERMINAL, 70])
                    audio.play("pickup", volume=0.5)
                    STATE.pickups.remove(pu)
                elif pu[2] == "keycard":
                    STATE.has_keycard = True
                    STATE.floating_texts.append(
                        [pu[0], pu[1] - 16, "GATE KEYCARD ACQUIRED", C_TERMINAL, 120]
                    )
                    audio.play("pickup", volume=0.5)
                    STATE.pickups.remove(pu)
                elif pu[2] == "bandage":
                    heal_amount = 40
                    old_hp = STATE.player.hp
                    STATE.player.hp = min(STATE.player.max_hp, STATE.player.hp + heal_amount)
                    actual_healed = STATE.player.hp - old_hp
                    if actual_healed > 0:
                        STATE.floating_texts.append(
                            [
                                pu[0],
                                pu[1] - 16,
                                f"+{actual_healed} HP",
                                (100, 220, 100),
                                70,
                            ]
                        )
                    else:
                        STATE.floating_texts.append(
                            [pu[0], pu[1] - 16, "HP FULL", (100, 220, 100), 70]
                        )
                    audio.play("pickup", volume=0.5)
                    STATE.pickups.remove(pu)
                elif pu[2] == "bottle":
                    if STATE.player_bottles < 4:
                        STATE.player_bottles += 1
                        STATE.floating_texts.append(
                            [pu[0], pu[1] - 16, "+1 MOLOTOV", (140, 200, 150), 70]
                        )
                        audio.play("pickup", volume=0.5)
                        STATE.pickups.remove(pu)
                    else:
                        STATE.floating_texts.append(
                            [pu[0], pu[1] - 16, "MOLOTOVS FULL", (140, 200, 150), 70]
                        )
                        STATE.pickups.remove(pu)
        if player_hit_this_frame and STATE.truck_hotwiring:
            STATE.truck_hotwiring = False
            STATE.hotwire_stage = 0
            STATE.floating_texts.append(
                [
                    STATE.player.rect.centerx,
                    STATE.player.rect.centery - 40,
                    "INTERRUPTED!",
                    (220, 60, 60),
                    60,
                ]
            )
    return fcx, fcy
# ─────────────────────────────────────────────
# MINIMAP
# ─────────────────────────────────────────────
def _draw_molotov_icon(surface, cx, cy, active=True):
    """Small chunky pixel-art Molotov icon for the HUD."""
    if active:
        glass = (105, 75, 42)
        glass_dark = (42, 28, 18)
        fuel = (230, 120, 35)
        rag = (190, 170, 120)
        flame_outer = (255, 95, 20)
        flame_inner = (255, 220, 90)
    else:
        glass = (42, 45, 46)
        glass_dark = (25, 27, 28)
        fuel = (60, 62, 64)
        rag = (65, 65, 60)
        flame_outer = None
        flame_inner = None
    # Bottle body
    pygame.draw.rect(surface, glass_dark, (cx - 5, cy - 8, 10, 18), border_radius=2)
    pygame.draw.rect(surface, glass, (cx - 4, cy - 7, 8, 16), border_radius=2)
    # Fuel strip
    pygame.draw.rect(surface, fuel, (cx - 2, cy - 5, 3, 11))
    # Neck
    pygame.draw.rect(surface, glass_dark, (cx - 2, cy - 14, 4, 6))
    pygame.draw.rect(surface, glass, (cx - 1, cy - 14, 2, 6))
    # Rag
    pygame.draw.rect(surface, rag, (cx - 4, cy - 17, 8, 3))
    # Highlight
    if active:
        pygame.draw.line(surface, (255, 180, 90), (cx - 3, cy - 5), (cx - 3, cy + 6), 1)
    # Tiny flame
    if active:
        pygame.draw.polygon(
            surface,
            flame_outer,
            [(cx, cy - 25), (cx - 5, cy - 16), (cx + 5, cy - 16)],
        )
        pygame.draw.polygon(
            surface,
            flame_inner,
            [(cx, cy - 22), (cx - 2, cy - 16), (cx + 2, cy - 16)],
        )
def _escape_subtitle(surface, speaker, text, alpha=255):
    box_w, box_h = 720, 92
    box_x = WIDTH // 2 - box_w // 2
    box_y = HEIGHT - LETTER_H - box_h + 16
    box = pygame.Surface((box_w, box_h), pygame.SRCALPHA)
    box.fill((0, 0, 0, min(205, alpha)))
    pygame.draw.rect(box, (120, 120, 105, min(180, alpha)), box.get_rect(), 1)
    pygame.draw.line(box, C_KRAP_BLUE, (0, 0), (0, box_h), 4)
    surface.blit(box, (box_x, box_y))
    sp = font_speaker.render(speaker, True, (190, 190, 175))
    tx = font_dialogue.render(text, True, C_WHITE)
    sp.set_alpha(alpha)
    tx.set_alpha(alpha)
    surface.blit(sp, (box_x + 22, box_y + 12))
    surface.blit(tx, (box_x + 22, box_y + 48))
def _draw_biribel_soldier_closeup(surface, cx, cy, t, scale=1.0):
    """Procedural close-up of Biribel as a soldier.
    Drawn from the portrait reference: narrow oval face, sharp dark side-parted
    hair, strong brows, large serious eyes, straight nose, defined lips.
    Kept in game identity as a field soldier/tactical uniform, not a suit.
    """
    s = scale
    # ── Soldier uniform / shoulders ───────────────────────────────────
    pygame.draw.polygon(surface, (25, 38, 29), [
        (cx - 155*s, cy + 190*s), (cx - 96*s, cy + 74*s),
        (cx + 96*s, cy + 74*s), (cx + 155*s, cy + 190*s),
    ])
    pygame.draw.polygon(surface, (15, 24, 18), [
        (cx - 78*s, cy + 184*s), (cx - 34*s, cy + 66*s),
        (cx + 34*s, cy + 66*s), (cx + 78*s, cy + 184*s),
    ])
    for ox in (-54, 54):
        pygame.draw.line(surface, (9, 15, 11), (cx + ox*s, cy + 86*s), (cx + ox*0.55*s, cy + 184*s), max(3, int(6*s)))
    pygame.draw.rect(surface, (44, 62, 46), (int(cx - 68*s), int(cy + 114*s), int(136*s), int(42*s)), border_radius=max(2, int(4*s)))
    pygame.draw.rect(surface, (16, 24, 18), (int(cx - 68*s), int(cy + 114*s), int(136*s), int(42*s)), max(1, int(2*s)), border_radius=max(2, int(4*s)))
    # collar / throat shadow
    pygame.draw.polygon(surface, (10, 15, 12), [(cx - 28*s, cy + 72*s), (cx, cy + 104*s), (cx + 28*s, cy + 72*s), (cx + 16*s, cy + 142*s), (cx - 16*s, cy + 142*s)])
    # ── Face shape: long, narrow, angular oval like the reference ──────
    skin = (184, 146, 116)
    skin_hi = (215, 181, 148)
    cheek = (157, 112, 88)
    shadow = (105, 74, 58)
    # neck
    pygame.draw.rect(surface, skin, (int(cx - 24*s), int(cy + 48*s), int(48*s), int(62*s)), border_radius=max(4, int(8*s)))
    pygame.draw.rect(surface, shadow, (int(cx + 14*s), int(cy + 52*s), int(13*s), int(58*s)), border_radius=max(3, int(5*s)))
    # angular face polygon over a soft oval base
    pygame.draw.ellipse(surface, (150, 106, 82), (int(cx - 58*s), int(cy - 84*s), int(116*s), int(156*s)))
    face_pts = [
        (cx - 49*s, cy - 51*s), (cx - 42*s, cy - 77*s), (cx - 18*s, cy - 92*s),
        (cx + 16*s, cy - 92*s), (cx + 42*s, cy - 76*s), (cx + 50*s, cy - 48*s),
        (cx + 47*s, cy + 7*s), (cx + 31*s, cy + 49*s), (cx + 8*s, cy + 72*s),
        (cx - 8*s, cy + 72*s), (cx - 31*s, cy + 49*s), (cx - 47*s, cy + 7*s),
    ]
    pygame.draw.polygon(surface, skin, face_pts)
    pygame.draw.polygon(surface, shadow, face_pts, max(1, int(2*s)))
    # forehead/cheek highlights and jaw shadow
    pygame.draw.polygon(surface, skin_hi, [(cx - 18*s, cy - 72*s), (cx + 22*s, cy - 73*s), (cx + 35*s, cy - 26*s), (cx - 30*s, cy - 22*s)], 0)
    pygame.draw.polygon(surface, cheek, [(cx + 31*s, cy - 26*s), (cx + 48*s, cy + 2*s), (cx + 25*s, cy + 34*s), (cx + 16*s, cy + 8*s)], 0)
    pygame.draw.arc(surface, (95, 62, 52), (int(cx - 38*s), int(cy + 19*s), int(76*s), int(54*s)), 0.15, math.pi - 0.15, max(1, int(2*s)))
    # ears tucked under hair
    pygame.draw.ellipse(surface, skin, (int(cx - 66*s), int(cy - 28*s), int(18*s), int(44*s)))
    pygame.draw.ellipse(surface, skin, (int(cx + 48*s), int(cy - 28*s), int(18*s), int(44*s)))
    pygame.draw.arc(surface, shadow, (int(cx - 62*s), int(cy - 18*s), int(10*s), int(24*s)), -1.2, 1.5, 1)
    pygame.draw.arc(surface, shadow, (int(cx + 52*s), int(cy - 18*s), int(10*s), int(24*s)), 1.7, 4.2, 1)
    # ── Hair: dark, neat side part, thick wave/forelock ────────────────
    hair = (9, 11, 12)
    hair_mid = (22, 25, 27)
    hair_hi = (45, 48, 50)
    # main cap with side-part silhouette
    cap_pts = [
        (cx - 55*s, cy - 36*s), (cx - 58*s, cy - 67*s), (cx - 45*s, cy - 95*s),
        (cx - 16*s, cy - 112*s), (cx + 20*s, cy - 111*s), (cx + 49*s, cy - 92*s),
        (cx + 59*s, cy - 62*s), (cx + 53*s, cy - 41*s), (cx + 35*s, cy - 59*s),
        (cx + 6*s, cy - 66*s), (cx - 23*s, cy - 60*s),
    ]
    pygame.draw.polygon(surface, hair, cap_pts)
    # side mass / temple darkness
    pygame.draw.polygon(surface, hair, [(cx - 58*s, cy - 63*s), (cx - 49*s, cy - 27*s), (cx - 38*s, cy - 9*s), (cx - 43*s, cy - 73*s)])
    pygame.draw.polygon(surface, hair, [(cx + 50*s, cy - 74*s), (cx + 55*s, cy - 24*s), (cx + 42*s, cy - 6*s), (cx + 40*s, cy - 60*s)])
    # combed wave and front locks
    wave_pts = [
        (cx - 42*s, cy - 66*s), (cx - 24*s, cy - 92*s), (cx + 4*s, cy - 101*s),
        (cx + 34*s, cy - 90*s), (cx + 48*s, cy - 68*s), (cx + 22*s, cy - 78*s),
        (cx - 6*s, cy - 76*s),
    ]
    pygame.draw.polygon(surface, hair_mid, wave_pts)
    # distinct curled forelock on viewer right like the reference
    pygame.draw.polygon(surface, hair, [(cx + 18*s, cy - 78*s), (cx + 44*s, cy - 94*s), (cx + 53*s, cy - 75*s), (cx + 34*s, cy - 64*s)])
    lock_pts = [
        [(cx - 35*s, cy - 62*s), (cx - 19*s, cy - 82*s), (cx - 9*s, cy - 61*s)],
        [(cx - 12*s, cy - 66*s), (cx + 9*s, cy - 88*s), (cx + 16*s, cy - 63*s)],
        [(cx + 12*s, cy - 66*s), (cx + 35*s, cy - 82*s), (cx + 32*s, cy - 58*s)],
    ]
    for pts in lock_pts:
        pygame.draw.polygon(surface, hair, pts)
    pygame.draw.line(surface, hair_hi, (cx - 36*s, cy - 82*s), (cx + 26*s, cy - 94*s), max(1, int(2*s)))
    pygame.draw.line(surface, hair_hi, (cx - 20*s, cy - 76*s), (cx + 38*s, cy - 82*s), 1)
    # ── Eyes / brows: bigger, serious, portrait-like ───────────────────
    brow = (18, 15, 14)
    eye_white = (224, 220, 210)
    iris = (38, 43, 40)
    # heavy straight brows angled slightly inward
    pygame.draw.line(surface, brow, (cx - 42*s, cy - 28*s), (cx - 10*s, cy - 33*s), max(2, int(4*s)))
    pygame.draw.line(surface, brow, (cx + 10*s, cy - 33*s), (cx + 42*s, cy - 28*s), max(2, int(4*s)))
    for side in (-1, 1):
        ex = cx + side * 25*s
        eye_rect = pygame.Rect(int(ex - 15*s), int(cy - 21*s), int(30*s), int(12*s))
        pygame.draw.ellipse(surface, eye_white, eye_rect)
        pygame.draw.ellipse(surface, (48, 36, 30), eye_rect, 1)
        pygame.draw.circle(surface, iris, (int(ex + side*1*s), int(cy - 15*s)), max(3, int(5*s)))
        pygame.draw.circle(surface, (5, 8, 7), (int(ex + side*1*s), int(cy - 15*s)), max(2, int(3*s)))
        pygame.draw.circle(surface, (235, 235, 220), (int(ex + side*3*s), int(cy - 17*s)), max(1, int(1*s)))
        # under-eye shadows
        pygame.draw.arc(surface, (118, 82, 68), (int(ex - 15*s), int(cy - 13*s), int(30*s), int(18*s)), 0.2, math.pi - 0.2, 1)
    # ── Straight nose, defined lips, subtle stubble ────────────────────
    pygame.draw.line(surface, (108, 70, 54), (cx + 1*s, cy - 7*s), (cx - 3*s, cy + 20*s), max(1, int(2*s)))
    pygame.draw.line(surface, (205, 160, 128), (cx - 9*s, cy + 20*s), (cx - 3*s, cy + 24*s), 1)
    pygame.draw.line(surface, (105, 68, 55), (cx - 11*s, cy + 25*s), (cx + 11*s, cy + 24*s), max(1, int(2*s)))
    # lips: fuller and centered like reference
    pygame.draw.arc(surface, (96, 55, 54), (int(cx - 24*s), int(cy + 34*s), int(48*s), int(14*s)), 0.05, math.pi - 0.05, max(1, int(2*s)))
    pygame.draw.line(surface, (82, 45, 46), (cx - 24*s, cy + 41*s), (cx + 24*s, cy + 39*s), max(1, int(2*s)))
    pygame.draw.arc(surface, (142, 91, 78), (int(cx - 19*s), int(cy + 41*s), int(38*s), int(12*s)), 0, math.pi, 1)
    # subtle moustache / jaw stubble texture
    stubble = (72, 55, 48)
    rng_face = random.Random(1200 + int(t // 8))
    for _ in range(28):
        px = cx + rng_face.randint(int(-34*s), int(34*s))
        py = cy + rng_face.randint(int(22*s), int(60*s))
        if abs(px - cx) < 8*s and py < cy + 34*s:
            continue
        surface.set_at((int(px), int(py)), stubble)
    pygame.draw.line(surface, (80, 58, 50), (cx - 18*s, cy + 31*s), (cx + 18*s, cy + 30*s), 1)
    # ── Dashboard/rain cinematic lighting ─────────────────────────────
    orange = pygame.Surface((int(230*s), int(195*s)), pygame.SRCALPHA)
    pygame.draw.ellipse(orange, (255, 130, 48, 30), orange.get_rect())
    surface.blit(orange, (int(cx - 115*s), int(cy - 10*s)))
    blue = pygame.Surface((int(190*s), int(180*s)), pygame.SRCALPHA)
    pygame.draw.ellipse(blue, (50, 120, 180, 22), blue.get_rect())
    surface.blit(blue, (int(cx - 118*s), int(cy - 96*s)))
def _draw_escape_truck(surface, x, y, scale=1.0, angle=0.0, headlights=True):
    s = scale
    # shadow/wake
    sh = pygame.Surface((int(170*s), int(70*s)), pygame.SRCALPHA)
    pygame.draw.ellipse(sh, (0, 0, 0, 110), sh.get_rect())
    surface.blit(sh, (int(x - 85*s), int(y + 20*s)))
    body = pygame.Rect(int(x - 70*s), int(y - 28*s), int(140*s), int(56*s))
    pygame.draw.rect(surface, (24, 32, 24), body, border_radius=max(2, int(5*s)))
    pygame.draw.rect(surface, (58, 68, 50), body, max(1, int(2*s)), border_radius=max(2, int(5*s)))
    cab = pygame.Rect(int(x + 18*s), int(y - 24*s), int(45*s), int(48*s))
    pygame.draw.rect(surface, (35, 46, 35), cab, border_radius=max(2, int(4*s)))
    pygame.draw.rect(surface, (80, 92, 74), cab, 1, border_radius=max(2, int(4*s)))
    pygame.draw.rect(surface, (22, 38, 46), (int(x + 32*s), int(y - 17*s), int(20*s), int(14*s)), border_radius=2)
    pygame.draw.rect(surface, C_KRAP_BLUE, (int(x - 52*s), int(y - 16*s), int(62*s), int(6*s)))
    pygame.draw.rect(surface, (210, 210, 205), (int(x - 52*s), int(y - 9*s), int(62*s), 1))
    for wx in (-45, 20, 52):
        for wy in (-31, 27):
            pygame.draw.ellipse(surface, (6, 7, 8), (int(x + wx*s - 10*s), int(y + wy*s - 5*s), int(20*s), int(10*s)))
    if headlights:
        beam = pygame.Surface((int(260*s), int(95*s)), pygame.SRCALPHA)
        pygame.draw.polygon(beam, (255, 230, 145, 38), [(0, 28*s), (250*s, 0), (250*s, 95*s), (0, 65*s)])
        surface.blit(beam, (int(x + 58*s), int(y - 48*s)))
        pygame.draw.rect(surface, (245, 220, 130), (int(x + 62*s), int(y - 18*s), int(8*s), int(10*s)))
        pygame.draw.rect(surface, (245, 220, 130), (int(x + 62*s), int(y + 8*s), int(8*s), int(10*s)))
def draw_biribel_escape_cutscene(surface, timer):
    """Cinematic escape cutscene after the real hotwire minigame."""
    t = int(timer)
    # base rainy night road/warehouse palette
    surface.fill((5, 7, 10))
    for y in range(HEIGHT):
        p = y / HEIGHT
        pygame.draw.line(surface, (int(6+p*8), int(8+p*10), int(13+p*18)), (0, y), (WIDTH, y))
    # rain streaks
    rng_r = random.Random(92)
    for _ in range(110):
        rx = (rng_r.randint(0, WIDTH) + t * 3) % WIDTH
        ry = (rng_r.randint(LETTER_H, HEIGHT - LETTER_H) + t * 7) % (HEIGHT - LETTER_H) + LETTER_H
        pygame.draw.line(surface, (110, 130, 160, 55), (rx, ry), (rx - 5, ry + 18), 1)
    if t < 135:
        # dashboard / wire close-up
        dash_y = HEIGHT // 2 + 80
        pygame.draw.rect(surface, (8, 10, 12), (0, dash_y, WIDTH, HEIGHT - dash_y))
        pygame.draw.rect(surface, (28, 34, 32), (160, dash_y - 80, WIDTH - 320, 105), border_radius=10)
        pygame.draw.rect(surface, (58, 70, 62), (160, dash_y - 80, WIDTH - 320, 105), 2, border_radius=10)
        for i, col in enumerate([(215,55,45), (225,190,55), (60,130,220), (70,185,95)]):
            y = dash_y - 54 + i * 20
            pygame.draw.line(surface, col, (235, y), (WIDTH//2 - 30, y + math.sin(t*.12+i)*8), 5)
            pygame.draw.circle(surface, (220, 140, 70), (WIDTH//2 - 25, int(y + math.sin(t*.12+i)*8)), 7)
        if t > 30 and (t // 5) % 2 == 0:
            for _ in range(10):
                sx = WIDTH//2 + random.randint(-20, 18)
                sy = dash_y - 25 + random.randint(-28, 18)
                pygame.draw.line(surface, (255, 220, 90), (sx, sy), (sx+random.randint(-24,24), sy+random.randint(-18,18)), 1)
        wheel_r = 92 + int(math.sin(t*.08)*2)
        pygame.draw.circle(surface, (12, 13, 14), (WIDTH//2 + 190, dash_y - 16), wheel_r, 12)
        _escape_subtitle(surface, "ENGINE", "starter catches...", min(255, t*6))
    elif t < 300:
        # Biribel close-up, soldier not suit.
        # windshield frame
        pygame.draw.rect(surface, (8, 10, 12), (80, LETTER_H + 20, WIDTH - 160, HEIGHT - 2*LETTER_H - 40), 6)
        for lx in (180, WIDTH-180):
            pygame.draw.line(surface, (20, 24, 28), (lx, LETTER_H+28), (lx-70, HEIGHT-LETTER_H-30), 5)
        _draw_biribel_soldier_closeup(surface, WIDTH//2, HEIGHT//2 - 20, t, scale=1.1)
        # windshield rain highlights
        for i in range(18):
            x = 120 + i * 47 + int(math.sin(t*.03+i)*8)
            pygame.draw.line(surface, (130, 150, 175, 45), (x, LETTER_H+40), (x-40, HEIGHT-LETTER_H-50), 1)
        _escape_subtitle(surface, "BIRIBEL", "Hold on.", 255)
    elif t < 500:
        # Clear readable side-view escape: truck starts, bursts through service gate, drives right.
        prog = (t - 300) / 200.0
        ease = 1 - (1 - max(0.0, min(1.0, prog))) ** 3
        ground_y = HEIGHT - LETTER_H - 118
        scroll = int(ease * 260)
        # Sky / rain / warehouse exterior.
        pygame.draw.rect(surface, (13, 15, 20), (0, LETTER_H, WIDTH, ground_y - LETTER_H))
        pygame.draw.rect(surface, (34, 31, 28), (-scroll, LETTER_H + 42, WIDTH + 340, ground_y - LETTER_H - 42))
        # Warehouse panels and grime.
        for x in range(-scroll - 80, WIDTH + 260, 110):
            pygame.draw.rect(surface, (27, 25, 23), (x, LETTER_H + 42, 104, ground_y - LETTER_H - 42), 1)
            pygame.draw.line(surface, (45, 38, 32), (x + 104, LETTER_H + 42), (x + 104, ground_y), 1)
        # Service gate behind truck, clearly breaking open.
        gate_x = 90 - scroll
        gate_y = LETTER_H + 92
        gate_w, gate_h = 260, 185
        pygame.draw.rect(surface, (8, 9, 10), (gate_x, gate_y, gate_w, gate_h))
        pygame.draw.rect(surface, (90, 72, 54), (gate_x, gate_y, gate_w, gate_h), 4)
        for i in range(8):
            gx = gate_x + i * (gate_w // 8)
            bend = int(ease * (20 if i % 2 == 0 else -14))
            pygame.draw.line(surface, (82, 68, 52), (gx, gate_y), (gx + bend, gate_y + gate_h), 3)
        gate_lbl = font_terminal_small.render("SERVICE GATE", True, (135, 120, 95))
        surface.blit(gate_lbl, (gate_x + gate_w//2 - gate_lbl.get_width()//2, gate_y - 24))
        # Ground / wet road.
        pygame.draw.rect(surface, (10, 12, 14), (0, ground_y, WIDTH, HEIGHT - LETTER_H - ground_y))
        for y in range(ground_y + 12, HEIGHT - LETTER_H, 28):
            pygame.draw.line(surface, (30, 40, 50), (0, y), (WIDTH, y), 1)
        # Puddles and reflections.
        rng_p = random.Random(77)
        for i in range(12):
            px = (rng_p.randint(0, WIDTH + 260) - scroll * 2) % (WIDTH + 220) - 110
            py = ground_y + rng_p.randint(18, 86)
            pygame.draw.ellipse(surface, (20, 28, 38, 130), (px, py, rng_p.randint(45, 100), rng_p.randint(8, 18)))
        # Big readable side-view truck.
        # Drive fully off-screen by the end of the shot; previously it lingered in frame.
        truck_x = int(_lerp(140, WIDTH + 235, ease))
        truck_y = ground_y - 28 + int(math.sin(t * 0.19) * 2)
        # Headlight beam
        beam = pygame.Surface((330, 135), pygame.SRCALPHA)
        pygame.draw.polygon(beam, (255, 225, 145, 48), [(0, 48), (325, 6), (325, 126), (0, 82)])
        surface.blit(beam, (truck_x + 104, truck_y - 74))
        # Motion / rain spray trail
        for i in range(22):
            mx = truck_x - 25 - i * int(28 + 18 * ease)
            my = truck_y + 38 + random.Random(i + t // 2).randint(-16, 24)
            pygame.draw.line(surface, (100, 128, 150, 80), (mx, my), (mx - 44, my + 5), 2)
        # Truck shadow
        pygame.draw.ellipse(surface, (0, 0, 0, 120), (truck_x - 112, truck_y + 46, 245, 38))
        # Cargo body
        pygame.draw.rect(surface, (28, 39, 28), (truck_x - 106, truck_y - 32, 156, 72), border_radius=5)
        pygame.draw.rect(surface, (72, 84, 62), (truck_x - 106, truck_y - 32, 156, 72), 3, border_radius=5)
        pygame.draw.rect(surface, (18, 25, 18), (truck_x - 92, truck_y - 19, 96, 43), border_radius=3)
        pygame.draw.line(surface, C_KRAP_BLUE, (truck_x - 88, truck_y - 8), (truck_x - 2, truck_y - 8), 5)
        pygame.draw.line(surface, (210, 210, 205), (truck_x - 88, truck_y - 1), (truck_x - 2, truck_y - 1), 1)
        # Cab
        cab_pts = [(truck_x + 45, truck_y - 32), (truck_x + 93, truck_y - 28), (truck_x + 116, truck_y + 0), (truck_x + 106, truck_y + 40), (truck_x + 46, truck_y + 40)]
        pygame.draw.polygon(surface, (36, 50, 36), cab_pts)
        pygame.draw.polygon(surface, (80, 94, 70), cab_pts, 2)
        pygame.draw.polygon(surface, (24, 42, 52), [(truck_x + 58, truck_y - 20), (truck_x + 88, truck_y - 17), (truck_x + 101, truck_y + 0), (truck_x + 60, truck_y + 0)])
        # Headlights / tail lights
        pygame.draw.rect(surface, (245, 220, 130), (truck_x + 108, truck_y + 6, 9, 10))
        pygame.draw.rect(surface, (180, 35, 28), (truck_x - 111, truck_y - 16, 6, 12))
        pygame.draw.rect(surface, (180, 35, 28), (truck_x - 111, truck_y + 19, 6, 12))
        # Wheels, very obvious.
        for wx in (truck_x - 70, truck_x - 10, truck_x + 76):
            pygame.draw.circle(surface, (5, 6, 7), (wx, truck_y + 44), 23)
            pygame.draw.circle(surface, (46, 50, 50), (wx, truck_y + 44), 12)
            spoke_ang = t * 0.22
            for sp in range(4):
                a = spoke_ang + sp * math.pi / 2
                pygame.draw.line(surface, (85, 88, 84), (wx, truck_y + 44), (wx + math.cos(a)*11, truck_y + 44 + math.sin(a)*11), 2)
        # Shards from gate
        if t < 390:
            rng_s = random.Random(800 + t // 3)
            for i in range(20):
                sx = gate_x + gate_w - 30 + rng_s.randint(-15, 70) + int((t-300)*1.4)
                sy = gate_y + rng_s.randint(10, gate_h - 8) + int((t-300)*0.25)
                pygame.draw.rect(surface, (95, 78, 56), (sx, sy, rng_s.randint(4, 12), rng_s.randint(2, 7)))
        # Clear text overlay for readability.
        banner = font_terminal.render("ESCAPE TRUCK MOVING", True, (255, 180, 70))
        bg = pygame.Surface((banner.get_width()+28, banner.get_height()+10), pygame.SRCALPHA)
        bg.fill((0, 0, 0, 150))
        pygame.draw.rect(bg, (255, 180, 70, 120), bg.get_rect(), 1)
        surface.blit(bg, (WIDTH//2 - bg.get_width()//2, LETTER_H + 24))
        surface.blit(banner, (WIDTH//2 - banner.get_width()//2, LETTER_H + 29))
        if t < 372:
            _escape_subtitle(surface, "BIRIBEL", "Go, go, go!", 255)
    else:
        # Clear rear-view escape: visible truck body, tail-lights, road, warehouse glow behind.
        prog = min(1.0, (t - 500) / 160.0)
        horizon = LETTER_H + 120
        road_bot = HEIGHT - LETTER_H
        pygame.draw.rect(surface, (6, 8, 12), (0, LETTER_H, WIDTH, HEIGHT - 2*LETTER_H))
        # Distant warehouse / fire glow behind.
        pygame.draw.rect(surface, (24, 21, 19), (0, horizon - 52, WIDTH, 70))
        for i, x in enumerate((110, 210, 805, 900)):
            glow = pygame.Surface((170, 120), pygame.SRCALPHA)
            a = 30 + int(22 * math.sin(t*0.04 + i))
            pygame.draw.ellipse(glow, (255, 105, 30, max(12, a)), glow.get_rect())
            surface.blit(glow, (x, horizon - 82))
        # Road in perspective.
        road = [(WIDTH//2-78, horizon), (WIDTH//2+78, horizon), (WIDTH+180, road_bot), (-180, road_bot)]
        pygame.draw.polygon(surface, (10, 12, 16), road)
        for i in range(8):
            frac = i / 7
            y = int(horizon + frac*frac*(road_bot-horizon))
            pygame.draw.line(surface, (32, 42, 52), (0, y), (WIDTH, y), 1)
        pygame.draw.line(surface, (82, 82, 70), (WIDTH//2, horizon), (WIDTH//2-150, road_bot), 2)
        pygame.draw.line(surface, (82, 82, 70), (WIDTH//2, horizon), (WIDTH//2+150, road_bot), 2)
        # Draw visible rear truck shrinking into distance.
        # Stay locked to the perspective road centerline; only tiny suspension sway.
        tx = int(WIDTH // 2 + math.sin(t * 0.045) * (5 * (1.0 - prog)))
        ty = int(_lerp(road_bot - 88, horizon + 38, prog))
        sc = _lerp(1.12, 0.36, prog)
        tw = int(122 * sc)
        th = int(76 * sc)
        pygame.draw.ellipse(surface, (0, 0, 0, 120), (tx - tw//2, ty + int(th*0.38), tw, max(8, int(22*sc))))
        pygame.draw.rect(surface, (24, 35, 25), (tx - tw//2, ty - th//2, tw, th), border_radius=max(2, int(5*sc)))
        pygame.draw.rect(surface, (70, 84, 62), (tx - tw//2, ty - th//2, tw, th), max(1, int(2*sc)), border_radius=max(2, int(5*sc)))
        pygame.draw.rect(surface, (15, 22, 18), (tx - int(42*sc), ty - int(24*sc), int(84*sc), int(36*sc)), border_radius=max(1, int(3*sc)))
        # Rear windows/tail lights
        pygame.draw.rect(surface, (18, 28, 36), (tx - int(28*sc), ty - int(18*sc), int(18*sc), int(16*sc)))
        pygame.draw.rect(surface, (18, 28, 36), (tx + int(10*sc), ty - int(18*sc), int(18*sc), int(16*sc)))
        for side in (-1, 1):
            lx = tx + side * int(43*sc)
            ly = ty + int(20*sc)
            pygame.draw.rect(surface, (220, 35, 28), (lx - int(6*sc), ly - int(5*sc), max(3, int(12*sc)), max(3, int(10*sc))))
            refl = pygame.Surface((max(8, int(45*sc)), max(18, int(130*sc))), pygame.SRCALPHA)
            pygame.draw.ellipse(refl, (220, 35, 28, int(85*(1-prog))), refl.get_rect())
            surface.blit(refl, (lx - refl.get_width()//2, ly + int(7*sc)))
        fog = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        fog.fill((18, 24, 32, int(70 * prog)))
        surface.blit(fog, (0, 0))
        loc = font_location_sub.render("KILEMENO HARBOR ROAD  ·  03:17", True, (165, 165, 150))
        loc.set_alpha(min(255, max(0, (t-520)*4)))
        surface.blit(loc, (WIDTH//2 - loc.get_width()//2, LETTER_H + 34))
        if t > 570:
            _escape_subtitle(surface, "RADIO", "Signal clear. They're away.", min(255, (t-570)*5))
    # Polished handoff to the results screen:
    # 1) long radio acquisition hold, 2) slower signal corruption, 3) readable report boot card.
    if t > 620:
        # Phase 1: keep the road visible and hold the radio acquisition long enough to read.
        acq_alpha = min(230, max(0, int((t - 620) * 3)))
        if t < 720:
            readout = pygame.Surface((500, 70), pygame.SRCALPHA)
            readout.fill((0, 0, 0, min(175, acq_alpha)))
            pygame.draw.rect(readout, (50, 110, 150, min(165, acq_alpha)), readout.get_rect(), 1)
            pygame.draw.rect(readout, C_KRAP_BLUE, (0, 0, 4, readout.get_height()))
            r1 = font_terminal.render("RADIO SIGNAL ACQUIRED", True, (90, 170, 220))
            r2 = font_terminal_small.render("exfil confirmed / packetizing field report", True, (165, 150, 125))
            r1.set_alpha(acq_alpha)
            r2.set_alpha(acq_alpha)
            surface.blit(readout, (WIDTH // 2 - 250, LETTER_H + 70))
            surface.blit(r1, (WIDTH // 2 - r1.get_width() // 2, LETTER_H + 84))
            surface.blit(r2, (WIDTH // 2 - r2.get_width() // 2, LETTER_H + 116))
        # Phase 2: signal tears slowly take over the road image.
        if t >= 700:
            glitch_t = min(1.0, (t - 700) / 110.0)
            rng_g = random.Random(8800 + t)
            for _ in range(4 + int(glitch_t * 16)):
                gy = rng_g.randint(LETTER_H, HEIGHT - LETTER_H)
                gh = rng_g.randint(2, 10)
                strip = pygame.Surface((WIDTH, gh), pygame.SRCALPHA)
                col = rng_g.choice([(70, 160, 220), (255, 130, 50), (230, 230, 220)])
                strip.fill((*col, rng_g.randint(16, 70)))
                surface.blit(strip, (rng_g.randint(-35, 35), gy))
            for _ in range(int(45 * glitch_t)):
                sx = rng_g.randint(0, WIDTH - 1)
                sy = rng_g.randint(LETTER_H, HEIGHT - LETTER_H - 1)
                shade = rng_g.randint(90, 210)
                surface.set_at((sx, sy), (shade, shade, shade))
            dark = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
            dark.fill((0, 0, 0, int(145 * glitch_t)))
            surface.blit(dark, (0, 0))
        # Phase 3: report receiver card has a much slower boot/read time.
        if t >= 790:
            report_t = min(1.0, (t - 790) / 120.0)
            wipe = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
            wipe.fill((2, 5, 9, int(235 * report_t)))
            surface.blit(wipe, (0, 0))
            card_w, card_h = 600, 240
            card_x = WIDTH // 2 - card_w // 2
            card_y = HEIGHT // 2 - card_h // 2
            card_alpha = int(255 * report_t)
            card = pygame.Surface((card_w, card_h), pygame.SRCALPHA)
            card.fill((5, 11, 18, min(238, card_alpha)))
            pygame.draw.rect(card, (45, 88, 126, min(180, card_alpha)), card.get_rect(), 1)
            pygame.draw.rect(card, C_KRAP_BLUE, (0, 0, 5, card_h))
            pygame.draw.line(card, (45, 88, 126, min(120, card_alpha)), (22, 62), (card_w - 22, 62), 1)
            surface.blit(card, (card_x, card_y))
            def _fade_text(surf, x, y, a=card_alpha):
                surf.set_alpha(max(0, min(255, int(a))))
                surface.blit(surf, (x, y))
            eyebrow = font_terminal_small.render("KRAP ARCHIVE LINK ESTABLISHED", True, (80, 160, 215))
            _fade_text(eyebrow, card_x + 24, card_y + 22, min(card_alpha, max(0, (t - 790) * 5)))
            stamp = font_terminal_small.render("EXFIL CONFIRMED", True, (80, 220, 135))
            _fade_text(stamp, card_x + card_w - stamp.get_width() - 24, card_y + 22, min(card_alpha, max(0, (t - 815) * 5)))
            title = font_terminal.render("FIELD REPORT RECEIVED", True, (220, 222, 210))
            _fade_text(title, card_x + 38, card_y + 88, min(card_alpha, max(0, (t - 835) * 5)))
            sub = font_prompt.render("OPERATION BLACK NOTEBOOK  /  UPLOADING AFTER ACTION REPORT", True, (170, 160, 130))
            _fade_text(sub, card_x + 38, card_y + 126, min(card_alpha, max(0, (t - 855) * 5)))
            bar_w, bar_h = card_w - 76, 6
            bx = card_x + 38
            by = card_y + 178
            pygame.draw.rect(surface, (12, 20, 28), (bx, by, bar_w, bar_h))
            # Deliberately slow upload fill so the player can actually read the report handoff.
            upload_t = min(1.0, max(0.0, (t - 850) / 170.0))
            pygame.draw.rect(surface, C_KRAP_BLUE, (bx, by, int(bar_w * upload_t), bar_h))
            pct = font_terminal_small.render(f"UPLOAD {int(upload_t * 100):03d}%", True, (95, 135, 165))
            _fade_text(pct, bx + bar_w - pct.get_width(), by + 12, min(card_alpha, max(0, (t - 850) * 4)))
            if t > 1025:
                ready_alpha = min(255, (t - 1025) * 7)
                ready = font_terminal_small.render("REPORT READY", True, C_ORANGE)
                _fade_text(ready, card_x + card_w // 2 - ready.get_width() // 2, card_y + 202, ready_alpha)
    draw_vignette(surface, strength=185)
    draw_scanlines(surface)
    draw_letterbox(surface)
def game_draw(fcx: float, fcy: float) -> None:
    screen.fill(C_BG_GAME)
    start_tx = int(fcx // FLOOR_TILE_SIZE) * FLOOR_TILE_SIZE
    start_ty = int(fcy // FLOOR_TILE_SIZE) * FLOOR_TILE_SIZE
    warehouse_y_start = 11 * TILE_SIZE
    warehouse_y_end = 20 * TILE_SIZE
    for tx in range(
        start_tx - FLOOR_TILE_SIZE,
        int(fcx + WIDTH + FLOOR_TILE_SIZE * 2),
        FLOOR_TILE_SIZE,
    ):
        for ty in range(
            start_ty - FLOOR_TILE_SIZE,
            int(fcy + HEIGHT + FLOOR_TILE_SIZE * 2),
            FLOOR_TILE_SIZE,
        ):
            tile = (
                FLOOR_TILE
                if (warehouse_y_start <= ty <= warehouse_y_end)
                else SLUM_FLOOR
            )
            screen.blit(tile, (tx - fcx, ty - fcy))
    container_tiles = [
        CONTAINER_TILE_RED,
        CONTAINER_TILE_BLUE,
        CONTAINER_TILE_RUST,
        CONTAINER_TILE_GREY,
    ]
    for wall in STATE.walls:
        dr = pygame.Rect(wall.x - fcx, wall.y - fcy, TILE_SIZE, TILE_SIZE)
        screen.blit(wall_shadow, (dr.x - 4, dr.y - 4))
        col = wall.x // TILE_SIZE
        row = wall.y // TILE_SIZE
        if (col, row) in STATE.warehouse_walls_set:
            screen.blit(WAREHOUSE_WALL, (dr.x, dr.y))
        else:
            tile_idx = (col + row) % 4
            screen.blit(container_tiles[tile_idx], (dr.x, dr.y))
    for marker in STATE.breach_markers[:]:
        mx, my, timer = marker
        mx -= fcx
        my -= fcy
        if -50 < mx < WIDTH + 50 and -50 < my < HEIGHT + 50:
            alpha = min(255, timer * 2)
            for i in range(3):
                radius = 8 + i * 4
                s = get_glow(radius, (255, 80, 20), 255)
                s.set_alpha(alpha // (i + 1))
                screen.blit(s, (mx - radius, my - radius))
        marker[2] -= 1
        if marker[2] <= 0:
            STATE.breach_markers.remove(marker)
    for desk in STATE.desks:
        dx = desk["x"] - fcx
        dy = desk["y"] - fcy
        if -50 < dx < WIDTH + 50 and -50 < dy < HEIGHT + 50:
            # ── Desk shadow ──
            shad = pygame.Surface((72, 54), pygame.SRCALPHA)
            pygame.draw.rect(shad, (0, 0, 0, 45), (0, 0, 72, 54), border_radius=3)
            screen.blit(shad, (dx - 34, dy - 23))
            # ── Desk surface ──
            pygame.draw.rect(screen, (70, 52, 32), (dx - 32, dy - 22, 64, 46), border_radius=2)
            # wood grain lines
            for gi in range(4):
                gy = dy - 18 + gi * 10
                pygame.draw.line(screen, (62, 46, 28), (dx - 30, gy), (dx + 30, gy), 1)
            pygame.draw.rect(screen, (95, 72, 44), (dx - 32, dy - 22, 64, 46), 1, border_radius=2)
            # ── Desk legs (visible corners in top-down) ──
            for lx2, ly2 in [(-28, -18), (24, -18), (-28, 18), (24, 18)]:
                pygame.draw.rect(screen, (48, 36, 22), (dx + lx2, dy + ly2, 6, 6))
            # ── Papers / scattered docs on desk ──
            pygame.draw.rect(screen, (220, 215, 200), (dx - 20, dy - 14, 28, 20), border_radius=1)
            pygame.draw.rect(screen, (200, 195, 178), (dx - 20, dy - 14, 28, 20), 1, border_radius=1)
            for li in range(3):
                pygame.draw.line(screen, (140, 135, 120), (dx - 16, dy - 8 + li * 5), (dx + 4, dy - 8 + li * 5), 1)
            # ── Folded note / envelope ──
            pygame.draw.rect(screen, (230, 220, 190), (dx + 6, dy - 6, 18, 14), border_radius=1)
            pygame.draw.line(screen, (190, 180, 155), (dx + 6, dy - 6), (dx + 15, dy + 1), 1)
            pygame.draw.line(screen, (190, 180, 155), (dx + 24, dy - 6), (dx + 15, dy + 1), 1)
            # ── Coffee mug ──
            pygame.draw.circle(screen, (42, 32, 24), (dx + 22, dy + 12), 7)
            pygame.draw.circle(screen, (58, 44, 30), (dx + 22, dy + 12), 7, 1)
            pygame.draw.circle(screen, (80, 55, 20), (dx + 22, dy + 12), 4)  # coffee inside
            # ── Unread/read indicator dot ──
            dot_col = (100, 220, 100) if desk["read"] else (240, 190, 50)
            glow2 = get_glow(7, dot_col, 70)
            screen.blit(glow2, (dx - 3, dy - 21))
            pygame.draw.circle(screen, dot_col, (dx, dy - 14), 4)
            label = font_terminal_small.render("DESK", True, (150, 140, 120))
            screen.blit(label, (dx - label.get_width() // 2, dy + 28))
    bay_x = 15 * TILE_SIZE + 32 - fcx
    bay_y = 19 * TILE_SIZE + 32 - fcy
    if -50 < bay_x < WIDTH + 50 and -50 < bay_y < HEIGHT + 50:
        label = font_terminal_small.render("BAY DOOR", True, (150, 140, 120))
        screen.blit(label, (bay_x - label.get_width() // 2, bay_y - 40))
    left_bay = None
    for d in STATE.doors:
        if d.is_bay and (left_bay is None or d.rect.x < left_bay.rect.x):
            left_bay = d
    for d in STATE.doors:
        dr = pygame.Rect(d.rect.x - fcx, d.rect.y - fcy, TILE_SIZE, TILE_SIZE)
        if d.is_bay:
            if d is not left_bay:
                if STATE.player and not STATE.player_dead:
                    pdist = math.hypot(
                        STATE.player.rect.centerx - d.rect.centerx,
                        STATE.player.rect.centery - d.rect.centery,
                    )
                    if pdist <= DOOR_INTERACT_RANGE:
                        prompt = font_terminal_small.render("[E]", True, C_TERMINAL)
                        screen.blit(
                            prompt,
                            (
                                dr.x + TILE_SIZE // 2 - prompt.get_width() // 2,
                                dr.y - 18,
                            ),
                        )
                continue
            bw = TILE_SIZE * 3
            bdr = pygame.Rect(d.rect.x - fcx, d.rect.y - fcy, bw, TILE_SIZE)
            if d.anim_progress < 1.0:
                draw_h = int(TILE_SIZE * (1.0 - d.anim_progress))
                src = pygame.Rect(0, 0, bw, draw_h)
                screen.blit(bay_door_shadow, (bdr.x - 4, bdr.y - 4))
                screen.blit(BAY_DOOR_TILE_3W, (bdr.x, bdr.y), src)
            else:
                screen.blit(BAY_DOOR_FRAME_3W, (bdr.x, bdr.y))
            if STATE.player and not STATE.player_dead:
                pdist = math.hypot(
                    STATE.player.rect.centerx - d.rect.centerx,
                    STATE.player.rect.centery - d.rect.centery,
                )
                if pdist <= DOOR_INTERACT_RANGE:
                    prompt = font_terminal_small.render("[E]", True, C_TERMINAL)
                    screen.blit(
                        prompt, (bdr.x + bw // 2 - prompt.get_width() // 2, bdr.y - 18)
                    )
        else:
            door_tile = DOOR_TILE
            door_frame = DOOR_FRAME_TILE
            if d.anim_progress < 1.0:
                draw_h = int(TILE_SIZE * (1.0 - d.anim_progress))
                src = pygame.Rect(0, 0, TILE_SIZE, draw_h)
                screen.blit(wall_shadow, (dr.x - 4, dr.y - 4))
                screen.blit(door_tile, (dr.x, dr.y), src)
            else:
                screen.blit(door_frame, (dr.x, dr.y))
            if STATE.player and not STATE.player_dead:
                pdist = math.hypot(
                    STATE.player.rect.centerx - d.rect.centerx,
                    STATE.player.rect.centery - d.rect.centery,
                )
                if pdist <= DOOR_INTERACT_RANGE:
                    prompt = font_terminal_small.render("[E]", True, C_TERMINAL)
                    screen.blit(
                        prompt,
                        (dr.x + TILE_SIZE // 2 - prompt.get_width() // 2, dr.y - 18),
                    )
    for decal in STATE.blood_decals[:]:
        d_surf = get_blood_decal(decal[3])
        d_surf.set_alpha(int(decal[2]))
        screen.blit(d_surf, (decal[0] - decal[3] - fcx, decal[1] - decal[3] - fcy))
        decal[2] -= 0.5
        if decal[2] <= 0:
            STATE.blood_decals.remove(decal)
    # Draw fire zones
    for fz in STATE.fire_zones:
        fz.draw(screen, fcx, fcy)
    # Shared bullet renderer (glow + sharp core + motion trail).
    draw_bullets(screen, STATE.bullets, fcx, fcy, with_glow=True)
    # ── Thrown bottles (in flight) ──
    for b in STATE.thrown_bottles:
        t = b["t"]
        arc_height = 40
        arc_y_off = -math.sin(t * math.pi) * arc_height
        bx = b["x"] - fcx
        by = b["y"] - fcy + arc_y_off
        shadow_alpha = int(60 * (1 - abs(arc_y_off / arc_height)))
        shadow_surf = get_shadow(14, 5, 'ellipse', alpha=255)
        shadow_surf.set_alpha(shadow_alpha)
        screen.blit(shadow_surf, (int(bx - 7), int(b["y"] - fcy - 2)))
        rot = b.get("spin", 0) + t * 900
        cos_r = math.cos(math.radians(rot))
        sin_r = math.sin(math.radians(rot))
        def _rot(lx, ly):
            return (
                bx + lx * cos_r - ly * sin_r,
                by + lx * sin_r + ly * cos_r,
            )
        # Molotov bottle silhouette
        bottle_pts = [
            _rot(-2.5, -12), _rot(2.5, -12),
            _rot(2.5, -8),
            _rot(1.5, -5),
            _rot(4.5, 0),
            _rot(4.5, 12),
            _rot(-4.5, 12),
            _rot(-4.5, 0),
            _rot(-1.5, -5),
            _rot(-2.5, -8),
        ]
        pygame.draw.polygon(screen, (95, 70, 35), bottle_pts)
        pygame.draw.polygon(screen, (210, 150, 60), bottle_pts, 1)
        pygame.draw.line(screen, (255, 120, 35), _rot(0, 1), _rot(0, 10), 3)
        pygame.draw.line(screen, (255, 210, 110), _rot(-2.5, 0), _rot(-2.5, 8), 1)
        pygame.draw.line(screen, (70, 55, 35), _rot(0, -13), _rot(0, -19), 3)
        flame_tip = _rot(0, -27)
        flame_l = _rot(-5, -17)
        flame_r = _rot(5, -17)
        flame_mid_l = _rot(-2.5, -18)
        flame_mid_r = _rot(2.5, -18)
        flame_mid_t = _rot(0, -24)
        flame_glow = get_glow(15, (255, 100, 20), 80)
        screen.blit(flame_glow, (int(flame_tip[0] - 17), int(flame_tip[1] - 17)))
        pygame.draw.polygon(screen, (255, 80, 15), [flame_tip, flame_l, flame_r])
        pygame.draw.polygon(screen, (255, 220, 80), [flame_mid_t, flame_mid_l, flame_mid_r])
        for trail_i in range(5):
            trail_t = max(0, t - 0.025 * (trail_i + 1))
            trail_arc = -math.sin(trail_t * math.pi) * arc_height
            trail_x = b["start_x"] + (b["tx"] - b["start_x"]) * trail_t - fcx
            trail_y = b["start_y"] + (b["ty"] - b["start_y"]) * trail_t - fcy + trail_arc
            ta = 110 - trail_i * 18
            ts = pygame.Surface((10, 10), pygame.SRCALPHA)
            if trail_i < 2:
                pygame.draw.circle(ts, (255, 120, 30, ta), (5, 5), 4)
            else:
                pygame.draw.circle(ts, (70, 65, 60, ta), (5, 5), 4)
            screen.blit(ts, (int(trail_x - 5), int(trail_y - 5)))
    if STATE.firefight_triggered and STATE.volkov_escape_timer > 0:
        if STATE.volkov_escape_pos and not STATE.volkov_escaped:
            vx = STATE.volkov_escape_pos[0] - fcx
            vy = STATE.volkov_escape_pos[1] - fcy + 30
            if -100 < vx < WIDTH + 100 and -100 < vy < HEIGHT + 100:
                facing = STATE.volkov_escape_pos[0] < (15 * TILE_SIZE + 32)
                draw_volkov(screen, int(vx), int(vy), scale=0.35, facing_right=facing)
        if STATE.commander_escape_pos and not STATE.commander_escaped:
            kx = STATE.commander_escape_pos[0] - fcx
            ky = STATE.commander_escape_pos[1] - fcy + 30
            if -100 < kx < WIDTH + 100 and -100 < ky < HEIGHT + 100:
                facing = STATE.commander_escape_pos[0] < (15 * TILE_SIZE + 32)
                draw_commander(
                    screen, int(kx), int(ky), scale=0.35, facing_right=facing
                )
    for e in STATE.enemies:
        e.draw(screen, fcx, fcy)
    reload_progress = 0.0
    if STATE.is_reloading and STATE.reload_timer > 0:
        reload_progress = 1.0 - STATE.reload_timer / 60.0
    melee_progress = 0.0
    if STATE.melee_active and STATE.melee_timer > 0:
        melee_progress = 1.0 - STATE.melee_timer / 18.0
    if STATE.player:
        # During the death animation, skip the standing player draw — the
        # fallen-body silhouette is drawn by death_anim.draw_death_overlay().
        import death_anim
        if not death_anim.should_skip_player_draw():
            STATE.player.draw(
                screen,
                fcx,
                fcy,
                STATE.walls,
                STATE.is_reloading,
                reload_progress,
                STATE.melee_active,
                melee_progress,
                is_moving=not STATE.player_dead and (
                    _last_keys and (
                        _last_keys[pygame.K_w] or _last_keys[pygame.K_s] or
                        _last_keys[pygame.K_a] or _last_keys[pygame.K_d]
                    )
                ),
            )
    for p in STATE.particles:
        p.draw(screen, fcx, fcy)
    for c in STATE.casings:
        c.draw(screen, fcx, fcy)
    for pu in STATE.pickups:
        px = pu[0] - fcx
        py = pu[1] - fcy + math.sin(time.time() * 3 + pu[0]) * 3
        if pu[2] == "bandage":
            glow_col = (100, 255, 100)
        elif pu[2] == "bottle":
            glow_col = (100, 200, 130)
        else:
            glow_col = (255, 210, 40)
        glow = get_glow(16, glow_col, 40)
        screen.blit(glow, (int(px - 16), int(py - 16)))
        if pu[2] == "mag":
            top_w, bot_w, h = 14, 11, 24
            taper = (top_w - bot_w) // 2
            mg_pts = [
                (px - top_w // 2, py - h // 2),
                (px + top_w // 2, py - h // 2),
                (px + taper + bot_w // 2, py + h // 2),
                (px + taper - bot_w // 2, py + h // 2),
            ]
            pygame.draw.polygon(screen, (100, 95, 87), mg_pts)
            pygame.draw.polygon(screen, (255, 210, 40), mg_pts, 1)
            for bi in range(5):
                by = py - h // 2 + 5 + bi * 3
                pygame.draw.circle(screen, (220, 185, 45), (px, by), 2)
        elif pu[2] == "keycard":
            pygame.draw.rect(screen, (200, 200, 200), (px - 8, py - 12, 16, 24))
            pygame.draw.rect(screen, (255, 50, 50), (px - 8, py - 6, 16, 6))
            pygame.draw.rect(screen, (100, 100, 100), (px - 8, py - 12, 16, 24), 1)
        elif pu[2] == "bandage":
            pygame.draw.rect(
                screen, (240, 240, 240), (px - 10, py - 10, 20, 20), border_radius=3
            )
            pygame.draw.rect(
                screen, (180, 180, 180), (px - 10, py - 10, 20, 20), 1, border_radius=3
            )
            pygame.draw.rect(screen, (220, 40, 40), (px - 2, py - 6, 4, 12))
            pygame.draw.rect(screen, (220, 40, 40), (px - 6, py - 2, 12, 4))
        elif pu[2] == "bottle":
            pygame.draw.rect(screen, (60, 60, 60), (px - 2, py - 12, 4, 2))
            pygame.draw.rect(screen, (80, 55, 25), (px - 1, py - 10, 2, 4))
            pygame.draw.rect(screen, (115, 75, 35), (px - 5, py - 6, 10, 16), border_radius=2)
            pygame.draw.rect(screen, (255, 155, 55), (px - 3, py - 4, 2, 12))
            pygame.draw.rect(screen, (50, 30, 15), (px - 5, py - 6, 10, 16), 1, border_radius=2)
    if STATE.firefight_triggered and not STATE.notebook_collected and STATE.NOTEBOOK_POS:
        nx = STATE.NOTEBOOK_POS[0] - fcx
        ny = STATE.NOTEBOOK_POS[1] - fcy + math.sin(time.time() * 2) * 3
        glow = get_glow(18, (255, 220, 100))
        pulse = int(60 + math.sin(time.time() * 4) * 30)
        glow.set_alpha(pulse)
        screen.blit(glow, (int(nx - 20), int(ny - 20)))
        pygame.draw.rect(screen, (15, 15, 15), (nx - 8, ny - 10, 16, 20))
        pygame.draw.rect(screen, (40, 40, 40), (nx - 8, ny - 10, 16, 20), 1)
        pygame.draw.line(screen, (40, 40, 40), (nx, ny - 10), (nx, ny + 10), 1)
        if (
            STATE.player
            and math.hypot(
                STATE.player.rect.centerx - STATE.NOTEBOOK_POS[0],
                STATE.player.rect.centery - STATE.NOTEBOOK_POS[1],
            )
            < 80
        ):
            nearby = [
                e
                for e in STATE.enemies
                if math.hypot(
                    e.rect.centerx - STATE.NOTEBOOK_POS[0], e.rect.centery - STATE.NOTEBOOK_POS[1]
                )
                < 300
            ]
            if len(nearby) == 0:
                txt = font_prompt.render("WALK OVER TO COLLECT", True, (255, 220, 100))
            else:
                txt = font_prompt.render("CLEAR HOSTILES FIRST", True, (220, 60, 60))
            screen.blit(txt, (int(nx) - txt.get_width() // 2, int(ny) - 35))
    if STATE.notebook_collected and STATE.EXFIL_POS:
        ex = STATE.EXFIL_POS[0] - fcx
        ey = STATE.EXFIL_POS[1] - fcy
        # ──── Draw top-down military truck ────
        # Body shadow
        shad_t = pygame.Surface((110, 56), pygame.SRCALPHA)
        pygame.draw.rect(shad_t, (0, 0, 0, 60), (0, 0, 110, 56), border_radius=4)
        screen.blit(shad_t, (int(ex - 53), int(ey - 26)))
        # Truck bed (cargo area) — rear 2/3
        pygame.draw.rect(screen, (45, 55, 40), (int(ex - 50), int(ey - 22), 68, 44), border_radius=2)
        # Cargo bed slat lines
        for sli in range(4):
            pygame.draw.line(screen, (35, 44, 30),
                (int(ex - 48), int(ey - 16 + sli * 10)),
                (int(ex + 16),  int(ey - 16 + sli * 10)), 1)
        # Cargo canopy / tarp stripes
        pygame.draw.rect(screen, (55, 68, 48), (int(ex - 46), int(ey - 18), 62, 36), border_radius=2)
        for ci in range(3):
            pygame.draw.line(screen, (42, 54, 36),
                (int(ex - 46 + ci * 20), int(ey - 18)),
                (int(ex - 46 + ci * 20), int(ey + 18)), 1)
        pygame.draw.rect(screen, (36, 46, 30), (int(ex - 46), int(ey - 18), 62, 36), 1, border_radius=2)
        # Cab (front box, right side — truck faces right)
        cab_x = int(ex + 18)
        pygame.draw.rect(screen, (38, 48, 34), (cab_x, int(ey - 22), 34, 44), border_radius=3)
        pygame.draw.rect(screen, (52, 62, 46), (cab_x, int(ey - 22), 34, 44), 1, border_radius=3)
        # Cab windshield (darker tinted rectangle)
        pygame.draw.rect(screen, (22, 30, 28), (cab_x + 18, int(ey - 16), 12, 32), border_radius=2)
        pygame.draw.rect(screen, (34, 44, 40), (cab_x + 18, int(ey - 16), 12, 32), 1, border_radius=2)
        # Cab dashboard strip
        pygame.draw.rect(screen, (28, 36, 26), (cab_x + 4, int(ey - 20), 14, 6))
        # Hood / engine block
        pygame.draw.rect(screen, (42, 52, 38), (cab_x + 30, int(ey - 14), 10, 28), border_radius=2)
        pygame.draw.rect(screen, (32, 40, 28), (cab_x + 30, int(ey - 14), 10, 28), 1, border_radius=2)
        # Headlights
        pygame.draw.ellipse(screen, (200, 200, 140), (cab_x + 38, int(ey - 14), 8, 6))
        pygame.draw.ellipse(screen, (200, 200, 140), (cab_x + 38, int(ey + 8),  8, 6))
        # Tail-lights (rear left)
        pygame.draw.rect(screen, (180, 40, 30), (int(ex - 52), int(ey - 22), 4, 8))
        pygame.draw.rect(screen, (180, 40, 30), (int(ex - 52), int(ey + 14),  4, 8))
        # Wheels (6 wheels – 3 axles visible from top)
        wheel_col = (16, 16, 18)
        rim_col   = (55, 58, 62)
        for wx, wy_pair in [
            (int(ex - 36), (int(ey - 26), int(ey + 20))),
            (int(ex +  4), (int(ey - 26), int(ey + 20))),
            (int(ex + 28), (int(ey - 26), int(ey + 20))),
        ]:
            for wy in wy_pair:
                pygame.draw.ellipse(screen, wheel_col, (wx - 7, wy - 4, 14, 8))
                pygame.draw.ellipse(screen, rim_col,   (wx - 4, wy - 2,  8, 5))
        # KRAP marking on cab door
        krap_lbl = font_terminal_small.render("KRAP", True, C_KRAP_BLUE)
        screen.blit(krap_lbl, (cab_x + 2, int(ey - 6)))
        # ──── Exfil pulsing ring and label (above truck) ────
        pulse = int(80 + math.sin(time.time() * 3) * 40)
        circle_surf = pygame.Surface((100, 100), pygame.SRCALPHA)
        pygame.draw.circle(circle_surf, (50, 200, 100, pulse), (50, 50), 40, 3)
        pygame.draw.circle(circle_surf, (50, 200, 100, pulse // 2), (50, 50), 30, 2)
        screen.blit(circle_surf, (int(ex - 50), int(ey - 50)))
        ext = font_prompt.render("EXFIL", True, (50, 200, 100))
        screen.blit(ext, (int(ex) - ext.get_width() // 2, int(ey) - 72))
        if (
            STATE.player
            and math.hypot(
                STATE.player.rect.centerx - STATE.EXFIL_POS[0], STATE.player.rect.centery - STATE.EXFIL_POS[1]
            )
            < 80
        ):
            if not STATE.truck_hotwiring:
                if STATE.enemies:
                    prompt_txt = font_prompt.render(
                        f"CLEAR HOSTILES FIRST [{len(STATE.enemies)} LEFT]", True, (230, 80, 60)
                    )
                else:
                    prompt_txt = font_prompt.render(
                        "[E] OPEN IGNITION PANEL", True, (100, 255, 100)
                    )
                screen.blit(
                    prompt_txt, (int(ex) - prompt_txt.get_width() // 2, int(ey) - 85)
                )
    if STATE.truck_hotwiring:
        # First-person-ish ignition panel overlay with a short open animation.
        open_t = min(1.0, getattr(STATE, "hotwire_panel_timer", 0) / 34.0)
        ease = 1 - (1 - open_t) ** 3
        overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, int(112 * ease)))
        screen.blit(overlay, (0, 0))
        panel_w, panel_h = 640, 410
        panel_x = WIDTH // 2 - panel_w // 2
        panel_y = int(HEIGHT // 2 - panel_h // 2 + (1.0 - ease) * 90)
        panel = pygame.Surface((panel_w, panel_h), pygame.SRCALPHA)
        panel.fill((10, 12, 15, 236))
        pygame.draw.rect(panel, (80, 82, 78), panel.get_rect(), 2)
        pygame.draw.rect(panel, C_KRAP_BLUE, (0, 0, 5, panel_h))
        # scratched metal plate
        rng_panel = random.Random(74)
        for _ in range(34):
            x1 = rng_panel.randint(24, panel_w - 24)
            y1 = rng_panel.randint(58, panel_h - 20)
            pygame.draw.line(panel, (30, 34, 38, 100), (x1, y1), (x1 + rng_panel.randint(8, 40), y1 + rng_panel.randint(-2, 2)), 1)
        screen.blit(panel, (panel_x, panel_y))
        title = font_terminal.render("VAN IGNITION PANEL", True, (180, 205, 210))
        screen.blit(title, (panel_x + 26, panel_y + 18))
        sub = font_terminal_small.render("Bridge the correct exposed wires. Wrong pairs short the panel.", True, (150, 150, 135))
        screen.blit(sub, (panel_x + 28, panel_y + 48))
        nodes = _hotwire_wire_nodes()
        used = {w for pair in STATE.hotwire_connections for w in pair}
        # Draw loose wire tails from side openings.
        for name, data in nodes.items():
            x, y = data["pos"]
            col = data["color"]
            side = data["side"]
            start_x = panel_x + 36 if side == "L" else panel_x + panel_w - 36
            mid_x = x - 34 if side == "L" else x + 34
            pygame.draw.line(screen, (18, 18, 20), (start_x, y + 3), (mid_x, y + 3), 7)
            pygame.draw.line(screen, col, (start_x, y), (mid_x, y), 5)
            pygame.draw.line(screen, col, (mid_x, y), (x, y), 4)
            # copper exposed tip
            pygame.draw.circle(screen, (210, 135, 70), (x, y), 9)
            pygame.draw.circle(screen, (40, 24, 12), (x, y), 9, 1)
            if name == STATE.hotwire_selected_wire:
                glow = pygame.Surface((58, 58), pygame.SRCALPHA)
                pygame.draw.circle(glow, (*col, 85), (29, 29), 26)
                screen.blit(glow, (x - 29, y - 29))
            if name in used:
                pygame.draw.circle(screen, (100, 255, 150), (x, y), 14, 2)
            label = font_terminal_small.render(name, True, col if name != "BLACK" else (120, 120, 125))
            lx = x - label.get_width() - 18 if side == "L" else x + 18
            screen.blit(label, (lx, y - 8))
        # Draw completed bridges.
        for pair in STATE.hotwire_connections:
            a, b = pair
            ax, ay = nodes[a]["pos"]
            bx, by = nodes[b]["pos"]
            pair_key = frozenset(pair)
            purpose = HOTWIRE_TARGET_PAIRS.get(pair_key, "")
            col = (95, 240, 145)
            # cable curve with three segments
            mid_y = (ay + by) // 2 - 24
            pygame.draw.line(screen, (18, 35, 24), (ax, ay), (WIDTH // 2, mid_y), 8)
            pygame.draw.line(screen, (18, 35, 24), (WIDTH // 2, mid_y), (bx, by), 8)
            pygame.draw.line(screen, col, (ax, ay), (WIDTH // 2, mid_y), 4)
            pygame.draw.line(screen, col, (WIDTH // 2, mid_y), (bx, by), 4)
            # Purpose text is shown in the status lights below; avoid center overlap.
        # Status lights.
        statuses = ["POWER", "IGNITION", "STARTER"]
        connected = {HOTWIRE_TARGET_PAIRS.get(frozenset(pair)) for pair in STATE.hotwire_connections}
        for i, st in enumerate(statuses):
            sx = panel_x + 128 + i * 150
            sy = panel_y + panel_h - 76
            live = st in connected
            pygame.draw.circle(screen, (70, 240, 120) if live else (50, 55, 55), (sx, sy), 9)
            pygame.draw.circle(screen, (10, 15, 12), (sx, sy), 9, 1)
            stxt = font_terminal_small.render(st, True, (160, 220, 170) if live else (90, 95, 95))
            screen.blit(stxt, (sx + 16, sy - 8))
        # Sparks on wrong pair / fresh connection.
        if STATE.hotwire_spark_timer > 0:
            rng_s = random.Random(pygame.time.get_ticks() // 20)
            center = nodes.get(STATE.hotwire_selected_wire or "RED", {"pos": (WIDTH // 2, HEIGHT // 2)})["pos"]
            for _ in range(18 if STATE.hotwire_fail_flash > 0 else 8):
                ang = rng_s.random() * math.tau
                dist = rng_s.randint(8, 46)
                sx = center[0] + math.cos(ang) * dist
                sy = center[1] + math.sin(ang) * dist
                pygame.draw.line(screen, (255, 210, 90), center, (sx, sy), 1)
        if STATE.hotwire_fail_flash > 0:
            flash = pygame.Surface((panel_w, panel_h), pygame.SRCALPHA)
            flash.fill((255, 55, 35, min(95, STATE.hotwire_fail_flash * 8)))
            screen.blit(flash, (panel_x, panel_y))
        msg_col = (220, 90, 70) if STATE.hotwire_fail_flash > 0 else (180, 215, 190)
        msg = font_prompt.render(STATE.hotwire_message or "Click a wire endpoint", True, msg_col)
        screen.blit(msg, (WIDTH // 2 - msg.get_width() // 2, panel_y + panel_h - 34))
        hint = font_terminal_small.render("VASILE'S HINT: red feeds yellow / blue wakes green / black bites white", True, (115, 125, 120))
        screen.blit(hint, (WIDTH // 2 - hint.get_width() // 2, panel_y + panel_h + 10))
    pinned = [ft for ft in STATE.floating_texts if len(ft) >= 6 and ft[5] == "pin"]
    unpinned = [ft for ft in STATE.floating_texts if not (len(ft) >= 6 and ft[5] == "pin")]
    for ft in unpinned:
        txt = font_terminal_small.render(ft[2], True, ft[3])
        screen.blit(txt, (ft[0] - fcx - txt.get_width() // 2, ft[1] - fcy))
    # Shared pinned-radio renderer (was 22-line inline loop; capped to last 4
    # so longer radio chatter can't overflow the bottom of the screen).
    draw_pinned_radio(screen, pinned)
    # Honor the Gameplay → Crosshair setting. The shared
    # ui_hud.draw_gameplay_crosshair() (called from acaristan.py) already
    # respects SETTINGS.show_crosshair, but this mission also draws its OWN
    # combat reticle below — gate it on the same setting so the user's
    # "Crosshair: Off" preference actually applies during gameplay.
    try:
        from user_settings import SETTINGS
        _show_ch = SETTINGS.show_crosshair
    except Exception:
        _show_ch = True
    ch_x, ch_y = get_scaled_mouse()
    if STATE.truck_hotwiring:
        # Compact pointing-hand cursor. The ACTUAL click/contact point is the
        # fingertip at (ch_x, ch_y), so it no longer feels offset.
        skin = (218, 178, 136)
        skin_hi = (238, 205, 165)
        outline = (54, 36, 24)
        glove_shadow = (120, 82, 55)
        cuff_col = (56, 68, 50)
        # soft shadow
        pygame.draw.polygon(
            screen, (0, 0, 0, 95),
            [(ch_x + 2, ch_y + 3), (ch_x - 7, ch_y + 13), (ch_x - 4, ch_y + 39),
             (ch_x - 19, ch_y + 47), (ch_x - 9, ch_y + 66), (ch_x + 22, ch_y + 62),
             (ch_x + 26, ch_y + 40), (ch_x + 10, ch_y + 34), (ch_x + 8, ch_y + 12)],
        )
        # index finger: pointed tip exactly at mouse position
        finger = [
            (ch_x, ch_y),
            (ch_x - 6, ch_y + 9),
            (ch_x - 5, ch_y + 35),
            (ch_x + 6, ch_y + 35),
            (ch_x + 7, ch_y + 9),
        ]
        pygame.draw.polygon(screen, outline, finger)
        inner_finger = [
            (ch_x, ch_y + 2),
            (ch_x - 4, ch_y + 10),
            (ch_x - 3, ch_y + 33),
            (ch_x + 4, ch_y + 33),
            (ch_x + 5, ch_y + 10),
        ]
        pygame.draw.polygon(screen, skin, inner_finger)
        pygame.draw.line(screen, skin_hi, (ch_x - 2, ch_y + 10), (ch_x - 2, ch_y + 29), 1)
        # palm
        palm = pygame.Rect(ch_x - 17, ch_y + 30, 35, 27)
        pygame.draw.rect(screen, outline, palm.inflate(4, 4), border_radius=8)
        pygame.draw.rect(screen, skin, palm, border_radius=7)
        # folded fingers
        for i, fx in enumerate((-12, -3, 6)):
            r = pygame.Rect(ch_x + fx, ch_y + 43 + (i % 2), 9, 17)
            pygame.draw.rect(screen, outline, r.inflate(2, 2), border_radius=4)
            pygame.draw.rect(screen, skin, r, border_radius=3)
            pygame.draw.line(screen, glove_shadow, (r.x + 2, r.y + 6), (r.x + r.w - 2, r.y + 6), 1)
        # thumb wrapped left
        thumb = [(ch_x - 15, ch_y + 37), (ch_x - 28, ch_y + 42), (ch_x - 26, ch_y + 54), (ch_x - 12, ch_y + 50)]
        pygame.draw.polygon(screen, outline, thumb)
        pygame.draw.polygon(screen, skin, [(ch_x - 15, ch_y + 39), (ch_x - 25, ch_y + 43), (ch_x - 23, ch_y + 51), (ch_x - 12, ch_y + 48)])
        # sleeve/cuff
        pygame.draw.rect(screen, outline, (ch_x - 13, ch_y + 59, 31, 16), border_radius=4)
        pygame.draw.rect(screen, cuff_col, (ch_x - 10, ch_y + 60, 26, 14), border_radius=3)
        pygame.draw.line(screen, (34, 42, 30), (ch_x - 8, ch_y + 64), (ch_x + 14, ch_y + 64), 1)
        # exact contact point marker on top of the fingertip
        pygame.draw.circle(screen, C_ORANGE, (ch_x, ch_y), 3, 1)
    else:
        # Combat reticle. Gated on SETTINGS.show_crosshair so the user's
        # "Crosshair: Off" preference is honored. Respects crosshair_size
        # (3=small, 6=medium, 10=large) and colorblind_mode (recolors the
        # reticle for accessibility) — same logic as the shared
        # ui_hud.draw_gameplay_crosshair(), so the two renderers match.
        if _show_ch:
            from user_settings import SETTINGS
            cb = SETTINGS.colorblind_mode
            if cb == "protanopia":
                col = (90, 180, 255)   # blue reads well for red-deficient vision
            elif cb == "deuteranopia":
                col = (255, 220, 80)   # yellow
            elif cb == "tritanopia":
                col = (255, 120, 120)  # pinkish-red
            else:
                col = C_ORANGE
            size = max(3, int(SETTINGS.crosshair_size))
            ring_r = size + 8
            arm = size + 6
            gap = max(2, size // 2)
            pygame.draw.circle(screen, col, (ch_x, ch_y), ring_r, 1)
            pygame.draw.circle(screen, col, (ch_x, ch_y), max(1, size // 3))
            for x1, y1, x2, y2 in [
                (ch_x - arm, ch_y, ch_x - gap, ch_y),
                (ch_x + gap, ch_y, ch_x + arm, ch_y),
                (ch_x, ch_y - arm, ch_x, ch_y - gap),
                (ch_x, ch_y + gap, ch_x, ch_y + arm),
            ]:
                pygame.draw.line(screen, col, (x1, y1), (x2, y2), 1)
    if STATE.muzzle_flash_timer > 0:
        if STATE.player:
            if hasattr(STATE.player, "barrel_tip"):
                tip_x, tip_y = STATE.player.barrel_tip()
            else:
                tip_x = STATE.player.rect.centerx + math.cos(STATE.player.angle) * 39
                tip_y = STATE.player.rect.centery + math.sin(STATE.player.angle) * 39
            flash_x = tip_x - fcx
            flash_y = tip_y - fcy
        else:
            flash_x, flash_y = ch_x, ch_y
        screen.blit(MUZZLE_FLASH, (int(flash_x - 40), int(flash_y - 40)))
        STATE.muzzle_flash_timer -= 1
    if STATE.player_dead:
        # Death animation overlay: blood pool, fallen body, weapon eject,
        # tinnitus. The camera tilt is applied at the very end of the frame
        # (after HUD) so the entire screen rotates including UI.
        import death_anim
        death_anim.draw_death_overlay(screen, fcx, fcy)
    if STATE.gc_flash_timer > 0 and not getattr(STATE, "reduced_motion", False):
        flash_surf = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        flash_surf.fill((255, 255, 255, min(255, STATE.gc_flash_timer * 22)))
        screen.blit(flash_surf, (0, 0))
    # ── Breach stage flicker ──
    if STATE.breach_stage in (3, 4):
        if (pygame.time.get_ticks() // 80) % 3 == 0:
            flicker = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
            flicker.fill((0, 0, 0, random.randint(40, 120)))
            screen.blit(flicker, (0, 0))
    draw_scanlines(screen)
    draw_vignette(screen)
    if STATE.player and not STATE.truck_hotwiring:
        hb_x, hb_y, hb_w, hb_h = 30, HEIGHT - 50, 160, 14
        hp_ratio = max(0.0, STATE.player.hp / STATE.player.max_hp)
        hud_bg = pygame.Surface((hb_w + 20, hb_h + 28), pygame.SRCALPHA)
        pygame.draw.rect(hud_bg, (0, 0, 0, 140), (0, 0, hb_w + 20, hb_h + 28))
        screen.blit(hud_bg, (hb_x - 10, hb_y - 16))
        screen.blit(
            font_terminal_small.render("HP", True, C_TERMINAL), (hb_x, hb_y - 14)
        )
        pygame.draw.rect(screen, (30, 30, 30), (hb_x, hb_y, hb_w, hb_h))
        if hp_ratio > 0.5:
            bar_col = (int(200 * hp_ratio), int(220 * hp_ratio), 40)
        elif hp_ratio > 0.25:
            bar_col = (220, int(200 * hp_ratio * 2), 40)
        else:
            bar_col = (220, 40, 40)
        pygame.draw.rect(screen, bar_col, (hb_x, hb_y, int(hb_w * hp_ratio), hb_h))
        pygame.draw.rect(screen, C_TERMINAL, (hb_x, hb_y, hb_w, hb_h), 1)
        # Objective text (without "OBJECTIVE:" prefix — the shared helper
        # prepends it, matching M2's behavior).
        obj_text = "Locate Volkov in the warehouse"
        if STATE.mission_phase == "firefight":
            if STATE.notebook_collected:
                obj_text = "Reach exfil"
            elif len(STATE.enemies) > 1:
                obj_text = f"Clear hostiles ({len(STATE.enemies)} remaining)"
            else:
                obj_text = "Recover the notebook"
        elif STATE.mission_phase == "escape":
            obj_text = "Reach exfil zone"
        draw_objective_panel(screen, obj_text)
        ammo_x, ammo_y = 30, hb_y - 96
        bg_w, bg_h = 246, 92
        bg = pygame.Surface((bg_w, bg_h), pygame.SRCALPHA)
        pygame.draw.rect(bg, (0, 0, 0, 140), (0, 0, bg_w, bg_h), border_radius=4)
        pygame.draw.rect(bg, (40, 42, 38), (0, 0, bg_w, bg_h), 1, border_radius=4)
        screen.blit(bg, (ammo_x - 6, ammo_y))
        for i in range(4):
            mx = ammo_x + 8 + i * 36
            my = ammo_y + 8
            is_active = i == 0
            if is_active:
                bullets_fill = min(STATE.ammo_in_mag, 12)
                is_empty = STATE.ammo_in_mag <= 0
            else:
                bullets_fill = 12 if STATE.spare_mags >= i else 0
                is_empty = STATE.spare_mags < i
            top_w, bot_w, h = 24, 20, 46
            taper = (top_w - bot_w) // 2
            body_pts = [
                (mx, my),
                (mx + top_w, my),
                (mx + taper + bot_w, my + h),
                (mx + taper, my + h),
            ]
            if is_empty:
                base = (45, 42, 38)
                hl = (55, 52, 48)
                rim = (55, 50, 45)
            elif is_active:
                base = (90, 86, 78)
                hl = (115, 110, 100)
                rim = (70, 66, 58)
            else:
                base = (72, 68, 62)
                hl = (92, 88, 80)
                rim = (60, 56, 50)
            pygame.draw.polygon(screen, base, body_pts)
            pygame.draw.polygon(
                screen,
                hl,
                [
                    (mx + 1, my + 2),
                    (mx + 5, my + 2),
                    (mx + taper + 3, my + h - 3),
                    (mx + taper + 1, my + h - 3),
                ],
            )
            outline = (
                C_TERMINAL if is_active else (rim if not is_empty else (55, 50, 45))
            )
            pygame.draw.polygon(screen, outline, body_pts, 1)
            bullet_y = my + 8
            gold = (220, 185, 45)
            dark = (55, 52, 48) if not is_empty else (40, 38, 35)
            for bi in range(12):
                col = gold if bi < bullets_fill else dark
                pygame.draw.circle(screen, col, (mx + top_w // 2, bullet_y + bi * 3), 2)
            if is_empty:
                pygame.draw.line(
                    screen,
                    (90, 55, 55),
                    (mx + 2, my + 2),
                    (mx + top_w - 2, my + h - 2),
                    1,
                )
                pygame.draw.line(
                    screen,
                    (90, 55, 55),
                    (mx + top_w - 2, my + 2),
                    (mx + 2, my + h - 2),
                    1,
                )
        ammo_text = f"{STATE.ammo_in_mag}/{STATE.mag_size}"
        text_col = C_TERMINAL if STATE.ammo_in_mag > 0 else (220, 60, 60)
        screen.blit(
            font_terminal_small.render(ammo_text, True, text_col),
            (ammo_x + 154, ammo_y + 8),
        )
        screen.blit(
            font_terminal_small.render("9MM", True, (100, 110, 100)),
            (ammo_x + 154, ammo_y + 26),
        )
        if STATE.is_reloading:
            bar_x, bar_y = ammo_x + 148, ammo_y + 46
            bar_w, bar_h = 80, 8
            progress = 1.0 - STATE.reload_timer / 60.0
            pygame.draw.rect(
                screen, (50, 50, 50), (bar_x, bar_y, bar_w, bar_h), border_radius=2
            )
            pygame.draw.rect(
                screen,
                (220, 160, 40),
                (bar_x, bar_y, int(bar_w * progress), bar_h),
                border_radius=2,
            )
            reload_lbl = font_terminal_small.render("RELOADING", True, (220, 160, 40))
            screen.blit(reload_lbl, (ammo_x + 150, ammo_y + 58))
        else:
            mag_label = f"MAGS: {STATE.spare_mags}"
            screen.blit(
                font_terminal_small.render(mag_label, True, (140, 150, 130)),
                (ammo_x + 154, ammo_y + 44),
            )
        # ── Bottle HUD ──
        bot_x = ammo_x - 6
        bot_y = ammo_y - 42
        bot_bg_w, bot_bg_h = 246, 36
        bot_bg = pygame.Surface((bot_bg_w, bot_bg_h), pygame.SRCALPHA)
        pygame.draw.rect(bot_bg, (0, 0, 0, 140), (0, 0, bot_bg_w, bot_bg_h), border_radius=4)
        pygame.draw.rect(bot_bg, (40, 42, 38), (0, 0, bot_bg_w, bot_bg_h), 1, border_radius=4)
        screen.blit(bot_bg, (bot_x, bot_y))
        for bi in range(4):
            icon_x = bot_x + 18 + bi * 26
            icon_y = bot_y + 23
            _draw_molotov_icon(screen, icon_x, icon_y, bi < STATE.player_bottles)
        bot_lbl = font_terminal_small.render(
            f"MOLOTOVS  [G]", True,
            (255, 150, 60) if STATE.player_bottles > 0 else (130, 80, 80),
        )
        screen.blit(bot_lbl, (bot_x + 120, bot_y + 4))
        bot_count = font_terminal_small.render(
            f"{STATE.player_bottles} / 4", True,
            C_TERMINAL if STATE.player_bottles > 0 else (180, 60, 60),
        )
        screen.blit(bot_count, (bot_x + 120, bot_y + 18))
        hud_bg2 = pygame.Surface((180, 26), pygame.SRCALPHA)
        pygame.draw.rect(hud_bg2, (0, 0, 0, 120), (0, 0, 180, 26))
        screen.blit(hud_bg2, (20, 20))
        screen.blit(
            font_terminal_small.render(f"HOSTILES: {len(STATE.enemies)}", True, C_TERMINAL),
            (30, 25),
        )
    if STATE.show_minimap and STATE.minimap:
        STATE.minimap.draw(
            screen,
            STATE.player,
            STATE.enemies,
            fcx,
            fcy,
            STATE.NOTEBOOK_POS,
            STATE.EXFIL_POS,
            STATE.volkov_pos,
            STATE.commander_pos,
        )
    # ── Death animation: camera tilt ──
    # Apply at the very end of the frame so the entire rendered scene
    # (world + HUD + minimap) rotates together. No-op when alive.
    if STATE.player_dead:
        import death_anim
        death_anim.apply_camera_tilt(screen)
