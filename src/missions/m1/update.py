
"""Split from mission.py - see mission.py (shim) for the map."""
"""Mission 1B gameplay: warehouse infiltrate/firefight/escape."""
import math
from engine.core import LEGACY_RNG as _rng_legacy  # RPE6 R6: named 'legacy' rng stream
import time
import pygame
from core.config import (C_BLOOD, C_TERMINAL, ENEMY_DAMAGE, HEIGHT, Particle, TILE_SIZE, WIDTH, audio, get_scaled_mouse)
from entities.art_cache import get_blood_decal, get_glow, get_shadow
from entities.enemy_ai import Enemy, enemy_hear_shot
from entities import corpse
from core.state import STATE
from ui.hud import MiniMap, draw_objective_panel, draw_pinned_radio
from entities.player import Player, resolve_melee
from core.interactions import (
    Door,
    trigger_alarm_early,
    trigger_radio_chatter,
)
from entities.weapons import (
    update_molotovs,
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
from core.camera import tick_camera_fx, follow_gameplay

from missions.m1.map import _tc, MAP_W, MAP_H
from missions.m1.main import _init_mission_specials, _trigger_civilian_payoff
from missions.m1.hotwire import _reset_hotwire_minigame
from engine.core import now_ms as _now_ms  # RPE6 B-001 timebase

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
    if STATE.EXFIL_POS and STATE.player:
        STATE.player.rect.centerx = int(STATE.EXFIL_POS[0] - 42)
        STATE.player.rect.centery = int(STATE.EXFIL_POS[1])
        max_cx = max(0, MAP_W * TILE_SIZE - WIDTH)
        max_cy = max(0, MAP_H * TILE_SIZE - HEIGHT)
        STATE.camera_x = max(0, min(max_cx, STATE.player.rect.centerx - WIDTH // 2))
        STATE.camera_y = max(0, min(max_cy, STATE.player.rect.centery - HEIGHT // 2))
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
    # and let it play out - the death_anim module will set request_death_screen
    # when the 2-second animation completes. We still return early so the rest
    # of the update logic (enemy AI, bullets, etc.) doesn't run on the frame
    # the player dies - subsequent frames will run update_death_anim() via the
    # block at line ~890.
    if STATE.player and STATE.player.hp <= 0 and not STATE.player_dead:
        from entities import death_anim
        death_anim.trigger_death()
        if not STATE.mission_end_time:
            STATE.mission_end_time = _now_ms()
        return tick_camera_fx(MAP_W, MAP_H)
    if STATE.active_read_note or STATE.safe_keypad_active:
        return tick_camera_fx(MAP_W, MAP_H)
    player_hit_this_frame = False
    if STATE.NOTEBOOK_POS is None:
        _init_mission_specials()
    if STATE.player and not STATE.firefight_triggered:
        # Combat only starts from enemy detection - no position trigger
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
                    px = 15 * TILE_SIZE + _rng_legacy.randint(-3 * TILE_SIZE, 3 * TILE_SIZE)
                    py = 19 * TILE_SIZE + _rng_legacy.randint(-TILE_SIZE, 0)
                    p = Particle(px, py, _rng_legacy.choice([(120, 110, 90), (90, 85, 70)]))
                    p.life = _rng_legacy.randint(30, 60)
                    p.dy = _rng_legacy.uniform(-0.5, 0.5)
                    p.dx = _rng_legacy.uniform(-0.3, 0.3)
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
                new_e = Enemy(mx, my)
                new_e.alerted = True
                new_e.state = "CHASE"
                # Ambush discipline: hunt Biribel's actual position on entry,
                # not a fixed waypoint across the map - otherwise the breach
                # wave marches to mid-warehouse while the player exfils.
                if STATE.player is not None:
                    ppx, ppy = STATE.player.rect.centerx, STATE.player.rect.centery
                    new_e.last_seen_pos = (
                        ppx + _rng_legacy.randint(-24, 24),
                        ppy + _rng_legacy.randint(-24, 24))
                else:
                    tx, ty = bay_targets[i % len(bay_targets)]
                    new_e.last_seen_pos = (tx, ty)
                new_e.combat_alert_timer = 420
                new_e.is_ambush_enemy = True
                new_e.is_breach_enemy = True
                new_e.fire_weakness = 1.15
                new_e.hp = 115
                new_e.fire_cooldown = 40 + i * 15 + _rng_legacy.randint(0, 30)
                new_e.speed = _rng_legacy.uniform(2.0, 2.7)
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
                new_e = Enemy(mx, my)
                new_e.alerted = True
                new_e.state = "CHASE"
                # Same ambush discipline as the bay wave: converge on the
                # player, not on stale mid-map waypoints.
                if STATE.player is not None:
                    ppx, ppy = STATE.player.rect.centerx, STATE.player.rect.centery
                    new_e.last_seen_pos = (
                        ppx + _rng_legacy.randint(-32, 32),
                        ppy + _rng_legacy.randint(-32, 32))
                else:
                    tx, ty = rear_targets[i % len(rear_targets)]
                    new_e.last_seen_pos = (tx, ty)
                new_e.combat_alert_timer = 420
                new_e.is_ambush_enemy = True
                new_e.is_breach_enemy = True
                new_e.fire_weakness = 1.15
                new_e.hp = 115
                new_e.fire_cooldown = 60 + i * 18 + _rng_legacy.randint(0, 25)
                new_e.speed = _rng_legacy.uniform(1.8, 2.4)
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
                # Keycard bypass - instant open, no minigame
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
                                    "GATE OPENED - KEYCARD",
                                    C_TERMINAL,
                                    120,
                                ]
                            )
                    STATE.gate_hacking = False
                    STATE.gate_hack_progress = 0.0
            else:
                # No keycard - hack minigame
                if keys[pygame.K_e]:
                    STATE.gate_hacking = True
                    STATE.gate_hack_progress += 1.0 / 180.0
                    if (_now_ms() // 200) % 2 == 0:
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
    # ── Molotovs: bottle flight + ground fire ──
    # Shared with every other mission via entities.weapons so the throw,
    # the arc, the embers and the damage all read identically everywhere.
    if update_molotovs(solid_walls):
        player_hit_this_frame = True
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
            # Death animation (Option B - Standard) handles the full sequence:
            # slow-mo, camera collapse, ragdoll, blood pool, tinnitus, radio cut.
            # Replaces the legacy single-burst + shake trigger.
            from entities import death_anim
            death_anim.trigger_death()
        if STATE.player_dead:
            # update_death_anim() advances all 6 layers and returns the
            # number of game-logic ticks to run (slow-mo via accumulator).
            from entities import death_anim
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

    # Unified camera: lerp + first-frame snap + map-bounds clamp + recoil kick + shake.
    # Both missions now use this same code path so the feel of "the camera
    # following the player" cannot drift between them. Aim-direction lookahead
    # shows more of what the player is aiming at; the deadzone kills lerp-tail
    # micro-jitter.
    if STATE.player:
        fcx, fcy = follow_gameplay(
            (STATE.player.rect.centerx, STATE.player.rect.centery),
            MAP_W, MAP_H, aim_angle=STATE.player.angle, who="m1",
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
            d.update(STATE.player.rect, STATE.enemies)
    if STATE.player and not STATE.player_dead:
        # Use raw mouse position for the angle, scaled mouse is for UI
        # but since we are in GAME state, the cursor is hidden and we
        # want the mouse to feel natural.
        # Actually, get_scaled_mouse is correct for the virtual screen coordinates.
        # Aim from the shake-free follow camera (STATE.camera_x/y), matching
        # M2/M3/molotov targeting. Using the render camera (fcx/fcy, which
        # includes recoil kick + shake) made the crosshair world position
        # drift on every shot.
        world_mx, world_my = get_scaled_mouse()
        world_mx += STATE.camera_x
        world_my += STATE.camera_y
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
        # player took no damage. Now entity hits take priority - if a bullet
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
                            [b["x"], b["y"], 120, _rng_legacy.randint(8, 16)]
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
                # (no blood, no shake, no hit-stop) - the player should not
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
            # Breach-wave discipline: keep converging on Biribel during the
            # firefight/escape instead of peeling to SEARCH on stale
            # waypoints. They heard the breach + truck, so they re-fix on
            # the player's position when they've lost sight.
            if getattr(e, "is_breach_enemy", False) and getattr(
                    STATE, "mission_phase", "") in ("firefight", "escape"):
                if getattr(e, "lost_sight_timer", 0) > 30:
                    e.last_seen_pos = (STATE.player.rect.centerx,
                                       STATE.player.rect.centery)
                    e.combat_alert_timer = max(
                        getattr(e, "combat_alert_timer", 0), 240)
                    if getattr(e, "state", "") == "SEARCH":
                        e.state = "CHASE"
                        e.search_timer = 0
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
                [e.rect.centerx, e.rect.centery, 160, _rng_legacy.randint(14, 22)]
            )
            # Body topples, bleeds out, and fades instead of vanishing
            # on the death frame (entities/corpse.py).
            corpse.spawn_corpse(e)
            if e.is_commander:
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
                roll = _rng_legacy.random()
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
    corpse.update_corpses()
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
