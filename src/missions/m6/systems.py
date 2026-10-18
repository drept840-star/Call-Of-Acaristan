"""Mission 6 - per-frame gameplay pipeline.

Order: i-frames -> corpses -> death -> player -> melee -> weapon timers ->
shooting -> enemies -> bullets -> floodlights -> effects -> flow -> camera.
The interactive train owns its own update/draw and is routed here first;
an exception in the scene hands the mission straight to the file stage
rather than looping or stranding it.
"""
import math

import pygame

from core.config import (
    C_BLOOD, ENEMY_DAMAGE, TILE_SIZE, get_scaled_mouse,
)
from core.state import STATE
from core.camera import collide_bullet_walls, follow_gameplay
from entities import corpse
from entities.player import resolve_melee
from entities import weapons as _weapons
from fx import effects

from . import maps as _maps
from . import world as _world
from . import flow as _flow
from . import stealth as _stealth
from .meta import STAGE_TRAIN


def _reload_frames():
    return {"os12": 90, "k9_smg": 72}.get(
        getattr(STATE, "current_weapon", "pistol"), 60)


def _update_player(keys):
    p = STATE.player
    if not p or STATE.player_dead:
        return
    p.speed = _world.M6_PLAYER_SPEED
    if _world._movement_locked():
        return
    mx, my = get_scaled_mouse()
    p.angle = math.atan2(my + STATE.camera_y - p.rect.centery,
                         mx + STATE.camera_x - p.rect.centerx)
    dt_mul = 60.0 * getattr(STATE, "dt", 1.0 / 60.0)
    dx = dy = 0.0
    if keys is not None:
        if keys[pygame.K_w]:
            dy -= p.speed * dt_mul
        if keys[pygame.K_s]:
            dy += p.speed * dt_mul
        if keys[pygame.K_a]:
            dx -= p.speed * dt_mul
        if keys[pygame.K_d]:
            dx += p.speed * dt_mul
    if dx and dy:
        dx *= 0.7071
        dy *= 0.7071
    p.move(dx, dy, _world.solid_walls())


def _update_weapon_timers():
    STATE.mission3_weapon = ("k9_smg" if getattr(STATE, "current_weapon", "") == "k9_smg"
                             else "sidearm")
    for name in ("shot_cooldown", "os12_shot_cooldown", "k9_shot_cooldown"):
        if getattr(STATE, name, 0) > 0:
            setattr(STATE, name, getattr(STATE, name) - 1)
    if getattr(STATE, "is_reloading", False):
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
            _world.sfx("rifle_handle", 0.35)
            STATE.weapon_swap_sound_played = True
        if STATE.weapon_swap_timer <= 0:
            STATE.weapon_swap_pending = None
            STATE.weapon_swap_sound_played = False


def _update_melee():
    if not getattr(STATE, "melee_active", False):
        return
    STATE.melee_timer -= 1
    if STATE.player and not getattr(STATE, "melee_hit_done", False) and STATE.melee_timer <= 10:
        STATE.melee_hit_done = True
        hit = resolve_melee(STATE.player, STATE.enemies, _world.solid_walls(), C_BLOOD)
        if hit is not None:
            STATE.shots_hit += 1
    if STATE.melee_timer <= 0:
        STATE.melee_active = False
        STATE.melee_hit_done = False


def _update_shooting():
    if (STATE.player and not STATE.player_dead
            and not _world._movement_locked()
            and not getattr(STATE, "is_reloading", False)
            and getattr(STATE, "weapon_swap_timer", 0) <= 0
            and getattr(STATE, "current_weapon", "pistol") == "k9_smg"
            and pygame.mouse.get_pressed()[0]):
        _weapons.handle_shoot()


def _update_enemies():
    p = STATE.player
    if not p or STATE.player_dead or _world._movement_locked():
        return
    solid = _world.solid_walls()
    dt = float(getattr(STATE, "dt", 1.0 / 60.0))
    for enemy in STATE.enemies[:]:
        # A Guard walking in from a gate owns his feet until he is planted:
        # no aiming, no fire, no pathing - just the step and the snow.
        if _world.tick_entry(enemy, dt):
            if enemy.hp <= 0:
                _kill_enemy(enemy)
            continue
        if enemy.hp > 0:
            enemy.update(p.rect.centerx, p.rect.centery, solid, STATE.bullets,
                         STATE.particles, STATE.enemies,
                         getattr(STATE, "fire_zones", []))
        if enemy.hp <= 0:
            _kill_enemy(enemy)


def _kill_enemy(enemy):
    STATE.hostiles_killed += 1
    STATE.blood_decals.append([enemy.rect.centerx, enemy.rect.centery, 150, 12])
    effects.burst(enemy.rect.centerx, enemy.rect.centery, (180, 50, 55), 16)
    corpse.spawn_corpse(enemy)
    STATE.enemies.remove(enemy)


def _update_bullets():
    p = STATE.player
    if not p:
        return
    solid = _world.solid_walls()
    w, h = _maps._live_map_dims()
    width, height = w * TILE_SIZE, h * TILE_SIZE
    dt_mul = 60.0 * getattr(STATE, "dt", 1.0 / 60.0)
    for bullet in STATE.bullets[:]:
        bullet["prev_x"] = bullet.get("x", 0)
        bullet["prev_y"] = bullet.get("y", 0)
        bullet["x"] += bullet.get("dx", 0) * dt_mul
        bullet["y"] += bullet.get("dy", 0) * dt_mul
        bullet["life"] -= 1
        hit = False
        if bullet.get("owner") == "enemy":
            if not STATE.player_dead and math.hypot(
                    bullet["x"] - p.rect.centerx,
                    bullet["y"] - p.rect.centery) < 22:
                if p.take_damage(bullet.get("damage", ENEMY_DAMAGE)):
                    effects.shake(5)
                    STATE.gc_flash_timer = max(STATE.gc_flash_timer, 4)
                hit = True
        elif bullet.get("owner") == "player":
            for enemy in STATE.enemies:
                if math.hypot(bullet["x"] - enemy.rect.centerx,
                              bullet["y"] - enemy.rect.centery) < 22:
                    enemy.hp -= bullet.get("damage", 50)
                    enemy.on_hit(p.rect.centerx, p.rect.centery)
                    STATE.shots_hit += 1
                    effects.burst(bullet["x"], bullet["y"], (180, 50, 55), 8)
                    hit = True
                    break
        if not hit:
            hit = collide_bullet_walls(bullet, solid)
        outside = not (-400 < bullet["x"] < width + 400
                       and -400 < bullet["y"] < height + 400)
        if hit or bullet["life"] <= 0 or outside:
            if bullet in STATE.bullets:
                STATE.bullets.remove(bullet)


def _update_stealth(dt):
    try:
        _stealth.update(dt)
    except Exception:
        # Detection must never break the combat loop; the stage stays
        # playable and exposure simply stops accumulating this frame.
        STATE.m6_exposure = 0.0


def _update_camera():
    if not STATE.player:
        return int(STATE.camera_x), int(STATE.camera_y)
    w, h = _maps._live_map_dims()
    aim = None if STATE.player_dead else STATE.player.angle
    return follow_gameplay((STATE.player.rect.centerx, STATE.player.rect.centery),
                           w, h, aim_angle=aim, who="m6")


def _train_active():
    return bool(getattr(STATE, "m6_train_active", False))


def game_update(keys):
    _maps._last_keys = keys
    dt = float(getattr(STATE, "dt", 1.0 / 60.0))

    if _train_active():
        try:
            from . import train3d as _train
            _train.update(keys)
        except Exception:
            if (getattr(STATE, "player_dead", False)
                    or getattr(STATE, "m6_train_result", None) in ("dead", "failed")):
                # A broken death/failure frame is still a failed run: keep the
                # 3D context and go to the terminal instead of the ending film.
                STATE.m6_train_active = False
                STATE.m6_train_death = True
                STATE.request_death_screen = True
            else:
                try:
                    from . import train3d as _train
                    _train.force_finish("fallback")
                except Exception:
                    if getattr(STATE, "mission6_stage", None) == STAGE_TRAIN:
                        _flow.on_train_done("fallback")
        return _update_camera()

    p = STATE.player
    if p:
        p.update_iframes(dt)
    if getattr(STATE, "gc_flash_timer", 0) > 0:
        STATE.gc_flash_timer -= 1
    corpse.update_corpses()

    from entities import death_anim
    if p and p.hp <= 0 and not STATE.player_dead:
        death_anim.trigger_death()
    death_anim.update_death_anim()

    _update_player(keys)
    _update_melee()
    _update_weapon_timers()
    _update_shooting()
    _update_enemies()
    _update_bullets()
    _update_stealth(dt)
    _weapons.update_molotovs(_world.solid_walls())
    effects.update_casings(_world.solid_walls())
    effects.update_particles()
    effects.update_floating_texts()
    _flow.update_stage(dt)
    return _update_camera()
