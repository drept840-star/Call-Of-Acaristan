"""Central game state singleton.
Everything that used to be a module-level global in game_core.py now lives
on STATE. Every submodule does:
    from core.state import STATE
    STATE.player.hp -= 10
reset() is called by mission.start_mission().
"""
import pygame
class GameState:
    def __init__(self):
        # Delta-time for the current frame (AEGIS standard #1).
        # Default to 1/60 so any code that runs outside the main loop
        # (smoke tests, dev scripts) gets sensible per-frame values.
        # The main loop overwrites this every frame.
        self.dt = 1.0 / 60.0
        # Persistent across missions (NOT reset)
        self.show_minimap = True
        self.minimap = None
        self.rain_drops = []
        self._footstep_timer = 0
        self._walk_footstep_timer = 0
        self._last_explosion_triggers = set()
        self.reset()
    def reset(self):
        """Reset everything that should be fresh at the start of a mission."""
        # ─── Entities ──────────────────────────────────────────────────
        self.player = None
        self.enemies = []
        self.bullets = []
        self.walls = []
        self.doors = []
        self.particles = []
        self.casings = []
        self.pickups = []
        self.desks = []
        self.blood_decals = []
        self.corpses = []  # entities/corpse.py - fallen enemy bodies (topple → bleed → fade)
        self.floating_texts = []
        self.breach_markers = []
        self.breach_spawn_queue = []
        self.breach_spawn_timer = 0
        self.breach_spawn_started = False
        self.bay_door_forced_open = False
        self.rear_door_forced_open = False
        # ─── Camera / FX ──────────────────────────────────────────────
        self.camera_x = 0
        self.camera_y = 0
        self.cam_kick_x = 0.0
        self.cam_kick_y = 0.0
        self.camera_initialized = False  # set True by camera.update_camera on first frame
        self.screen_shake = 0
        # AEGIS Pass F: hit-stop freeze timer (seconds remaining). When > 0,
        # the main loop in acaristan.py skips gc.game_update(keys) for that
        # frame, but still renders - so the player sees the moment of impact
        # frozen on screen. Trigger via effects.hit_stop(seconds); never
        # assign directly (use the max-clamp helper, same discipline as
        # screen_shake). Default 0 = no freeze active.
        self.hit_stop_timer = 0.0
        self.muzzle_flash_timer = 0
        self.gc_flash_timer = 0
        self.crosshair_kick = 0  # frames left of crosshair spread after a shot
        # ─── Combat / inventory ───────────────────────────────────────
        self.ammo_in_mag = 12
        self.mag_size = 12
        self.spare_mags = 3
        self.shot_cooldown = 0
        self.is_reloading = False
        self.reload_timer = 0
        self.melee_active = False
        self.melee_timer = 0
        self.melee_hit_done = False
        # OS 12 assault rifle
        self.current_weapon = "pistol"          # "pistol" or "os12"
        self.os12_unlocked = False              # set True during M2 cutscene
        self.os12_ammo_in_mag = 25
        self.os12_mag_size = 25                 # was 30, then 20 (too weak), now 25 - middle ground
        self.os12_spare_mags = 2                # exactly 2 - no mid-mission resupply, scarcity is design
        self.os12_shot_cooldown = 0             # separate cooldown for full-auto
        # Mission 3 armory reward: K-9 suppressed SMG / PDW.
        self.k9_unlocked = False
        self.k9_ammo_in_mag = 24
        self.k9_mag_size = 24
        self.k9_spare_mags = 2
        self.k9_shot_cooldown = 0
        # Weapon swap animation
        self.weapon_swap_timer = 0              # counts down from weapon_swap_duration
        self.weapon_swap_duration = 24          # total frames (~0.4s @ 60fps)
        self.weapon_swap_pending = None         # target weapon flipped at midpoint
        self.weapon_swap_sound_played = False
        self.player_bottles = 2
        self.thrown_bottles = []
        self.molotov_fires = []
        self.fire_zones = []
        # Disarmed flag - True when the player has no weapon (M3 cell breakout,
        # before picking up a shank/sidearm). weapons.py gates all weapon
        # actions on this. Default False (M1/M2 start armed).
        self.player_disarmed = False
        # ─── Mission 3 crafting ──
        # The chair breaks during the breach; Biribel grabs a chair leg,
        # then whittles it into a shiv on the drain grate. The doorway is
        # blocked until the shiv is crafted (mandatory crafting).
        self.mission3_chair_broken = False
        self.mission3_weapon = "none"        # "none" → "chair_leg" → "shiv"
        self.mission3_chair_break_anim = -1  # -1 = not started, >=0 = frame counter
        self.mission3_crafting_active = False
        self.mission3_crafting_progress = 0.0    # 0.0..1.0
        self.mission3_crafting_accum = 0.0       # accumulated mouse drag px
        self.mission3_crafting_mouse_held = False
        self.mission3_crafting_prev_mx = 0
        self.mission3_crafting_shavings = []     # particle list
        self.mission3_crafting_stroke_dir = 1    # +1=right stroke, -1=left stroke
        self.mission3_crafting_stroke_progress = 0.0  # pixels in current stroke
        self.mission3_crafting_stroke_target = 80.0   # pixels required per stroke
        self.mission3_crafting_strokes_done = 0   # completed strokes
        self.mission3_crafting_strokes_needed = 8  # strokes to complete
        self.mission3_vent_open = False          # vent grate in cell
        self.mission3_doorway_blocked = True     # mandatory lock
        # One-shot guarantee: the first guard killed in M3 while the player
        # still lacks a firearm drops a sidearm (pistol). Decoupled from the
        # hostiles_killed counter so scripted/other kills can't consume it.
        self.mission3_first_pistol_dropped = False
        # NOTE: mission3_sidearm_acquired is deliberately NOT reset here. It is
        # owned by the Mission 3 start paths instead: the comms/archives
        # checkpoints set it True (the player arrives already armed with the
        # K-9), and start_mission3_breakout_checkpoint() sets it False because
        # that respawn hands back only the chair leg.
        #
        # A blanket reset here looks tempting but breaks those checkpoints: they
        # call start_mission3() -> reset() and then rely on the flag reading
        # True, so clearing it makes every restart spawn the player with a K-9
        # that weapons._player_has_firearm() refuses to fire.
        self.mission3_sidearm_acquired = False
        # ─── Mission 3 Black Ledger easter egg ──
        # Keep these in the global reset, not only mission3.start_mission3(),
        # so Mission 1 / Mission 2 cannot inherit a lingering M3 death overlay
        # or custom death-screen state after menu transitions/restarts.
        self.m3_black_ledger_triggered = False
        self.m3_black_ledger_inmate_active = False
        self.m3_black_ledger_inmate = None
        self.m3_black_ledger_intro_timer = 0
        self.m3_black_ledger_death_active = False
        self.m3_black_ledger_death_timer = 0
        # Volkov mags resupply (dynamic, in-world)
        self.m3_volkov_mags = []  # list of {"x":, "y":, "target_x":, "target_y":, "life":, "vx":, "vy":}
        # Volkov Comms Wing A* navigation scratch.
        self.m3_volkov_path = []
        self.m3_volkov_path_timer = 0
        self.m3_volkov_path_goal = None
        self.m3_volkov_stuck_timer = 0
        self.m3_volkov_last_pos = (0.0, 0.0)
        # Mission 3 Comms Wing multi-step objective state.
        self.m3_comms_power_restored = False
        self.m3_comms_auth_acquired = False
        self.m3_comms_ambience_timer = 0
        # ─── Mission flow ─────────────────────────────────────────────
        self.player_dead = False
        self.death_timer = 0
        self.request_death_screen = False
        # ── Mission 2 checkpoint ──
        # Set to True when the player survives the tanker explosion and
        # transitions to STAGE_EVIDENCE. When the player dies during the
        # evidence phase (or upload/exfil), restart_current_mission() checks
        # this flag and calls start_mission2_checkpoint() instead of
        # start_mission2() - so the player respawns at the shelter with
        # the evidence phase already active, instead of restarting the
        # entire mission from the intro cutscene.
        self.mission2_checkpoint_reached = False
        # ── Evidence completion cinematic (Option E) ──
        # When the player reads the 3rd evidence item, a 5-second cinematic
        # plays before the upload objective appears. These fields drive it:
        #   - mission2_evidence_cinematic_active: gate flag
        #   - mission2_evidence_cinematic_timer: frames since start (0-300)
        #   - mission2_evidence_cinematic_shot: current shot index (0-3)
        # The cinematic is driven in mission2._update_evidence_cinematic()
        # and drawn in mission2._draw_evidence_cinematic().
        self.mission2_evidence_cinematic_active = False
        self.mission2_evidence_cinematic_timer = 0
        self.mission2_evidence_cinematic_shot = 0
        self.mission2_evidence_cinematic_flash = 0  # white flash alpha 0-255
        self.mission2_evidence_cinematic_grace = 0  # post-cinematic enemy freeze (frames)
        # ── Mission 3 checkpoint ──
        # Once Volkov's breach has fully handed control to the breakout gameplay,
        # Mission 3 restarts should respawn at gameplay with the chair leg
        # instead of replaying the intro/interrogation/breach/chair-break cutscenes.
        self.mission3_breakout_checkpoint_reached = False
        # Once the player reaches the Comms Wing (STAGE_COMMS), Mission 3
        # restarts should respawn there with the K-9 loadout instead of at the
        # breakout checkpoint. Set in _start_comms_phase().
        self.mission3_comms_checkpoint_reached = False
        # Once the player reaches the Archives Wing (STAGE_ARCHIVES), Mission 3
        # restarts should respawn there instead of at Comms.
        self.mission3_archives_checkpoint_reached = False
        # Once the player reaches the Kill Order ground floor, Mission 3
        # restarts should respawn on the KO floor instead of in the atrium.
        # Set in _start_kill_order_phase().
        self.mission3_kill_order_checkpoint_reached = False
        # Once the player reaches the Broadcast Wing (STAGE_BROADCAST), Mission 3
        # restarts should respawn in the studio instead of on the KO floor.
        # Set in _start_broadcast_phase().
        # Both live flags above MUST reset here: restart_current_mission picks
        # the DEEPEST phase reached, so a stale deeper flag left over from an
        # earlier M3 entry (every checkpoint loader runs start_mission3) would
        # hijack a later respawn.
        self.mission3_broadcast_checkpoint_reached = False
        # Sticky flag: all cell-block guards have been killed at least once.
        # Drives the service-door minimap marker + directional arrow.
        self.m3_guards_all_killed = False
        # Set by Mission 3 when Biribel runs dry in the Comms Wing and Volkov
        # should toss him spare mags; consumed by acaristan._GameState_.update.
        self.request_volkov_mags_cutscene = False
        # ── Mission 4: The Aftermath ──
        # Stage values mirror missions.m4.meta STAGE_* strings; owned by
        # start_m4()/m4 flow (same double-reset idiom as the M3 flags: reset
        # here keeps M1-M3 from inheriting stale M4 state, and start_m4
        # re-assigns them on every entry/checkpoint respawn).
        self.mission4_stage = None
        self.m4_chaos_timer = 0            # frames since mission start
        self.m4_liaison_reached = False    # station exterior door opened
        self.m4_cache_taken = False        # Vasile comms cache picked up (E)
        self.m4_maru_joined = False        # Maru accepted at the meet
        self.m4_dialogue_active = False    # meet dialogue locks movement
        self.m4_jammer_installed = False   # transmitter jammer beat done
        self.m4_siege_active = False       # loyalist assault running
        self.m4_hold_timer = 0             # frames held at the transmitter
        self.m4_broadcast_held = False     # hold completed → arrest on air
        self.request_mission4_ending = False
        # Siege director (W4 STAGE_COMMIT): loyalist fireteams spawn from the
        # insertion doors up to world.M4_MAX_CONCURRENT; a marksman press draws
        # a laser telegraph on m4_lasers (m2._add_sniper_laser visual idiom,
        # ported). Reset in world._reset_world_lists + flow.start_m4.
        self.m4_lasers = []                # [{"from","to","life"}] telegraph beams
        self.m4_siege_wave = 0             # fireteams committed this hold
        self.m4_siege_spawn_timer = 0      # frames to next committed fireteam
        self.m4_laser_timer = 0            # frames to next marksman telegraph
        self.m4_allies = []                # Vasile/Maru combat records (world.py)
        # Checkpoint ladder (deepest flag wins in restart_current_mission).
        self.mission4_station_checkpoint_reached = False
        self.mission4_tower_checkpoint_reached = False
        # One-shot radio/story marks so _radio beats fire once per entry.
        self.m4_marks = set()
        # ── Mission 5: Martial Law ──
        # Stage values mirror missions.m5.meta STAGE_* strings; owned by
        # m5 flow (start_m5 re-assigns them on every entry/checkpoint).
        self.mission5_stage = None
        self.m5_guard_kills = 0            # Lower Quarter kills (mercy, read by M8)
        self.m5_maru_found = False         # reached Maru in the back office
        self.m5_dialogue_active = False    # typewriter dialogue locks movement
        self.m5_dialogue_done = False
        self.m5_raid_active = False        # Guard raid on the print works
        self.m5_raid_timer = 0             # frames survived in the raid
        self.m5_maru_hp = 0                # escort HP (tunnel); 0 => fail
        self.m5_maru_dead = False
        self.request_mission5_ending = False
        # Checkpoint ladder (deepest flag wins in restart_current_mission).
        self.mission5_quarter_checkpoint_reached = False  # HQ office done
        self.mission5_printworks_checkpoint_reached = False
        self.mission5_tunnel_checkpoint_reached = False
        self.m5_marks = set()
        self.m5_office_done = False         # Vasile office dialogue (phase 2)
        self.m5_hq_npcs = []                # HQ walking-sim squadmates
        self.m5_mag_drops = 0              # drop-economy caps (m5 systems)
        self.m5_bandage_drops = 0
        self.m5_maru_mags = []             # Maru's thrown resupply mags in flight (m5 world)
        self.m5_maru_mags_thrown_count = 0
        self.m5_outfit = "krap"            # core.outfits: "guard" once forced into the black (M5 only)
        # ── Death animation (Option B - Standard) ──
        # When HP hits 0, death_anim.trigger_death() populates these and
        # death_anim.update_death_anim() advances them every frame. The
        # mission draw loop reads them to render the fall / camera collapse /
        # blood pool / weapon eject. Total duration = DEATH_ANIM_DURATION
        # frames (~2s @ 60fps), after which request_death_screen fires and
        # the existing menu.draw_death_screen() takes over.
        self.death_anim_phase = 0          # 0 = alive, 1 = anim playing
        self.death_anim_timer = 0          # frames since death trigger
        self.death_time_scale = 1.0        # multiplier for game logic updates
        self.death_camera_y_offset = 0.0   # 0 → +35 (Biribel drops to knees)
        self.death_camera_tilt = 0.0       # degrees, 0 → 12 clockwise
        self.death_player_rotation = 0.0   # degrees, 0 → 85 (falls forward)
        self.death_player_slide_x = 0.0    # body slides 8px in fall direction
        self.death_player_slide_y = 0.0
        self.death_blood_pool_radius = 0.0 # grows 0 → 40 under the body
        self.death_blood_pool_pos = None   # (world_x, world_y) where death happened
        self.death_blood_bleed_timer = 0   # counts down 36 frames (0.6s) of continuous bleed
        self.death_weapon_ejected = False
        self.death_weapon_pos = None       # (world_x, world_y) where weapon clattered
        self.death_weapon_rotation = 0.0
        self.death_weapon_type = "pistol"  # "pistol" or "os12"
        self.death_tinnitus_timer = 0      # reused by _draw_tinnitus_overlay
        self._death_frame_accumulator = 0.0  # slow-mo fractional frame carry
        self.request_escape_cutscene = False
        self.request_notebook_inspect = False
        self.notebook_collected = False
        self.exfil_reached = False
        self.show_notebook_inspect = False
        self.notebook_inspect_timer = 0
        self.mission_phase = "infiltrate"
        self.firefight_triggered = False
        self.stealth_failed = False
        self.mag_spawn_done = False
        self.breach_countdown = 0
        self.radio_chatter_stage = 0
        self.volkov_escape_timer = 0
        self.volkov_escape_pos = None
        self.commander_escape_pos = None
        self.volkov_escaped = False
        self.commander_escaped = False
        self.volkov_pos = None
        self.commander_pos = None
        self.NOTEBOOK_POS = None
        self.EXFIL_POS = None
        self.warehouse_walls_set = set()
        # ── Mission 1 pacing additions ──
        self.breach_armed = False
        self.breach_sequence_active = False
        self.breach_stage = 0
        self.breach_stage_timer = 0
        self.lights_flicker_timer = 0
        self.second_wave_timer = 0
        self.second_wave_spawned = True
        self.volkov_sighting_played = False
        self.volkov_sighting_timer = 0
        self.volkov_sighted = False
        self.volkov_visible = False
        self.volkov_display_pos = None
        self.commander_line_played = False
        self.commander_at_console = False
        self.commander_moving = False
        self.commander_lockdown_done = False
        self.stealth_clean = True
        self.stealth_reward_applied = False
        self.quiet_entry = True
        self.hotwire_line_played = False
        self.hotwire_radio_said = False
        self.notebook_twist_shown = False
        self._pending_twist_line = False
        self.civilian_payoff_played = False
        self.civilian_payoff_done = False
        # ─── Interactables ────────────────────────────────────────────
        self.has_keycard = False
        self.gate_hacking = False
        self.gate_hack_progress = 0.0
        self.safe_keypad_active = False
        self.safe_keypad_code = ""
        self.safe_keypad_target = ""
        self.safe_keypad_callback = None
        self.safe_keypad_wrong_attempts = 0  # drives Biribel's escalating code hints
        # Mission 1 safe easter egg - triggered by entering 666.
        self.safe_666_active = False
        self.safe_666_timer = 0
        self.safe_666_seed = 666
        self.truck_hotwiring = False
        self.truck_hotwire_progress = 0.0
        self.hotwire_stage = 0
        self.hotwire_needle = 0.0
        self.hotwire_needle_dir = 1
        self.hotwire_zone_start = 0.4
        self.hotwire_zone_end = 0.6
        self.hotwire_fail_flash = 0
        self.hotwire_selected_wire = None
        self.hotwire_connections = []
        self.hotwire_wrong_attempts = 0
        self.hotwire_spark_timer = 0
        self.hotwire_message = ""
        self.hotwire_panel_timer = 0
        self.mission_end_time = 0
        self.escape_reinforcement_timer = 0
        self.escape_reinforcement_count = 0
        self.active_read_note = None
        # ─── Stats ────────────────────────────────────────────────────
        self.hostiles_killed = 0
        self.shots_fired = 0
        self.shots_hit = 0
        self.mission3_guards_killed = 0
        self.mission3_ammo_drops_spawned = 0
        self.mission3_bandages_spawned = 0
        self.mission3_detainees = []
        self.mission_start_time = 0
        # ─── Walking sim ─────────────────────────────────────────────
        self.walk_dialogue_active = False
        self.walk_dialogue_speaker = ""
        self.walk_dialogue_text = ""
        self.walk_dialogue_char_idx = 0
        self.walk_dialogue_timer = 0
        # ─── Walking sim attack cutscene ────────────────────────────
        self.walk_attack_active = False
        self.walk_attack_timer = 0
        self.walk_attack_events_done = set()
        self.walk_after_firefight = False
        self.walk_boat_active = False
        self.walk_boat_x = 0.0
        self.walk_boat_y = 0.0
        self.walk_missiles = []
        self.walk_explosions = []
        self.walk_terminal_active = False
        self.walk_terminal_status = ""
        self.rig_status = ["ONLINE", "ONLINE", "ONLINE"]
        # Radio director: drop queued transmissions so a stale queue never
        # greets the next mission / respawn.
        try:
            from core.interactions import clear_radio
            clear_radio()
        except Exception:
            pass
# Module-level singleton
STATE = GameState()
