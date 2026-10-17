
"""Split from mission.py - see mission.py (shim) for the map."""
"""Mission 1B gameplay: warehouse infiltrate/firefight/escape."""
import math
import time
import pygame
from core.config import (C_TERMINAL, HEIGHT, WIDTH, audio)
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
