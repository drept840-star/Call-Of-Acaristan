"""Package missions/m3 - re-export facade. Parts: meta.py, maps.py, world.py, flow.py, interrog.py, systems.py, draw.py."""
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
from .meta import *  # noqa: F401,F403
from .meta import _astar, _config, _draw_molotov_icon, _wall_blocks_line  # noqa: F401  (imported names, skipped by star imports)
from .maps import *  # noqa: F401,F403
from .world import *  # noqa: F401,F403
from .flow import *  # noqa: F401,F403
from .interrog import *  # noqa: F401,F403
from .systems import *  # noqa: F401,F403
from .draw import *  # noqa: F401,F403
from .meta import _POST_TYPE_HOLD_MIN, _POST_TYPE_HOLD_MAX, _POST_TYPE_HOLD_PER_CHAR, _BREACH_FREEZE_FRAMES, _TONE_DEFIANT, _TONE_PROBING, _TONE_SILENT, _MONITOR_TILE_COL, _MONITOR_TILE_ROW, _CELL_COL_WEST, _CELL_COL_EAST, _CELL_ROW_NORTH, _CELL_ROW_SOUTH, _DOOR_TILE_COL, _DOOR_TILE_ROW  # noqa: F401
from .flow import start_mission3_kill_order_checkpoint
from .world import _build_kill_order_world, _exfil_pos, _KO_INSERT_TILES, _KO_MEZZ_TILE
from .interrog import _post_type_hold_frames, _start_kill_order_phase, _current_beat, _beat_text, _advance_beat, _line_fully_typed, _play_typewriter_tick, _update_interrogation, _detonate_cell_door, _trigger_action, _transition_to_breakout, _open_cell_door, _update_camera, _ACTION_CAPTIONS, _UNSKIPPABLE_ACTIONS, _UNSKIPPABLE_ACTION_MIN_FRAMES, _action_is_unskippable, _action_auto_locked  # noqa: F401
from .maps import _set_tile, _paint_tiles, _outline_building, _generate_map, _generate_comms_map, _generate_archives_map, _generate_broadcast_map, _last_keys, _objective, _radio_marks  # noqa: F401
from .world import _CHAIR_RECT, _dist, _player_pos, _interrogation_chair_pos, _near, _camera_offset_for_target, _snap_camera_to, _solid_walls, _m3_cell_door_pair_for_col, _m3_door_obj_at, _m3_cell_door_pair_objects, _m3_open_cell_door_pair, _m3_damage_cell_door_with_bullet, _set_objective, _movement_locked, _radio, _start_m3_alarm, _stop_m3_alarm, _draw_m3_alarm_effect, _update_volkov_escape_route, _volkov_escape_path_points, _sample_volkov_escape_path, _volkov_world_pose, _volkov_world_pos, _GUARD_POST_1_TILE, _GUARD_POST_2_TILE, _GUARD_POST_3_TILE, _GUARD_POST_4_TILE, _GUARD_POST_5_TILE, _GUARD_POST_6_TILE, _GUARD_POST_7_TILE, _GUARD_POST_8_TILE, _PATROL_ROUTE_1, _PATROL_ROUTE_2, _PATROL_ROUTE_3, _PATROL_ROUTE_4, _PATROL_ROUTE_5, _PATROL_ROUTE_6, _PATROL_ROUTE_7, _PATROL_ROUTE_8, _EXIT_TILE_COL, _EXIT_TILE_ROW, _VOLKOV_ESCAPE_TARGET, _VENT_GRATE_COL, _VENT_GRATE_ROW, _VENT_EXIT_COL, _VENT_EXIT_ROW, _K9_STAND_COL, _K9_STAND_ROW, _RELAY_TILE_COL, _RELAY_TILE_ROW, _ARCHIVE_EXIT_COL, _ARCHIVE_EXIT_ROW, _MARU_TERMINAL_COL, _MARU_TERMINAL_ROW, _VOSTRAL_FILE_COL, _VOSTRAL_FILE_ROW, _ARCHIVES_SPAWN_COL, _ARCHIVES_SPAWN_ROW, _ARCHIVES_EXIT_COL, _ARCHIVES_EXIT_ROW, _VOSTRAL_DOOR_COLS, _VOSTRAL_DOOR_ROWS, _EXIT_DOOR_COLS, _EXIT_DOOR_ROWS, _spawn_m3_guard, _build_world, _build_comms_world, _build_archives_world, _build_broadcast_world, _spawn_m3_guards_once, _init_m3_detainees, _update_m3_detainees, _detainee_draw_pos, _detainee_palette, _draw_detainee_shadow, _poly_rot, _draw_rot_line, _draw_prisoner_core, _draw_detainee_stand, _draw_detainee_sit, _draw_detainee_cower, _draw_detainee_pushup, _draw_detainee_bars, _draw_detainee_worker, _draw_prisoner_player_sprite, _draw_detainee_dead, _draw_volkov_mags, _draw_m3_detainees  # noqa: F401
from .flow import _dialogue_beats, _dialogue_index, _dialogue_timer, _dialogue_choice, _dialogue_tone, _dialogue_char_idx, _dialogue_slide, _TYPE_SPEED, _TYPE_PAUSE_FULL, _TYPE_PAUSE_SOFT, _TYPE_PAUSE_MID, _monitor_on, _breach_flash, _light_flicker, _volkov_breach_t, _boots_approach_t, _post_type_hold, _complete_mission3, _update_player, _CB_SHOT1, _CB_SHOT2, _CB_SHOT3, _CB_SHOT4, _CB_END, _CB_SHOT1_DUR, _CB_SHOT2_DUR, _CB_SHOT3_DUR, _CB_SHOT4_DUR, _draw_chair_break_cutscene, _grant_chair_leg_from_cutscene, _update_chair_break_cutscene_state, _update_stage, _m3_exit_requirements, _m3_check_volkov_ammo_resupply, _update_volkov_mags, _trigger_volkov_mags_throw, _update_breakout_stage, _start_comms_phase, _maybe_trigger_archives_handoff, _start_archives_phase, _start_broadcast_phase, _update_broadcast_stage, _fail_broadcast_timeout, _retry_broadcast_slice, start_mission3_broadcast_checkpoint, start_mission3_upload_checkpoint, _maru_terminal_pos, _vostral_file_pos, _archives_exit_pos, _archives_nav_target, _draw_archives_nav_arrow, _archives_reachable_hostiles, _start_maru_contact, _update_maru_contact, _acquire_vostral_file, _update_archives_stage  # noqa: F401
from .systems import _mission3_melee_duration, _mission3_melee_progress, _update_mission3_melee, _mission3_arm_pose_for_weapon, _rot_vec, _draw_weapon_layer, _draw_tapered_blade, _draw_chair_leg_weapon, _draw_gripping_hand, _draw_shiv_spark, _draw_mission3_hand_weapon, _draw_m3_weapon_icon, _draw_mission3_hud, _draw_broadcast_address_clock, _update_weapon_timers, _update_doors, _m3_volkov_navigation_walls, _m3_volkov_segment_clear, _m3_volkov_build_grid, _m3_volkov_repath, _m3_volkov_move, _update_volkov_ally, _draw_volkov_ally, _m3_guards_active, _m3_enemy_has_strict_los, _m3_enemy_has_los_to_point, _m3_volkov_target_pos, _m3_choose_enemy_target, _m3_enemy_update_target, _update_m3_enemies, _m3_black_ledger_player_hit_count, _m3_spawn_black_ledger_inmate, _m3_check_black_ledger_trigger, _trigger_black_ledger_death, _update_black_ledger_death, _update_black_ledger_inmate, _draw_black_ledger_inmate, _draw_black_ledger_death_overlay, _m3_hit_detainee_with_bullet, _update_bullets, _update_m3_camera, _update_m3_pickups, _TILE_BASE, _door_obj_at_tile, _draw_tiny_padlock, _draw_m3_door_tile, _relay_pos, _comms_breaker_pos, _comms_auth_pos, _restore_comms_power, _acquire_comms_auth, _start_comms_relay_tuning, _update_comms_relay, _DRAIN_TILE_COL, _DRAIN_TILE_ROW, _CRAFT_DRAG_RATE, _CRAFT_MAX_OFFSET, _CRAFT_CONTACT_Y, _CRAFT_CONTACT_BAND, _finish_crafting, _craft_contact_from_mouse, _craft_overall_progress, _spawn_shaving, _update_crafting, _draw_crafting_overlay, _resolve_choice, _click_blip, _CAMERA_TILE_COL, _CAMERA_TILE_ROW, _CAMERA_SWEEP_HALF, _CAMERA_SWEEP_SPEED, _CAMERA_CONE_HALF, _CAMERA_DETECT_RANGE, _has_los, _security_camera, _draw_security_camera, _spawn_bcast_wave  # noqa: F401
from .draw import _render_cell_bg, _screen_visible_rect, _draw_bg_crate_stack, _draw_bg_barrels, _draw_bg_cable_coil, _draw_bg_mop_bucket, _draw_bg_service_cart, _draw_bg_wall_pipe, _draw_m3_background_dressing, _draw_m3_corridor_and_map_details, _draw_cell_block_corridor_details, _draw_guard_room_details, _draw_k9_wall_stand, _draw_armory_details, _draw_wall_segment, _draw_wall_jamb, _draw_room_label_plate, _draw_rect_room_frame, _draw_lower_wing_wall_readability, _draw_lower_service_wing_details, _draw_lower_service_spine_details, _draw_laundry_room_details, _draw_exercise_yard_details, _draw_maintenance_wing_details, _draw_exit_zone_details, _draw_m3_doors_foreground, _draw_m3_doors, _draw_interrogation_restrained_player, _objective_waypoint_target, _draw_objective_waypoint, _draw_drain_guidance, _draw_comms_wing_details, _draw_comms_map_polish, _draw_comms_relay_prompt, _draw_comms_dynamic_atmosphere, _draw_comms_system_prompts, _draw_comms_relay_overlay, _draw_m3_enemy_type_overlay, _draw_archives_wing_details, _draw_archives_map_polish, _draw_prompt_tag, _draw_archives_system_prompts, _draw_archives_atmosphere, _draw_maru_contact_overlay, _game_draw_archives, _game_draw_comms, _draw_interrogation_monitor_view, _clamp_m3_camera, _ease_in_out, _mission3_breach_camera, _draw_breach_cinematic_letterbox, _draw_m3_pickup, _PANEL_H, _PANEL_PAD, _PANEL_W, _PANEL_X, _wrap, _draw_wall_monitor, _draw_interrogation_status_strip, _draw_text_shadowed, _draw_interrogation_text_scrim, _draw_dialogue_panel, _draw_continue_hint, _draw_cell_atmosphere, _draw_cell_details, _draw_neighbor_cell_base, _draw_neighbor_cells, _draw_kitchen_details, _draw_cell_room, _draw_boots_approach_shadow, _draw_cell_door, _draw_volkov_breach, _C_VOLKOV_COAT, _C_VOLKOV_COAT_OPEN, _C_VOLKOV_LEG, _C_VOLKOV_BOOT, _C_VOLKOV_RIM, _C_VOLKOV_RIM_DIM, _C_VOLKOV_HEAD_RIM, _C_VOLKOV_SKIN, _C_VOLKOV_HAIR, _C_VOLKOV_EYE_OUTER, _C_VOLKOV_EYE_INNER, _C_VOLKOV_CIG, _C_VOLKOV_EMBER, _C_VOLKOV_NAME, _draw_volkov_in_game  # noqa: F401

del MISSION3_MAP, _last_keys, _objective, _radio_marks, _dialogue_index, _dialogue_timer, _dialogue_choice, _dialogue_tone, _dialogue_char_idx, _dialogue_slide, _monitor_on, _breach_flash, _light_flicker, _volkov_breach_t, _boots_approach_t, _post_type_hold, _CHAIR_RECT, _security_camera


_LIVE_STATE = frozenset([
    "MISSION3_MAP",
    "_last_keys",
    "_objective",
    "_radio_marks",
    "_dialogue_index",
    "_dialogue_timer",
    "_dialogue_choice",
    "_dialogue_tone",
    "_dialogue_char_idx",
    "_dialogue_slide",
    "_monitor_on",
    "_breach_flash",
    "_light_flicker",
    "_volkov_breach_t",
    "_boots_approach_t",
    "_post_type_hold",
    "_CHAIR_RECT",
    "_security_camera",
])

_LIVE_MODULES = (
    "missions.m3.draw",
    "missions.m3.systems",
    "missions.m3.interrog",
    "missions.m3.flow",
    "missions.m3.world",
    "missions.m3.maps",
    "missions.m3.meta",
)


def __getattr__(name):
    """PEP 562 live view for rebound shared state (see _LIVE_STATE)."""
    if name in _LIVE_STATE:
        import sys as _sys2
        for _mod in _LIVE_MODULES:
            _m = _sys2.modules.get(_mod)
            if _m is not None and name in vars(_m):
                return vars(_m)[name]
    raise AttributeError(
        "module " + repr(__name__) + " has no attribute " + repr(name))
