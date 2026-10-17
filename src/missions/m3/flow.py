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

from core.config import (C_VASILE, HEIGHT, TILE_SIZE, WIDTH, font_terminal_small, get_scaled_mouse, screen)
from entities.art_cache import get_blood_decal, get_fullscreen_overlay, get_panel_bg
from core.state import STATE
from entities.player import Player, resolve_melee
from entities.enemy_ai import Enemy, enemy_hear_shot, _astar
from ui.hud import MiniMap, draw_objective_panel, draw_pinned_radio
from missions.m1 import _draw_molotov_icon
from fx import effects
import cutscenes
from core.camera import update_camera, reset_camera_state, draw_bullets, collide_bullet_walls
from entities.weapons import _wall_blocks_line
from core import config as _config
from engine.core import now_ms as _now_ms  # RPE6 B-001 timebase
audio = _config.audio

from missions.m3 import maps as _m3_maps  # _m3_maps.MISSION3_MAP/_m3_maps._last_keys/_m3_maps._objective/_m3_maps._radio_marks owner
from missions.m3.meta import _CELL_COL_EAST, _CELL_COL_WEST, _CELL_ROW_NORTH, _CELL_ROW_SOUTH  # cell bounds for the containment net
from missions.m3.meta import BCAST_TIME_LIMIT, C_BALACEANU, C_MARU, C_VOLKOV, INTERROGATION_SCRIPT, MISSION3_ID, MISSION3_KEY, MISSION3_TITLE, STAGE_ARCHIVES, STAGE_ARCHIVES_TRANSITION, STAGE_BREAKOUT, STAGE_BROADCAST, STAGE_BROADCAST_TRANSITION, STAGE_COMMS, STAGE_DONE, STAGE_INTERROGATION, STAGE_KILL_ORDER, STAGE_KO_TRANSITION, STAGE_VENT_CUTSCENE, _DOOR_TILE_COL, _DOOR_TILE_ROW
from missions.m3.maps import MISSION3_CELL_MAP, MISSION3_COMMS_MAP, MISSION3_ARCHIVES_MAP
from missions.m3.world import _exfil_pos, _build_kill_order_world
from missions.m3.world import _ARCHIVE_EXIT_COL, _ARCHIVE_EXIT_ROW, _ARCHIVES_EXIT_COL, _ARCHIVES_EXIT_ROW, _EXIT_TILE_COL, _EXIT_TILE_ROW, _MARU_TERMINAL_COL, _MARU_TERMINAL_ROW, _VOSTRAL_FILE_COL, _VOSTRAL_FILE_ROW, _build_archives_world, _build_comms_world, _build_world, _init_m3_detainees, _interrogation_chair_pos, _movement_locked, _near, _radio, _set_objective, _snap_camera_to, _spawn_m3_guards_once, _stop_m3_alarm, _update_volkov_escape_route
from missions.m3.interrog import _detonate_cell_door, _open_cell_door, _start_kill_order_phase, _update_interrogation
from missions.m3 import sweep as _ko_sweep
from engine.text import T as _T  # RPE6 Phase 4 text table
import game.world as _gw  # RPE6 Phase 5 (D4): mission data lives in components
from missions.m3.components import M3Door as _M3Door


def _m3d(door):
    """Declared M3 data of a door (replaces the ad hoc ``door.m3_*`` attributes)."""
    return _gw.ensure(door, _M3Door)


# Dialogue state (Slice 1: the interrogation cold open). Kept here so
# handle_event can read/write it without a STATE round-trip; mirrored onto
# STATE on start for save/inspect surfaces.
#   _dialogue_beats   - working list of beats (starts as a copy of the
#                       script; choice beats inject the player's follow-up
#                       line in-place, so the player's voice actually plays).
#   _dialogue_index   - index of the currently-visible beat.
#   _dialogue_timer   - frames the current beat has been on screen; used by
#                       the auto-advance fallback when the player doesn't
#                       press ENTER / SPACE.
#   _dialogue_choice  - highlighted option index while a choice beat is up.
#   _dialogue_tone    - list of option indices the player has picked so far
#                       (one entry per choice beat). Merged into
#                       STATE.mission3_tone at the end.
#   _dialogue_char_idx - typewriter: how many chars of the current line/action
#                       caption are revealed. Reset to 0 on each beat entry,
#                       advanced per-frame by _update_interrogation with the
#                       same punctuation-pause cadence as the cutscene engine
#                       (acaristan.py TEXT_SPEED). Reuses the cutscene's
#                       _play_typewriter_tick pattern for audio.
#   _dialogue_slide   - panel slide-up animation offset (12 -> 0 over ~12
#                       frames on beat entry, cubic ease), mirroring
#                       cutscenes.draw_dialogue_box's _dialogue_box_slide.
_dialogue_beats = []
_dialogue_index = 0
_dialogue_timer = 0
_dialogue_choice = 0
_dialogue_tone = []
_dialogue_char_idx = 0
_dialogue_slide = 0.0

# Typewriter cadence - matches acaristan.py's cutscene TEXT_SPEED (4 frames
# per char) and its punctuation-pause logic (extra frames after .!?,;:).
_TYPE_SPEED = 4
_TYPE_PAUSE_FULL = 25   # extra frames after . ! ?
_TYPE_PAUSE_SOFT = 12   # extra frames after , ; :
_TYPE_PAUSE_MID = 15    # extra frames after : (between soft/full)
# Visual FX flags the dialogue system raises and the renderer reads:
#   _monitor_on        - Balaceanu's wall monitor is lit (draws a red glow).
#   _breach_flash      - frames-remaining of the white breach flash overlay.
#   _light_flicker     - frames-remaining of the post-monitor-off flicker.
#   _volkov_breach_t   - animation clock for Volkov's door-kick: counts UP
#                        from 0 starting on the breach beat; renderer reads
#                        it to position his leg / body / door swing. Stays
#                        positive (and Volkov stays in the doorway) for the
#                        rest of STAGE_INTERROGATION and into early
#                        STAGE_BREAKOUT, so the kick is visible AND the
#                        aftermath reads as "Volkov is here, in the room."
_monitor_on = False
_breach_flash = 0
_light_flicker = 0
_volkov_breach_t = -1   # -1 = not yet triggered; >=0 = frames since breach
# Boots-in-the-corridor establishing beat. Set to 0 by the "boots_approach"
# action beat (fired BEFORE the breach beat). Renderer reads it to draw a
# faint shadow sweeping under the cell door - evidence that someone is
# approaching before the C4 appears. Counts up while active; -1 = inactive.
_boots_approach_t = -1
# Per-beat counter: frames elapsed since the typewriter finished revealing
# the current beat's text. Reset to 0 in _advance_beat and on every frame the
# typewriter is still working. When it reaches _post_type_hold_frames(beat)
# (length-scaled: 3s floor, 6s ceiling, ~3 frames/char in between), the beat
# auto-advances.
_post_type_hold = 0

# Interactive struggle component (removed in favor of cinematic)
# _chair_struggle = None

# ─────────────────────────────────────────────
# Chair-break cutscene shots (Mission 3 - the post-breach moment).
# These scene IDs route to bespoke cinematic renderers in cutscenes.py.
# They show the whole beat: restraints strain → chair leg snaps free →
# Biribel grabs it → he stands ready with the improvised weapon.
# ─────────────────────────────────────────────
chair_break_shots = [
    {
        "scene": "cb_strain",
        "speaker": "BIRIBEL",
        "text": "Come on... break.",
        "min_ms": 4000,
    },
    {
        "scene": "cb_crack",
        "speaker": "",
        "text": "[ METAL SCREAMS. THE CHAIR LEG TEARS FREE. ]",
        "min_ms": 2200,
    },
    {
        "scene": "cb_grab",
        "speaker": "BIRIBEL",
        "text": "Finally.",
        "min_ms": 2400,
    },
    {
        "scene": "cb_ready",
        "speaker": "BIRIBEL",
        "text": "Volkov was right. I owe him one.",
        "min_ms": 3000,
    },
]

# ─────────────────────────────────────────────
# Utility helpers
# ─────────────────────────────────────────────




# ─────────────────────────────────────────────
# Mission start / completion
# ─────────────────────────────────────────────
def start_mission3(preserve_timer=False):
    """Called by game_core/acaristan to begin Mission 3 gameplay."""
    global _dialogue_beats, _dialogue_index, _dialogue_timer, _dialogue_choice, _dialogue_tone
    global _dialogue_char_idx, _dialogue_slide
    global _monitor_on, _breach_flash, _light_flicker, _volkov_breach_t, _post_type_hold
    global _boots_approach_t

    _stop_m3_alarm(force=True)
    _m3_maps.MISSION3_MAP = MISSION3_CELL_MAP

    STATE.reset()
    STATE.active_mission = MISSION3_KEY
    STATE.active_mission_id = MISSION3_ID
    STATE.active_mission_title = MISSION3_TITLE
    STATE.active_mission_operation = "THE STABILIZATION CENTER - THE VOSTRAL"
    STATE.active_mission_outcome = "Biribel disavowed  ·  Balaceanu's vendetta in motion  ·  Broadcast tonight"
    STATE.active_mission_quote_attr = "Balaceanu, on the monitor:"
    STATE.active_mission_quote = '"You told them I was a coward, Biribel. A fake. Tonight I tell the nation what you are."'
    STATE.show_minimap = True
    STATE.m3_door_glow = False
    STATE.m3_hide_molotov = True
    STATE.minimap = MiniMap(_m3_maps.MISSION3_MAP, palette="m3")
    STATE.mission_start_time = (
        STATE.mission_start_time if (preserve_timer and STATE.mission_start_time)
        else _now_ms()
    )
    STATE.mission_end_time = 0
    STATE.hostiles_killed = 0
    STATE.shots_fired = 0
    STATE.shots_hit = 0
    STATE.request_mission3_ending = False
    STATE.request_chair_break_cutscene = False
    STATE.request_death_screen = False
    STATE.player_dead = False
    STATE.death_timer = 0

    # Every M3 entry (fresh start, checkpoint respawn, dev jump) must close
    # any stray upload OS. The broadcast OS is fullscreen and freezes
    # gameplay, so leaving it up across a respawn strands the player on a
    # terminal that is no longer connected to the slice.
    try:
        from ui import upload_os  # lazy: ui package
        if upload_os.is_upload_os_active():
            upload_os.deactivate_upload_os()
    except Exception:
        pass

    # ── Mission 3 stage / phase ──
    STATE.mission3_stage = STAGE_INTERROGATION
    STATE.mission_phase = "m3_interrogation"
    STATE.mission3_events = set()
    STATE.mission3_evidence_uploaded = False
    STATE.mission3_guards_spawned = False
    STATE.mission3_ammo_drops_spawned = 0
    STATE.mission3_bandages_spawned = 0
    STATE.mission3_dialogue_index = 0
    STATE.mission3_dialogue_choices = []
    # Tone memory: list of option indices the player picked at each choice
    # beat. Empty until the first choice resolves. Later slices (and the
    # ending cutscene) read this to color Biribel's voice.
    STATE.mission3_tone = []
    # Door-open flag for the breakout gate (set True by the breach beat).
    STATE.mission3_cell_open = False

    STATE.m3_alarm_active = False
    STATE.m3_alarm_timer = 0

    STATE.m3_volkov_run_active = False
    STATE.m3_volkov_run_timer = 0
    STATE.m3_volkov_run_done = False

    # Biribel is DISARMED in the cell - no pistol, no molotovs, no melee.
    # weapons.py reads this flag and early-returns from handle_shoot /
    # start_reload / handle_throw_bottle / handle_melee / switch_weapon so
    # the player can't fire / reload / throw with nothing in their hands.
    # Slice 2 sets this False when the player picks up a shank or takes a
    # sidearm off a dead guard.
    STATE.player_disarmed = True
    STATE.ammo_in_mag = 0
    STATE.spare_mags = 0
    STATE.mission3_weapon = "none"
    STATE.current_weapon = "pistol"
    STATE.k9_unlocked = False
    STATE.k9_ammo_in_mag = 24
    STATE.k9_mag_size = 24
    STATE.k9_spare_mags = 2
    STATE.k9_shot_cooldown = 0
    STATE.request_k9_pickup_cutscene = False
    STATE.request_service_transition_cutscene = False
    STATE.mission3_transition_kind = ""
    STATE.m3_volkov_ally_active = False
    STATE.m3_volkov_ally_x = 0.0
    STATE.m3_volkov_ally_y = 0.0
    STATE.m3_volkov_ally_angle = 0.0
    STATE.m3_volkov_ally_cooldown = 0
    STATE.m3_volkov_ally_shots = []
    STATE.m3_volkov_ally_max_hp = 220
    STATE.m3_volkov_ally_hp = 220
    STATE.m3_volkov_ally_hit_flash = 0
    STATE.m3_relay_active = False
    STATE.m3_relay_timer = 0
    STATE.m3_relay_tuned = False
    STATE.m3_comms_power_restored = False
    STATE.m3_comms_auth_acquired = False
    STATE.m3_comms_ambience_timer = 0

    # Archives (Phase 4)
    STATE.mission3_archives_checkpoint_reached = False
    STATE.m3_archives_cleared = False
    STATE.m3_maru_contacted = False
    STATE.m3_maru_contact_active = False
    STATE.m3_maru_contact_timer = 0
    STATE.m3_vostral_acquired = False
    STATE.m3_archives_ambience_timer = 0
    STATE.m3_archives_alarm = False
    STATE.request_archives_transition_cutscene = False
    STATE.request_vostral_pickup_cutscene = False
    STATE.request_broadcast_transition_cutscene = False
    # 22:00 fail-cutscene request. Cleared on every entry (and by
    # _retry_broadcast_slice) so a stale True can't fire a fail cutscene into
    # a fresh run.
    STATE.request_mission3_fail_cutscene = False

    # ── Black Ledger easter egg ──
    # Triggered only if the player personally shoots every ambient detainee.
    # This is deliberately a punishment/consequence encounter, not a reward.
    STATE.m3_black_ledger_triggered = False
    STATE.m3_black_ledger_inmate_active = False
    STATE.m3_black_ledger_inmate = None
    STATE.m3_black_ledger_intro_timer = 0
    STATE.m3_black_ledger_death_active = False
    STATE.m3_black_ledger_death_timer = 0

    # World build + camera snap.
    _build_world()
    _init_m3_detainees()
    if STATE.player is not None:
        # Phase 1 starts with Biribel cuffed to the interrogation chair, not
        # standing on the generic map spawn tile. Once the chair breaks, the
        # same world position becomes the breakout starting point.
        STATE.player.rect.center = _interrogation_chair_pos()
    reset_camera_state()
    _snap_camera_to(_interrogation_chair_pos())
    STATE.screen_shake = 0  # fresh start must not inherit a previous run's shake

    # Fresh scratch.
    _m3_maps._objective = "Survive the interrogation."
    _m3_maps._radio_marks = set()
    _m3_maps._last_keys = None

    # Dialogue cold-open: deep-copy the script so choice beats can inject
    # the player's follow-up line in-place without mutating the template.
    _dialogue_beats = [dict(b) for b in INTERROGATION_SCRIPT]
    _dialogue_index = 0
    _dialogue_timer = 0
    _dialogue_choice = 0
    _dialogue_tone = []
    _dialogue_char_idx = 0
    _dialogue_slide = 0.0
    _monitor_on = False
    _breach_flash = 0
    _light_flicker = 0
    _post_type_hold = 0
    _volkov_breach_t = -1
    _boots_approach_t = -1

    return STATE.player


def start_mission3_breakout_checkpoint(preserve_timer=False):
    """Respawn Mission 3 at playable breakout after Volkov's breach.

    Used by restart_current_mission() once the player has already reached the
    post-breach gameplay. This intentionally skips:
      - Mission 3 intro cutscene,
      - interactive interrogation,
      - Volkov breach cinematic,
      - chair-break cutscene.

    The player respawns in the cell with the chair leg and must sharpen it at
    the drain, matching the first real gameplay objective after the cutscenes.
    """
    global _dialogue_beats, _dialogue_index, _dialogue_timer, _dialogue_choice, _dialogue_tone
    global _dialogue_char_idx, _dialogue_slide
    global _monitor_on, _breach_flash, _light_flicker, _volkov_breach_t, _boots_approach_t, _post_type_hold

    start_mission3(preserve_timer=preserve_timer)

    # Mechanical post-breach state.
    STATE.mission3_stage = STAGE_BREAKOUT
    STATE.mission_phase = "m3_breakout"
    STATE.mission3_breakout_checkpoint_reached = True
    STATE.mission3_cell_open = True
    STATE.mission3_chair_broken = True
    STATE.mission3_chair_break_anim = -1
    STATE.request_chair_break_cutscene = False
    STATE.player_disarmed = False
    STATE.mission3_weapon = "chair_leg"
    STATE.current_weapon = "pistol"
    # This respawn hands back only the chair leg, so the first-guard sidearm
    # guarantee must be pending again. mission3_sidearm_acquired is not part of
    # STATE.reset() (that would break the comms/archives checkpoints, which are
    # meant to arrive armed), so clear it here explicitly. Without this a death
    # restart leaves the flag True, the drop logic thinks the player is already
    # armed, and no guard ever drops a pistol.
    STATE.mission3_sidearm_acquired = False
    STATE.pickups = []
    STATE.mission3_doorway_blocked = True
    STATE.mission3_crafting_active = False
    STATE.mission3_crafting_progress = 0.0
    STATE.mission3_crafting_shavings = []
    STATE.mission3_vent_open = False
    STATE.mission3_breakout_announced = True

    # Volkov's breach/run is already over for checkpoint purposes; don't replay
    # him standing/running through the doorway on every death restart.
    STATE.m3_volkov_run_active = False
    STATE.m3_volkov_run_timer = 241
    STATE.m3_volkov_run_done = True
    _volkov_breach_t = -1
    _boots_approach_t = -1
    _breach_flash = 0
    _light_flicker = 0
    _monitor_on = False
    _post_type_hold = 0

    # Make the blasted cell door passable/visually resolved.
    for door in STATE.doors:
        if (door.rect.x // TILE_SIZE in (_DOOR_TILE_COL, _DOOR_TILE_COL + 1)
                and door.rect.y // TILE_SIZE == _DOOR_TILE_ROW):
            door.locked = True
            door.target_open = False
            door.anim_progress = 0.0
            door.collision_disabled = True
    _open_cell_door()

    # Respawn at the first playable post-cutscene position.
    if STATE.player is not None:
        STATE.player.rect.center = _interrogation_chair_pos()
        STATE.player.hp = STATE.player.max_hp
        STATE.player_dead = False
        STATE.death_timer = 0
        STATE.death_anim_phase = 0
        STATE.death_anim_timer = 0
        STATE.request_death_screen = False
        STATE.player.angle = math.pi / 2

    # Dialogue/cutscene state is done; keep tone empty unless a save system later
    # wants to preserve choices.
    _dialogue_beats = []
    _dialogue_index = 0
    _dialogue_timer = 0
    _dialogue_choice = 0
    _dialogue_tone = []
    _dialogue_char_idx = 0
    _dialogue_slide = 0.0
    STATE.mission3_dialogue_index = 0
    STATE.mission3_dialogue_choices = []

    _m3_maps._objective = "Sharpen the chair leg at the drain. Volkov holds the door."
    _m3_maps._radio_marks = set()
    _m3_maps._last_keys = None
    _set_objective("Craft shiv at marked drain.")
    _radio("VOLKOV: I bought you seconds. Make the leg useful, then move.",
           color=C_VOLKOV, duration=300, mark="breakout_checkpoint_respawn")

    reset_camera_state()
    _snap_camera_to(_interrogation_chair_pos())

    # Re-arm the cell block. STATE.reset() (inside start_mission3) cleared the
    # guard flags, so without this the player would respawn into an empty map
    # once the doorway unblocks: nothing to kill, no guard sidearm drop, and no
    # way out - _m3_exit_requirements() requires the cell block to be secured
    # first. Mirrors the live path (_update_breakout_stage() spawns as soon as
    # the doorway unblocks). Must run LAST: _spawn_m3_guards_once() clears
    # STATE.enemies, and anything after it would fight the fresh spawn.
    _spawn_m3_guards_once(force=True)
    return STATE.player


def start_mission3_comms_checkpoint(preserve_timer=False):
    """Respawn Mission 3 at the Comms Wing after reaching STAGE_COMMS.

    Used by restart_current_mission() once the player has already reached the
    Comms Wing (``mission3_comms_checkpoint_reached``). This intentionally
    skips the entire breakout slice - interrogation, Volkov breach, cell-block
    guards, the service-door transition cutscene, and the K-9 armory - because
    reaching comms already required clearing all of that. The player respawns
    in the Comms Wing with the K-9 loadout and full health.
    """
    global _dialogue_beats, _dialogue_index, _dialogue_timer, _dialogue_choice, _dialogue_tone
    global _dialogue_char_idx, _dialogue_slide
    global _monitor_on, _breach_flash, _light_flicker, _volkov_breach_t, _boots_approach_t, _post_type_hold

    start_mission3(preserve_timer=preserve_timer)

    # Comms-wing mechanical state - reaching comms implies all breakout beats
    # are done, so mirror the post-cutscene state here.
    STATE.mission3_stage = STAGE_COMMS
    STATE.mission_phase = "m3_comms"
    STATE.mission3_breakout_checkpoint_reached = True
    STATE.mission3_comms_checkpoint_reached = True
    STATE.mission3_cell_block_cleared = True
    STATE.mission3_cell_open = True
    STATE.mission3_chair_broken = True
    STATE.mission3_chair_break_anim = -1
    STATE.request_chair_break_cutscene = False
    STATE.player_disarmed = False
    STATE.mission3_weapon = "k9_smg"
    STATE.current_weapon = "k9_smg"
    STATE.k9_unlocked = True
    STATE.k9_ammo_in_mag = STATE.k9_mag_size
    STATE.k9_spare_mags = 2
    STATE.k9_shot_cooldown = 0
    # The player looted the guard sidearm back in the cell block, and
    # weapons._player_has_firearm() gates the K-9 on this flag - without it this
    # checkpoint respawns "armed" with a K-9 that refuses to fire. The flag is
    # not in STATE.reset(), so every armed path must set it explicitly.
    STATE.mission3_sidearm_acquired = True
    STATE.mission3_doorway_blocked = False
    STATE.mission3_crafting_active = False
    STATE.mission3_crafting_progress = 0.0
    STATE.mission3_crafting_shavings = []
    STATE.mission3_vent_open = False
    STATE.mission3_breakout_announced = True
    STATE.m3_volkov_run_active = False
    STATE.m3_volkov_run_timer = 241
    STATE.m3_volkov_run_done = True
    _volkov_breach_t = -1
    _boots_approach_t = -1
    _breach_flash = 0
    _light_flicker = 0
    _monitor_on = False
    _post_type_hold = 0

    # Swap to the Comms Wing map and entities (also fully heals the player).
    _build_comms_world()
    if STATE.player is not None:
        STATE.player.hp = STATE.player.max_hp
        STATE.player_dead = False
        STATE.death_timer = 0
        STATE.death_anim_phase = 0
        STATE.death_anim_timer = 0
        STATE.request_death_screen = False
        STATE.player.angle = math.pi / 2

    # Dialogue/cutscene state is done.
    _dialogue_beats = []
    _dialogue_index = 0
    _dialogue_timer = 0
    _dialogue_choice = 0
    _dialogue_tone = []
    _dialogue_char_idx = 0
    _dialogue_slide = 0.0
    STATE.mission3_dialogue_index = 0
    STATE.mission3_dialogue_choices = []

    _m3_maps._objective = "Restore auxiliary power → copy relay authorization → tune the relay."
    _m3_maps._radio_marks = set()
    _m3_maps._last_keys = None
    _set_objective("Restore auxiliary power in Battery Backup.")
    _radio("VASILE: Relay is dead down here. Restore battery backup, copy auth from Security, then tune the terminal.",
           color=C_VASILE, duration=420, mark="comms_phase_onboarding", priority=1)

    reset_camera_state()
    _snap_camera_to(STATE.player.rect.center)
    return STATE.player



def start_mission3_archives_checkpoint(preserve_timer=False):
    """Respawn Mission 3 at the Archives Wing after reaching STAGE_ARCHIVES.

    Used by restart_current_mission() once the player has crossed from Comms
    into Archives. Skips interrogation / breakout / comms entirely and drops
    the player at the Archives foyer with the K-9 loadout and full health.
    """
    global _dialogue_beats, _dialogue_index, _dialogue_timer, _dialogue_choice, _dialogue_tone
    global _dialogue_char_idx, _dialogue_slide
    global _monitor_on, _breach_flash, _light_flicker, _volkov_breach_t, _boots_approach_t, _post_type_hold

    start_mission3(preserve_timer=preserve_timer)

    STATE.mission3_stage = STAGE_ARCHIVES
    STATE.mission_phase = "m3_archives"
    STATE.mission3_breakout_checkpoint_reached = True
    STATE.mission3_comms_checkpoint_reached = True
    STATE.mission3_archives_checkpoint_reached = True
    STATE.mission3_cell_block_cleared = True
    STATE.mission3_cell_open = True
    STATE.mission3_chair_broken = True
    STATE.mission3_chair_break_anim = -1
    STATE.request_chair_break_cutscene = False
    STATE.player_disarmed = False
    STATE.mission3_weapon = "k9_smg"
    STATE.current_weapon = "k9_smg"
    STATE.k9_unlocked = True
    STATE.k9_ammo_in_mag = STATE.k9_mag_size
    STATE.k9_spare_mags = 2
    STATE.k9_shot_cooldown = 0
    # The player looted the guard sidearm back in the cell block, and
    # weapons._player_has_firearm() gates the K-9 on this flag - without it this
    # checkpoint respawns "armed" with a K-9 that refuses to fire. The flag is
    # not in STATE.reset(), so every armed path must set it explicitly.
    STATE.mission3_sidearm_acquired = True
    STATE.mission3_doorway_blocked = False
    STATE.mission3_crafting_active = False
    STATE.mission3_crafting_progress = 0.0
    STATE.mission3_crafting_shavings = []
    STATE.mission3_vent_open = False
    STATE.mission3_breakout_announced = True
    STATE.m3_volkov_run_active = False
    STATE.m3_volkov_run_timer = 241
    STATE.m3_volkov_run_done = True
    # Comms already done.
    STATE.m3_relay_tuned = True
    STATE.m3_comms_power_restored = True
    STATE.m3_comms_auth_acquired = True
    _volkov_breach_t = -1
    _boots_approach_t = -1
    _breach_flash = 0
    _light_flicker = 0
    _monitor_on = False
    _post_type_hold = 0

    _build_archives_world()
    if STATE.player is not None:
        STATE.player.hp = STATE.player.max_hp
        STATE.player_dead = False
        STATE.death_timer = 0
        STATE.death_anim_phase = 0
        STATE.death_anim_timer = 0
        STATE.request_death_screen = False
        STATE.player.angle = -math.pi / 2

    _dialogue_beats = []
    _dialogue_index = 0
    _dialogue_timer = 0
    _dialogue_choice = 0
    _dialogue_tone = []
    _dialogue_char_idx = 0
    _dialogue_slide = 0.0
    STATE.mission3_dialogue_index = 0
    STATE.mission3_dialogue_choices = []

    _m3_maps._objective = "With Volkov, clear the atrium, then find Maru's dead-drop (NW)."
    _m3_maps._radio_marks = set()
    _m3_maps._last_keys = None
    _set_objective("With Volkov, clear the atrium, then find Maru's dead-drop (NW).")
    _radio("VOLKOV: Back on your six. Call when you're dry, I've got mags.",
           color=C_VOLKOV, duration=300, mark="archives_checkpoint_volkov")
    _radio("VASILE: Archives wing is live. Maru's dead-drop is northwest.",
           color=C_VASILE, duration=320, mark="archives_checkpoint_respawn")

    reset_camera_state()
    _snap_camera_to(STATE.player.rect.center)
    return STATE.player


def _complete_mission3():
    """Signal mission completion → acaristan plays mission3_ending_shots."""
    if getattr(STATE, "request_mission3_ending", False):
        return  # idempotent guard

    _stop_m3_alarm()

    STATE.mission3_stage = STAGE_DONE
    STATE.mission3_evidence_uploaded = True
    STATE.mission_end_time = _now_ms()
    STATE.request_mission3_ending = True
    audio.play("terminal_glitch", volume=0.55)


# ─────────────────────────────────────────────
# Per-frame update
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
    if not _movement_locked() and _m3_maps._last_keys is not None:
        # Delta-time aware: speed is in px/frame, multiply by (60*dt).
        _dt_mul = 60.0 * STATE.dt
        if _m3_maps._last_keys[pygame.K_w]:
            dy -= STATE.player.speed * _dt_mul
        if _m3_maps._last_keys[pygame.K_s]:
            dy += STATE.player.speed * _dt_mul
        if _m3_maps._last_keys[pygame.K_a]:
            dx -= STATE.player.speed * _dt_mul
        if _m3_maps._last_keys[pygame.K_d]:
            dx += STATE.player.speed * _dt_mul
    if dx and dy:
        dx *= 0.707
        dy *= 0.707
    prev_center = STATE.player.rect.center
    STATE.player.move(dx, dy, solid_walls)

    # Anti-tunnel guard. Player.move() resolves collisions by snapping the
    # rect to the wall edge on the side it was moving toward. That is correct
    # when the player walks INTO a wall, but if the rect already overlapped a
    # solid (spawned inside a prop, a door collider closing on him), the snap
    # can fling him to the far side of the wall - a teleport, not a stop. A
    # legitimate step can never displace him further than the step itself,
    # so anything beyond that is rejected and he stays where he was.
    nx, ny = STATE.player.rect.center
    if (abs(nx - prev_center[0]) > abs(dx) + 2
            or abs(ny - prev_center[1]) > abs(dy) + 2):
        STATE.player.rect.center = prev_center

    # Cell containment safety net. Until the shiv is crafted the blasted
    # doorway is sealed (Volkov holds it), so Biribel can only legitimately
    # be inside his cell. If anything ever puts him outside it, he can't get
    # back in or reach the drain - a hard softlock. Put him back on his feet
    # at the broken chair instead.
    if (getattr(STATE, "mission3_stage", "") == STAGE_BREAKOUT
            and getattr(STATE, "mission3_doorway_blocked", False)
            and _m3_maps.MISSION3_MAP is MISSION3_CELL_MAP):
        cx, cy = STATE.player.rect.center
        inside = (_CELL_COL_WEST * TILE_SIZE <= cx < (_CELL_COL_EAST + 1) * TILE_SIZE
                  and _CELL_ROW_NORTH * TILE_SIZE <= cy < (_CELL_ROW_SOUTH + 1) * TILE_SIZE)
        if not inside:
            STATE.player.rect.center = _interrogation_chair_pos()



# Chair-break cutscene phase boundaries (frames @ 60fps).
_CB_SHOT1 = cutscenes.CB_SHOT1   # ① Strain  (wrist close-up)   ~4s
_CB_SHOT2 = cutscenes.CB_SHOT2   # ② Crack   (chair bursts)     ~2.2s
_CB_SHOT3 = cutscenes.CB_SHOT3   # ③ Grab    (hand on the leg)   ~2.4s
_CB_SHOT4 = cutscenes.CB_SHOT4   # ④ Ready   (hefts the leg)     ~3s
_CB_END   = cutscenes.CB_END     # total cutscene length

# Individual shot durations (smoke_test / inspection imports these).
_CB_SHOT1_DUR = cutscenes.CB_SHOT1_DUR
_CB_SHOT2_DUR = cutscenes.CB_SHOT2_DUR
_CB_SHOT3_DUR = cutscenes.CB_SHOT3_DUR
_CB_SHOT4_DUR = cutscenes.CB_SHOT4_DUR


def _draw_chair_break_cutscene(anim_t: int) -> None:
    """Render the chair-break cinematic for global-clock frame `anim_t`.

    Each shot is a self-contained full-screen cinematic illustration.
    No tilemap compositing - each shot draws its own background,
    characters, and lighting from scratch.

    Transitions:
    - Shot 1-2: hard cut (the crack snaps - no dissolve needed)
    - Shot 2-3: hard cut (the break cuts to the grab)
    - Shot 3-4: 12-frame cross-dissolve (smooths the pose change)
    - Shot 4-gameplay: fade to black (handled inside the shot)
    """
    # Cross-dissolve between Shot 3 and Shot 4
    xfade_in = _CB_SHOT4
    xfade_len = 12
    if xfade_in <= anim_t < xfade_in + xfade_len:
        p = (anim_t - xfade_in) / xfade_len
        # Draw Shot 3 at its final frame
        cutscenes._draw_cb_grab(screen, cutscenes.CB_SHOT3_DUR - 1)
        # Blend Shot 4 at its first frame on top
        rs = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        cutscenes._draw_cb_ready(rs, 0)
        rs.set_alpha(int(255 * p))
        screen.blit(rs, (0, 0))
    elif anim_t < _CB_SHOT2:
        cutscenes._draw_cb_strain(screen, anim_t - _CB_SHOT1)
    elif anim_t < _CB_SHOT3:
        cutscenes._draw_cb_crack(screen, anim_t - _CB_SHOT2)
    elif anim_t < _CB_SHOT4:
        cutscenes._draw_cb_grab(screen, anim_t - _CB_SHOT3)
    else:
        cutscenes._draw_cb_ready(screen, anim_t - _CB_SHOT4)


def _grant_chair_leg_from_cutscene():
    """Apply the gameplay handoff authored into the chair-break cinematic.

    The full application loop also performs these mutations when it launches
    the legacy cutscene request. Mission 3's own update/render path uses
    STATE.mission3_chair_break_anim directly, so the mission module must own
    the same handoff for smoke tests, debug starts, and in-engine cinematic
    rendering.
    """
    if getattr(STATE, "mission3_chair_broken", False):
        return

    STATE.mission3_chair_broken = True
    STATE.player_disarmed = False
    STATE.mission3_weapon = "chair_leg"

    try:
        audio.play("door_break", volume=0.35)
    except Exception:
        pass


def _update_chair_break_cutscene_state():
    """Advance the Mission 3 chair-break cinematic clock.

    Returns True while the cinematic is active, allowing game_update() to
    pause normal combat/player simulation until the cutscene hands control
    back to the breakout.
    """
    anim_t = getattr(STATE, "mission3_chair_break_anim", -1)
    if anim_t < 0:
        return False

    # ── Chair foley: the struggle is audible, not just animated ──
    if "chair_foley_strain" not in STATE.mission3_events:
        STATE.mission3_events.add("chair_foley_strain")
        audio.play("chair_drag", volume=0.50)
    if anim_t >= _CB_SHOT1 and "chair_foley_second_drag" not in STATE.mission3_events:
        STATE.mission3_events.add("chair_foley_second_drag")
        audio.schedule(50, "chair_drag", volume=0.40)
    if anim_t >= _CB_SHOT3 and "chair_foley_scrape" not in STATE.mission3_events:
        STATE.mission3_events.add("chair_foley_scrape")
        audio.play("chair_scrape_short", volume=0.45)

    if anim_t >= _CB_SHOT2:
        _grant_chair_leg_from_cutscene()

    if anim_t >= _CB_END:
        _grant_chair_leg_from_cutscene()
        STATE.mission3_chair_break_anim = -1
        STATE.request_chair_break_cutscene = False
        _set_objective("Sharpen the chair leg at the drain. Volkov holds the door.")
        return True

    STATE.mission3_chair_break_anim = anim_t + 1
    return True


def _update_stage(keys):
    """Phase dispatcher.

    STAGE_INTERROGATION (Slice 1): advance the dialogue cold open. Line and
    action beats auto-advance after a reading-time timeout; choice beats
    block until the player picks. When the script runs off the end, the
    breach has already fired - flip to STAGE_BREAKOUT and open the cell.

    STAGE_BREAKOUT (Slice 2): stealth-first escape. The player must reach
    the cell-block exit tile (south of the security door) to advance to
    STAGE_COMMS. Guards start unaware; killing them or making noise will
    alert the others via enemy_hear_shot. Picking up a guard's dropped
    sidearm lets the player engage at range (and escalates any nearby
    guards who hear the gunshot).

    STAGE_ARCHIVES (Slice 4): separate map, clear security, Maru dead-drop
    contact, steal the Vostral file, exit east toward Kill Order.

    STAGE_BROADCAST (Slice 6): combat gauntlet in the Broadcast Wing. Race
    the 22:00 address clock: clear wave 1 in the cable corridor, wave 2 at
    the studio gate, then hold the studio during uplink. Timeout triggers a
    fail cutscene and retry from the start of Slice 6.
    """
    global _dialogue_timer, _dialogue_index, _breach_flash, _light_flicker
    global _volkov_breach_t
    global _boots_approach_t
    stage = getattr(STATE, "mission3_stage", STAGE_INTERROGATION)

    if getattr(STATE, "m3_alarm_active", False):
        STATE.m3_alarm_timer = getattr(STATE, "m3_alarm_timer", 0) + 1

    if stage == STAGE_INTERROGATION:
        _set_objective("Survive the interrogation.")
        _update_interrogation()
        return

    # STAGE_BREAKOUT onward: keep ticking the breach animation clock (so
    # Volkov's kick finishes and he stands in the doorway) and decay any
    # residual FX. The renderer reads these flags in every stage.
    if _volkov_breach_t >= 0 and _volkov_breach_t < 600:
        _volkov_breach_t += 1
        if _volkov_breach_t == 301:
            _detonate_cell_door()
        # At frame 150, the C4 brick is "seated" on the door hinge - play a
        # soft metallic click so the placement reads as a deliberate action,
        # not silent debris appearing.
        if _volkov_breach_t == 150 and "volkov_charge_placed" not in STATE.mission3_events:
            STATE.mission3_events.add("volkov_charge_placed")
            try:
                audio.play("rifle_handle", volume=0.25)
            except Exception:
                pass
    if _breach_flash > 0:
        _breach_flash -= 1
    if _light_flicker > 0:
        _light_flicker -= 1

    if stage == STAGE_BREAKOUT:
        _update_breakout_stage()
    elif stage == STAGE_VENT_CUTSCENE:
        # Cutscene is playing (handled by acaristan.py). Once the request
        # flag is consumed, transition to STAGE_COMMS.
        if not getattr(STATE, "request_vent_cutscene", False):
            _start_comms_phase()
    elif stage == STAGE_ARCHIVES_TRANSITION:
        # Cutscene is playing (handled by acaristan.py). Once the request
        # flag is consumed, transition to STAGE_ARCHIVES.
        if not getattr(STATE, "request_archives_transition_cutscene", False):
            _start_archives_phase()
    elif stage == STAGE_COMMS:
        STATE.m3_comms_ambience_timer = getattr(
            STATE, "m3_comms_ambience_timer", 0) + 1
        _m3_check_volkov_ammo_resupply()
        _update_volkov_mags()
        if getattr(STATE, "m3_relay_active", False):
            _set_objective("Tuning relay...")
        elif not getattr(STATE, "m3_relay_tuned", False):
            if len(getattr(STATE, "enemies", [])) > 0:
                _set_objective(f"Clear Comms Wing: {len(STATE.enemies)} guard(s) left.")
            elif not getattr(STATE, "m3_comms_power_restored", False):
                _set_objective("Restore auxiliary power in Battery Backup.")
            elif not getattr(STATE, "m3_comms_auth_acquired", False):
                _set_objective("Copy relay authorization from the Security booth.")
            else:
                _set_objective("Return to the relay and establish KRAP contact.")
        else:
            _set_objective("Signal restored. Reach Archives.")
            _maybe_trigger_archives_handoff()
    elif stage == STAGE_ARCHIVES:
        _m3_check_volkov_ammo_resupply()
        _update_volkov_mags()
        _update_archives_stage()
    elif stage == STAGE_KO_TRANSITION:
        # Cutscene holding stage: once the app consumes the request flag,
        # finish the handoff into the real phase.
        if not getattr(STATE, "request_ko_transition_cutscene", False):
            _start_kill_order_phase()
    elif stage == STAGE_KILL_ORDER:
        # Slice 5a: entered after Vostral is secured and player exits north.
        if not getattr(STATE, "m3_ko_world_built", False):
            # Dev console set_stage path: build the world on first tick.
            _start_kill_order_phase(force=True)
        else:
            _update_kill_order_stage()
    elif stage == STAGE_BROADCAST_TRANSITION:
        # Cutscene holding stage: once the app consumes the request flag,
        # finish the handoff into the real phase.
        if not getattr(STATE, "request_broadcast_transition_cutscene", False):
            _start_broadcast_phase()
    elif stage == STAGE_BROADCAST:
        # Volkov holds the floor with you in the finale: same mag-toss
        # resupply as Comms/Archives/Kill Order.
        if getattr(STATE, "m3_volkov_ally_active", False) \
                and not getattr(STATE, "m3_volkov_bailed", False):
            _m3_check_volkov_ammo_resupply()
            _update_volkov_mags()
        _update_broadcast_stage()


def _update_kill_order_stage():
    """Phase 5 runtime (5a): PA beats + objective ladder.

    Sweep director (5b), overwatch pin + Volkov window (5c) and the exfil
    holdout (5d) hook in here.
    """
    pa = getattr(STATE, "m3_ko_pa_timer", 0)
    if pa > 0:
        STATE.m3_ko_pa_timer = pa - 1
        if pa == 1 and "ko_pa_balaceanu" not in STATE.mission3_events:
            STATE.mission3_events.add("ko_pa_balaceanu")
            try:
                audio.play("pa_mumble", volume=0.30)
            except Exception:
                pass
            _radio(
                "BALACEANU (PA): Sweep teams, report. The prisoner carries state "
                "property. My address begins at 22:00, and he will not outlive it.",
                color=C_BALACEANU, duration=420, mark="ko_pa_balaceanu",
            )
    # Volkov keeps tossing mags in Phase 5 too (bug report 2026-09-19:
    # resupply was wired for Comms/Archives branches only).
    if getattr(STATE, "m3_volkov_ally_active", False) \
            and not getattr(STATE, "m3_volkov_bailed", False):
        _m3_check_volkov_ammo_resupply()
        _update_volkov_mags()
    if STATE.player is None:
        return
    ex_x, ex_y = _exfil_pos()
    px, py = STATE.player.rect.centerx, STATE.player.rect.centery
    st = getattr(STATE, "m3_sweep", None)
    gate0 = bool(st and len(st["waves"]) > 0
                 and st["waves"][0].get("cleared", False))
    gate1 = bool(st and len(st["waves"]) > 1
                 and st["waves"][1].get("cleared", False))
    if py > 32 * TILE_SIZE and math.hypot(px - ex_x, py - ex_y) < TILE_SIZE * 2.2:
        if not getattr(STATE, "m3_sweep_committed", False):
            STATE.m3_sweep_committed = True
            STATE.floating_texts.append([
                px, py - 40, "EXFIL POINT, HOLDOUT INCOMING", (200, 185, 120), 160])
        _set_objective("Loading dock, exfil at the van.")
    elif not gate0:
        _set_objective("Stairwell, clear the ambush to open the south gates.")
    elif not gate1:
        _set_objective("Lobby, drop the marksman to open the dock gates.")
    elif py > 27 * TILE_SIZE:
        _set_objective("South corridors, push to the loading dock.")
    elif py > 9 * TILE_SIZE:
        _set_objective("Lobby, push south, the dock gates are open.")
    else:
        _set_objective("Sweep still hunting, push to the dock.")
    _ko_sweep.update_kill_order()


def _ko_zone_of(px, py):
    """Zone graph node for the sweep director (5b): 6-zone map partition."""
    if py <= 8 * TILE_SIZE:
        return "stair"
    if py > 32 * TILE_SIZE:
        return "dock"
    if py > 27 * TILE_SIZE:
        return "south"
    if px <= 8 * TILE_SIZE:
        return "west"
    if px >= 29 * TILE_SIZE:
        return "east"
    return "lobby"


def start_mission3_kill_order_checkpoint(preserve_timer=False):
    """Restart Mission 3 at the Kill Order ground floor (Phase 5).

    Skips interrogation / breakout / comms / archives entirely: grants the
    Vostral flag and loadout, then enters the phase for real.
    """
    global _dialogue_beats, _dialogue_index, _dialogue_timer, _dialogue_choice, _dialogue_tone
    global _dialogue_char_idx, _dialogue_slide
    global _monitor_on, _breach_flash, _light_flicker, _volkov_breach_t, _boots_approach_t, _post_type_hold

    start_mission3(preserve_timer=preserve_timer)

    STATE.mission3_stage = STAGE_ARCHIVES          # momentarily, for the handoff
    STATE.mission3_breakout_checkpoint_reached = True
    STATE.mission3_comms_checkpoint_reached = True
    STATE.mission3_archives_checkpoint_reached = True
    STATE.mission3_cell_block_cleared = True
    STATE.mission3_cell_open = True
    STATE.mission3_chair_broken = True
    STATE.m3_vostral_acquired = True
    STATE.mission3_sidearm_acquired = True
    # Loadout mirror of the archives checkpoint (interrogation left the
    # player restrained/disarmed - the KO phase starts armed).
    STATE.player_disarmed = False
    STATE.mission3_weapon = "k9_smg"
    STATE.current_weapon = "k9_smg"
    STATE.k9_unlocked = True
    STATE.k9_ammo_in_mag = STATE.k9_mag_size
    STATE.k9_spare_mags = 2
    STATE.k9_shot_cooldown = 0
    STATE.mission3_doorway_blocked = False
    STATE.mission3_crafting_active = False
    STATE.m3_volkov_run_active = False
    STATE.m3_volkov_run_done = True
    STATE.m3_volkov_ally_active = True
    STATE.m3_volkov_ally_hp = 150
    _start_kill_order_phase(force=True)
    if STATE.player is not None:
        STATE.player.hp = STATE.player.max_hp
        STATE.player_dead = False
        STATE.death_timer = 0
        STATE.death_anim_phase = 0
        STATE.death_anim_timer = 0
        STATE.request_death_screen = False
    return STATE.player


def _m3_exit_requirements():
    """Return (ready, reason) for leaving the cell-block slice.

    The service exit should not fire just because the player reaches the tile.
    It now requires the authored slice beats: Volkov has drawn attention away,
    guards are spawned/cleared, and the armory K-9 has been taken.
    """
    if not getattr(STATE, "m3_volkov_run_done", False):
        return False, "Wait for Volkov to clear out."
    if not getattr(STATE, "mission3_guards_spawned", False):
        return False, "Secure the cell block first."
    guards_left = len(getattr(STATE, "enemies", []))
    if guards_left > 0:
        return False, f"{guards_left} guard(s) left."
    if not getattr(STATE, "k9_unlocked", False):
        return False, "Take the K-9 in the armory."
    return True, "Service exit clear."


def _m3_check_volkov_ammo_resupply():
    """Dynamic in-world resupply: Volkov throws magazines when the player
    runs completely dry (Comms Wing + Archives).

    No cutscene. Magazines fly through the world and land near the player.
    """
    if not getattr(STATE, "m3_volkov_ally_active", False):
        return
    if getattr(STATE, "m3_volkov_ally_hp", 0) <= 0:
        return
    if len(getattr(STATE, "m3_volkov_mags", [])) > 0:
        return  # already throwing

    weapon = getattr(STATE, "current_weapon", "pistol")
    if weapon == "k9_smg":
        empty = STATE.k9_ammo_in_mag <= 0 and STATE.k9_spare_mags <= 0
    elif weapon == "pistol":
        empty = STATE.ammo_in_mag <= 0 and STATE.spare_mags <= 0
    else:
        empty = False

    if empty:
        _trigger_volkov_mags_throw()


def _update_volkov_mags():
    """Update flying magazines. When they land near the player, grant ammo."""
    if not getattr(STATE, "m3_volkov_mags", None):
        return
    if not STATE.player:
        return

    px, py = STATE.player.rect.center
    remaining = []

    for mag in STATE.m3_volkov_mags:
        if mag.get("caught"):
            continue

        # Authored ballistic arc rather than frame-by-frame gravity.  The old
        # values used very low horizontal speed with extremely strong gravity,
        # so the mags dropped beside Volkov like heavy blocks.  Interpolating
        # over a fixed flight time guarantees a clean throw toward Biribel while
        # the parabolic lift still makes it look physical.
        mag["age"] = mag.get("age", 0) + 1
        mag["life"] -= 1
        delay = mag.get("delay", 0)
        flight_age = max(0, mag["age"] - delay)
        duration = max(1, mag.get("duration", 42))

        # Let the catch point follow Biribel gently during flight. This avoids
        # misses when the player keeps moving without making the mag visibly
        # home or snap sideways.
        if flight_age > 0:
            follow = 0.075
            mag["target_x"] += (px - mag["target_x"]) * follow
            mag["target_y"] += (py - mag["target_y"]) * follow

        t = max(0.0, min(1.0, flight_age / duration))
        eased = t * t * (3.0 - 2.0 * t)  # smooth launch and catch
        old_x, old_y = mag["x"], mag["y"]
        base_x = mag["start_x"] + (mag["target_x"] - mag["start_x"]) * eased
        base_y = mag["start_y"] + (mag["target_y"] - mag["start_y"]) * eased
        arc = math.sin(math.pi * t) * mag.get("arc_height", 76.0)
        mag["x"] = base_x
        mag["y"] = base_y - arc
        mag["vx"] = mag["x"] - old_x
        mag["vy"] = mag["y"] - old_y
        mag["rot"] = mag.get("rot", 0.0) + 0.24

        # Resolve exactly at the catch point. Life expiry remains a safety net.
        if (flight_age >= duration) or mag["life"] <= 0:
            # Grant the mag
            if getattr(STATE, "current_weapon", "") == "k9_smg":
                STATE.k9_spare_mags = getattr(STATE, "k9_spare_mags", 0) + 1
            else:
                STATE.spare_mags = getattr(STATE, "spare_mags", 0) + 1

            # Floating text
            STATE.floating_texts.append([
                mag["x"], mag["y"] - 18,
                "+1 MAG",
                (140, 220, 160),
                55,
            ])

            try:
                audio.play("pickup", volume=0.65)
            except Exception:
                pass

            mag["caught"] = True
            continue

        remaining.append(mag)

    STATE.m3_volkov_mags = remaining

    # When all mags are caught, clear the list
    if not remaining:
        STATE.m3_volkov_mags = []


def _trigger_volkov_mags_throw():
    """Volkov throws two magazines in-world when the player is dry.

    Magazines now spawn directly from Volkov's current position so the throw
    is clearly visible.
    """
    if not STATE.player:
        return
    if len(getattr(STATE, "m3_volkov_mags", [])) > 0:
        return

    px, py = STATE.player.rect.center

    # Use Volkov's actual position if he's active as an ally
    if getattr(STATE, "m3_volkov_ally_active", False):
        volkov_x = getattr(STATE, "m3_volkov_ally_x", px - 80)
        volkov_y = getattr(STATE, "m3_volkov_ally_y", py - 30)
    else:
        volkov_x = px - 80
        volkov_y = py - 30

    # Two magazines with different trajectories (clear arc)
    mags = []
    for i, (ox, oy) in enumerate([(-18, -12), (22, -9)]):
        target_x = px + _rng_legacy.randint(-22, 22)
        target_y = py + _rng_legacy.randint(-15, 15)

        # Fixed-time ballistic throw. The second mag leaves a few frames later
        # and takes a slightly different/lower arc so the pair is readable.
        start_x = volkov_x + ox
        start_y = volkov_y + oy
        duration = 40 + i * 5
        mag = {
            "x": start_x,
            "y": start_y,
            "target_x": target_x,
            "target_y": target_y,
            "life": 100,
            "duration": duration,
            "delay": i * 6,
            "arc_height": 82.0 - i * 12.0,
            "vx": (target_x - start_x) / duration,
            "vy": (target_y - start_y) / duration,
            "rot": _rng_legacy.uniform(-1.1, 1.1),
            "age": 0,
            "caught": False,
            "start_x": start_x,
            "start_y": start_y,
        }
        mags.append(mag)

    STATE.m3_volkov_mags = mags

    # Small particle burst at throw origin
    try:
        effects.burst(volkov_x, volkov_y, (255, 200, 80), count=8, speed_mul=0.8, life_min=12, life_max=22)
    except Exception:
        pass

    # Radio line from Volkov (stage-aware, rotating).
    STATE.m3_volkov_mags_thrown_count = getattr(STATE, "m3_volkov_mags_thrown_count", 0) + 1
    stage = getattr(STATE, "mission3_stage", "")
    n = STATE.m3_volkov_mags_thrown_count
    if stage == STAGE_ARCHIVES:
        lines = (
            "VOLKOV: Dry? Catch, don't make me regret this!",
            "VOLKOV: Mag! Keep pushing the stacks!",
            "VOLKOV: Last spare. Make them count!",
        )
    else:
        lines = (
            "VOLKOV: Out?! Catch!",
            "VOLKOV: Mag up, move!",
            "VOLKOV: Stay lethal!",
        )
    line = lines[min(n - 1, len(lines) - 1)]
    try:
        from core.interactions import trigger_radio_chatter
        trigger_radio_chatter(line, color=C_VOLKOV, duration=180)
    except Exception:
        pass

    try:
        audio.play("rifle_handle", volume=0.55)
    except Exception:
        pass


def _update_breakout_stage():
    _update_volkov_escape_route()

    # Guards enter the simulation only after the scripted breach/chair-leg
    # sequence is over and the player has actually unlocked the cell doorway.
    if (not getattr(STATE, "mission3_doorway_blocked", False)
            and getattr(STATE, "mission3_weapon", "none") in ("shiv", "sidearm", "k9_smg")):
        _spawn_m3_guards_once()

    if not getattr(STATE, "mission3_breakout_announced", False):
        STATE.mission3_breakout_announced = True
        _radio("VOLKOV: They're awake now. South hall, move.",
               color=C_VOLKOV, duration=420, mark="breakout_announced",
               priority=1)

    weapon = getattr(STATE, "mission3_weapon", "none")
    has_sidearm = getattr(STATE, "mission3_sidearm_acquired", False)
    guards_left = len(STATE.enemies)
    # Once every cell-block guard is dead, remember it so the service-door
    # marker + arrow can show on the minimap regardless of later state.
    if getattr(STATE, "mission3_guards_spawned", False) and guards_left == 0:
        STATE.m3_guards_all_killed = True

    exit_ready, exit_reason = _m3_exit_requirements()
    if weapon == "chair_leg":
        _set_objective("Craft shiv at marked drain.")
    elif not getattr(STATE, "m3_volkov_run_done", False):
        _set_objective("Wait for Volkov to clear out.")
    elif not getattr(STATE, "mission3_guards_spawned", False):
        _set_objective("Secure the cell block.")
    elif guards_left > 0:
        _set_objective(f"Clear hostiles: {guards_left} guard(s) left.")
    elif not getattr(STATE, "k9_unlocked", False):
        _set_objective("Armory: take the K-9 SMG.")
    elif exit_ready:
        _set_objective("Reach the service exit.")
    else:
        _set_objective(exit_reason)

    if STATE.player is not None:
        exit_pos = (_EXIT_TILE_COL * TILE_SIZE + TILE_SIZE // 2,
                    _EXIT_TILE_ROW * TILE_SIZE + TILE_SIZE // 2)
        if _near(exit_pos, radius=TILE_SIZE * 0.6):
            exit_ready, exit_reason = _m3_exit_requirements()
            if exit_ready:
                STATE.mission3_stage = STAGE_VENT_CUTSCENE
                STATE.mission_phase = "m3_service_transition"
                STATE.mission3_transition_kind = "service"
                STATE.request_service_transition_cutscene = True
            else:
                _set_objective(exit_reason)
                warn_t = getattr(STATE, "m3_exit_block_hint_timer", 0)
                if warn_t <= 0:
                    STATE.m3_exit_block_hint_timer = 75
                    STATE.floating_texts.append([
                        exit_pos[0], exit_pos[1] - 36,
                        exit_reason,
                        (220, 170, 90), 70,
                    ])
        if getattr(STATE, "m3_exit_block_hint_timer", 0) > 0:
            STATE.m3_exit_block_hint_timer -= 1


def _start_comms_phase():
    """Slice 2 → Slice 3 transition: flip STAGE_BREAKOUT → STAGE_COMMS.

    This is the Phase 2 win. The cell-block exit fires, the breakout is
    marked cleared on STATE (so later slices can read it for narrative
    callbacks), and the objective updates to the Phase 3 stub text. The
    actual Vasile re-contact cutscene + comms relay puzzle is Slice 3.
    """
    if getattr(STATE, "mission3_stage", None) == STAGE_COMMS:
        return  # idempotent

    _stop_m3_alarm()

    _build_comms_world()
    STATE.mission3_stage = STAGE_COMMS
    STATE.mission_phase = "m3_comms"
    STATE.mission3_cell_block_cleared = True
    # Comms checkpoint: reaching the Comms Wing is a respawn point AND a full
    # heal, so dying later in the mission doesn't punish the whole breakout.
    STATE.mission3_comms_checkpoint_reached = True
    if STATE.player is not None:
        STATE.player.hp = STATE.player.max_hp
    STATE.mission3_transition_kind = ""
    _set_objective("Restore auxiliary power in Battery Backup.")
    try:
        audio.play("radio_static", volume=0.35)
    except Exception:
        pass
    _radio("VASILE: Relay is dead down here. Restore battery backup, copy auth from Security, then tune the terminal.",
           color=C_VASILE, duration=420, mark="comms_phase_onboarding", priority=1)




def _maybe_trigger_archives_handoff():
    """If the player reaches the Comms Wing east archive E-tile after the
    relay is live, request the archives transition cutscene."""
    if getattr(STATE, "mission3_stage", None) != STAGE_COMMS:
        return
    if not getattr(STATE, "m3_relay_tuned", False):
        return
    if STATE.player is None:
        return
    exit_pos = (
        _ARCHIVE_EXIT_COL * TILE_SIZE + TILE_SIZE // 2,
        _ARCHIVE_EXIT_ROW * TILE_SIZE + TILE_SIZE // 2,
    )
    if _near(exit_pos, radius=TILE_SIZE * 0.85):
        # Prebuild the real Archives world before handing control to the cutscene.
        # The transition renderer then uses the same map, props, characters, and
        # enemy sprites as gameplay instead of a disconnected illustration.
        _build_archives_world()
        STATE.m3_archives_transition_prebuilt = True
        STATE.mission3_stage = STAGE_ARCHIVES_TRANSITION
        STATE.mission_phase = "m3_archives_transition"
        STATE.request_archives_transition_cutscene = True


def _start_archives_phase():
    """Comms → Archives transition: load the Archives map and Phase 4 state."""
    if getattr(STATE, "mission3_stage", None) == STAGE_ARCHIVES:
        return  # idempotent

    _stop_m3_alarm()
    # Normal entry prebuilds the Archives for the seamless in-engine cutscene.
    # Checkpoint/debug entry can still call this function without a prebuilt map.
    if not getattr(STATE, "m3_archives_transition_prebuilt", False):
        _build_archives_world()
    STATE.m3_archives_transition_prebuilt = False
    STATE.mission3_stage = STAGE_ARCHIVES
    STATE.mission_phase = "m3_archives"
    STATE.mission3_archives_checkpoint_reached = True
    if STATE.player is not None:
        STATE.player.hp = STATE.player.max_hp
    STATE.mission3_transition_kind = ""
    _set_objective("With Volkov, clear the atrium, then find Maru's dead-drop (NW).")
    try:
        audio.play("radio_static", volume=0.35)
        audio.play("terminal_glitch", volume=0.30)
    except Exception:
        pass
    _radio(
        "VOLKOV: I'm with you. Stacks west, vault northeast. Don't dry the mag, I'll toss you one.",
        color=C_VOLKOV, duration=360, mark="archives_entered_volkov",
    )
    _radio(
        "VASILE: Maru's dead-drop is in the northwest clerk office. Clear a path.",
        color=C_VASILE, duration=340, mark="archives_entered",
    )


def _start_broadcast_phase():
    """Kill Order -> Broadcast transition: enter the Phase 6 combat gauntlet.

    Builds the Broadcast Wing studio floor, resets the 22:00 timer and wave
    state, heals, and sets the Slice 6 objective + onboarding radio.
    """
    if getattr(STATE, "mission3_stage", None) == STAGE_BROADCAST \
            and getattr(STATE, "m3_bcast_world_built", False) \
            and getattr(STATE, "m3_bcast_time_left", None) is not None:
        return  # idempotent - runtime already initialized

    _stop_m3_alarm()

    from missions.m3.world import _build_broadcast_world
    _build_broadcast_world()

    STATE.mission3_stage = STAGE_BROADCAST
    STATE.mission_phase = "m3_broadcast"
    STATE.mission3_broadcast_checkpoint_reached = True
    STATE.m3_bcast_time_left = BCAST_TIME_LIMIT
    STATE.m3_bcast_wave = 0
    STATE.m3_bcast_upload_progress = 0.0
    STATE.m3_bcast_upload_active = False
    STATE.m3_bcast_pc_ready = False
    STATE.m3_bcast_failed = False
    STATE.mission3_transition_kind = ""
    if STATE.player is not None:
        STATE.player.hp = STATE.player.max_hp
    _set_objective("Hold the studio. Get the file on air.")
    try:
        audio.play("radio_static", volume=0.35)
    except Exception:
        pass
    _radio("VASILE: Doors are live. Whatever you choose, fast. The address won't wait.",
           color=C_VASILE, duration=360, mark="broadcast_entered", priority=1)
    _radio("VOLKOV: I'm on your six. You take the desk, I'll hold the floor.",
           color=C_VOLKOV, duration=320, mark="broadcast_entered_volkov")


def _update_broadcast_stage():
    """Slice 6 per-frame update: timer, waves, control-room assault, PC upload."""
    if getattr(STATE, "m3_bcast_failed", False):
        return

    STATE.m3_bcast_time_left = max(0, STATE.m3_bcast_time_left - 1)

    if STATE.m3_bcast_time_left <= 0:
        _fail_broadcast_timeout()
        return

    from missions.m3.world import _bcast_pc_pos
    from missions.m3.systems import _spawn_bcast_wave

    px, py = STATE.player.rect.centerx, STATE.player.rect.centery

    wave = STATE.m3_bcast_wave
    enemies_alive = len(STATE.enemies)

    if wave == 0:
        if py > 6 * TILE_SIZE:
            _spawn_bcast_wave(1)
            STATE.m3_bcast_wave = 1
            _set_objective("Clear the cable corridor.")
    elif wave == 1:
        if enemies_alive == 0:
            _spawn_bcast_wave(2)
            STATE.m3_bcast_wave = 2
            _set_objective("Breach the studio gate.")
    elif wave == 2:
        gate_open = all(
            not d.locked for d in STATE.doors
            if _m3d(d).bcast_gate
        )
        if not gate_open and enemies_alive == 0:
            for d in STATE.doors:
                if _m3d(d).bcast_gate:
                    d.locked = False
                    d.target_open = True
            _set_objective("They know you're in the studio. Hold the floor.")
            STATE.m3_bcast_wave = 3
    elif wave == 3:
        # The booth protectors are already awake and tracking her.
        _spawn_bcast_wave(3)
        STATE.m3_bcast_wave = 4
        _set_objective("Clear the booth. Get to the station PC.")
    elif wave == 4:
        if enemies_alive == 0:
            STATE.m3_bcast_pc_ready = True
            _set_objective("Use the station PC. Upload the file.")

    # Station PC: [E] boots the broadcast OS (replaces the hold-E desk).
    if getattr(STATE, "m3_bcast_pc_ready", False):
        from ui import upload_os  # lazy: ui package
        if not upload_os.is_upload_os_active():
            pcx, pcy = _bcast_pc_pos()
            if math.hypot(px - pcx, py - pcy) < 110:
                _set_objective("Press [E] at the station PC.")
                if pygame.key.get_pressed()[pygame.K_e]:
                    upload_os.start_upload_os(profile=upload_os.PROFILE_M3)


def _fail_broadcast_timeout():
    """22:00 reached: play the fail cutscene, then retry the slice.

    The request flag is consumed by app.py, which plays
    ``broadcast_fail_shots`` and routes the cutscene's end back here through
    ``_retry_broadcast_slice()``. The stage stays STAGE_BROADCAST and
    ``_update_broadcast_stage`` early-returns while ``m3_bcast_failed`` is
    set, so the wing is frozen until the retry lands - the player is never
    left in a half-failed slice.
    """
    STATE.m3_bcast_failed = True
    STATE.m3_bcast_upload_active = False
    _stop_m3_alarm()
    _set_objective("The address has begun. The studio is lost.")
    try:
        audio.play("terminal_glitch", volume=0.55)
    except Exception:
        pass
    STATE.request_mission3_fail_cutscene = True


def _retry_broadcast_slice():
    """Retry Slice 6 from the start: rebuild broadcast world, reset timer."""
    STATE.m3_bcast_failed = False
    STATE.m3_bcast_time_left = BCAST_TIME_LIMIT
    STATE.m3_bcast_wave = 0
    STATE.m3_bcast_upload_progress = 0.0
    STATE.m3_bcast_upload_active = False
    STATE.m3_bcast_pc_ready = False
    STATE.request_mission3_fail_cutscene = False

    from missions.m3.world import _build_broadcast_world
    _build_broadcast_world()

    if STATE.player is not None:
        STATE.player.hp = STATE.player.max_hp
    # Refill from the checkpoint loadout: the retry is a fresh attempt, so the
    # K-9 comes back full rather than inheriting the dead run's mag count.
    # (Volkov is re-anchored at full HP by _build_broadcast_world itself.)
    if getattr(STATE, "k9_unlocked", False):
        STATE.k9_ammo_in_mag = STATE.k9_mag_size
        STATE.k9_spare_mags = max(2, getattr(STATE, "k9_spare_mags", 0))
    _set_objective("Hold the studio. Get the file on air.")
    _radio("VASILE: Feed's back on your side. Clock is live again - move.",
           color=C_VASILE, duration=300, mark="broadcast_retry", priority=1)


def start_mission3_broadcast_checkpoint(preserve_timer=False):
    """Restart Mission 3 at the Broadcast Wing (Phase 6).

    Skips interrogation / breakout / comms / archives / kill order entirely:
    grants the Vostral flag and loadout, then enters the phase for real.

    Doubles as the death checkpoint for Phase 6 (see
    ``game_core.restart_current_mission``), so ``preserve_timer`` matches the
    other M3 checkpoints: a death restart resets the mission clock, a dev jump
    passes whatever the caller wants.
    """
    global _dialogue_beats, _dialogue_index, _dialogue_timer, _dialogue_choice, _dialogue_tone
    global _dialogue_char_idx, _dialogue_slide
    global _monitor_on, _breach_flash, _light_flicker, _volkov_breach_t, _boots_approach_t, _post_type_hold

    start_mission3(preserve_timer=preserve_timer)

    # NOTE: do NOT set mission3_stage here - _start_broadcast_phase() owns
    # the stage assignment and its idempotence guard reads it. Pre-setting
    # STAGE_BROADCAST trips the guard, skipping the timer/wave/upload init
    # and crashing _update_broadcast_stage on the first tick.
    STATE.mission3_breakout_checkpoint_reached = True
    STATE.mission3_comms_checkpoint_reached = True
    STATE.mission3_archives_checkpoint_reached = True
    STATE.mission3_kill_order_checkpoint_reached = True
    STATE.mission3_cell_block_cleared = True
    STATE.mission3_cell_open = True
    STATE.mission3_chair_broken = True
    STATE.m3_vostral_acquired = True
    STATE.mission3_sidearm_acquired = True
    STATE.player_disarmed = False
    STATE.mission3_weapon = "k9_smg"
    STATE.current_weapon = "k9_smg"
    STATE.k9_unlocked = True
    STATE.k9_ammo_in_mag = STATE.k9_mag_size
    STATE.k9_spare_mags = 2
    STATE.k9_shot_cooldown = 0
    STATE.mission3_doorway_blocked = False
    STATE.mission3_crafting_active = False
    STATE.m3_volkov_run_active = False
    STATE.m3_volkov_run_done = True
    STATE.m3_volkov_ally_active = False

    _start_broadcast_phase()
    if STATE.player is not None:
        STATE.player.hp = STATE.player.max_hp
        STATE.player_dead = False
        STATE.death_timer = 0
        STATE.death_anim_phase = 0


def start_mission3_upload_checkpoint(open_terminal=True):
    """Dev jump: land at the Broadcast Wing station PC, ready to upload.

    Builds the slice via start_mission3_broadcast_checkpoint(), then skips
    straight past the waves: the studio is clear, the PC is flagged ready, and
    Biribel stands in the vault. With ``open_terminal`` the M3 upload OS is
    booted immediately, so the PC session can be worked on without replaying
    the corridor and gate first.

    Wired to ``python acaristan.py --dev-mission3-upload`` (aliases
    ``--m3-upload``) and to the ``--jump m3-upload`` registry target.
    """
    start_mission3_broadcast_checkpoint()

    from missions.m3.world import _bcast_pc_pos

    # Pretend the booth wave is already cleared.
    STATE.enemies = []
    STATE.m3_bcast_wave = 4
    STATE.m3_bcast_pc_ready = True
    if STATE.player is not None:
        STATE.player.hp = STATE.player.max_hp
        STATE.player.rect.center = _bcast_pc_pos()
    _set_objective("Use the station PC. Upload the file.")

    if open_terminal:
        from ui import upload_os  # lazy: ui package
        upload_os.start_upload_os(profile=upload_os.PROFILE_M3)
        _set_objective("Upload the Vostral on the live feed.")
    return True


def _maru_terminal_pos():
    return (
        _MARU_TERMINAL_COL * TILE_SIZE + TILE_SIZE // 2,
        _MARU_TERMINAL_ROW * TILE_SIZE + TILE_SIZE // 2,
    )


def _vostral_file_pos():
    return (
        _VOSTRAL_FILE_COL * TILE_SIZE + TILE_SIZE // 2,
        _VOSTRAL_FILE_ROW * TILE_SIZE + TILE_SIZE // 2,
    )


def _archives_exit_pos():
    return (
        _ARCHIVES_EXIT_COL * TILE_SIZE + TILE_SIZE // 2,
        _ARCHIVES_EXIT_ROW * TILE_SIZE + TILE_SIZE // 2,
    )



def _archives_nav_target():
    """World position the player should head to next, or None."""
    if getattr(STATE, "mission3_stage", None) not in (STAGE_ARCHIVES, STAGE_KILL_ORDER):
        return None
    if getattr(STATE, "m3_maru_contact_active", False):
        return None
    # Only guide once the wing is clear of fightable hostiles.
    if len(_archives_reachable_hostiles()) > 0:
        return None

    if getattr(STATE, "m3_vostral_acquired", False):
        return _archives_exit_pos()
    if not getattr(STATE, "m3_maru_contacted", False):
        return _maru_terminal_pos()
    # Vault unlocked - guide to the file pedestal.
    return _vostral_file_pos()


def _draw_archives_nav_arrow(cam_x, cam_y):
    """Floating arrow above Biribel pointing toward the next objective.

    Hides when the player is close enough that the interact prompt takes over,
    so the arrow never sits on top of desks/plaques/prompts.
    """
    if not STATE.player or STATE.player_dead:
        return
    target = _archives_nav_target()
    if target is None:
        return
    px, py = STATE.player.rect.centerx, STATE.player.rect.centery
    tx, ty = target
    dx, dy = tx - px, ty - py
    dist = math.hypot(dx, dy)
    # Interact range owns the last stretch - hide arrow to avoid clutter.
    if dist < 140:
        return
    # Inside the Vostral vault room while hunting the file: no arrow (room is small).
    pc, pr = px // TILE_SIZE, py // TILE_SIZE
    if target == _vostral_file_pos() and 36 <= pc <= 46 and 4 <= pr <= 14:
        return

    angle = math.atan2(dy, dx)
    bob = math.sin(_now_ms() * 0.008) * 3
    sx = int(px - cam_x)
    # High above the sprite so it clears Volkov labels / furniture.
    sy = int(py - cam_y - 58 + bob)
    # Clamp so the arrow itself never draws under the top HUD.
    sy = max(64, min(HEIGHT - 90, sy))
    sx = max(24, min(WIDTH - 24, sx))

    col = (255, 220, 90)
    tip_len = 16
    tip = (sx + math.cos(angle) * tip_len, sy + math.sin(angle) * tip_len)
    left = (sx + math.cos(angle + 2.45) * 11, sy + math.sin(angle + 2.45) * 11)
    right = (sx + math.cos(angle - 2.45) * 11, sy + math.sin(angle - 2.45) * 11)
    pygame.draw.polygon(screen, (0, 0, 0),
                        [(tip[0] + 1, tip[1] + 1), (left[0] + 1, left[1] + 1),
                         (right[0] + 1, right[1] + 1)])
    pygame.draw.polygon(screen, col, [tip, left, right])

    # Distance plate ABOVE the arrow (not on the cork board / desk).
    meters = max(1, int(dist / 8))
    tag = font_terminal_small.render(_T("flow.meters_m", meters=meters), True, col)
    tw, th = tag.get_width() + 8, tag.get_height() + 4
    txp = max(4, min(WIDTH - tw - 4, sx - tw // 2))
    typ = max(54, sy - th - 10)
    plate = pygame.Surface((tw, th), pygame.SRCALPHA)
    pygame.draw.rect(plate, (0, 0, 0, 200), plate.get_rect(), border_radius=2)
    pygame.draw.rect(plate, (*col, 180), plate.get_rect(), 1, border_radius=2)
    screen.blit(plate, (txp, typ))
    screen.blit(tag, (txp + 4, typ + 2))


def _archives_reachable_hostiles():
    """Enemies the player can fight right now (not trapped behind locked doors)."""
    locked_vault = not getattr(STATE, "m3_maru_contacted", False)
    locked_exit = not getattr(STATE, "m3_vostral_acquired", False)
    out = []
    for e in getattr(STATE, "enemies", []):
        c = e.rect.centerx // TILE_SIZE
        r = e.rect.centery // TILE_SIZE
        # Inside sealed Vostral vault chamber.
        if locked_vault and c >= 37 and 5 <= r <= 13:
            continue
        # Inside sealed north stairwell.
        if locked_exit and 23 <= c <= 27 and 3 <= r <= 5:
            continue
        out.append(e)
    return out


def _start_maru_contact():
    """Begin the Maru dead-drop contact sequence (locks movement briefly)."""
    if getattr(STATE, "m3_maru_contacted", False):
        return
    if getattr(STATE, "m3_maru_contact_active", False):
        return
    hostiles = _archives_reachable_hostiles()
    if len(hostiles) > 0:
        mx, my = _maru_terminal_pos()
        STATE.floating_texts.append([
            mx, my - 34, "CLEAR HOSTILES FIRST", (220, 150, 90), 90])
        _set_objective(
            f"Clear Archives hostiles ({len(hostiles)}) before contacting Maru.")
        return

    STATE.m3_maru_contact_active = True
    STATE.m3_maru_contact_timer = 0
    _set_objective("Hold position - receiving Maru's ghost-channel...")
    try:
        audio.play("terminal_glitch", volume=0.50)
        audio.play("radio_static", volume=0.40)
        audio.play("type_tick", volume=0.18)
    except Exception:
        pass


def _update_maru_contact():
    """Advance the Maru contact cinematic timer; unlock vault on completion."""
    if not getattr(STATE, "m3_maru_contact_active", False):
        return
    STATE.m3_maru_contact_timer = getattr(STATE, "m3_maru_contact_timer", 0) + 1
    t = STATE.m3_maru_contact_timer
    duration = int(getattr(STATE, "m3_maru_contact_duration", 960) or 960)

    if t in (50, 120, 200, 300, 420, 540, 680, 820):
        try:
            audio.play("type_tick", volume=0.12)
        except Exception:
            pass

    if t >= duration:
        STATE.m3_maru_contact_active = False
        STATE.m3_maru_contacted = True
        STATE.m3_maru_contact_timer = duration
        # Unlock the Vostral vault doors.
        for door in getattr(STATE, "doors", []):
            if _m3d(door).vostral_vault:
                door.locked = False
                door.target_open = True
                door.anim_progress = 1.0
                door.collision_rect = None
                door.manual_timer = 400
        _set_objective("Vault unlocked (NE). Walk in and [E] Take the Vostral file.")
        # Waypoint ping on the vault doors.
        for door in getattr(STATE, "doors", []):
            if _m3d(door).vostral_vault:
                STATE.floating_texts.append([
                    door.rect.centerx, door.rect.centery - 36,
                    "VAULT OPEN", (180, 140, 220), 140])
                break
        try:
            audio.play("terminal_glitch", volume=0.55)
            audio.play("door_break", volume=0.30)
        except Exception:
            pass
        _radio(
            "MARU: The only unforged copy is under glass in the cold vault. Take it. "
            "Then the north stairwell, Balaceanu's sweep is already moving.",
            color=C_MARU, duration=480, mark="maru_contact_done",
        )
        mx, my = _maru_terminal_pos()
        STATE.floating_texts.append([
            mx, my - 40, "VAULT AUTHORIZATION GRANTED", (180, 140, 220), 140])


def _acquire_vostral_file():
    """Player takes the Vostral dossier from the vault pedestal."""
    if getattr(STATE, "m3_vostral_acquired", False):
        return
    if not getattr(STATE, "m3_maru_contacted", False):
        vx, vy = _vostral_file_pos()
        STATE.floating_texts.append([
            vx, vy - 34, "VAULT SEALED, CONTACT MARU", (220, 165, 80), 100])
        _set_objective("Vault sealed. NW clerk office, contact Maru first.")
        return
    hostiles = _archives_reachable_hostiles()
    if len(hostiles) > 0:
        vx, vy = _vostral_file_pos()
        STATE.floating_texts.append([
            vx, vy - 34, "CLEAR HOSTILES FIRST", (220, 150, 90), 90])
        _set_objective(f"Clear {len(hostiles)} hostile(s), then take the Vostral.")
        return

    STATE.m3_vostral_acquired = True
    STATE.mission3_evidence_uploaded = False  # file held, not yet broadcast
    STATE.request_vostral_pickup_cutscene = True
    # Open the east Kill Order exit.
    for door in getattr(STATE, "doors", []):
        if _m3d(door).kill_order_exit:
            door.locked = False
            door.target_open = True
            door.manual_timer = 200
    vx, vy = _vostral_file_pos()
    STATE.floating_texts.append([
        vx, vy - 42, "VOSTRAL FILE ACQUIRED", (200, 230, 160), 150])
    try:
        audio.play("pickup", volume=0.55)
        audio.play("terminal_glitch", volume=0.35)
    except Exception:
        pass
    _set_objective("Vostral secured. North stairwell, exit before the sweep.")
    _radio(
        "VASILE: Confirmed, Vostral is in your hands. North stairwell. Move.",
        color=C_VASILE, duration=360, mark="vostral_acquired",
    )
    _radio(
        "VOLKOV: I've got your back to the door. Go.",
        color=C_VOLKOV, duration=260, mark="vostral_acquired_volkov",
    )
    _radio(
        "MARU: They will burn the wing when they realize. Don't look back.",
        color=C_MARU, duration=320, mark="maru_exit_warning",
    )


def _update_archives_stage():
    """Phase 4 runtime: objectives, Maru contact, file pickup, north exit."""
    STATE.m3_archives_ambience_timer = getattr(
        STATE, "m3_archives_ambience_timer", 0) + 1
    _update_maru_contact()

    guards_left = len(_archives_reachable_hostiles())
    total_left = len(getattr(STATE, "enemies", []))
    if total_left == 0:
        STATE.m3_archives_cleared = True

    volkov_up = (
        getattr(STATE, "m3_volkov_ally_active", False)
        and getattr(STATE, "m3_volkov_ally_hp", 0) > 0
    )
    tag = "with Volkov" if volkov_up else "solo"

    if getattr(STATE, "m3_maru_contact_active", False):
        _set_objective("Hold position, receiving Maru's ghost-channel...")
    elif getattr(STATE, "m3_vostral_acquired", False):
        _set_objective(f"Vostral secured ({tag}). North stairwell, exit before the sweep.")
        if STATE.player is not None and _near(_archives_exit_pos(), radius=TILE_SIZE * 0.85):
            if getattr(STATE, "mission3_stage", None) != STAGE_KO_TRANSITION:
                _start_kill_order_phase(prebuild=True)
    elif not getattr(STATE, "m3_maru_contacted", False):
        if guards_left > 0:
            _set_objective(
                f"Clear Archives hostiles ({guards_left}), then NW clerk office ({tag}).")
        else:
            _set_objective(
                "Vault is sealed. NW clerk office, [E] contact Maru to unlock it.")
    else:
        # Vault unlocked after Maru contact.
        if guards_left > 0:
            _set_objective(
                f"Vault unlocked (NE). Clear {guards_left} hostile(s), then [E] Vostral.")
        else:
            _set_objective("Vault unlocked (NE). Walk in and [E] Take the Vostral file.")
