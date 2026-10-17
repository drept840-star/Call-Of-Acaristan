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
import time

import pygame

from core.config import (C_VASILE, audio)
from entities.art_cache import get_blood_decal, get_fullscreen_overlay, get_tinnitus_bar, get_panel_bg
from core.state import STATE
from entities.player import Player, resolve_melee
from entities.enemy_ai import Enemy
from ui.hud import MiniMap, draw_objective_panel, draw_pinned_radio
from core.interactions import trigger_radio_chatter
from entities.weapons import (
    spawn_molotov_fire as _spawn_molotov_fire,
    _wall_blocks_line,
    MOLOTOV_RADIUS,
    MOLOTOV_ENEMY_DAMAGE,
    MOLOTOV_PLAYER_DAMAGE,
    handle_shoot,
)
from fx import effects
from core.camera import update_camera, reset_camera_state, collide_bullet_walls, draw_bullets

from missions.m2 import world as _m2_world  # shared mutable globals (_objective/_radio_marks/_last_keys) live here
from missions.m2.meta import CONTROL_ROOM, IPA_TRUCK_POS, KILLBOX_COVER_POSITIONS, KILLBOX_FLANK_POSITIONS, MISSION2_ID, MISSION2_KEY, MISSION2_TITLE, REGROUP_TARGET_POSITIONS, REQUIRED_INVESTIGATION_CLUES, SAFE_ZONE, SNIPER_FLANK_POS, SNIPER_LOCK_FRAMES, STAGE_EVIDENCE, STAGE_INVESTIGATE, STAGE_TRUCK
from missions.m2.world import MISSION2_MAP, _build_world, _init_scripted_props, _player_pos, _radio, _set_objective, _snap_camera_to
from missions.m2.sniper import _cleanup_sniper_state, _explode_tanker, _spawn_control_cleanup, _spawn_initial_ipa_team, grant_seby_os12
from engine.core import now_ms as _now_ms  # RPE6 B-001 timebase
import game.world as _gw  # RPE6 Phase 5 (D4): mission data lives in components
from missions.m2.components import M2Role as _M2Role


def _m2g(e):
    """Declared M2 data of an enemy (replaces the ad hoc ``e.m2_*`` attributes)."""
    return _gw.ensure(e, _M2Role)


def start_mission2(preserve_timer=False):
    """Called by game_core/acaristan to begin Mission 2 gameplay."""
    STATE.reset()
    STATE.active_mission = MISSION2_KEY
    STATE.active_mission_id = MISSION2_ID
    STATE.active_mission_title = MISSION2_TITLE
    STATE.active_mission_operation = "ROUTE 12, QUIET ON ROUTE 12"
    STATE.active_mission_outcome = "KRAP framed  ·  Evidence transmitted  ·  Comms compromised"
    STATE.active_mission_quote_attr = "Vasile, over broken static:"
    STATE.active_mission_quote = '"No. They framed you first."'
    STATE.show_minimap = True  # was False - caused players to think the minimap was broken in M2
    STATE.minimap = MiniMap(MISSION2_MAP, palette="m2")
    STATE.mission_start_time = STATE.mission_start_time if (preserve_timer and STATE.mission_start_time) else _now_ms()
    STATE.mission_end_time = 0
    STATE.hostiles_killed = 0
    STATE.shots_fired = 0
    STATE.shots_hit = 0
    STATE.request_mission2_ending = False
    STATE.request_death_screen = False
    STATE.player_dead = False
    STATE.death_timer = 0

    STATE.mission2_stage = STAGE_INVESTIGATE
    STATE.mission_phase = "m2_investigate"
    STATE.mission2_timer = 0
    STATE.mission2_events = set()
    STATE.mission2_card = None
    STATE.mission2_comms_cut = False
    STATE.mission2_tanker_exploded = False
    STATE.mission2_countdown = 0
    STATE.mission2_upload_progress = 0.0
    STATE.mission2_upload_started = False
    STATE.mission2_evidence_uploaded = False
    STATE.mission2_camera_focus = None
    STATE.mission2_sniper_traces = []
    STATE.mission2_sniper_lasers = []
    STATE.mission2_abandoned_nest = None
    STATE.mission2_sniper_muzzle_flashes = []
    STATE.mission2_sniper_flash = 0
    STATE.mission2_near_miss_flash = 0
    STATE.mission2_tinnitus_timer = 0
    STATE.mission2_tanker_blast_timer = 0
    STATE.mission2_tanker_shockwave_radius = 0
    STATE.mission2_tanker_shake_decay = 0
    # Aftermath visuals - initialized empty so drawing code can safely
    # getattr them before the blast fires. Populated in _explode_tanker.
    STATE.mission2_tanker_scorch = None
    STATE.mission2_tanker_scorch_cracks = []
    STATE.mission2_tanker_destroyed = False
    STATE.mission2_tanker_debris_field = []
    STATE.mission2_tanker_outer_debris = []
    STATE.mission2_tanker_blast_streaks = []
    STATE.mission2_tanker_asphalt_cracks = []
    STATE.mission2_tanker_spot_fires = []
    STATE.mission2_tanker_wreckage_ribs = []
    STATE.mission2_all_clues_found = False
    STATE.mission2_camera_focus_timer = 0
    STATE.mission2_current_zone = "approach"
    STATE.mission2_post_sniper_phase = ""
    STATE.mission2_post_sniper_timer = 0
    STATE.mission2_grace_timer = 0
    STATE.mission2_sniper_pressure_timer = 0
    STATE.mission2_sniper_pending_timer = 0
    STATE.mission2_sniper_target = None
    STATE.mission2_sniper_suppressed = False
    # Cleanup-team spawn gate for the post-flank "done" phase. Reset on
    # mission restart so the squad can spawn again on a fresh playthrough.
    STATE.mission2_cleanup_team_spawned = False
    # Tanker inspection gate. The player must press [E] at the tanker to
    # discover the hidden detonator before the run-to-shelter phase begins.
    # Resets on mission restart.
    STATE.mission2_tanker_inspected = False
    STATE.mission2_sniper_lock = 0
    STATE.mission2_sniper_lock_max = SNIPER_LOCK_FRAMES
    STATE.mission2_sniper_warned = set()
    STATE.mission2_sniper_lethal_target = None
    STATE.mission2_sniper_kill_flash = 0
    STATE.mission2_sniper_close_execute_done = False
    STATE.mission2_cover_hold = 0
    STATE.mission2_reinforcement_waves = 0
    STATE.mission2_reinforcement_timer = 0
    STATE.mission2_reinforcement_triggered = False
    # Evidence-phase multi-wave reinforcement state. Reset on mission start
    # so a restart doesn't carry stale wave counters from a previous run.
    STATE.mission2_evidence_wave = 0
    STATE.mission2_evidence_wave_timer = 0
    STATE.mission2_evidence_wave_cleared = False
    # Sniper-cutscene removed. Minimal combat state kept below.
    STATE.mission2_input_freeze = 0
    STATE.mission2_radio_muffle_timer = 0
    STATE.mission2_heartbeat_active = False
    STATE.mission2_heartbeat_timer = 0
    # One-shot radio gate - must be reset on mission start so the
    # "tanker manifest - second cargo" line can fire on a fresh playthrough.
    # Previously stayed True across restarts, silencing the line forever.
    STATE.mission2_late_reveal_played = False
    STATE.mission2_hard_black = 0
    STATE.mission2_chromatic_timer = 0
    STATE.mission2_death_callout = None
    # Player try-to-save-Gabi state. Both default False so the
    # acknowledgment line in _m1_regroup_wrong_scan only fires if the
    # player actually pressed E during the attempt window.
    STATE.mission2_tried_to_save = False
    STATE.mission2_tried_to_save_acknowledged = False
    # Sniper cutscene phase state. These were previously only initialized
    # inside _start_sniper_sequence, which meant stale state could leak
    # between cutscene runs and silently change the next opening beat.
    STATE.mission2_sniper_phase = "regroup"
    STATE.mission2_sniper_phase_timer = 0
    STATE.mission2_sniper_events_fired = set()
    STATE.mission2_sniper_origin_revealed = False
    STATE.mission2_sniper_silhouette_flash = 0
    STATE.mission2_camera_snap = None
    STATE.mission2_sniper3d = None          # 3D film object (missions/m2/sniper3d.py)

    STATE.mission2_weapon_pickup_active = False
    STATE.mission2_weapon_pickup_timer = 0
    STATE.mission2_weapon_pickup_ready = False
    STATE.mission2_fade_out = 0
    STATE.mission2_os12_acquired = False
    STATE.request_seby_pickup_cutscene = False
    STATE._m3_pickup_done = False
    STATE._seby_os12_granted = False
    STATE._m3_killbox_started = False
    STATE.player_locked = False

    STATE.os12_unlocked = False
    STATE.os12_ammo_in_mag = 25
    STATE.os12_spare_mags = 2
    STATE.os12_shot_cooldown = 0
    STATE.current_weapon = "pistol"

    STATE.ammo_in_mag = 12
    STATE.mag_size = 12
    STATE.spare_mags = 4
    STATE.player_bottles = 2
    STATE.shot_cooldown = 0
    STATE.is_reloading = False
    STATE.reload_timer = 0
    STATE.melee_active = False
    STATE.melee_timer = 0

    _build_world()
    _init_scripted_props()

    _snap_camera_to(_player_pos())
    STATE.screen_shake = 0  # fresh start must not inherit a previous run's shake
    STATE.mission2_camera_initialized = True  # legacy flag, kept for save compatibility
    STATE.camera_initialized = True  # shared flag: camera is already snapped, don't re-snap in update_camera

    _m2_world._objective = f"Inspect staged evidence markers with [E] (0/{REQUIRED_INVESTIGATION_CLUES})"
    _m2_world._radio_marks = set()
    _m2_world._last_keys = None
    # Skip the investigation-phase intro radio line when starting from a
    # checkpoint or dev jump - it's wrong context for those entry points.
    if not getattr(STATE, "_skip_mission2_intro_radio", False):
        _radio('VASILE: "Start with the obvious lie. Inspect the staged evidence."', mark="start")
    else:
        STATE._skip_mission2_intro_radio = False  # reset the flag
    return STATE.player


def _mark_squad_dead():
    """Mark all KRAP squad actors as dead at their kill-box final positions.

    Used by all post-kill-box skip shortcuts (flank, truck, checkpoint,
    evidence-debug) to ensure the squad renders as corpses after the sniper
    kill-box has killed them. Without this, the squad would visibly be
    standing and alive at the regroup point despite the narrative having
    moved past their deaths.

    Positions match REGROUP_TARGET_POSITIONS (where they died during
    movement_one / movement_two) and the state matches what _kill_actor()
    sets: alive=False, activity="down".

    Note: start_mission2_sniper and start_mission2_after_sniper do NOT call
    this - those shortcuts land BEFORE/DURING the kill-box, so the squad
    is still alive at that point in the narrative.
    """
    STATE.mission2_squad = [
        {"name": "GABI",   "pos": list(REGROUP_TARGET_POSITIONS[0]), "alive": False, "activity": "down", "reaction": "down"},
        {"name": "SEBY",   "pos": list(REGROUP_TARGET_POSITIONS[1]), "alive": False, "activity": "down", "reaction": "down"},
        {"name": "DARIUS", "pos": list(REGROUP_TARGET_POSITIONS[2]), "alive": False, "activity": "down", "reaction": "down"},
    ]
    print(f"[SQUAD] Marked dead at kill-box positions: {[(a['name'], a['alive'], a['activity']) for a in STATE.mission2_squad]}")


def start_mission2_sniper(preserve_timer=False):
    """Start Mission 2 and immediately jump to the sniper cutscene.

    Useful for testing the sniper sequence without the investigation phase.
    Usage: python acaristan.py --m2-sniper
    """
    player = start_mission2(preserve_timer=preserve_timer)
    # Mark all clues as found so the sniper phase triggers on approach.
    for clue in getattr(STATE, "mission2_clues", []):
        clue["done"] = True
        if clue.get("id"):
            STATE.mission2_clues_found.add(clue["id"])
    # Also mark the truck manifest as inspected so the tanker stage is available.
    if getattr(STATE, "mission2_truck_manifest", None):
        STATE.mission2_truck_manifest["done"] = True
    # Set the state as if the flank cutscene has finished: sniper suppressed,
    # cleanup team ready to spawn, stage advanced to combat.
    _cleanup_sniper_state()
    STATE.mission2_post_sniper_phase = "done"
    STATE.mission2_post_sniper_timer = 0
    STATE.mission2_flank_cutscene_timer = 0
    STATE.mission2_flank_cutscene_max = 0
    STATE.player_locked = False
    STATE.mission2_camera_focus = None
    STATE.mission2_camera_focus_timer = 0
    # Move the player near the flank route so they can immediately see the
    # cleanup team and truck without having to walk the whole gantry.
    if player:
        px, py = SNIPER_FLANK_POS
        player.rect.center = (px, py - 20)
        _snap_camera_to((px, py - 20))
    return player


def start_mission2_after_sniper(preserve_timer=False):
    """Start Mission 2 and jump directly to the post-sniper cutscene combat.

    Skips the investigation phase AND the sniper cutscene. The player has
    Seby's OS-12 rifle, is in STAGE_COMBAT / get_cover phase, standing at
    the nearest killbox cover position. The initial IPA team (including
    the sniper) is spawned, so the full kill-box flow plays out from the
    moment you press a movement key.

    Usage: python acaristan.py --m2-after-sniper
    """
    player = start_mission2(preserve_timer=preserve_timer)
    for clue in getattr(STATE, "mission2_clues", []):
        clue["done"] = True
        if clue.get("id"):
            STATE.mission2_clues_found.add(clue["id"])
    grant_seby_os12()
    if player:
        px, py = KILLBOX_COVER_POSITIONS[0]
        player.rect.center = (px, py)
        _snap_camera_to((px, py))
    print("[SKIP] --m2-after-sniper: landed at STAGE_COMBAT / get_cover")
    return player


def start_mission2_flank(preserve_timer=False):
    """Start Mission 2 and jump directly to the flank phase.

    Skips investigation, sniper cutscene, and the entire kill-box fight
    (get_cover → survive → clear). The player has the OS-12, the sniper
    is still alive on the gantry, and the post_sniper_phase is "flank".
    The player is placed right next to the south flank marker so the
    flank cutscene triggers within a second of walking.

    Usage: python acaristan.py --m2-flank
    """
    player = start_mission2(preserve_timer=preserve_timer)
    _mark_squad_dead()  # post-kill-box: squad is dead at regroup positions
    for clue in getattr(STATE, "mission2_clues", []):
        clue["done"] = True
        if clue.get("id"):
            STATE.mission2_clues_found.add(clue["id"])
    grant_seby_os12()
    _spawn_initial_ipa_team()
    STATE.enemies[:] = [
        e for e in STATE.enemies if _m2g(e).sniper
    ]
    STATE.mission2_reinforcement_triggered = True
    STATE.mission2_reinforcement_waves = 3
    STATE.mission2_reinforcement_timer = 0
    STATE.mission2_late_reveal_played = True
    STATE.mission2_post_sniper_phase = "flank"
    STATE.mission2_post_sniper_timer = 0
    STATE.mission_phase = "m2_flank_sniper"
    _set_objective("SNIPER STILL ACTIVE - flank to the orange circle")
    if player:
        fx, fy = KILLBOX_FLANK_POSITIONS[0]
        player.rect.center = (fx, fy + 300)
        _snap_camera_to((fx, fy + 300))
    print("[SKIP] --m2-flank: landed at STAGE_COMBAT / flank phase")
    return player


def start_mission2_truck(preserve_timer=False):
    """Start Mission 2 and jump directly to the truck inspection phase.

    Skips everything up to and including the flank cutscene + cleanup team
    fight. The player has the OS-12 with 2 spare mags (the cleanup-team
    reward), the sniper is suppressed/removed, and the stage is STAGE_TRUCK.
    The player is placed right next to the IPA truck so the manifest
    inspection triggers immediately.

    Usage: python acaristan.py --m2-truck
    """
    player = start_mission2(preserve_timer=preserve_timer)
    _mark_squad_dead()  # post-kill-box: squad is dead at regroup positions
    for clue in getattr(STATE, "mission2_clues", []):
        clue["done"] = True
        if clue.get("id"):
            STATE.mission2_clues_found.add(clue["id"])
    grant_seby_os12()
    _spawn_initial_ipa_team()
    _cleanup_sniper_state()
    STATE.mission2_cleanup_team_spawned = True
    STATE.enemies[:] = []
    STATE.mission2_post_sniper_phase = ""
    STATE.mission2_stage = STAGE_TRUCK
    STATE.mission_phase = "m2_truck"
    _set_objective("Inspect the IPA truck manifest with [E]")
    # OS-12 spare mags are now granted at pickup (exactly 2) - no mid-mission
    # resupply. Scarcity is the design tension that makes the rifle feel earned.
    STATE.mission2_flank_cutscene_timer = 0
    STATE.mission2_camera_focus = None
    STATE.mission2_camera_focus_timer = 0
    STATE.player_locked = False
    if player:
        tx, ty = IPA_TRUCK_POS
        player.rect.center = (tx, ty + 80)
        _snap_camera_to((tx, ty + 80))
    print("[SKIP] --m2-truck: landed at STAGE_TRUCK (+2 OS 12 mags granted)")
    return player


def start_mission2_checkpoint(preserve_timer=False):
    """Start Mission 2 at the evidence-phase checkpoint (post-tanker explosion).

    Called by restart_current_mission() when STATE.mission2_checkpoint_reached
    is True - i.e. the player survived the tanker blast, reached STAGE_EVIDENCE,
    and then died during the cleanup team fight. Instead of restarting the
    entire mission from the intro cutscene, this drops the player back at
    the shelter (SAFE_ZONE) with the evidence phase already active.

    State setup mirrors what the "blast_done" card close does in _close_card():
      - Stage = STAGE_EVIDENCE
      - Player at SAFE_ZONE (the concrete shelter)
      - OS-12 granted with 2 spare mags
      - Sniper suppressed/removed
      - All clues marked as found
      - Cleanup team spawned (wave 1)
      - Persistent fire zones created (via _explode_tanker)
      - Player HP restored to 80 (survived the blast with debris scrape)
      - Checkpoint flag re-set (so subsequent deaths also respawn here)
    """
    player = start_mission2(preserve_timer=preserve_timer)
    # ── CRITICAL: Re-set the checkpoint flag IMMEDIATELY after start_mission2() ──
    # start_mission2() calls STATE.reset(), which clears mission2_checkpoint_reached
    # to False. If we only re-set it at the end of this function (as the original
    # code did) and any intermediate call (grant_seby_os12, _explode_tanker,
    # _spawn_control_cleanup, etc.) throws an exception, the flag is left False.
    # The death-screen fallback handler then calls start_mission2() (NOT the
    # checkpoint variant), which also clears the flag - so the next death
    # restart does a full mission restart instead of a checkpoint respawn, or
    # worse, boots to main menu if the fallback also fails. Setting it here
    # ensures the flag survives any exception in the setup code below.
    STATE.mission2_checkpoint_reached = True
    # Suppress the investigation-phase intro radio line - wrong context for
    # the evidence phase checkpoint. We play a checkpoint-specific line instead.
    STATE._skip_mission2_intro_radio = True
    _mark_squad_dead()  # post-kill-box: squad is dead at regroup positions
    for clue in getattr(STATE, "mission2_clues", []):
        clue["done"] = True
        if clue.get("id"):
            STATE.mission2_clues_found.add(clue["id"])
    grant_seby_os12()
    _spawn_initial_ipa_team()
    _cleanup_sniper_state()
    STATE.enemies[:] = []
    STATE.mission2_post_sniper_phase = ""
    STATE.mission2_stage = STAGE_EVIDENCE
    STATE.mission_phase = "m2_evidence"
    _set_objective("Enter the control building and inspect green evidence terminals")
    # Checkpoint-specific Vasile line - replaces the wrong-context
    # "inspect the staged evidence" intro that start_mission2() would play.
    _radio('VASILE: "You made it. Control building - move. The evidence is inside."',
           color=C_VASILE, mark="checkpoint_respawn")
    # Re-create the persistent fire zones from the tanker explosion so the
    # evidence phase has the same environmental pressure as the first time.
    # _explode_tanker handles the fire zones + scorch + wreckage creation.
    # We call it here to recreate the post-blast state. The player is at the
    # shelter so they survive the "blast" damage check.
    if player:
        player.rect.center = SAFE_ZONE
        player.hp = 80  # post-blast debris scrape HP
    # Re-create the persistent fire zones from the tanker explosion so the
    # evidence phase has the same environmental pressure as the first time.
    # Wrapped in try/except: _explode_tanker() is the most complex call in
    # this function (audio scheduling, particle spawning, fire zone creation,
    # vehicle charring, debris field generation) and is the most likely throw
    # point. If it fails, the checkpoint respawn still works - the player just
    # won't have the persistent fire zones, which is an acceptable degradation
    # compared to losing the checkpoint entirely or booting to main menu.
    try:
        _explode_tanker()
    except Exception as _blast_err:
        import traceback
        traceback.print_exc()
        print(f"[CHECKPOINT] _explode_tanker() failed during checkpoint respawn: {_blast_err}")
        # Still mark the tanker as exploded so downstream code (draw routines,
        # stage updates) treats it as destroyed even if the blast setup was
        # only partially applied.
        STATE.mission2_tanker_exploded = True
        STATE.mission2_tanker_destroyed = True
    # _explode_tanker sets stage to STAGE_BLACKOUT; override back to EVIDENCE.
    STATE.mission2_stage = STAGE_EVIDENCE
    STATE.mission_phase = "m2_evidence"
    STATE.mission2_camera_focus = None
    STATE.mission2_camera_focus_timer = 0
    STATE.mission2_input_freeze = 0
    # Restore HP AFTER _explode_tanker (which deals 20-40 debris damage even
    # at the shelter). The player should start the evidence phase at 80 HP.
    if player:
        player.hp = 80
    # Spawn the cleanup team (wave 1).
    STATE.mission2_events.discard("control_cleanup")  # allow re-spawn
    _spawn_control_cleanup()
    # Belt-and-suspenders re-set of the checkpoint flag. The canonical set
    # is at the top of this function (immediately after start_mission2()),
    # but we re-set here too in case any code path above unexpectedly cleared
    # it - this is the original location of the flag re-set.
    STATE.mission2_checkpoint_reached = True
    STATE.player_locked = False
    if player:
        player.rect.center = SAFE_ZONE
        _snap_camera_to(SAFE_ZONE)
        STATE.screen_shake = 0  # respawn must not inherit the killing blow's shake
    # ── Kill the _explode_tanker() aftermath so the respawn doesn't replay
    # the BLEVE symphony. _explode_tanker() (called above at line 1582)
    # sets a 130-frame white-out flash (gc_flash_timer), screenshake
    # (cleared explicitly above), and ~12 scheduled audio events
    # plus a 480-loop rig_fire_burst. Without this cleanup, the player
    # respawns into a flashbang + 8+ minutes of fire roar.
    # Surgical variant (preserves the checkpoint radio line just queued
    # by _radio() at line 1572): stop only the fire roar loop and clear
    # the scheduled-events list.
    STATE.gc_flash_timer = 0
    STATE.mission2_chromatic_timer = 0
    STATE.mission2_tanker_ripple_timer = 0
    STATE.mission2_tanker_subflash_queue = []
    STATE.mission2_tanker_shake_decay = 0
    try:
        audio.stop("rig_fire_burst")
        audio.scheduled.clear()
    except Exception:
        pass
    print("[CHECKPOINT] Respawned at shelter - evidence phase active")
    return player


def start_mission2_evidence_debug(preserve_timer=False):
    """Start Mission 2 already past the tanker explosion, with all 3 IPA
    cleanup waves pre-cleared. Player can immediately walk around the
    control building picking up the 3 evidence files and upload them.

    Sets up the post-blast narrative state (tanker exploded, comms cut,
    OS-12 granted, all clues found) but DOES NOT call _explode_tanker -
    the burning wreckage + persistent fire zones would clutter the map
    for evidence testing. The tanker is marked "destroyed" so the
    draw routine doesn't render the intact tanker either.

    All 3 evidence waves are marked as spent (wave = 3, cleared = True)
    AND the "control_cleanup" event is added to STATE.mission2_events
    so _spawn_control_cleanup() early-outs even if something else
    triggers it.

    Usage: python acaristan.py --m2-evidence
    """
    player = start_mission2(preserve_timer=preserve_timer)
    # Suppress the investigation-phase intro radio line - wrong context.
    STATE._skip_mission2_intro_radio = True
    _mark_squad_dead()  # post-kill-box: squad is dead at regroup positions
    # Mark all investigation clues as found (investigation phase is over).
    for clue in getattr(STATE, "mission2_clues", []):
        clue["done"] = True
        if clue.get("id"):
            STATE.mission2_clues_found.add(clue["id"])
    # Grant Seby's OS-12 (player survived the killbox + flank + cleanup).
    grant_seby_os12()
    # Initialize IPA team state, then immediately clear it - the player
    # is past all combat.
    _spawn_initial_ipa_team()
    _cleanup_sniper_state()
    STATE.enemies[:] = []
    STATE.mission2_post_sniper_phase = ""
    STATE.mission2_cleanup_team_spawned = True
    # Post-blast narrative state. We mark the tanker as destroyed + comms
    # cut so radio dialogue + draw routines know we're past the explosion,
    # but we DON'T call _explode_tanker - the fire zones + scorch would
    # clutter the map for evidence testing.
    STATE.mission2_tanker_exploded = True
    STATE.mission2_tanker_destroyed = True
    STATE.mission2_comms_cut = True
    STATE.mission2_tanker_inspected = True
    # Skip ALL 3 evidence waves - set wave counter to max + mark cleared.
    # _update_evidence_waves() early-outs when wave >= 3.
    STATE.mission2_evidence_wave = 3
    STATE.mission2_evidence_wave_cleared = True
    STATE.mission2_evidence_wave_timer = 0
    # Mark the cleanup event as fired so _spawn_control_cleanup won't run
    # even if something else triggers it.
    STATE.mission2_events.add("control_cleanup")
    # Activate the evidence stage.
    STATE.mission2_stage = STAGE_EVIDENCE
    STATE.mission_phase = "m2_evidence"
    _set_objective("Inspect green evidence terminals with [E] (0/3)")
    # Brief Vasile line - replaces the wrong-context intro.
    _radio('VASILE: "Cleanup team\'s down. Grab the evidence - three terminals, then upload."',
           color=C_VASILE, mark="debug_evidence_start")
    # Restore player HP - player survived prior combat at full strength.
    if player:
        player.hp = 100
        # Place the player just south of the first evidence marker
        # (DECREE at _tc(55, 23)) so they can immediately walk up and
        # press [E]. The control building entrance is south of the
        # evidence cluster, so this is also the natural approach path.
        first_ev = STATE.mission2_evidence[0] if STATE.mission2_evidence else None
        if first_ev:
            fx, fy = first_ev["pos"]
            player.rect.center = (fx, fy + 80)
            _snap_camera_to((fx, fy + 80))
        else:
            player.rect.center = CONTROL_ROOM
            _snap_camera_to(CONTROL_ROOM)
    # Set checkpoint so subsequent deaths respawn at the evidence phase
    # (via start_mission2_checkpoint). This is the canonical "you
    # reached the evidence phase" respawn point.
    STATE.mission2_checkpoint_reached = True
    STATE.player_locked = False
    STATE.mission2_camera_focus = None
    STATE.mission2_camera_focus_timer = 0
    STATE.mission2_input_freeze = 0
    print("[SKIP] --m2-evidence: landed at STAGE_EVIDENCE (all 3 waves cleared)")
    return player


# ─────────────────────────────────────────────
# Story scripting / interactions
# ─────────────────────────────────────────────
def _clue_count():
    return sum(1 for c in STATE.mission2_clues if c.get("done"))


def _evidence_count():
    return sum(1 for e in STATE.mission2_evidence if e.get("done"))
