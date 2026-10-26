"""Mission 1 breach roles (WP7): rusher / cover / flanker per wave enemy, and CIOCAN's
shoulder charge. ``missions.m1.update`` calls ``role_step`` / ``ciocan_step`` per enemy
before ``Enemy.update``; a True "handled" result means the role moved the enemy itself
this frame and ``Enemy.update`` is skipped."""
from __future__ import annotations

import math
from dataclasses import dataclass

import game.world as _gw
from core.config import SPEAKER_COLORS, TILE_SIZE, audio
from core.state import STATE
from engine.core import LEGACY_RNG as _rng_legacy
from engine.world import component
from entities.enemy_ai import Enemy
from fx import effects
from missions.m1.map import MAP_H, MAP_W

__all__ = ["M1Role"]

RUSHER_SPEED = 2.6
RUSHER_HOLD = (60, 120)          # closes to 120 px, no cover
COVER_HOLD = (200, 280)          # opens fire from 280 px, holds 200-280
FLANKER_SPEED = 2.4
FLANK_DIST = 260
FLANK_REACH = 48
FLANK_MAX_FRAMES = 300

CIOCAN_HP = 400
CIOCAN_TINT = (96, 30, 26)
CIOCAN_FLASH = (225, 40, 30)
CHARGE_COOLDOWN = (420, 540)     # 7-9 s
CHARGE_RANGE = (160, 420)
CHARGE_WINDUP = 48               # 0.8 s
CHARGE_SPEED = 9
CHARGE_DIST = 6 * TILE_SIZE
CHARGE_DAMAGE = 30
CHARGE_KNOCKBACK = 56
STUN_FRAMES = 90                 # 1.5 s
STUN_DAMAGE_MUL = 2


@component
@dataclass(slots=True)
class M1Role:
    kind: str = ""               # rusher / cover / flanker / ciocan
    wave: int = 0                # breach wave 1-3; 4 = exfil van drop
    flank_side: int = 1
    flank_angle: float = 0.0
    flank_t: int = 0
    flanked: bool = False


def role_of(e):
    """M1Role of an enemy, or None for enemies the wave director did not spawn."""
    return _gw.get(e, M1Role)


def spawn_role_enemy(x, y, kind, wave):
    """A breach-discipline enemy (hp 115, CHASE, alert 420) centred on (x, y) with its role."""
    e = Enemy(x, y)
    e.rect.center = (x, y)
    e.alerted = True
    e.state = "CHASE"
    p = STATE.player
    if p is not None:
        e.last_seen_pos = (p.rect.centerx + _rng_legacy.randint(-24, 24),
                           p.rect.centery + _rng_legacy.randint(-24, 24))
    else:
        e.last_seen_pos = (x, y)
    e.combat_alert_timer = 420
    e.is_ambush_enemy = True
    e.is_breach_enemy = True
    e.fire_weakness = 1.15
    e.hp = 115
    e.fire_cooldown = 40 + _rng_legacy.randint(0, 45)
    if kind == "rusher":
        e.speed = RUSHER_SPEED
        e.hold_range = RUSHER_HOLD
    elif kind == "cover":
        e.speed = _rng_legacy.uniform(1.9, 2.3)
        e.attack_range = COVER_HOLD[1]
        e.hold_range = COVER_HOLD
    else:
        e.speed = FLANKER_SPEED
    r = _gw.ensure(e, M1Role)
    r.kind, r.wave = kind, wave
    r.flank_side = _rng_legacy.choice((-1, 1))
    return e


def _flank_point(r, px, py):
    fx = px + math.cos(r.flank_angle) * FLANK_DIST
    fy = py + math.sin(r.flank_angle) * FLANK_DIST
    fx = max(TILE_SIZE + 16, min((MAP_W - 1) * TILE_SIZE - 16, fx))
    fy = max(TILE_SIZE + 16, min((MAP_H - 1) * TILE_SIZE - 16, fy))
    return fx, fy


def role_step(e, px, py, walls):
    """Per-frame role steering before Enemy.update; True = handled (skip Enemy.update)."""
    r = role_of(e)
    if r is None:
        return False
    if r.kind == "rusher" and e.state == "SEARCH":
        e.state, e.last_seen_pos, e.path = "CHASE", (px, py), []
    elif r.kind == "flanker" and not r.flanked:
        if r.flank_t == 0:
            # Fixed bearing, 90 deg around the player from where the flanker starts.
            r.flank_angle = (math.atan2(e.rect.centery - py, e.rect.centerx - px)
                             + r.flank_side * math.pi / 2)
        r.flank_t += 1
        fx, fy = _flank_point(r, px, py)
        if (r.flank_t > FLANK_MAX_FRAMES
                or math.hypot(fx - e.rect.centerx, fy - e.rect.centery) < FLANK_REACH
                or math.hypot(px - e.rect.centerx, py - e.rect.centery) < 120):
            r.flanked = True
            e.state, e.last_seen_pos = "CHASE", (px, py)
            e.path, e.path_timer = [], 0
            return False
        e._dt_mul = 60.0 * STATE.dt
        e.state = "CHASE"
        e._update_pathfinding(fx, fy, walls)
        e._move_toward(fx, fy, walls)
        return True
    return False


def spawn_ciocan(x, y):
    """CIOCAN: hp 400 miniboss with the shoulder charge; arrives with wave 2."""
    e = spawn_role_enemy(x, y, "ciocan", 2)
    e.hp = CIOCAN_HP
    e.speed = 1.8
    e.is_miniboss = True
    e.is_ambush_enemy = False
    e.fire_weakness = 1.0
    e.body_tint = CIOCAN_TINT
    STATE.m1_ciocan_mode = ""
    STATE.m1_ciocan_timer = 0
    STATE.m1_ciocan_cooldown = _rng_legacy.randint(*CHARGE_COOLDOWN)
    STATE.m1_ciocan_last_hp = e.hp
    return e


def _end_charge(e):
    STATE.m1_ciocan_mode = ""
    STATE.m1_ciocan_timer = 0
    STATE.m1_ciocan_cooldown = _rng_legacy.randint(*CHARGE_COOLDOWN)
    e.body_tint = CIOCAN_TINT
    e.path, e.path_timer = [], 0


def ciocan_step(e, walls, sight_walls):
    """CIOCAN's charge state machine. Returns (handled, hit_player): handled = he is in
    windup / dash / stun and Enemy.update is skipped; hit_player = the dash landed."""
    p = STATE.player
    if p is None:
        return False, False
    mode = getattr(STATE, "m1_ciocan_mode", "")
    if mode == "stun":
        # 2x damage while stunned: whatever landed since last frame lands again.
        lost = getattr(STATE, "m1_ciocan_last_hp", e.hp) - e.hp
        if lost > 0:
            e.hp -= lost * (STUN_DAMAGE_MUL - 1)
    STATE.m1_ciocan_last_hp = e.hp
    px, py = p.rect.centerx, p.rect.centery
    handled, hit = True, False
    if mode == "":
        STATE.m1_ciocan_cooldown -= 1
        dist = math.hypot(px - e.rect.centerx, py - e.rect.centery)
        if (STATE.m1_ciocan_cooldown <= 0 and CHARGE_RANGE[0] <= dist <= CHARGE_RANGE[1]
                and e._can_see(px, py, sight_walls)):
            STATE.m1_ciocan_mode = "windup"
            STATE.m1_ciocan_timer = CHARGE_WINDUP
            e.path = []
            e.angle = math.atan2(py - e.rect.centery, px - e.rect.centerx)
            STATE.floating_texts.append([e.rect.centerx, e.rect.centery - 40, "Hah!",
                                         SPEAKER_COLORS.get("CIOCAN", (205, 75, 60)), 50])
        else:
            handled = False
    elif mode == "windup":
        STATE.m1_ciocan_timer -= 1
        e.angle = math.atan2(py - e.rect.centery, px - e.rect.centerx)
        e.body_tint = CIOCAN_FLASH if (STATE.m1_ciocan_timer // 4) % 2 == 0 else CIOCAN_TINT
        if STATE.m1_ciocan_timer <= 0:
            STATE.m1_ciocan_mode = "dash"
            STATE.m1_ciocan_dir = (math.cos(e.angle), math.sin(e.angle))
            STATE.m1_ciocan_dash_left = float(CHARGE_DIST)
            e.body_tint = CIOCAN_TINT
    elif mode == "dash":
        dx, dy = STATE.m1_ciocan_dir
        step = min(CHARGE_SPEED * 60.0 * STATE.dt, STATE.m1_ciocan_dash_left)
        STATE.m1_ciocan_dash_left -= step
        mx, my = int(round(dx * step)), int(round(dy * step))
        bumped = False
        e.rect.x += mx
        for wall in walls:
            if e.rect.colliderect(wall):
                bumped = True
                if mx > 0:
                    e.rect.right = wall.left
                elif mx < 0:
                    e.rect.left = wall.right
        e.rect.y += my
        for wall in walls:
            if e.rect.colliderect(wall):
                bumped = True
                if my > 0:
                    e.rect.bottom = wall.top
                elif my < 0:
                    e.rect.top = wall.bottom
        if e.rect.inflate(8, 8).colliderect(p.rect):
            hit = p.take_damage(CHARGE_DAMAGE)
            for _ in range(4):
                p.move(dx * CHARGE_KNOCKBACK / 4, dy * CHARGE_KNOCKBACK / 4, walls)
            effects.shake(14)
            audio.play("bullet_impact_enemy", volume=0.7)
            _end_charge(e)
        elif bumped:
            STATE.m1_ciocan_mode = "stun"
            STATE.m1_ciocan_timer = STUN_FRAMES
            effects.shake(10)
            audio.play("door_rattle", volume=0.6)
            STATE.floating_texts.append([e.rect.centerx, e.rect.centery - 40, "STUNNED",
                                         (230, 200, 90), 60])
        elif STATE.m1_ciocan_dash_left <= 0:
            _end_charge(e)
    elif mode == "stun":
        STATE.m1_ciocan_timer -= 1
        if STATE.m1_ciocan_timer <= 0:
            _end_charge(e)
            e.state, e.last_seen_pos = "CHASE", (px, py)
    return handled, hit
