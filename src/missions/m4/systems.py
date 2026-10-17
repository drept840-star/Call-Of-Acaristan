
"""Split from mission4.py - see __init__.py for the package facade.

Per-frame update pipeline for Mission 4 (game_update). The pipeline ORDER
mirrors missions.m3.systems.game_update: i-frames → corpses → death
trigger → doors → walls → player → weapon timers → shooting → enemies →
bullets → pickups → stage → camera. Enemy AI is the plain shared-Enemy
loop (M3's Volkov-ally / strict-LOS / sweep director are mission-scoped
and deliberately not imported; W4 ports the wave director locally).
"""

import math
from engine.core import LEGACY_RNG as _rng_legacy  # RPE6 R6: named 'legacy' rng stream
import time

import pygame

from core.config import (C_BLOOD, C_TERMINAL, ENEMY_DAMAGE, TILE_SIZE, get_scaled_mouse)
from core.state import STATE
from entities import corpse
from entities.player import Player, resolve_melee
from entities.enemy_ai import Enemy
from fx import effects
from core import config as _config
from core.camera import (
    update_camera, reset_camera_state, collide_bullet_walls, draw_bullets,
)

audio = _config.audio

from missions.m4 import maps as _m4_maps  # _last_keys owner
from missions.m4.meta import (
    MAP_W, MAP_H, M4_ROLE_TUNING,
    STAGE_INTRO, STAGE_AFTERMATH, STAGE_KRAP_STATUS, STAGE_MARU,
    STAGE_COMMIT, STAGE_DONE,
)
from missions.m4.world import (
    _solid_walls, _movement_locked, _near, _radio, _set_objective,
    _spawn_m4_guard, _update_m4_allies, _hit_m4_ally,
)
from missions.m4 import flow as _m4_flow  # _update_stage / _complete_m4 owner
import game.world as _gw  # RPE6 Phase 5 (D4): mission data lives in components
from missions.m4.components import M4Guard as _M4Guard


def _m4g(e):
    """Declared M4 data of an enemy (replaces the ad hoc ``e.m4_*`` attributes)."""
    return _gw.ensure(e, _M4Guard)



# Reload durations in frames, per weapon (m3.draw/_update_weapon_timers values).
_M4_RELOAD_FRAMES = {"os12": 90, "k9_smg": 72, "pistol": 60}


def _reload_duration():
    cw = getattr(STATE, "current_weapon", "pistol")
    return _M4_RELOAD_FRAMES.get(cw, 60)


def _update_camera():
    """Per-frame camera follow. Returns the render camera for game_draw."""
    if not STATE.player:
        return int(STATE.camera_x), int(STATE.camera_y)
    # Shared gameplay follow (deadzone + aim lookahead) - same feel as M1/M3.
    from core.camera import follow_gameplay
    w, h = _m4_maps._live_map_dims()
    aim = None if getattr(STATE, "player_dead", False) else STATE.player.angle
    return follow_gameplay(_player_pos_safe(), w, h, aim_angle=aim, who="m4")


def _player_pos_safe():
    if STATE.player:
        return STATE.player.rect.centerx, STATE.player.rect.centery
    return (0, 0)


# ─────────────────────────────────────────────
# Player movement / aim
# ─────────────────────────────────────────────
def _update_player(keys, solid_walls):
    if not STATE.player or STATE.player_dead:
        return
    STATE.player.speed = 3.6

    mx, my = get_scaled_mouse()
    world_mx = mx + STATE.camera_x
    world_my = my + STATE.camera_y
    STATE.player.angle = math.atan2(
        world_my - STATE.player.rect.centery,
        world_mx - STATE.player.rect.centerx,
    )

    dx = dy = 0
    if not _movement_locked() and _m4_maps._last_keys is not None:
        # Delta-time aware: speed is in px/frame, multiply by (60*dt).
        _dt_mul = 60.0 * STATE.dt
        if _m4_maps._last_keys[pygame.K_w]:
            dy -= STATE.player.speed * _dt_mul
        if _m4_maps._last_keys[pygame.K_s]:
            dy += STATE.player.speed * _dt_mul
        if _m4_maps._last_keys[pygame.K_a]:
            dx -= STATE.player.speed * _dt_mul
        if _m4_maps._last_keys[pygame.K_d]:
            dx += STATE.player.speed * _dt_mul
    if dx and dy:
        dx *= 0.707
        dy *= 0.707
    STATE.player.move(dx, dy, solid_walls)


# ─────────────────────────────────────────────
# Weapon timers / melee / shooting
# ─────────────────────────────────────────────
def _update_weapon_timers():
    """Cooldowns + reload completion (m3.systems._update_weapon_timers idiom,
    minus the mission3_weapon enum sync - M4 carries real firearms only)."""
    if STATE.shot_cooldown > 0:
        STATE.shot_cooldown -= 1

    if getattr(STATE, "os12_shot_cooldown", 0) > 0:
        STATE.os12_shot_cooldown -= 1

    if getattr(STATE, "k9_shot_cooldown", 0) > 0:
        STATE.k9_shot_cooldown -= 1

    if STATE.is_reloading:
        STATE.reload_timer -= 1
        if STATE.reload_timer <= 0:
            STATE.is_reloading = False

            current_weapon = getattr(STATE, "current_weapon", "pistol")
            if current_weapon == "os12":
                if STATE.os12_spare_mags > 0:
                    STATE.os12_spare_mags -= 1
                    STATE.os12_ammo_in_mag = STATE.os12_mag_size
            elif current_weapon == "k9_smg":
                if getattr(STATE, "k9_spare_mags", 0) > 0:
                    STATE.k9_spare_mags -= 1
                    STATE.k9_ammo_in_mag = STATE.k9_mag_size
            else:
                if STATE.spare_mags > 0:
                    STATE.spare_mags -= 1
                    STATE.ammo_in_mag = STATE.mag_size

    if getattr(STATE, "weapon_swap_timer", 0) > 0:
        STATE.weapon_swap_timer -= 1
        duration = getattr(STATE, "weapon_swap_duration", 24)
        midpoint = duration // 2
        if (
            STATE.weapon_swap_timer <= midpoint
            and not getattr(STATE, "weapon_swap_sound_played", False)
            and getattr(STATE, "weapon_swap_pending", None) is not None
        ):
            STATE.current_weapon = STATE.weapon_swap_pending
            audio.play("rifle_handle", volume=0.35)
            STATE.weapon_swap_sound_played = True
        if STATE.weapon_swap_timer <= 0:
            STATE.weapon_swap_pending = None
            STATE.weapon_swap_sound_played = False


def _update_melee():
    """Melee swing progression (m2/update.py idiom; V key starts it via
    weapons.handle_melee through the game_core proxy)."""
    if not getattr(STATE, "melee_active", False):
        return
    STATE.melee_timer -= 1
    if STATE.player and not STATE.melee_hit_done and STATE.melee_timer <= 10:
        hit_enemy = resolve_melee(STATE.player, STATE.enemies, _solid_walls(), C_BLOOD)
        if hit_enemy is not None:
            STATE.melee_hit_done = True
            STATE.shots_hit += 1
    if STATE.melee_timer <= 0:
        STATE.melee_active = False


def _update_shooting():
    """Full-auto while LMB is held (K-9 SMG). Semi-auto pistol/OS-12 fire is
    app.py's generic click → gc.handle_shoot() through the proxy, same as M2/M3."""
    if (STATE.player and not STATE.player_dead
            and not _movement_locked()
            and not getattr(STATE, "is_reloading", False)
            and getattr(STATE, "weapon_swap_timer", 0) <= 0
            and getattr(STATE, "current_weapon", "pistol") == "k9_smg"):
        try:
            if pygame.mouse.get_pressed()[0]:
                from entities import weapons as _weapons
                _weapons.handle_shoot()
        except Exception:
            pass


# ─────────────────────────────────────────────
# Enemies / bullets / pickups
# ─────────────────────────────────────────────
def _m4_guards_active():
    """Combat AI only runs in the playable action stages - and never while a
    dialogue/story beat has the frame (the liaison meet must not be a firefight)."""
    if _movement_locked():
        return False
    stage = getattr(STATE, "mission4_stage", STAGE_AFTERMATH)
    return stage in (STAGE_AFTERMATH, STAGE_KRAP_STATUS, STAGE_MARU, STAGE_COMMIT)


def _update_m4_enemies(solid_walls):
    if not STATE.player or STATE.player_dead:
        return
    px, py = STATE.player.rect.centerx, STATE.player.rect.centery

    for e in STATE.enemies[:]:
        if e.hp > 0:
            if _m4g(e).loyalist \
                    and getattr(STATE, "mission4_stage", None) == STAGE_COMMIT:
                e.alerted = True
                e.last_seen_pos = (px, py)
                e.combat_alert_timer = max(getattr(e, "combat_alert_timer", 0), 420)
                if e.state in ("IDLE", "PATROL", "SEARCH"):
                    e.state = "CHASE"
            e.update(px, py, solid_walls, STATE.bullets, STATE.particles,
                     STATE.enemies, getattr(STATE, "fire_zones", []))
        if e.hp <= 0:
            STATE.hostiles_killed += 1
            STATE.blood_decals.append([
                e.rect.centerx, e.rect.centery, 165, _rng_legacy.randint(12, 22)])
            effects.burst(e.rect.centerx, e.rect.centery, C_BLOOD, 24)
            effects.shake(6)
            # Body topples, bleeds out, fades (entities/corpse.py).
            corpse.spawn_corpse(e)
            # Drop economy (m3 ratios ported): a mag most kills, a bandage
            # sometimes - capped through the session so fights aren't loot piñatas.
            if getattr(STATE, "m4_mag_drops", 0) < 4 and _rng_legacy.random() < 0.30:
                STATE.m4_mag_drops = getattr(STATE, "m4_mag_drops", 0) + 1
                STATE.pickups.append([e.rect.centerx, e.rect.centery, "k9mag"])
            if getattr(STATE, "m4_bandage_drops", 0) < 3 and _rng_legacy.random() < 0.22:
                STATE.m4_bandage_drops = getattr(STATE, "m4_bandage_drops", 0) + 1
                STATE.pickups.append([
                    e.rect.centerx + _rng_legacy.randint(-8, 8),
                    e.rect.centery + _rng_legacy.randint(-8, 8),
                    "bandage"])
            try:
                audio.play("bullet_impact_enemy", volume=0.45)
            except Exception:
                pass
            STATE.enemies.remove(e)


def _update_bullets(solid_walls):
    """Move bullets, player/enemy/wall collisions, expiry (m3 idiom minus the
    detainee / Volkov-ally / cell-door passes - M4 has none yet)."""
    if not STATE.player:
        return
    px, py = STATE.player.rect.centerx, STATE.player.rect.centery
    w_tiles, h_tiles = _m4_maps._live_map_dims()
    for b in STATE.bullets[:]:
        b["prev_x"] = b["x"]
        b["prev_y"] = b["y"]
        _dt_mul = 60.0 * STATE.dt
        b["x"] += b["dx"] * _dt_mul
        b["y"] += b["dy"] * _dt_mul
        b["life"] -= 1
        hit = False

        # Enemy bullets vs player / station allies.
        if b.get("owner") == "enemy" and not hit:
            if _hit_m4_ally(b):
                effects.burst(b["x"], b["y"], C_BLOOD, 6)
                hit = True
        if b.get("owner") == "enemy" and not hit and not STATE.player_dead:
            if math.hypot(b["x"] - px, b["y"] - py) < 22:
                if STATE.player.take_damage(b.get("damage", ENEMY_DAMAGE)):
                    effects.shake(6)
                    effects.burst(b["x"], b["y"], C_BLOOD, 8)
                    STATE.gc_flash_timer = max(STATE.gc_flash_timer, 4)
                    try:
                        audio.play("bullet_impact_enemy", volume=0.5)
                    except Exception:
                        pass
                hit = True

        # Player bullets vs enemies.
        if b.get("owner") == "player" and not hit:
            for e in STATE.enemies:
                if math.hypot(b["x"] - e.rect.centerx, b["y"] - e.rect.centery) < 22:
                    damage = b.get("damage", 50)
                    e.hp -= damage
                    e.on_hit(px, py)
                    hit = True
                    if not b.get("ally"):
                        STATE.shots_hit += 1
                    STATE.blood_decals.append([b["x"], b["y"], 140, _rng_legacy.randint(8, 16)])
                    effects.burst(b["x"], b["y"], C_BLOOD, 14)
                    try:
                        audio.play("bullet_impact_enemy", volume=0.42)
                    except Exception:
                        pass
                    break

        # Wall hits (only if no entity was hit).
        if not hit:
            hit = collide_bullet_walls(b, solid_walls)
            if hit:
                effects.burst(b["x"], b["y"], (130, 125, 110), 4)
                try:
                    audio.play("bullet_impact", volume=0.30)
                except Exception:
                    pass

        out_of_world = not (-500 < b["x"] < w_tiles * TILE_SIZE + 500
                            and -500 < b["y"] < h_tiles * TILE_SIZE + 500)
        if hit or b["life"] <= 0 or out_of_world:
            if b in STATE.bullets:
                STATE.bullets.remove(b)


def _update_m4_pickups():
    """Auto-pickup within 36px of the player (m3._update_m3_pickups idiom).
    Kinds: "k9mag" (SMG spare), "mag" (pistol spare), "bandage" (+40 HP)."""
    if not STATE.player or STATE.player_dead:
        return
    for pu in STATE.pickups[:]:
        if math.hypot(pu[0] - STATE.player.rect.centerx,
                      pu[1] - STATE.player.rect.centery) > 36:
            continue
        kind = pu[2]
        if kind == "k9mag":
            if getattr(STATE, "k9_spare_mags", 0) < 5:
                STATE.k9_spare_mags = getattr(STATE, "k9_spare_mags", 0) + 1
                STATE.floating_texts.append([
                    pu[0], pu[1] - 16, "+1 K-9 MAG", C_TERMINAL, 70])
            else:
                STATE.spare_mags = min(5, STATE.spare_mags + 1)
                STATE.floating_texts.append([
                    pu[0], pu[1] - 16, "+1 9MM MAG", C_TERMINAL, 70])
        elif kind == "mag":
            if STATE.spare_mags < 5:
                STATE.spare_mags += 1
                STATE.floating_texts.append([
                    pu[0], pu[1] - 16, "+1 9MM MAG", C_TERMINAL, 70])
        elif kind == "bandage":
            if STATE.player.hp < STATE.player.max_hp:
                STATE.player.hp = min(STATE.player.max_hp, STATE.player.hp + 40)
                STATE.floating_texts.append([
                    pu[0], pu[1] - 16, "+40 HP", (120, 220, 140), 70])
            else:
                continue  # leave full-HP bandages on the ground
        STATE.pickups.remove(pu)


# ─────────────────────────────────────────────
# Frame driver
# ─────────────────────────────────────────────
def game_update(keys):
    """Per-frame update. Returns (cam_x, cam_y) for acaristan's renderer."""
    _m4_maps._last_keys = keys
    if STATE.player:
        STATE.player.update_iframes(STATE.dt)
    if STATE.gc_flash_timer > 0:
        STATE.gc_flash_timer -= 1
    # Corpses animate on every frame, including the death-anim path below.
    corpse.update_corpses()

    if STATE.player and STATE.player.hp <= 0 and not STATE.player_dead:
        from entities import death_anim
        death_anim.trigger_death()
    if STATE.player_dead:
        from entities import death_anim
        ticks = death_anim.update_death_anim()
        STATE._death_logic_ticks = ticks
    else:
        STATE._death_logic_ticks = 1

    solid_walls = _solid_walls()
    _update_player(keys, solid_walls)
    _update_melee()
    _update_weapon_timers()
    _update_shooting()
    _update_m4_allies(solid_walls)
    if _m4_guards_active():
        _update_m4_enemies(solid_walls)
    _update_bullets(solid_walls)
    effects.update_casings(solid_walls)
    _update_m4_pickups()
    effects.update_particles()
    effects.update_floating_texts()
    _m4_flow._update_stage(keys)
    return _update_camera()
