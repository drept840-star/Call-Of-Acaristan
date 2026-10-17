
"""Package missions/m2 - re-export facade. Parts: meta.py, world.py, starts.py, sniper.py, update.py, draw.py."""
"""Mission 2: Quiet on Route 12 - clean cinematic vertical slice.

This module keeps the existing game integration intact:
    - game_core.start_mission2()
    - game_core.game_update()/game_draw() routing
    - acaristan.py Mission 2 intro and ending cutscenes
    - save as MISSION_2
    - dev command: python acaristan.py --dev-mission2


"""
from .meta import *  # noqa: F401,F403
from .world import *  # noqa: F401,F403
from .starts import *  # noqa: F401,F403
from .sniper import *  # noqa: F401,F403
from .update import *  # noqa: F401,F403
from .draw import *  # noqa: F401,F403
from .meta import _tc, _tile_rect, _zone_world_rect, _HEDGE_W, _HEDGE_H, _beat, _beat_now, _spawn_molotov_fire, _wall_blocks_line  # noqa: F401
from .world import _set_tile, _paint_tiles, _outline_building, _generate_map, _last_keys, _objective, _radio_marks, _dist, _player_pos, _near, _camera_offset_for_target, _snap_camera_to, _solid_walls, _build_shelter_walls, _set_objective, _radio, _muffle_radio_text, _burst, _open_card, _close_card, _spawn_enemy, _build_world, _spawn_mission2_clues, _setup_travel_triggers, _story_prop_collision_rect, _sync_story_prop_collisions, _init_scripted_props  # noqa: F401
from .starts import _mark_squad_dead, _clue_count, _evidence_count  # noqa: F401
from .sniper import _activate_travel_trigger, _update_travel_triggers, _actor_collision_rect, _actor_rect_collides, _try_actor_step, _move_actor_towards, _nearest_unfound_clue, _update_squad_ambient, _sniper_phase_activity, _update_squad_actor_positions, _sniper_phase_index, _sniper_phase, _sniper_phase_name, _sniper_phase_event, _sniper_actor_pos, _midpoint, _avg_points, _squad_focus, _sniper_camera_target, _advance_sniper_phase, _start_sniper_aftermath, _finish_sniper_sequence, _m3_start_killbox_combat, _nearest_killbox_cover, _nearest_flank_marker, _sniper_alive, _player_exposed_to_sniper, _player_in_meaningful_cover, _cleanup_sniper_state, _suppress_or_remove_sniper, _sniper_close_execute_player, _update_sniper_pressure, _update_post_sniper_gameplay, _smoothstep, _ease_out_cubic_m2, _pulse01, _sniper_set_focus, _sniper_callout, _sniper_fire, _sniper_concrete_impact, _sniper_fire_at, _draw_sniper_callout, _m0_regroup, _m1_regroup_wrong_scan, _m2_seby_darius_die, _m3_near_miss_handoff, _update_sniper_sequence, _start_sniper_sequence, _kill_actor, _add_sniper_laser, _spawn_initial_ipa_team, _spawn_reinforcement_wave, _spawn_control_cleanup, _spawn_evidence_reinforcement_wave, _update_evidence_waves, _start_tanker_run, _explode_tanker, _complete_mission2  # noqa: F401
from .update import _movement_locked, _update_stage, _update_player, _update_weapon_timers, _update_molotovs, _update_sniper_enemy, _update_bullets_enemies, _update_pickups, _update_particles_texts, _update_camera  # noqa: F401
from .draw import _world, _CIVILIAN_CAR_PALETTES, _car_palette, _draw_civilian_car, _draw_burned_car, _draw_car_burn_overlay, _draw_vehicle, _draw_ipa_truck, _draw_ipa_truck_charred, _draw_tanker, _draw_story_prop, _draw_story_props, _draw_sniper_lasers_world, _draw_sniper_muzzle_flashes, _draw_os12_rifle, _WEAPON_CARD_BG, _WEAPON_CARD_BORDER, _WEAPON_CARD_ACCENT, _WEAPON_CARD_TITLE_FG, _WEAPON_CARD_LABEL_FG, _WEAPON_CARD_VALUE_FG, _WEAPON_CARD_FLAVOR_FG, _WEAPON_CARD_STAMP_FG, _draw_route12_pickup_backdrop, _draw_sebi_body_fpv, _draw_fpv_hands_reach, _draw_fpv_hand, _draw_fpv_hands_inspect, _draw_weapon_stat_card, _draw_pickup_overlays, _draw_tinnitus_overlay, _draw_gantry, _draw_actor, _draw_prop_icon, _draw_world_prop, _draw_marker, _draw_shelter, _draw_shelter_arrow, _GRASS_W, _GRASS_H, _grass_surf, _build_garden_walls, _draw_garden, _draw_interactables, _draw_upload_computer, _EVIDENCE_CINEMATIC_SHOTS, _EVIDENCE_CINEMATIC_VASILE_LINE, _update_evidence_cinematic, _draw_evidence_cinematic, _draw_card, _draw_decree_document, _draw_terminal_document, _draw_packet_document, _draw_tanker_schematic, _draw_pistol_icon, _draw_rifle_icon, _draw_weapon_hud, _draw_hud, _draw_radio_text, _draw_clues_note, _draw_sniper_closeup_insert, _draw_dead_air_overlay, _draw_sniper_subtitles, _draw_sniper_overlay, _wrap_text, _draw_tanker_blast_fx, _draw_blackout_overlay, _draw_abandoned_nest, _start_flank_cutscene, _update_flank_cutscene, _draw_flank_cutscene, _gx, _gy, _rng, _shade  # noqa: F401

del _last_keys, _objective, _radio_marks


_LIVE_STATE = frozenset([
    "_last_keys",
    "_objective",
    "_radio_marks",
])

_LIVE_MODULES = (
    "missions.m2.draw",
    "missions.m2.update",
    "missions.m2.sniper",
    "missions.m2.starts",
    "missions.m2.world",
    "missions.m2.meta",
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
