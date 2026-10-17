
"""Split from mission2.py - see mission2.py (shim) for the map."""
# missions.m2 package
# ------------------------------------------------------------

"""Mission 2: Quiet on Route 12 - clean cinematic vertical slice.

This module keeps the existing game integration intact:
    - game_core.start_mission2()
    - game_core.game_update()/game_draw() routing
    - acaristan.py Mission 2 intro and ending cutscenes
    - save as MISSION_2
    - dev command: python acaristan.py --dev-mission2


"""

import math
from engine.core import LEGACY_RNG as _rng_legacy  # RPE6 R6: named 'legacy' rng stream
import time

import pygame

from core.config import (C_BLOOD, C_TERMINAL, ENEMY_DAMAGE, Particle, TILE_SIZE, audio, get_scaled_mouse)
from entities.art_cache import get_blood_decal, get_fullscreen_overlay, get_tinnitus_bar, get_panel_bg
from core.state import STATE
from entities.player import Player, resolve_melee
from entities.enemy_ai import Enemy
from entities import corpse
from ui.hud import MiniMap, draw_objective_panel, draw_pinned_radio
from core.interactions import trigger_radio_chatter
from entities.weapons import (
    update_molotovs,
    spawn_molotov_fire as _spawn_molotov_fire,
    _wall_blocks_line,
    MOLOTOV_RADIUS,
    MOLOTOV_ENEMY_DAMAGE,
    MOLOTOV_PLAYER_DAMAGE,
    handle_shoot,
)
from fx import effects
from core.camera import update_camera, reset_camera_state, collide_bullet_walls, draw_bullets
from core.camera import tick_camera_fx, CAM_EASE_FOCUS, CAM_EASE_M2, CAM_DEADZONE_PX, CAM_LOOKAHEAD_PX

from missions.m2 import world as _m2_world  # _last_keys owner
from missions.m2.meta import CONTROL_ROOM, EXFIL_POS, KILL_ZONE, MAP_H, MAP_W, MISSION2_KEY, REQUIRED_INVESTIGATION_CLUES, SAFE_ZONE, SNIPER_CLOSE_AIM_FRAMES, STAGE_BLACKOUT, STAGE_COMBAT, STAGE_DONE, STAGE_EVIDENCE, STAGE_EXFIL, STAGE_INVESTIGATE, STAGE_RUN, STAGE_SNIPER, STAGE_TANKER, STAGE_TRUCK, STAGE_UPLOAD, TANKER_POS, UPLOAD_TERMINAL_POS, _beat
from missions.m2.world import _burst, _close_card, _dist, _near, _open_card, _player_pos, _radio, _set_objective, _solid_walls, _sync_story_prop_collisions
from missions.m2.starts import _clue_count, _evidence_count
from missions.m2.sniper import _add_sniper_laser, _complete_mission2, _explode_tanker, _sniper_actor_pos, _start_sniper_sequence, _start_tanker_run, _update_evidence_waves, _update_post_sniper_gameplay, _update_sniper_sequence, _update_squad_ambient, _update_travel_triggers
import game.world as _gw  # RPE6 Phase 5 (D4): mission data lives in components
from missions.m2.components import M2Role as _M2Role


def _m2g(e):
    """Declared M2 data of an enemy (replaces the ad hoc ``e.m2_*`` attributes)."""
    return _gw.ensure(e, _M2Role)


def handle_interact():
    """Mission-specific [E] interactions. Called through game_core."""
    if not STATE.player or STATE.player_dead:
        return
    if getattr(STATE, "mission2_card", None):
        if STATE.mission2_card.get("age", 0) >= 18:
            _close_card()
        return

    stage = STATE.mission2_stage
    if stage == STAGE_SNIPER:
        gabi_pos = _sniper_actor_pos(0)
        if _dist(_player_pos(), gabi_pos) < 90:
            # Point 10: Player can try to save Gabi during the 40-frame window
            # Input is read but does nothing; acknowledged later in Vasile line
            window_start = _beat("movement_one", "tried_to_save_window_start", 340)
            window_end = _beat("movement_one", "tried_to_save_window_end", 380)
            pt = int(getattr(STATE, "mission2_sniper_phase_timer", 0))
            if window_start <= pt < window_end:
                if not getattr(STATE, "mission2_tried_to_save", False):
                    STATE.mission2_tried_to_save = True
                    # Store that player tried - will be acknowledged later
                    STATE.mission2_tried_to_save_acknowledged = False
            return
    if stage == STAGE_INVESTIGATE:
        for clue in STATE.mission2_clues:
            if not clue["done"] and _near(clue["pos"], 86):
                clue["done"] = True
                STATE.mission2_clues_found.add(clue["id"])
                _open_card(clue["title"], clue["lines"], color=(245, 190, 65), kind=clue.get("kind", "document"))
                if _clue_count() >= REQUIRED_INVESTIGATION_CLUES:
                    _set_objective("Regroup at the blue toll-barrier marker")
                return
    elif stage == STAGE_TRUCK:
        truck = STATE.mission2_truck_manifest
        if not truck["done"] and _near(truck["pos"], 100):
            truck["done"] = True
            _open_card(truck["title"], truck["lines"], color=(255, 190, 90), after="truck_done", kind=truck.get("kind", "manifest"))
            return
    elif stage == STAGE_TANKER:
        inspection = STATE.mission2_tanker_inspection
        if not inspection["done"] and _near(inspection["pos"], 140):
            inspection["done"] = True
            STATE.mission2_tanker_inspected = True
            _open_card(
                inspection["title"],
                inspection["lines"],
                color=(255, 120, 60),
                after="tanker_inspected",
                kind=inspection.get("kind", "document"),
            )
            return
    elif stage == STAGE_EVIDENCE:
        # Old behaviour blocked evidence pickup if ANY enemy existed anywhere
        # on the map. That made the cleanup team too punishing if a stray
        # grunt spawned far from the player. Now block only when an enemy
        # is actually near the evidence the player is trying to grab.
        if STATE.enemies and any(
            (not ev.get("done"))
            and _near(ev["pos"], 82)
            and any(math.hypot(e.rect.centerx - ev["pos"][0],
                               e.rect.centery - ev["pos"][1]) < 220
                    for e in STATE.enemies)
            for ev in STATE.mission2_evidence
        ):
            STATE.floating_texts.append([STATE.player.rect.centerx, STATE.player.rect.centery - 42, "CLEAR IPA CONTACTS FIRST", (255, 120, 75), 90])
            return
        for ev in STATE.mission2_evidence:
            if not ev["done"] and _near(ev["pos"], 82):
                # Evidence positions are now arranged so the player encounters
                # them in narrative order (decree → balaceanu → mag_packet)
                # by walking through the control building south-to-north.
                # No lock-out needed - the level layout guides the order.
                ev["done"] = True
                after = "evidence_ready" if _evidence_count() >= 3 else None
                _open_card(ev["title"], ev["lines"], color=C_TERMINAL, after=after, kind=ev.get("kind", "terminal"))
                return
        if _evidence_count() >= 3 and _near(UPLOAD_TERMINAL_POS, 95):
            _set_objective("Hold [E] at the upload terminal")


def blocks_player_actions():
    """True when the main input router should suppress weapons/items."""
    return (
        getattr(STATE, "active_mission", "") == MISSION2_KEY
        and (
            getattr(STATE, "mission2_card", None) is not None
            or getattr(STATE, "mission2_stage", "") in (STAGE_SNIPER, STAGE_BLACKOUT, STAGE_DONE)
        )
    )


def debug_jump_to_evidence():
    if not STATE.player:
        return
    STATE.mission2_stage = STAGE_EVIDENCE
    STATE.mission_phase = "m2_debug_evidence"
    STATE.mission2_comms_cut = True
    STATE.mission2_tanker_exploded = True
    STATE.mission2_camera_focus = None
    STATE.enemies.clear()
    STATE.player.rect.center = CONTROL_ROOM
    _set_objective("Debug: inspect green evidence terminals")


# ─────────────────────────────────────────────
# Stage update
# ─────────────────────────────────────────────
def _movement_locked():
    return (
        STATE.player_dead
        or STATE.mission2_stage in (STAGE_SNIPER, STAGE_BLACKOUT, STAGE_DONE)
        or getattr(STATE, "mission2_card", None) is not None
    )


def _update_stage(keys):
    stage = STATE.mission2_stage
    STATE.mission2_timer += 1
    if getattr(STATE, "mission2_card", None):
        STATE.mission2_card["age"] += 1
        return

    if stage == STAGE_INVESTIGATE:
        count = _clue_count()
        total = len(STATE.mission2_clues)
        if count < REQUIRED_INVESTIGATION_CLUES:
            _set_objective(f"Inspect staged evidence markers with [E] ({count}/{REQUIRED_INVESTIGATION_CLUES})")
        else:
            _set_objective("Regroup at the blue toll-barrier marker")
            if count >= total and "all_clues_warning" not in STATE.mission2_events:
                STATE.mission2_events.add("all_clues_warning")
                _radio('VASILE: "Range marks, timing relay, clean boots... this scene is a trap."', color=(255, 170, 80), mark="all_clues")
            if _near(KILL_ZONE, 120):
                _start_sniper_sequence()

    elif stage == STAGE_SNIPER:
        _update_sniper_sequence()

    elif stage == STAGE_COMBAT:
        _update_post_sniper_gameplay()
        post_phase = getattr(STATE, "mission2_post_sniper_phase", "")
        # Only allow combat -> truck once the flank cutscene has actually played.
        # Otherwise emptying STATE.enemies during get_cover/survive/clear
        # silently skips the rest of the act.
        # Only advance to STAGE_TRUCK once the cleanup team (spawned in the
        # "done" phase) has been cleared. If enemies are still alive, fall
        # through to the elif below which shows the live enemy-count objective.
        # CRITICAL: also gate on the flank cutscene being finished. Without
        # this, the frame the flank triggers (phase becomes "done", sniper
        # removed, STATE.enemies empty) the gate passes and the game skips
        # straight to STAGE_TRUCK - the "done" branch that spawns the
        # cleanup team never runs.
        if (post_phase == "done"
                and not STATE.enemies
                and getattr(STATE, "mission2_flank_cutscene_timer", 0) <= 0):
            STATE.mission2_post_sniper_phase = ""
            STATE.mission2_stage = STAGE_TRUCK
            STATE.mission_phase = "m2_truck"
            _set_objective("Inspect the IPA truck manifest with [E]")
            _radio('VASILE: "No MAG soldiers. Find out why that IPA truck is here."', mark="truck")
        elif STATE.enemies and post_phase in ("", "clear", "done"):
            ground_enemies = [e for e in STATE.enemies if not _m2g(e).sniper]
            if ground_enemies:
                _set_objective(f"CLEAR REMAINING IPA CONTACTS ({len(ground_enemies)} left)")
    elif stage == STAGE_TRUCK:
        _set_objective("Inspect the IPA truck manifest with [E]")
    elif stage == STAGE_TANKER:
        inspection = getattr(STATE, "mission2_tanker_inspection", None)
        inspected = getattr(STATE, "mission2_tanker_inspected", False)
        if inspected:
            _start_tanker_run()
        elif inspection and _near(inspection["pos"], 140):
            _set_objective("Inspect the tanker valve with [E]")
        else:
            _set_objective("Approach the fuel tanker - inspect with [E]")
    elif stage == STAGE_RUN:
        # --- Pre-blast tension wind-up (last 90 frames of the countdown).
        # Detonator beeps accelerate, radio static rises, camera tightens
        # on the tanker, low rumble builds. This is the "oh god oh god"
        # moment that makes the actual bang land. ---
        cd = getattr(STATE, "mission2_countdown", 0)
        if cd < 90 and cd > 0:
            tension = (90 - cd) / 90.0  # 0 -> 1 as we approach detonation
            STATE.mission2_tension_phase = tension
            # Accelerating detonator beeps - every 18 frames early, every 5 late.
            beep_interval = max(5, int(18 - 13 * tension))
            if cd % beep_interval == 0:
                audio.play("empty_click", volume=0.4 + 0.5 * tension)
            # Rising radio static + low rumble in the last 45 frames.
            if cd < 45 and cd % 30 == 0:
                audio.play("radio_static", volume=0.15 + 0.25 * tension)
            if cd < 30 and cd % 15 == 0:
                audio.play("rig_low_boom", volume=0.15 + 0.35 * tension)
            # Creeping screen shake - barely perceptible early, real by the end.
            STATE.screen_shake = max(STATE.screen_shake, int(8 * tension))
            # Last 15 frames: camera slowly drifts toward the tanker so the
            # player sees the blast coming.
            if cd < 15:
                STATE.mission2_camera_focus = TANKER_POS
                STATE.mission2_camera_focus_timer = 15
        else:
            STATE.mission2_tension_phase = 0
        if _near(SAFE_ZONE, 105):
            STATE.mission2_countdown = min(STATE.mission2_countdown, 90)
            _set_objective("Stay in cover - brace for the tanker blast")
        else:
            _set_objective("RUN to the blue shelter marker before the tanker detonates")
        STATE.mission2_countdown -= 1
        if STATE.mission2_countdown <= 0:
            _explode_tanker()
    elif stage == STAGE_BLACKOUT:
        # Gate on not player_dead - if the player died during the blast,
        # the death animation is running and we should NOT open the
        # "COMMS LOST" card. Opening it during death leaves a stale card
        # in STATE.mission2_card that can interfere with the restart path.
        if STATE.mission2_timer >= 210 and not STATE.player_dead:
            _open_card(
                "COMMS LOST",
                [
                    "Vasile cuts out mid-sentence.",
                    "The checkpoint loudspeakers are dead.",
                    "Only the control building still has power.",
                ],
                color=(165, 170, 180),
                after="blast_done",
                kind="static",
            )
    elif stage == STAGE_EVIDENCE:
        # Drive the multi-wave reinforcement schedule. Spawns waves 2 and 3
        # on a timer / when the previous wave is cleared. Wave 1 was already
        # spawned by _spawn_control_cleanup() when the blast_done card closed.
        _update_evidence_waves()
        found = _evidence_count()
        if STATE.enemies:
            wave = getattr(STATE, "mission2_evidence_wave", 1)
            _set_objective(f"Clear IPA cleanup team - wave {wave}/3 ({len(STATE.enemies)} left)")
        elif found < 3:
            _set_objective(f"Inspect green evidence terminals with [E] ({found}/3)")
        else:
            _set_objective("Hold [E] at the upload terminal")
            if _near(UPLOAD_TERMINAL_POS, 95) and keys[pygame.K_e]:
                STATE.mission2_stage = STAGE_UPLOAD
                STATE.mission_phase = "m2_upload"
                STATE.mission2_timer = 0
    elif stage == STAGE_UPLOAD:
        # ── Upload OS integration ──
        # The old "hold [E] to fill progress bar" mechanic is replaced by a
        # full retro CRT OS (upload_os.py). When the player presses [E] at
        # the upload terminal, the OS boots and takes over the screen.
        #
        # NOTE: When the OS IS active, game_update() returns early (before
        # _update_stage is reached) and handles the OS update + completion
        # check there. So this branch only runs when the OS is NOT active
        # - i.e. the player hasn't pressed [E] yet, or the OS has been
        # deactivated after completion. We just show the prompt and start
        # the OS on [E].
        from ui import upload_os
        if not upload_os.is_upload_os_active():
            if not _near(UPLOAD_TERMINAL_POS, 110):
                _set_objective("Return to the upload terminal")
            else:
                _set_objective("Press [E] at the upload terminal")
                if keys[pygame.K_e]:
                    upload_os.start_upload_os()
                    STATE.mission2_upload_started = True
    elif stage == STAGE_EXFIL:
        _set_objective("Reach the green exfil marker")
        if _near(EXFIL_POS, 92):
            _complete_mission2()


# ─────────────────────────────────────────────
# Combat/update helpers
# ─────────────────────────────────────────────
def _update_player(keys, solid_walls):
    if not STATE.player or STATE.player_dead:
        return
    if STATE.mission2_stage == STAGE_INVESTIGATE:
        STATE.player.speed = 3.45
    elif STATE.mission2_stage == STAGE_RUN:
        STATE.player.speed = 4.45
    else:
        STATE.player.speed = 3.6

    mx, my = get_scaled_mouse()
    world_mx = mx + STATE.camera_x
    world_my = my + STATE.camera_y
    STATE.player.angle = math.atan2(world_my - STATE.player.rect.centery, world_mx - STATE.player.rect.centerx)

    dx = dy = 0
    if getattr(STATE, "mission2_input_freeze", 0) > 0:
        keys_for_move = {pygame.K_w: False, pygame.K_s: False, pygame.K_a: False, pygame.K_d: False}
    else:
        keys_for_move = _m2_world._last_keys
    if not _movement_locked():
        # Delta-time aware: speed is in px/frame, multiply by (60*dt).
        _dt_mul = 60.0 * STATE.dt
        if keys_for_move[pygame.K_w]:
            dy -= STATE.player.speed * _dt_mul
        if keys_for_move[pygame.K_s]:
            dy += STATE.player.speed * _dt_mul
        if keys_for_move[pygame.K_a]:
            dx -= STATE.player.speed * _dt_mul
        if keys_for_move[pygame.K_d]:
            dx += STATE.player.speed * _dt_mul
    if dx and dy:
        dx *= 0.707
        dy *= 0.707
    STATE.player.move(dx, dy, solid_walls)



def _update_weapon_timers():
    if STATE.shot_cooldown > 0:
        STATE.shot_cooldown -= 1
    if STATE.is_reloading:
        STATE.reload_timer -= 1
        if STATE.reload_timer <= 0:
            STATE.is_reloading = False
            is_os12 = getattr(STATE, "current_weapon", "pistol") == "os12"
            if is_os12:
                if STATE.os12_spare_mags > 0:
                    STATE.os12_spare_mags -= 1
                    STATE.os12_ammo_in_mag = STATE.os12_mag_size
            else:
                if STATE.spare_mags > 0:
                    STATE.spare_mags -= 1
                    STATE.ammo_in_mag = STATE.mag_size

    # OS 12 separate cooldown
    if getattr(STATE, "os12_shot_cooldown", 0) > 0:
        STATE.os12_shot_cooldown -= 1

    # ── Weapon swap animation tick ──
    if getattr(STATE, "weapon_swap_timer", 0) > 0:
        STATE.weapon_swap_timer -= 1
        duration = getattr(STATE, "weapon_swap_duration", 24)
        midpoint = duration // 2
        # At midpoint: flip the actual weapon and play the handling sound
        if (STATE.weapon_swap_timer <= midpoint
                and not getattr(STATE, "weapon_swap_sound_played", False)
                and getattr(STATE, "weapon_swap_pending", None) is not None):
            STATE.current_weapon = STATE.weapon_swap_pending
            vol = 0.4 if STATE.current_weapon == "os12" else 0.3
            audio.play("rifle_handle", volume=vol)
            STATE.weapon_swap_sound_played = True
        # On completion: clear pending
        if STATE.weapon_swap_timer <= 0:
            STATE.weapon_swap_pending = None
            STATE.weapon_swap_sound_played = False

    # ── Full-auto: OS 12 fires while mouse button is held ──
    if (not STATE.player_dead and STATE.player
            and not STATE.is_reloading
            and getattr(STATE, "weapon_swap_timer", 0) <= 0
            and getattr(STATE, "current_weapon", "pistol") == "os12"
            and getattr(STATE, "os12_unlocked", False)):
        if pygame.mouse.get_pressed()[0]:
            if getattr(STATE, "os12_shot_cooldown", 0) <= 0:
                handle_shoot()
    if STATE.melee_active:
        STATE.melee_timer -= 1
        if STATE.player and not STATE.melee_hit_done and STATE.melee_timer <= 10:
            # Shared melee resolver: range, cone, LOS, damage, particles,
            # shake are all defined in player.resolve_melee. M2 previously
            # had no cone check and no LOS check - you could hit enemies
            # behind you and through walls. Now consistent with M1.
            hit_enemy = resolve_melee(
                STATE.player, STATE.enemies, _solid_walls(), C_BLOOD,
            )
            if hit_enemy is not None:
                STATE.melee_hit_done = True
                STATE.shots_hit += 1
        if STATE.melee_timer <= 0:
            STATE.melee_active = False
            STATE.melee_hit_done = False


def _update_molotovs(solid_walls):
    # Bottle flight + ground fire now come from the shared Mission 1
    # implementation (entities.weapons.update_molotovs) so the molotov -
    # arc, embers, heat-scaled damage, alert/distraction logic - reads
    # identically in every mission. Mission 2 only suspends the player's
    # own burn damage during its authored locked beats (sniper / blackout /
    # mission cards); nothing else deviates.
    player_hit = update_molotovs(
        solid_walls, player_damage_allowed=not _movement_locked())

    # ── Car-burning hook ──
    # If a molotov fire overlaps a civilian car (not the IPA truck, not
    # already burned), start it burning. The burn progresses while any
    # molotov fire overlaps the car; once burn_progress reaches 1.0 the
    # car flips to "burned" permanently and stops accepting new fire.
    # This lets the player torch cars at will for fun/sabotage.
    if STATE.molotov_fires:
        for v in getattr(STATE, "mission2_vehicles", []):
            # IPA truck + tanker-blast-charred cars + already-burned cars
            # are immune to molotov burning.
            if v.get("kind") == "ipa_truck":
                continue
            if v.get("blast_charred", False):
                continue
            if v.get("kind") == "burned" and not v.get("burning", False):
                continue
            # If already fully burned, skip.
            if v.get("burn_progress", 0.0) >= 1.0:
                continue
            vcx = v["rect"].centerx
            vcy = v["rect"].centery
            # Check if any active molotov fire overlaps the car.
            overlapping = False
            for fire in STATE.molotov_fires:
                d = math.hypot(fire["x"] - vcx, fire["y"] - vcy)
                if d < MOLOTOV_RADIUS + 20:
                    overlapping = True
                    break
            if overlapping:
                v["burning"] = True
                # Burn progresses over ~6 seconds of sustained fire overlap.
                v["burn_progress"] = min(1.0, v.get("burn_progress", 0.0) + 1.0 / 360.0)
                # Once fully burned, flip the kind to "burned" so the
                # drawing code renders the permanent wreck variant.
                if v["burn_progress"] >= 1.0:
                    v["kind"] = "burned"
                    v["burning"] = False
                    v["molotov_burned"] = True  # distinguish from blast-charred
            # If not overlapping but was burning, the burn pauses (doesn't
            # reverse) - the car stays at its current burn level. Real fire
            # would keep going once lit, but for gameplay this is fine and
            # avoids cars torching themselves without sustained fire.

    # ── Burn-progress effects: smoke + flame particles ──
    # While a car is actively burning (burning=True, not yet fully
    # burned), emit flame + smoke particles from it so the player sees
    # the car catch fire and burn.
    for v in getattr(STATE, "mission2_vehicles", []):
        if not v.get("burning", False):
            continue
        if v.get("burn_progress", 0.0) >= 1.0:
            continue
        bp = v["burn_progress"]
        vcx = v["rect"].centerx
        vcy = v["rect"].centery
        # Flame particles - more as the burn progresses. Throttled.
        flame_rate = 1 + int(bp * 3)
        if STATE.mission2_timer % 2 == 0:
            for _ in range(flame_rate):
                col = _rng_legacy.choice([
                    (255, 180, 60), (255, 140, 40),
                    (255, 100, 30), (255, 220, 100),
                ])
                p = Particle(vcx + _rng_legacy.randint(-30, 30),
                             vcy + _rng_legacy.randint(-12, 12), col)
                p.dx = _rng_legacy.uniform(-0.6, 0.6)
                p.dy = _rng_legacy.uniform(-2.8, -1.2)
                p.life = _rng_legacy.randint(30, 70)
                STATE.particles.append(p)
        # Smoke particles - thicker as the burn progresses.
        if STATE.mission2_timer % 4 == 0:
            for _ in range(1 + int(bp * 2)):
                col = _rng_legacy.choice([(28, 24, 22), (45, 40, 35), (60, 52, 45)])
                p = Particle(vcx + _rng_legacy.randint(-35, 35),
                             vcy + _rng_legacy.randint(-16, 8), col)
                p.dx = _rng_legacy.uniform(-0.7, 0.7)
                p.dy = _rng_legacy.uniform(-3.0, -1.5)
                p.life = _rng_legacy.randint(120, 220)
                STATE.particles.append(p)

    # NOTE: the persistent fire-zone tick now happens inside the shared
    # update_molotovs() call above - do not duplicate it here.
    return player_hit


def _update_sniper_enemy(e, solid_walls):
    """Mission 2 sniper: fixed nest, long sightline, deliberate shots."""
    if not STATE.player or STATE.player_dead:
        return
    px, py = _player_pos()
    dx = px - e.rect.centerx
    dy = py - e.rect.centery
    e.angle = math.atan2(dy, dx)
    if e.fire_cooldown > 0:
        e.fire_cooldown -= 1
    if _wall_blocks_line(e.rect.centerx, e.rect.centery, px, py, solid_walls):
        return
    if e.fire_cooldown <= 0:
        dist = max(1.0, math.hypot(dx, dy))
        vx, vy = dx / dist, dy / dist
        STATE.bullets.append({
            "x": e.rect.centerx + vx * 22,
            "y": e.rect.centery + vy * 22,
            "prev_x": e.rect.centerx + vx * 22,
            "prev_y": e.rect.centery + vy * 22,
            "dx": vx * 28,
            "dy": vy * 28,
            "life": 34,
            "owner": "enemy",
            "damage": 26,
        })
        STATE.mission2_sniper_traces.append({"from": (e.rect.centerx, e.rect.centery), "to": (px, py), "life": 10})
        audio.play("gunshot_distant", volume=0.55)
        e.fire_cooldown = 115 + _rng_legacy.randint(0, 45)


def _update_bullets_enemies(solid_walls):
    player_hit = False
    for b in STATE.bullets[:]:
        b["prev_x"], b["prev_y"] = b["x"], b["y"]
        # Delta-time aware: dx/dy are in px/frame, multiply by (60*dt).
        _dt_mul = 60.0 * STATE.dt
        b["x"] += b["dx"] * _dt_mul
        b["y"] += b["dy"] * _dt_mul
        b["life"] -= 1
        # ── Entity hits checked BEFORE wall hits ──
        # Previously wall collision ran first, which meant a bullet that
        # reached the player's hitbox (22px radius) but was also inside a
        # cover rect (common when the player spawns behind sandbags or
        # leans against a wall) was absorbed as a "wall hit" and the
        # player took no damage. Now entity hits take priority - if a
        # bullet reaches an entity, it hits that entity, not the cover.
        hit = False
        # ── Player bullets vs enemies ──
        if not hit and b.get("owner") == "player":
            for e in STATE.enemies:
                if math.hypot(b["x"] - e.rect.centerx, b["y"] - e.rect.centery) < 22:

                    # You cannot pistol-snipe the sniper from the open road.
                    # If your bullet can reach him, he has already seen you.
                    if _m2g(e).sniper and not getattr(STATE, "mission2_sniper_suppressed", False):
                        hit = True

                        STATE.mission2_sniper_pressure_timer = 0
                        STATE.mission2_sniper_pending_timer = min(
                            getattr(STATE, "mission2_sniper_pending_timer", 999),
                            SNIPER_CLOSE_AIM_FRAMES,
                        )
                        STATE.mission2_sniper_target = _player_pos()
                        _add_sniper_laser(STATE.mission2_sniper_target, life=20)

                        STATE.floating_texts.append([
                            STATE.player.rect.centerx,
                            STATE.player.rect.centery - 52,
                            "SNIPER HAS YOUR ANGLE",
                            (255, 60, 40),
                            70,
                        ])

                        _burst(b["x"], b["y"], (140, 135, 120), 10, speed_mul=1.4)
                        audio.play("concrete_impact", volume=0.45)
                        break

                    e.hp -= b.get("damage", 50)
                    e.on_hit(STATE.player.rect.centerx, STATE.player.rect.centery)
                    hit = True
                    STATE.shots_hit += 1
                    STATE.blood_decals.append([b["x"], b["y"], 140, _rng_legacy.randint(8, 16)])
                    _burst(b["x"], b["y"], C_BLOOD, 14)
                    # Spatial audio for enemy-hit (was flat audio.play(...,0.42)).
                    effects.play_impact(
                        "bullet_impact_enemy", (b["x"], b["y"]), base_volume=0.42,
                    )
                    break
        if not hit and b.get("owner") == "enemy" and STATE.player and not STATE.player_dead:
            if math.hypot(b["x"] - STATE.player.rect.centerx, b["y"] - STATE.player.rect.centery) < 22:
                # AEGIS Pass E: route through take_damage() so i-frames apply.
                # The mission2_grace_timer (post-sniper narrative protection)
                # is preserved as the outer gate - if a grace window is
                # active, neither damage nor i-frame logic runs. Inside the
                # grace-expired path, take_damage() adds tactical i-frames
                # on top, so the player can't be chain-melted by overlapping
                # enemy fire. If i-frames absorb the hit, player_hit stays
                # False (no damage feedback for an absorbed hit).
                if getattr(STATE, "mission2_grace_timer", 0) <= 0:
                    if STATE.player.take_damage(b.get("damage", ENEMY_DAMAGE)):
                        player_hit = True
                hit = True
                # Shared max-clamp shake trigger (was max(...) inline; now via
                # effects.shake for consistency with the rest of the campaign).
                effects.shake(6)
                _burst(b["x"], b["y"], C_BLOOD, 8)
                audio.play("bullet_impact_enemy", volume=0.5)
        # ── Wall hits checked LAST (only if no entity was hit) ──
        # This is the fix for "player not taking damage": previously the wall
        # check ran first and absorbed any bullet that was inside a cover rect,
        # even if the bullet had reached the player's hitbox. Now entity hits
        # take priority; wall hits only happen for bullets that missed everyone.
        if not hit:
            hit = collide_bullet_walls(b, solid_walls)
            if hit:
                _burst(b["x"], b["y"], (130, 125, 110), 4)
                effects.play_impact("bullet_impact", (b["x"], b["y"]), base_volume=0.30)
        if hit or b["life"] <= 0 or not (-500 < b["x"] < MAP_W * TILE_SIZE + 500 and -500 < b["y"] < MAP_H * TILE_SIZE + 500):
            if b in STATE.bullets:
                STATE.bullets.remove(b)

    for e in STATE.enemies[:]:
        if STATE.player and not STATE.player_dead:
            e.alerted = True
            if _m2g(e).sniper:
                # Mission 2's post-ambush sniper is handled by the authored
                # kill-box pressure system, not generic enemy fire. Keep the
                # actor facing the player for drawing/feedback.
                px, py = _player_pos()
                e.angle = math.atan2(py - e.rect.centery, px - e.rect.centerx)
            else:
                if e.state in ("IDLE", "PATROL", "SEARCH"):
                    e.state = "CHASE"
                e.last_seen_pos = _player_pos()
                e.update(STATE.player.rect.centerx, STATE.player.rect.centery, solid_walls, STATE.bullets, STATE.particles, STATE.enemies, STATE.fire_zones)
        if e.hp <= 0:
            STATE.hostiles_killed += 1
            STATE.blood_decals.append([e.rect.centerx, e.rect.centery, 165, _rng_legacy.randint(12, 22)])
            _burst(e.rect.centerx, e.rect.centery, C_BLOOD, 24)
            # Body topples, bleeds out, and fades instead of vanishing
            # on the death frame (entities/corpse.py).
            corpse.spawn_corpse(e)
            roll = _rng_legacy.random()
            if roll < 0.28:
                STATE.pickups.append([e.rect.centerx, e.rect.centery, "bandage"])
            elif roll < 0.56 and STATE.spare_mags < 5:
                STATE.pickups.append([e.rect.centerx, e.rect.centery, "mag"])
            STATE.enemies.remove(e)
    return player_hit


def _update_pickups():
    if not STATE.player or STATE.player_dead:
        return
    for pu in STATE.pickups[:]:
        if math.hypot(pu[0] - STATE.player.rect.centerx, pu[1] - STATE.player.rect.centery) > 32:
            continue
        kind = pu[2]
        if kind == "bandage":
            old = STATE.player.hp
            STATE.player.hp = min(STATE.player.max_hp, STATE.player.hp + 35)
            STATE.floating_texts.append([pu[0], pu[1] - 16, f"+{int(STATE.player.hp - old)} HP", (100, 220, 100), 70])
        elif kind == "mag":
            STATE.spare_mags = min(5, STATE.spare_mags + 1)
            STATE.floating_texts.append([pu[0], pu[1] - 16, "+1 MAG", C_TERMINAL, 70])
        audio.play("pickup", volume=0.45)
        STATE.pickups.remove(pu)


def _update_particles_texts(solid_walls):
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
    for tr in STATE.mission2_sniper_traces[:]:
        tr["life"] -= 1
        if tr["life"] <= 0:
            STATE.mission2_sniper_traces.remove(tr)
    for laser in getattr(STATE, "mission2_sniper_lasers", [])[:]:
        laser["life"] -= 1
        if laser["life"] <= 0:
            STATE.mission2_sniper_lasers.remove(laser)
    for flash in getattr(STATE, "mission2_sniper_muzzle_flashes", [])[:]:
        flash["life"] -= 1
        if flash["life"] <= 0:
            STATE.mission2_sniper_muzzle_flashes.remove(flash)
    if getattr(STATE, "mission2_tinnitus_timer", 0) > 0:
        STATE.mission2_tinnitus_timer -= 1

    # --- Tanker explosion ongoing effects ---
    # ─────────────────────────────────────────────────────────────────
    # POST-BLAST AFTERMATH - runs for the rest of the mission whenever
    # the tanker has exploded, regardless of stage. Previously this whole
    # block was gated on STAGE_BLACKOUT, which meant the moment the player
    # closed the "COMMS LOST" card and transitioned to STAGE_EVIDENCE,
    # ALL ambient smoke/embers stopped instantly AND any in-flight debris
    # chunks froze in mid-air. That's why the aftermath felt underwhelming
    # - the blast site went from "roaring inferno" to "slightly scorched
    # ground with campfires" in a single frame.
    # ─────────────────────────────────────────────────────────────────
    if getattr(STATE, "mission2_tanker_exploded", False):
        STATE.mission2_tanker_blast_timer = getattr(STATE, "mission2_tanker_blast_timer", 0) + 1
        bt = STATE.mission2_tanker_blast_timer

        # --- Heavy debris chunk physics. Runs every frame so in-flight
        # chunks keep moving and landed chunks keep bouncing until their
        # life expires, even after the stage transitions away from
        # STAGE_BLACKOUT. ---
        new_chunks = []
        for chunk in getattr(STATE, "mission2_tanker_debris_chunks", []):
            chunk["x"] += chunk["dx"]
            chunk["y"] += chunk["dy"]
            chunk["dy"] += 0.25   # slightly heavier gravity for bigger chunks
            chunk["dx"] *= 0.995
            chunk["age"] += 1
            chunk["life"] -= 1
            if chunk["y"] > chunk["ground_y"] and chunk["dy"] > 0:
                chunk["y"] = chunk["ground_y"]
                chunk["dy"] *= -0.3
                chunk["dx"] *= 0.55
                # Bigger dust puff for bigger chunks.
                if abs(chunk["dy"]) > 1.0:
                    for _ in range(6):
                        p = Particle(int(chunk["x"]) + _rng_legacy.randint(-8, 8),
                                     int(chunk["y"]) + _rng_legacy.randint(-3, 3),
                                     (90, 80, 70))
                        p.dx = _rng_legacy.uniform(-1.5, 1.5)
                        p.dy = _rng_legacy.uniform(-2.2, -0.3)
                        p.life = _rng_legacy.randint(20, 40)
                        STATE.particles.append(p)
            if chunk["life"] > 0:
                new_chunks.append(chunk)
        STATE.mission2_tanker_debris_chunks = new_chunks

        # --- Persistent aftermath smoke + embers. Runs FOREVER (for the
        # rest of the mission) so the blast site keeps visibly smoldering
        # during STAGE_EVIDENCE / STAGE_UPLOAD / STAGE_EXFIL. During
        # STAGE_BLACKOUT the heavier emitters below dominate; this block
        # carries the aftermath once those fade out. Rate is throttled
        # (every 6th frame for smoke, every 8th frame for embers) so it
        # stays cheap but never goes silent. ---
        if not STATE.mission2_stage == STAGE_BLACKOUT or bt >= 600:
            tanker = STATE.mission2_tanker_rect
            cx_sm, cy_sm = tanker.centerx, tanker.centery
            # Smoke - 2-3 particles every 6 frames, drifting up and out.
            if bt % 6 == 0:
                for _ in range(3):
                    col = _rng_legacy.choice([(25, 22, 20), (40, 35, 32), (55, 48, 42)])
                    p = Particle(cx_sm + _rng_legacy.randint(-45, 45),
                                 cy_sm + _rng_legacy.randint(-25, 5), col)
                    p.dx = _rng_legacy.uniform(-0.8, 0.8)
                    p.dy = _rng_legacy.uniform(-2.8, -1.2)
                    p.life = _rng_legacy.randint(200, 320)
                    STATE.particles.append(p)
            # Embers - 1-2 particles every 8 frames, glowing orange/red.
            if bt % 8 == 0:
                for _ in range(2):
                    col = _rng_legacy.choice([
                        (255, 180, 60), (255, 140, 40), (255, 100, 30), (255, 80, 25),
                    ])
                    p = Particle(cx_sm + _rng_legacy.randint(-90, 90),
                                 cy_sm + _rng_legacy.randint(-30, 50), col)
                    p.dx = _rng_legacy.uniform(-0.5, 0.5)
                    p.dy = _rng_legacy.uniform(-3.2, -1.2)
                    p.life = _rng_legacy.randint(50, 110)
                    STATE.particles.append(p)

        # --- Outer spot fires - emit fire + smoke particles from each
        # persistent spot fire (embers that landed 250-600px out and
        # ignited secondary blazes). Throttled so 12 fires stay cheap.
        # Runs forever so the wider scene keeps burning. ---
        spot_fires = getattr(STATE, "mission2_tanker_spot_fires", [])
        if spot_fires and bt % 5 == 0:
            for sf in spot_fires:
                # Fire particles - orange/red, rising.
                col = _rng_legacy.choice([
                    (255, 160, 50), (255, 120, 35), (255, 90, 25), (255, 200, 80),
                ])
                p = Particle(sf["x"] + _rng_legacy.randint(-6, 6),
                             sf["y"] + _rng_legacy.randint(-4, 4), col)
                p.dx = _rng_legacy.uniform(-0.4, 0.4)
                p.dy = _rng_legacy.uniform(-2.2, -1.0)
                p.life = _rng_legacy.randint(25, 55)
                STATE.particles.append(p)
                # Occasional smoke wisp from each spot fire.
                if bt % 15 == 0:
                    sp = Particle(sf["x"] + _rng_legacy.randint(-8, 8),
                                  sf["y"] + _rng_legacy.randint(-6, 2),
                                  _rng_legacy.choice([(30, 27, 24), (45, 40, 35)]))
                    sp.dx = _rng_legacy.uniform(-0.5, 0.5)
                    sp.dy = _rng_legacy.uniform(-1.8, -0.8)
                    sp.life = _rng_legacy.randint(90, 160)
                    STATE.particles.append(sp)

    # ─────────────────────────────────────────────────────────────────
    # ACTIVE BLAST - heavy one-shot effects that only make sense during
    # the cinematic STAGE_BLACKOUT window: screen shake, shockwave ring
    # growth, fireball growth, BLEVE subflashes, the initial 600-frame
    # heavy smoke plume, and the big ember rise. Once the player closes
    # the "COMMS LOST" card and the stage transitions to EVIDENCE, this
    # block stops running and only the persistent aftermath above remains.
    # ─────────────────────────────────────────────────────────────────
    if getattr(STATE, "mission2_tanker_exploded", False) and STATE.mission2_stage == STAGE_BLACKOUT:
        bt = getattr(STATE, "mission2_tanker_blast_timer", 0)

        # Screen shake decay - 160 peak over 240 frames.
        if getattr(STATE, "mission2_tanker_shake_decay", 0) > 0:
            decay_remaining = STATE.mission2_tanker_shake_decay
            shake_val = int(160 * (decay_remaining / 240.0))
            STATE.screen_shake = max(STATE.screen_shake, shake_val)
            STATE.mission2_tanker_shake_decay -= 1

        # Screen ripple timer - drives the horizontal wobble distortion
        # drawn in _draw_blackout_overlay. Decays over 40 frames.
        if getattr(STATE, "mission2_tanker_ripple_timer", 0) > 0:
            STATE.mission2_tanker_ripple_timer -= 1

        # Shockwave ring: 1600px max radius over 50 frames (was 1100/40).
        # This actually fills the screen and beyond.
        if bt <= 50:
            STATE.mission2_tanker_shockwave_radius = int(bt * 32.0)  # 1600px max

        # Fireball core radius: 700px max over 45 frames (was 280/35).
        # This is the screen-dominating white-hot sphere.
        if bt <= 45:
            STATE.mission2_tanker_fireball_radius = int(bt * 15.5)  # ~700px max

        # Secondary debris wave + heavy chunks (90 chunks, was 34).
        pending_debris = getattr(STATE, "mission2_pending_debris_wave", 0)
        if pending_debris > 0:
            STATE.mission2_pending_debris_wave = pending_debris - 1
            if pending_debris == 1:
                tanker = STATE.mission2_tanker_rect
                cx, cy = tanker.centerx, tanker.centery
                # Lightweight spray (350 particles, matches _spawn_debris).
                for _ in range(350):
                    col = _rng_legacy.choice([
                        (60, 55, 50), (40, 35, 30), (95, 88, 76),
                        (140, 40, 32), (75, 30, 25),
                    ])
                    p = Particle(cx + _rng_legacy.randint(-70, 70), cy + _rng_legacy.randint(-40, 40), col)
                    angle = _rng_legacy.uniform(0, math.tau)
                    speed = _rng_legacy.uniform(2.0, 5.5)
                    p.dx = math.cos(angle) * speed
                    p.dy = math.sin(angle) * speed
                    p.life = _rng_legacy.randint(60, 160)
                    STATE.particles.append(p)
                # Heavy debris chunks - 90 of them, with bigger sizes.
                for _ in range(90):
                    angle = _rng_legacy.uniform(-math.pi, 0.0)  # bias upward
                    speed = _rng_legacy.uniform(5.0, 11.0)
                    chunk = {
                        "x": cx + _rng_legacy.randint(-40, 40),
                        "y": cy + _rng_legacy.randint(-30, 10),
                        "dx": math.cos(angle) * speed,
                        "dy": math.sin(angle) * speed,
                        "size": _rng_legacy.randint(5, 12),  # bigger chunks
                        "color": _rng_legacy.choice([
                            (60, 55, 50), (40, 35, 30), (95, 88, 76),
                            (140, 40, 32), (75, 30, 25),
                        ]),
                        "age": 0,
                        "life": _rng_legacy.randint(100, 200),
                        "ground_y": cy + _rng_legacy.randint(20, 60),
                    }
                    STATE.mission2_tanker_debris_chunks.append(chunk)

        # Subflash triggers - 5 BLEVE secondaries at t=15, 30, 50, 75, 105.
        subflash_q = getattr(STATE, "mission2_tanker_subflash_queue", [])
        if subflash_q and bt >= subflash_q[0]:
            subflash_q.pop(0)
            STATE.gc_flash_timer = max(getattr(STATE, "gc_flash_timer", 0), 30)
            STATE.screen_shake = max(getattr(STATE, "screen_shake", 0), 75)
            STATE.cam_kick_x += _rng_legacy.uniform(-1.0, 1.0) * 20.0
            STATE.cam_kick_y += _rng_legacy.uniform(-1.0, 1.0) * 20.0
            STATE.mission2_chromatic_timer = max(getattr(STATE, "mission2_chromatic_timer", 0), 80)
            STATE.mission2_tanker_ripple_timer = max(getattr(STATE, "mission2_tanker_ripple_timer", 0), 12)
            # Fresh ember burst - bigger on each secondary.
            tanker = STATE.mission2_tanker_rect
            cx2, cy2 = tanker.centerx, tanker.centery
            for _ in range(100):
                col = _rng_legacy.choice([
                    (255, 255, 230), (255, 220, 140), (255, 160, 50), (255, 95, 20),
                ])
                p = Particle(cx2 + _rng_legacy.randint(-60, 60), cy2 + _rng_legacy.randint(-40, 20), col)
                angle = _rng_legacy.uniform(0, math.tau)
                speed = _rng_legacy.uniform(3.0, 7.5)
                p.dx = math.cos(angle) * speed
                p.dy = math.sin(angle) * speed
                p.life = _rng_legacy.randint(30, 80)
                STATE.particles.append(p)

        # Continuous heavy smoke plume - emit for 600 frames (10s) during
        # the blackout. After bt >= 600 OR after the stage transitions,
        # the persistent-aftermath block above takes over at a lower rate.
        if bt < 600 and bt % 2 == 0:
            tanker = STATE.mission2_tanker_rect
            cx, cy = tanker.centerx, tanker.centery
            for _ in range(7):
                col = _rng_legacy.choice([(15, 13, 12), (22, 20, 18), (35, 30, 28), (55, 48, 42)])
                p = Particle(cx + _rng_legacy.randint(-60, 60), cy + _rng_legacy.randint(-40, 10), col)
                p.dx = _rng_legacy.uniform(-1.2, 1.2)
                p.dy = _rng_legacy.uniform(-3.5, -1.5)
                p.life = _rng_legacy.randint(180, 320)
                STATE.particles.append(p)

        # Big ember rise during the active burn - denser and wider than
        # the persistent aftermath emitters.
        if bt > 20 and bt % 2 == 0:
            tanker = STATE.mission2_tanker_rect
            cx, cy = tanker.centerx, tanker.centery
            for _ in range(5):
                col = _rng_legacy.choice([(255, 200, 80), (255, 180, 60), (255, 120, 40), (255, 90, 30)])
                p = Particle(cx + _rng_legacy.randint(-150, 150), cy + _rng_legacy.randint(-40, 70), col)
                p.dx = _rng_legacy.uniform(-0.6, 0.6)
                p.dy = _rng_legacy.uniform(-4.0, -1.5)
                p.life = _rng_legacy.randint(60, 120)
                STATE.particles.append(p)
    if getattr(STATE, "mission2_sniper_kill_flash", 0) > 0:
        STATE.mission2_sniper_kill_flash -= 1
    props_changed = False
    for prop in getattr(STATE, "mission2_story_props", [])[:]:
        prop["age"] = prop.get("age", 0) + 1
        if prop.get("life", -1) > 0:
            prop["life"] -= 1
            if prop["life"] <= 0:
                STATE.mission2_story_props.remove(prop)
                props_changed = True
    if props_changed:
        _sync_story_prop_collisions()
    if getattr(STATE, "mission2_sniper_flash", 0) > 0:
        STATE.mission2_sniper_flash -= 1
    if getattr(STATE, "mission2_near_miss_flash", 0) > 0:
        STATE.mission2_near_miss_flash -= 1

    callout = getattr(STATE, "mission2_death_callout", None)
    if callout:
        callout["life"] -= 1
        if callout["life"] <= 0:
            STATE.mission2_death_callout = None


def _update_camera():
    # M2-specific target selection: cutscene focus overrides player; cutscene
    # snap overrides both. Then delegate the actual shake / kick / lerp /
    # clamp / jitter to the shared camera.update_camera so M1 and M2 can't
    # drift on those axes again.
    target = STATE.mission2_camera_focus or _player_pos()
    if getattr(STATE, "mission2_camera_snap", None):
        target = STATE.mission2_camera_snap
        STATE.mission2_camera_snap = None

    # M2 used to keep its own first-frame-snap flag (mission2_camera_initialized).
    # The shared camera uses STATE.camera_initialized instead. Migrate the flag
    # so the snap still fires on the first frame after start_mission2.
    if getattr(STATE, "mission2_camera_initialized", False):
        STATE.camera_initialized = True
        STATE.mission2_camera_initialized = False  # one-shot migration

    # Per-stage lerp strategy:
    #   - Sniper stage: distance-scaled smoothstep (slow start, slow end, fast middle).
    #     Preserved from the original M2 implementation - this is the
    #     carefully-tuned "tense camera" feel for the Route 12 ambush.
    #   - Cutscene focus pull: CAM_EASE_FOCUS (snappy).
    #   - Default gameplay: CAM_EASE_M2 (slightly slower than M1's ease
    #     to preserve M2's deliberately weightier feel), plus aim lookahead
    #     and a follow deadzone. Focus pulls and sniper anchors need exact
    #     arrival on composed shots, so they skip deadzone/lookahead.
    stage = getattr(STATE, "mission2_stage", "")
    in_sniper = stage == STAGE_SNIPER
    focus_active = getattr(STATE, "mission2_camera_focus_timer", 0) > 0

    deadzone = 0.0
    lookahead = None
    if in_sniper:
        def _smoothstep_factor(dx, dy, dist):
            f = min(1.0, 0.08 * (1.0 + dist / 600.0))
            return f * f * (3.0 - 2.0 * f)
        factor_fn = _smoothstep_factor
        focus_factor = None
    elif focus_active:
        factor_fn = None
        focus_factor = CAM_EASE_FOCUS
    else:
        factor_fn = None
        focus_factor = CAM_EASE_M2
        deadzone = CAM_DEADZONE_PX
        if STATE.player and not STATE.player_dead:
            _a = STATE.player.angle
            lookahead = (math.cos(_a) * CAM_LOOKAHEAD_PX,
                         math.sin(_a) * CAM_LOOKAHEAD_PX)

    handheld = (getattr(STATE, "mission2_sniper_phase_timer", 0)
                if in_sniper else None)

    # Shared follow helper; M2's sniper smoothstep / handheld sway and focus
    # pulls are explicit overrides, not a forked camera.
    from core.camera import follow_gameplay, CAM_EASE_GAMEPLAY
    return follow_gameplay(
        target, MAP_W, MAP_H,
        ease=CAM_EASE_GAMEPLAY if focus_factor is None else focus_factor,
        deadzone_px=deadzone,
        lookahead=lookahead if lookahead is not None else (0.0, 0.0),
        factor_fn=factor_fn,
        handheld_jitter_timer=handheld,
        who="m2",
    )


def game_update(keys):
    from missions.m2.draw import _update_evidence_cinematic, _update_flank_cutscene  # lazy: breaks update<->draw cycle
    _m2_world._last_keys = keys
    # AEGIS Pass E: advance player i-frame timer + sprite blink every frame.
    # Must run BEFORE the death-trigger check below so the timer ticks down
    # even on the frame the player dies (otherwise a freshly-set i-frame
    # window would freeze the blink state on the death frame).
    if STATE.player:
        STATE.player.update_iframes(STATE.dt)
    if STATE.gc_flash_timer > 0:
        STATE.gc_flash_timer -= 1
    # Corpses animate on every frame - including cinematic/death-anim
    # early-return paths below (they tick with slow-mo via the logic ticks).
    corpse.update_corpses()
    if STATE.player and STATE.player.hp <= 0 and not STATE.player_dead:
        # Death animation (Option B - Standard) handles the full sequence:
        # slow-mo, camera collapse, ragdoll, blood pool, tinnitus, radio cut.
        # Replaces the legacy single-burst + shake trigger.
        from entities import death_anim
        death_anim.trigger_death()
    if STATE.player_dead:
        from entities import death_anim
        ticks = death_anim.update_death_anim()
        STATE._death_logic_ticks = ticks
    else:
        STATE._death_logic_ticks = 1

    # ── Grace timer countdown ──
    # This was previously inside _update_sniper_pressure(), which only runs
    # during STAGE_COMBAT with the sniper alive. Once the player advanced
    # past the sniper (STAGE_EVIDENCE, STAGE_TRUCK, etc.), the grace timer
    # never counted down - it stayed at 90 forever, blocking ALL enemy bullet
    # damage during the cleanup team fight. Moving it here ensures it ticks
    # down regardless of stage. The timer is only SET during the sniper phase.
    if getattr(STATE, "mission2_grace_timer", 0) > 0:
        STATE.mission2_grace_timer -= 1

    # ── Evidence completion cinematic (Option E) ──
    # When active, this takes priority over normal gameplay updates -
    # the player is watching a cinematic, not fighting. We still update
    # particles + camera so the scene looks alive, but we skip enemy AI,
    # bullets, etc.
    if getattr(STATE, "mission2_evidence_cinematic_active", False):
        _update_evidence_cinematic()
        # Update particles + floating texts so the scene doesn't freeze.
        solid_walls = _solid_walls()
        effects.update_particles()
        effects.update_floating_texts()
        # Run the real camera (not the raw follow position): the upload_punch
        # shot sets a focus target + shake, and those only take effect
        # through _update_camera().
        return _update_camera()

    # Post-cinematic grace period - enemies stay frozen for 0.5s after the
    # cinematic ends so the player can orient before combat resumes.
    if getattr(STATE, "mission2_evidence_cinematic_grace", 0) > 0:
        STATE.mission2_evidence_cinematic_grace -= 1
        # Still update player movement + camera, but skip enemy AI + bullets.
        solid_walls = _solid_walls()
        _update_player(keys, solid_walls)
        effects.update_particles()
        effects.update_floating_texts()
        # The focus timer ticks here too so the terminal hold set by the
        # upload_punch shot releases on time once gameplay resumes.
        if getattr(STATE, "mission2_camera_focus_timer", 0) > 0:
            STATE.mission2_camera_focus_timer -= 1
            if STATE.mission2_camera_focus_timer == 0:
                STATE.mission2_camera_focus = None
        return _update_camera()

    # ── Upload OS (Option: Acarizwork upload) ──
    # When the upload OS is active, freeze enemies + skip gameplay updates.
    # The OS handles its own input via handle_upload_os_event (called from
    # acaristan.py's event loop). Here we update the OS frame state (boot
    # reveal, upload progress, done timer) and check for completion.
    #
    # CRITICAL: This MUST be done here, NOT in _update_stage(). When the OS
    # is active, this branch returns early - _update_stage() is never called.
    # Previously the update_upload_os() call lived in _update_stage()'s
    # STAGE_UPLOAD branch, which was unreachable when the OS was active.
    # That left _os_timer stuck at 0: boot lines never revealed, upload
    # progress never filled, done timer never advanced. The player saw a
    # frozen black screen with scanlines.
    from ui import upload_os
    if upload_os.is_upload_os_active():
        mouse_pos = pygame.mouse.get_pos()
        upload_os.update_upload_os(keys, mouse_pos)
        # ── Vasile radio warning at ~50% upload progress ──
        # Fires once, when the upload crosses 50%. Uses _vasile_warning_played
        # flag (reset in start_upload_os) to ensure it only plays once.
        if (not upload_os._vasile_warning_played
                and upload_os._upload_progress >= 0.5
                and upload_os._os_phase == upload_os.PHASE_UPLOAD
                and not upload_os._upload_intrusion_active):
            upload_os._vasile_warning_played = True
            _radio('VASILE: "Hurry. They\'re triangulating."',
                   color=(255, 150, 80), mark="upload_warning",
                   allow_when_cut=True)
            audio.play("radio_static", volume=0.3)
        # Check if the upload completed - if so, deactivate the OS and
        # open the "TRANSMISSION SENT" card. The card's `after="upload_done"`
        # handler transitions to STAGE_EXFIL when closed.
        if upload_os.is_upload_complete():
            upload_os.deactivate_upload_os()  # plays CRT thunk + restores cursor
            _open_card(
                "TRANSMISSION SENT",
                [
                    "The Route 12 evidence package is out.",
                    "IPA corrupted part of the archive, but enough survived.",
                    "Move to extraction before the state broadcast lands.",
                ],
                color=C_TERMINAL,
                after="upload_done",
                kind="terminal",
            )
        effects.update_particles()
        effects.update_floating_texts()
        # Frozen fullscreen OS: don't move the follow camera, but still decay
        # shake/kick so leftovers don't fire late when the OS closes.
        return tick_camera_fx(MAP_W, MAP_H)

    solid_walls = _solid_walls()
    _update_player(keys, solid_walls)
    _update_travel_triggers()
    _update_squad_ambient()
    _update_weapon_timers()
    player_hit = _update_molotovs(solid_walls)
    if STATE.mission2_stage not in (STAGE_SNIPER, STAGE_BLACKOUT, STAGE_DONE) and not getattr(STATE, "mission2_card", None):
        player_hit = _update_bullets_enemies(solid_walls) or player_hit
    if player_hit:
        STATE.screen_shake = max(STATE.screen_shake, 4)
    _update_pickups()
    _update_stage(keys)
    _update_particles_texts(solid_walls)

    _update_flank_cutscene()
    if getattr(STATE, "mission2_chromatic_timer", 0) > 0:
        STATE.mission2_chromatic_timer -= 1
    if getattr(STATE, "mission2_sniper_silhouette_flash", 0) > 0:
        STATE.mission2_sniper_silhouette_flash -= 1
    if getattr(STATE, "mission2_radio_muffle_timer", 0) > 0:
        STATE.mission2_radio_muffle_timer -= 1
    if getattr(STATE, "mission2_input_freeze", 0) > 0:
        STATE.mission2_input_freeze -= 1
    # Camera focus timer ticks down here so the heavy ease (0.38) returns
    # to default (0.14) once the focus event has passed. Previously the
    # timer was only set, never decremented, leaving the camera in
    # high-ease mode for the entire post-cutscene gameplay.
    if getattr(STATE, "mission2_camera_focus_timer", 0) > 0:
        STATE.mission2_camera_focus_timer -= 1
        # Safety net: when the timer expires, also clear the focus target
        # itself. _update_camera uses `target = mission2_camera_focus or
        # _player_pos()`, so an uncleared focus keeps the camera pinned
        # even after the timer hits 0. This is the root cause of the
        # "camera locks on the tanker after the blast" bug - the focus
        # was set in _explode_tanker but only the timer was decremented,
        # never the focus itself. The per-card close handlers (e.g.
        # blast_done) also clear this, but this catches any focus set
        # via _focus_camera_for_frames / inline that doesn't have a
        # matching close handler.
        if STATE.mission2_camera_focus_timer == 0:
            STATE.mission2_camera_focus = None

    if getattr(STATE, "mission2_heartbeat_active", False):
        STATE.mission2_heartbeat_timer += 1
        if STATE.mission2_heartbeat_timer % 72 == 0:
            audio.play("heartbeat", volume=0.18)
        # Point 12: Fade heartbeat as player takes first action (moves, shoots, etc.)
        # Also hard cap at ~12 seconds (720 frames)
        player_acting = False
        if STATE.player and not STATE.player_dead:
            keys = _m2_world._last_keys
            if keys and (keys[pygame.K_w] or keys[pygame.K_s] or keys[pygame.K_a] or keys[pygame.K_d] or keys[pygame.K_e] or keys[pygame.K_SPACE] or keys[pygame.K_r] or keys[pygame.K_g] or keys[pygame.K_v]):
                player_acting = True
        if (STATE.mission2_stage == STAGE_COMBAT and (STATE.mission2_heartbeat_timer > 720 or player_acting)):
            STATE.mission2_heartbeat_active = False

    return _update_camera()


# ─────────────────────────────────────────────
# Drawing helpers
# ─────────────────────────────────────────────
# Mission 2 clue/prop draw tuning.  The same _draw_prop_icon() artwork is used
# both on the ground and inside the inspection cards; only the presentation shell
# changes.  Keep world props small, then use halos/markers for readability.
