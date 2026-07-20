"""Player interactions with the world: doors, safe, NPCs, alarms."""
import math
import random
import pygame
from config import (
    TILE_SIZE, audio, Particle,
    DOOR_INTERACT_RANGE, DOOR_MANUAL_OVERRIDE, DOOR_OPEN_RANGE,
)
from state import STATE
from effects import shake
class Door:
    def __init__(self, x, y, is_bay=False):
        self.rect = pygame.Rect(x, y, TILE_SIZE, TILE_SIZE)
        self.is_bay = is_bay
        self.anim_progress = 0.0
        self.anim_speed = 0.03 if is_bay else 0.1
        self.target_open = False
        self.manual_timer = 0
        self.collision_rect = pygame.Rect(x, y, TILE_SIZE, TILE_SIZE)
        self.is_gate = False
        self.locked = False
        self.collision_disabled = False
    @property
    def is_open(self):
        return self.anim_progress >= 1.0
    def toggle(self):
        if self.locked:
            return
        self.target_open = not self.target_open
        self.manual_timer = DOOR_MANUAL_OVERRIDE
    def update(self, player_rect):
        if self.manual_timer > 0:
            self.manual_timer -= 1
        elif not self.is_bay and not self.locked:
            dist = math.hypot(
                player_rect.centerx - self.rect.centerx,
                player_rect.centery - self.rect.centery,
            )
            self.target_open = dist <= DOOR_OPEN_RANGE
        if self.target_open and self.anim_progress < 1.0:
            self.anim_progress = min(1.0, self.anim_progress + self.anim_speed)
        elif not self.target_open and self.anim_progress > 0.0:
            self.anim_progress = max(0.0, self.anim_progress - self.anim_speed)
        if self.collision_disabled:
            self.collision_rect = None
        else:
            h = max(0, int(TILE_SIZE * (1.0 - self.anim_progress)))
            if h > 0:
                self.collision_rect = pygame.Rect(
                    self.rect.x, self.rect.y, TILE_SIZE, h
                )
            else:
                self.collision_rect = None
def dismiss_note():
    STATE.active_read_note = None
    pygame.mouse.set_visible(False)
def interact_door():
    if not STATE.player or STATE.player_dead:
        return
    closest, closest_dist = None, float("inf")
    for d in STATE.doors:
        dist = math.hypot(
            STATE.player.rect.centerx - d.rect.centerx,
            STATE.player.rect.centery - d.rect.centery,
        )
        if dist <= DOOR_INTERACT_RANGE and dist < closest_dist:
            closest, closest_dist = d, dist
    if closest:
        if closest.locked:
            if closest.is_bay:
                STATE.floating_texts.append([
                    closest.rect.centerx,
                    closest.rect.centery - 20,
                    "BAY DOOR SEALED",
                    (220, 140, 80),
                    70,
                ])
            return
        closest.toggle()
        audio.play(
            "door_open" if closest.is_bay else "door_creak", volume=0.5
        )
        if closest.is_bay:
            for o in STATE.doors:
                if o is not closest and o.is_bay:
                    o.target_open = closest.target_open
                    o.manual_timer = DOOR_MANUAL_OVERRIDE
def handle_interact():
    if not STATE.player or STATE.player_dead:
        return
    for desk in STATE.desks:
        if math.hypot(
            STATE.player.rect.centerx - desk["x"],
            STATE.player.rect.centery - desk["y"],
        ) < 80:
            STATE.active_read_note = desk["clue"]
            desk["read"] = True
            audio.play("pickup", volume=0.5)
            return
    if not STATE.notebook_collected and STATE.NOTEBOOK_POS:
        dist = math.hypot(
            STATE.player.rect.centerx - STATE.NOTEBOOK_POS[0],
            STATE.player.rect.centery - STATE.NOTEBOOK_POS[1],
        )
        if dist < 96:
            if STATE.breach_stage > 0:
                STATE.floating_texts.append([
                    STATE.NOTEBOOK_POS[0], STATE.NOTEBOOK_POS[1] - 20,
                    "BREACH IN PROGRESS!", (255, 100, 30), 90,
                ])
                return
            nearby = [
                e for e in STATE.enemies
                if math.hypot(
                    e.rect.centerx - STATE.NOTEBOOK_POS[0],
                    e.rect.centery - STATE.NOTEBOOK_POS[1],
                ) < 300
            ]
            if not nearby:
                STATE.safe_keypad_active = True
                STATE.safe_keypad_code = ""
                STATE.safe_keypad_target = "742"
                STATE.safe_keypad_callback = _on_safe_opened
                pygame.mouse.set_visible(True)
                audio.play("menu_click", volume=0.5)
            else:
                STATE.floating_texts.append([
                    STATE.NOTEBOOK_POS[0], STATE.NOTEBOOK_POS[1] - 20,
                    "CLEAR HOSTILES FIRST", (220, 60, 60), 90,
                ])
            return
    interact_door()
def _on_safe_opened(success):
    if success:
        STATE.notebook_collected = True
        STATE.floating_texts.append([
            STATE.player.rect.centerx,
            STATE.player.rect.centery - 40,
            "NOTEBOOK ACQUIRED", (50, 200, 100), 120,
        ])
        audio.play("pickup", volume=0.6)
        STATE.request_notebook_inspect = True
        # Lock bay doors — breach will force them open
        for d in STATE.doors:
            if d.is_bay:
                d.locked = True
                d.target_open = False
        # Subtle twist
        trigger_radio_chatter(
            'VASILE: "\u2026Some of this was already in our files."'
        )
        # Start staged breach (not instant — builds over ~6 seconds)
        STATE.breach_stage = 1
        STATE.breach_stage_timer = 0
        STATE.mission_phase = "escape"
        STATE.firefight_triggered = True
        # Make sure all enemies are alert
        for e in STATE.enemies:
            e.alerted = True
            e.state = "CHASE"
    else:
        STATE.floating_texts.append([
            STATE.player.rect.centerx,
            STATE.player.rect.centery - 40,
            "WRONG CODE", (220, 60, 60), 90,
        ])
def trigger_radio_chatter(text, color=(100, 160, 220), duration=360):
    audio.play("radio_static", volume=0.4)
    audio.play("radio_chatter", volume=0.3)
    # Radio text appears as a pinned message, so fake the terminal typing audio
    # with scheduled ticks. Limit count so long radio lines do not become noisy.
    tick_i = 0
    for ch in text:
        if ch and not ch.isspace():
            if tick_i < 34 and (tick_i % 2 == 0 or ch in ".!?"):
                audio.schedule(8 + tick_i * 2, "type_tick", volume=0.085)
            tick_i += 1
    if STATE.player:
        STATE.floating_texts.append([
            STATE.player.rect.centerx,
            STATE.player.rect.centery + 20,
            text, color, duration, "pin",
        ])
def trigger_alarm_early():
    if STATE.stealth_failed:
        return
    STATE.stealth_failed = True
    STATE.firefight_triggered = True
    STATE.mission_phase = "firefight"
    STATE.quiet_entry = False
    # Cancel any active sighting
    if STATE.volkov_sighting_timer > 0:
        STATE.volkov_sighting_timer = 0
    # Start Volkov escape if he hasn't left yet
    if not STATE.volkov_escaped and STATE.volkov_pos:
        STATE.volkov_escape_pos = list(STATE.volkov_pos)
        STATE.volkov_escape_timer = 90
    STATE.volkov_escaped = False
    STATE.commander_escaped = False
    shake(12)
    audio.play("alarm", volume=0.5, loops=0)
    for e in STATE.enemies:
        e.alerted = True
        e.state = "CHASE"
    STATE.floating_texts.append([
        STATE.player.rect.centerx,
        STATE.player.rect.centery - 40,
        "ALARM TRIGGERED!", (220, 60, 60), 120,
    ])
    STATE.radio_chatter_stage = 1
    trigger_radio_chatter(
        'VASILE: "Biribel, they spotted you! Alarm is active!"'
    )
def trigger_mag_ambush():
    """Execute the actual breach — spawn MAG enemies, blow bay doors."""
    from enemy_ai import Enemy
    STATE.radio_chatter_stage = 6
    shake(28)
    audio.play("explosion", volume=0.8)
    audio.play("breach", volume=0.7)
    # Block the stairs
    STATE.walls.append(pygame.Rect(
        2 * TILE_SIZE, 23 * TILE_SIZE, TILE_SIZE, TILE_SIZE))
    STATE.walls.append(pygame.Rect(
        3 * TILE_SIZE, 23 * TILE_SIZE, TILE_SIZE, TILE_SIZE))
    # Force bay doors open
    for d in STATE.doors:
        if d.is_bay:
            d.locked = False
            d.target_open = True
            d.anim_progress = 1.0
            d.collision_disabled = True
            d.manual_timer = 9999
    # Spawn MAG enemies
    spawns = [
        (14 * TILE_SIZE + 16, 25 * TILE_SIZE + 16),
        (16 * TILE_SIZE + 16, 25 * TILE_SIZE + 16),
    ]
    # Stealth penalty: extra enemy if alarm was triggered early
    if not STATE.quiet_entry:
        spawns.append((15 * TILE_SIZE + 16, 25 * TILE_SIZE + 16))
    for mx, my in spawns:
        e = Enemy(mx, my)
        e.alerted = True
        e.state = "CHASE"
        e.last_seen_pos = (14 * TILE_SIZE + 32, 22 * TILE_SIZE + 32)
        e.is_ambush_enemy = True
        e.hp = 80
        e.fire_cooldown = 90
        STATE.enemies.append(e)
        for _ in range(25):
            STATE.particles.append(Particle(mx, my, (180, 180, 180)))
        for _ in range(15):
            STATE.particles.append(Particle(mx, my, (255, 120, 30)))
        STATE.breach_markers.append([mx, my, 180])
    trigger_radio_chatter(
        'VASILE: "They blocked the stairs! Hotwire the delivery truck!"'
    )
