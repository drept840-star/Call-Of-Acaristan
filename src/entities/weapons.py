
"""Player weapons: pistol, melee, molotov cocktails, fire zones."""
import math
import random
from engine.core import LEGACY_RNG as _rng_legacy  # RPE6 R6: named 'legacy' rng stream
import pygame
from core.config import (
    WIDTH, HEIGHT, TILE_SIZE, audio, Particle, Casing, C_BLOOD,
    ENEMY_HEAR_RADIUS, get_scaled_mouse,
)
from core.state import STATE
from fx.effects import spawn_particles, shake, hit_stop
from core.user_settings import SETTINGS
from entities.art_cache import get_shadow, get_glow
from engine.core import now_ms as _now_ms  # RPE6 B-001 timebase
MOLOTOV_RADIUS = 92
MOLOTOV_DURATION = 300
# Per-frame damage inside the fire zone. A molotov actually deals damage
# from two sources at once - the molotov_fires loop in mission2.py and the
# FireZone in weapons.py - so per-frame values must stay modest or the
# total adds up to an instant kill.
#
# Tuned values: a standard IPA grunt (115 HP) standing at the centre of
# the fire dies in ~1.8 seconds. An enemy skirting the outer edge can
# escape with light damage. The player takes ~7-8 seconds of full-burn
# exposure to lose half their HP.
MOLOTOV_ENEMY_DAMAGE = 0.6
MOLOTOV_PLAYER_DAMAGE = 0.35


def _mission2_actions_blocked():
    """Hard safety gate for authored Mission 2 beats.

    The main loop also blocks input, but weapon functions can be reached from
    multiple paths.  Keeping this guard here prevents shooting/reload/molotov
    leaks during sniper/blackout/cinematic locks.
    """
    if getattr(STATE, "active_mission", "") != "MISSION2":
        return False
    return (
        getattr(STATE, "mission2_card", None) is not None
        or getattr(STATE, "mission2_stage", "") in {"sniper", "blackout", "done"}
    )


def _player_disarmed():
    """True when the player has no weapon at all (e.g. Mission 3's cell,
    before the chair breaks). Blocks ALL weapon actions."""
    return bool(getattr(STATE, "player_disarmed", False))


def _player_has_firearm():
    """True when the player has a ranged weapon (pistol / OS-12 / sidearm).

    M3's improvised weapons (chair_leg, shiv) are melee-only - they block
    shooting, reloading, molotovs, and weapon-switching. The player can
    only melee with them until they take a sidearm off a dead guard (which
    sets mission3_weapon to "sidearm" and re-enables ranged).
    """
    weapon = getattr(STATE, "mission3_weapon", "none")
    if weapon in ("chair_leg", "shiv"):
        return False
    if weapon == "sidearm":
        return True
    return not getattr(STATE, "player_disarmed", False)


class FireZone:
    """Persistent ground fire created by a Molotov impact."""
    def __init__(self, x, y):
        self.x = x
        self.y = y
        self.radius = 48
        self.life = 420
        self.max_life = 420
        self.damage_tick = 0
    def update(self, enemies, player_rect, audio_sys):
        self.life -= 1
        self.damage_tick += 1
        player_center = (player_rect.centerx, player_rect.centery) if player_rect else (self.x, self.y)
        if self.damage_tick >= 12:
            self.damage_tick = 0
            for e in enemies:
                if e.hp <= 0:
                    continue
                dist = math.hypot(e.rect.centerx - self.x, e.rect.centery - self.y)
                if dist < self.radius:
                    dmg = 15 if dist < self.radius * 0.4 else 8
                    fire_mult = e.fire_weakness
                    e.hp -= dmg * fire_mult
                    e.alerted = True
                    spark_count = 4 if e.is_breach_enemy else 3
                    for _ in range(spark_count):
                        STATE.particles.append(Particle(
                            e.rect.centerx + _rng_legacy.randint(-6, 6),
                            e.rect.centery + _rng_legacy.randint(-6, 6),
                            (255, _rng_legacy.randint(80, 210), 0)
                        ))
        if _rng_legacy.random() < 0.04 and audio_sys:
            audio_sys.play_3d("explosion", (self.x, self.y), player_center, base_volume=0.08)
        return self.life > 0
    def draw(self, surface, cam_x, cam_y):
        for d in self.drawables(cam_x, cam_y):
            d.draw(surface, 0, 0)

    def drawables(self, cam_x, cam_y):
        """RPE6 Phase 6: the burning patch as screen-space drawables (same numbers as ``draw``;
        the smoke wisps keep drawing from the legacy rng stream - submit order = legacy order)."""
        from engine.render2d import PolyDraw as _PolyDraw, SCREEN as _SCREEN, SurfaceDraw as _SurfaceDraw  # lazy
        sx = int(self.x - cam_x)
        sy = int(self.y - cam_y)
        if not (-self.radius - 60 < sx < WIDTH + self.radius + 60 and
                -self.radius - 60 < sy < HEIGHT + self.radius + 60):
            return
        life_ratio = max(0.0, self.life / self.max_life)
        flicker = 0.75 + 0.25 * math.sin(_now_ms() * 0.018)
        # Scorched irregular ground patch
        scorch = pygame.Surface((self.radius * 3, self.radius * 3), pygame.SRCALPHA)
        cx = cy = self.radius * 3 // 2
        rng = random.Random(int(self.x * 13 + self.y * 7))
        points = []
        for i in range(18):
            ang = i / 18.0 * math.pi * 2
            rr = self.radius * rng.uniform(0.75, 1.25)
            points.append((cx + math.cos(ang) * rr, cy + math.sin(ang) * rr * 0.72))
        pygame.draw.polygon(scorch, (10, 7, 5, int(115 * life_ratio)), points)
        pygame.draw.polygon(scorch, (45, 22, 8, int(80 * life_ratio)), points, 2)
        yield _SurfaceDraw(scorch, (sx - cx, sy - cy), space=_SCREEN)
        # Low orange glow, not a giant perfect circle
        glow = pygame.Surface((self.radius * 3, self.radius * 2), pygame.SRCALPHA)
        for r, a in [
            (self.radius + 25, 24),
            (self.radius, 40),
            (self.radius - 20, 65),
        ]:
            if r > 0:
                pygame.draw.ellipse(
                    glow,
                    (255, 95, 20, int(a * life_ratio * flicker)),
                    (
                        self.radius * 3 // 2 - r,
                        self.radius - int(r * 0.45),
                        r * 2,
                        int(r * 0.9),
                    ),
                )
        yield _SurfaceDraw(glow, (sx - self.radius * 3 // 2, sy - self.radius), space=_SCREEN)
        # Pixel flame tongues
        flame_count = int(9 * life_ratio) + 3
        for i in range(flame_count):
            seed = i * 31
            ang = seed * 0.77 + math.sin(_now_ms() * 0.004 + i)
            rr = self.radius * (0.15 + (i % 5) * 0.13)
            fx = sx + math.cos(ang) * rr
            fy = sy + math.sin(ang) * rr * 0.55
            h = int((18 + (i % 4) * 5) * life_ratio * flicker)
            w = max(4, h // 3)
            outer = [
                (fx, fy - h),
                (fx - w, fy + h * 0.25),
                (fx + w, fy + h * 0.25),
            ]
            inner = [
                (fx, fy - h * 0.6),
                (fx - w * 0.45, fy + h * 0.05),
                (fx + w * 0.45, fy + h * 0.05),
            ]
            yield _PolyDraw(outer, (255, 85, 18), space=_SCREEN)
            yield _PolyDraw(inner, (255, 205, 80), space=_SCREEN)
        # Smoke wisps
        if life_ratio > 0.2:
            for i in range(5):
                drift = math.sin(_now_ms() * 0.002 + i) * 12
                smoke_x = sx + int(drift) + (i - 2) * 12
                smoke_y = sy - 35 - i * 8
                sr = 7 + i
                smoke_a = int(32 * life_ratio)
                sm = pygame.Surface((sr * 2, sr * 2), pygame.SRCALPHA)
                pygame.draw.circle(sm, (45, 43, 40, smoke_a), (sr, sr), sr)
                yield _SurfaceDraw(sm, (smoke_x - sr, smoke_y - sr), space=_SCREEN)
        if life_ratio > 0.15:
            for _ in range(2):
                smoke_x = sx + _rng_legacy.randint(-int(self.radius * 0.5), int(self.radius * 0.5))
                smoke_y = sy - _rng_legacy.randint(10, 35)
                smoke_r = _rng_legacy.randint(4, 10)
                smoke_a = int(40 * life_ratio)
                smoke_s = pygame.Surface((smoke_r * 2, smoke_r * 2), pygame.SRCALPHA)
                pygame.draw.circle(smoke_s, (50, 45, 40, smoke_a),
                                   (smoke_r, smoke_r), smoke_r)
                yield _SurfaceDraw(smoke_s, (smoke_x - smoke_r, smoke_y - smoke_r), space=_SCREEN)
def _wall_blocks_line(x1, y1, x2, y2, solid_walls):
    for w in solid_walls:
        if w.clipline((x1, y1), (x2, y2)):
            return True
    return False
def _solid_walls():
    out = list(STATE.walls)
    for d in STATE.doors:
        if d.collision_rect:
            out.append(d.collision_rect)
    return out
def start_reload():
    if _mission2_actions_blocked():
        return
    if _player_disarmed():
        return
    if not _player_has_firearm():
        return   # melee-only weapon - no gun to reload
    current_weapon = getattr(STATE, "current_weapon", "pistol")
    is_os12 = current_weapon == "os12"
    is_k9 = current_weapon == "k9_smg"

    if is_os12:
        if (STATE.os12_spare_mags <= 0
                or STATE.os12_ammo_in_mag == STATE.os12_mag_size
                or STATE.is_reloading):
            return
        STATE.is_reloading = True
        STATE.reload_timer = 90  # heavier gun, slower reload
        audio.play("reload", volume=0.6)
    elif is_k9:
        if (getattr(STATE, "k9_spare_mags", 0) <= 0
                or getattr(STATE, "k9_ammo_in_mag", 0) == getattr(STATE, "k9_mag_size", 24)
                or STATE.is_reloading):
            return
        STATE.is_reloading = True
        STATE.reload_timer = 72  # unique SMG mag-pull / palm-slap reload
        audio.play("reload", volume=0.52)
    else:
        if (STATE.spare_mags <= 0
                or STATE.ammo_in_mag == STATE.mag_size
                or STATE.is_reloading):
            return
        STATE.is_reloading = True
        STATE.reload_timer = 60
        audio.play("reload", volume=0.6)

    if STATE.player:
        for _ in range(6):
            STATE.particles.append(Particle(
                STATE.player.rect.centerx + _rng_legacy.randint(-6, 6),
                STATE.player.rect.centery + _rng_legacy.randint(-4, 4),
                (160, 155, 140),
            ))
def handle_shoot():
    from entities.enemy_ai import enemy_hear_shot
    if _mission2_actions_blocked():
        return
    if _player_disarmed():
        return
    if not _player_has_firearm():
        # Mission 3 improvised weapons are melee-only. Let left-click use
        # the equipped chair leg / shiv instead of silently doing nothing.
        if getattr(STATE, "mission3_weapon", "none") in ("chair_leg", "shiv"):
            handle_melee()
        return   # melee-only weapon - no gun to fire
    current_weapon = getattr(STATE, "current_weapon", "pistol")
    is_os12 = current_weapon == "os12"
    is_k9 = current_weapon == "k9_smg"

    # Pick the right ammo/cooldown state for the active weapon
    if is_os12:
        ammo = STATE.os12_ammo_in_mag
        cooldown = STATE.os12_shot_cooldown
    elif is_k9:
        ammo = getattr(STATE, "k9_ammo_in_mag", 0)
        cooldown = getattr(STATE, "k9_shot_cooldown", 0)
    else:
        ammo = STATE.ammo_in_mag
        cooldown = STATE.shot_cooldown

    if (STATE.player_dead or not STATE.player
            or STATE.is_reloading or cooldown > 0):
        return
    if getattr(STATE.player, "weapon_raised", False):
        return
    # Block firing during weapon swap animation
    if getattr(STATE, "weapon_swap_timer", 0) > 0:
        return
    if ammo <= 0:
        audio.play("empty_click", volume=0.5)
        # Auto-reload (Gameplay → Auto-Reload setting) - only if user opted in
        # and the player has spare magazines.
        if SETTINGS.auto_reload:
            if is_os12 and STATE.os12_spare_mags > 0:
                start_reload()
            elif is_k9 and getattr(STATE, "k9_spare_mags", 0) > 0:
                start_reload()
            elif not is_os12 and not is_k9 and STATE.spare_mags > 0:
                start_reload()
        return

    p = STATE.player

    # ── Aim assist (Gameplay → Aim Assist setting) ──
    # Snap the player's aim slightly toward the closest visible enemy that's
    # already near the cursor line. Magnet strength is small (~6° max swing)
    # so it feels like a forgiveness window, not auto-targeting.
    if SETTINGS.aim_assist and STATE.enemies:
        best = None
        best_diff = math.radians(7.0)  # 7° cone
        px, py = p.rect.centerx, p.rect.centery
        cur_angle = p.angle
        solid = _solid_walls()
        for e in STATE.enemies:
            if e.hp <= 0:
                continue
            ex, ey = e.rect.centerx, e.rect.centery
            dist = math.hypot(ex - px, ey - py)
            if dist > 500 or dist < 40:
                continue
            target_angle = math.atan2(ey - py, ex - px)
            # Wrap-around safe angle diff
            diff = math.atan2(math.sin(target_angle - cur_angle),
                              math.cos(target_angle - cur_angle))
            adiff = abs(diff)
            if adiff < best_diff and not _wall_blocks_line(px, py, ex, ey, solid):
                best_diff = adiff
                best = (target_angle, diff)
        if best is not None:
            # Pull halfway toward the target (smooth, not snap)
            p.angle = cur_angle + best[1] * 0.5

    if hasattr(p, "barrel_tip"):
        bx, by = p.barrel_tip()
    else:
        bx = p.rect.centerx + math.cos(p.angle) * 39
        by = p.rect.centery + math.sin(p.angle) * 39

    # OS 12: slightly slower bullet, longer range.
    # Damage history:
    #   35 (original)  - trivialized M2, killed anything in 3-4 shots.
    #   22 (nerf #1)   - overcorrected, felt too weak (6 shots per grunt,
    #                    5 per reinforcement, mag emptied after 3 kills).
    #   28 (current)   - middle ground. 115-HP grunt takes 5 shots, 100-HP
    #                    reinforcement takes 4. With 25-round mag = 5 clean
    #                    kills per mag. Player must aim but isn't punished
    #                    for spraying under pressure.
    # Mag size history: 30 → 20 → 25 (same middle-ground logic).
    # Spare mags: capped at exactly 2 from pickup, no mid-mission rewards -
    # ammo scarcity is the design tension that makes the OS-12 feel earned.
    if is_os12:
        bullet_speed = 22
        bullet_life = 24
        bullet_damage = 28
    elif is_k9:
        bullet_speed = 25
        bullet_life = 18
        bullet_damage = 18
    else:
        bullet_speed = 24
        bullet_life = 20
        bullet_damage = 50

    STATE.bullets.append({
        "x": bx, "y": by,
        "prev_x": bx, "prev_y": by,
        "dx": math.cos(p.angle) * bullet_speed,
        "dy": math.sin(p.angle) * bullet_speed,
        "life": bullet_life,
        "owner": "player",
        "damage": bullet_damage,
    })
    solid_for_noise = _solid_walls()
    if is_k9:
        # Suppressed, not silent: only nearby guards with a clear acoustic path
        # react. Keeps the K-9 useful in the black-site without making it magic.
        for e in STATE.enemies:
            if math.hypot(e.rect.centerx - bx, e.rect.centery - by) <= ENEMY_HEAR_RADIUS * 0.45:
                if not _wall_blocks_line(bx, by, e.rect.centerx, e.rect.centery, solid_for_noise):
                    e.hear_shot(bx, by, solid_for_noise)
    else:
        enemy_hear_shot(bx, by, STATE.enemies, solid_for_noise)

    if is_os12:
        shake(28)
        hit_stop(0.04)  # rifle weight: brief freeze so the shot lands heavy
        STATE.cam_kick_x = -math.cos(p.angle) * 30.0
        STATE.cam_kick_y = -math.sin(p.angle) * 30.0
        STATE.crosshair_kick = 9
    elif is_k9:
        shake(8)
        # No hit-stop on the suppressed SMG - it should feel fast, not heavy.
        STATE.cam_kick_x = -math.cos(p.angle) * 9.0
        STATE.cam_kick_y = -math.sin(p.angle) * 9.0
        STATE.crosshair_kick = 4
    else:
        shake(18)
        hit_stop(0.03)  # 2-frame punch on the trigger pull
        STATE.cam_kick_x = -math.cos(p.angle) * 20.0
        STATE.cam_kick_y = -math.sin(p.angle) * 20.0
        STATE.crosshair_kick = 6

    STATE.muzzle_flash_timer = 5 if is_os12 else (2 if is_k9 else 4)

    # Recoil
    if is_os12:
        p._recoil_timer = 12
        p._recoil_offset = -10.0
        p._slide_timer = 0  # no slide on a rifle
    elif is_k9:
        p._recoil_timer = 5
        p._recoil_offset = -3.5
        p._slide_timer = 0
    else:
        p._recoil_timer = 8
        p._recoil_offset = -6.0
        p._slide_timer = 6

    # Casing eject - OS 12 ejects further
    eject_offset = 13 if is_os12 else 10
    STATE.casings.append(Casing(
        p.rect.centerx + math.cos(p.angle) * 8
        + math.cos(p.angle - math.pi / 2) * eject_offset,
        p.rect.centery + math.sin(p.angle) * 8
        + math.sin(p.angle - math.pi / 2) * eject_offset,
        p.angle - math.pi / 2,
    ))

    # Consume ammo
    if is_os12:
        STATE.os12_ammo_in_mag -= 1
        STATE.os12_shot_cooldown = 8   # full-auto: ~7.5 shots/sec (~450 RPM, AK cadence)
    elif is_k9:
        STATE.k9_ammo_in_mag -= 1
        STATE.k9_shot_cooldown = 5     # compact SMG cadence (~720 RPM equivalent)
    else:
        STATE.ammo_in_mag -= 1
        STATE.shot_cooldown = 12       # semi-auto: ~5 shots/sec

    STATE.shots_fired += 1

    if is_os12:
        audio.play("gunshot", volume=0.8)  # louder, heavier
    elif is_k9:
        audio.play("gunshot", volume=0.34)  # suppressed SMG thump
    else:
        audio.play("gunshot", volume=0.7)

    # Auto-reload on empty (Gameplay → Auto-Reload)
    if SETTINGS.auto_reload:
        if is_os12 and STATE.os12_ammo_in_mag <= 0 and STATE.os12_spare_mags > 0:
            start_reload()
        elif is_k9 and STATE.k9_ammo_in_mag <= 0 and STATE.k9_spare_mags > 0:
            start_reload()
        elif not is_os12 and not is_k9 and STATE.ammo_in_mag <= 0 and STATE.spare_mags > 0:
            start_reload()
def handle_melee():
    if _mission2_actions_blocked():
        return
    if _player_disarmed():
        return
    if STATE.player_dead or not STATE.player or STATE.melee_active:
        return
    STATE.is_reloading = False
    STATE.reload_timer = 0
    STATE.melee_active = True
    # Melee timer + damage scale with the equipped weapon. The chair leg is
    # slow and blunt; the shiv is fast and piercing. Default (M1/M2) is the
    # original pistol-butt value.
    weapon = getattr(STATE, "mission3_weapon", "none")
    if weapon == "chair_leg":
        STATE.melee_timer = 24
        STATE.melee_damage = 50
    elif weapon == "shiv":
        STATE.melee_timer = 14
        STATE.melee_damage = 85
    elif weapon == "k9_smg":
        # Quick buttstroke / muzzle shove with the compact SMG.
        STATE.melee_timer = 20
        STATE.melee_damage = 62
    else:
        STATE.melee_timer = 18
        STATE.melee_damage = 78
    STATE.melee_duration = STATE.melee_timer   # lets draw code compute 0..1 swing progress
    STATE.melee_hit_done = False
    audio.play("melee_hit", volume=0.6)
def handle_throw_bottle():
    if _mission2_actions_blocked():
        return
    if _player_disarmed():
        return
    if not _player_has_firearm():
        return   # melee-only weapon - no molotovs
    if STATE.player_dead or not STATE.player:
        return
    if STATE.player_bottles <= 0:
        STATE.floating_texts.append([
            STATE.player.rect.centerx,
            STATE.player.rect.centery - 40,
            "NO MOLOTOVS", (220, 60, 60), 60,
        ])
        return
    mx, my = get_scaled_mouse()
    world_mx = mx + STATE.camera_x
    world_my = my + STATE.camera_y
    dx = world_mx - STATE.player.rect.centerx
    dy = world_my - STATE.player.rect.centery
    dist = math.hypot(dx, dy)
    if dist > 400:
        world_mx = STATE.player.rect.centerx + (dx / dist) * 400
        world_my = STATE.player.rect.centery + (dy / dist) * 400
    STATE.player_bottles -= 1
    STATE.thrown_bottles.append({
        "x": STATE.player.rect.centerx,
        "y": STATE.player.rect.centery,
        "start_x": STATE.player.rect.centerx,
        "start_y": STATE.player.rect.centery,
        "tx": world_mx, "ty": world_my,
        "t": 0.0, "speed": 0.035,
        "spin": _rng_legacy.uniform(0, 360),
    })
    audio.play("molotov_throw", volume=0.6)
def spawn_molotov_fire(tx, ty, solid_walls):
    STATE.molotov_fires.append({
        "x": tx, "y": ty,
        "life": MOLOTOV_DURATION,
        "max_life": MOLOTOV_DURATION,
    })
    STATE.fire_zones.append(FireZone(tx, ty))
    shake(12)
    listener = ((STATE.player.rect.centerx, STATE.player.rect.centery)
                if STATE.player else (tx, ty))
    audio.play_3d("molotov_explode", (tx, ty), listener, base_volume=0.9)
    # ── Impact burst ──
    for _ in range(40): spawn_particles(tx, ty, (255, 200, 80), 1)
    for _ in range(30): spawn_particles(tx, ty, (255, 120, 35), 1)
    for _ in range(24): spawn_particles(tx, ty, (80, 75, 70), 1)
    for _ in range(15): spawn_particles(tx, ty, (190, 220, 190), 1)
    # Fire bloom ring expands outward
    for ring_r in range(10, 80, 8):
        for ang in range(0, 360, 30):
            ang_r = math.radians(ang)
            px = tx + math.cos(ang_r) * ring_r
            py = ty + math.sin(ang_r) * ring_r
            STATE.particles.append(Particle(px, py, (255, _rng_legacy.randint(80, 180), 0)))
            STATE.particles[-1].life = _rng_legacy.randint(12, 24)
            STATE.particles[-1].dy -= _rng_legacy.uniform(0.5, 1.5)
    for e in STATE.enemies:
        d = math.hypot(e.rect.centerx - tx, e.rect.centery - ty)
        if d < MOLOTOV_RADIUS * 2.4 and not _wall_blocks_line(
                tx, ty, e.rect.centerx, e.rect.centery, solid_walls):
            e.alerted = True
            e.last_seen_pos = (tx, ty)
            if d < MOLOTOV_RADIUS:
                e.state = "CHASE"
            elif e.state in ("IDLE", "PATROL"):
                e.state = "SEARCH"
                e.search_timer = 240
                e.distraction_target = (tx, ty)
                e.path = []


def update_molotovs(solid_walls, player_damage_allowed=True):
    """Advance the molotov system one frame: bottle flight + ground fire.

    Lifted verbatim from Mission 1's ``game_update`` so every mission runs
    the *same* molotov: the in-flight bottle tracks toward its target and
    detonates on walls, then each fire burns for its lifetime dealing
    heat-scaled damage, spawning embers, and alerting/distracting guards
    (a fire only pulls an uncommitted guard into SEARCH - it never yanks
    a guard already in CHASE/ATTACK away from the player).

    ``player_damage_allowed`` lets a mission suspend the player's own burn
    damage during authored locked beats (Mission 2's sniper / blackout /
    mission cards) without altering any other behavior. Missions that do
    not pass it keep Mission 1's exact handling.

    Returns ``True`` when the player took fire damage this frame.
    """
    player_hit = False

    # ── Bottles in flight: travel toward the target, stop at walls ──
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
            spawn_molotov_fire(impact_x, impact_y, solid_walls)
            STATE.thrown_bottles.remove(b)
        else:
            b["x"] = new_x
            b["y"] = new_y

    # ── Molotov fire damage ──
    for fire in STATE.molotov_fires[:]:
        fire["life"] -= 1
        fx, fy = fire["x"], fire["y"]
        if _rng_legacy.random() < 0.75:
            px = fx + _rng_legacy.uniform(-MOLOTOV_RADIUS * 0.55, MOLOTOV_RADIUS * 0.55)
            py = fy + _rng_legacy.uniform(-MOLOTOV_RADIUS * 0.55, MOLOTOV_RADIUS * 0.55)
            if math.hypot(px - fx, py - fy) < MOLOTOV_RADIUS * 0.65:
                col = _rng_legacy.choice([(255, 95, 25), (255, 150, 40), (255, 210, 80), (80, 70, 65)])
                p = Particle(px, py, col)
                p.dy -= _rng_legacy.uniform(1.0, 2.4)
                p.dx *= 0.35
                p.life = _rng_legacy.randint(18, 34)
                STATE.particles.append(p)
        for e in STATE.enemies:
            dist = math.hypot(e.rect.centerx - fx, e.rect.centery - fy)
            if dist < MOLOTOV_RADIUS and not _wall_blocks_line(
                fx, fy, e.rect.centerx, e.rect.centery, solid_walls
            ):
                heat = 1.0 - dist / MOLOTOV_RADIUS
                fire_mult = e.fire_weakness
                e.hp -= MOLOTOV_ENEMY_DAMAGE * (0.45 + heat) * fire_mult
                if e.is_breach_enemy and _rng_legacy.random() < 0.018:
                    STATE.particles.append(Particle(e.rect.centerx, e.rect.centery, (255, 190, 70)))
                e.alerted = True
                e.combat_alert_timer = max(e.combat_alert_timer, 300)
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
                        e.search_timer = max(e.search_timer, 120)
                if _rng_legacy.random() < 0.12:
                    STATE.particles.append(
                        Particle(e.rect.centerx, e.rect.centery, (255, 110, 30))
                    )
        if player_damage_allowed and STATE.player and not STATE.player_dead:
            pdist = math.hypot(STATE.player.rect.centerx - fx, STATE.player.rect.centery - fy)
            player_burn_radius = MOLOTOV_RADIUS * 0.72
            if pdist < player_burn_radius and not _wall_blocks_line(
                fx, fy, STATE.player.rect.centerx, STATE.player.rect.centery, solid_walls
            ):
                heat = 1.0 - pdist / player_burn_radius
                # Route through take_damage() so i-frames apply. Molotov burns
                # tick every frame; without i-frames the player could lose
                # 100+ HP in a single step into a fire zone.
                if STATE.player.take_damage(MOLOTOV_PLAYER_DAMAGE * (0.35 + heat)):
                    player_hit = True
        if fire["life"] <= 0:
            STATE.molotov_fires.remove(fire)

    # Process active fire zones (persistent ground fire spawned on impact)
    if STATE.player and not STATE.player_dead:
        STATE.fire_zones[:] = [fz for fz in STATE.fire_zones if fz.update(
            STATE.enemies, STATE.player.rect, audio
        )]
    return player_hit


def draw_thrown_bottles(surface, cam_x, cam_y):
    """Draw molotovs currently in flight.

    Shared by every mission so the throw reads the same everywhere - a
    spinning bottle on a parabolic arc, a contact shadow that fades as it
    rises, a burning wick, and a short flame/smoke trail. Lifted verbatim
    from Mission 1's draw pass.
    """
    for b in STATE.thrown_bottles:
        t = b["t"]
        arc_height = 40
        arc_y_off = -math.sin(t * math.pi) * arc_height
        bx = b["x"] - cam_x
        by = b["y"] - cam_y + arc_y_off
        shadow_alpha = int(60 * (1 - abs(arc_y_off / arc_height)))
        shadow_surf = get_shadow(14, 5, 'ellipse', alpha=255)
        shadow_surf.set_alpha(shadow_alpha)
        surface.blit(shadow_surf, (int(bx - 7), int(b["y"] - cam_y - 2)))
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
        pygame.draw.polygon(surface, (95, 70, 35), bottle_pts)
        pygame.draw.polygon(surface, (210, 150, 60), bottle_pts, 1)
        pygame.draw.line(surface, (255, 120, 35), _rot(0, 1), _rot(0, 10), 3)
        pygame.draw.line(surface, (255, 210, 110), _rot(-2.5, 0), _rot(-2.5, 8), 1)
        pygame.draw.line(surface, (70, 55, 35), _rot(0, -13), _rot(0, -19), 3)
        flame_tip = _rot(0, -27)
        flame_l = _rot(-5, -17)
        flame_r = _rot(5, -17)
        flame_mid_l = _rot(-2.5, -18)
        flame_mid_r = _rot(2.5, -18)
        flame_mid_t = _rot(0, -24)
        flame_glow = get_glow(15, (255, 100, 20), 80)
        surface.blit(flame_glow, (int(flame_tip[0] - 17), int(flame_tip[1] - 17)))
        pygame.draw.polygon(surface, (255, 80, 15), [flame_tip, flame_l, flame_r])
        pygame.draw.polygon(surface, (255, 220, 80), [flame_mid_t, flame_mid_l, flame_mid_r])
        for trail_i in range(5):
            trail_t = max(0, t - 0.025 * (trail_i + 1))
            trail_arc = -math.sin(trail_t * math.pi) * arc_height
            trail_x = b["start_x"] + (b["tx"] - b["start_x"]) * trail_t - cam_x
            trail_y = b["start_y"] + (b["ty"] - b["start_y"]) * trail_t - cam_y + trail_arc
            ta = 110 - trail_i * 18
            ts = pygame.Surface((10, 10), pygame.SRCALPHA)
            if trail_i < 2:
                pygame.draw.circle(ts, (255, 120, 30, ta), (5, 5), 4)
            else:
                pygame.draw.circle(ts, (70, 65, 60, ta), (5, 5), 4)
            surface.blit(ts, (int(trail_x - 5), int(trail_y - 5)))


def switch_weapon():
    """Toggle between pistol and OS 12 (Q key)."""
    if _player_disarmed():
        return
    if not _player_has_firearm():
        return   # melee-only weapon - nothing to switch to
    # Mission 3: pistol <-> K-9 swap once both are carried.
    if (getattr(STATE, "k9_unlocked", False)
            and getattr(STATE, "mission3_sidearm_acquired", False)):
        if getattr(STATE, "weapon_swap_timer", 0) > 0:
            return
        target = "k9_smg" if STATE.current_weapon == "pistol" else "pistol"
        STATE.weapon_swap_timer = STATE.weapon_swap_duration
        STATE.weapon_swap_pending = target
        STATE.weapon_swap_sound_played = False
        STATE.is_reloading = False
        STATE.reload_timer = 0
        return
    if not getattr(STATE, "os12_unlocked", False):
        return
    if STATE.is_reloading:
        return
    if STATE.player_dead or not STATE.player:
        return
    # Block if a swap is already in progress
    if getattr(STATE, "weapon_swap_timer", 0) > 0:
        return

    # Determine target weapon (flipped at midpoint, not immediately)
    target = "os12" if STATE.current_weapon == "pistol" else "pistol"

    # Kick off the swap animation
    STATE.weapon_swap_timer = STATE.weapon_swap_duration
    STATE.weapon_swap_pending = target
    STATE.weapon_swap_sound_played = False

    # Cancel any in-progress reload since we initiated a swap
    STATE.is_reloading = False
    STATE.reload_timer = 0
