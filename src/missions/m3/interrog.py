"""Split from mission3.py - see mission3.py (shim) for the map."""
"""Mission 3: The Vostral - dialogue-driven cold open into action.

This is the third campaign mission, picking up 3 days after Mission 2's
Route 12 frame-up. Biribel wakes in an IPA black-site cell (the
"Stabilization Center") facing Prime Minister Balaceanu's long-promised
vendetta. The mission's spine is the Vostral - the buried rumor that
Balaceanu's decorated military career is fabricated. The only copy of
the service record that can prove it is held in the regime's own
Archives, so the engine of the mission is: break out of the cell, reach
the Archives, steal the file, and get it onto a live state broadcast
before Balaceanu finishes his 22:00 address pinning Route 12 on Biribel
personally.

Story posture (per the project bible): KRAP is STILL an organization -
disavowed, under siege, fighting for its survival and credibility. So
this is not Vasile-as-lone-wolf feeding floor plans out of guilt; KRAP
mobilizes as a resistance. Vasile brings real assets (an off-book
extraction element, a stolen IPA comms relay). The trust tension is
organizational, not personal.

This module keeps the existing game integration intact:
    - game_core.start_mission3()
    - game_core.game_update()/game_draw() routing (MISSION3 is checked
      BEFORE MISSION2 - see game_core.game_update)
    - acaristan.py Mission 3 intro and ending cutscenes (shot-lists
      exposed as module-level names below)
    - save as MISSION_3
    - dev command: python acaristan.py --dev-mission3

Scaffolding note: acaristan.py already routes ALL Mission 3 input
through mission3.handle_event(event) (arrow keys to pick choices,
ENTER to confirm) - this was purpose-built for the dialogue-driven
interrogation cold open that is Phase 1. Action phases (STAGE_BREAKOUT
onward) later relax that gate in acaristan.py so normal mouse-shoot
input falls through.
"""

import math
from engine.core import LEGACY_RNG as _rng_legacy  # RPE6 R6: named 'legacy' rng stream
import time

import pygame

from core.config import (C_VASILE, Particle, TILE_SIZE)
from entities.art_cache import get_blood_decal, get_fullscreen_overlay, get_panel_bg
from core.state import STATE
from entities.player import Player, resolve_melee
from entities.enemy_ai import Enemy, enemy_hear_shot, _astar
from ui.hud import MiniMap, draw_objective_panel, draw_pinned_radio
from missions.m1 import _draw_molotov_icon
from fx import effects
import cutscenes
from core.camera import update_camera, reset_camera_state, draw_bullets, collide_bullet_walls
from core.camera import CAM_EASE_GAMEPLAY, CAM_EASE_M3_BREACH_TRACK, follow_gameplay
from entities.weapons import _wall_blocks_line
from core import config as _config
audio = _config.audio

from missions.m3 import flow as _m3_flow  # dialogue/monitor/volkov-breach state owner
from missions.m3.meta import C_BALACEANU, C_SYSTEM, C_VOLKOV, MAP_W, MAP_H, STAGE_BREAKOUT, STAGE_INTERROGATION, STAGE_KILL_ORDER, STAGE_KO_TRANSITION, _DOOR_TILE_COL, _DOOR_TILE_ROW, _POST_TYPE_HOLD_MIN, _POST_TYPE_HOLD_MAX, _POST_TYPE_HOLD_PER_CHAR
from missions.m3.world import _player_pos, _radio, _set_objective, _start_m3_alarm, _volkov_world_pos
import game.world as _gw  # RPE6 Phase 5 (D4): mission data lives in components
from missions.m3.components import M3Door as _M3Door


def _m3d(door):
    """Declared M3 data of a door (replaces the ad hoc ``door.m3_*`` attributes)."""
    return _gw.ensure(door, _M3Door)


def _post_type_hold_frames(beat):
    """Length-scaled hold (in frames) for the given beat's text.

    See _POST_TYPE_HOLD_* constants above for the calibration table. Uses
    _beat_text() so action captions and choice prompts scale the same way
    spoken lines do.
    """
    text = _beat_text(beat)
    n = max(0, len(text))
    return max(_POST_TYPE_HOLD_MIN,
               min(_POST_TYPE_HOLD_MAX, n * _POST_TYPE_HOLD_PER_CHAR))



def _start_kill_order_phase(force=False, prebuild=False):
    """Archives → Kill Order handoff (Slice 5a: real phase init).

    Builds the ground-floor world, trips the alarm, seeds the sweep/Volkov
    window flags (director lands in 5b/5c) and opens with the VASILE kill
    order beat + a scheduled Balaceanu PA announcement.

    ``force=True`` is the checkpoint/dev-console path (skips the Vostral
    gate - the checkpoint grants the flag itself).
    """
    # Idempotence keys off the WORLD, not the stage: the dev console
    # set_stage path pre-sets mission3_stage before any world exists, so a
    # stage-based guard here silently skipped the build (audit 2026-09-19).
    from missions.m3 import maps as _m3_maps
    from missions.m3.maps import MISSION3_KILL_ORDER_MAP
    built = (getattr(STATE, "m3_ko_world_built", False)
             and _m3_maps.MISSION3_MAP is MISSION3_KILL_ORDER_MAP)
    if not built:
        if not force and not getattr(STATE, "m3_vostral_acquired", False):
            return
        from missions.m3.world import _build_kill_order_world
        _build_kill_order_world()
    if prebuild:
        # Seamless in-engine cutscene handoff (mirrors the Archives
        # transition): world exists, stage holds while the cutscene plays.
        # The lockdown siren starts HERE so the cutscene carries the same
        # audio bed on both entry paths (it is idempotent).
        try:
            from missions.m3.world import _start_m3_alarm
            _start_m3_alarm()
        except Exception:
            pass
        STATE.mission3_stage = STAGE_KO_TRANSITION
        STATE.mission_phase = "m3_ko_transition"
        STATE.request_ko_transition_cutscene = True
        return
    if getattr(STATE, "mission3_stage", None) == STAGE_KILL_ORDER:
        return   # already in the KO world (flag survives STATE.reset)
    STATE.mission3_stage = STAGE_KILL_ORDER
    STATE.mission_phase = "m3_kill_order"
    STATE.mission3_kill_order_checkpoint_reached = True
    # Sweep director / Volkov window state (director ticks land in 5b/5c).
    STATE.m3_sweep_seeded = False      # director state is per-phase
    STATE.m3_sweep = None
    STATE.m3_sweep_window_frames = 5 * 60 * 60
    STATE.m3_sweep_window_active = False
    STATE.m3_sweep_committed = False
    STATE.m3_volkov_bailed = False
    STATE.m3_sweep_wave_idx = 0
    STATE.m3_sweep_advance_timer = 0
    STATE.m3_sweep_last_seen = None
    STATE.m3_exfil_door_cycle = 0
    STATE.m3_ko_pa_timer = 90          # Balaceanu PA beat (~1.5s in)
    STATE.m3_ko_dock_notified = False
    # Fresh phase = fresh gates: a checkpoint reload reuses the KO world
    # (the build is skipped, doors keep their breached state), so re-seal
    # the beat gates here - otherwise a reload inherits open gates and the
    # beats can be skipped again (anti-soft-lock for the rush fix).
    for d in STATE.doors:
        if _m3d(d).ko_beat_gate is not None and not d.locked:
            d.locked = True
            d.target_open = False
    if STATE.player is not None:
        STATE.player.hp = STATE.player.max_hp
    try:
        from missions.m3.world import _start_m3_alarm
        _start_m3_alarm()
    except Exception:
        pass
    _set_objective("Stairwell down, the sweep is inbound.")
    try:
        audio.play("radio_static", volume=0.40)
    except Exception:
        pass
    _radio(
        "VASILE: Balaceanu signed the kill order on state radio. Every disciplined "
        "team in that building is hunting you now, and he's listening. I'll "
        "keep their comms in your ear. Vasile out.",
        color=C_VASILE, duration=420, mark="kill_order_entered",
    )


def _current_beat():
    """Return the active dialogue beat, or None once the script is done."""
    if 0 <= _m3_flow._dialogue_index < len(_m3_flow._dialogue_beats):
        return _m3_flow._dialogue_beats[_m3_flow._dialogue_index]
    return None


def _beat_text(beat):
    """The string the typewriter reveals for this beat.

    Lines type their ``text``; action beats type their caption text (pulled
    from _ACTION_CAPTIONS so the renderer and typewriter stay in sync);
    choice beats type their ``prompt`` (the options appear only after the
    prompt finishes, so the panel reads as "think, then choose").
    """
    if not beat:
        return ""
    btype = beat.get("type")
    if btype == "line":
        return beat.get("text", "")
    if btype == "action":
        caption, _color = _ACTION_CAPTIONS.get(beat.get("action"), ("", C_SYSTEM))
        return caption
    if btype == "choice":
        return beat.get("prompt", "")
    return ""


def _advance_beat():
    """Move to the next beat. Resets per-beat timer, typewriter, slide, and
    post-typewriter hold. Fires the breach transition when the script runs
    off the end."""
    _m3_flow._dialogue_index += 1
    _m3_flow._dialogue_timer = 0
    _m3_flow._dialogue_char_idx = 0
    _m3_flow._dialogue_slide = 0.0
    _m3_flow._post_type_hold = 0
    # Mirror onto STATE for save/inspect surfaces.
    STATE.mission3_dialogue_index = _m3_flow._dialogue_index
    if _m3_flow._dialogue_index >= len(_m3_flow._dialogue_beats):
        _transition_to_breakout()


def _line_fully_typed(beat):
    """True once the typewriter has revealed every char of this beat's text."""
    return _m3_flow._dialogue_char_idx >= len(_beat_text(beat))


def _play_typewriter_tick(ch, idx, volume=0.11):
    """Per-char tick sound - mirrors acaristan._play_typewriter_tick exactly.

    Skips odd-index non-punctuation chars so it never sounds like a machine
    gun, but always ticks lightly on . ! ? so sentence ends land.
    """
    if not ch or ch.isspace():
        return
    if idx % 2 != 0 and ch not in ".!?":
        return
    try:
        audio.play("type_tick", volume=volume)
    except Exception:
        pass


def _update_interrogation():
    """Drive the typewriter, then auto-advance line/action beats once typing
    finishes plus a 2s hold. Choice beats block until handle_event resolves
    them."""
    beat = _current_beat()
    if beat is None:
        # Script is done but we haven't handed off yet (e.g. choice resolved
        # on the final beat). Still decay FX so the flash doesn't stick.
        if _m3_flow._breach_flash > 0:
            _m3_flow._breach_flash -= 1
        if _m3_flow._light_flicker > 0:
            _m3_flow._light_flicker -= 1
        if _m3_flow._volkov_breach_t >= 0:
            _m3_flow._volkov_breach_t += 1   # keep animating Volkov post-breach
        # Decay boots-approach too (in case the script ended mid-beat).
        if _m3_flow._boots_approach_t >= 0:
            _m3_flow._boots_approach_t += 1
        return
    _m3_flow._dialogue_timer += 1

    # Tick down FX flags the renderer reads.
    if _m3_flow._light_flicker > 0:
        _m3_flow._light_flicker -= 1
    if _m3_flow._breach_flash > 0:
        _m3_flow._breach_flash -= 1
    # Tick UP the breach animation clock once it's been seeded. The renderer
    # reads _m3_flow._volkov_breach_t to position Volkov's body, leg, and the swinging
    # door panel across the kick animation. Capped at 600 (10s) so the int
    # stays small even if the player walks away from the keyboard.
    if _m3_flow._volkov_breach_t >= 0 and _m3_flow._volkov_breach_t < 600:
        _m3_flow._volkov_breach_t += 1
        if _m3_flow._volkov_breach_t == 301:
            _detonate_cell_door()
        # At frame 150, the C4 brick is "seated" on the door hinge - play a
        # soft metallic click so the placement reads as a deliberate action,
        # not silent debris appearing.
        if _m3_flow._volkov_breach_t == 150 and "volkov_charge_placed" not in STATE.mission3_events:
            STATE.mission3_events.add("volkov_charge_placed")
            try:
                audio.play("rifle_handle", volume=0.25)
            except Exception:
                pass

    # Tick UP the boots-approach clock while the establishing beat is active.
    # The renderer reads _m3_flow._boots_approach_t to draw a faint shadow sweeping
    # under the cell door. Spaced footstep SFX at frames 0, 45, 90 (~0.75s
    # apart) sell "deliberate, slow cadence - not a patrol round."
    if _m3_flow._boots_approach_t >= 0:
        _m3_flow._boots_approach_t += 1
        if _m3_flow._boots_approach_t in (0, 45, 90) and \
                f"boots_step_{_m3_flow._boots_approach_t}" not in STATE.mission3_events:
            STATE.mission3_events.add(f"boots_step_{_m3_flow._boots_approach_t}")
            try:
                # Deliberate slow cadence, getting closer: tile heels, rising volume.
                audio.play("boot_step_tile",
                           volume={0: 0.45, 45: 0.60, 90: 0.75}[
                               _m3_flow._boots_approach_t])
            except Exception:
                pass

    # Panel slide-up on entry: ramps 0 -> 12 in the first frames, then the
    # renderer eases it back down to 0 (see _draw_dialogue_panel).
    if _m3_flow._dialogue_timer <= 12:
        _m3_flow._dialogue_slide = min(12.0, _m3_flow._dialogue_timer)

    btype = beat.get("type")

    # ── Typewriter: reveal one char per _TYPE_SPEED frames, with the
    # cutscene engine's punctuation-pause cadence. Drives the per-char tick.
    full_text = _beat_text(beat)
    if _m3_flow._dialogue_char_idx < len(full_text):
        if _m3_flow._dialogue_timer % _m3_flow._TYPE_SPEED == 0:
            # Apply punctuation pause to the PREVIOUS char (matches
            # acaristan.py:1277-1281): slow down after .!?,;:.
            prev = full_text[_m3_flow._dialogue_char_idx - 1] if _m3_flow._dialogue_char_idx > 0 else ""
            if prev in ".!?":
                pass  # full pause already consumed via the modulo skip below
            nxt = full_text[_m3_flow._dialogue_char_idx]
            _play_typewriter_tick(nxt, _m3_flow._dialogue_char_idx, volume=0.11)
            _m3_flow._dialogue_char_idx += 1

    # Choice beats: once the prompt finishes typing, the options appear and
    # the beat blocks until the player picks. Never auto-advance.
    if btype == "choice":
        return

    # Fire action-beat FX on entry (first frame the beat is visible).
    if btype == "action" and _m3_flow._dialogue_timer == 1:
        _trigger_action(beat.get("action"))

    # Voice-over for spoken beats (includes the injected choice replies).
    # Balaceanu is a pre-recorded tape on the cell monitor -> radio/TV filter.
    if btype == "line" and _m3_flow._dialogue_timer == 1:
        try:
            from audio import voice
            spk = beat.get("speaker", "") or ""
            voice.play_line(spk, beat.get("text", ""),
                            radio=spk.upper().startswith("BALACEANU"))
        except Exception:
            pass

    # Auto-advance rule: once the typewriter has revealed every character of
    # the current beat's text, hold for a length-scaled number of frames
    # (_post_type_hold_frames(beat) -- 3s floor, 6s ceiling, ~3 frames/char
    # in between), then advance. While the typewriter is still working, the
    # hold counter stays at 0 so a long line is never cut off mid-type.
    # Choice beats already returned above and never reach here.
    if not _line_fully_typed(beat):
        _m3_flow._post_type_hold = 0
        return
    _m3_flow._post_type_hold += 1

    # Do not auto-cut away from unskippable cinematic actions early.
    if _action_auto_locked(beat):
        return

    if _m3_flow._post_type_hold >= _post_type_hold_frames(beat):
        _advance_beat()


def _detonate_cell_door():
    """Actual detonation beat for Volkov's breach animation.

    Called when _m3_flow._volkov_breach_t reaches the detonation frame.
    This prevents the explosion SFX/flash from firing before Volkov
    has approached, planted the charge, and stepped back.
    """

    if "volkov_breach_detonated" in STATE.mission3_events:
        return

    STATE.mission3_events.add("volkov_breach_detonated")
    STATE.mission3_cell_open = True

    _m3_flow._breach_flash = 28
    effects.shake(36)

    # High-action lockdown alarm moment.
    _start_m3_alarm()

    try:
        audio.play("explosion", volume=0.9)
        audio.play("door_open", volume=0.6)
    except Exception:
        pass

    # The alarm alerts the entire cell block.
    for e in getattr(STATE, "enemies", []):
        try:
            e.alerted = True
            if e.state in ("IDLE", "PATROL", "SEARCH"):
                e.state = "CHASE"
            e.last_seen_pos = (
                _DOOR_TILE_COL * TILE_SIZE + TILE_SIZE,
                _DOOR_TILE_ROW * TILE_SIZE + TILE_SIZE // 2,
            )
            e.combat_alert_timer = max(getattr(e, "combat_alert_timer", 0), 420)
        except Exception:
            pass

    _set_objective("ALARMS TRIGGERED, GET OUT OF THE CELL BLOCK")

    door_px = _DOOR_TILE_COL * TILE_SIZE + TILE_SIZE // 2
    door_py = _DOOR_TILE_ROW * TILE_SIZE + TILE_SIZE // 2

    for _ in range(40):
        STATE.particles.append(Particle(
            door_px + _rng_legacy.randint(-20, 20),
            door_py + _rng_legacy.randint(-20, 20),
            (255, _rng_legacy.randint(100, 200), 0)
        ))

    STATE.gc_flash_timer = max(getattr(STATE, "gc_flash_timer", 0), 10)
    STATE.floating_texts.append([
        STATE.player.rect.centerx if STATE.player else door_px,
        (STATE.player.rect.centery - 50) if STATE.player else (door_py - 30),
        "ALARM TRIGGERED",
        (255, 60, 60),
        90,
    ])

    _radio("VOLKOV: Too loud now. Move!", color=C_VOLKOV, duration=220, mark="volkov_alarm_line")


def _trigger_action(action):
    """Fire the diegetic FX for an action beat (monitor on/off, breach, ...).

    Called from handle_event the first time an action beat becomes active so
    the sound/shake/caption land on entry, not on every frame the beat sits.
    """
    if action == "monitor_on":
        _m3_flow._monitor_on = True
        try:
            audio.play("radio_static", volume=0.5)
            audio.play("terminal_glitch", volume=0.4)
        except Exception:
            pass
        effects.shake(4)
    elif action == "monitor_off":
        _m3_flow._monitor_on = False
        _m3_flow._light_flicker = 60  # ~1s of fluorescent flicker after the cut
        try:
            audio.play("radio_static", volume=0.4)
        except Exception:
            pass
    elif action == "broadcast_caption":
        # The "STATE ADDRESS - LIVE TONIGHT - 22:00" caption beat. No FX of
        # its own beyond a soft CRT hum; the caption text does the work.
        try:
            audio.play("terminal_glitch", volume=0.25)
        except Exception:
            pass
    elif action == "boots_approach":
        # Pre-breach establishing beat. Someone is walking down the corridor
        # outside the cell - Volkov, but the player doesn't know that yet.
        # We play three spaced footsteps (3 separate SFX calls spread across
        # the beat's hold) and seed _m3_flow._boots_approach_t so the renderer can
        # draw a faint shadow sweeping under the cell door. The boots are
        # "wrong cadence" - too deliberate for a patrol - which is the
        # fiction cue that this isn't a normal guard round.
        _m3_flow._boots_approach_t = 0
        try:
            audio.play("boot_step_tile", volume=0.45)
        except Exception:
            pass
    elif action == "breach":
        # Start Volkov's breach animation.
        # Important: DO NOT detonate immediately. The explosion now fires
        # from _detonate_cell_door() when _m3_flow._volkov_breach_t reaches the
        # planted-charge detonation frame.
        STATE.mission3_events.add("volkov_breach")
        _m3_flow._volkov_breach_t = 0
        # Boots approach beat is done - stop drawing the under-door shadow.
        _m3_flow._boots_approach_t = -1

        try:
            audio.play("door_creak", volume=0.35)
            audio.play("rifle_handle", volume=0.35)
        except Exception:
            pass


def _transition_to_breakout():
    """Flip STAGE_INTERROGATION → STAGE_BREAKOUT, open the cell door, and
    trigger the chair-break cinematic.

    The breach beat already played the FX; this is the mechanical handoff:
    movement unlocks (see _movement_locked), the objective updates, and the
    cell's south-wall door tile becomes walkable so Biribel can step out.

    The chair break is now a cinematic cutscene, replacing the old
    interactive mash minigame.
    """
    STATE.mission3_stage = STAGE_BREAKOUT
    STATE.mission_phase = "m3_breakout"
    STATE.mission3_cell_open = True
    STATE.mission3_breakout_checkpoint_reached = True
    STATE.mission3_tone = list(_m3_flow._dialogue_tone)
    _m3_flow._monitor_on = False

    # Volkov does not wait in the doorway forever - he draws attention away.
    STATE.m3_volkov_run_active = True
    STATE.m3_volkov_run_timer = 0
    STATE.m3_volkov_run_done = False

    _radio(
        "VOLKOV: Alarm's up. I'll draw them off, you move.",
        color=C_VOLKOV,
        duration=360,
        mark="volkov_draws_them_off",
    )

    # Biribel's cell door is NEVER interactactable. The C4 blast tore a
    # hole through it - the player walks through the hole, they don't open
    # the door. Keep door.locked = True (so interact_door() rejects E-key
    # presses with a "locked" no-op) and disable its collision_rect (so
    # the player can walk through the blasted opening). The door STAYS
    # locked for the rest of the mission - it never becomes a normal
    # toggleable door.
    for door in STATE.doors:
        if door.rect.x // TILE_SIZE == _DOOR_TILE_COL and door.rect.y // TILE_SIZE == _DOOR_TILE_ROW:
            door.locked = True            # stays locked - no toggle, no E-key
            door.target_open = False      # never animates open
            door.anim_progress = 0.0      # stays in closed visual state
            door.collision_disabled = True  # but player can walk through (blast hole)
        elif (door.rect.x // TILE_SIZE == _DOOR_TILE_COL + 1 and
              door.rect.y // TILE_SIZE == _DOOR_TILE_ROW):
            door.locked = True
            door.target_open = False
            door.anim_progress = 0.0
            door.collision_disabled = True

    _open_cell_door()
    # Trigger the cinematic cutscene via acaristan's unified engine.
    # Mutations (chair broken, armed) are handled by the acaristan loop
    # when picking up this request.
    STATE.request_chair_break_cutscene = True


def _open_cell_door():
    """Punch the cell's south-wall door tile open so the player can leave.

    The interrogation cell is the 12x10 room outlined at (4,4) with a door
    gap at tile offset (5,9). That gap is already floor in MISSION3_MAP, but
    the wall tiles flanking it are solid 'C' - Slice 0 left them so the
    player couldn't wander during the (then-stub) cold open. Now that the
    breach has fired, we don't need to mutate the map (the door gap is
    already walkable); we just make sure no barrier rect overlaps the
    threshold. Kept as a no-op-safe hook for Slice 2's lockpick/shank beat.
    """
    # The door tile (col 9, row 13 → 4+5, 4+9) is already "." in the map.
    # No wall removal needed in Slice 1; this is the seam Slice 2 will use
    # to swap a locked-door tile for an open one.
    return



def _update_camera():
    """Per-frame camera. Returns the final render camera with shake + recoil."""
    target = _player_pos()

    # Interrogation breach focus
    if (getattr(STATE, "mission3_stage", STAGE_INTERROGATION) == STAGE_INTERROGATION
            and _m3_flow._volkov_breach_t >= 0):
        volkov_pos = _volkov_world_pos()
        if volkov_pos is not None:
            t = _m3_flow._volkov_breach_t
            if t <= 90:
                # Approach phase (~1.5s): TWO-SHOT. Frame both Volkov (in
                # the corridor, south) and the player (in the cell, north)
                # so the player sees where Volkov is coming from. Midpoint
                # between the two, biased slightly toward Volkov so his
                # silhouette isn't cut off at the screen's bottom edge.
                player_pos = _player_pos()
                mid_x = (volkov_pos[0] + player_pos[0]) // 2
                mid_y = (volkov_pos[1] + player_pos[1]) // 2
                # Bias toward Volkov by 25% so he gets more screen real
                # estate during the approach.
                target = (
                    int(mid_x + (volkov_pos[0] - mid_x) * 0.25),
                    int(mid_y + (volkov_pos[1] - mid_y) * 0.25) - 20,
                )
                # Slower focus factor during the two-shot so the pull-back
                # reads as cinematic, not as a bug.
                return follow_gameplay(target, MAP_W, MAP_H, ease=CAM_EASE_GAMEPLAY,
                                       deadzone_px=0.0, aim_angle=None, who="m3_breach")
            else:
                # Plant / retreat / detonation / re-enter: tight follow on
                # Volkov (original behavior).
                target = (volkov_pos[0], volkov_pos[1] - 40)
                return follow_gameplay(target, MAP_W, MAP_H, ease=CAM_EASE_M3_BREACH_TRACK,
                                       deadzone_px=0.0, aim_angle=None, who="m3_breach")

    # Default gameplay follow: aim lookahead + deadzone (breach framing above
    # needs exact arrival, so it skips both).
    aim = STATE.player.angle if (STATE.player and not STATE.player_dead) else None
    from missions.m3 import maps as _m3_maps  # lazy: live dims (broadcast map is smaller)
    mw, mh = _m3_maps._live_map_dims()
    return follow_gameplay(target, mw, mh, aim_angle=aim, who="m3")

_ACTION_CAPTIONS = {
    "monitor_on":        ("MONITOR: LIVE",                  C_BALACEANU),
    "monitor_off":       ("MONITOR: SIGNAL LOST",           (120, 120, 120)),
    "broadcast_caption": ("STATE ADDRESS, LIVE TONIGHT, 22:00. SUBJECT: ROUTE 12 PERPETRATOR", C_SYSTEM),
    "boots_approach":    ("(Boots in the corridor. Wrong cadence, too deliberate for a patrol.)", C_SYSTEM),
    "breach":            ("[ THE DOOR COMES IN ]",          C_VOLKOV),
}

_UNSKIPPABLE_ACTIONS = {"breach"}

# Volkov breach timing:
# 0-90   approach
# 90-210 plant charge
# 210-300 retreat
# 301    detonation
# 306-390 re-enter
# 430+   safe to let the script continue naturally
_UNSKIPPABLE_ACTION_MIN_FRAMES = {
    "breach": 430,
}


def _action_is_unskippable(beat):
    return (
        beat is not None
        and beat.get("type") == "action"
        and beat.get("action") in _UNSKIPPABLE_ACTIONS
    )


def _action_auto_locked(beat):
    """True while an unskippable action is still playing.

    Player input is ignored for unskippable actions, but this also stops
    the auto-advance from cutting away too early if timing constants change.
    """
    if not _action_is_unskippable(beat):
        return False

    action = beat.get("action")

    if action == "breach":
        return _m3_flow._volkov_breach_t < _UNSKIPPABLE_ACTION_MIN_FRAMES["breach"]

    return True
