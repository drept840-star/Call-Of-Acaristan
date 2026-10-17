"""Mission 5 - part module. See __init__.py for the package facade.

Per-frame update pipeline for Mission 5 (game_update). Ported from
missions.m4.systems (same ORDER and idioms) - ported, NOT imported: m4
globals are mission-scoped (one-owner rule).

Order: i-frames -> corpses -> death trigger -> player -> melee -> weapon
timers -> shooting -> enemies (guard kills -> world._register_guard_kill)
-> bullets (enemy bullets hit Maru BEFORE the player) -> casings ->
pickups -> particles/texts -> flow._update_stage (also drives Maru) ->
camera.
"""

import math
from engine.core import LEGACY_RNG as _rng_legacy  # RPE6 R6: named 'legacy' rng stream

import pygame

from core.config import (C_BLOOD, C_TERMINAL, ENEMY_DAMAGE, TILE_SIZE, get_scaled_mouse)
from core.state import STATE
from entities import corpse
from entities.player import resolve_melee
from fx import effects
from core import config as _config
from core.camera import update_camera, collide_bullet_walls

audio = _config.audio

from missions.m5 import maps as _m5_maps  # _last_keys / _live_map_dims owner
from missions.m5.meta import STAGE_QUARTER, STAGE_RAID, STAGE_TUNNEL
from missions.m5 import world as _m5_world  # _hit_maru / _register_guard_kill
from missions.m5.world import _solid_walls, _movement_locked
from missions.m5 import flow as _m5_flow  # _update_stage owner
from missions.m5 import inspect_fpv as _m5_fpv
import game.world as _gw  # RPE6 Phase 5 (D4): mission data lives in components
from missions.m5.components import M5Guard as _M5Guard


def _m5g(e):
    """Declared M5 data of an enemy (replaces the ad hoc ``e.m5_*`` attributes)."""
    return _gw.ensure(e, _M5Guard)


M5_PLAYER_SPEED = 3.6
_M5_RELOAD_FRAMES = {"os12": 90, "k9_smg": 72, "pistol": 60}
_M5_MAG_DROP_CAP = 4
_M5_BANDAGE_DROP_CAP = 3


def _reload_duration():
    return _M5_RELOAD_FRAMES.get(getattr(STATE, "current_weapon", "pistol"), 60)


def _player_pos_safe():
    if STATE.player:
        return STATE.player.rect.centerx, STATE.player.rect.centery
    return (0, 0)


def _update_camera():
    """Per-frame camera follow. Returns the render camera for game_draw."""
    if not STATE.player:
        return int(STATE.camera_x), int(STATE.camera_y)
    # Shared gameplay follow (deadzone + aim lookahead): the old bare
    # update_camera() call here was why M5 felt floaty next to M1/M3.
    from core.camera import follow_gameplay
    w, h = _m5_maps._live_map_dims()
    aim = None if getattr(STATE, "player_dead", False) else STATE.player.angle
    return follow_gameplay(_player_pos_safe(), w, h, aim_angle=aim, who="m5")


def _sfx(name, volume):
    try:
        audio.play(name, volume=volume)
    except Exception:
        pass


# ─────────────────────────────────────────────
# Player movement / aim
# ─────────────────────────────────────────────
def _update_player(keys, solid_walls):
    if not STATE.player or STATE.player_dead:
        return
    STATE.player.speed = M5_PLAYER_SPEED
    if not _movement_locked():
        mx, my = get_scaled_mouse()
        STATE.player.angle = math.atan2(
            my + STATE.camera_y - STATE.player.rect.centery,
            mx + STATE.camera_x - STATE.player.rect.centerx)

    dx = dy = 0
    k = _m5_maps._last_keys
    if not _movement_locked() and k is not None:
        _dt_mul = 60.0 * STATE.dt
        if k[pygame.K_w]:
            dy -= STATE.player.speed * _dt_mul
        if k[pygame.K_s]:
            dy += STATE.player.speed * _dt_mul
        if k[pygame.K_a]:
            dx -= STATE.player.speed * _dt_mul
        if k[pygame.K_d]:
            dx += STATE.player.speed * _dt_mul
    if dx and dy:
        dx *= 0.707
        dy *= 0.707
    STATE.player.move(dx, dy, solid_walls)


# ─────────────────────────────────────────────
# Weapon timers / melee / shooting
# ─────────────────────────────────────────────
def _update_weapon_timers():
    # weapons.handle_melee picks swing speed/damage from mission3_weapon (M3's
    # enum). Keep it synced to the M5 gun so the K-9 gets its buttstroke and
    # a stale M3 value (shiv/chair_leg) never leaks into M5 melee.
    STATE.mission3_weapon = ("k9_smg" if getattr(STATE, "current_weapon", "") == "k9_smg"
                             else "sidearm")
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
            cw = getattr(STATE, "current_weapon", "pistol")
            if cw == "os12":
                if STATE.os12_spare_mags > 0:
                    STATE.os12_spare_mags -= 1
                    STATE.os12_ammo_in_mag = STATE.os12_mag_size
            elif cw == "k9_smg":
                if getattr(STATE, "k9_spare_mags", 0) > 0:
                    STATE.k9_spare_mags -= 1
                    STATE.k9_ammo_in_mag = STATE.k9_mag_size
            else:
                if STATE.spare_mags > 0:
                    STATE.spare_mags -= 1
                    STATE.ammo_in_mag = STATE.mag_size

    if getattr(STATE, "weapon_swap_timer", 0) > 0:
        STATE.weapon_swap_timer -= 1
        midpoint = getattr(STATE, "weapon_swap_duration", 24) // 2
        if (STATE.weapon_swap_timer <= midpoint
                and not getattr(STATE, "weapon_swap_sound_played", False)
                and getattr(STATE, "weapon_swap_pending", None) is not None):
            STATE.current_weapon = STATE.weapon_swap_pending
            _sfx("rifle_handle", 0.35)
            STATE.weapon_swap_sound_played = True
        if STATE.weapon_swap_timer <= 0:
            STATE.weapon_swap_pending = None
            STATE.weapon_swap_sound_played = False


def _update_melee():
    if not getattr(STATE, "melee_active", False):
        return
    STATE.melee_timer -= 1
    # One hit check per swing at the contact frame, same as M1-M4. (Re-checking
    # every frame let a whiff turn into a late hit while the arm was retracting.)
    if STATE.player and not STATE.melee_hit_done and STATE.melee_timer <= 10:
        STATE.melee_hit_done = True
        hit_enemy = resolve_melee(STATE.player, STATE.enemies, _solid_walls(), C_BLOOD)
        if hit_enemy is not None:
            STATE.shots_hit += 1
    if STATE.melee_timer <= 0:
        STATE.melee_active = False
        STATE.melee_hit_done = False


def _update_shooting():
    """Full-auto K-9 while LMB is held (semi-auto goes through app.py)."""
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
def _m5_guards_active():
    """Combat AI only runs in the action stages and never during dialogue
    or the Maru-death fail hold."""
    if _movement_locked() or getattr(STATE, "m5_maru_dead", False):
        return False
    return getattr(STATE, "mission5_stage", None) in (
        STAGE_QUARTER, STAGE_RAID, STAGE_TUNNEL)


def _on_enemy_death(e):
    STATE.hostiles_killed += 1
    _m5_world._register_guard_kill(e)
    STATE.blood_decals.append([
        e.rect.centerx, e.rect.centery, 165, _rng_legacy.randint(12, 22)])
    effects.burst(e.rect.centerx, e.rect.centery, C_BLOOD, 24)
    effects.shake(6)
    corpse.spawn_corpse(e)
    if getattr(STATE, "m5_mag_drops", 0) < _M5_MAG_DROP_CAP and _rng_legacy.random() < 0.30:
        STATE.m5_mag_drops = getattr(STATE, "m5_mag_drops", 0) + 1
        STATE.pickups.append([e.rect.centerx, e.rect.centery, "k9mag"])
    if (getattr(STATE, "m5_bandage_drops", 0) < _M5_BANDAGE_DROP_CAP
            and _rng_legacy.random() < 0.22):
        STATE.m5_bandage_drops = getattr(STATE, "m5_bandage_drops", 0) + 1
        STATE.pickups.append([e.rect.centerx + _rng_legacy.randint(-8, 8),
                              e.rect.centery + _rng_legacy.randint(-8, 8), "bandage"])
    _sfx("bullet_impact_enemy", 0.45)


def _update_m5_enemies(solid_walls):
    if not STATE.player or STATE.player_dead:
        return
    px, py = STATE.player.rect.centerx, STATE.player.rect.centery
    for e in STATE.enemies[:]:
        if e.hp > 0 and not _m5g(e).passive:  # quarter.py old faces stand down
            e.update(px, py, solid_walls, STATE.bullets, STATE.particles,
                     STATE.enemies, getattr(STATE, "fire_zones", []))
        if e.hp <= 0:
            _on_enemy_death(e)
            if e in STATE.enemies:
                STATE.enemies.remove(e)


def _reap_dead_enemies():
    """Enemies killed while the AI is paused (dialogue) still die properly."""
    for e in STATE.enemies[:]:
        if e.hp <= 0:
            _on_enemy_death(e)
            STATE.enemies.remove(e)


def _update_bullets(solid_walls):
    if not STATE.player:
        return
    px, py = STATE.player.rect.centerx, STATE.player.rect.centery
    w_tiles, h_tiles = _m5_maps._live_map_dims()
    _dt_mul = 60.0 * STATE.dt
    for b in STATE.bullets[:]:
        b["prev_x"] = b["x"]
        b["prev_y"] = b["y"]
        b["x"] += b["dx"] * _dt_mul
        b["y"] += b["dy"] * _dt_mul
        b["life"] -= 1
        hit = False

        # Enemy bullets: Maru first (escort), then the player.
        if b.get("owner") == "enemy":
            if _m5_world._hit_maru(b):
                effects.burst(b["x"], b["y"], C_BLOOD, 6)
                hit = True
            elif not STATE.player_dead and math.hypot(b["x"] - px, b["y"] - py) < 22:
                if STATE.player.take_damage(b.get("damage", ENEMY_DAMAGE)):
                    effects.shake(6)
                    effects.burst(b["x"], b["y"], C_BLOOD, 8)
                    STATE.gc_flash_timer = max(STATE.gc_flash_timer, 4)
                    _sfx("bullet_impact_enemy", 0.5)
                hit = True

        if b.get("owner") == "player" and not hit:
            for e in STATE.enemies:
                if math.hypot(b["x"] - e.rect.centerx, b["y"] - e.rect.centery) < 22:
                    e.hp -= b.get("damage", 50)
                    e.on_hit(px, py)
                    hit = True
                    if not b.get("ally"):
                        STATE.shots_hit += 1
                    STATE.blood_decals.append([b["x"], b["y"], 140, _rng_legacy.randint(8, 16)])
                    effects.burst(b["x"], b["y"], C_BLOOD, 14)
                    _sfx("bullet_impact_enemy", 0.42)
                    break

        if not hit:
            hit = collide_bullet_walls(b, solid_walls)
            if hit:
                effects.burst(b["x"], b["y"], (130, 125, 110), 4)
                _sfx("bullet_impact", 0.30)

        out_of_world = not (-500 < b["x"] < w_tiles * TILE_SIZE + 500
                            and -500 < b["y"] < h_tiles * TILE_SIZE + 500)
        if hit or b["life"] <= 0 or out_of_world:
            if b in STATE.bullets:
                STATE.bullets.remove(b)


def _update_m5_pickups():
    """Auto-pickup within 36px. Kinds: "k9mag", "mag", "bandage" (+40 HP)."""
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
                STATE.floating_texts.append([pu[0], pu[1] - 16, "+1 K-9 MAG", C_TERMINAL, 70])
            else:
                STATE.spare_mags = min(5, STATE.spare_mags + 1)
                STATE.floating_texts.append([pu[0], pu[1] - 16, "+1 9MM MAG", C_TERMINAL, 70])
        elif kind == "mag":
            if STATE.spare_mags >= 5:
                continue
            STATE.spare_mags += 1
            STATE.floating_texts.append([pu[0], pu[1] - 16, "+1 9MM MAG", C_TERMINAL, 70])
        elif kind == "bandage":
            if STATE.player.hp >= STATE.player.max_hp:
                continue  # leave full-HP bandages on the ground
            STATE.player.hp = min(STATE.player.max_hp, STATE.player.hp + 40)
            STATE.floating_texts.append([pu[0], pu[1] - 16, "+40 HP", (120, 220, 140), 70])
        STATE.pickups.remove(pu)


# ─────────────────────────────────────────────
# Frame driver
# ─────────────────────────────────────────────
def game_update(keys):
    """Per-frame update. Returns (cam_x, cam_y) for the renderer."""
    _m5_maps._last_keys = keys
    if getattr(STATE, "request_m5_cutscene", None):
        return _update_camera()  # every cinematic handoff freezes movement/combat
    if _m5_fpv.active():
        _m5_fpv.update()         # first-person look: the world holds still until it closes
        return _update_camera()
    if STATE.player:
        STATE.player.update_iframes(STATE.dt)
    if STATE.gc_flash_timer > 0:
        STATE.gc_flash_timer -= 1
    corpse.update_corpses()

    if STATE.player and STATE.player.hp <= 0 and not STATE.player_dead:
        from entities import death_anim
        death_anim.trigger_death()
    if STATE.player_dead:
        from entities import death_anim
        STATE._death_logic_ticks = death_anim.update_death_anim()
    else:
        STATE._death_logic_ticks = 1

    solid_walls = _solid_walls()
    _update_player(keys, solid_walls)
    _update_melee()
    _update_weapon_timers()
    _update_shooting()
    if _m5_guards_active():
        _update_m5_enemies(solid_walls)
    else:
        _reap_dead_enemies()
    _update_bullets(solid_walls)
    effects.update_casings(solid_walls)
    _update_m5_pickups()
    effects.update_particles()
    effects.update_floating_texts()
    _m5_flow._update_stage(keys)   # also steps Maru (raid / tunnel)
    return _update_camera()
