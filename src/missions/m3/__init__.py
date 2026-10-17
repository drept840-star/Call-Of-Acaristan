
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

# ------------------------------------------------------------
# tools\smoke_test.py
# ------------------------------------------------------------

import os

# RPE6 B-010 / R7: this block is a stale copy of tools/smoke_test.py. Its
# env/sys.path/save-redirect side effects used to run whenever the game
# imported missions.m3, which sent the player's saves, settings and wallet
# to a temp dir for the rest of the session. They now run only as __main__.
_AS_SCRIPT = __name__ == "__main__"
if _AS_SCRIPT:
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
    os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

import importlib
import importlib.util
import sys
import traceback
from pathlib import Path

# Game modules live in src/ (repo root / src). Resolve relative to this
# file so `python tools/smoke_test.py` works from the repo root.
if _AS_SCRIPT:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

# Redirect save/settings stores to a temp dir BEFORE game modules load, so
# mission-start progress writes never touch the real save_data.json/settings.json.
import tempfile
import time

_TMP_STORE = Path(tempfile.mkdtemp(prefix="acaristan_smoke_")) if _AS_SCRIPT else None
from core import appearance as _appearance  # noqa: E402
from core import profile_store as _profile_store  # noqa: E402
from core import save_system as _save_system  # noqa: E402
from core import settings_store as _settings_store  # noqa: E402

if _AS_SCRIPT:
    _save_system.SAVE_FILE = str(_TMP_STORE / "save_data.json")
    _settings_store.SAVE_FILE = str(_TMP_STORE / "settings.json")
# The wallet needs the same sandbox as the other two, and for a sharper
# reason: crediting a round writes to disk from inside the match draw path,
# and several checks below drive a whole match to a result. Without this the
# suite would mint real Acaribucks into the player's own profile.json.
if _AS_SCRIPT:
    _profile_store.PROFILE_FILE = str(_TMP_STORE / "profile.json")

import pygame

from core import config
from core import game_core as gc
import ui as menu
import game.world as _gw  # RPE6 Phase 5 (D4): mission data lives in components
from engine.world import Label as _Label
from missions.m3.components import M3Guard as _M3Guard


def _m3g(e):
    """Declared M3 data of an enemy (replaces the ad hoc ``e.m3_*`` attributes)."""
    return _gw.ensure(e, _M3Guard)


def _m3l(e):
    """Shared ``Label`` component of an enemy: ``kind`` = enemy type, ``text`` = spawn label."""
    return _gw.ensure(e, _Label)



# Set this to True after you finish splitting game_core.py into modules.
# If False, missing split modules are reported as SKIP instead of FAIL.
REQUIRE_SPLIT_MODULES = True

VERBOSE_TRACEBACKS = True

SPLIT_MODULES = [
    "core.state",
    "entities.player",
    "entities.weapons",
    "missions.m1",
    "cutscenes",
    "missions.walking_sim",
    "fx.effects",
    "ui.hud",
    "core.interactions",
]


class EmptyKeys:
    """Fake pygame.key.get_pressed() object.

    Any key lookup returns False.
    """
    def __getitem__(self, key):
        return False


def run_check(name, fn, required=True):
    try:
        fn()
        pygame.event.pump()

        if pygame.display.get_surface() is not None:
            pygame.display.flip()

    except Exception as e:
        status = "FAIL" if required else "SKIP"
        print(f"{name}: {status} {e!r}")

        if required and VERBOSE_TRACEBACKS:
            traceback.print_exc()

        return not required

    print(f"{name}: OK")
    return True


def run_import_check(module_name):
    spec = importlib.util.find_spec(module_name)

    if spec is None:
        if REQUIRE_SPLIT_MODULES:
            print(f"import {module_name}: FAIL module not found")
            return False

        print(f"import {module_name}: SKIP module not found")
        return True

    return run_check(
        f"import {module_name}",
        lambda: importlib.import_module(module_name),
        required=True,
    )


def clear_screen():
    config.screen.fill((0, 0, 0))


def check_menu_draw():
    clear_screen()
    menu.draw_menu()


def check_settings_draw():
    clear_screen()
    menu.draw_menu_background()
    # Signature must mirror acaristan.py:1362-1370 exactly.
    menu.draw_settings(
        0, 0, 0,
        80, 80, 100, False,           # master, music, sfx, mute_on_focus_loss
        0, 8, True, False, True,      # crosshair, crosshair_size, auto_reload, aim_assist, subtitles
        100, True, True, 100,         # brightness, scanlines, grain, particle_density
        50, False,                    # mouse_sensitivity, invert_mouse
        False, 0,                     # reduced_motion, colorblind_mode
    )


def check_multiplayer_opens_on_server_browser():
    """Clicking MULTIPLAYER must land on the SERVER LIST, not the host panel.

    Regression guard for "MULTIPLAYER goes straight to hosting". MatchScreen
    is a single process-wide instance and every gate in app.py's
    _MultiplayerState -- handle_event, update and render -- short-circuits to
    the match screen when ``mode`` is panel/hosting/playing. Its constructor
    used to start at "panel", so the very first click on MULTIPLAYER drew the
    HOST/JOIN panel and the server browser was unreachable for the whole
    session.

    The screen's contract is: closed = browser showing, open_panel() = the
    arena panel raised on top of it.
    """
    from ui.match_screen import MatchScreen

    m = MatchScreen()
    assert m.mode == "closed", (
        "MatchScreen must start closed so the server browser is the landing "
        "screen, got mode=%r" % (m.mode,))
    assert not m.is_open(), "a fresh MatchScreen reports itself open"

    # A closed screen must not own input or draw anything over the browser.
    assert m.draw(config.screen) is None, "closed MatchScreen drew a frame"
    _esc = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_ESCAPE,
                              unicode="\x1b")
    assert m.handle_event(_esc, (0, 0)) is False, \
        "closed MatchScreen swallowed input that belongs to the browser"

    # The arena panel raises it explicitly, and closing lowers it again so
    # the browser comes back.
    m.open_panel()
    assert m.mode == "panel" and m.is_open(), "open_panel did not raise panel"
    m.close()
    assert m.mode == "closed", "close() did not lower the panel"

    # Leaving a live match returns to the panel (map choice kept), which is
    # the documented behaviour and must not be turned into a silent close.
    m.open_panel()
    m.leave_match()
    assert m.mode == "panel", \
        "leave_match must return to the panel, got %r" % (m.mode,)
    m.close()


def check_host_is_taught_how_to_host():
    """A player who has never hosted must be told what hosting IS.

    Hosting is the one control on this screen that does not do the obvious
    thing: HOST MATCH does not put you in a game, it makes you the thing other
    people connect to, and the artefact they need (a room code) only exists
    people connect to, and the thing they need (a room code) only exists
    afterwards. The panel now spells that out, and hosting opens a frozen
    lobby with the code visible. A peer joining fills the roster but DOES NOT
    start the round; the host must press START MATCH.
    """
    from ui.match_screen import MatchScreen, HOST_HELP
    from ui.match_screen import PANEL_H as _H
    from ui import mp as _browser

    assert _browser.SERVER_CONNECT_Y >= (
        _browser.SERVER_SUBTITLE_Y
        + _browser.font_terminal_small.get_height() + 4), \
        "direct-connect row crowds the relay status line"
    assert (_browser.SERVER_CONNECT_Y + _browser._connect_rect.h
            <= _browser.SERVER_TAB_Y), \
        "direct-connect row overlaps the browser tabs"
    assert _browser.SERVER_LIST_TOP >= _browser.SERVER_DIVIDER_Y + 36, \
        "column headings crowd the browser divider"

    assert len(HOST_HELP) == 3, "hosting is explained in %d steps" % len(
        HOST_HELP)
    joined = " ".join(HOST_HELP).lower()
    for word in ("host", "code", "send", "join"):
        assert word in joined, "hosting steps never mention %r" % (word,)

    m = MatchScreen()
    m.open_panel()
    # The help block has to fit inside the panel, or it is drawn off the
    # bottom edge and the last step is the one nobody reads.
    assert _H >= 444, "panel too short for the hosting steps: %r" % (_H,)
    m.draw_panel(config.screen)

    # The lobby card is shared by hosts and joiners, and remains visible after
    # a peer connects until the host explicitly starts.
    m.mode = "hosting"
    m._session_phase = "lobby"
    m.room_code = "ACAR-A974P-K39GWZ"
    m.share_host = "192.168.0.5"
    m.share_port = 27015
    m._draw_waiting(config.screen)
    assert m._wait_rects.get("copy") is not None, \
        "waiting card offered no way to copy the code"

    # COPY CODE must work from the card, without opening the pause menu.
    import ui.match_screen as _ms
    _orig = _ms.clipboard_text
    m.status = ""
    try:
        _c = m._wait_rects["copy"].center
        _ev = pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=_c)
        assert m.handle_event(_ev, _c) is True, \
            "COPY CODE click was not consumed"
    finally:
        _ms.clipboard_text = _orig

    # The forwarding verdict must be one shared function: a host told the
    # code is fine on one screen and unusable on the other is worse than
    # either answer.
    m.forwarded, m.forward_note = True, ""
    ok_note, _ = m._forward_status()
    m.forwarded, m.forward_note = False, "no UPnP gateway found"
    bad_note, _ = m._forward_status()
    assert "port" in ok_note.lower() and "LAN" in bad_note, \
        "forwarding status does not distinguish public mapping from LAN-only"

    # ...and that the card's hit-rect dies with it. A rect left behind after
    # the card is gone is an invisible live button: the click where COPY CODE
    # used to be would copy instead of firing.
    m.peers.append(type("P", (), {"close": lambda self: None})())
    m._match_started = True
    m._session_phase = "playing"
    m.sim = type("S", (), {"finished": False, "scoreboard": tuple})()
    m.sess = type("Sess", (), {"local_id": 0, "world": [],
                              "sample_world": dict})()
    m.view = type("V", (), {"draw": lambda *a, **k: None})()
    m._draw_match(config.screen)
    assert m._wait_rects == {}, \
        "waiting card hit-rect survived a joining player: %r" % (
            m._wait_rects,)
    m.peers.clear()
    m.close()


def check_remote_input_is_applied():
    """A REMOTE player's input must reach the simulation.

    This is the check that catches the worst multiplayer bug there is: the
    host accepting packets, acknowledging them, and quietly throwing them
    away. Both the host's own keyboard input and the host-side read path
    build packets containing the "t" field, so anything that re-parses
    after a parse strips it and the validation then rejects the packet --
    leaving local play working perfectly while no remote player can move or
    shoot. It looks exactly like "the netcode is fine, the sim is fine".
    """
    import socket as _socket
    from net import protocol as _P
    from ui.match_screen import MatchScreen as _MS

    m = _MS()
    m.open_panel()
    m.players = 4
    m.request_host(0)
    keys = pygame.key.get_pressed()
    idle = (500, 350, False)
    m.update(keys, idle, 1.0 / 60.0)
    port = m.srv.getsockname()[1]
    conn = None
    try:
        conn = _socket.create_connection(("127.0.0.1", port), timeout=5)
        conn.setblocking(False)
        # A connection is only a CANDIDATE until it sends the join handshake;
        # without it the host must not create a player (see the phantom-peer
        # regression check).
        conn.sendall(_P.encode(_P.make_join_match()))
        for _ in range(8):          # let the host accept
            m.update(keys, idle, 1.0 / 60.0)
        assert len(m.peers) == 1, "remote player never joined"
        assert sorted(m.sim.players) == [0, 1], \
            "sim roster wrong: %r" % sorted(m.sim.players)

        from missions import arena as _AR
        st = m.sim.players[1]
        _AR._grant(st, _P.WPN_OS12)
        st["weapon"] = _P.WPN_PISTOL
        x0 = st["x"]
        y0 = st["y"]

        # Even hostile/stale input packets during the lobby are ignored.
        for f in range(20):
            conn.sendall(_P.encode(_P.make_input(f, 1.0, 0.0, 0.0, 0)))
            m.update(keys, idle, 1.0 / 60.0)
        assert st["x"] == x0 and st["y"] == y0, \
            "remote input moved a player while the host was in the lobby"
        assert m.sim.tick == 0, "the lobby advanced the authoritative clock"

        assert m._begin_countdown(), "host could not start after a peer joined"
        ammo_before_intro = st["ammo"]
        for f in range(20, 240):
            # Movement, fire, reload and a valid weapon switch must not be
            # buffered for the first live tick.
            conn.sendall(_P.encode(_P.make_input(
                f, 1.0, 0.0, 0.0, _P.F_FIRING | _P.F_RELOAD,
                cycle=True)))
            m.update(keys, idle, 1.0 / 60.0)
            if m.session_phase() == "playing":
                break
            assert st["x"] == x0 and st["y"] == y0, \
                "remote player moved during the host countdown"
            assert st["ammo"] == ammo_before_intro, \
                "remote player fired during the host countdown"
        assert m.session_phase() == "playing", \
            "host countdown did not release the simulation"
        assert st["x"] == x0 and st["y"] == y0, \
            "countdown movement leaked onto the first live tick"
        assert st["ammo"] == ammo_before_intro, \
            "countdown firing leaked onto the first live tick"
        assert st["weapon"] == _P.WPN_PISTOL, \
            "countdown weapon switch leaked onto the first live tick"

        # MOVE: hold east for a second of live ticks.
        for f in range(60):
            conn.sendall(_P.encode(
                _P.make_input(100 + f, 1.0, 0.0, 0.0, 0)))
            m.update(keys, idle, 1.0 / 60.0)
        assert st["x"] > x0 + 4, \
            "remote input ignored after Start: x stayed %.1f (was %.1f)" % (st["x"], x0)

        # FIRE: hold the trigger and check the magazine is spent.
        ammo0 = st["ammo"]
        shots = 0
        for f in range(120):
            conn.sendall(_P.encode(_P.make_input(
                1000 + f, 0.0, 0.0, 0.0,
                _P.F_FIRING if f < 100 else 0)))
            m.update(keys, idle, 1.0 / 60.0)
            if m.sim.last_shot is not None:
                shots += 1
                # last_shot is per-tick and must carry the shooter id.
                assert len(m.sim.last_shot) == 6, \
                    "last_shot shape changed: %r" % (m.sim.last_shot,)
                assert m.sim.last_shot[4] == 1, \
                    "last_shot shooter id wrong: %r" % (m.sim.last_shot[4],)
        assert shots > 0, "remote player never fired"
        assert st["ammo"] < ammo0, "remote trigger did not spend ammo"
    finally:
        if conn is not None:
            try:
                conn.close()
            except OSError:
                pass
        m.close()


def check_lobby_relay_is_not_a_player():
    """The lobby relay's own connection must never become an opponent.

    The game keeps a relay client running while a match is hosted, and that
    client retries a FIXED local master address forever. When the match
    listener shared the relay's port, its reconnect was accepted as a
    player: a "bot" that never moved appeared, and the frozen waiting lobby
    ended even though nobody had joined. An accepted socket is now only a
    candidate until it sends the join handshake.
    """
    import socket as _socket
    from net import protocol as _P
    from ui.match_screen import MatchScreen

    m = MatchScreen()
    m.open_panel()
    m.players = 4
    m.request_host(0)
    keys = pygame.key.get_pressed()
    idle = (500, 350, False)
    m.update(keys, idle, 1.0 / 60.0)
    port = m.srv.getsockname()[1]
    conn = None
    try:
        conn = _socket.create_connection(("127.0.0.1", port), timeout=5)
        conn.setblocking(False)
        for _ in range(8):
            m.update(keys, idle, 1.0 / 60.0)
        # Accepted, but not a player: no roster entry, no round.
        assert not m.peers, "an unannounced connection became a player"
        assert sorted(m.sim.players) == [0], "phantom player in the sim roster"
        assert m.waiting_for_player(), "the waiting lobby ended for a stranger"
        assert m.sim.tick == 0, "the round started with nobody in it"

        # The relay speaks the LOBBY protocol (hello + query), not the match
        # protocol. Sending it must close the connection, not seat it.
        conn.sendall(_P.encode({"t": _P.T_HELLO, "user": "operator",
                                "proto": _P.PROTO_VERSION}))
        conn.sendall(_P.encode({"t": _P.T_QUERY}))
        for _ in range(8):
            m.update(keys, idle, 1.0 / 60.0)
        assert not m.peers, "a lobby client was seated as a player"
        assert sorted(m.sim.players) == [0], "lobby client entered the sim"
        assert m.waiting_for_player(), "the waiting lobby ended for the relay"
        assert m.sim.tick == 0, "a lobby client started the round"
        # It must be CLOSED, not merely ignored, so the slot is free again
        # and the relay's retry cycle cannot pile up sockets.
        conn.settimeout(2.0)
        try:
            data = conn.recv(65536)
        except OSError:
            data = b""      # RST is also a closed connection
        assert data == b"", "the stray connection was left open"

        # A genuine client on the same listener still gets in, so the guard
        # did not simply break joining.
        good = _socket.create_connection(("127.0.0.1", port), timeout=5)
        good.sendall(_P.encode(_P.make_join_match()))
        for _ in range(8):
            m.update(keys, idle, 1.0 / 60.0)
        assert len(m.peers) == 1, "a real match client was rejected"
        assert m.peers[0].player_id == 1, "real client got the wrong slot"
        assert m.waiting_for_player(), \
            "joining automatically started the round instead of opening a lobby"
        assert m.sim.tick == 0, "a joined player advanced the frozen lobby"
        assert len(m._lobby_roster()) == 2, \
            "the lobby roster did not include host and joining player"
        good.close()
    finally:
        if conn is not None:
            try:
                conn.close()
            except OSError:
                pass
        m.close()


def check_client_join_completes():
    """Clients join a lobby; only the host can start the frozen countdown.

    This drives a real MatchScreen client against a real host over loopback:
    socket assignment, initial static snapshot, room roster, explicit host
    start, synchronized 3/2/1/GO, and then the first live simulation tick.
    """
    from ui.match_screen import MatchScreen
    from net import roomcode as _RC

    host = MatchScreen()
    host.open_panel()
    host.players = 2
    # Real names, so the roster assertion below also proves the name crossed
    # the wire. With slot labels it only proved two slots existed.
    host.player_name = "HOSTNAME"
    host.request_host(0)               # ephemeral; no router touch
    keys = pygame.key.get_pressed()
    idle = (500, 350, False)
    host.update(keys, idle, 1.0 / 60.0)
    assert host.mode == "hosting", "host did not start: " + host.status
    assert host.waiting_for_player(), "host should start in the waiting lobby"
    host.update(keys, (500, 350, True), 0.1)
    assert host.sim.tick == 0, "host simulation advanced before anyone joined"
    port = host.srv.getsockname()[1]

    client = MatchScreen()
    client.open_panel()
    client.player_name = "JOINER"
    client.request_join(_RC.encode("127.0.0.1", port))
    try:
        for _ in range(180):
            host.update(keys, idle, 1.0 / 60.0)
            client.update(keys, idle, 1.0 / 60.0)
            if client.sess is not None and client.sess.local_id == 1 \
                    and client.mode == "playing" \
                    and client.sess.sample_world():
                break
        assert client.mode == "playing", (
            "client never entered the room (mode=%r status=%r)"
            % (client.mode, client.status))
        # Connection alone only creates the lobby: both sides must remain
        # frozen and the client must receive the two-player roster.
        assert host.waiting_for_player(), \
            "a client joining auto-started the match"
        assert host.sim.tick == 0, "simulation advanced before host Start"
        assert client.in_match_lobby(), \
            "joiner did not remain on the shared pre-game lobby"
        assert client._match_state.get("roster") == [
            (0, "HOSTNAME"), (1, "JOINER")], \
            "joiner did not receive the host's player roster: %r" % (
                client._match_state.get("roster"),)
        assert client.sess.local_id == 1, \
            "client never learned its slot: %r" % client.sess.local_id
        assert len(host.peers) == 1, "host never accepted the client"
        assert client.sess.sample_world(), "client received no lobby world"

        host._draw_waiting(config.screen)
        start_rect = host._lobby_rects.get("start")
        assert start_rect is not None, \
            "host lobby did not show START MATCH with two players"
        click = pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1,
                                   pos=start_rect.center)
        assert host.handle_event(click, start_rect.center), \
            "START MATCH click was not consumed"
        assert host.session_phase() == "countdown", \
            "host click did not start the countdown"
        frozen_pos = tuple(host.sim.players[1][k] for k in ("x", "y"))
        frozen_ammo = host.sim.players[1]["ammo"]

        class _HeldKeys(dict):
            def __missing__(self, key):
                return key in (pygame.K_w, pygame.K_d)

        held = _HeldKeys()
        for _ in range(260):
            host.update(keys, (500, 350, True), 1.0 / 60.0)
            client.update(held, (500, 350, True), 1.0 / 60.0)
            if host.session_phase() == "playing" and \
                    client.session_phase() == "playing":
                break
            assert host.sim.tick == 0, \
                "host simulation ticked before the countdown finished"
            assert tuple(host.sim.players[1][k] for k in ("x", "y")) == frozen_pos, \
                "remote player moved during the lobby/countdown"
            assert host.sim.players[1]["ammo"] == frozen_ammo, \
                "remote player fired during the lobby/countdown"
        assert host.session_phase() == "playing", \
            "host did not enter gameplay after the countdown"
        assert client.session_phase() == "playing", \
            "client did not receive the host's live phase"
        for _ in range(3):
            host.update(keys, idle, 1.0 / 60.0)
            client.update(keys, idle, 1.0 / 60.0)
        assert host.sim.tick > 0, "simulation did not resume after GO"
        assert client.sess.sample_world(), "client lost the world after GO"
    finally:
        client.close()
        host.close()


def check_host_left_ends_session():
    """A host that leaves must end the session for every client in it.

    The host IS the simulation and there is no host migration, so its
    departure is not "a player left", it is "the match no longer exists".
    Two ways of getting that wrong are covered here.

    Silence: a host that loses power never sends FIN or RST, so a client
    that only reacts to the socket dying waits in a frozen arena forever.

    Ambiguity: even a clean socket close tells the client nothing about
    WHY -- its own wifi dropping looks identical -- so the host now says
    the session is over before it closes, and the client leaves with an
    explanation instead of a guess.
    """
    import time as _time
    from ui.match_screen import MatchScreen, HOST_SILENCE_TIMEOUT
    from net import roomcode as _RC
    from net import protocol as _P

    assert _P.parse_host_left(_P.make_host_left("gone")) == "gone", \
        "host-left packet did not carry its reason"
    assert _P.parse_host_left({"t": _P.T_HOST_LEFT}) == "", \
        "a reasonless host-left packet is still a complete answer"
    assert _P.parse_host_left({"t": "snap"}) is None, \
        "a snapshot was mistaken for a host-left packet"

    keys = pygame.key.get_pressed()
    idle = (500, 350, False)

    host = MatchScreen()
    host.open_panel()
    host.players = 2
    host.request_host(0)
    host.update(keys, idle, 1.0 / 60.0)
    port = host.srv.getsockname()[1]

    client = MatchScreen()

    def _rejoin():
        """Join (or re-join) the host and wait until the slot is assigned."""
        client.open_panel()
        client.request_join(_RC.encode("127.0.0.1", port))
        for _ in range(180):
            host.update(keys, idle, 1.0 / 60.0)
            client.update(keys, idle, 1.0 / 60.0)
            if client.mode == "playing" and client.sess.local_id == 1:
                return
        raise AssertionError("client never joined: " + client.status)

    try:
        _rejoin()
        # (1) A host that goes quiet. No packet, no RST, just nothing.
        assert client._last_recv is not None, \
            "client never armed its host-silence watchdog"
        client._last_recv = _time.monotonic() - (HOST_SILENCE_TIMEOUT + 1.0)
        client.update(keys, idle, 1.0 / 60.0)
        assert client.mode != "playing", \
            "a silent host left the client sitting in a dead match"
        assert "host" in client.status.lower(), \
            "the client was not told why it left: %r" % (client.status,)

        # (2) A host that leaves cleanly. The announcement has to reach the
        # client before the sockets it rides on are closed.
        _rejoin()
        host.close()
        for _ in range(60):
            client.update(keys, idle, 1.0 / 60.0)
            if client.mode != "playing":
                break
        assert client.mode != "playing", \
            "the client was still in the match after the host left"
        assert "host" in client.status.lower(), \
            "the client was not told the host ended it: %r" % (client.status,)
        assert client.sock is None and client.sess is None, \
            "leaving an ended session leaked its socket"
    finally:
        client.close()
        host.close()


def check_switch_survives_batched_inputs():
    """Switches must survive network batching and apply only once.

    Gameplay input is sampled every rendered frame, but TCP may deliver two
    frames in one read. A switch is a one-shot action: taking only the latest
    input erases it if a neutral frame follows; reusing the same latest input
    for catch-up simulation ticks cycles twice and lands back on the start.
    """
    from net.match import MatchSession
    from net import protocol as P
    from missions import arena as AR

    class _Sink:
        def _send(self, obj):
            return True

    sess = MatchSession(_Sink(), is_host=True)
    sim = AR.ArenaSim(sess, AR.ARENA_YARD, score_limit=99)
    st = sim.add_player(1, "CLIENT")
    AR._grant(st, P.WPN_OS12)
    st["weapon"] = P.WPN_PISTOL

    # Two inputs land in the same host read before it runs the next tick.
    sess._accept_input(P.make_input(1, 0, 0, 0, cycle=True), peer_id=1)
    sess._accept_input(P.make_input(2, 0, 0, 0), peer_id=1)
    sim.step()
    assert st["weapon"] == P.WPN_OS12, \
        "a neutral frame batched behind Q erased the switch"
    sim.step()
    assert st["weapon"] == P.WPN_OS12, \
        "a catch-up tick applied the same switch a second time"

    # Even if the host has no new packet for several ticks, Q is a single
    # tap, not a held direction; it must not ping-pong between guns.
    sess._accept_input(P.make_input(3, 0, 0, 0, cycle=True), peer_id=1)
    for _ in range(4):
        sim.step()
    assert st["weapon"] == P.WPN_PISTOL, \
        "a single Q tap was reapplied across host simulation ticks"

    # Direct number-key requests can be batched as well; don't lose one just
    # because another input arrived before the next host update.
    sess._accept_input(P.make_input(4, 0, 0, 0, weapon=P.WPN_OS12), peer_id=1)
    sess._accept_input(P.make_input(5, 0, 0, 0), peer_id=1)
    sim.step()
    assert st["weapon"] == P.WPN_OS12, \
        "a neutral frame batched behind a number key erased the switch"

    # Player IDs are recycled. A departed player's queued Q must not equip
    # a weapon for the next connection that inherits that slot.
    sess._accept_input(P.make_input(6, 0, 0, 0, cycle=True), peer_id=1)
    sess.forget_peer(1)
    sess._accept_input(P.make_input(0, 0, 0, 0), peer_id=1)
    assert not sess.consume_input(1).get("wcycle"), \
        "a departed player's queued switch reached the replacement peer"

    # Through the *real* host socket read path, too. A direct _accept_input
    # test alone would miss a regression where the host drops an earlier
    # packet while parsing several newline frames from a single TCP recv.
    import socket
    from ui.match_screen import MatchScreen

    host = MatchScreen()
    host.open_panel()
    host.players = 2
    host.request_host(0)
    keys = pygame.key.get_pressed()
    idle = (500, 350, False)
    host.update(keys, idle, 1.0 / 60.0)
    conn = None
    try:
        conn = socket.create_connection(("127.0.0.1",
                                         host.srv.getsockname()[1]), timeout=3)
        conn.sendall(P.encode(P.make_join_match()))
        for _ in range(8):
            host.update(keys, idle, 1.0 / 60.0)
        assert len(host.peers) == 1, "host did not accept the real client"
        assert host.waiting_for_player(), \
            "a raw client connection started the match without host input"
        assert host._begin_countdown(), "host could not start with a joined player"
        for _ in range(240):
            host.update(keys, idle, 1.0 / 60.0)
            if host.session_phase() == "playing":
                break
        assert host.session_phase() == "playing", \
            "host never reached live play after explicit start"
        player = host.sim.players[1]
        AR._grant(player, P.WPN_OS12)
        player["weapon"] = P.WPN_PISTOL
        # Deliver the tap and its next neutral frame in a single TCP write.
        conn.sendall(P.encode(P.make_input(1, 0, 0, 0, cycle=True))
                     + P.encode(P.make_input(2, 0, 0, 0)))
        for _ in range(8):
            host.update(keys, idle, 1.0 / 60.0)
        assert player["weapon"] == P.WPN_OS12, \
            "batched switch disappeared on the real host socket"
    finally:
        if conn is not None:
            conn.close()
        host.close()


def check_weapon_switching_in_match():
    """A player must be able to switch weapons mid-match.

    Switching is a request, never an order: the host owns the loadout, so
    a client that names a gun it never picked up is refused -- otherwise
    every weapon crate on the map is pointless, because the gun is free.
    What the request does need is to actually ARRIVE. The cycle request
    (Q / wheel) was dropped in validation and never reached the host at
    all, so the key did nothing and there was no way to tell why.
    """
    from ui.match_screen import MatchScreen
    from net import roomcode as _RC
    from net import protocol as _P
    from missions import arena as _AR

    # The cycle flag has to survive the wire, or the host never sees it.
    assert _P.parse_input(_P.make_input(1, 0, 0, 0.0, cycle=True)).get(
        "wcycle") == 1, "cycle request was stripped in validation"
    assert "c" not in _P.make_input(1, 0, 0, 0.0), \
        "an idle packet grew a cycle field"

    keys = pygame.key.get_pressed()
    idle = (500, 350, False)
    host = MatchScreen()
    host.open_panel()
    host.players = 2
    host.request_host(0)
    host.update(keys, idle, 1.0 / 60.0)
    port = host.srv.getsockname()[1]

    client = MatchScreen()
    client.open_panel()
    client.request_join(_RC.encode("127.0.0.1", port))
    try:
        for _ in range(180):
            host.update(keys, idle, 1.0 / 60.0)
            client.update(keys, idle, 1.0 / 60.0)
            if client.mode == "playing" and client.sess.local_id == 1:
                break
        assert client.mode == "playing", "client never joined: " + client.status
        assert client.in_match_lobby(), \
            "joining should show the pre-game lobby, not live gameplay"

        def pump(n=90):
            for _ in range(n):
                host.update(keys, idle, 1.0 / 60.0)
                client.update(keys, idle, 1.0 / 60.0)

        # Gameplay controls are swallowed in the lobby and countdown. They
        # must not turn into pending requests after the host presses Start.
        q = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_q)
        client.handle_event(q, (500, 350))
        assert not client._want_cycle and not client._toast, \
            "lobby input leaked through to weapon handling"
        assert host._begin_countdown(), "host could not start after the join"
        pump(2)
        assert client.session_phase() == "countdown", \
            "joiner did not receive the host-owned countdown"
        client.handle_event(q, (500, 350))
        assert not client._want_cycle, \
            "countdown input queued a weapon switch"
        for _ in range(240):
            pump()
            if (host.session_phase() == "playing"
                    and client.session_phase() == "playing"):
                break
        assert host.session_phase() == client.session_phase() == "playing", \
            "host and client did not leave the frozen countdown together"
        client.handle_event(q, (500, 350))
        assert "PICK UP" in client._toast, \
            "Q with only the spawn pistol gave no explanation in live play"

        # Collect actual weapon crates, not a synthetic _grant call: a
        # freshly spawned player only owns the pistol and Q cannot switch
        # until they collect another gun. Exercise the real pickup path.
        st = host.sim.players[1]
        rifle = next(pk for pk in host.sim.pickup_items
                     if pk["kind"] == "weapon"
                     and pk["value"] == _P.WPN_OS12)
        st["x"], st["y"] = rifle["x"], rifle["y"]
        host.update(keys, idle, 1.0 / 60.0)
        assert _P.WPN_OS12 in _AR.owned_weapons(st), \
            "the client did not collect the OS-12 crate"
        st["weapon"] = _P.WPN_PISTOL
        host_st = host.sim.players[0]
        smg = next(pk for pk in host.sim.pickup_items
                   if pk["kind"] == "weapon" and pk["value"] == _P.WPN_K9)
        host_st["x"], host_st["y"] = smg["x"], smg["y"]
        host.update(keys, idle, 1.0 / 60.0)
        assert _P.WPN_K9 in _AR.owned_weapons(host_st), \
            "the host did not collect the K-9 crate"
        host_st["weapon"] = _P.WPN_PISTOL

        # The loadout has to reach the client, or it cannot grey out the
        # keys the host is going to refuse.
        pump(60)
        assert _P.WPN_OS12 in client._local_carry(), \
            "client never learned what it is carrying: %r" % (
                client._local_carry(),)

        # 2 = the OS-12 we just picked up.
        client.handle_event(pygame.event.Event(pygame.KEYDOWN,
                                              key=pygame.K_2), (500, 350))
        assert client._want_weapon == _P.WPN_OS12, "number key did not arm"
        pump()
        assert host.sim.players[1]["weapon"] == _P.WPN_OS12, \
            "an owned weapon switch was not applied by the host"

        # 3 = the K-9, which we do NOT have. Must be refused, and said so.
        client.handle_event(pygame.event.Event(pygame.KEYDOWN,
                                              key=pygame.K_3), (500, 350))
        pump(30)
        assert host.sim.players[1]["weapon"] == _P.WPN_OS12, \
            "host equipped a weapon the player never picked up"
        assert client._toast, "a refused switch gave the player no feedback"

        # Q cycles: OS-12 -> back to the pistol.
        client.handle_event(pygame.event.Event(pygame.KEYDOWN,
                                              key=pygame.K_q), (500, 350))
        pump()
        assert host.sim.players[1]["weapon"] == _P.WPN_PISTOL, \
            "Q did not cycle to the next carried weapon"

        # The mouse wheel is the same request by another route.
        client.handle_event(pygame.event.Event(pygame.MOUSEWHEEL, y=1),
                            (500, 350))
        pump()
        assert host.sim.players[1]["weapon"] == _P.WPN_OS12, \
            "the mouse wheel did not cycle weapons"

        # And the HOST cycles through its own input path, not a special one.
        host.handle_event(pygame.event.Event(pygame.KEYDOWN,
                                             key=pygame.K_q), (500, 350))
        pump()
        assert host.sim.players[0]["weapon"] == _P.WPN_K9, \
            "the host could not switch its own weapon"
    finally:
        client.close()
        host.close()


def check_arena_sprite_rig_and_anim():
    """An arena player must draw their OWN gun and their OWN animation.

    The arena reuses the campaign's Player sprite on purpose -- a second,
    hand-rolled remote-player rig would drift from the single-player art.
    But that sprite picks its gun silhouette from the mission global
    STATE.current_weapon: one value, correct for a mission's single player
    and meaningless in a match where several players hold different guns.
    So every arena player drew the SAME gun, and a real switch (2/3/Q)
    changed nothing on screen.

    Three single-player behaviours were missing for the same reason, and are
    pinned here together: the gun model (above), PS_MOVING only being set
    while SPRINTING (so walking never played the walk cycle), and the reload
    arm animation being fed a fixed 0 progress (so a reload stood still).
    """
    from ui.arena_view import ArenaView, rig_for_weapon
    from entities.player import Player
    from missions import arena as AR
    from net.match import MatchSession
    from net import protocol as P
    from core.state import STATE

    # ── wire id -> rig name, with a safe fallback ──
    assert rig_for_weapon(P.WPN_OS12) == "os12"
    assert rig_for_weapon(P.WPN_K9) == "k9_smg"
    assert rig_for_weapon(P.WPN_PISTOL) == "pistol"
    assert rig_for_weapon(9999) == "pistol", \
        "an unknown weapon id must fall back, never leave a player gun-less"

    # ── the sprite obeys its per-instance override, not the global ──
    saved_weapon = getattr(STATE, "current_weapon", "pistol")
    try:
        p = Player(0, 0)
        assert p.rig_weapon_name() == "pistol"   # no override -> global default
        p.rig_weapon = "os12"
        STATE.current_weapon = "pistol"
        assert p.rig_weapon_name() == "os12", \
            "the per-instance weapon was overridden by the mission global"
        # barrel_tip() must follow the override too, or the muzzle flash sits
        # at the pistol's reach on a longer gun: OS-12 reaches further.
        p.angle = 0.0
        os12_tip = p.barrel_tip()[0]
        p.rig_weapon = "pistol"
        assert os12_tip > p.barrel_tip()[0], \
            "barrel_tip ignored the per-instance weapon"

        # ── the view drives the rig from each entity's weapon field ──
        view = ArenaView("yard")
        world = {
            0: P.make_entity(0, P.ENT_PLAYER, 100, 100, 0.0, 100,
                             P.PS_IDLE, P.WPN_PISTOL, 0, 0),
            1: P.make_entity(1, P.ENT_REMOTE, 200, 200, 0.0, 100,
                             P.PS_IDLE, P.WPN_OS12, 0, 0),
        }
        posed = view.sync(world)
        assert posed[0][0].rig_weapon == "pistol"
        assert posed[1][0].rig_weapon == "os12", \
            "a remote player holding the OS-12 was drawn with the wrong gun"
        assert posed[1][0].swap_timer == 0, \
            "a player swap-animated on the very first frame they were seen"

        # A REAL mid-life switch arms the sprite's swap animation...
        world[1] = P.make_entity(1, P.ENT_REMOTE, 200, 200, 0.0, 100,
                                 P.PS_IDLE, P.WPN_K9, 0, 0)
        posed = view.sync(world)
        assert posed[1][0].rig_weapon == "k9_smg"
        assert posed[1][0].swap_timer > 0, \
            "switching guns did not play the swap animation"

        # ...but coming back from the dead must not swap-dance on respawn.
        v1 = view._views[1]
        v1.swap_timer = 0
        view.sync({1: P.make_entity(1, P.ENT_REMOTE, 200, 200, 0.0, 100,
                                    P.PS_DEAD, P.WPN_K9, 0, 0)})
        view.sync({1: P.make_entity(1, P.ENT_REMOTE, 200, 200, 0.0, 100,
                                    P.PS_IDLE, P.WPN_PISTOL, 0, 0)})
        assert v1.swap_timer == 0, "respawning animated a weapon swap"
        assert v1.rig_weapon == "pistol", \
            "a respawned player kept the gun they died holding"

        # ── reload progress advances instead of freezing on frame one ──
        view2 = ArenaView("yard")
        rel = {0: P.make_entity(0, P.ENT_PLAYER, 100, 100, 0.0, 100,
                                P.PS_RELOADING, P.WPN_PISTOL,
                                P.F_RELOADING, 0)}
        view2.sync(rel)
        v0 = view2._views[0]
        assert v0._arena_reload_total == AR.weapon_stats(P.WPN_PISTOL)["reload"], \
            "the reload clock ignored the weapon's reload length"
        first = v0._arena_reload
        for _ in range(3):
            view2.sync(rel)
        assert v0._arena_reload < first, \
            "the reload animation never advanced past its first frame"
    finally:
        STATE.current_weapon = saved_weapon

    # ── walking sets PS_MOVING; standing still does not ──
    class _Sink(object):
        def _send(self, obj):
            return True

    sess = MatchSession(_Sink(), is_host=True)
    sim = AR.ArenaSim(sess, AR.ARENA_YARD, score_limit=99)
    sim.add_player(2, "WALKER")
    sess._accept_input(P.make_input(1, 1, 0, 0), peer_id=2)
    sim.step()
    ent = next(e for e in sim.snapshot_entities() if e[0] == 2)
    assert ent[6] == P.PS_MOVING, \
        "walking did not report a moving state, so the walk cycle is dead"
    # No new input: the player stops, and the state has to say so, or the
    # walk cycle would keep running while standing still.
    sess._accept_input(P.make_input(2, 0, 0, 0), peer_id=2)
    sim.step()
    ent = next(e for e in sim.snapshot_entities() if e[0] == 2)
    assert ent[6] == P.PS_IDLE, "standing still still reported movement"


def check_arena_os12_is_the_story_rifle():
    """The arena's OS-12 must be the story's OS-12, not a shotgun.

    The campaign's OS-12 is the AK-pattern assault rifle Seby hands you in
    M2 -- entities/weapons.py calls it "OS 12 assault rifle", and m2/draw.py
    carries a note that it is explicitly NOT a shotgun. The arena had
    restated it as an 8-pellet, 6-shell, 300px-range spread weapon, so the
    gun wearing the OS-12 name -- and, after the sprite fix, the OS-12
    rifle model -- fought like a completely different gun. Pin the arena's
    numbers to the campaign's semantics so it cannot drift back.
    """
    from missions import arena as AR
    from net import protocol as P
    from core.state import STATE

    os12 = AR.weapon_stats(P.WPN_OS12)
    pistol = AR.weapon_stats(P.WPN_PISTOL)

    assert os12["name"] == "OS-12"
    # One projectile: a rifle, not a spread weapon.
    assert os12["pellets"] == 1, \
        "the arena OS-12 fires %d pellet(s) -- it is a shotgun again" % (
            os12["pellets"],)
    # Cross-checked against the campaign's own magazine constant rather than
    # a copied literal, so the two can never disagree silently.
    assert os12["mag"] == STATE.os12_mag_size, (
        "arena OS-12 mag %r does not match the campaign os12_mag_size %r"
        % (os12["mag"], STATE.os12_mag_size))
    # Full-auto: it cycles faster than the semi-auto pistol...
    assert os12["cooldown"] < pistol["cooldown"], \
        "the arena OS-12 does not cycle faster than the pistol"
    # ...so its SUSTAINED damage beats the pistol even though one rifle round
    # is weaker than one pistol round (28 vs 34 in the campaign).
    assert (os12["damage"] / os12["cooldown"]) > \
        (pistol["damage"] / pistol["cooldown"]), \
        "the arena OS-12 has no damage advantage over the pistol"
    # ...reaches further (the story's rifle has the longer bullet life)...
    assert os12["range"] > pistol["range"], \
        "the arena OS-12 out-ranges nothing"
    # ...and costs some mobility to carry.
    assert os12["move_mul"] < pistol["move_mul"], \
        "the heavier rifle costs no mobility"


def check_arena_hud_legibility():
    """The MP HUD must stay readable, and the world must not look frozen.

    Two player-reported problems, pinned together because both made the
    arena read as a dead screenshot:

    * The held weapon in the number-key strip was rendered near-black on its
      plate, so the one slot a player most needs to see looked greyed out.
      The ladder is now current > available > locked, by luminance.
    * Crates did bob and pulse, but by 2px under a very dim halo -- which
      reads as motionless. Draw one crate at two animation times and require
      the pixels to actually change.
    """
    from ui.arena_view import ArenaView, _weapon_slot_color, CRATE_SIZE
    from net import protocol as P

    def _lum(c):
        return 0.299 * c[0] + 0.587 * c[1] + 0.114 * c[2]

    cur = _weapon_slot_color(True, False)
    avail = _weapon_slot_color(False, False)
    locked = _weapon_slot_color(False, True)
    assert _lum(cur) > _lum(avail) > _lum(locked), \
        "the weapon strip no longer reads current > available > locked"
    assert _lum(cur) > 150, \
        "the held weapon is darker than mid-grey -- it looks greyed out"

    # ── crates must visibly animate ──
    view = ArenaView("yard")
    size = CRATE_SIZE + 24
    surf = pygame.Surface((size, size))

    def _snapshot(s):
        try:
            return pygame.image.tobytes(s, "RGB")
        except AttributeError:                       # pygame < 2.0
            return pygame.image.tostring(s, "RGB")

    def _frame(t):
        surf.fill((0, 0, 0))
        view._anim_t = t
        view._draw_crate(surf, size // 2, size // 2,
                         (235, 150, 70), "weapon", P.WPN_OS12)
        return _snapshot(surf)

    base = _frame(0)
    assert any(_frame(t) != base for t in range(1, 90)), \
        "a crate changed no pixel over 90 frames -- it is motionless"

    # ── the HUD must be able to draw a named match ──
    # The name, name tag, kill feed, local chip and respawn plate are all new
    # surfaces, and all of them index into tables that arrive from a peer.
    # Rendering one pixel of each is the only thing that proves the indexes
    # line up: a mismatched tuple or a None from a stubbed font raises here
    # rather than on somebody's machine mid-match.
    from core.config import WIDTH as _W, HEIGHT as _H
    hud = ArenaView("yard")
    hud._local_id = 0
    hud._names = {"0": "BIRIBEL", "1": "VOLKOV"}
    hud._teams = {"1": 1}
    world = {
        0: P.make_entity(0, P.ENT_PLAYER, 200, 200, 0.0, 100, P.PS_IDLE,
                         P.WPN_OS12),
        1: P.make_entity(1, P.ENT_REMOTE, 500, 300, 90.0, 40, P.PS_MOVING,
                         P.WPN_K9),
    }
    board = [(1, 6, 4), (0, 5, 5)]
    frame = pygame.Surface((_W, _H))
    # Alive: name tag, kill feed, local chip.
    hud.draw(frame, world, 0, board, mode="TDM", clock=90,
             team_scores={"0": 6, "1": 4}, score_limit=15, phase="playing",
             killfeed=[[2, 1, 0, P.WPN_K9], [40, 0, 0, P.WPN_PISTOL]],
             local_weapon=P.WPN_OS12, local_ammo=6, local_carry=[0, 1])
    alive = _snapshot(frame)
    # Dead: the respawn plate, and the local chip dimmed.
    dead_world = dict(world)
    dead_world[0] = P.make_entity(0, P.ENT_PLAYER, 200, 200, 0.0, 0,
                                  P.PS_DEAD, P.WPN_OS12)
    hud.draw(frame, dead_world, 0, board, mode="TDM", clock=90,
             team_scores={"0": 6, "1": 4}, score_limit=15, phase="playing",
             local_weapon=None, local_ammo=0, local_carry=[],
             respawn={0: 2.4}, respawn_killer=1)
    dead = _snapshot(frame)
    assert dead != alive, "dying changed nothing on screen"

    # An EXPIRED timer must draw no plate at all. Drawing "respawning in 1"
    # for a player who is already back looks like the game has hung, which is
    # the one impression the countdown exists to remove.
    #
    # Tested on _draw_respawn directly rather than by diffing whole frames:
    # the reticle and the crate bob are clock-driven, so two full draw() calls
    # a millisecond apart always differ and a frame diff here would pass no
    # matter what the plate did.
    def _plate_only(respawn):
        probe = pygame.Surface((_W, _H))
        probe.fill((1, 2, 3))
        hud._draw_respawn(probe, respawn, 0, 1)
        return _snapshot(probe)

    blank = _plate_only({})
    assert _plate_only({0: 0.0}) == blank, \
        "an expired respawn timer still drew a countdown plate"
    assert _plate_only({0: -5.0}) == blank, \
        "a negative respawn timer drew a countdown plate"
    # Only a timer for somebody ELSE must not put a card on MY screen.
    assert _plate_only({1: 2.4}) == blank, \
        "another player's countdown drew the local plate"
    assert _plate_only({0: 2.4}) != blank, \
        "a live respawn timer drew nothing at all"

    # A REMOTE player's countdown rides on their corpse, not on a card. The
    # claim is in the HUD docstring, and a client that knows the player who
    # just killed it is back in two seconds can only use that if it is drawn.
    _corpse = pygame.Surface((_W, _H))
    _corpse.fill((1, 2, 3))
    hud.draw(_corpse, dead_world, 0, board, mode="FFA", clock=90,
             local_weapon=P.WPN_OS12, local_ammo=6, local_carry=[0, 1],
             respawn={1: 1.4})
    assert _snapshot(_corpse) != blank, \
        "a remote player's respawn countdown drew nothing"

    # The plate must not cover the local corpse, which the camera keeps centred.
    # If it does, the player cannot see where they died -- and in a deathmatch
    # "where they died" is the only useful thing to look at while dead.
    hud.draw(frame, dead_world, 0, board, mode="TDM", clock=90,
             local_weapon=None, local_ammo=0, local_carry=[],
             respawn={0: 2.4}, respawn_killer=1)
    cx, cy = (int(round(dead_world[0][2] - hud.cam_x)),
              int(round(dead_world[0][3] - hud.cam_y)))
    plate = pygame.Rect(_W // 2 - 190, _H // 2 - 70 - 70, 380, 132)
    assert not plate.collidepoint(cx, cy), \
        "the respawn plate covers the corpse at (%d,%d)" % (cx, cy)


def check_match_intro_transition():
    """The host starts explicitly, and every player stays frozen until GO."""
    from ui.match_screen import MatchScreen, INTRO_SECONDS
    from net import roomcode as _RC

    host = MatchScreen()
    host.open_panel()
    host.players = 2
    host.request_host(0)
    keys = pygame.key.get_pressed()
    idle = (500, 350, False)
    host.update(keys, idle, 1.0 / 60.0)
    port = host.srv.getsockname()[1]
    assert host.waiting_for_player(), "host did not open in the match lobby"
    assert not host._intro_armed and host._intro_left == 0.0, \
        "the intro fired before a single opponent arrived"

    client = MatchScreen()
    client.open_panel()
    client.request_join(_RC.encode("127.0.0.1", port))
    try:
        for _ in range(120):
            host.update(keys, idle, 1.0 / 60.0)
            client.update(keys, idle, 1.0 / 60.0)
            if client.mode == "playing" and client.sess.local_id == 1 \
                    and client._latest_snap_tick is not None:
                break
        assert client.mode == "playing", (
            "loopback join never reached its lobby (status=%r)" % client.status)
        assert host.waiting_for_player() and client.in_match_lobby(), \
            "joining automatically began gameplay"
        assert host.sim.tick == 0, "the waiting lobby advanced the simulation"
        assert not host._intro_armed and not client._intro_armed, \
            "the countdown armed merely because a player joined"

        assert host._begin_countdown(), "host could not explicitly start"
        # First pump delivers the host's phase=COUNTDOWN packet to the joiner.
        for _ in range(3):
            host.update(keys, idle, 1.0 / 60.0)
            client.update(keys, idle, 1.0 / 60.0)
        assert host.session_phase() == client.session_phase() == "countdown", \
            "the host-owned countdown was not synchronized"
        assert host.input_frozen() and client.input_frozen(), \
            "one side accepted gameplay input during the countdown"
        assert host._intro_armed and host._intro_left > 0.0, \
            "the host did not arm its countdown overlay"
        assert client._intro_armed and client._intro_left > 0.0, \
            "the client did not arm its countdown overlay"

        host_pos = tuple(host.sim.players[0][k] for k in ("x", "y"))
        remote_pos = tuple(host.sim.players[1][k] for k in ("x", "y"))
        ammo = {pid: st["ammo"] for pid, st in host.sim.players.items()}

        class _HeldKeys(dict):
            def __missing__(self, key):
                return key == pygame.K_w

        held = _HeldKeys()
        for _ in range(24):
            host.update(held, (500, 350, True), 1.0 / 60.0)
            client.update(held, (500, 350, True), 1.0 / 60.0)
            assert host.session_phase() == client.session_phase() == "countdown", \
                "countdown ended before its configured duration"
            assert host.input_frozen() and client.input_frozen(), \
                "movement/fire was enabled under the intro overlay"
            assert host.sim.tick == 0, \
                "authoritative simulation advanced during the intro"
            assert tuple(host.sim.players[0][k] for k in ("x", "y")) == host_pos, \
                "host moved during the frozen intro"
            assert tuple(host.sim.players[1][k] for k in ("x", "y")) == remote_pos, \
                "remote player moved during the frozen intro"
            assert {pid: st["ammo"] for pid, st in host.sim.players.items()} == ammo, \
                "a player fired during the frozen intro"

        # Idempotent: a duplicate start/countdown signal cannot restart it.
        first_left = host._intro_left
        host._arm_intro()
        assert host._intro_left <= first_left, \
            "re-arming restarted the host countdown"

        # The overlay begins fully black, then disappears after the host's GO.
        surf = pygame.Surface((640, 360))
        surf.fill((30, 60, 90))
        client._intro_left = INTRO_SECONDS
        client._draw_intro(surf)
        r, g, b, _a = surf.get_at((320, 180))
        assert (r, g, b) == (0, 0, 0), \
            "the intro did not fade from black (centre was %r)" % ((r, g, b),)

        for _ in range(240):
            host.update(keys, idle, 1.0 / 60.0)
            client.update(keys, idle, 1.0 / 60.0)
            if host.session_phase() == client.session_phase() == "playing":
                break
        assert host.session_phase() == client.session_phase() == "playing", \
            "host and client did not release the match together"
        assert not host.input_frozen() and not client.input_frozen(), \
            "players remained frozen after the host's GO"
        assert host.sim.tick > 0, "simulation did not resume after GO"
        assert host._intro_left == 0.0 and client._intro_left == 0.0, \
            "intro overlay survived the synchronized transition"
        before = surf.get_at((320, 180))
        client._draw_intro(surf)
        assert surf.get_at((320, 180)) == before, \
            "the intro kept drawing after its clock expired"

        host._teardown()
        assert not host._intro_armed and host._intro_left == 0.0, \
            "leaving a match did not clear the intro state"
    finally:
        client.close()
        host.close()


def check_join_loopback_fallback():
    """A join to an unroutable private address must fall back to loopback.

    Host-and-join-on-one-PC (or a machine whose own LAN IP local_ip() picks
    is a VPN/Hyper-V adapter) is the most common test setup. A listener on
    0.0.0.0 is always reachable at 127.0.0.1, so a private target that
    refuses is retried on loopback before the join is declared failed.
    """
    from ui.match_screen import MatchScreen
    from net import roomcode as _RC
    from net import portmap as _pm

    assert _pm.is_private("192.168.1.42") and not _pm.is_private("82.78.75.76")

    host = MatchScreen()
    host.open_panel()
    host.players = 2
    host.request_host(0)
    keys = pygame.key.get_pressed()
    idle = (500, 350, False)
    host.update(keys, idle, 1.0 / 60.0)
    port = host.srv.getsockname()[1]

    # A private address that will refuse, so the first connect attempt fails.
    client = MatchScreen()
    client.open_panel()
    client.request_join(_RC.encode("10.255.255.1", port))
    try:
        for _ in range(60):
            host.update(keys, idle, 1.0 / 60.0)
            client.update(keys, idle, 1.0 / 60.0)
            if client.mode == "playing" and client.sess.local_id == 1:
                break
        assert client.mode == "playing", (
            "loopback fallback did not connect (status=%r)" % client.status)
        assert client._peer_addr == ("127.0.0.1", port), \
            "fallback did not use loopback: %r" % (client._peer_addr,)
    finally:
        client.close()
        host.close()


def check_client_interpolation_smooth():
    """The client must interpolate every frame, not every packet.

    The host snaps the world forward in 3-tick steps (20 Hz). Sampling at
    the newest snapshot tick made remote players freeze between packets and
    teleport forward on each one, which reads as low FPS. The client now
    advances a 60 Hz render clock, so a player moving 5 px/tick must move
    ~5 px per frame - not 0,0,15.
    """
    from ui.match_screen import MatchScreen
    from net import roomcode as _RC

    host = MatchScreen()
    host.open_panel()
    host.players = 2
    host.request_host(0)
    keys = pygame.key.get_pressed()
    idle = (500, 350, False)
    host.update(keys, idle, 1.0 / 60.0)
    port = host.srv.getsockname()[1]

    client = MatchScreen()
    client.open_panel()
    client.request_join(_RC.encode("127.0.0.1", port))
    try:
        for _ in range(90):
            host.update(keys, idle, 1.0 / 60.0)
            client.update(keys, idle, 1.0 / 60.0)
            if client.mode == "playing" and client.sess.local_id == 1:
                break
        assert client.mode == "playing", "client did not connect"
        assert client.in_match_lobby(), \
            "client did not remain in the lobby before host start"
        assert host._begin_countdown(), "host could not start interpolation test"
        for _ in range(240):
            host.update(keys, idle, 1.0 / 60.0)
            client.update(keys, idle, 1.0 / 60.0)
            if host.session_phase() == client.session_phase() == "playing":
                break
        assert host.session_phase() == client.session_phase() == "playing", \
            "host/client did not reach live play before interpolation test"

        xs = []
        for _ in range(40):
            # Drive the host's local player forward 5 px per sim tick.
            host.sim.players[0]["x"] += 5.0
            host.update(keys, idle, 1.0 / 60.0)
            client.update(keys, idle, 1.0 / 60.0)
            world = client.sess.sample_world() or {}
            if 0 in world:
                xs.append(world[0][2])
        deltas = [xs[i + 1] - xs[i] for i in range(len(xs) - 1)]
        # Skip the startup fill; then the motion must be per-frame smooth.
        tail = deltas[8:]
        assert tail, "not enough samples"
        assert max(tail) < 8.0, (
            "motion steps at packet rate (max frame delta %.1f, want ~5)"
            % max(tail))
        assert any(d > 1.0 for d in tail[:10]), "world is frozen between packets"
    finally:
        client.close()
        host.close()


def check_arena_weapons_and_pickups():
    """Weapons must differ, pickups must work, and guns must be OWNED.

    The arena used to ship exactly one gun (34 damage, forever) and pickups
    that were drawn but never collected -- `pickups()` existed and
    `draw_pickups` painted health packs, but no code ever granted anything.
    Both are invisible in a diff and ruin a match in play.
    """
    from missions import arena as AR
    from net.match import MatchSession
    from net import protocol as P

    class _FC(object):
        def _send(self, obj):
            return True

    # Three genuinely different guns, not three names for one gun.
    assert len(AR.WEAPONS) >= 3, \
        "arena still has %d weapon(s)" % len(AR.WEAPONS)
    for wid, s in AR.WEAPONS.items():
        for key in ("damage", "pellets", "cooldown", "mag", "reload",
                    "range", "spread", "move_mul"):
            assert key in s, "weapon %r is missing %r" % (s.get("name"), key)
        assert s["damage"] > 0 and s["mag"] > 0 and s["reload"] > 0
    fastest = min(AR.WEAPONS, key=lambda w: AR.WEAPONS[w]["cooldown"])
    slowest = max(AR.WEAPONS, key=lambda w: AR.WEAPONS[w]["cooldown"])
    assert fastest != slowest, "every weapon has the same fire rate"

    # A clear lane on row 11 of the Yard (no interior walls).
    lane_y = 11 * 64 + 32
    cs = MatchSession(_FC(), is_host=True, local_id=0)
    sim = AR.ArenaSim(cs, AR.ARENA_YARD, score_limit=99)
    sim.add_player(0, "A")
    sim.add_player(1, "B")
    sim.players[0]["x"], sim.players[0]["y"] = 400.0, lane_y
    sim.players[1]["x"], sim.players[1]["y"] = 100.0, lane_y
    sim.rules.spawned_at[0] = -(10 ** 6)
    sim.rules.spawned_at[1] = -(10 ** 6)
    shooter, target = sim.players[1], sim.players[0]
    seq = [0]

    def fire(ticks, weapon=None):
        for _ in range(ticks):
            cs._accept_input(P.make_input(seq[0], 0, 0, 0.0, P.F_FIRING,
                                          weapon=weapon), peer_id=1)
            seq[0] += 1
            sim.step()

    # Spawn pistol: one clear shot must connect.
    before = target["hp"]
    fire(1)
    assert target["hp"] < before, \
        "a clear pistol shot at 300px did no damage"

    # A weapon the player is NOT carrying must be refused. Otherwise the
    # number keys hand out the rifle for free and no pickup ever matters.
    AR._grant(shooter, P.WPN_K9)
    want = shooter["weapon"]
    cs._accept_input(P.make_input(seq[0], 0, 0, 0.0, 0,
                                  weapon=P.WPN_OS12), peer_id=1)
    seq[0] += 1
    sim.step()
    assert shooter["weapon"] == want, \
        "host equipped a weapon the player never picked up"
    # ...but an owned one must switch.
    fire(1, weapon=P.WPN_PISTOL)
    assert shooter["weapon"] == P.WPN_PISTOL, \
        "host refused to switch to a weapon the player owns"

    # Spread must be able to ACCUMULATE. Recovery runs every tick while
    # growth runs once per shot, so too-fast recovery makes the whole
    # mechanic silently inert -- which is exactly what happened once.
    # Measured with the trigger HELD but firing rate-limited, which is the
    # case that matters: holding the button is how a player actually loses
    # accuracy.
    cs2 = MatchSession(_FC(), is_host=True, local_id=0)
    sim2 = AR.ArenaSim(cs2, AR.ARENA_YARD, score_limit=99)
    sim2.add_player(0, "A")
    sim2.rules.spawned_at[0] = -(10 ** 6)
    st = sim2.players[0]
    seq2 = [0]
    peak = 0.0
    for _ in range(600):
        cs2._accept_input(P.make_input(seq2[0], 0, 0, 0.0, P.F_FIRING),
                          peer_id=0)
        seq2[0] += 1
        sim2.step()
        peak = max(peak, st["spread"])
    assert peak > 1.0, \
        ("spread never accumulated under sustained fire (peak %.2f); "
         "recovery is outrunning growth" % peak)

    # And it must actually come back down once the trigger is released.
    for _ in range(120):
        sim2.step()
    assert st["spread"] < peak * 0.5, \
        ("spread did not recover once the trigger was released "
         "(%.2f of %.2f)" % (st["spread"], peak))

    # Pickups must be GRANTED, with a respawn timer, and must not be
    # collected by somebody standing at full health.
    cs3 = MatchSession(_FC(), is_host=True, local_id=0)
    sim3 = AR.ArenaSim(cs3, AR.ARENA_FOUNDRY, score_limit=99)
    sim3.add_player(0, "A")
    st3 = sim3.players[0]
    hp_pack = [p for p in sim3.pickup_items if p["kind"] == "health"]
    assert hp_pack, "foundry has no health pickup"
    pk = hp_pack[0]
    st3["x"], st3["y"] = pk["x"], pk["y"]
    st3["hp"] = 30
    sim3.step()
    assert st3["hp"] > 30, "walking onto a health pack granted nothing"
    assert pk["ready_at"] > sim3.tick, "a taken pickup did not start a timer"
    st3["hp"] = 30
    sim3.step()
    assert st3["hp"] == 30, "pickup was re-collected during its own timer"

    # Armour must actually reduce damage, or the armour tiles are scenery.
    cs4 = MatchSession(_FC(), is_host=True, local_id=0)
    sim4 = AR.ArenaSim(cs4, AR.ARENA_YARD, score_limit=99)
    sim4.add_player(0, "A")
    sim4.add_player(1, "B")
    sim4.rules.spawned_at[0] = -(10 ** 6)
    sim4.players[0]["armour"] = 100
    hp0 = sim4.players[0]["hp"]
    sim4.damage(0, 60, killer_id=1)
    armoured = hp0 - sim4.players[0]["hp"]
    sim4.players[0]["armour"] = 0
    hp0 = sim4.players[0]["hp"]
    sim4.damage(0, 60, killer_id=1)
    bare = hp0 - sim4.players[0]["hp"]
    assert armoured < bare, \
        "armour did not reduce damage (%d vs %d)" % (armoured, bare)

    # Every map must offer at least one gun, or a match has no loadout.
    for name, rows in AR.ARENAS.items():
        kinds = [k for (_x, _y, k, _v) in AR.pickups(rows)]
        assert "weapon" in kinds, "arena %r offers no weapon pickup" % name
def check_arena_teams_and_rounds():
    """TDM must balance teams, refuse friendly fire, and end on a clock."""
    from missions import arena as AR

    # Balance on join: a player arriving later must land on the smaller side,
    # or one team is permanently short however the players turn up.
    dm = AR.Deathmatch(AR.ARENA_YARD, score_limit=99, mode=AR.MODE_TDM)
    for pid in range(4):
        dm.register(pid)
        dm.teams[pid] = dm.balance_teams()
    sides = [dm.team_of(p) for p in range(4)]
    assert sides.count(AR.TEAM_IPA) == sides.count(AR.TEAM_KRAP) == 2, \
        "four players were not split 2/2: %r" % (sides,)

    # Friendly fire kills the victim but credits nobody. Crediting it pays
    # players for shooting their own side.
    #
    # Balance alternates sides (IPA, KRAP, IPA, KRAP), so the enemy and the
    # teammate are picked by SIDE, not by hardcoded id -- hardcoding them
    # silently turned this into a friendly-fire test and it passed anyway.
    mine = dm.team_of(0)
    enemy = next(p for p in (1, 2, 3) if dm.team_of(p) != mine)
    teammate = next(p for p in (1, 2, 3) if dm.team_of(p) == mine)
    dm.kill(0, enemy, 10)
    assert dm.kills.get(0, 0) == 1, \
        "an enemy kill was not credited: %r" % (dm.kills,)
    assert dm.deaths.get(enemy, 0) == 1, \
        "the enemy was not credited a death: %r" % (dm.deaths,)
    assert dm.team_score(mine) == 1, \
        "team score did not follow the kill: %r" % (mine,)
    dm.kill(0, teammate, 20)
    assert dm.kills.get(0, 0) == 1, \
        "friendly fire was credited as a kill"
    assert dm.deaths.get(teammate, 0) == 1, \
        "friendly fire did not kill the victim: %r" % (dm.deaths,)
    assert dm.team_score(mine) == 1, \
        "friendly fire moved the team score: %r" % (mine,)

    # The score limit must end the round.
    dm2 = AR.Deathmatch(AR.ARENA_YARD, score_limit=2, mode=AR.MODE_TDM)
    dm2.register(0); dm2.register(1)
    dm2.teams = {0: AR.TEAM_IPA, 1: AR.TEAM_KRAP}
    assert dm2.kill(0, 1, 1) is False, "round ended on the first kill"
    assert dm2.kill(0, 1, 2) is True, "score limit did not end the round"
    assert dm2.round_over() and dm2.winner == 0

    # The clock exists at all: without it the leading side just refuses to
    # die and the round never resolves.
    dm3 = AR.Deathmatch(AR.ARENA_YARD, score_limit=999, mode=AR.MODE_TDM)
    dm3.register(0); dm3.register(1)
    dm3.teams = {0: AR.TEAM_IPA, 1: AR.TEAM_KRAP}
    dm3.kill(0, 1, 1)
    assert not dm3.round_over(), "a score-999 round ended after one kill"
    assert AR.ROUND_TICKS > 0, "the round clock is not configured"

    # Intermission must reset the board rather than stranding players.
    dm3.start_intermission(100)
    assert dm3.phase == "intermission"
    dm3.reset_round(100 + AR.INTERMISSION_TICKS)
    assert dm3.phase == "live" and dm3.kills == {} and dm3.round == 2

    # FFA has no sides at all, which is the whole point of the mode.
    dm4 = AR.Deathmatch(AR.ARENA_YARD, score_limit=1, mode=AR.MODE_FFA)
    dm4.register(0)
    assert dm4.team_of(0) == AR.TEAM_NONE
    assert dm4.balance_teams() == AR.TEAM_NONE
    assert dm4.kill(0, 1, 1) is True, "FFA did not honour the score limit"

    # Spawns must not stack. In TDM only opponents decide which spawn is
    # safest, so BOTH members of a team used to be handed the same "furthest
    # from the enemy" point and appeared on top of each other -- which reads
    # as a netcode desync and is not one.
    dm5 = AR.Deathmatch(AR.ARENA_YARD, score_limit=99, mode=AR.MODE_TDM)
    for pid in range(4):
        dm5.register(pid)
        dm5.teams[pid] = dm5.balance_teams()
        dm5.note_position(pid, dm5.respawn_at(pid, 10))
    spots = [(dm5._positions[p][0], dm5._positions[p][1])
             for p in range(4)]
    for i in range(len(spots)):
        for j in range(i + 1, len(spots)):
            d = AR._dist(spots[i], spots[j])
            assert d >= AR.SPAWN_CLEAR_PX - 0.01, (
                "players %d and %d spawned %.0fpx apart (min %.0f): %r"
                % (i, j, d, AR.SPAWN_CLEAR_PX, spots))


def check_client_prediction_is_authoritative():
    """The client must PREDICT its own movement, not wait for the host.

    This is the single biggest feel regression available in the arena. Before
    prediction the client drew its own character out of the same 100 ms-behind
    interpolation buffer as everybody else, so your own movement was always
    a frame and a half late and the crosshair aimed from where you USED to
    be. It looks fine in a diff and is unbearable to play.

    Two things are pinned:
      1. the predictor seeds from the first authoritative snapshot, and
      2. after moving, the predicted position equals the host's authoritative
         position EXACTLY. Any residue means the two ends disagree about
         movement maths, which is the rubber-band bug.
    """
    from ui.match_screen import MatchScreen
    from net import roomcode as _RC

    host = MatchScreen()
    host.open_panel()
    host.players = 2
    host.request_host(0)
    keys = pygame.key.get_pressed()
    idle = (500, 350, False)
    host.update(keys, idle, 1.0 / 60.0)
    port = host.srv.getsockname()[1]

    client = MatchScreen()
    client.open_panel()
    client.request_join(_RC.encode("127.0.0.1", port))
    try:
        # Wait for the slot AND for real snapshots. Breaking as soon as the
        # assign lands tests nothing: the buffer is still empty and the
        # predictor legitimately has nothing to seed from yet.
        for _ in range(400):
            host.update(keys, idle, 1.0 / 60.0)
            client.update(keys, idle, 1.0 / 60.0)
            if client.sess.local_id == 1 and len(client.sess._buf) >= 3:
                break
        assert client.mode == "playing", "client did not connect"
        assert client._pred is not None, "client built no predictor"
        assert client._pred.seeded, \
            "predictor never seeded from the authoritative snapshot"

        class _East(object):
            def __getitem__(self, k):
                return k == pygame.K_d

        worst = 0.0
        for _ in range(90):
            east = _East()
            client.update(east, idle, 1.0 / 60.0)
            host.update(keys, idle, 1.0 / 60.0)
            # Residue after reconciliation must be zero. step_move is shared
            # by both ends, so any non-zero number here is a real divergence.
            auth = host.sim.players[client.sess.local_id]
            worst = max(worst, abs(auth["x"] - client._pred.x)
                        + abs(auth["y"] - client._pred.y))
        assert worst < 0.51, (
            "prediction diverges from the host by %.2f px; the two ends "
            "disagree about movement and this will rubber-band" % worst)
    finally:
        client.close()
        host.close()


def check_hit_marker_decays():
    """Floating "HIT" markers must fade on the client, not hang in the world.

    update_feel() was only called from the host path, so a joiner's own hit
    markers never decayed and stayed pinned in the air. This checks the
    timer itself and that the client update path drives it.
    """
    from ui.arena_view import ArenaView, FLOATER_MAX_FRAMES
    from ui.match_screen import MatchScreen
    from net import roomcode as _RC

    # Unit: a hit creates a marker and update_feel clears it.
    view = ArenaView("yard")
    view.on_local_shot(100.0, 100.0, 0.0, 50.0, True)
    assert view._floaters, "a hit did not create a marker"
    for _ in range(FLOATER_MAX_FRAMES + 5):
        view.update_feel()
    assert not view._floaters, "hit marker did not decay"
    assert view._hit_confirm == 0, "hit-confirm flash did not decay"

    # Integration: _update_client must advance the cosmetic timers.
    host = MatchScreen()
    host.open_panel()
    host.players = 2
    host.request_host(0)
    keys = pygame.key.get_pressed()
    idle = (500, 350, False)
    host.update(keys, idle, 1.0 / 60.0)
    port = host.srv.getsockname()[1]
    client = MatchScreen()
    client.open_panel()
    client.request_join(_RC.encode("127.0.0.1", port))
    try:
        for _ in range(90):
            host.update(keys, idle, 1.0 / 60.0)
            client.update(keys, idle, 1.0 / 60.0)
            if client.mode == "playing":
                break
        assert client.mode == "playing", "client did not connect"
        client.view.on_local_shot(100.0, 100.0, 0.0, 50.0, True)
        assert client.view._floaters, "client hit did not create a marker"
        for _ in range(FLOATER_MAX_FRAMES + 20):
            host.update(keys, idle, 1.0 / 60.0)
            client.update(keys, idle, 1.0 / 60.0)
        assert not client.view._floaters, (
            "client hit marker never decayed - _update_client must call "
            "update_feel()")
    finally:
        client.close()
        host.close()


def check_local_shot_kicks_camera():
    """Firing must move the camera, the way it does in the campaign.

    Guards the arena against quietly regressing to a dead hitscan: a
    private camera lerp looks almost right while silently dropping the
    recoil kick, so shots would land with no screen response at all.
    """
    from core.state import STATE as _STATE
    from ui.arena_view import ArenaView, RECOIL_KICK_PX
    from net import protocol as _P

    v = ArenaView("yard")
    cx, cy = v.map_w / 2.0, v.map_h / 2.0

    def ents(angle=0.0):
        return {0: _P.make_entity(0, _P.ENT_PLAYER, cx, cy, angle, 100,
                                  _P.PS_IDLE, _P.WPN_PISTOL, 0)}

    surface = config.screen
    for _ in range(8):              # let the follow settle
        v.draw(surface, ents(), 0, ())

    # Aim east: the camera must be punched WEST, the opposite direction.
    _STATE.screen_shake = 0
    _STATE.cam_kick_x = 0.0
    _STATE.cam_kick_y = 0.0
    v.draw(surface, ents(0.0), 0, ())
    base = v.cam_x
    v.on_local_shot(cx, cy, 0.0, 120.0, False)
    assert abs(_STATE.cam_kick_x + RECOIL_KICK_PX) < 0.01, \
        "kick not applied along aim: %r" % _STATE.cam_kick_x
    _STATE.screen_shake = 0        # cancel shake, keep the kick
    v.draw(surface, ents(0.0), 0, ())
    assert v.cam_x < base - 1.0, \
        "camera did not recoil (cam_x %.1f -> %.1f)" % (base, v.cam_x)

    # The rest of the shooting feel, all local-only cosmetics.
    casings = len(_STATE.casings)
    v.on_local_shot(cx, cy, 0.0, 120.0, False)
    assert len(_STATE.casings) > casings, "no casing ejected on shot"
    assert v._hit_confirm == 0, "wall hit should not confirm"
    v.on_local_shot(cx, cy, 0.0, 120.0, True)
    assert v._hit_confirm > 0, "player hit did not confirm"
    _STATE.reduced_motion = True
    _STATE.cam_kick_x = _STATE.cam_kick_y = 0.0
    _STATE.screen_shake = 0

    # Remote shot: spawns an in-flight bolt, casing, but no camera kick or hit confirm
    c_count = len(_STATE.casings)
    b_count = len(v._bolts)
    v.on_remote_shot(1, cx, cy, 0.0, 120.0, False)
    assert len(v._bolts) == b_count + 1, "remote shot did not spawn a bolt"
    assert len(_STATE.casings) == c_count + 1, "remote shot did not eject casing"
    assert _STATE.cam_kick_x == 0.0 and _STATE.cam_kick_y == 0.0, "remote shot kicked camera"


def check_match_identity_and_comms():
    """Player names and in-match chat, end to end over a real socket.

    The failure this guards is the one that makes a match feel like a demo:
    eight anonymous colour swatches with no way to talk. Both halves are
    checked against a real host and a real client over loopback, because the
    parts that break are the parts where the two ends disagree -- a name that
    sanitizes differently in the handshake than in the roster, a chat line
    relayed under the sender's claimed name, a kick that arrives as a dead
    socket and gets reported as a network fault.
    """
    import socket as _socket
    from net import protocol as P
    from ui.match_screen import MatchScreen, CHAT_MIN_GAP
    from ui.arena_view import ArenaView
    from missions import arena as AR

    # ── name sanitising ────────────────────────────────────────────────
    # Names are drawn over sprites and into the kill feed, straight off a
    # socket. Control characters and unbounded length are the two ways that
    # stops being true.
    assert P.sanitize_name("  Biribel  ") == "Biribel", \
        "surrounding whitespace survived sanitising"
    assert P.sanitize_name("bad\nname\ttab") == "bad name tab", \
        "a newline did not collapse to one space: %r" % (
            P.sanitize_name("bad\nname\ttab"),)
    assert "\n" not in P.sanitize_name("a\nb"), \
        "a newline survived into a single-line label"
    assert "\x00" not in (P.sanitize_name("a\x00b") or ""), \
        "a NUL byte survived into a rendered label"
    long_name = P.sanitize_name("N" * 500)
    assert long_name is not None and len(long_name) <= P.MAX_NAME_CHARS, \
        f"name was not length-capped: {len(long_name or '')}"
    assert P.sanitize_name(None) is None, "a non-string became a name"
    assert P.sanitize_name("   ") is None, "whitespace-only produced a name"
    assert P.default_name(3) == "P3", "slot fallback is not P<id>"

    # ── the name rides in the join handshake ───────────────────────────
    assert P.join_match_name(P.make_join_match("yard", "Biribel")) == "Biribel", \
        "the join handshake did not carry the name"
    assert P.join_match_name(P.make_join_match("yard")) is None, \
        "a nameless handshake invented a name"
    # A hostile peer naming itself as somebody else must not survive: the host
    # re-sanitizes, and the strip below shows what actually reaches a label.
    assert P.join_match_name(P.make_join_match("yard", "x" * 400)).__len__() \
        <= P.MAX_NAME_CHARS, "a hostile name was not capped"

    # ── chat codec ─────────────────────────────────────────────────────
    assert P.parse_match_chat(P.make_match_chat("gg")) == "gg", \
        "a chat line did not survive its own round trip"
    assert P.make_match_chat("   ") is None, "a blank chat line was put on the wire"
    assert P.parse_match_chat({"t": P.T_MATCH_CHAT, "x": 42}) is None, \
        "a non-string chat body was accepted"
    # The author is the HOST's attribution. A client that puts one in anyway
    # is not believed -- that is the whole point of relaying rather than
    # forwarding, and it is what stops anyone posting as another player.
    spoof = {"t": P.T_MATCH_CHAT, "x": "hi", "by": "ADMIN"}
    assert P.match_chat_author(spoof) == "ADMIN", \
        "author field was not readable at all"
    assert P.parse_match_chat(spoof) == "hi", "body lost its author"

    # ── view name resolution ───────────────────────────────────────────
    view = ArenaView("yard")
    assert view.name_for(7) == "P7", \
        "an unnamed slot rendered something other than its label"
    view._names = {"7": "Biribel"}
    assert view.name_for(7) == "Biribel", "a published name was not used"

    # ── host publishes names and respawn timers ────────────────────────
    sim = AR.ArenaSim.__new__(AR.ArenaSim)
    sim.rules = AR.Deathmatch(AR.ARENA_YARD)
    sim.players = {0: {"id": 0, "nick": "Host",
                       "look": {"palette": "pal_krap", "head": "head_goggles",
                                "finish": {"os12": "os12_blued",
                                           "k9": "k9_standard",
                                           "pistol": "pistol_standard"}}},
                   1: {"id": 1, "nick": ""}}
    sim.tick = 0
    sim.round_started = 0
    sim.pickup_items = []
    sim.finished = False
    sim.match_id = "cafe0001"
    sim.rules.respawn = {1: 90}
    st = sim.match_state()
    assert st["names"]["0"] == "Host", f"host name not published: {st['names']}"
    assert st["looks"]["0"]["palette"] == "pal_krap", \
        f"host did not publish a loadout: {st.get('looks')}"
    assert st["looks"]["1"] == _appearance.DEFAULT, \
        f"a seat with no loadout published {st['looks']['1']!r}"
    # An empty nick must become the slot label, never a blank key the HUD
    # would render as an empty tag.
    assert st["names"]["1"] == "P1", \
        f"an unnamed player was published as {st['names'].get('1')!r}"
    assert abs(st["respawn"]["1"] - 1.5) < 1e-6, \
        f"respawn timer not published in seconds: {st['respawn']}"
    # The packet has to survive the wire with both tables intact.
    wire = P.make_match_state(st)
    back = P.parse_match_state(wire)
    assert back["names"]["0"] == "Host", "names did not survive the wire"
    assert abs(back["respawn"]["1"] - 1.5) < 1e-6, \
        "respawn timer did not survive the wire"
    assert back["looks"]["0"]["head"] == "head_goggles", \
        "a cosmetic loadout did not survive the wire"
    assert back["looks"]["0"]["finish"]["os12"] == "os12_blued", \
        "a weapon finish did not survive the wire"
    assert back["match_id"] == "cafe0001", \
        f"the match token did not survive the wire: {back.get('match_id')!r}"
    # A slot that published nothing still has to resolve to a person, not to
    # an absent key the renderer would have to guess about.
    assert P.join_match_appearance({"t": P.T_JOIN_MATCH}) is None, \
        "a handshake with no loadout should read as nothing-claimed"
    assert _appearance.normalize(None) == _appearance.DEFAULT, \
        "nothing-claimed must resolve to the free default"
    # A hostile rules packet must not be able to park a huge countdown, a
    # paragraph name, or somebody's entire catalog on someone's screen.
    hostile = P.parse_match_state(P.encode and {
        "t": P.T_MATCH_STATE, "round": 1, "clock": 1,
        "names": {"0": "N" * 900}, "respawn": {"0": 1e9},
        "looks": {"0": {"palette": "p" * 900, "head": {"nested": 1},
                        "finish": [1, 2, 3]}}})
    assert len(hostile["names"]["0"]) <= P.MAX_NAME_CHARS, \
        "hostile name not capped on the way in"
    assert hostile["respawn"]["0"] <= P.MAX_RESPAWN_SECONDS, \
        "hostile respawn timer not capped on the way in"
    # The bound that matters for cosmetics is that a peer cannot put anything
    # it wants onto an opponent's sprite: an over-long identifier is truncated
    # here and then refused by the catalog where the sprite is built.
    assert len(hostile["looks"]["0"]["palette"]) <= P.APPEARANCE_ID_CHARS, \
        "hostile palette id not capped on the way in"
    assert "head" not in hostile["looks"]["0"], \
        "a non-string head id was allowed onto the wire table"
    assert _appearance.normalize(hostile["looks"]["0"]) == _appearance.DEFAULT, \
        "a junk loadout resolved to something other than the default"

    # ── live host + client: names, chat, kick ──────────────────────────
    host = MatchScreen()
    host.open_panel()
    host.players = 2
    host.player_name = "HOSTNAME"
    host.request_host(0)
    keys = pygame.key.get_pressed()
    idle = (500, 350, False)
    host.update(keys, idle, 1.0 / 60.0)
    assert host.mode == "hosting", "host did not start: " + str(host.status)
    assert host.players == 2, "player count wrong"

    client = MatchScreen()
    client.open_panel()
    client.player_name = "JOINER"
    client.request_join("127.0.0.1:%d" % host.srv.getsockname()[1])
    try:
        for _ in range(180):
            host.update(keys, idle, 1.0 / 60.0)
            client.update(keys, idle, 1.0 / 60.0)
            if client.mode == "playing" and client._match_state.get("names"):
                break
        assert client.mode == "playing", \
            "client never joined: %r" % (client.status,)
        assert client.sess.local_id == 1, "client never learned its slot"
        assert client._match_state["names"].get("1") == "JOINER", \
            "the joiner's name never reached its own client: %r" % (
                client._match_state.get("names"),)
        assert client.name_of(1) == "JOINER", \
            "the joiner cannot resolve its own name for the HUD"

        # ── the countdown is a floor, not a suggestion ────────────────
        # A rules packet must never be able to lengthen a respawn clock that
        # is already running: packets are sampled at different points in the
        # same timer, and a clock that jumps up reads as the host resetting
        # you mid-respawn.
        client._respawn = {1: 2.0}
        client._sync_respawn({"respawn": {"1": 2.9}})
        assert client._respawn[1] == 2.0, \
            "a rules packet lengthened a running countdown"
        # But a countdown that has run out while the host still says there is
        # time IS restarted, otherwise a dropped packet leaves a dead player
        # with no clock at all.
        client._respawn = {}
        client._sync_respawn({"respawn": {"1": 2.9}})
        assert client._respawn[1] == 2.9, \
            "an expired countdown was not restarted from the host"
        client._tick_respawn(2.9)
        assert 1 not in client._respawn, "countdown did not expire"
        client._respawn = {}

        # ── chat: client -> host -> everyone, attributed by the host ──
        client._chat_input = "on your left"
        client.toggle_chat()
        assert client._composing, "the composer did not open"
        client.send_match_chat()
        assert not client._composing, "sending did not close the composer"
        assert client._chat_input == "", "the composer was not cleared"
        for _ in range(12):
            host.update(keys, idle, 1.0 / 60.0)
            client.update(keys, idle, 1.0 / 60.0)
        texts = [row[2] for row in client._chat_messages]
        assert "on your left" in texts, \
            "the client's chat line never came back: %r" % (client._chat_messages,)
        authors = [row[1] for row in client._chat_messages]
        assert "JOINER" in authors, \
            "the relay attributed the line to the wrong player: %r" % (authors,)
        # The host's transcript must agree, or the two players are reading
        # different conversations.
        host_texts = [row[2] for row in host._chat_messages]
        assert "on your left" in host_texts, \
            "the host never recorded the relayed line: %r" % (host._chat_messages,)
        assert "JOINER" in [row[1] for row in host._chat_messages], \
            "the host attributed the line to the wrong player"

        # The host answers, and the line is attributed to the host.
        host._chat_input = "copy"
        host.send_match_chat()
        for _ in range(12):
            client.update(keys, idle, 1.0 / 60.0)
        assert "copy" in [row[2] for row in client._chat_messages], \
            "the host's own chat line never reached the client"
        assert "HOSTNAME" in [row[1] for row in client._chat_messages], \
            "the host's line was misattributed"

        # ── rate limit ────────────────────────────────────────────────
        # One client must not be able to fill everybody else's screen. The
        # floor is per sender, so a second player is unaffected.
        before = len(host._chat_messages)
        peer = host.peers[0]
        host._peer_chat_last[peer.player_id] = time.monotonic()
        host._relay_match_chat(peer, "spamming")
        assert len(host._chat_messages) == before, \
            "the chat rate floor let a second line straight through"

        # ── kick ──────────────────────────────────────────────────────
        assert host.kick_peer(peer, "go outside"), "kick_peer refused"
        assert host.peers == [], "the kicked peer was still on the roster"
        assert 1 not in host.sim.players, "the kicked player was still simulated"
        # The client must LEARN it was kicked. A closed socket is
        # indistinguishable from the client's own wifi dropping, and the
        # player is told to go check their router for something a human did.
        for _ in range(20):
            client.update(keys, idle, 1.0 / 60.0)
            if client.mode != "playing":
                break
        assert client.mode != "playing", \
            "the client stayed in a match it had been removed from"
        assert "outside" in client.status, \
            "the kick reason was lost: %r" % (client.status,)

        # The host keeps the room. Throwing away the room code that was just
        # read out into a group chat would be the wrong trade.
        assert host.mode == "hosting", "the host left on kicking a player"
        assert host.waiting_for_player(), \
            "the host did not return to the lobby after a kick"
    finally:
        client.close()
        host.close()


def check_match_screen_roster():
    """Match entry panel, hosting, and a 3+ player roster over real sockets.

    The roster is the part most likely to rot: a slot is handed out at
    accept time and freed on disconnect, and if those two ever disagree a
    joiner inherits a slot whose old owner is still sending input. This
    drives the real accept/read path rather than faking it.
    """
    import socket as _socket
    socket = _socket
    from ui.match_screen import MatchScreen
    from net import protocol as _P

    # The button that opens the panel must line up with the one that is
    # drawn, otherwise it looks clickable and does nothing.
    rect = menu.enter_arena_rect()
    assert menu.enter_arena_hit(rect.center), "arena button hit test failed"
    assert not menu.enter_arena_hit((rect.x - 40, rect.y)), \
        "arena button hit test is too generous"

    m = MatchScreen()
    m.open_panel()
    m.map_name = "crossfire"
    m.players = 4
    m.request_host(0)                 # port 0 = ephemeral, safe in tests
    m.update(pygame.key.get_pressed(), (0, 0, False), 1.0 / 60.0)
    assert m.mode == "hosting", "did not enter hosting: " + str(m.status)
    assert m.sim.map_name == "crossfire", "map choice was ignored"
    assert m.players == 4, "player count choice was ignored"
    assert sorted(m.sim.players) == [0], "host slot missing"

    port = m.srv.getsockname()[1]
    conns = []
    try:
        for _ in range(3):
            c = _socket.create_connection(("127.0.0.1", port), timeout=5)
            c.setblocking(False)
            # Announce as a match client, or the host keeps it unverified.
            c.sendall(_P.encode(_P.make_join_match()))
            conns.append(c)
            # One update per accept: the host accepts at most one per frame.
            for _ in range(6):
                m.update(pygame.key.get_pressed(), (0, 0, False), 1.0 / 60.0)
        # Let a few frames pass so the sim advances with players present.
        for _ in range(10):
            m.update(pygame.key.get_pressed(), (0, 0, False), 1.0 / 60.0)

        assert len(m.peers) == 3, "expected 3 peers, got %d" % len(m.peers)
        ids = sorted(p.player_id for p in m.peers)
        assert ids == [1, 2, 3], "player ids not contiguous: %r" % ids
        assert sorted(m.sim.players) == [0, 1, 2, 3], \
            "sim roster wrong: %r" % sorted(m.sim.players)
        # Every peer must be sent its own slot (assign) and then snapshots it
        # can actually decode. Snapshots go out every third sim tick, so allow
        # a real interval rather than assuming one frame is enough.
        for i, c in enumerate(conns):
            c.settimeout(3.0)
            buf = b""
            got_assign = None
            snap = None
            while snap is None:
                data = c.recv(65536)
                assert data, "host sent nothing to a joined player"
                buf += data
                for line in buf.split(b"\n"):
                    if not line.strip():
                        continue
                    msg = _P.decode(line)
                    aid = _P.parse_assign(msg)
                    if aid is not None:
                        got_assign = aid
                        # The host's map must be announced with the slot.
                        assert _P.assign_map(msg) == m.map_name, \
                            "assign did not carry the host's map"
                        continue
                    snap = _P.parse_snapshot(msg)
                    if snap is not None:
                        break
            assert snap is not None, "undecodable snapshot on the wire"
            # conns are in accept order, so slots are 1, 2, 3.
            assert got_assign == i + 1, (
                f"client {i} assigned {got_assign}, expected {i + 1}")

        # A disconnect must free exactly that player's slot. Shut down from
        # the client end, which is what a real departure looks like: the
        # host sees EOF on recv. Closing the host's own socket object is a
        # different (also handled) path, tested separately.
        victim = conns.pop(1)
        victim.shutdown(socket.SHUT_RDWR)
        victim.close()
        for _ in range(6):
            m.update(pygame.key.get_pressed(), (0, 0, False), 1.0 / 60.0)
        assert 2 not in m.sim.players, "disconnected player still simulated"
        assert len(m.peers) == 2, "peer not removed: %d" % len(m.peers)
        # And the freed slot must be reusable by the next joiner.
        c = _socket.create_connection(("127.0.0.1", port), timeout=5)
        c.sendall(_P.encode(_P.make_join_match()))
        conns.append(c)
        for _ in range(6):
            m.update(pygame.key.get_pressed(), (0, 0, False), 1.0 / 60.0)
        assert 2 in m.sim.players, "freed slot was not reused"
    finally:
        for c in conns:
            try:
                c.close()
            except OSError:
                pass
        m.close()
    assert m.mode == "closed", "close() did not reset mode"
    assert m.sim is None and m.srv is None, "close() leaked state"


def check_match_panel_draw():
    clear_screen()
    from ui.match_screen import MatchScreen
    m = MatchScreen()
    m.open_panel()
    m.address = "127.0.0.1:27015"
    m.draw_panel(config.screen)

    # A map's seat cap must pull the player count down with it, or a host
    # could try to seat 8 on Crossfire's four spawns.
    m.players = 8
    m.map_name = "crossfire"
    m.open_panel()
    assert m.players == 4, "crossfire cap not enforced on map change: %r" % m.players
    m.draw_panel(config.screen)

    # JOIN must resolve a room code to the host address it encodes.
    from net import roomcode as _RC
    m.request_join(_RC.encode("82.78.75.76", 27015))
    assert m._pending and m._pending[0] == ("join", ("82.78.75.76", 27015)), \
        "room code not resolved on join: %r" % (m._pending,)
    m._pending = []

    # Ctrl+V must paste into the room-code box. A paste is an SDL TEXTINPUT
    # event, not a keypress, so the KEYDOWN.unicode path never saw it and
    # Ctrl+V did nothing until the clipboard was read explicitly.
    import ui.match_screen as _ms
    _orig_clip = _ms.clipboard_text
    _ms.clipboard_text = lambda max_len=512: "ACAR-A974P-K39GWZ"
    try:
        m.address = ""
        m.selected_field = "address"
        _paste = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_v,
                                    mod=pygame.KMOD_CTRL, unicode="")
        assert m.handle_event(_paste, (0, 0)) is True, "Ctrl+V was not consumed"
        assert m.address == "ACAR-A974P-K39GWZ", \
            "Ctrl+V did not paste: %r" % (m.address,)
        m.request_join()
        assert m._pending and m._pending[0] == ("join", ("82.78.75.76", 27015)), \
            "pasted room code did not resolve: %r" % (m._pending,)
    finally:
        _ms.clipboard_text = _orig_clip
    m._pending = []

    m.close()


def check_server_browser_servers_draw():
    clear_screen()
    if hasattr(menu, "switch_mp_tab"):
        menu.switch_mp_tab("SERVERS")
    menu.draw_menu_background()
    menu.draw_server_browser(-1, False, "")


def check_server_browser_connections_draw():
    clear_screen()
    if hasattr(menu, "switch_mp_tab"):
        menu.switch_mp_tab("CONNECTIONS")
    menu.draw_menu_background()
    menu.draw_server_browser(-1, False, "")

    # Restore default tab.
    if hasattr(menu, "switch_mp_tab"):
        menu.switch_mp_tab("SERVERS")


def check_notebook_inspection_draw():
    clear_screen()
    gc.draw_notebook_inspection()


def check_safe_keypad_draw():
    clear_screen()

    setattr(gc, "safe_keypad_active", True)
    setattr(gc, "safe_keypad_code", "")
    setattr(gc, "safe_keypad_target", "742")
    setattr(gc, "safe_keypad_callback", None)

    gc.draw_safe_keypad()

    setattr(gc, "safe_keypad_active", False)


def check_desk_note_draw():
    clear_screen()

    setattr(
        gc,
        "active_read_note",
        "TEST NOTE:\nThis is a smoke-test note.\nPress SPACE to close.",
    )

    gc.draw_desk_note()

    setattr(gc, "active_read_note", None)


def check_cutscene_draw():
    clear_screen()

    if not hasattr(gc, "cutscene1_shots"):
        raise RuntimeError("gc.cutscene1_shots missing")

    shot = gc.cutscene1_shots[0]

    gc.draw_cutscene_scene(config.screen, shot, 0)
    gc.draw_dialogue_box(
        config.screen,
        shot.get("speaker", "NARRATOR"),
        shot.get("text", ""),
        min(20, len(shot.get("text", ""))),
        len(shot.get("text", "")),
    )


def check_start_mission():
    gc.start_mission()

    if getattr(gc, "player", None) is None:
        raise RuntimeError("gc.start_mission() did not create player")


def check_game_update():
    gc.game_update(EmptyKeys())


def check_game_draw():
    clear_screen()

    fcx = getattr(gc, "camera_x", 0)
    fcy = getattr(gc, "camera_y", 0)

    gc.game_draw(fcx, fcy)


def check_walking_sim_start_update_draw():
    clear_screen()

    gc.start_walking_sim()
    gc.update_walking_sim(EmptyKeys())
    gc.draw_walking_sim()


def check_pause_draw():
    clear_screen()
    menu.draw_pause_menu()


def check_death_draw():
    clear_screen()

    if hasattr(menu, "reset_death_animation"):
        menu.reset_death_animation()

    menu.draw_death_screen()


def check_molotov_update_path():
    """Catches missing _spawn_molotov_fire import in mission.py."""
    gc.start_mission()
    setattr(gc, "player_bottles", 1)
    gc.handle_throw_bottle()

    for _ in range(45):
        gc.game_update(EmptyKeys())


def check_mission2_molotov_update_path():
    """Mission 2 must share Mission 1's molotov flight + fire implementation.

    Catches a regression where M2 stops routing through
    entities.weapons.update_molotovs (e.g. a stale private copy) - the
    throw must still detonate into a live fire zone.
    """
    gc.start_mission2()
    setattr(gc, "player_bottles", 1)
    gc.handle_throw_bottle()

    if not gc.thrown_bottles:
        raise RuntimeError("mission 2 throw produced no bottle in flight")

    for _ in range(35):  # bottle lands at ~frame 29 (speed 0.035/frame)
        gc.game_update(EmptyKeys())

    if not gc.molotov_fires:
        raise RuntimeError("mission 2 molotov never produced a fire")

    gc.game_draw(gc.camera_x, gc.camera_y)


def check_mission_draw_story_characters():
    """Catches missing draw_volkov / draw_commander imports."""
    gc.start_mission()

    if getattr(gc, "volkov_pos", None) is None:
        raise RuntimeError("volkov_pos missing")

    vx, vy = gc.volkov_pos
    gc.game_draw(vx - config.WIDTH // 2, vy - config.HEIGHT // 2)


def check_walking_dialogue_draw():
    """Catches missing draw_dialogue_box import in walking_sim.py."""
    gc.start_walking_sim()

    setattr(gc, "walk_dialogue_active", True)
    setattr(gc, "walk_dialogue_speaker", "SYSTEM")
    setattr(gc, "walk_dialogue_text", "Smoke test walking dialogue.")
    setattr(gc, "walk_dialogue_char_idx", 10)

    gc.draw_walking_sim()

    setattr(gc, "walk_dialogue_active", False)


def check_mission3_chair_break_cutscene():
    """Drives the Mission 3 chair-break cutscene end-to-end and asserts the
    in-cell state mutations fire at the Crack shot, the cutscene clock
    returns to -1, and the objective updates. (Spec §8.)
    """
    from missions import m3 as mission3
    from core.state import STATE

    # Start Mission 3, then jump straight into the breakout: the chair-break
    # cutscene is gated on STAGE_BREAKOUT + mission3_chair_break_anim == 0.
    gc.start_mission3()
    STATE.mission3_stage = mission3.STAGE_BREAKOUT
    STATE.mission3_chair_broken = False
    STATE.player_disarmed = True
    STATE.mission3_weapon = "none"
    STATE.mission3_chair_break_anim = 0

    cb_end = mission3._CB_END
    crack = mission3._CB_SHOT2

    # Run enough frames to clear the whole cutscene. We cap at cb_end + a
    # generous margin so a logic bug (counter never reaching _CB_END) surfaces
    # instead of looping forever.
    for _ in range(cb_end + 60):
        gc.game_update(EmptyKeys())
        if getattr(STATE, "mission3_chair_break_anim", -1) < 0:
            break

    # State mutations flipped at the Crack shot must hold after the cutscene.
    assert getattr(STATE, "mission3_chair_broken", False), \
        "mission3_chair_broken did not flip True during the chair-break cutscene"
    assert not getattr(STATE, "player_disarmed", True), \
        "player_disarmed was not cleared during the chair-break cutscene"
    assert getattr(STATE, "mission3_weapon", "none") == "chair_leg", \
        "mission3_weapon was not granted as 'chair_leg' during the cutscene"
    # Cutscene clock returned to -1 (movement unlocks) and objective updated.
    assert getattr(STATE, "mission3_chair_break_anim", -1) < 0, \
        "chair-break cutscene clock did not return to -1 at _CB_END"
    assert mission3._objective == \
        "Sharpen the chair leg at the drain. Volkov holds the door.", \
        "objective text was not updated after the chair-break cutscene"

    # Sanity: the Crack boundary used by the dispatcher is the canonical
    # cutscenes.CB_SHOT2 value - keeps the art/timing and the logic in sync.
    import cutscenes
    assert crack == cutscenes.CB_SHOT2


def check_mission3_chair_break_shots_render():
    """Each cutscenes._draw_cb_* shot must render without raising on a
    representative `t` in its shot's range, and game_draw must take the
    cutscene branch without crashing (covers the dispatcher + the ③→④
    cross-dissolve). (Spec §8.)
    """
    import cutscenes
    from missions import m3 as mission3
    from core.state import STATE

    # Build a stand-in cell buffer the shots can composite onto. It mimics
    # the real cell's dominant colors (concrete wall / floor / metal chair)
    # so the readability checks below can confirm the shots USE the cell
    # palette rather than an invented one.
    W, H = config.WIDTH, config.HEIGHT
    cell_surf = pygame.Surface((W, H))
    cell_surf.fill((54, 54, 52))                       # concrete wall C
    pygame.draw.rect(cell_surf, (32, 33, 33),          # floor "."
                     (0, H // 2, W, H - H // 2))
    # Metal chair blob at center (seat_col / seat_dark).
    pygame.draw.rect(cell_surf, (28, 26, 24),
                     (W // 2 - 18, H // 2 - 9, 36, 18))
    pygame.draw.rect(cell_surf, (42, 40, 36),
                     (W // 2 - 16, H // 2 - 7, 32, 14))
    cx, cy = W // 2, H // 2

    # Direct shot draws at representative per-shot frame counters.
    def run_shot(fn, t):
        clear_screen()
        fn(config.screen, t, cell_surf, cx, cy)

    run_shot(cutscenes._draw_cb_strain, 0)
    run_shot(cutscenes._draw_cb_strain, cutscenes.CB_SHOT1_DUR // 2)
    run_shot(cutscenes._draw_cb_strain, cutscenes.CB_SHOT1_DUR - 1)

    run_shot(cutscenes._draw_cb_crack, 0)            # frame-0 white flash
    run_shot(cutscenes._draw_cb_crack, 5)
    run_shot(cutscenes._draw_cb_crack, cutscenes.CB_SHOT2_DUR - 1)

    run_shot(cutscenes._draw_cb_grab, 0)
    run_shot(cutscenes._draw_cb_grab, cutscenes.CB_SHOT3_DUR // 2)
    run_shot(cutscenes._draw_cb_grab, cutscenes.CB_SHOT3_DUR - 1)

    run_shot(cutscenes._draw_cb_ready, 0)
    run_shot(cutscenes._draw_cb_ready, cutscenes.CB_SHOT4_DUR // 2)
    run_shot(cutscenes._draw_cb_ready, cutscenes.CB_SHOT4_DUR - 1)  # final fade

    # Shared scaffolding helpers.
    cutscenes._cb_letterbox(config.screen)
    op = cutscenes._cb_frame(config.screen, 10, 50)
    assert 0.0 <= op <= 1.0

    # Readability check: the Crack shot at t=70 (authored pieces at peak
    # travel) must actually contain the metal/splinter palette (proves the
    # shot matches the cell, not an invented wood palette) and have
    # subject-region contrast (std-dev > 25) so it isn't a flat blob.
    import statistics as _st
    run_shot(cutscenes._draw_cb_crack, 70)
    px = pygame.surfarray.array3d(config.screen)
    region = px[cx - 60:cx + 60, cy - 60:cy + 60]   # chair-center 120x120
    flat = region.reshape(-1, 3).tolist()
    present_colors = set()
    for r, g, b in flat[::7]:
        present_colors.add((r, g, b))
    # Look for any pixel within ~12 of the metal / splinter / edge colors.
    def near(col, target, tol=14):
        return all(abs(col[i] - target[i]) <= tol for i in range(3))
    metal_targets = [cutscenes.CB_METAL, cutscenes.CB_METAL_DARK,
                     cutscenes.CB_METAL_EDGE, cutscenes.CB_SPLINTER,
                     cutscenes.CB_SPLINTER_HI]
    has_metal = any(any(near(c, m) for c in present_colors) for m in metal_targets)
    assert has_metal, \
        "Crack shot region does not contain the cell's metal/splinter palette"
    lum = [(r + g + b) // 3 for r, g, b in flat]
    sd = _st.pstdev(lum)
    assert sd > 4, f"Crack shot subject region too flat (std-dev={sd:.1f}, need >4)"

    # game_draw cutscene branch: drive the clock across every shot boundary
    # (incl. the ③→④ cross-dissolve window) and the final frame.
    gc.start_mission3()
    STATE.mission3_stage = mission3.STAGE_BREAKOUT
    STATE.mission3_chair_broken = False
    STATE.player_disarmed = True
    STATE.mission3_weapon = "none"
    # Sample one frame per shot + each transition boundary.
    sample_frames = [
        0,
        mission3._CB_SHOT1_DUR // 2,
        mission3._CB_SHOT2 - 1,          # last strain frame
        mission3._CB_SHOT2,              # crack, frame 0 (flash + mutations)
        mission3._CB_SHOT2 + 5,
        mission3._CB_SHOT3 - 1,          # last crack frame
        mission3._CB_SHOT3,              # grab start
        mission3._CB_SHOT4 - 1,          # last grab frame
        mission3._CB_SHOT4,              # ready start (cross-dissolve frame 0)
        mission3._CB_SHOT4 + 6,          # mid cross-dissolve
        mission3._CB_END - 1,            # final fade-out frame
    ]
    fcx = getattr(gc, "camera_x", 0)
    fcy = getattr(gc, "camera_y", 0)
    for t in sample_frames:
        STATE.mission3_chair_break_anim = t
        gc.game_draw(fcx, fcy)
        pygame.event.pump()
        pygame.display.flip()
    # Restore quiescent state.
    STATE.mission3_chair_break_anim = -1


def check_game_core_facade_state():
    """Checks that game_core still exposes old global-style names.

    This is especially useful if you use the proxy facade approach.
    """
    setattr(gc, "show_minimap", True)

    if getattr(gc, "show_minimap") is not True:
        raise RuntimeError("gc.show_minimap did not round-trip correctly")

    setattr(gc, "show_minimap", False)

    if getattr(gc, "show_minimap") is not False:
        raise RuntimeError("gc.show_minimap write failed")


# ── Save system checks (run against the temp SAVE_FILE patched in above) ──

def _reset_save_store():
    _save_system.save_data(_save_system._default_data())
    _save_system._current_slot = 0


def check_save_roundtrip_flags_merged():
    """start_new_campaign → save_mission_complete must merge, not discard."""
    _reset_save_store()
    _save_system.select_slot(0)
    _save_system.start_new_campaign(0)
    slot = _save_system.get_slot(0)
    assert slot["occupied"], "new campaign slot not occupied"
    assert slot["flags"].get("mission1_started"), "mission1_started missing"
    assert slot["progress"] == "walk", "new campaign should start at walk"

    assert _save_system.save_mission_complete_record(
        "MISSION1", "01:23", stats={"kills": 3}
    )
    slot = _save_system.get_slot(0)
    assert slot["last_completed_mission"] == "MISSION_1"
    assert slot["total_time"] == "01:23"
    assert slot["flags"].get("mission1_started"), "prior flags must survive"
    assert slot["flags"].get("mission1_complete"), "new flags missing"
    assert slot["stats"]["kills"] == 3


def check_save_mission3_record():
    """Mission 3 completions must save as MISSION_3 (regression: saved as M1)."""
    _reset_save_store()
    rec = _save_system.mission_complete_record("MISSION3", "10:00", stats={})
    assert rec is not None, "MISSION3 must map to a record"
    assert rec["mission_id"] == "MISSION_3"
    assert "Vostral" in rec["label"]
    assert rec["flags"].get("mission3_complete")

    _save_system.select_slot(1)
    _save_system.start_new_campaign(1)
    assert _save_system.save_mission_complete_record(
        "MISSION3", "10:00", stats={"rank": "S"}
    )
    slot = _save_system.get_slot(1)
    assert slot["last_completed_mission"] == "MISSION_3"
    assert slot["flags"].get("mission3_complete")
    assert slot["stats"]["rank"] == "S"

    # Unknown mission key must refuse to write (never clobber a slot).
    before = _save_system.get_slot(1)["last_completed_mission"]
    assert _save_system.save_mission_complete_record("MISSION_X", "00:00") is False
    assert _save_system.get_slot(1)["last_completed_mission"] == before


def check_save_corrupt_recovery():
    """A corrupt main file must recover from .bak instead of wiping slots."""
    import json as _json

    _reset_save_store()
    _save_system.select_slot(2)
    _save_system.start_new_campaign(2)
    good = _save_system.load_data()
    with open(_save_system.SAVE_FILE + ".bak", "w", encoding="utf-8") as f:
        _json.dump(good, f)
    with open(_save_system.SAVE_FILE, "w", encoding="utf-8") as f:
        f.write("{ this is not json")

    recovered = _save_system.load_data()
    assert recovered["slots"][2]["occupied"], "backup did not recover the save"
    _save_system.save_data(recovered)  # restore a clean main file


def check_save_current_slot_persist():
    _reset_save_store()
    _save_system.select_slot(0)
    _save_system.start_new_campaign(0)
    _save_system.select_slot(2)
    import json as _json

    with open(_save_system.SAVE_FILE, "r", encoding="utf-8") as f:
        data = _json.load(f)
    assert data.get("current_slot") == 2, "current_slot not persisted"


def check_save_progress_marker():
    """Progress writes only on occupied slots; round-trips through load."""
    _reset_save_store()
    _save_system.set_slot_progress("m1")  # empty slot → no-op
    assert not _save_system.get_slot(0)["occupied"], "phantom save created"
    assert _save_system.get_slot(0)["progress"] == ""

    _save_system.select_slot(0)
    _save_system.start_new_campaign(0)
    _save_system.set_slot_progress("m1")
    assert _save_system.get_slot(0)["progress"] == "m1"


def check_save_atomic_no_tmp():
    _reset_save_store()
    _save_system.select_slot(0)
    _save_system.start_new_campaign(0)
    assert not os.path.exists(_save_system.SAVE_FILE + ".tmp"), \
        "temp file left behind after atomic write"
    assert os.path.exists(_save_system.SAVE_FILE + ".bak"), \
        "backup not created"


def check_settings_preserve_omitted_keys():
    """save() must not drop keys the caller's dict omits (ambience_layers)."""
    ss = _settings_store
    ss.save({"ambience_layers": False})
    assert ss.load()["ambience_layers"] is False

    ss.save({"master_volume": 42})  # omits ambience_layers entirely
    loaded = ss.load()
    assert loaded["ambience_layers"] is False, "omitted key was dropped"
    assert loaded["master_volume"] == 42
    assert not os.path.exists(ss.SAVE_FILE + ".tmp"), "settings tmp left behind"


def check_mission3_broadcast_world_build():
    """Broadcast Wing map builds with spawn, uplink, gate doors, pickups."""
    from missions.m3 import world as _m3_world
    from missions.m3 import maps as _m3_maps
    from missions.m3.maps import MISSION3_BROADCAST_MAP
    from missions.m3.meta import BCAST_MAP_W, BCAST_MAP_H

    assert len(MISSION3_BROADCAST_MAP) == BCAST_MAP_H, "broadcast map height wrong"
    assert all(len(row) == BCAST_MAP_W for row in MISSION3_BROADCAST_MAP), "broadcast map width wrong"

    from core.state import STATE
    old_map = _m3_maps.MISSION3_MAP
    old_stage = getattr(STATE, "mission3_stage", None)
    try:
        _m3_world._build_broadcast_world()
        assert _m3_maps.MISSION3_MAP is MISSION3_BROADCAST_MAP, "broadcast map not bound"
        assert len(STATE.walls) > 0, "no walls built"
        assert len(STATE.doors) > 0, "no doors built"
        assert len(STATE.pickups) > 0, "no pickups placed"
        assert STATE.player is not None, "player missing"
        assert not STATE.player_dead, "player dead on build"
    finally:
        _m3_maps.MISSION3_MAP = old_map
        if old_stage is not None:
            STATE.mission3_stage = old_stage


def check_mission3_broadcast_wave_spawn():
    """Broadcast waves spawn enemies with correct labels."""
    from missions.m3 import systems as _m3_systems
    from core.state import STATE

    old_enemies = STATE.enemies[:]
    STATE.enemies = []
    try:
        _m3_systems._spawn_bcast_wave(1)
        assert len(STATE.enemies) == 3, "wave 1 should spawn 3 enemies"
        labels = [_m3l(e).text for e in STATE.enemies]
        assert all("bcast_corridor" in lbl for lbl in labels), "wave 1 labels wrong"

        STATE.enemies = []
        _m3_systems._spawn_bcast_wave(2)
        assert len(STATE.enemies) == 4, "wave 2 should spawn 4 enemies"

        STATE.enemies = []
        _m3_systems._spawn_bcast_wave(3)
        assert len(STATE.enemies) == 5, "wave 3 should spawn 5 enemies"
    finally:
        STATE.enemies = old_enemies


def check_mission3_broadcast_upload():
    """Station PC: [E] boots the M3 upload OS and DONE hands off to the ending."""
    from missions.m3 import flow as _m3_flow
    from missions.m3 import systems as _m3_systems
    from missions.m3 import world as _m3_world
    from missions.m3.meta import STAGE_BROADCAST
    from core.state import STATE
    from ui import upload_os as _os

    STATE.enemies = []
    STATE.mission3_stage = STAGE_BROADCAST
    STATE.m3_bcast_wave = 4
    STATE.m3_bcast_time_left = 3600
    STATE.m3_bcast_failed = False
    STATE.m3_bcast_pc_ready = True
    STATE.request_mission3_ending = False

    old_player = STATE.player
    try:
        from entities.player import Player
        STATE.player = Player(0, 0, max_hp=115)
        pcx, pcy = _m3_world._bcast_pc_pos()
        STATE.player.rect.center = (pcx, pcy)

        # [E] at the PC opens the OS in its M3 (Vostral) profile.
        original_get_pressed = pygame.key.get_pressed

        class _KeyMock:
            def __getitem__(self, k):
                return k == pygame.K_e
        pygame.key.get_pressed = lambda: _KeyMock()
        try:
            _m3_flow._update_broadcast_stage()
        finally:
            pygame.key.get_pressed = original_get_pressed
        assert _os.is_upload_os_active(), "station PC did not open the upload OS"
        assert _os._os_profile == _os.PROFILE_M3, "M3 content profile not active"
        assert _os.DESKTOP_ICONS[0]["label"] == "VOSTRAL", "M3 desktop icons not installed"

        # Force the DONE phase; game_update must close the OS and request the
        # ending cutscene (the M2 tables are restored on deactivate).
        _os._os_phase = _os.PHASE_DONE
        _os._done_timer = 200

        class _Keys(dict):
            def __missing__(self, k):
                return False
        _m3_systems.game_update(_Keys())
        assert not _os.is_upload_os_active(), "OS did not deactivate after DONE"
        assert STATE.request_mission3_ending, "ending cutscene not requested"
        assert _os.DESKTOP_ICONS[0]["label"] == "EVIDENCE", "M2 tables not restored"
    finally:
        if _os.is_upload_os_active():
            _os.deactivate_upload_os()
        STATE.player = old_player
        STATE.m3_bcast_upload_active = False
        STATE.m3_bcast_upload_progress = 0.0
        STATE.m3_bcast_pc_ready = False


def check_mission3_broadcast_draw():
    """Broadcast draw path runs without error."""
    from missions.m3 import draw as _m3_draw
    from missions.m3 import maps as _m3_maps
    from missions.m3 import world as _m3_world
    from missions.m3.maps import MISSION3_BROADCAST_MAP
    from missions.m3.meta import STAGE_BROADCAST
    from core.state import STATE

    old_map = _m3_maps.MISSION3_MAP
    old_stage = getattr(STATE, "mission3_stage", None)
    try:
        _m3_world._build_broadcast_world()
        STATE.mission3_stage = STAGE_BROADCAST
        _m3_draw._game_draw_broadcast(0, 0)
    finally:
        _m3_maps.MISSION3_MAP = old_map
        if old_stage is not None:
            STATE.mission3_stage = old_stage


def check_mission3_broadcast_timeout_retry():
    """22:00 timeout -> fail request -> retry rebuilds the wing.

    The fail path used to dead-end: the timeout set m3_bcast_failed and asked
    for a cutscene nobody played, then froze the slice forever. This walks the
    whole loop the way app.py does (request -> retry) and asserts the wing
    comes back playable.
    """
    from missions.m3 import flow as _m3_flow
    from missions.m3 import maps as _m3_maps
    from missions.m3 import world as _m3_world
    from missions.m3.maps import MISSION3_BROADCAST_MAP
    from missions.m3.meta import BCAST_TIME_LIMIT, STAGE_BROADCAST
    from core.state import STATE

    old_map = _m3_maps.MISSION3_MAP
    old_stage = getattr(STATE, "mission3_stage", None)
    try:
        _m3_world._build_broadcast_world()
        STATE.mission3_stage = STAGE_BROADCAST
        STATE.m3_bcast_time_left = 2
        STATE.m3_bcast_wave = 4
        STATE.m3_bcast_pc_ready = True
        STATE.m3_bcast_failed = False
        STATE.request_mission3_fail_cutscene = False

        # Two ticks: the last frame of the clock trips the fail.
        _m3_flow._update_broadcast_stage()
        _m3_flow._update_broadcast_stage()
        assert STATE.m3_bcast_failed, "timeout did not set m3_bcast_failed"
        assert STATE.request_mission3_fail_cutscene, \
            "timeout did not request the fail cutscene"
        assert STATE.mission3_stage == STAGE_BROADCAST, \
            "fail path moved the stage out of the broadcast wing"
        # Frozen: no wave logic, no PC boot while the fail cutscene is pending.
        STATE.enemies = []
        _m3_flow._update_broadcast_stage()
        assert STATE.m3_bcast_time_left == 0, "clock kept ticking after the fail"
        from ui import upload_os as _os
        assert not _os.is_upload_os_active(), \
            "upload OS booted while the slice was failed"

        # app.py's _handle_end hand-off.
        _m3_flow._retry_broadcast_slice()
        assert not STATE.m3_bcast_failed, "retry left the slice failed"
        assert not STATE.request_mission3_fail_cutscene, "retry left the fail flag set"
        assert STATE.m3_bcast_time_left == BCAST_TIME_LIMIT, "retry did not reset the clock"
        assert STATE.m3_bcast_wave == 0, "retry did not reset the wave ladder"
        assert not STATE.m3_bcast_pc_ready, "retry left the PC flagged ready"
        assert _m3_maps.MISSION3_MAP is MISSION3_BROADCAST_MAP, \
            "retry did not rebind the broadcast map"
        assert STATE.player is not None and STATE.player.hp == STATE.player.max_hp, \
            "retry did not heal the player"
        assert len(STATE.doors) > 0, "retry rebuilt an empty world"
        # And the wing runs again after a retry.
        STATE.m3_bcast_time_left = BCAST_TIME_LIMIT
        _m3_flow._update_broadcast_stage()
        assert not STATE.m3_bcast_failed, "wing still failing after retry"
    finally:
        STATE.request_mission3_fail_cutscene = False
        STATE.m3_bcast_failed = False
        _m3_maps.MISSION3_MAP = old_map
        if old_stage is not None:
            STATE.mission3_stage = old_stage


def check_mission3_broadcast_fail_shots_render():
    """Every fail-cutscene shot has a renderer and paints a real frame.

    Guards the dead half of the fail path: the shot list shipped before the
    scene art, so draw_cutscene_scene fell through and the cutscene played
    three lit-black frames.
    """
    import statistics as _st
    import cutscenes
    from missions.m3.meta import broadcast_fail_shots

    # The facade must expose the list app.py asks game_core for.
    assert getattr(gc, "broadcast_fail_shots", None) is broadcast_fail_shots, \
        "gc.broadcast_fail_shots does not resolve to the M3 fail shots"

    assert len(broadcast_fail_shots) == 3, "fail shot list changed shape"
    for shot in broadcast_fail_shots:
        scene = shot["scene"]
        for t in (0, 1500, 4000, 9000):
            cutscenes.draw_cutscene_scene(config.screen, shot, t)
            px = pygame.surfarray.array3d(config.screen)
            lum = [(r + g + b) // 3 for r, g, b in px.reshape(-1, 3).tolist()]
            sd = _st.pstdev(lum)
            assert sd > 3.0, f"{scene} frame t={t} is a flat wash (std-dev={sd:.1f})"


def check_mission3_death_checkpoints():
    """Death respawns at the deepest M3 phase reached, not the archives.

    Phase 5/6 are combat gauntlets; the restart route only went as deep as the
    Archives, so dying in the dock holdout threw away the whole run.
    """
    from missions import m3
    from missions.m3 import flow as _m3_flow
    from missions.m3.meta import (STAGE_BROADCAST, STAGE_KILL_ORDER)
    from core.state import STATE

    # Broadcast: deepest, must win over the archives flag.
    m3.start_mission3_archives_checkpoint(preserve_timer=True)
    STATE.mission3_broadcast_checkpoint_reached = True
    gc.restart_current_mission()
    assert STATE.mission3_stage == STAGE_BROADCAST, \
        "broadcast death respawn did not land in the Broadcast Wing"
    assert STATE.m3_bcast_time_left, "broadcast respawn has no clock"
    assert STATE.player is not None and STATE.player.hp == STATE.player.max_hp, \
        "broadcast respawn did not heal the player"

    # Kill Order: next deepest.
    m3.start_mission3_archives_checkpoint(preserve_timer=True)
    STATE.mission3_kill_order_checkpoint_reached = True
    gc.restart_current_mission()
    assert STATE.mission3_stage == STAGE_KILL_ORDER, \
        "kill-order death respawn did not land on the KO floor"
    assert getattr(STATE, "m3_ko_world_built", False), \
        "KO respawn did not build the ground floor"
    # The director seeds lazily on its first tick, but the phase must hand it
    # the full window + uncommitted state, or the beat gates start sealed.
    assert getattr(STATE, "m3_sweep_window_frames", 0) == 5 * 60 * 60, \
        "KO respawn did not reseed the Volkov window"
    assert not getattr(STATE, "m3_sweep_committed", False), \
        "KO respawn inherited a committed holdout"
    assert not getattr(STATE, "m3_volkov_bailed", False), \
        "KO respawn inherited Volkov's bail"

    # Archives still reachable when neither gauntlet was entered.
    m3.start_mission3_archives_checkpoint(preserve_timer=True)
    gc.restart_current_mission()
    from missions.m3.meta import STAGE_ARCHIVES
    assert STATE.mission3_stage == STAGE_ARCHIVES, \
        "archives checkpoint regressed"

    # The fail cutscene is offered to app.py with a resume tag, and the tag is
    # the one _CutsceneState._handle_end routes on.
    assert _m3_flow.STAGE_BROADCAST == STAGE_BROADCAST, "stage constant drifted"


def check_mp_relay_roundtrip():
    """The multiplayer browser must work against a real socket backend.

    Spins up a real master in-process on an ephemeral port, points a real
    MPRelayClient at it, and drives the same path the game uses. This is
    the regression guard for the relay wiring: if the protocol, the thread
    handoff, or the sync breaks, this fails.

    Also covers the defensive paths in protocol.normalize_row, which are
    what stop a hostile or buggy master from feeding the UI garbage.
    """
    import socket as _socket
    import threading as _threading
    import time as _time

    from net import protocol as _P
    from net.client import MPRelayClient as _Client

    # ── normalize_row must reject junk and clamp absurd values ──
    assert _P.normalize_row(None) is None
    assert _P.normalize_row([]) is None
    assert _P.normalize_row({"name": ""}) is None
    assert _P.normalize_row({"name": "x", "current": "abc", "max": 4, "ping": 9}) is None
    # Player count above max, and a negative ping, must be clamped rather
    # than reaching the layout maths.
    clamped = _P.normalize_row({"name": "c", "current": 99, "max": 4, "ping": -5})
    assert clamped == ("c", 4, 4, 0), f"clamp failed: {clamped}"
    big = _P.normalize_row({"name": "b", "current": 0, "max": 1, "ping": 10 ** 9})
    assert big[3] == 9999, f"ping clamp failed: {big}"
    assert _P.normalize_rows("not a list") == []
    # Wire round-trip.
    blob = _P.encode({"t": "servers", "servers": [["a", 1, 2, 3]]})
    assert _P.decode(blob.strip())["servers"] == [["a", 1, 2, 3]]
    # Garbage must decode to None, never raise.
    assert _P.decode(b"{not json") is None
    assert _P.decode(b"[1,2,3]") is None
    assert _P.decode(b"") is None

    # ── Real master on an ephemeral port ──
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import mp_server as _srv

    state = _srv.MasterState(seed=True)
    # Ask the OS for a free port, release it, let the server bind.
    probe = _socket.socket()
    probe.bind(("127.0.0.1", 0))
    port = probe.getsockname()[1]
    probe.close()

    server = _srv.ThreadedTCPServer(("127.0.0.1", port), _srv.MasterHandler,
                                    state, verbose=False)
    _threading.Thread(target=server.serve_forever,
                      kwargs={"poll_interval": 0.05}, daemon=True).start()
    try:
        got = []
        from net.client import register_chat_sink as _reg
        _reg(lambda m: got.append(m))
        client = _Client(host="127.0.0.1", port=port, nickname="SmokeTester")
        client.start()
        client.request_connect()

        deadline = _time.time() + 12.0
        while _time.time() < deadline:
            st, _err, servers, _nick = client.state()
            if st == "online" and servers:
                break
            _time.sleep(0.1)

        st, err, servers, nick = client.state()
        assert st == "online", f"relay never came online (state={st!r} err={err!r})"
        assert servers, "master returned no servers"
        assert nick == "SmokeTester", f"nickname not adopted: {nick!r}"

        # Rows arrive pre-normalized to the shape the UI draws.
        for row in servers:
            assert len(row) == 5, f"unexpected row arity: {row!r}"
            name, cur, mx, _ping, rules = row
            assert isinstance(name, str) and name
            assert 0 <= cur <= mx
            assert isinstance(rules, tuple)

        # The connection must SURVIVE the first keepalive cycle. This is
        # the regression that caught recv() reporting a timeout as b"", which
        # is indistinguishable from a clean close if mishandled.
        _time.sleep(6.0)
        st2, err2, servers2, _ = client.state()
        assert st2 == "online", f"connection dropped during keepalive: {st2!r} {err2!r}"
        assert servers2, "server list emptied after keepalive"

        # Chat round-trips with a derived colour.
        assert client.send_chat("smoke test ping")
        deadline = _time.time() + 8.0
        while _time.time() < deadline and not got:
            _time.sleep(0.1)
        assert got, "chat was never relayed back"
        assert got[0]["text"] == "smoke test ping", f"chat mangled: {got[0]!r}"
        assert got[0]["user"] == "SmokeTester", f"chat user wrong: {got[0]!r}"
        assert len(got[0]["color"]) == 3, f"bad chat colour: {got[0]!r}"

        # send_chat must reject junk rather than putting it on the wire.
        assert client.send_chat("") is False
        assert client.send_chat("   ") is False
        assert client.send_chat("x" * 500) is False
        assert client.send_chat(None) is False

        # ── abuse limits ─────────────────────────────────────────────────
        # Driven against the same live master, with a SECOND client. The point
        # of a per-sender limit is that a flood is contained without taking
        # everyone else down, so this asserts both halves.
        flood_got = []
        _reg(lambda m: flood_got.append(m))
        flooder = _Client(host="127.0.0.1", port=port, nickname="Flooder")
        flooder.start()
        try:
            _time.sleep(0.8)
            assert flooder.send_chat("warm up")
            _time.sleep(0.5)
            flood_got.clear()
            for i in range(60):
                flooder.send_chat("flood %d" % i)
            _time.sleep(2.5)
            assert len(flood_got) < 30, \
                ("the master relayed an unbounded chat flood (%d of 60 "
                 "reached this listener)" % len(flood_got),)
            assert len(flood_got) >= 2, \
                "the chat limit throttled a legitimate sender to nothing"
        finally:
            flooder.stop()

        # The innocent client must have survived it, still online.
        st3, err3, servers3, _n3 = client.state()
        assert st3 == "online", \
            "a flood by one client disconnected another: %r %r" % (st3, err3)

        # Register rewrites EVERY client's server list, so it is the most
        # abusable verb on the wire. A second row under the same name inside
        # the interval must be refused -- and the refusal must be visible to
        # the publisher, not silently dropped.
        _raw = _socket.create_connection(("127.0.0.1", port), timeout=5)
        try:
            _raw.sendall(_P.encode({"t": _P.T_HELLO, "user": "Spammer",
                                    "proto": _P.PROTO_VERSION}))
            _time.sleep(0.3)
            _reg_msg = {"t": _P.T_REGISTER,
                        "row": ["Spam Row", 1, 8, 10],
                        "rules": ["RULES: " + "x" * 5000] * 40}
            _raw.sendall(_P.encode(_reg_msg))
            _raw.sendall(_P.encode(_reg_msg))          # inside REGISTER_MIN_GAP
            _raw.settimeout(3.0)
            _buf = b""
            _refused = False
            _rules_bounded = True
            try:
                while b"\n" not in _buf or not _refused:
                    chunk = _raw.recv(65536)
                    if not chunk:
                        break
                    _buf += chunk
                    for _line in _buf.split(b"\n"):
                        _msg = _P.decode(_line.strip())
                        if not isinstance(_msg, dict):
                            continue
                        if _msg.get("t") == _P.T_ERROR:
                            _refused = True
                        elif _msg.get("t") == _P.T_SERVERS:
                            for _row in _msg.get("servers") or ():
                                for _rule in (_msg.get("rules") or {}).get(
                                        _row[0]) or ():
                                    _rules_bounded = _rules_bounded and \
                                        len(_rule) <= 64
            except (_socket.timeout, OSError):
                pass
            assert _refused, \
                "a duplicate register inside the rate interval was accepted"
            assert _rules_bounded, \
                "an oversized rules string reached the server list"
        finally:
            _raw.close()

        # The token gate itself, isolated: a burst is allowed, a sustained
        # flood is not, and it refills over time.
        _gate = _srv.TokenGate(gap=1.0, burst=3)
        assert sum(1 for _ in range(3) if _gate.allow()) == 3, \
            "the gate refused a legitimate burst"
        assert not _gate.allow(), "the gate allowed a fourth back-to-back call"
        _time.sleep(1.1)
        assert _gate.allow(), "the gate never refilled"

        # And a client that outruns the gate is told so, once.
        _slow = _Client(host="127.0.0.1", port=port, nickname="TooFast")
        _slow.start()
        try:
            _time.sleep(0.8)
            for i in range(_srv.CHAT_BURST + 6):
                _slow.send_chat("spam %d" % i)
            _time.sleep(1.2)
            assert _slow.state()[0] == "online", \
                "a client that outran the chat gate was disconnected"
        finally:
            _slow.stop()

        client.stop()
    finally:
        server.stopping = True
        server.shutdown()
        server.server_close()
        _reg(None)

    # Dead host must degrade, not hang or raise.
    dead = _Client(host="127.0.0.1", port=1, nickname="Nobody")
    dead.start()
    _time.sleep(1.5)
    st, err, _servers, _ = dead.state()
    assert st in ("error", "connecting"), f"unexpected state vs dead host: {st!r}"
    # A refused connect reports a readable reason. Only assert the text once
    # the state is settled on "error" -- mid-retry the status is "connecting"
    # and the error string is legitimately empty for an instant.
    deadline = _time.time() + 6.0
    while _time.time() < deadline:
        st, err, _s, _ = dead.state()
        if st == "error" and err:
            break
        _time.sleep(0.2)
    assert st == "error" and err, \
        f"dead host should settle on error with a reason (got {st!r} {err!r})"
    dead.stop()


def check_mp_relay_ui_integration():
    """ui.mp must fall back to fiction offline and use the relay when live.

    Guards the UI seams: server_list must keep its 4-tuple shape (every
    draw/hit-test site indexes it positionally), and the relay helpers
    must be safe to call with no master running.
    """
    import ui.mp as _mp

    # Rows are structurally sound 4-tuples. Note we deliberately do NOT
    # assert cur <= mx: the fictional list ships one over-capacity row on
    # purpose ("Sebi's Parlament", 50/49) and _server_status() renders it
    # as FULL. normalize_row() is what clamps the relay's rows, and that is
    # asserted in check_mp_relay_roundtrip.
    for row in _mp.server_list:
        assert isinstance(row, tuple) and len(row) == 4, f"bad row: {row!r}"
        name, cur, mx, ping = row
        assert isinstance(name, str) and name
        assert isinstance(cur, int) and cur >= 0, f"bad cur in {row!r}"
        assert isinstance(mx, int) and mx > 0, f"bad max in {row!r}"
        assert isinstance(ping, int) and ping >= 0, f"bad ping in {row!r}"

    # server_rules_for must always resolve, preferring relay rules.
    assert _mp.server_rules_for("MAG Recruitment Center"), \
        "fictional rules should resolve when no relay is live"

    # Offline: no client, so these must be safe no-ops returning False.
    assert _mp.relay_is_live() is False
    assert _mp.relay_send_chat("x") is False
    assert _mp.relay_refresh() is False
    assert _mp.relay_status()[0] == "offline"

    # Start/stop must be idempotent and must not raise.
    _mp.relay_start(nick="SmokeUI", host="127.0.0.1", port=1)
    _mp.relay_start(nick="SmokeUI", host="127.0.0.1", port=1)  # second call
    _mp.relay_stop()
    _mp.relay_stop()  # second stop
    assert _mp.relay_status()[0] == "offline"

    # Chat input stays empty offline and accepts no keys.
    assert _mp._chat_input == ""

    class _Ev:
        key = 13
        unicode = ""
    assert _mp.relay_chat_key(_Ev()) is False, "offline chat key should be ignored"

    # A sync with no client must be a safe no-op reporting offline.
    _mp._sync_relay_into_server_list()
    assert _mp.relay_status()[0] == "offline"

    # Discovery must degrade to None rather than raise when nothing is out
    # there, and an explicit host must never be overridden by a probe.
    from net.discovery import discover_master as _disc
    found = _disc(timeout=0.5)
    assert found is None or (isinstance(found, tuple) and len(found) == 2), \
        f"discovery returned junk: {found!r}"
    _mp.relay_start(nick="SmokeUI2", host="10.255.255.1", port=1)
    assert _mp._relay_host == "10.255.255.1", \
        f"explicit host was overridden: {_mp._relay_host!r}"
    _mp.relay_stop()


def check_mp_host_and_portmap():
    """Self-hosting path: address validation, host state, port-map helpers.

    The network calls (UPnP/NAT-PMP/STUN) are NOT exercised here -- they
    depend on the machine's router and would make the suite flaky. What is
    tested is everything deterministic: address parsing, the host's server
    row, and the pure helpers that decide what address we advertise.
    """
    import ui.mp as _mp
    from net import portmap as _pm
    from net import protocol as P
    from net import tcp_tunnel as _tt

    # Hamachi addresses are IPv4s in 25/8. Reject lookalikes / malformed
    # values, and parse addresses emitted by the adapter-discovery command.
    assert _pm._hamachi_address("25.156.88.19") == "25.156.88.19"
    assert _pm._hamachi_address("24.156.88.19") is None
    assert _pm._hamachi_address("25.999.88.19") is None
    assert _pm._parse_hamachi_addresses(
        "25.156.88.19\n192.168.0.10\n25.156.88.19") == ["25.156.88.19"]

    # When Hamachi is active, hosting advertises its virtual IP and does not
    # wait on or launch public router/tunnel setup. The listener must remain
    # wildcard-bound so the overlay interface can receive the TCP stream.
    from ui.match_screen import MatchScreen as _HamachiMatch
    _hamachi_match = _HamachiMatch()
    _hamachi_match.mode = "hosting"
    _hamachi_match._host_token = object()
    _hamachi_token = _hamachi_match._host_token
    _old_hamachi, _old_open, _old_start = (
        _pm.hamachi_ipv4, _pm.open_port, _tt.start_ngrok_tunnel)
    _pm.hamachi_ipv4 = lambda: "25.156.88.19"
    _pm.open_port = lambda *args, **kwargs: (_ for _ in ()).throw(
        AssertionError("Hamachi hosting should skip router mapping"))
    _tt.start_ngrok_tunnel = lambda *args, **kwargs: (_ for _ in ()).throw(
        AssertionError("Hamachi hosting should skip public tunnels"))
    try:
        _hamachi_match._begin_forwarding(27017, _hamachi_token)
    finally:
        _pm.hamachi_ipv4, _pm.open_port, _tt.start_ngrok_tunnel = (
            _old_hamachi, _old_open, _old_start)
    from net import roomcode as _HamachiRoomCode
    assert _HamachiRoomCode.decode(_hamachi_match.room_code) == (
        "25.156.88.19", 27017), "Hamachi host did not publish its virtual IP"

    # The forwarding worker re-encodes the invite with the reachable address.
    # It must reuse the session's pinned flavour, not mint a new one: the host
    # may already be reading the first code out loud.
    _hamachi_match.code_prefix = "MAG"
    _pm.hamachi_ipv4 = lambda: "25.156.88.19"
    try:
        _hamachi_match._begin_forwarding(27017, _hamachi_token)
    finally:
        _pm.hamachi_ipv4 = _old_hamachi
    assert _hamachi_match.room_code.startswith("MAG-"), \
        "hosting changed the room-code flavour mid-session: %r" % (
            _hamachi_match.room_code,)
    assert _HamachiRoomCode.decode(_hamachi_match.room_code) == (
        "25.156.88.19", 27017), "re-encoded invite lost the Hamachi address"
    _hamachi_joiner = _HamachiMatch()
    assert _hamachi_joiner.request_join(_hamachi_match.room_code) is True, \
        "joiner rejected Hamachi room code"
    assert _hamachi_joiner._pending == [
        ("join", ("25.156.88.19", 27017))], \
        "joiner did not route to the Hamachi virtual IP"
    _hamachi_joiner._teardown()
    assert _hamachi_match._hamachi_active, "Hamachi mode was not announced"
    _listen = _hamachi_match._bind_listener(0)
    try:
        assert _listen.getsockname()[0] == "0.0.0.0", \
            "match listener must accept connections on Hamachi interface"
    finally:
        _listen.close()
    assert "Hamachi" in _hamachi_match._forward_status()[0], \
        "waiting UI did not identify Hamachi connection mode"
    _hamachi_match._teardown()

    # Public tunnels: both providers must be parsed into a raw address that
    # JOIN MATCH understands. cloudflared is tried FIRST because free ngrok TCP
    # is card-gated, so on a fresh machine it is the only one that can work.
    assert _tt.parse_endpoint(
        "Forwarding tcp://0.tcp.ngrok.io:12345 -> localhost:27017") == \
        ("0.tcp.ngrok.io", 12345)
    assert _tt.parse_endpoint("no forwarding endpoint yet") is None
    assert _tt.parse_endpoint("tcp://host.example:70000") is None
    # cloudflared announces a bare hostname and maps the port it was handed, so
    # the port comes back None here and the starter fills it in.
    assert _tt.parse_endpoint(
        "https://random-words-1234.trycloudflare.com") == \
        ("random-words-1234.trycloudflare.com", None)

    class _FakeTunnelOutput:
        def __init__(self, lines):
            self.lines = iter(lines)
        def readline(self):
            try:
                return next(self.lines)
            except StopIteration:
                return ""

    class _FakeTunnelProcess:
        def __init__(self, lines=("Forwarding tcp://1.tcp.ngrok.io:45678\n", "")):
            self.stdout = _FakeTunnelOutput(lines)
            self.terminated = False
        def poll(self):
            return None
        def terminate(self):
            self.terminated = True
        def wait(self, timeout=None):
            return 0
        def kill(self):
            self.terminated = True

    # The 8013 message has to name the FIX, not just the problem. A host who
    # reads "card verification required" has no next step; one who reads
    # "install cloudflared" does.
    _e8013 = _tt.explain_error(
        "ERROR: must add a credit or debit card. ERR_NGROK_8013")
    assert "8013" in _e8013, "the ngrok card-verification code was lost"
    assert "cloudflared" in _e8013, \
        "the ngrok card error does not offer a card-free alternative: %r" % _e8013
    assert "ERR_NGROK_9009" in _tt.explain_error("ERR_NGROK_9009 Pay-as-you-go feature") \
        or "paid plan" in _tt.explain_error("ERR_NGROK_9009 Pay-as-you-go feature")
    # Every provider failure must translate into prose a host can act on --
    # a raw error code is not guidance.
    for _raw in ("ERR_NGROK_8013", "ERR_NGROK_9009", "ERR_NGROK_4018"):
        _said = _tt.explain_error(_raw)
        assert _said and _raw not in _said, \
            "explain_error(%r) did not translate it: %r" % (_raw, _said)
    # A missing provider must name the one-command install, since that is the
    # only thing a LAN-only host can actually do next.
    assert "cloudflare.cloudflared" in _tt.explain_error(
        "cloudflared is not installed"), \
        "a missing cloudflared does not produce an install instruction"

    _old_which, _old_popen = _tt.shutil.which, _tt.subprocess.Popen
    _launch = {}
    _fake_proc = _FakeTunnelProcess()
    _tt.shutil.which = lambda name: "ngrok.exe" if name == "ngrok" else None
    def _fake_popen(args, **kwargs):
        _launch["args"] = args
        _launch["env"] = kwargs.get("env", {})
        return _fake_proc
    _tt.subprocess.Popen = _fake_popen
    try:
        _endpoint, _proc, _error = _tt.start_ngrok_tunnel(27017, timeout=1.0)
    finally:
        _tt.shutil.which, _tt.subprocess.Popen = _old_which, _old_popen
    assert _endpoint == ("1.tcp.ngrok.io", 45678) and _proc is _fake_proc, \
        "ngrok TCP endpoint was not returned to the match host"
    assert _launch["args"] == ["ngrok.exe", "tcp", "27017"], \
        "ngrok was not asked to expose the match's local TCP port"
    assert not any(key in _launch["env"] for key in (
        "HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY",
        "http_proxy", "https_proxy", "all_proxy")), \
        "ngrok TCP launcher inherited proxy variables that trigger paid-plan errors"
    _tt.stop_process(_fake_proc)
    assert _fake_proc.terminated, "leaving a match must stop its tunnel process"

    # cloudflared: same contract, and it must be tried BEFORE ngrok. This is
    # the ordering that makes public play work at all on a free account.
    _cf_proc = _FakeTunnelProcess(
        ["+-------------------------------------------+\n",
         "|  https://abcd-ef12.trycloudflare.com     |\n"])
    _old_which, _old_popen = _tt.shutil.which, _tt.subprocess.Popen
    _launch = {}
    _tt.shutil.which = lambda name: "cloudflared.exe" if name == "cloudflared" else None
    def _fake_popen_cf(args, **kwargs):
        _launch["args"] = args
        return _cf_proc
    _tt.subprocess.Popen = _fake_popen_cf
    try:
        _endpoint, _proc, _error = _tt.start_cloudflared_tunnel(27017, timeout=1.0)
        _tt.stop_process(_proc)
        # And the order, through the public entry point.
        _order = []
        _tt.shutil.which = lambda name: None
        _tt.subprocess.Popen = _fake_popen
        def _fake_popen_both(args, **kwargs):
            _order.append(args[0].rsplit("\\", 1)[-1].rsplit("/", 1)[-1])
            return _FakeTunnelProcess()
        _tt.subprocess.Popen = _fake_popen_both
        _tt.start_cloudflared_tunnel = lambda port, timeout=None: (
            ("cf.example", 27017), None, "")
        _tt.start_ngrok_tunnel = lambda port, timeout=None: (
            None, None, "ngrok should not have been reached")
        _e, _p, _provider = _tt.start_tunnel(27017, timeout=0.1)
    finally:
        _tt.shutil.which, _tt.subprocess.Popen = _old_which, _old_popen
    assert _endpoint == ("abcd-ef12.trycloudflare.com", 27017), \
        f"cloudflared endpoint not parsed: {_endpoint}"
    assert _provider == "cloudflared" and _e == ("cf.example", 27017), \
        f"start_tunnel did not prefer cloudflared: {_provider} {_e}"
    assert _cf_proc.terminated, "cloudflared process was not stopped"
    assert "tunnel" in " ".join(_launch["args"]) and \
        "tcp://localhost:27017" in _launch["args"], \
        "cloudflared was not asked to expose the match's local TCP port: %r" % (
            _launch["args"],)

    # The live host path must take a tunnel endpoint once router mapping fails,
    # publish its host:port in the invite field, and stop the process when the
    # match is torn down. Patched at start_tunnel (not start_ngrok_tunnel)
    # because that is the seam the host actually calls.
    from ui.match_screen import MatchScreen as _MatchScreen
    _match = _MatchScreen()
    _match.mode = "hosting"
    _match._host_token = object()
    _host_token = _match._host_token
    _forward_proc = _FakeTunnelProcess()
    _old_open, _old_start = _pm.open_port, _tt.start_tunnel
    _pm.open_port = lambda *args, **kwargs: _pm.ForwardResult(
        False, error="router mapping unavailable")
    _tt.start_tunnel = lambda port, timeout=None: (
        ("1.tcp.ngrok.io", 45678), _forward_proc, "cloudflared")
    try:
        _match._begin_forwarding(27017, _host_token)
    finally:
        _pm.open_port, _tt.start_tunnel = _old_open, _old_start
    assert _match._tunnel_active and _match.forwarded, \
        "host did not mark the public TCP tunnel active"
    assert _match.room_code == "1.tcp.ngrok.io:45678", \
        "host invite did not publish the tunnel address"
    assert "cloudflared" in _match.forward_note, \
        "the host did not say WHICH tunnel provider it used: %r" % (
            _match.forward_note,)
    _match._teardown()
    assert _forward_proc.terminated, "match teardown leaked its public tunnel"

    # When neither provider is installed the host must say WHAT TO INSTALL.
    # "LAN only" on its own leaves a player with no next action, and that was
    # the whole open blocker on public play.
    _lan = _MatchScreen()
    _lan.mode = "hosting"
    _lan._host_token = object()
    _old_open, _old_start = _pm.open_port, _tt.start_tunnel
    _pm.open_port = lambda *args, **kwargs: _pm.ForwardResult(
        False, error="router mapping unavailable")
    _tt.start_tunnel = lambda port, timeout=None: (
        None, None, "cloudflared is not installed; ngrok is not installed")
    try:
        _lan._begin_forwarding(27017, _lan._host_token)
    finally:
        _pm.open_port, _tt.start_tunnel = _old_open, _old_start
    assert "cloudflared" in _lan.status, \
        "a LAN-only host was not told what to install: %r" % (_lan.status,)
    assert "cloudflare.cloudflared" in _lan._forward_status()[0] or \
        "cloudflared" in _lan._forward_status()[0], \
        "the waiting card gives no install instruction: %r" % (
            _lan._forward_status()[0],)
    _lan._teardown()

    # ── is_private drives the "is this shareable?" decision ──
    assert _pm.is_private("192.168.0.185") is True
    assert _pm.is_private("10.0.0.1") is True
    assert _pm.is_private("172.16.0.1") is True
    assert _pm.is_private("172.32.0.1") is False, "172.32 is outside the private block"
    assert _pm.is_private("127.0.0.1") is True
    assert _pm.is_private("100.64.0.1") is True, "CGNAT was treated as public"
    assert _pm.is_private("100.128.0.1") is False
    assert _pm.is_private("169.254.1.2") is True
    assert _pm.is_private("8.8.8.8") is False

    # NAT-PMP must target the router from the OS route table, not loopback,
    # and the 12-byte external-address reply is valid (no 4 extra bytes).
    _route_output = (
        "Network Destination Netmask Gateway Interface Metric\n"
        "0.0.0.0 0.0.0.0 192.168.1.1 192.168.1.42 25\n"
    )
    assert _pm._windows_default_gateway(_route_output) == "192.168.1.1"

    import socket as _socket
    import struct as _struct
    class _NatReplySocket(object):
        def __init__(self):
            self.target = None
            self.packet = None
        def settimeout(self, _seconds):
            pass
        def sendto(self, packet, target):
            self.packet = packet
            self.target = target
        def recvfrom(self, _size):
            reply = (_struct.pack("!BBHI", 0, _pm.OPCODE_EXTERNAL | 0x80, 0, 42)
                     + _socket.inet_aton("203.0.113.9"))
            return reply, ("192.168.1.1", _pm.NATPMP_PORT)
    _nat_socket = _NatReplySocket()
    _nat_result = _pm._natpmp_request(
        _nat_socket, _pm.OPCODE_EXTERNAL, gateway="192.168.1.1")
    assert _nat_socket.target == ("192.168.1.1", _pm.NATPMP_PORT), \
        "NAT-PMP request was not sent to the router"
    assert _nat_result == (0, "203.0.113.9", 0), \
        f"12-byte NAT-PMP external-IP reply was rejected: {_nat_result!r}"

    class _NatMapReplySocket(_NatReplySocket):
        def recvfrom(self, _size):
            reply = _struct.pack("!BBHIHHI", 0, _pm.OPCODE_MAP | 0x80, 0, 42,
                                 27015, 27015, 7200)
            return reply, ("192.168.1.1", _pm.NATPMP_PORT)
    _map_socket = _NatMapReplySocket()
    _map_result = _pm._natpmp_request(
        _map_socket, _pm.OPCODE_MAP, 27015, 27015, 7200,
        gateway="192.168.1.1")
    assert _map_socket.packet[1] == 2, \
        "NAT-PMP TCP listener must use opcode 2 (opcode 1 maps UDP)"
    assert _map_result == (0, None, 27015), \
        f"NAT-PMP TCP mapping reply was rejected: {_map_result!r}"

    # Junk must not raise.
    for junk in ("", "junk", "1.2.3", "1.2.3.4.5", None, 12345):
        assert _pm.is_private(junk) in (True, False)

    # ── Address validation for "join by address" ──
    # These must not raise and must not start a connection on bad input.
    bad = ["", "   ", "host:notaport", "host:0", "host:70000",
           "1.2.3.4:99999", "has space:27015"]
    for text in bad:
        ok, msg = _mp.relay_connect_to(text, nick="SmokeDirect")
        assert ok is False, f"should have rejected {text!r} (got {msg!r})"
        assert isinstance(msg, str) and msg
    assert _mp.relay_connect_to(None)[0] is False
    assert _mp.relay_connect_to(12345)[0] is False

    # A well-formed address is accepted and parsed. Use a documentation
    # address (192.0.2.x, RFC 5737) so nothing can accidentally connect.
    ok, msg = _mp.relay_connect_to("192.0.2.1:27020", nick="SmokeDirect")
    assert ok is True, f"valid address rejected: {msg!r}"
    assert msg == "192.0.2.1:27020", f"bad echo: {msg!r}"
    _mp.relay_stop()

    # Bare host gets the default port.
    ok, msg = _mp.relay_connect_to("192.0.2.1")
    assert ok is True and msg.endswith(":27015"), f"default port wrong: {msg!r}"
    _mp.relay_stop()

    # The direct-connect widget state must be safe to poke.
    _mp._connect_input = ""
    _mp._connect_focused = False
    class _Ev:
        key = 13
        unicode = ""
    assert _mp.direct_connect_key(_Ev()) is False, "unfocused box must ignore keys"
    _mp._connect_focused = True
    _mp._connect_input = "1.2.3.4:27015"
    _mp.direct_connect_tick()
    assert _mp._connect_msg_age >= 1, "tick did not age the message"
    _mp._connect_focused = False
    _mp._connect_input = ""

    # Fiction chat must be tagged, and the handover to a live relay must
    # drop ONLY fiction. The master backfills recent chat to every joiner,
    # and that backfill usually lands alongside the server list, so a
    # blanket clear() would wipe real messages the instant they arrived.
    # That was a real bug; this drives the real function to prove it fixed.
    _mp.relay_stop()
    _mp._chat_messages[:] = []
    _mp._relay_status = "offline"

    # Seed the panel the way it looks mid-session: invented lines from
    # CHAT_POOL, plus a real line that the host backfilled on join.
    _mp._chat_messages[:] = [
        {"user": "FictionUser", "text": "invented", "color": (1, 2, 3),
         "age": 4, "fict": True},
        {"user": "RealFriend", "text": "actually typed this",
         "color": (4, 5, 6), "age": 2},
    ]

    # Stand in for a live relay so _sync_relay_into_server_list() takes
    # the handover branch (_was_live False -> "online").
    class _FakeClient(object):
        def state(self):
            return ("online", "", (("Some Host", 1, 8, 20, ()),), "SmokeUI3")

        # The browser drains soft-error notes every frame, so a stand-in that
        # omits this is not a stand-in -- it is a crash waiting for the first
        # real frame. Any client shape the browser drives has to satisfy it.
        def take_notes(self):
            return []

    saved_client = _mp._relay_client
    try:
        _mp._relay_client = _FakeClient()
        _mp._sync_relay_into_server_list()
    finally:
        _mp._relay_client = saved_client

    users = [m["user"] for m in _mp._chat_messages]
    assert "RealFriend" in users, \
        f"handover wiped the real backfilled message: {users!r}"
    assert "FictionUser" not in users, \
        f"fiction survived the handover: {users!r}"
    assert not any(m.get("fict") for m in _mp._chat_messages), \
        "a fiction entry was left behind"
    # The real message must be the untouched original object, not a copy.
    assert _mp._chat_messages[0]["text"] == "actually typed this"

    # A soft note from the master must surface, and must NOT be mistaken for a
    # disconnection.
    class _NoteClient(_FakeClient):
        def take_notes(self):
            return ["sending too fast; slow down"]

    _mp._chat_messages[:] = []
    saved_client = _mp._relay_client
    try:
        _mp._relay_client = _NoteClient()
        _mp._sync_relay_into_server_list()
    finally:
        _mp._relay_client = saved_client
    assert any("too fast" in m["text"] for m in _mp._chat_messages), \
        "a master note never reached the player: %r" % (_mp._chat_messages,)
    assert _mp._relay_status == "online", \
        "a master note was treated as a disconnection"
    assert not _mp._relay_error, \
        "a master note was reported as a connection error"

    _mp._chat_messages[:] = []
    _mp._relay_status = "offline"

    # ── The joiner a friend actually runs ──
    # Its whole job is tolerating whatever the host pasted at them, so the
    # parser is the piece most worth pinning down.
    import mp_join
    cases = [
        ("1.2.3.4:27015", ("1.2.3.4", 27015)),
        ("192.168.1.42", ("192.168.1.42", 27015)),   # port defaults
        ("  1.2.3.4:27015  ", ("1.2.3.4", 27015)),   # stray whitespace
        ("tcp://0.tcp.ngrok.io:14872", ("0.tcp.ngrok.io", 14872)),
        ("https://abc-def.trycloudflare.com", ("abc-def.trycloudflare.com", 27015)),
        ("https://abc.trycloudflare.com/", ("abc.trycloudflare.com", 27015)),
        ('"1.2.3.4:27015"', ("1.2.3.4", 27015)),       # quoted by a chat app
        ("host.example.com:65535", ("host.example.com", 65535)),
    ]
    for raw, want in cases:
        got = mp_join.parse_addr(raw)
        assert got == want, f"parse_addr({raw!r}) -> {got!r}, want {want!r}"
    for bad in ("", "   ", None, "not a host", "1.2.3.4:99999",
                "1.2.3.4:abc", "has space:27015"):
        assert mp_join.parse_addr(bad) is None, \
            f"parse_addr({bad!r}) should have been rejected"

    # The chat sink must dedupe: the master backfills recent history AND
    # echoes your own line back, so without this the panel double-prints.
    mp_join.LINES[:] = []
    mp_join.SEEN.clear()
    mp_join.sink({"user": "A", "text": "hi"})
    mp_join.sink({"user": "A", "text": "hi"})
    assert len(mp_join.LINES) == 1, f"sink did not dedupe: {mp_join.LINES!r}"
    mp_join.sink({"user": "B", "text": "yo"})
    assert len(mp_join.LINES) == 2
    mp_join.LINES[:] = []
    mp_join.SEEN.clear()

    # ── Fixed timestep (multiplayer simulation determinism) ──
    # The host simulates the authoritative world, so its sim rate must not
    # depend on its hardware. Before this, ~60 frame counters
    # (`fire_cooldown -= 1`) advanced once per *rendered frame*, meaning a
    # host rendering at 30 FPS handed clients half the fire rate of one at
    # 60. These tests pin the accumulator that fixes it.
    from core import fixedstep

    def _sim_ticks(hz_display, seconds=2.0, hz_sim=60, max_steps=5):
        c = fixedstep.FixedStepClock(hz_sim, max_steps)
        for _ in range(int(seconds * hz_display)):
            c.steps(1.0 / hz_display)
        return int(c.sim_time * hz_sim + 0.5)

    # 2 s of wall clock is 120 sim ticks at 60 Hz regardless of display.
    # 144 Hz lands 1 short because 1/144 is not exact in binary and the
    # remainder sits as precisely one tick; it drains on the next frame, so
    # allow a tick either way and assert no drift beyond that.
    for hz in (60, 144, 180, 240):
        ticks = _sim_ticks(hz)
        assert abs(ticks - 120) <= 1, \
            f"at {hz} Hz render, 2 s gave {ticks} sim ticks (want ~120)"

    # The legacy behaviour this replaces, for contrast: one update per frame
    # means the tick count tracks the frame count.
    legacy_at_30 = 30 * 2
    assert legacy_at_30 == 60, "sanity: legacy would give 60 ticks at 30 FPS"

    # A hitch must not death-spiral: catch-up is capped and the surplus
    # discarded, so the sim runs briefly slow rather than locking up.
    c = fixedstep.FixedStepClock(60, 5)
    n = c.steps(0.5)                     # 500 ms freeze
    assert n == 5, f"500 ms frame ran {n} steps, expected the cap of 5"
    assert c.dropped_steps == 25, \
        f"expected 25 dropped steps, got {c.dropped_steps}"
    assert c.steps(1.0 / 60) == 1, "backlog should be cleared next frame"

    # Zero/negative/None dt must not drain the accumulator, or a paused game
    # would fast-forward the moment it resumed.
    c2 = fixedstep.FixedStepClock(60, 5)
    for bad in (0, 0.0, -0.1, None):
        assert c2.steps(bad) == 0, f"steps({bad!r}) should be 0"

    # Partial frames must accumulate rather than being rounded away. Ten
    # 6 ms frames is 60 ms = 3.6 ticks, so 3 whole ticks fire and the
    # remaining 0.6 tick stays in the accumulator for the next frame. The
    # property that matters is that no wall-clock time is lost: feeding
    # 1800 tiny 1 ms frames must yield the same 30 ticks as 30 x 20 ms.
    c3 = fixedstep.FixedStepClock(60, 5)
    got = sum(c3.steps(0.006) for _ in range(10))
    assert got == 3, f"60 ms should complete 3 ticks, got {got}"
    assert 0.0 < c3.alpha() < 1.0, \
        "the partial tick should still be pending, alpha=%.3f" % c3.alpha()

    fine = fixedstep.FixedStepClock(60, 5)
    ticks_fine = sum(fine.steps(0.001) for _ in range(1800))   # 1.8 s
    coarse = fixedstep.FixedStepClock(60, 5)
    ticks_coarse = sum(coarse.steps(0.020) for _ in range(90))  # 1.8 s
    assert ticks_fine == ticks_coarse == 108, \
        "sub-tick frames lost time: fine=%d coarse=%d want 108" \
        % (ticks_fine, ticks_coarse)

    # alpha() is the render interpolation factor and must stay in [0, 1).
    c4 = fixedstep.FixedStepClock(60, 5)
    for _ in range(20):
        c4.steps(1.0 / 90)
        a = c4.alpha()
        assert 0.0 <= a < 1.0, f"alpha out of range: {a}"

    # Constructor must reject nonsense rather than dividing by zero later.
    for bad in ((0, 5), (-60, 5), (60, 0), (60, -1)):
        try:
            fixedstep.FixedStepClock(*bad)
            raise AssertionError(f"FixedStepClock{bad} should have raised")
        except ValueError:
            pass

    # The switch is off by default -- single-player must be untouched -- and
    # disabling it clears the accumulator so the legacy path cannot inherit
    # a partial step.
    prev = fixedstep.set_enabled(True)
    assert fixedstep.is_enabled() is True
    c5 = fixedstep.clock()
    c5.steps(0.005)                      # leave a partial step behind
    fixedstep.set_enabled(False)
    assert fixedstep.is_enabled() is False
    assert c5.alpha() == 0.0, \
        "disabling must clear the partial step, got alpha %.3f" % c5.alpha()
    fixedstep.set_enabled(prev)          # restore prior state

    # ── Snapshot codec (step 2) ──
    # Everything here arrives off a socket, so the contract is: never raise,
    # never trust a number, and stay small. An unbounded or crashing parse
    # would be a remote crash of the client's render loop.
    P2 = P

    ent = P2.make_entity(0, P2.ENT_PLAYER, 1234.5, 5678.9, 90.25, 100,
                         P2.PS_MOVING, P2.WPN_PISTOL, P2.F_SPRINTING)
    got = P2.parse_snapshot(P2.decode(P2.encode(P2.make_snapshot(4242, [ent]))))
    assert got is not None, "valid snapshot failed to round trip"
    tick, back = got
    assert tick == 4242, f"tick lost: {tick}"
    assert back[0] == ent, f"entity lost fields:\n  {back[0]}\n  {ent}"
    assert P2.entity_to_dict(ent)["state"] == P2.PS_MOVING

    # Positional arrays exist to beat verbose JSON. Guard that, or someone
    # will "helpfully" switch to dicts and triple the bandwidth.
    one = P2.encode(P2.make_snapshot(1, [ent]))
    assert len(one) < 120, \
        f"one entity is {len(one)} bytes; positional encoding regressed"

    # Clamping: an out-of-range value is a cosmetic problem, a dropped frame
    # is a visible stutter, so clamp rather than reject.
    def _snap(e):
        return P2.parse_snapshot({"t": P2.T_SNAPSHOT, "k": 1, "e": [e]})
    c = _snap([0, 0, float("nan"), 2.0, 0.0, 1, 0, 0, 0])
    assert c is not None and c[1][0][2] == 0.0, f"NaN coord not sanitized: {c}"
    c = _snap([0, 0, 1e300, 1.0, 0.0, 10 ** 12, 0, 0, 0])
    assert c[1][0][2] == P2.MAX_COORD, f"huge coord not clamped: {c[1][0][2]}"
    assert c[1][0][5] == P2.MAX_HP, f"huge hp not clamped: {c[1][0][5]}"
    c = _snap([0, 0, 1.0, 2.0, 0.0, -50, 0, 0, 0])
    assert c[1][0][5] == 0, f"negative hp not clamped: {c[1][0][5]}"
    c = _snap([0, 0, 1.0, 2.0, 400.0, 1, 0, 0, 0])
    assert 0 <= c[1][0][4] < 360.0, f"angle not wrapped: {c[1][0][4]}"

    # Rejection: a structurally wrong message drops whole, because a
    # half-understood snapshot desyncs the client silently.
    good_e = list(ent)
    for bad in (
        "not a dict",
        {"t": P2.T_CHAT, "k": 1, "e": []},                    # wrong type
        {"t": P2.T_SNAPSHOT, "k": 1, "e": "boom"},            # e not a list
        {"t": P2.T_SNAPSHOT, "k": 1, "e": {"a": 1}},          # e is a dict
        {"t": P2.T_SNAPSHOT, "k": 1, "e": [[0, 0, 1, 2]]},    # entity too short
        {"t": P2.T_SNAPSHOT, "k": 1, "e": ["nope"]},          # entity not a list
        {"t": P2.T_SNAPSHOT, "k": 1, "e": [good_e] * 500},    # absurd count
        {"t": P2.T_SNAPSHOT, "k": "abc", "e": []},            # tick not a number
    ):
        assert P2.parse_snapshot(bad) is None, \
            f"hostile snapshot accepted: {bad!r}"

    # Input packets. The axis is a DIRECTION, never a magnitude -- the host
    # multiplies by its own player speed -- so an absurd value clamps to
    # full-left/full-right rather than being rejected. That is deliberate:
    # a peer claiming 400 gets exactly 1x speed, so it cannot cheat by
    # inflating it, and a clamped input is better than a dropped one.
    assert P2.parse_input(P2.decode(P2.encode(
        P2.make_input(7, 1, -1, 450, P2.F_FIRING)))) == {
            "q": 7, "mx": 1, "my": -1, "a": 90.0, "b": P2.F_FIRING}
    for v, want in ((400, 1), (-99, -1), (1e300, 1), (0.9, 1), (-0.9, -1)):
        r = P2.parse_input({"t": P2.T_INPUT, "q": 1, "mx": v, "my": 0,
                            "a": 0, "b": 0})
        assert r is not None and r["mx"] == want, \
            f"axis {v!r} -> {r and r['mx']!r}, want {want}"
    # Garbage that is not a number at all degrades to "no movement" rather
    # than raising or being treated as input.
    for v in ("left", None, [1], {"a": 1}):
        r = P2.parse_input({"t": P2.T_INPUT, "q": 1, "mx": v, "my": 0,
                            "a": 0, "b": 0})
        assert r is not None and r["mx"] == 0, \
            f"garbage axis {v!r} -> {r and r['mx']!r}, want 0"
    # int() truncates toward zero, so an earlier version turned -0.9 into 0
    # -- silently dead input. The snap must not regress to that.
    assert P2.parse_input({"t": P2.T_INPUT, "q": 1, "mx": -0.9,
                           "my": 0.2, "a": 0, "b": 0}) == {
                               "q": 1, "mx": -1, "my": 0, "a": 0.0, "b": 0}
    # Non-input messages are still rejected outright.
    for bad in (42, "string", None, {"t": P2.T_CHAT, "q": 1}, {}):
        assert P2.parse_input(bad) is None, \
            f"non-input accepted: {bad!r}"

    # Assign packet: host -> client slot id. Round-trips, clamps to 16 bits,
    # and is rejected when it is not an assign at all (so the client's
    # message dispatch cannot mistake a snapshot for one).
    assert P2.parse_assign(P2.decode(P2.encode(P2.make_assign(3)))) == 3, \
        "assign did not round-trip"
    # The map name rides along so a client renders the host's geometry.
    assert P2.assign_map(P2.make_assign(3, "crossfire")) == "crossfire", \
        "assign map name did not round-trip"
    assert P2.assign_map(P2.make_assign(3)) is None, \
        "assign without a map should report None"
    for bad in (42, "string", None, {"t": P2.T_SNAPSHOT}, {}):
        assert P2.parse_assign(bad) is None, \
            f"non-assign accepted: {bad!r}"

    # Room codes: the host's address in disguise, so a friend can be handed
    # a short string instead of an IP. Must round-trip, accept the KRAP
    # prefix, never swallow a raw address, and reject a typo via checksum.
    from net import roomcode as _RC
    _code = _RC.encode("82.78.75.76", 27015)
    assert _RC.decode(_code) == ("82.78.75.76", 27015), \
        "room code did not round-trip"
    assert _RC.decode(_RC.encode("82.78.75.76", 27015, "KRAP")) == \
        ("82.78.75.76", 27015), "KRAP-prefixed code did not decode"
    assert _RC.decode("1.2.3.4:27015") is None, \
        "a raw address was mistaken for a room code"
    _bad = _code[:-1] + ("0" if _code[-1] != "0" else "1")
    assert _RC.decode(_bad) is None, "checksum did not reject a typo"

    # The prefix is flavour, not data, so EVERY in-universe flavour must
    # round-trip and every one must be short enough to still be read aloud.
    assert len(_RC.PREFIX_POOL) >= 4, \
        "room codes only carry %d flavour(s)" % len(_RC.PREFIX_POOL)
    for _p in _RC.PREFIX_POOL:
        assert len(_p) <= 4, f"prefix {_p!r} is too long to read aloud"
        assert "-" not in _p, f"prefix {_p!r} would split the code"
        _c = _RC.encode("10.0.0.7", 27018, _p)
        assert _c.startswith(_p + "-"), f"{_p} prefix not used: {_c!r}"
        assert _RC.decode(_c) == ("10.0.0.7", 27018), \
            f"{_p} flavour did not round-trip"
    # A code a friend wrote down before the pool grew must still open.
    assert _RC.decode("ACAR-A974P-K39GWZ") == ("82.78.75.76", 27015), \
        "a legacy ACAR code no longer decodes"

    # encode() must actually draw from the pool when no prefix is named, or
    # every host is handed the same "ACAR-..." string again. random_prefix is
    # patched so the check is deterministic rather than a 1-in-pool lottery.
    _orig_pick = _RC.random_prefix
    _RC.random_prefix = lambda rng=None: "MAG"
    try:
        assert _RC.encode("10.0.0.7", 27018).startswith("MAG-"), \
            "encode() ignored the chosen in-universe prefix"
    finally:
        _RC.random_prefix = _orig_pick
    import random as _random
    _pick = _RC.random_prefix(_random.Random(1))
    assert _pick in _RC.PREFIX_POOL and \
        _RC.random_prefix(_random.Random(1)) == _pick, \
        "prefix pick is not reproducible from a seeded rng"

    # ── Snapshot interpolation buffer ──
    # The host sends at 20 Hz, the client draws at 60. Drawing the newest
    # snapshot verbatim makes remote players stutter; interpolating between
    # the two snapshots straddling a render time 100 ms in the past is the
    # standard fix. These are the cases that actually bite in practice.
    from core.fixedstep import SnapshotBuffer, lerp, lerp_angle

    def E(x, a=0.0, hp=100):
        return (0, 0, float(x), 100.0, a, hp, 0, 0, 0)

    # The 0/360 seam: a naive lerp from 350 to 10 sweeps back through 180,
    # making a player spin almost a full turn while crossing north.
    assert lerp(350, 10, 0.5) == 180.0, "sanity: naive lerp really is wrong"
    assert lerp_angle(350, 10, 0.5) < 90.0, \
        f"angle seam spun the long way: {lerp_angle(350, 10, 0.5)}"
    assert abs(lerp_angle(10, 350, 0.5) - 0.0) < 1e-6, "seam not symmetric"

    b = SnapshotBuffer(60, 0.0)
    b.push(0, [E(0.0)])
    b.push(10, [E(100.0)])
    assert abs(b.sample(5)[0][2] - 50.0) < 0.01, \
        f"midpoint wrong: {b.sample(5)[0][2]}"
    assert abs(b.sample(0)[0][2] - 0.0) < 0.01
    assert abs(b.sample(10)[0][2] - 100.0) < 0.01

    # Out-of-order and duplicate packets happen on real networks. Accepting
    # a stale one would make the world visibly jump backwards.
    assert b.push(5, [E(50.0)]) is False, "stale packet accepted"
    assert b.push(10, [E(100.0)]) is False, "duplicate packet accepted"
    assert b.push(11, [E(110.0)]) is True, "fresh packet rejected"
    assert b.latest_tick() == 11

    # Never extrapolate past the newest snapshot: that would invent motion
    # the host never simulated.
    assert b.sample(99999)[0][2] == 110.0, "client extrapolated into fiction"
    assert SnapshotBuffer().sample(5) is None, "empty buffer should yield None"

    # A pause (alt-tab, breakpoint) must not leave a stale backlog.
    bb = SnapshotBuffer(60, 0.0)
    for t in range(100):
        bb.push(t, [E(float(t))])
    assert len(bb) == 32, f"buffer unbounded: {len(bb)}"

    # Spawn/despawn must pop, not fade: a ghost drifting across the map is
    # worse than a visible pop.
    bs = SnapshotBuffer(60, 0.0)
    bs.push(0, [E(0.0), (1, 0, 50.0, 50.0, 0.0, 100, 0, 0, 0)])
    bs.push(10, [(1, 0, 150.0, 50.0, 0.0, 100, 0, 0, 0)])
    assert sorted(bs.sample(5).keys()) == [0, 1], "entity vanished mid-blend"

    # hp is an int on the wire, so blending must not hand back a fraction.
    bh = SnapshotBuffer(60, 0.0)
    bh.push(0, [E(0, hp=100)])
    bh.push(10, [E(100, hp=0)])
    assert isinstance(bh.sample(5)[0][5], int), "hp blended to a float"

    # The end-to-end property that matters, and the whole reason the buffer
    # exists: a host sending at 20 Hz must look like smooth 60 Hz motion.
    # Simulate the real cadence -- host ticks in lockstep, sends every 3rd
    # tick, client renders every frame -- and check no frame ever takes a
    # 3 px "teleport" step. Naive snap-to-newest would produce 3.0 on every
    # third frame and 0.0 on the others, which is the visible stutter.
    bi = SnapshotBuffer(60, 0.100)      # 100 ms = 6 ticks of delay
    deltas, prev, sent, frozen = [], None, 0, []
    for now in range(1, 121):
        if (now - 1) % 3 == 0:
            bi.push(now, [E(sent * 3.0)])
            sent += 1
        w = bi.sample(now)
        if w is None:
            continue
        x = w[0][2]
        if prev is not None:
            d = x - prev
            deltas.append(d)
            if d == 0.0:
                frozen.append(now)
        prev = x
    assert len(deltas) > 100, f"too few samples: {len(deltas)}"
    assert max(deltas) <= 1.01, (
        f"client teleported: max frame step {max(deltas):.2f} px, host only "
        f"moves 3.0 px per snapshot -- interpolation is not smoothing")
    # The only frozen frames are the warm-up, before two snapshots exist to
    # interpolate between. A freeze later on would mean a stalled stream.
    assert all(f <= 8 for f in frozen), \
        f"stream stalled mid-run at frames {frozen}"

    # The tick-numbering contract, which cost real debugging time. If a host
    # numbers snapshots by packet count (0,1,2,3) instead of sim tick
    # (0,3,6,9), the client's clock runs ahead of the stream and remote
    # motion nearly freezes. Both cadences must produce the same speed.
    def _speed(push_ticks):
        bb2 = SnapshotBuffer(60, 0.100)
        prev2, ds = None, []
        for now in range(1, 121):
            if (now - 1) % 3 == 0:
                bb2.push(push_ticks(now), [E((now - 1) * 1.0)])
            w = bb2.sample(now)
            if w is None:
                continue
            x = w[0][2]
            if prev2 is not None:
                ds.append(x - prev2)
            prev2 = x
        return ds
    good = _speed(lambda now: now)
    bad = _speed(lambda now: (now - 1) // 3)      # packet count, not tick
    assert max(good) <= 1.01, f"sim-tick cadence teleports: {max(good)}"
    # The wrong numbering moves the entity the same total distance, so a
    # "did it arrive" check would miss it entirely. What it breaks is
    # smoothness: the 3 px host move lands in a single frame instead of
    # being spread across three, which is exactly the visible stutter the
    # buffer exists to remove.
    assert max(bad) > 2.0, (
        "packet-count numbering should teleport (max step ~3 px); got "
        f"{max(bad):.2f}. If this asserts, the symptom changed and the "
        "push() contract note needs revisiting.")

# ── Hitscan and combat ──
    # A shooter is only a shooter if cover works. These are the cases that
    # decide whether the game is fair or broken.
    from missions import arena as AR
    from net.match import MatchSession, SNAPSHOT_EVERY, INPUT_HISTORY
    import pygame as _pg

    class _FC(object):
        def __init__(self):
            self.sent = []

        def _send(self, obj):
            self.sent.append(obj)
            return True
    _wal = _pg.Rect(200, 100, 64, 200)      # vertical wall, x 200..264

    def _host_events(fc):
        """Every event the host has put on the wire so far, flattened.

        Read from the SENT packets rather than ``drain_events()``: the event
        queue on MatchSession is the INBOUND path for a client, and a host's
        own events go out through send_events() instead. Checking the wrong
        one of those finds an empty list and looks like a missing event.
        """
        out = []
        for obj in fc.sent:
            if isinstance(obj, dict) and obj.get("t") == P.T_EVENTS:
                out.extend(obj.get("x") or ())
        return out

    def _hs(x, y, ang, walls, targets):
        return AR.hitscan(x, y, ang, walls, targets)[:2]

    assert _hs(100, 200, 0.0, [_wal], [(3, 400, 200)]) == ("wall", None), \
        "shot passed through a wall -- cover does not work"
    assert _hs(100, 200, 0.0, [], [(3, 400, 200)]) == ("player", 3), \
        "clear line of fire did not connect"
    # A target behind the shooter must never be hit.
    assert _hs(100, 200, 0.0, [], [(3, 40, 200)])[0] != "player", \
        "shot backwards hit the shooter"
    # Nearest target wins, so you cannot shoot through a player.
    assert _hs(100, 200, 0.0, [], [(3, 200, 200), (4, 500, 200)]) == \
        ("player", 3), "nearest target did not win"
    # A near miss must miss.
    assert _hs(100, 200, 0.0, [], [(3, 400, 260)])[0] == "none", \
        "shot 60px wide connected"
    # A wall closer than the player stops the shot.
    assert _hs(100, 200, 0.0, [_pg.Rect(300, 150, 40, 100)],
               [(3, 400, 200)])[0] == "wall", "wall behind the target ignored"
    # Nothing can be shot from inside geometry.
    _inside = AR.hitscan(232, 200, 0.0, [_wal], [])
    assert _inside[0] == "wall" and _inside[2] == 0.0, \
        f"ray from inside a wall was not blocked: {_inside}"
    # Range limit.
    assert _hs(100, 200, 0.0, [],
               [(3, 100 + AR.WEAPON_RANGE + 100, 200)])[0] == "none", \
        "target beyond weapon range was hit"

    # Combat, driven exactly as the network would drive it.
    _fc = _FC()
    _cs = MatchSession(_fc, is_host=True, local_id=0)
    _sim = AR.ArenaSim(_cs, AR.ARENA_YARD, score_limit=99)
    _sim.add_player(0, "Host")
    _sim.add_player(1, "Alex")
    # Open lane on row 5 of the Yard map; nothing solid between them.
    _sim.players[0]["x"], _sim.players[0]["y"] = 160.0, 352.0
    _sim.players[1]["x"], _sim.players[1]["y"] = 520.0, 352.0
    _sim.rules.spawned_at[0] = -(10 ** 6)
    _sim.rules.spawned_at[1] = -(10 ** 6)
    _sq = [0]

    def _fire(ticks=1, aim=180.0):
        for _i in range(ticks):
            _cs._accept_input(P.make_input(_sq[0], 0, 0, aim, P.F_FIRING),
                              peer_id=1)
            _sq[0] += 1
            _sim.step()

    _hp = _sim.players[0]["hp"]
    _fire(1)
    assert _sim.players[0]["hp"] == _hp - AR.WEAPON_DAMAGE, \
        f"shot did no damage: {_hp} -> {_sim.players[0]['hp']}"
    assert _sim.players[1]["ammo"] == AR.MAG_SIZE - 1, "firing did not use ammo"
    # Holding the trigger must be rate limited, or a 12-round mag empties in
    # 12 ticks and the game is not a shooter.
    _a = _sim.players[1]["ammo"]
    _fire(AR.FIRE_COOLDOWN_TICKS)
    assert _a - _sim.players[1]["ammo"] == 1, (
        "one cooldown of held trigger fired %d shots, want 1"
        % (_a - _sim.players[1]["ammo"]))
    _a = _sim.players[1]["ammo"]
    _fire(AR.FIRE_COOLDOWN_TICKS * 3)
    assert _a - _sim.players[1]["ammo"] == 3, (
        "three cooldowns fired %d shots, want 3"
        % (_a - _sim.players[1]["ammo"]))
    # Kill, and the scoreboard must credit the right player.
    _guard = 0
    while _sim.players[0]["dead"] is False and _guard < 500:
        _fire(AR.FIRE_COOLDOWN_TICKS + 1)
        _guard += 1
    assert _sim.players[0]["dead"] is True, "sustained fire never killed"
    _board = dict((p, (k, d)) for p, k, d in _sim.scoreboard())
    assert _board[1][0] >= 1 and _board[0][1] >= 1, \
        f"scoreboard miscredited the kill: {_sim.scoreboard()}"
    # Respawn restores a full mag: coming back with three rounds is a death
    # sentence with no way to fight back.
    for _i in range(AR.RESPAWN_TICKS + 5):
        _sim.step()
    assert _sim.players[0]["ammo"] == AR.MAG_SIZE, "respawn did not refill"
    assert _sim.players[0]["hp"] == 100, "respawn did not heal"
    # Emptying the mag must trigger a reload, and the reload must refill.
    #
    # Settle any reload the sustained fire above already started first. The
    # last input is still held, so those RESPAWN_TICKS steps kept pulling the
    # trigger, and a reload in flight makes _step_player return before it
    # ever looks at the magazine -- which reads as "empty magazine did not
    # auto-reload" when the real cause is a half-finished magazine swap.
    for _i in range(AR.RELOAD_TICKS + 5):
        _sim.step()
    _sim.players[1]["ammo"] = 1
    assert _sim.players[1]["reload"] == 0, \
        f"reload did not settle before the empty-mag test: {_sim.players[1]['reload']}"
    _ev_before = len(_host_events(_fc))
    _fire(2)
    assert _sim.players[1]["reload"] > 0, "empty magazine did not auto-reload"
    # A dry trigger pull is an EVENT, not silence. Only the host knows the
    # magazine was empty at the instant the player pulled, so only the host
    # can state it -- a client sees ammo counts twice a second, which is a
    # different moment entirely.
    _new = _host_events(_fc)[_ev_before:]
    assert any(e[0] == P.EV_EMPTY and e[1] == 1 for e in _new), \
        f"empty trigger pull emitted no EV_EMPTY: {_new}"
    _fire(AR.RELOAD_TICKS + 5)
    assert _sim.players[1]["ammo"] == AR.MAG_SIZE, "reload did not refill"

    # ── Arena renderer ──
    # Two real bugs lived here and both were invisible in a diff, so they
    # are pinned explicitly. See ui/arena_view.py for the long versions.
    from ui.arena_view import ArenaView, color_for

    # 0. Map geometry. A map is a list of row strings; one row of the wrong
    #    length is invisible in a diff, yet draw_tiles() silently skips the
    #    missing columns (black gap down the edge) and build_walls() can no
    #    longer merge a solid border. Crossfire shipped with two 11-char rows
    #    in an otherwise 10-wide map, which is exactly this failure.
    from missions import arena as _AR
    for _name, _rows in _AR.ARENAS.items():
        _widths = set(len(r) for r in _rows)
        assert len(_widths) == 1, (
            f"arena {_name!r} is not rectangular: row widths {sorted(_widths)}")
        assert set(_rows[0]) == {"#"} and set(_rows[-1]) == {"#"}, (
            f"arena {_name!r} top/bottom border is not solid")
        for _ridx, _row in enumerate(_rows):
            assert _row[0] == "#" and _row[-1] == "#", (
                f"arena {_name!r} row {_ridx} has an open side wall: {_row!r}")
        _spawns = _AR.spawn_points(_rows)
        assert _spawns, f"arena {_name!r} has no spawn points"
        _walls = _AR.build_walls(_rows)
        for _sx, _sy in _spawns:
            assert not any(w.collidepoint(_sx, _sy) for w in _walls), (
                f"arena {_name!r} spawn ({_sx},{_sy}) is inside a wall")
        assert _AR.max_players(_name) >= 2, (
            f"arena {_name!r} seats fewer than 2 players")
    # Capacity is a declared property of the map, and Crossfire's four
    # corner spawns are why it seats four.
    assert _AR.max_players("crossfire") == 4, "crossfire must seat 4"
    assert _AR.max_players("yard") == 8, "yard must seat 8"

    # 1. Camera convention. The missions pass a TOP-LEFT camera
    #    (`desired = target - WIDTH//2`) and Player.draw subtracts it. A
    #    screen-centred camera puts every sprite in the corner.
    _av = ArenaView("yard")
    _w = {0: P.make_entity(0, P.ENT_PLAYER, 700, 520, 0.0, 100,
                           P.PS_IDLE, 0, 0)}
    _av.update_camera(_w, 0, 1000, 700)
    assert abs((700 - _av.cam_x) - 500) < 2, (
        f"local player not centred: screen x {700 - _av.cam_x}, want 500")
    assert abs((520 - _av.cam_y) - 350) < 2, (
        f"local player not centred: screen y {520 - _av.cam_y}, want 350")

    # Camera must never leave the map, and a map smaller than the viewport
    # must be centred rather than pinned to one side (which leaves a black
    # bar down the edge).
    # A sub-viewport fixture, spelled out here: Crossfire used to be 10x10
    # (640x640) and served this role, but it is now 16x12 (1024x768) and
    # scrolls like every other arena.
    _tiny_rows = [
        "########",
        "#1....2#",
        "#......#",
        "#..##..#",
        "#..##..#",
        "#......#",
        "#3....4#",
        "########",
    ]
    _small = ArenaView("yard")
    _small.map_rows = _tiny_rows
    _small.cols, _small.rows = 8, 8
    from core.config import TILE_SIZE as _TS
    _small.map_w = 8 * _TS
    _small.map_h = 8 * _TS
    _small.walls = _AR.build_walls(_tiny_rows)
    _small._cam_init = False
    _sw = {0: P.make_entity(0, P.ENT_PLAYER, 200, 200, 0.0, 100,
                            P.PS_IDLE, 0, 0)}
    _small.update_camera(_sw, 0, 1000, 700)
    assert _small.cam_x < 0, (
        f"small map should be centred with a negative offset, got "
        f"cam_x={_small.cam_x}")

    # ...and it must still SHAKE. On a sub-viewport map the map bound is 0,
    # so the camera's final clamp pins the view to a fixed centred offset and
    # swallows every shake/kick - the arena once had no gunfeel at all on
    # the old sub-viewport Crossfire because of this. Warm the follow
    # camera first.
    # The recoil kick is used rather than screen shake because shake is
    # randomised per frame (it can coincidentally cancel the kick, making
    # the test flaky). Both ride the same returned-delta path, so a kick
    # that survives proves the clamp no longer swallows the effect.
    from core.state import STATE as _STATE
    _prev_reduced = _STATE.reduced_motion
    _STATE.reduced_motion = False   # a prior check leaves this True
    for _ in range(3):
        _small.update_camera(_sw, 0, 1000, 700)
    _base_cam_x = _small.cam_x
    _STATE.screen_shake = 0
    _STATE.cam_kick_x = 30.0
    _STATE.cam_kick_y = 30.0
    _small.update_camera(_sw, 0, 1000, 700)
    assert abs(_small.cam_x - _base_cam_x) > 1.0, (
        "camera recoil kick is swallowed on a sub-viewport arena map")
    _STATE.screen_shake = 0
    _STATE.cam_kick_x = _STATE.cam_kick_y = 0.0
    _STATE.reduced_motion = _prev_reduced

    _big = ArenaView("yard")
    for (px, py) in ((0, 0), (1407, 1087), (700, 520)):
        _big._cam_init = False
        _big.update_camera({0: P.make_entity(0, P.ENT_PLAYER, px, py, 0.0,
                                             100, P.PS_IDLE, 0, 0)},
                           0, 1000, 700)
        assert 0.0 <= _big.cam_x <= _big.map_w - 1000 + 0.001, \
            f"camera off map at x={px}: cam_x={_big.cam_x}"
        assert 0.0 <= _big.cam_y <= _big.map_h - 700 + 0.001, \
            f"camera off map at y={py}: cam_y={_big.cam_y}"

    # 2. Angle units. Snapshots carry DEGREES; Player.angle is in RADIANS
    #    because draw() feeds it straight to math.cos/math.sin. Feeding
    #    degrees straight in points every player at a nonsense bearing.
    import math as _math
    _av2 = ArenaView("yard")
    _posed = _av2.sync({1: P.make_entity(1, P.ENT_REMOTE, 100, 100,
                                         90.0, 100, P.PS_IDLE, 0, 0)})
    _deg = _math.degrees(_posed[1][0].angle) % 360.0
    assert abs(_deg - 90.0) < 1.0, (
        f"snapshot angle 90 deg became {_deg:.1f} on the sprite -- units "
        "mismatch between the wire format (degrees) and Player.angle "
        "(radians)")
    # And the 0/360 seam must take the short way, in radians.
    _av3 = ArenaView("yard")
    p1 = P.make_entity(1, P.ENT_REMOTE, 100, 100, 350.0, 100, P.PS_IDLE, 0, 0)
    q1 = _av3.sync({1: p1})[1][0]
    p2 = P.make_entity(1, P.ENT_REMOTE, 100, 100, 10.0, 100, P.PS_IDLE, 0, 0)
    q2 = _av3.sync({1: p2})[1][0]
    step = _math.degrees(q2.angle - q1.angle) % 360.0
    assert step < 90.0, (
        f"crossing the 0/360 seam rotated {step:.1f} deg; it should be the "
        "short way (20 deg)")

    # A player who leaves must not leave a ghost sprite behind for the next
    # person to inherit.
    _av4 = ArenaView("yard")
    _av4.sync({5: P.make_entity(5, P.ENT_REMOTE, 100, 100, 0.0, 100,
                                 P.PS_IDLE, 0, 0)})
    assert 5 in _av4._views
    _av4.sync({})
    assert 5 not in _av4._views, "left player's sprite was not released"

    # A remote player's shot must be VISIBLE to the observer. The wire only
    # carries an F_FIRING flag (the arena is hitscan, no bullets on the
    # wire), so the view turns it into a muzzle flash AND a traced bullet.
    # Previously the tracer was drawn only on the shooter's machine, so
    # nobody else saw anyone's shots.
    _av5 = ArenaView("yard")
    _firing = P.make_entity(1, P.ENT_REMOTE, 700, 520, 0.0, 100,
                            P.PS_SHOOTING, 0, P.F_FIRING)
    _p5 = _av5.sync({1: _firing})
    assert getattr(_p5[1][0], "_arena_muzzle", 0) > 0, \
        "F_FIRING did not raise the muzzle/tracer timer"
    _av5.draw_players(config.screen, _p5, 0)   # must not raise

    # Every player needs a colour distinguishable from the local player.
    assert color_for(0, 0) != color_for(1, 0), "local and remote share a colour"

    # ── Match transport (step 3) ──
    # One MatchSession per client, driven from the fixed-timestep loop.
    from net.match import MatchSession, SNAPSHOT_EVERY, INPUT_HISTORY
    from missions import arena as AR
    from net import client as NC

    class _FC(object):
        def __init__(self):
            self.sent = []

        def _send(self, obj):
            self.sent.append(obj)
            return True

    # Host broadcasts on the 20 Hz cadence, not every tick.
    fc = _FC()
    hs = MatchSession(fc, is_host=True, local_id=0)
    hs.world = [P.make_entity(0, P.ENT_PLAYER, 100, 100)]
    for _ in range(90):
        hs.tick_once()
    snaps = [m for m in fc.sent if m["t"] == P.T_SNAPSHOT]
    assert len(snaps) == 90 // SNAPSHOT_EVERY, \
        f"host sent {len(snaps)} snapshots, want {90 // SNAPSHOT_EVERY}"
    assert snaps[0]["k"] == SNAPSHOT_EVERY, \
        "first broadcast must be tick 3 (sim tick, not packet count)"

    # Client input reaches the host; the newest wins.
    cc = _FC()
    cs = MatchSession(cc, is_host=False)
    for _i in range(4):
        cs.tick_once()
        cs.send_input(-1, 0, 90.0, P.F_FIRING)
    cs.tick_once()
    cs.send_input(1, 0, 90.0, P.F_FIRING)
    for m in [x for x in cc.sent if x["t"] == P.T_INPUT]:
        assert hs._accept_input(m, peer_id=7)
    got = hs.consume_input(7)
    # Five sends -> sequences 0..4, so the newest is q=4.
    assert got is not None and got["mx"] == 1 and got["q"] == 4, \
        f"newest input should win, got {got}"
    assert hs.consume_input(99) is None, "unknown peer must yield None"
    # Input history must stay bounded against a flooding peer.
    hf = MatchSession(_FC(), is_host=True)
    for i in range(200):
        hf._accept_input(P.make_input(i, 1, 0, 0, 0), peer_id=3)
    assert len(hf._inputs[3]) <= INPUT_HISTORY + 1, \
        f"input history unbounded: {len(hf._inputs[3])}"
    # Hostile match traffic must be dropped, never raised on.
    assert hf._accept_input("garbage") is False
    assert hf._accept_snapshot({"t": P.T_SNAPSHOT, "k": 1, "e": "bad"}) is False

    # The client routes gameplay traffic to an attached session, and to
    # nowhere when none is attached.
    cl = NC.MPRelayClient(host="127.0.0.1", port=1, chat_enabled=False)
    assert cl._match_snapshot({"t": P.T_SNAPSHOT, "k": 1, "e": []}) is False
    assert cl._match_input({"t": P.T_INPUT, "q": 1}) is False
    ms = MatchSession(_FC(), is_host=False)
    cl.attach_match(ms)
    assert cl._match_snapshot(P.make_snapshot(
        1, [P.make_entity(0, P.ENT_PLAYER, 10, 10)])) is True, \
        "attached session did not receive the snapshot"
    assert cl._match_input(P.make_input(0, 1, 0, 0, 0)) is True
    cl.detach_match()
    assert cl._match_snapshot(P.make_snapshot(2, [])) is False

    # ── Arenas ──
    for _name, _rows in AR.ARENAS.items():
        _w = AR.build_walls(_rows)
        _sp = AR.spawn_points(_rows)
        assert _sp, f"arena {_name} has no spawn points"
        assert _w, f"arena {_name} has no walls"
        assert AR.pickups(_rows), f"arena {_name} has no pickups"
        # A player spawning inside a wall is stuck and unfixable, so this
        # is a hard requirement rather than a nicety.
        for (x, y) in _sp:
            for _wall in _w:
                assert not _wall.collidepoint(x, y), \
                    f"arena {_name}: spawn {x},{y} is inside a wall"
    # Merging must actually merge: the border is far fewer rects than tiles.
    _yard = AR.build_walls(AR.ARENA_YARD)
    _solid = sum(row.count("#") for row in AR.ARENA_YARD)
    assert len(_yard) < _solid, \
        f"walls not merged: {len(_yard)} rects for {_solid} solid tiles"

    # ── Deathmatch rules ──
    dm = AR.Deathmatch(AR.ARENA_YARD, score_limit=3)
    dm.register(0)
    dm.register(1)
    dm.note_position(1, (200, 200))
    # Spawn away from a living enemy: the furthest spawn point.
    _got = dm.spawn_position(0, 10)
    _far = max(AR.spawn_points(AR.ARENA_YARD),
               key=lambda p: (p[0] - 200) ** 2 + (p[1] - 200) ** 2)
    assert _got == _far, f"spawned at {_got}, furthest is {_far}"
    dm.kill(0, 1, 100)
    assert dm.alive(1, 100) is False
    assert dm.alive(1, 100 + AR.RESPAWN_TICKS + 1) is True
    assert dm.kill(0, 1, 200) is False
    assert dm.kill(0, 1, 300) is True and dm.winner == 0
    assert dm.scoreboard()[0][0] == 0
    # Suicide must never score.
    _before = dm.kills[1]
    assert dm.kill(1, 1, 400) is False and dm.kills[1] == _before
    # Spawn protection.
    dm2 = AR.Deathmatch(AR.ARENA_YARD)
    dm2.register(0)
    dm2.spawned_at[0] = 10
    assert dm2.protection_flag(0, 12) == P.F_INVULNERABLE
    assert dm2.protection_flag(0, 10 + AR.SPAWN_PROTECT_TICKS + 1) == 0

    # ── Host simulation ──
    # The whole match must run headless: that is the only practical way to
    # be confident about netcode.
    hfc = _FC()
    session = MatchSession(hfc, is_host=True, local_id=0)
    sim = AR.ArenaSim(session, AR.ARENA_YARD, score_limit=5)
    sim.add_player(0, "Host")
    sim.add_player(1, "Alex")
    x_start = sim.players[1]["x"]
    sq = 0
    for _ in range(180):
        session._accept_input(P.make_input(sq, 1, 0, 0.0, 0), peer_id=1)
        sq += 1
        sim.step()
    assert sim.players[1]["x"] > x_start, "remote input did not move the player"
    sent = [m for m in hfc.sent if m["t"] == P.T_SNAPSHOT]
    assert len(sent) == 180 // 3, \
        f"host sent {len(sent)} snapshots in 180 ticks"
    parsed = P.parse_snapshot(sent[-1])
    assert parsed is not None and len(parsed[1]) == 2, "snapshot lost a player"

    # Collision: walking into the border forever must never leave the map.
    esc = MatchSession(_FC(), is_host=True, local_id=0)
    sim2 = AR.ArenaSim(esc, AR.ARENA_YARD, score_limit=99)
    sim2.add_player(1, "X")
    cols, _rws = AR.map_size(AR.ARENA_YARD)
    sq = 0
    for _ in range(900):
        esc._accept_input(P.make_input(sq, 1, 0, 0.0, 0), peer_id=1)
        sq += 1
        sim2.step()
    assert sim2.players[1]["x"] < cols * 64, \
        f"player escaped the map: x={sim2.players[1]['x']} >= {cols * 64}"

    # Death, then respawn.
    assert sim2.damage(1, 200, killer_id=0) is True
    assert sim2.players[1]["dead"] is True
    # Damage during spawn protection must be ignored entirely.
    sim2.rules.spawned_at[1] = -10 ** 6
    assert sim2.damage(1, 50, killer_id=0) is False
    assert sim2.players[1]["hp"] == 0, "protection did not block damage"
    for _ in range(AR.RESPAWN_TICKS + 10):
        sim2.step()
    assert sim2.players[1]["dead"] is False, "never respawned"
    assert sim2.players[1]["hp"] == 100, "respawned at the wrong hp"

    # ── The vertical slice, end to end ──
    # Host simulates two players; a separate client session receives the
    # snapshots and interpolates. This is the property steps 1-3 exist to
    # deliver: a remote player moves smoothly on another machine. The host
    # moves 5 px/tick and publishes every 3rd tick, so each snapshot
    # carries 15 px. A client that failed to interpolate would show those
    # 15 px as one visible jump.
    hfc2 = _FC()
    h2 = MatchSession(hfc2, is_host=True, local_id=0)
    s2 = AR.ArenaSim(h2, AR.ARENA_YARD, score_limit=99)
    s2.add_player(0, "Host")
    s2.add_player(1, "Alex")
    c2 = MatchSession(_FC(), is_host=False, local_id=0)
    seq, steps, prev, none_frames = 0, [], None, 0
    for _ in range(300):
        h2._accept_input(P.make_input(seq, 1, 0, 0.0, 0), peer_id=1)
        seq += 1
        s2.step()
        while hfc2.sent and hfc2.sent[-1].get("t") == P.T_SNAPSHOT:
            c2._accept_snapshot(hfc2.sent.pop())
        c2.tick = h2.tick
        world = c2.sample_world()
        if world is None:
            none_frames += 1
            continue
        if 1 not in world:
            continue
        x = world[1][2]
        if prev is not None:
            steps.append(x - prev)
        prev = x
    assert len(steps) > 200, f"client drew only {len(steps)} frames"
    assert none_frames <= 8, f"client had no world for {none_frames} frames"
    assert max(steps) <= 6.0, (
        f"remote player teleported: max frame step {max(steps):.2f} px, but a "
        "snapshot carries 15 px -- interpolation is not smoothing")
    _before = dm.kills[1]
    assert dm.kill(1, 1, 400) is False and dm.kills[1] == _before
    # Spawn protection.
    dm2 = AR.Deathmatch(AR.ARENA_YARD)
    dm2.register(0)
    dm2.spawned_at[0] = 10
    assert dm2.protection_flag(0, 12) == P.F_INVULNERABLE
    assert dm2.protection_flag(0, 10 + AR.SPAWN_PROTECT_TICKS + 1) == 0
    # The host tool builds a single-row state ──
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import mp_host as _h
    import mp_server as _srv

    class _Args:
        name = "Smoke Host"
        max_players = 4
    state = _h.build_state(_Args())
    rows, rules = state.list_payload()
    assert len(rows) == 1, f"host should publish exactly one row, got {rows!r}"
    assert rows[0][0] == "Smoke Host", f"wrong name: {rows[0]!r}"
    assert rows[0][2] == 4, f"wrong max players: {rows[0]!r}"
    assert "Smoke Host" in rules and rules["Smoke Host"], "host row needs rules"
    # The published row must survive the client's own validation.
    from net import protocol as _P
    assert _P.normalize_row(rows[0]) is not None, "host row failed normalize"
    # firewall_hint must always return usable text.
    assert isinstance(_h.firewall_hint(), str) and _h.firewall_hint()
    # --check must be runnable and must not bind a port.
    assert _h.main(["--check", "-q"]) == 0


def check_font_glyph_coverage():
    """No rendered string may contain a glyph the bundled fonts lack.

    A character with no glyph draws as a tofu box, and the bundled faces
    are a narrow Latin + Cyrillic set: no triangles, no emoji, no warning
    signs, no block bullets. Oswald (used for the title/location banners)
    is narrower still and has no arrows or block glyphs, so those are
    allow-listed as Plex-only - every string that uses them is rendered
    with a Plex face.

    fontTools is a dev-only dependency; skip rather than fail without it.
    """
    try:
        from fontTools.ttLib import TTFont
    except ImportError:
        return

    import ast

    font_dir = config.resource_path(os.path.join("assets", "fonts"))

    faces = {
        "plex_regular": "IBMPlexMono-Regular.ttf",
        "plex_bold": "IBMPlexMono-Bold.ttf",
        "plex_semibold": "IBMPlexMono-SemiBold.ttf",
        "oswald": "Oswald.ttf",
    }

    coverage = {}

    for key, fname in faces.items():
        path = os.path.join(font_dir, fname)

        assert os.path.exists(path), f"bundled font missing: {path}"

        font = TTFont(path, fontNumber=0, lazy=True)

        chars = set()

        for table in font["cmap"].tables:
            chars |= set(table.cmap.keys())

        coverage[key] = chars

    # Plex-only: fine in any Plex face, must never reach an Oswald surface.
    plex_only = {0x2190, 0x2191, 0x2192, 0x2193, 0x2588}

    src_root = Path(__file__).resolve().parent.parent / "src"

    missing = {}

    for py in sorted(src_root.rglob("*.py")):

        if "__pycache__" in py.parts:
            continue

        try:
            tree = ast.parse(py.read_text(encoding="utf-8-sig"))
        except SyntaxError:
            continue

        # Docstrings are never drawn, so they are not glyph obligations.
        for node in ast.walk(tree):
            body = getattr(node, "body", None)

            if isinstance(node, (ast.Module, ast.FunctionDef,
                                 ast.AsyncFunctionDef, ast.ClassDef)):
                if body and isinstance(body[0], ast.Expr) \
                        and isinstance(body[0].value, ast.Constant) \
                        and isinstance(body[0].value.value, str):
                    body.pop(0)

        for node in ast.walk(tree):
            if not (isinstance(node, ast.Constant)
                    and isinstance(node.value, str)):
                continue

            for ch in node.value:
                cp = ord(ch)

                if cp < 128 or cp in plex_only:
                    continue

                for key, chars in coverage.items():
                    if cp not in chars:
                        missing.setdefault(cp, set()).add(key)

    assert not missing, "tofu glyphs: " + "; ".join(
        "U+%04X missing in %s" % (cp, ",".join(sorted(faces_)))
        for cp, faces_ in sorted(missing.items())
    )


# ── Cosmetics and the Acaribucks economy ────────────────────────────────
# Everything here runs against the temp profile.json wired up at the top of
# this file, so no check can move a real player's money.

# The colours entities/player.py drew before it could be recolored, transcribed
# from the pre-customization file. If one of these drifts, every sprite in the
# game changes appearance on someone who never bought anything.
LEGACY_BODY = {
    "uniform": (60, 70, 50), "skin": (210, 180, 140),
    "helmet": (30, 35, 28), "helmet_arc": (50, 58, 42),
    "eyes": (30, 20, 10),
    "kevlar": (50, 52, 56), "kevlar_edge": (28, 30, 32),
    "kevlar_line": (25, 27, 30), "kevlar_ridge": (38, 40, 44),
}
LEGACY_RIGS = {
    "os12": {
        "receiver": (38, 36, 32), "cover": (58, 56, 52),
        "cover_edge": (22, 20, 18), "wood": (110, 70, 40),
        "wood_edge": (75, 48, 28), "barrel": (70, 68, 64),
        "muzzle": (50, 48, 44), "groove": (35, 33, 30),
        "bore": (8, 8, 10), "front_sight": (45, 43, 40),
        "mag": (28, 27, 24), "mag_edge": (16, 15, 13),
        "mag_ridge": (20, 19, 17),
    },
    "k9": {
        "receiver": (22, 25, 25), "receiver_edge": (72, 88, 82),
        "receiver_shine": (105, 126, 116), "can": (36, 40, 40),
        "can_shine": (96, 112, 104), "bore": (6, 8, 8),
        "stock": (62, 70, 66), "stock_knob": (38, 44, 42),
        "grip": (28, 30, 30), "grip_shine": (92, 100, 96),
        "mag": (20, 22, 22), "mag_edge": (76, 88, 82),
        "mag_line": (36, 40, 38),
    },
    "pistol": {
        "frame": (24, 25, 27), "slide": (52, 55, 58),
        "slide_edge": (12, 13, 15), "barrel": (70, 74, 78),
        "bore": (8, 8, 10), "grip": (18, 19, 20),
        "optic": (180, 35, 35),
    },
}


def check_appearance_default_is_legacy():
    """The catalog must carry the exact pixels the sprite used to hard-code.

    This is the table half of the parity proof. The pixel half is
    avatar_render_parity below, and tools/avatar_parity.py goes further and
    renders the pre-change file itself.
    """
    resolved = _appearance.resolve(None)
    for role, want in LEGACY_BODY.items():
        got = resolved[role]
        assert tuple(got) == want, "role %s is %s, was %s" % (role, tuple(got), want)
    for gun, roles in LEGACY_RIGS.items():
        for role, want in roles.items():
            got = tuple(resolved["rigs"][gun][role])
            assert got == want, "%s %s is %s, was %s" % (gun, role, got, want)
    # A palette that recolored the face would let a colour scheme encode a
    # racial read of the character. The renderer refuses it; the catalog is not
    # allowed to tempt it.
    for pid, entry in _appearance.PALETTES.items():
        assert "skin" not in entry["roles"], "%s tries to recolor skin" % pid
    # Every finish must name roles its own gun actually has, or buying it
    # silently changes nothing and the player has spent money on a no-op.
    for fid, entry in _appearance.FINISHES.items():
        gun = entry["gun"]
        for role in entry["roles"]:
            assert role in _appearance.GUN_BASE[gun], \
                "%s overrides %r, which %s does not have" % (fid, role, gun)
    counts = (len(_appearance.PALETTES), len(_appearance.HEADGEARS),
              len(_appearance.FINISHES))
    assert sum(counts) == 32, "catalog size changed: %s" % (counts,)
    for free in _appearance.FREE_ITEM_IDS:
        assert _appearance.price_of(free) == 0, "%s is free by name only" % free


def _render_look(app, rig="os12", angle=0.6):
    """One deterministic frame of the sprite with *app* worn on *rig*."""
    from entities.player import Player
    os.environ["ACA_FREEZE"] = "1"
    surf = pygame.Surface((220, 220), pygame.SRCALPHA)
    p = Player(96, 96, appearance=app)
    p.angle = angle
    p.rig_weapon = rig
    p.blink_timer = 40
    p.walk_cycle = 0.3
    p.visible = True
    p.draw(surf, offset_x=0, offset_y=0)
    return pygame.image.tostring(surf, "RGBA")


def check_avatar_render_parity():
    """Default appearance must render the old sprite, and non-default must not.

    Both halves matter. A renderer that ignored the palette entirely would pass
    a comparison of default-against-default forever, which is the failure mode
    that would ship a shop selling colours nobody can see.
    """
    baseline = _render_look(None)
    assert baseline == _render_look(_appearance.default_appearance()), \
        "explicit default appearance does not match the legacy sprite"
    assert baseline != _render_look(_appearance.make(palette="pal_noir")), \
        "a palette changed nothing on screen"
    assert baseline != _render_look(_appearance.make(head="head_beret")), \
        "head gear changed nothing on screen"
    assert baseline != _render_look(
        _appearance.make(finish={"os12": "os12_goldleaf"})), \
        "a weapon finish changed nothing on screen"
    # Every catalog item has to render without raising, and every one has to
    # look like something - a hat that draws nothing is indistinguishable from
    # a hat that was never wired up.
    for head in _appearance.HEADGEARS:
        assert _render_look(_appearance.make(head=head)) != baseline or head \
            == _appearance.DEFAULT_HEAD, "head %s renders as the default" % head
    for gun, rig in (("os12", "os12"), ("k9", "k9_smg"), ("pistol", "pistol")):
        for fid, entry in _appearance.FINISHES.items():
            if entry["gun"] != gun:
                continue
            assert _render_look(_appearance.make(finish={gun: fid}), rig=rig)
    # A junk identifier from a newer catalog must still produce a person.
    assert _render_look({"palette": "pal_from_the_future", "head": 42}) == baseline


def check_appearance_junk_rejected():
    """Nothing a peer or a hand-edited file claims may survive as a colour."""
    default = _appearance.default_appearance()
    # A bundle with far more keys than an appearance has is refused whole,
    # before any of its values is read.
    bloated = {"palette": "pal_krap"}
    for i in range(40):
        bloated["extra%d" % i] = "v"
    junk = [
        None, "pal_krap", 42, [], {},
        {"palette": "x" * 4000},
        {"palette": {"nested": True}, "head": ["a"]},
        bloated,
        {"finish": "not-a-dict"},
        {"finish": {"nonexistent_gun": "os12_blued"}},
        # A finish bought for one gun cannot be worn on another.
        {"finish": {"os12": "k9_arctic"}},
    ]
    for raw in junk:
        got = _appearance.normalize(raw)
        assert got == default, "%r normalized to %r" % (raw, got)
    # A valid claim survives, and only the valid part of a mixed claim.
    mixed = _appearance.normalize({"palette": "pal_krap", "head": "bogus"})
    assert mixed["palette"] == "pal_krap" and mixed["head"] == default["head"], mixed
    assert _appearance.key_of(None) == _appearance.key_of(default), \
        "key_of must canonicalize before hashing"
    assert _appearance.key_of(mixed) != _appearance.key_of(default)


def check_profile_wallet():
    """Buy, wear, persist, and survive a hand-edited file."""
    from core import json_store
    ps = _profile_store
    ps.save({"version": 1, "acaribucks": 500, "lifetime_earned": 500,
             "rounds_scored": 10, "owned": list(_appearance.FREE_ITEM_IDS),
             "equipped": _appearance.default_appearance(), "credited": []})
    assert ps.balance() == 500, ps.balance()
    assert ps.buy("not_a_hat") == (False, "unknown")
    bought = ps.buy("pal_coyote")
    assert bought == (True, "ok"), "first purchase returned %r" % (bought,)
    assert ps.balance() == 380, "price was not deducted: %s" % ps.balance()
    assert ps.buy("pal_coyote") == (False, "owned"), "double purchase allowed"
    # Equipping something not owned has to be refused at the store, not only in
    # the UI, because the UI is one bug away from granting it.
    assert not ps.equip("pal_parade"), "unowned palette was equipped"
    assert ps.equip("pal_coyote"), "owned palette refused"
    assert ps.equipped()["palette"] == "pal_coyote"
    # Reload from disk: the write has to have actually landed.
    assert ps.load()["acaribucks"] == 380
    assert ps.equipped()["palette"] == "pal_coyote", "equipped did not persist"
    # A short balance must not partially spend.
    assert ps.buy("head_heavy_helmet") == (False, "poor")
    assert ps.balance() == 380, "a refused purchase moved money"
    # Tampering: claim a hat you never bought, and inflate the wallet.
    raw = ps.load()
    raw["equipped"] = {"palette": "pal_parade", "head": "head_heavy_helmet",
                       "finish": dict(raw["equipped"]["finish"])}
    raw["acaribucks"] = 10 ** 12
    raw["owned"] = ["pal_coyote", "made_up_item", None, 7]
    json_store.atomic_write(ps.PROFILE_FILE, raw)
    loaded = ps.load()
    assert loaded["acaribucks"] == ps.BALANCE_MAX, \
        "balance was not clamped: %s" % loaded["acaribucks"]
    assert loaded["equipped"]["palette"] == _appearance.DEFAULT_PALETTE, \
        "a hand-edited file equipped an unowned palette"
    assert loaded["equipped"]["head"] == _appearance.DEFAULT_HEAD
    assert "made_up_item" not in loaded["owned"]
    # The free defaults are always present, whatever the file claimed.
    for free in _appearance.FREE_ITEM_IDS:
        assert free in loaded["owned"], "%s vanished from owned" % free
    # Corrupt the primary file; the backup has to carry the load. The .bak is
    # whatever atomic_write last replaced, which here is the honest profile from
    # before the tamper - so recovery must hand back the pre-tamper wallet, not
    # the inflated one it is replacing.
    with open(ps.PROFILE_FILE, "w", encoding="utf-8") as fh:
        fh.write("{ this is not json")
    recovered = ps.load()
    assert recovered["acaribucks"] == 380, \
        "corrupt profile did not fall back to the backup: %r" % (
            recovered["acaribucks"],)
    assert "pal_coyote" in recovered["owned"], "backup lost a purchase"


def check_round_credit_is_once_per_round():
    """One round, one payment, however many times the card is re-derived."""
    ps = _profile_store
    ps.save({"version": 1, "acaribucks": 0, "lifetime_earned": 0,
             "rounds_scored": 0, "owned": list(_appearance.FREE_ITEM_IDS),
             "equipped": _appearance.default_appearance(), "credited": []})
    assert ps.credit_round("cafe:1:0:15", 82) is True
    assert ps.balance() == 82, ps.balance()
    # The round-end card stays up for five seconds and the edge can be
    # re-evaluated after a pause; neither may pay twice.
    assert ps.credit_round("cafe:1:0:15", 82) is False
    assert ps.balance() == 82, "a repeated round key paid again"
    assert ps.credit_round("cafe:2:0:3", 14) is True
    assert ps.balance() == 96
    # A different match token is a different match.
    assert ps.credit_round("beef:1:0:15", 82) is True
    assert ps.credit_round("", 50) is False, "an empty key was accepted"
    assert ps.credit_round("cafe:3:0:0", 0) is True, "a zero round must still log"
    # The log is bounded, so a long career cannot grow profile.json forever.
    for i in range(60):
        ps.credit_round("bulk:%d:0:1" % i, 1)
    assert len(ps.load()["credited"]) <= ps.CREDITED_MAX, \
        "credit log grew past its bound"


def check_payout_is_result_only():
    """Acaribucks come from what happened in the round, capped and clamped."""
    from missions import arena as ar
    board = [[0, 15, 2], [1, 9, 4], [2, 4, 6], [3, 0, 8]]
    got = ar.compute_payout(ar.MODE_FFA, board, 0, 0, {}, {})
    assert got == (82, 15, 0, True), "15-kill FFA win paid %r" % (got,)
    assert ar.compute_payout(ar.MODE_FFA, board, 0, 2, {}, {})[0] == 17
    # Winning nothing with nothing is nothing. This is the rule that keeps the
    # economy out of being an idle timer.
    assert ar.compute_payout(ar.MODE_FFA, board, 0, 3, {}, {}) == (0, 0, 3, False)
    # A player seated after the board was built earns nothing for it.
    assert ar.compute_payout(ar.MODE_FFA, board, 0, 42, {}, {})[0] == 0
    # Team play pays the side, and never pays two teammates as both first.
    teams = {"0": 0, "1": 0, "2": 1}
    scores = {"0": 27, "1": 5}
    tboard = [[0, 15, 1], [1, 12, 3], [2, 5, 4]]
    win = ar.compute_payout(ar.MODE_TDM, tboard, 1, 0, teams, scores)
    lose = ar.compute_payout(ar.MODE_TDM, tboard, 1, 2, teams, scores)
    assert win[3] is True and win[2] == 0, "teammate did not read as the winner"
    assert lose[3] is False and lose[2] == 1, "losing side did not place 2nd"
    assert win[0] > lose[0]
    # Clock timeout: no winner id, so the higher side took it.
    assert ar.compute_payout(ar.MODE_TDM, tboard, None, 0, teams, scores)[3]
    assert not ar.compute_payout(ar.MODE_TDM, tboard, None, 2, teams, scores)[3]
    # A doctored or broken board cannot inflate a payout past the cap, and
    # cannot raise. Kills are the host's number; this only reads it.
    for bad in ([[0, 10 ** 9, 0]], [[0, "lots", 0]], [[0, None, 0]], "junk", None):
        amount, kills, _place, _won = ar.compute_payout(
            ar.MODE_FFA, bad, None, 0, {}, {}, score_limit=15)
        assert 0 <= kills <= 15, "kills escaped the score limit: %r" % (bad,)
        assert 0 <= amount <= ar.PAYOUT_MAX, "payout escaped its cap: %r" % (bad,)
    assert ar.compute_payout(None, None, None, "x", None, None) == (0, 0, 0, False)


def check_arena_look_reaches_the_sprite():
    """A loadout published by the host has to end up on the cached sprite.

    The arena keeps one Player per SLOT and reuses it as people come and go, so
    the repaint has to be driven by the loadout changing, not by the sprite
    being new. Getting this wrong shows up as a replaced player wearing the
    stranger's hat.
    """
    from entities.player import Player
    from ui.arena_view import ArenaView
    view = ArenaView("yard")
    assert view.look_for(0) == _appearance.default_appearance(), \
        "an unpublished slot should draw the default"
    sprite = Player(0, 0)
    assert sprite.look == _appearance.default_appearance(), \
        "a bare Player should be the legacy look"
    view._views[3] = sprite
    krap = _appearance.make(palette="pal_krap", head="head_goggles")
    view._looks = {"3": krap}
    posed = view._pose(3)
    assert posed is sprite, "_pose should reuse the cached sprite"
    assert posed.look["palette"] == "pal_krap", "loadout did not reach the sprite"
    assert posed._rk["uniform"] == _appearance.PALETTES["pal_krap"]["roles"]["uniform"]
    # Same slot, new occupant with nothing claimed: must repaint, not persist.
    view._looks = {}
    view._pose(3)
    assert sprite.look == _appearance.default_appearance(), \
        "a reused slot kept the previous player's colours"
    # A peer claiming an item from a catalog this build does not have.
    view._looks = {"3": {"palette": "pal_impossible"}}
    assert view.look_for(3) == _appearance.default_appearance()


def check_outfitter_screen():
    """The shop opens, cycles, sells, wears and leaves without raising."""
    from ui import shop as shop_mod
    ShopScreen = shop_mod.ShopScreen
    ACTION = shop_mod.ACTION
    ps = _profile_store
    ps.save({"version": 1, "acaribucks": 1000, "lifetime_earned": 1000,
             "rounds_scored": 20, "owned": list(_appearance.FREE_ITEM_IDS),
             "equipped": _appearance.default_appearance(), "credited": []})
    surf = pygame.Surface((config.WIDTH, config.HEIGHT), pygame.SRCALPHA)
    shop = ShopScreen()
    # No item name may be truncated in its cell. A shop where "Ballistic
    # Goggles" reads as "Ballisti..." sells a hat under a broken label, and the
    # regression is silent: everything still draws, so only a reader notices.
    cell_w = shop_mod.LABEL_MAX_W
    for table in (_appearance.PALETTES, _appearance.HEADGEARS,
                  _appearance.FINISHES):
        for item_id, entry in table.items():
            lines = shop_mod._name_lines(
                config.font_terminal_small, entry["name"], cell_w)
            assert len(lines) <= 2, \
                "%r needs %d lines in a %dpx cell" % (entry["name"],
                                                      len(lines), cell_w)
            for line in lines:
                assert not line.endswith("..."), \
                    "%r truncated to %r" % (entry["name"], line)
                assert config.font_terminal_small.size(line)[0] <= cell_w, \
                    "%r overflows its cell at %dpx" % (line,
                        config.font_terminal_small.size(line)[0])
    assert shop.handle_event(
        pygame.event.Event(pygame.KEYDOWN, {"key": pygame.K_ESCAPE}),
        (0, 0)) is None, "input on a closed panel should be ignored"
    shop.open_panel("MENU")
    assert shop.mode == "open" and shop.return_to == "MENU"
    for tab in range(len(shop_mod.TABS)):
        shop.tab = tab
        shop.gun = _appearance.GUN_KEYS[tab % 3]
        shop.selected = shop._first_unowned()
        shop.update(0.016)
        shop.draw(surf)
        assert shop._rects, "tab %d laid out no cells" % tab
        # Every cell must map to a real catalog item, or a click selects junk.
        for _rect, item_id in shop._rects:
            assert _appearance.is_known(item_id), "cell offers %r" % item_id
    # Buy by clicking: select a palette cell, then press the action button.
    shop.tab, shop.gun = 0, "os12"
    shop.draw(surf)
    target = [r for r, i in shop._rects if i == "pal_coyote"]
    assert target, "PALETTES tab did not offer pal_coyote"
    point = target[0].center
    shop.handle_event(pygame.event.Event(
        pygame.MOUSEBUTTONDOWN, {"button": 1, "pos": point}), point)
    assert shop.selected == "pal_coyote", "click did not select the cell"
    press = ACTION.center
    shop.handle_event(pygame.event.Event(
        pygame.MOUSEBUTTONDOWN, {"button": 1, "pos": press}), press)
    assert "pal_coyote" in ps.load()["owned"], "action button did not buy"
    assert ps.balance() == 880, "wrong price charged: %s" % ps.balance()
    assert ps.equipped()["palette"] == "pal_coyote", "bought but not worn"
    shop.update(3.0)
    assert shop.toast == "", "toast never expired"
    # Re-pressing on an owned item must not charge again.
    shop.handle_event(pygame.event.Event(
        pygame.MOUSEBUTTONDOWN, {"button": 1, "pos": press}), press)
    assert ps.balance() == 880, "a second press re-charged an owned item"
    assert shop.handle_event(
        pygame.event.Event(pygame.KEYDOWN, {"key": pygame.K_ESCAPE}),
        (0, 0)) == "back", "ESC should ask to leave"


def check_outfitter_lives_behind_multiplayer():
    """The shop is reached from the multiplayer screen, not the main menu.

    Acaribucks come from arena results and the loadouts are worn where other
    players can see them, so the entrance belongs next to the balance that
    feeds it. Putting it on the main menu would present a multiplayer economy
    as a campaign feature - and the menu's button indices are a contract with
    acaristan.py's routing, so a row added or dropped here has to match there.
    """
    menu.draw_menu_background()
    menu.draw_menu()
    texts = [b.text for b in menu.buttons]
    assert texts == ["CONTINUE", "NEW CAMPAIGN", "MULTIPLAYER", "SETTINGS",
                     "EXIT"], texts
    assert "OUTFITTER" not in texts, "the shop leaked back onto the main menu"
    visible = sorted(b.y for b in menu.buttons if b.y > 0)
    assert len(set(visible)) == len(visible), "two menu buttons share a row"
    # The KRAPNET WIRE ticker strip starts at HEIGHT-56 and the footer divider
    # is at HEIGHT-50; a button bottom below either is drawn through.
    lowest = max(visible)
    assert lowest + 40 <= config.HEIGHT - 60, \
        "last menu button at y=%d collides with the ticker" % lowest

    # The multiplayer browser is where it lives. Its rect is only positioned
    # during the draw, so drawing first is part of the assertion.
    menu.draw_menu_background()
    menu.draw_server_browser(-1, False, "")
    rect = menu.outfitter_btn_rect
    assert rect.x > 0 and rect.y > 0, \
        "the multiplayer screen never laid out the OUTFITTER button"
    assert rect.right <= config.WIDTH, "the OUTFITTER button runs off screen"
    # Not a tab: it leaves the panel, and a tab that navigates away reads as a
    # broken tab the first time it is clicked.
    assert not rect.colliderect(menu.servers_tab_rect), \
        "OUTFITTER overlaps the SERVERS tab"
    assert not rect.colliderect(menu.connections_tab_rect), \
        "OUTFITTER overlaps the CONNECTIONS tab"
    assert "SHOP" in menu.CURSOR_ARROW_STATES, \
        "the shop would show an OS cursor beside the custom one"


def check_cosmetic_loadout_survives_a_match():
    """End to end: a client's claimed loadout reaches the host's published state.

    The seat call is where a claim becomes a colour, so this is the one path a
    peer cannot talk around by editing its own files.
    """
    from net.match import MatchSession
    from net import protocol as P
    from missions import arena as AR

    class _Sink:
        def _send(self, obj):
            return True

    sim = AR.ArenaSim(MatchSession(_Sink(), is_host=True), AR.ARENA_YARD,
                      score_limit=99)
    krap = _appearance.make(palette="pal_krap", head="head_goggles",
                            finish={"os12": "os12_blued"})
    claim = P.make_join_match("yard", "Nika", krap)
    sim.add_player(0, "Host")
    sim.add_player(1, "Nika", P.join_match_appearance(claim))
    state = sim.match_state()
    assert state["looks"]["1"]["palette"] == "pal_krap", state["looks"].get("1")
    assert state["looks"]["0"] == _appearance.default_appearance(), \
        "an unclaimed seat should publish the default, not nothing"
    back = P.parse_match_state(P.make_match_state(state))
    assert back["looks"]["1"]["head"] == "head_goggles"
    assert back["looks"]["1"]["finish"]["os12"] == "os12_blued"
    # A peer that lies about an item the catalog does not have gets the default,
    # and the lie has to be caught before the state is published, not at draw.
    liar = {"t": P.T_JOIN_MATCH, "a": {"palette": "pal_not_for_sale",
                                       "head": "head_gold_crown"}}
    sim.add_player(2, "Liar", P.join_match_appearance(liar))
    published = sim.match_state()["looks"]["2"]
    assert published == _appearance.default_appearance(), \
        "a fabricated loadout was published as claimed: %r" % (published,)


def check_two_players_wear_what_they_bought():
    """A live host/client pair: a claimed loadout reaches the other sprite, and
    a finished round pays both sides from their own read of the same board.

    The checks above test the pieces. This one plays the match, because the
    thing a player actually does - join somebody, see their hat, win, get paid
    once - crosses four modules that can each be individually right and still
    fail together.
    """
    from ui.match_screen import MatchScreen
    from net import roomcode as _RC
    ps = _profile_store
    A = _appearance
    ps.save({"version": 1, "acaribucks": 0, "lifetime_earned": 0,
             "rounds_scored": 0, "owned": list(A.FREE_ITEM_IDS),
             "equipped": A.default_appearance(), "credited": []})
    host = MatchScreen()
    host.open_panel()
    host.players = 2
    host.player_name = "HOSTNAME"
    host.request_host(0)
    keys = pygame.key.get_pressed()
    idle = (500, 350, False)
    host.update(keys, idle, 1.0 / 60.0)
    assert host.mode == "hosting", "host did not start: " + host.status
    port = host.srv.getsockname()[1]

    # The joiner arrives wearing KRAP slate, goggles and a blued rifle. Both
    # sides read the same profile module in one process, so the claim is
    # injected on the client only - which is the shape of two different people
    # on two different machines.
    claim = A.make(palette="pal_krap", head="head_goggles",
                   finish={"os12": "os12_blued"})
    real = ps.equipped
    ps.equipped = lambda: claim
    client = MatchScreen()
    try:
        client.open_panel()
        client.player_name = "JOINER"
        client.request_join(_RC.encode("127.0.0.1", port))
        for _ in range(240):
            host.update(keys, idle, 1.0 / 60.0)
            client.update(keys, idle, 1.0 / 60.0)
            if (client.sess is not None and client.sess.local_id == 1
                    and client.mode == "playing" and client.sess.sample_world()):
                break
    finally:
        ps.equipped = real
    assert client.mode == "playing", "joiner never got in: " + client.status

    # The claim has to survive seating, publishing, and the repaint.
    assert host.sim.players[1]["look"]["head"] == "head_goggles", \
        "the claim did not reach the host's seat"
    host.update(keys, idle, 1.0 / 60.0)
    assert host.view._looks["1"]["palette"] == "pal_krap", \
        "the published state lost the loadout"
    peer = host.view._pose(1)
    assert peer._rk["uniform"] == A.PALETTES["pal_krap"]["roles"]["uniform"], \
        "the peer's sprite was never repainted"
    # And the host must not be painted in the joiner's kit.
    assert host.view._pose(0).look["palette"] == A.DEFAULT_PALETTE, \
        "the host inherited the peer's loadout"

    host._draw_waiting(config.screen)
    start = host._lobby_rects.get("start")
    assert start is not None, "waiting lobby had no start button"
    host.handle_event(pygame.event.Event(
        pygame.MOUSEBUTTONDOWN, {"button": 1, "pos": start.center}),
        start.center)
    for _ in range(600):
        host.update(keys, idle, 1.0 / 60.0)
        client.update(keys, idle, 1.0 / 60.0)
        if host.sim.tick > 60 and not host.waiting_for_player():
            break
    assert host.sim.tick > 60, "the match never went live"

    rules = host.sim.rules
    rules.kills[1] = rules.score_limit
    rules.kills[0] = 2
    rules.winner = 1
    host.sim.finished = True
    for _ in range(90):
        host.update(keys, idle, 1.0 / 60.0)
        client.update(keys, idle, 1.0 / 60.0)
        host.draw(config.screen)
        client.draw(config.screen)

    assert client._round_result()[0] is True, "client never saw the round end"
    assert host.sim.match_id, "host never minted a session token"
    assert client._match_state.get("match_id") == host.sim.match_id, \
        "the client could not see which match it was being paid for"
    # Each side derives its own number from the shared board. The host lost, so
    # it gets kill credit and second; the joiner took the round.
    assert host._last_payout == (14, 2, 1, False), \
        "host derived its own payout wrong: %r" % (host._last_payout,)
    assert client._last_payout == (82, 15, 0, True), \
        "client derived its own payout wrong: %r" % (client._last_payout,)
    assert ps.balance() == 96, \
        "expected one credit each, wallet holds %s" % ps.balance()
    logged = ps.load()["credited"]
    assert len(logged) == 2 and len(set(logged)) == 2, \
        "the two seats did not produce two distinct credit keys: %r" % (logged,)
    # Driving the frames again must not re-pay: the card is up for seconds and
    # the edge is the only thing between a round and a money printer.
    for _ in range(30):
        host.draw(config.screen)
        client.draw(config.screen)
    assert ps.balance() == 96, "a lingering round card paid out again"


def check_campaign_player_wears_the_loadout():
    """The campaign seam: a started mission exposes a dressable Player.

    acaristan.py/app.py cannot be imported from here - the module body runs the
    game loop - so this verifies the two halves the GAME state's hook relies on:
    a mission really does leave a live sprite on STATE.player, and that sprite
    accepts a loadout and changes appearance. If either half breaks, the arena
    keeps working while the single-player hero silently stays olive.
    """
    from core.state import STATE
    gc.start_mission()
    player = STATE.player
    assert player is not None, "start_mission left STATE.player empty"
    assert hasattr(player, "set_appearance"), "Player lost the appearance hook"
    assert player.look == _appearance.default_appearance(), \
        "a fresh campaign sprite should be the legacy look"
    before = player.look_key
    player.set_appearance(_appearance.make(palette="pal_rust",
                                           head="head_balaclava"))
    assert player.look["palette"] == "pal_rust"
    assert player.look_key != before, "look_key did not follow the repaint"
    assert player._rk["uniform"] == \
        _appearance.PALETTES["pal_rust"]["roles"]["uniform"]


def check_team_claims_survive_balance():
    """A side you chose must not be undone by the auto-balance.

    This is the whole point of the feature. Auto-balance on join is what made
    team selection impossible, so if rebalancing could still move a player who
    asked for a side, the feature would be a button that sometimes lies.
    """
    from missions import arena as AR
    rows = AR.ARENA_FOUNDRY
    rules = AR.Deathmatch(rows, 15, AR.MODE_TDM)
    for pid in range(6):
        rules.register(pid)
        rules.teams[pid] = rules.balance_teams()
    assert rules.team_counts() == {AR.TEAM_IPA: 3, AR.TEAM_KRAP: 3}
    # Two friends both want KRAP.
    assert rules.claim_team(0, AR.TEAM_KRAP) is True
    assert rules.claim_team(1, AR.TEAM_KRAP) is True
    rules.rebalance()
    assert rules.teams[0] == AR.TEAM_KRAP and rules.teams[1] == AR.TEAM_KRAP, \
        "rebalance moved players off a side they chose: %r" % (rules.teams,)
    # ...and the rest still even out around them.
    assert rules.team_counts() == {AR.TEAM_IPA: 3, AR.TEAM_KRAP: 3}, \
        "rebalance failed to even the unclaimed seats: %r" % (
            rules.team_counts(),)
    # Junk and free-for-all are both refused rather than silently accepted.
    ffa = AR.Deathmatch(rows, 15, AR.MODE_FFA)
    assert ffa.claim_team(0, AR.TEAM_KRAP) is False, "FFA should have no teams"
    assert rules.claim_team(0, 7) is False
    assert rules.claim_team(0, "KRAP") is False
    assert rules.claim_team(0, True) is False
    # Leaving clears the claim, so a returning friend is asked, not assumed.
    rules.release_team(0)
    assert 0 not in rules.claims


def check_team_pick_codec():
    """The preference packet round-trips, and junk never becomes a team."""
    from net import protocol as _P
    for team in (_P.TEAM_PICK_IPA, _P.TEAM_PICK_KRAP):
        msg = _P.make_team_pick(team)
        assert _P.parse_team_pick(msg) == team, msg
    assert _P.parse_team_pick(_P.make_team_pick(1)) == 1
    # Anything that is not a team pick must read as None, so a snapshot or a
    # chat line can never be mistaken for one.
    for junk in (None, {}, {"t": "in"}, {"t": _P.T_TEAM_PICK},
                 {"t": _P.T_TEAM_PICK, "team": 7},
                 {"t": _P.T_TEAM_PICK, "team": -1},
                 {"t": _P.T_TEAM_PICK, "team": "0"},
                 {"t": _P.T_TEAM_PICK, "team": True},
                 {"t": _P.T_TEAM_PICK, "team": None},
                 {"t": _P.T_TEAM_PICK, "team": 1.0}):
        assert _P.parse_team_pick(junk) is None, \
            "junk team pick accepted: %r" % (junk,)


def check_two_friends_pick_the_same_side():
    """Three players in a real TDM lobby: both joiners choose KRAP, and every
    screen ends up agreeing.

    The unit checks above could each pass while the feature still did nothing,
    because the path runs client -> socket -> host rules -> state packet ->
    every client's board. This drives all of it over loopback.
    """
    from ui.match_screen import MatchScreen
    from net import roomcode as _RC
    from missions import arena as AR
    _profile_store.save({
        "version": 1, "acaribucks": 0, "lifetime_earned": 0, "rounds_scored": 0,
        "owned": list(_appearance.FREE_ITEM_IDS),
        "equipped": _appearance.default_appearance(), "credited": []})
    keys = pygame.key.get_pressed()
    idle = (500, 350, False)
    host = MatchScreen()
    host.open_panel()
    host.players = 4
    host.mode_name = AR.MODE_TDM
    host.player_name = "HOST"
    host.request_host(0)
    host.update(keys, idle, 1.0 / 60.0)
    assert host.mode == "hosting", "TDM host did not start: " + host.status
    assert host.sim.rules.mode == AR.MODE_TDM
    port = host.srv.getsockname()[1]

    def pump(times=90):
        for _ in range(times):
            host.update(keys, idle, 1.0 / 60.0)
            for peer in clients:
                peer.update(keys, idle, 1.0 / 60.0)

    clients = []
    for name in ("ALICE", "BOB"):
        peer = MatchScreen()
        peer.open_panel()
        peer.player_name = name
        peer.request_join(_RC.encode("127.0.0.1", port))
        clients.append(peer)
    pump(240)
    for peer in clients:
        assert peer.mode == "playing" and peer.in_match_lobby(), \
            "%s never reached the lobby: %s" % (peer.player_name, peer.status)

    # The board is only worth building if it is clickable, and only the host
    # gets the override controls.
    host._draw_waiting(config.screen)
    assert "team_%d" % AR.TEAM_IPA in host._lobby_rects and \
        "team_%d" % AR.TEAM_KRAP in host._lobby_rects, \
        "TDM lobby drew no team targets: %r" % (sorted(host._lobby_rects),)
    joiner = clients[0]
    joiner._draw_waiting(config.screen)
    targets = sorted(str(k) for k in joiner._lobby_rects)
    assert "team_%d" % AR.TEAM_KRAP in targets, \
        "a joiner's lobby had no team targets: %r" % (targets,)
    assert not [k for k in targets if k.startswith(("swap_", "balance"))], \
        "a joiner was given the host's override controls: %r" % (targets,)

    # ALICE picks by clicking the KRAP column, the way a player does it. BOB's
    # pick goes through the same call the click handler makes.
    alice_target = joiner._lobby_rects["team_%d" % AR.TEAM_KRAP]
    joiner.handle_event(pygame.event.Event(
        pygame.MOUSEBUTTONDOWN, {"button": 1, "pos": alice_target.center}),
        alice_target.center)
    assert clients[1].request_team(AR.TEAM_KRAP) is True, \
        "BOB's pick was refused before it left"
    pump(60)

    teams = host.sim.rules.teams
    assert teams[1] == AR.TEAM_KRAP and teams[2] == AR.TEAM_KRAP, \
        "the host ignored the joiners' picks: %r" % (teams,)
    assert host.sim.players[1]["team"] == AR.TEAM_KRAP, \
        "the entity record kept the old side -- friendly fire would too"
    assert sorted(host.sim.rules.claims) == [1, 2]
    # And it comes back to everybody, including each other.
    for peer in clients:
        seen = peer._teams_table()
        assert seen == {0: teams[0], 1: AR.TEAM_KRAP, 2: AR.TEAM_KRAP}, \
            "%s sees %r" % (peer.player_name, seen)

    # The host can overrule, and the overrule propagates the same way.
    host._move_player_to(1, AR.TEAM_IPA)
    pump(60)
    assert host.sim.rules.teams[1] == AR.TEAM_IPA
    for peer in clients:
        assert peer._teams_table()[1] == AR.TEAM_IPA, \
            "%s never learned the host moved a player" % peer.player_name

    # A free-for-all must NOT offer team controls, and must refuse a pick even
    # if something constructs one anyway.
    solo = MatchScreen()
    solo.open_panel()
    solo.players = 2
    solo.mode_name = AR.MODE_FFA      # MatchScreen defaults to TDM
    solo.player_name = "FFAHOST"
    solo.request_host(0)
    solo.update(keys, idle, 1.0 / 60.0)
    assert solo.sim.rules.mode == AR.MODE_FFA, \
        "the free-for-all host built a %r match" % (solo.sim.rules.mode,)
    solo._draw_waiting(config.screen)
    assert not [k for k in solo._lobby_rects if str(k).startswith("team_")], \
        "a free-for-all lobby offered team buttons"
    assert solo.request_team(AR.TEAM_KRAP) is False, \
        "a free-for-all accepted a team pick"


def check_one_sided_lobby_cannot_start():
    """A team match with an empty side must not start, and must say why.

    Round victory is "reach the score limit", so if nobody is on a side that
    side can never be reached: the round can only die on the five-minute clock
    in a draw, with three players shooting at people the scoreboard insists are
    their teammates. Allowing two friends to stack together is the feature;
    allowing BOTH sides to end up empty-handed is a broken match.
    """
    from ui.match_screen import MatchScreen, _fit_to_font
    from net import roomcode as _RC
    from missions import arena as AR
    _profile_store.save({
        "version": 1, "acaribucks": 0, "lifetime_earned": 0, "rounds_scored": 0,
        "owned": list(_appearance.FREE_ITEM_IDS),
        "equipped": _appearance.default_appearance(), "credited": []})
    keys = pygame.key.get_pressed()
    idle = (500, 350, False)
    host = MatchScreen()
    host.open_panel()
    host.players = 4
    host.mode_name = AR.MODE_TDM
    host.player_name = "HOST"
    host.request_host(0)
    host.update(keys, idle, 1.0 / 60.0)
    port = host.srv.getsockname()[1]
    joiners = []
    for name in ("ALICE", "BOB"):
        peer = MatchScreen()
        peer.open_panel()
        peer.player_name = name
        peer.request_join(_RC.encode("127.0.0.1", port))
        joiners.append(peer)

    def pump(times=90):
        for _ in range(times):
            host.update(keys, idle, 1.0 / 60.0)
            for peer in joiners:
                peer.update(keys, idle, 1.0 / 60.0)

    pump(300)
    assert len(host.peers) == 2, "joiners did not reach the lobby"
    # Everyone piles onto KRAP.
    host._draw_waiting(config.screen)
    target = host._lobby_rects["team_%d" % AR.TEAM_KRAP]
    host.handle_event(pygame.event.Event(
        pygame.MOUSEBUTTONDOWN, {"button": 1, "pos": target.center}),
        target.center)
    for peer in joiners:
        peer.request_team(AR.TEAM_KRAP)
    pump(80)
    counts = host.sim.rules.team_counts()
    assert counts[AR.TEAM_IPA] == 0, \
        "expected an empty side to be reachable, got %r" % (counts,)

    reason = host._unstartable_reason()
    assert reason and "IPA" in reason, \
        "an empty side was not explained: %r" % (reason,)
    assert host._begin_countdown() is False, \
        "a one-sided team match was allowed to start"
    assert host.session_phase() == "lobby", \
        "the phase advanced anyway: %r" % (host.session_phase(),)
    # And the button itself refuses the click, not just the logic behind it.
    host._session_phase = "lobby"
    config.screen.fill((0, 0, 0))
    host.draw(config.screen)
    start_center = None
    for key, rect in host._lobby_rects.items():
        if key == "start":
            start_center = rect.center
    assert start_center is None, \
        "START MATCH stayed clickable with a side empty"
    # The reason has to FIT inside the button it is written on.
    font = host._font(16, True, True)
    label = _fit_to_font(font, reason, 304 - 18)
    assert font.size(label)[0] <= 304 - 18, \
        "%r overflows the START button at %dpx" % (label, font.size(label)[0])
    assert "..." not in label, \
        "the empty-side warning had to be truncated to fit: %r" % (label,)

    # Fixing it is one click, and a lopsided-but-playable split still starts.
    host._draw_waiting(config.screen)
    other = host._lobby_rects["team_%d" % AR.TEAM_IPA]
    host.handle_event(pygame.event.Event(
        pygame.MOUSEBUTTONDOWN, {"button": 1, "pos": other.center}), other.center)
    pump(60)
    counts = host.sim.rules.team_counts()
    assert min(counts.values()) >= 1, "moving the host did not fill the side"
    assert host._unstartable_reason() is None, \
        "a 1-vs-2 split was still blocked: %r" % (host._unstartable_reason(),)
    assert host._begin_countdown() is True, "a playable split would not start"


def check_lobby_owns_the_pointer_not_the_reticle():
    """The frozen lobby must show the menu arrow and hide the combat reticle,
    for the joiner exactly as much as for the host.

    Two bugs lived here at once. app.py decided "is this live play" with
    waiting_for_player(), which is hardcoded to mode == "hosting", so a joiner
    sitting in the same frozen lobby lost the arrow -- and because MULTIPLAYER
    is in CURSOR_ARROW_STATES the OS cursor is hidden too, leaving a joiner with
    NO pointer on a screen whose whole job is clicking a team. Meanwhile the
    arena drew its reticle from entity liveness alone, and the host seats and
    snapshots you before the sim runs, so an aiming crosshair floated over a
    MATCH LOBBY panel with nothing aimable in it.
    """
    from ui.match_screen import MatchScreen
    from net import roomcode as _RC
    keys = pygame.key.get_pressed()
    idle = (500, 350, False)
    host = MatchScreen()
    host.open_panel()
    host.players = 2
    host.mode_name = "TDM"
    host.player_name = "HOST"
    host.request_host(0)
    host.update(keys, idle, 1.0 / 60.0)
    peer = MatchScreen()
    peer.open_panel()
    peer.player_name = "GUEST"
    peer.request_join(_RC.encode("127.0.0.1", host.srv.getsockname()[1]))
    for _ in range(300):
        host.update(keys, idle, 1.0 / 60.0)
        peer.update(keys, idle, 1.0 / 60.0)
    assert peer.mode == "playing" and peer.in_match_lobby(), \
        "joiner never reached the lobby: %r" % (peer.status,)

    # Lobby: arrow for BOTH sides, reticle off for both.
    for label, ms in (("host", host), ("joiner", peer)):
        ms._push_hud_tables()
        assert ms.wants_menu_cursor() is True, \
            "%s lost the menu arrow in the lobby" % label
        assert getattr(ms.view, "aim_frozen", False) is True, \
            "%s would draw a combat reticle over the lobby" % label
    # The old host-only test, kept honest: a joiner is NOT the host, so any
    # cursor rule that asks who owns the room is the wrong question.
    assert peer.mode != "hosting" and not peer.waiting_for_player(), \
        "precondition changed: waiting_for_player() is no longer host-only"

    # Start the match. Both sides must flip to reticle-and-no-arrow once live.
    host._draw_waiting(config.screen)
    start = host._lobby_rects["start"]
    host.handle_event(pygame.event.Event(
        pygame.MOUSEBUTTONDOWN, {"button": 1, "pos": start.center}),
        start.center)
    for _ in range(420):
        host.update(keys, idle, 1.0 / 60.0)
        peer.update(keys, idle, 1.0 / 60.0)
    assert host.session_phase() == "playing" and \
        peer.session_phase() == "playing", \
        "match did not go live: %r / %r" % (host.session_phase(),
                                            peer.session_phase())
    for label, ms in (("host", host), ("joiner", peer)):
        ms._push_hud_tables()
        assert ms.wants_menu_cursor() is False, \
            "%s still showed the menu arrow during play" % label
        assert getattr(ms.view, "aim_frozen", None) is False, \
            "%s lost the reticle in a live round" % label

    # Pause brings the arrow back for both, so RESUME / LEAVE stay clickable.
    for ms in (host, peer):
        ms.handle_event(pygame.event.Event(pygame.KEYDOWN,
                                           {"key": pygame.K_ESCAPE}),
                        (500, 350))
    for _ in range(4):
        host.update(keys, idle, 1.0 / 60.0)
        peer.update(keys, idle, 1.0 / 60.0)
        host.draw(config.screen)
        peer.draw(config.screen)
    assert host.paused and peer.paused, "ESC did not pause both sides"
    for label, ms in (("host", host), ("joiner", peer)):
        assert ms.wants_menu_cursor() is True, \
            "%s' pause menu had no arrow to click" % label


def check_fallen_body_wears_the_loadout():
    """A corpse must be painted from the dead player's own resolved palette.

    The point of routing colours through core.appearance rather than reading the
    config constants is that eight players can die wearing eight different kits.
    A body that ignored them would be a cosmetic bug at the exact moment a player
    is looking hardest at their own character.
    """
    from entities.fallen import FallenBody
    default_roles = _appearance.resolve(None)
    base = pygame.Surface((132, 132), pygame.SRCALPHA)
    b = FallenBody(66, 66, -0.7, default_roles, "head_kevlar", "os12", seed=9)
    b.t = b.fall_frames * 4
    b.draw(base, 0, 0)
    plain = pygame.image.tostring(base, "RGBA")

    variants = {
        "palette": _appearance.make(palette="pal_winter"),
        "goggles": _appearance.make(head="head_goggles"),
        "beret": _appearance.make(head="head_beret"),
        "heavy": _appearance.make(head="head_heavy_helmet"),
        "balaclava": _appearance.make(head="head_balaclava"),
        "cap": _appearance.make(head="head_peaked_cap"),
        "gold_pistol": _appearance.make(finish={"pistol": "pistol_goldleaf"}),
    }
    for label, app in variants.items():
        roles = _appearance.resolve(app)
        s = pygame.Surface((132, 132), pygame.SRCALPHA)
        body = FallenBody(66, 66, -0.7, roles, app["head"],
                          "pistol" if label == "gold_pistol" else "os12",
                          seed=9)
        body.t = body.fall_frames * 4
        body.draw(s, 0, 0)
        got = pygame.image.tostring(s, "RGBA")
        assert got != plain, "%s rendered an identical corpse to the default" % label

    # Different seeds sprawl differently; the same seed must not.
    def shot(seed):
        s = pygame.Surface((132, 132), pygame.SRCALPHA)
        body = FallenBody(66, 66, 0.0, default_roles, "head_kevlar", "os12",
                          seed=seed)
        body.t = body.fall_frames * 4
        body.draw(s, 0, 0)
        return pygame.image.tostring(s, "RGBA")
    assert shot(3) == shot(3), "the same seed produced two different poses"
    assert shot(3) != shot(4), "every corpse is lying in the identical pose"

    # Topple must actually progress and then settle.
    body = FallenBody(66, 66, 0.0, default_roles, "head_kevlar", "os12", seed=1)
    assert body.progress == 0.0, "a fresh body should start standing"
    body.advance(body.fall_frames)
    assert abs(body.progress - 1.0) < 1e-6, "body did not finish toppling"
    body.advance(500)
    assert body.progress == 1.0, "progress overshot its ceiling"

    # Junk palettes must not take the frame down.
    for junk in (None, {}, {"uniform": "not-a-colour"}, {"rigs": 5}):
        s = pygame.Surface((132, 132), pygame.SRCALPHA)
        weird = FallenBody(66, 66, 0.3, junk or {}, "head_kevlar", "os12", seed=2)
        weird.t = 30
        weird.draw(s, 0, 0)


def check_every_corpse_shows_for_everyone():
    """A body must appear on all four machines, for every death.

    Three separate bugs lived here and each one hid a different corpse:

    - the host rebuilt its own rules packet every frame but never ran
      _sync_respawn on it, so it only ever counted down its OWN deaths and
      drew no remote bodies at all;
    - a client's local death is played from EV_KILL before the snapshot that
      flags PS_DEAD arrives, so the machine where the kill happened was the
      one place the victim's own corpse could be missed;
    - keying death off the respawn countdown alone loses any death with no
      wait attached, which is what the published ``dead`` set is for.
    """
    from net import protocol as _P
    from missions import arena as AR
    host, peers, keys, idle, pump = _live_tdm_match()
    sim = host.sim
    screens = [("host", host)] + [("peer%d" % p.sess.local_id, p)
                                  for p in peers]

    def park(pid, x, y):
        """Stand slot `pid` at (x, y) on the host AND let it reach every client.

        Clients draw from an interpolation buffer 100ms behind the host's 20Hz
        snapshots, so a position set only on the sim takes several frames to
        surface on four separate screens -- and a body placed off-screen is
        skipped by the 40px view cull, correctly, for a reason unrelated to
        corpses. This waits for the number to actually arrive everywhere.
        """
        st = sim.players[pid]
        st["x"], st["y"] = float(x), float(y)
        for _ in range(60):
            pump(1)
            if all(_coord(ms, pid) == (round(float(x)), round(float(y)))
                   for _, ms in screens):
                return
        raise AssertionError("slot %d never reached every client at %r: %r"
                             % (pid, (x, y),
                                {n: _coord(ms, pid) for n, ms in screens}))

    def _coord(ms, pid):
        world = ms.sess.sample_world() or {}
        if isinstance(world, (list, tuple)):
            world = dict((e[0], e) for e in world)
        ent = world.get(pid)
        return (round(ent[2]), round(ent[3])) if ent else None

    # Bring every camera inside the map first: slots 1 and 3 spawn at opposite
    # corners of a yard larger than a viewport, so their own machines would
    # clamp and never see anything.
    for pid in sorted(sim.players):
        park(pid, 200 + pid * 45, 200 + (pid % 2) * 40)

    def kill(pid):
        """Kill `pid`, leave it dead with a held respawn wait, in mid-view."""
        sim.rules.respawn.clear()
        for other in list(sim.players):
            sim.rules.spawned_at.pop(other, None)
        sim.damage(pid, 999, killer_id=0)
        pump(2)
        st = sim.players[pid]
        if not st["dead"]:
            # Revived on the next tick, as any death with no wait attached is.
            # Re-kill it and hold the timer open so the state outlives the pump.
            sim.rules.respawn[pid] = sim.tick + AR.RESPAWN_TICKS
            sim.damage(pid, 999, killer_id=0)
        park(pid, 300 + pid * 40, 260)

    def bodies():
        out = {}
        for name, ms in screens:
            ms.draw(config.screen)
            out[name] = sorted(ms.view._corpses)
        return out

    def seen_by_all(pid):
        """Draw until every machine has the body, or give up."""
        for _ in range(60):
            pump(1)
            got = bodies()
            if all(pid in seen for seen in got.values()):
                return got
        raise AssertionError("slot %d never drew a body everywhere: %r"
                             % (pid, got))

    # A REMOTE slot dying: the machine running the sim used to draw bodies only
    # for its own death, because it rebuilt the rules packet every frame without
    # ever syncing the countdown out of it.
    kill(3)
    seen_by_all(3)

    # OUR OWN death, on the machine of whoever died.
    victim = peers[0].sess.local_id
    kill(victim)
    seen_by_all(victim)
    assert len(host.view._corpses) >= 2, \
        "host still draws no corpses at all: %r" % (sorted(host.view._corpses),)

    # Respawn clears the body: a live player must not stay flat on the deck.
    # Let the sim revive everyone through its own rule rather than flipping
    # st["dead"] by hand -- an out-of-band flag would leave the countdown and
    # the dead set disagreeing, which is a state the game cannot produce.
    sim.rules.respawn.clear()
    for other in list(sim.players):
        sim.rules.spawned_at.pop(other, None)
    for _ in range(40):
        pump(1)
        if not any(st["dead"] for st in sim.players.values()):
            break
    else:
        raise AssertionError("the sim never revived anybody: %r"
                             % [p for p, s in sim.players.items() if s["dead"]])
    # The host's own EV_KILL seeded a full-length local countdown for the slot
    # it runs, and that clock is deliberately allowed to outlast the packet that
    # reported the death (see _sync_respawn). It expires on its own; waiting it
    # out is what a real player does between dying and coming back.
    for _ in range(int(AR.RESPAWN_SECONDS * 60) + 40):
        pump(1)
        got = bodies()
        if all(seen == [] for seen in got.values()):
            break
    else:
        raise AssertionError("a body outlived its respawn: %r" % (got,))

    # The published dead set is what carries a death with NO wait attached --
    # unreachable through play, since arena.py revives any slot whose timer
    # already expired on the very next tick. Exercised on a CLIENT, because
    # that is the only side that reads it: the host answers _down_ids from its
    # own sim and has no reason to consult a table it wrote itself.
    alice = peers[0]
    nobody = alice.sess.local_id + 50
    alice._sync_dead({"dead": [nobody]})
    assert nobody in alice._down_ids(), \
        "a waitless death did not reach the board: %r" % (alice._down_ids(),)
    alice._sync_dead({"dead": []})
    assert nobody not in alice._down_ids(), \
        "a respawned player stayed a corpse: %r" % (alice._down_ids(),)

    # The wire table survives junk rather than raising inside the render loop.
    for junk in (None, "x", 5, {"a": 1}, [True], [1, 2, 3]):
        want = [] if junk != [1, 2, 3] else [1, 2, 3]
        d = _P.parse_match_state(_P.make_match_state(
            {"mode": "tdm", "phase": "live", "round": 1, "clock": 5,
             "dead": junk})).get("dead")
        assert d == want, "dead table round-tripped %r to %r" % (junk, d)


def _live_tdm_match():
    """Host + three joiners, match started, with real kills on the board."""
    from ui.match_screen import MatchScreen
    from net import roomcode as _RC
    keys = pygame.key.get_pressed()
    idle = (500, 350, False)
    host = MatchScreen()
    host.open_panel()
    host.players = 4
    host.mode_name = "TDM"
    host.player_name = "HOST"
    host.request_host(0)
    host.update(keys, idle, 1.0 / 60.0)
    port = host.srv.getsockname()[1]
    peers = []
    for name in ("ALICE", "BOB", "CARL"):
        peer = MatchScreen()
        peer.open_panel()
        peer.player_name = name
        peer.request_join(_RC.encode("127.0.0.1", port))
        peers.append(peer)

    def pump(times):
        for _ in range(times):
            host.update(keys, idle, 1.0 / 60.0)
            for peer in peers:
                peer.update(keys, idle, 1.0 / 60.0)

    pump(400)
    assert len(host.peers) == 3, "three joiners did not reach the lobby"
    host._draw_waiting(config.screen)
    start = host._lobby_rects.get("start")
    assert start is not None, "no START button in a four-player TDM lobby"
    host.handle_event(pygame.event.Event(
        pygame.MOUSEBUTTONDOWN, {"button": 1, "pos": start.center}),
        start.center)
    pump(420)
    assert host.session_phase() == "playing", "match never went live"
    sim = host.sim
    for victim, killer in ((1, 0), (2, 0), (3, 1)):
        sim.rules.respawn.clear()
        for pid in list(sim.players):
            sim.rules.spawned_at.pop(pid, None)
        sim.damage(victim, 999, killer_id=killer)
    pump(40)
    return host, peers, keys, idle, pump


def check_tab_leaderboard():
    """Hold Tab for the standings; release closes it; scores reach the client.

    Also guards a bug this feature exposed: the host published the rules packet
    once at GO and never again during a round, so every joiner's scoreboard,
    clock and team totals were frozen at zero for the entire match. The pause
    table and HUD score strip had the same stale data -- the overlay just made
    it impossible to miss.
    """
    from net import protocol as _P
    host, peers, keys, idle, pump = _live_tdm_match()
    alice = peers[0]
    board = host.sim.scoreboard()
    assert any(row[1] for row in board), \
        "no kills landed, so the test would prove nothing: %r" % (board,)

    def press(ms):
        ms.handle_event(pygame.event.Event(pygame.KEYDOWN,
                                           {"key": pygame.K_TAB}), (500, 350))

    def release(ms):
        ms.handle_event(pygame.event.Event(pygame.KEYUP,
                                           {"key": pygame.K_TAB}), (500, 350))

    # Live: opens, draws, closes.
    press(alice)
    assert alice._scoreboard is True, "Tab did not open the board"
    alice.draw(config.screen)
    release(alice)
    assert alice._scoreboard is False, "releasing Tab did not close the board"

    # The client must see the SAME numbers as the host, not zeros.
    seen = (alice._match_state or {}).get("scoreboard") or ()
    assert seen == [tuple(r) for r in board] or list(seen) == list(map(list, board)), \
        "client scoreboard is stale: host=%r client=%r" % (board, seen)
    host_rows = [(d, n, k) for d, n, k, _m, _t in host.standings()]
    client_rows = [(d, n, k) for d, n, k, _m, _t in alice.standings()]
    assert host_rows == client_rows, \
        "host and client disagree on rank: %r vs %r" % (host_rows, client_rows)
    # And the local player is marked as theirs, not the host's.
    mine = [line[3] for line in alice.standings()]
    assert sum(1 for m in mine if m) == 1, \
        "exactly one row should be 'me' on a client: %r" % (mine,)

    # Works while paused too -- opening the menu then wanting the standings is
    # the same urge, and making the player un-pause to look is a bad joke.
    alice.paused = True
    press(alice)
    alice.draw(config.screen)
    release(alice)
    alice.paused = False

    # Tab in the LOBBY must not cover the room code with an empty table.
    fresh = _fresh_lobby_pair()
    if fresh:
        fh, fc = fresh
        press(fc)
        assert fc._scoreboard is True, "Tab flag did not set in the lobby"
        fc.draw(config.screen)      # must not raise, must not draw the board
        release(fc)

    # The entry panel keeps its own Tab meaning: toggling between the two text
    # fields. Stealing it there would make the address box unusable by keyboard.
    panel = __import__("ui.match_screen", fromlist=["MatchScreen"]).MatchScreen()
    panel.open_panel()
    before = panel.selected_field
    handled = panel.handle_event(pygame.event.Event(
        pygame.KEYDOWN, {"key": pygame.K_TAB}), (500, 350))
    assert panel.mode == "panel", "entry panel unexpectedly left panel mode"
    assert handled is True, "entry panel stopped consuming Tab"
    assert panel.selected_field != before, \
        "Tab no longer moves between the entry panel's fields"


def _fresh_lobby_pair():
    """A host plus one joiner sitting in the frozen lobby. Returns None on
    socket trouble so the leaderboard check does not fail on environment."""
    from ui.match_screen import MatchScreen
    from net import roomcode as _RC
    keys = pygame.key.get_pressed()
    idle = (500, 350, False)
    try:
        host = MatchScreen()
        host.open_panel()
        host.players = 2
        host.mode_name = "FFA"
        host.player_name = "LOBHOST"
        host.request_host(0)
        host.update(keys, idle, 1.0 / 60.0)
        peer = MatchScreen()
        peer.open_panel()
        peer.player_name = "LOBPEER"
        peer.request_join(_RC.encode("127.0.0.1", host.srv.getsockname()[1]))
        for _ in range(300):
            host.update(keys, idle, 1.0 / 60.0)
            peer.update(keys, idle, 1.0 / 60.0)
        if not peer.in_match_lobby():
            return None
        return host, peer
    except Exception:
        return None


def check_mission4_boot_and_walk():
    """M4 Slice 0 boot proof: start headless, walk ticks, draw a frame.

    Also enforces the map-seam contract the M2/M3 procedural style skips
    (MapBuilder.validate() is unused there): MISSION4_MAP's border must be
    solid on all four sides and the player must spawn on a floor tile.
    """
    from missions import m4
    from core.state import STATE

    m4.start_m4()
    assert STATE.active_mission == "MISSION4", "active_mission not MISSION4"
    assert STATE.mission4_stage == m4.STAGE_AFTERMATH, "stage not aftermath"

    grid = m4.MISSION4_MAP
    h = len(grid)
    w = len(grid[0])
    assert w == h == 40, "street map must be 40x40"
    for x in range(w):
        assert grid[0][x] in m4.M4_SOLID_CHARS and grid[h - 1][x] in m4.M4_SOLID_CHARS
    for y in range(h):
        assert grid[y][0] in m4.M4_SOLID_CHARS and grid[y][w - 1] in m4.M4_SOLID_CHARS

    pcx, pcy = STATE.player.rect.center
    pcol, prow = pcx // m4.TILE, pcy // m4.TILE
    assert grid[prow][pcol] not in m4.M4_SOLID_CHARS, "player spawned inside geometry"

    assert m4._objective.startswith("Regroup with Vasile"), \
        "opening objective missing: " + repr(m4._objective)

    # W2 content proof: the named curfew-zone table resolves to world rects
    # and the boulevard drives position lookups; the street spawns both IPA
    # types (guards hold checkpoints, marksmen cover the long sightlines).
    assert len(m4.M4_ZONE_DEFS) == 3 and len(m4.M4_ZONE_WORLD_RECTS) == 3, \
        "W2 zone table not fully populated"
    assert m4.zone_at(m4._vasile_cache_pos()) == "boulevard", \
        "zone_at failed to place the Vasile cache on the boulevard"
    from engine.world import Label as _Label  # lazy: M4 self-check (D4: type lives in the Label component)
    _types = [_gw.ensure(e, _Label).kind for e in STATE.enemies]
    assert _types.count("guard") >= 1 and _types.count("marksman") == 2, \
        "W2 IPA patrol mix missing: " + repr(_types)

    keys = EmptyKeys()
    cam = m4.game_update(keys)
    for _ in range(30):
        cam = m4.game_update(keys)
    m4.game_draw(*cam)
    m4.handle_interact()

    # W2 story-beat ladder: advance the chaos clock to a timed beat and
    # confirm the radio line is queued (dedup mark set on the owner module).
    STATE.m4_chaos_timer = 239
    if getattr(STATE, "mission4_stage", None) == m4.STAGE_AFTERMATH:
        cam = m4.game_update(keys)
        assert "beat_loyalists" in m4._radio_marks, \
            "timed story beat did not fire at chaos-frame 240"


def check_mission4_stage_transitions():
    """Headless E2E chain: street -> station -> meet -> hold -> ending.

    The W3 station ladder: the Vasile cache beat arms the door objective, the
    door tile hands the world over to the station interior, walking to Maru
    opens the typewriter liaison dialogue (a choice beat records the tone on
    STATE.m4_tone), completing it moves to the jammer stage, planting the
    jammer gates the STAGE_COMMIT hold, and M4_HOLD_SECONDS of ticking raises
    request_mission4_ending exactly once (idempotent guard).
    """
    from missions import m4
    from missions.m4.meta import (
        M4_HOLD_SECONDS, STATION_START_TILE, LIAISON_TILE, JAMMER_TILE)
    from core.state import STATE

    keys = EmptyKeys()
    m4.start_m4()

    # 1) Vasile cache: the drop is a real pickup (E). The street stage can no
    #    longer be skipped - the station door refuses entry until the cache
    #    is in hand, so prove the gate first, then take the drop.
    dx, dy = m4._street_door_pos()
    STATE.player.rect.center = (dx, dy)
    cam = m4.game_update(keys)
    assert STATE.mission4_stage == m4.STAGE_AFTERMATH, \
        "station door entered without the comms cache (stage skip)"
    cx, cy = m4._vasile_cache_pos()
    STATE.player.rect.center = (cx, cy)
    for _ in range(5):
        cam = m4.game_update(keys)
    m4.handle_interact()
    assert getattr(STATE, "m4_cache_taken", False), \
        "cache interact did not pick up the drop"
    assert "Reach the radio station door" in m4._objective, \
        "cache beat did not arm the door objective: " + repr(m4._objective)

    # 2) Station door -> interior world swap + checkpoint flag.
    dx, dy = m4._street_door_pos()
    STATE.player.rect.center = (dx, dy)
    cam = m4.game_update(keys)
    assert STATE.mission4_stage == m4.STAGE_KRAP_STATUS, "door did not enter station"
    assert STATE.mission4_station_checkpoint_reached, "station checkpoint flag not set"
    assert m4.MISSION4_MAP is m4.MISSION4_STATION_MAP, "map not swapped to station"
    sx, sy = m4._tile_world(*STATION_START_TILE)
    assert abs(STATE.player.rect.centerx - sx) < 80 \
        and abs(STATE.player.rect.centery - sy) < 80, \
        "player not spawned in the station entry hall"

    # 3) Liaison meet: walk to Maru -> dialogue opens (movement locks), then
    #    drive the typewriter + choice beats to completion -> STAGE_MARU.
    lx, ly = m4._tile_world(*LIAISON_TILE)
    STATE.player.rect.center = (lx, ly)
    cam = m4.game_update(keys)  # proximity triggers _start_liaison_dialogue
    assert STATE.m4_dialogue_active, "liaison proximity did not open the dialogue"
    _enter = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN)
    _frames = 0
    for _ in range(800):
        if not STATE.m4_dialogue_active:
            break
        m4.handle_dialogue_event(_enter)   # snap the typewriter to full
        cam = m4.game_update(keys)         # tick the reveal
        m4.handle_dialogue_event(_enter)   # advance / resolve the choice
        cam = m4.game_update(keys)
        # Render the meet every few frames so the dialogue panel (typing +
        # the choice beat) and the friendly-NPC poses are drawn headlessly.
        _frames += 1
        if _frames % 3 == 0:
            m4.game_draw(*cam)
    assert STATE.m4_dialogue_done and not STATE.m4_dialogue_active, \
        "liaison dialogue did not complete"
    assert STATE.mission4_stage == m4.STAGE_MARU, \
        "dialogue did not hand off to the jammer stage"
    assert getattr(STATE, "m4_tone", []) and STATE.m4_tone[0] in (0, 1), \
        "the tone choice was not recorded on STATE.m4_tone"

    # 3b) Jammer install (E) is the gate to the siege hold.
    jx, jy = m4._tile_world(*JAMMER_TILE)
    STATE.player.rect.center = (jx, jy)
    m4.handle_interact()
    assert STATE.m4_jammer_installed, "jammer interact did not install the jammer"
    assert STATE.mission4_stage == m4.STAGE_COMMIT, \
        "jammer install did not gate the siege hold"
    assert STATE.m4_siege_active and STATE.mission4_tower_checkpoint_reached

    # 4) The hold clock completes the mission exactly once.
    hold_frames = int(M4_HOLD_SECONDS * 60) + 120
    for _ in range(hold_frames):
        if STATE.request_mission4_ending:
            break
        cam = m4.game_update(keys)
    assert STATE.request_mission4_ending, "hold clock never requested the ending"
    assert STATE.mission4_stage == m4.STAGE_DONE
    held = STATE.m4_hold_timer
    m4._complete_m4()  # idempotent guard must be a no-op
    assert STATE.m4_hold_timer == held, "_complete_m4 is not idempotent"


def check_mission4_checkpoint_routes():
    """Death-restart ladder: deepest checkpoint first (tower -> station)."""
    from missions import m4
    from core.state import STATE

    m4.start_mission4_station_checkpoint()
    assert STATE.mission4_stage == m4.STAGE_KRAP_STATUS
    assert m4.MISSION4_MAP is m4.MISSION4_STATION_MAP
    cam = m4.game_update(EmptyKeys())
    m4.game_draw(*cam)

    m4.start_mission4_tower_checkpoint()
    assert STATE.mission4_stage == m4.STAGE_COMMIT
    assert STATE.m4_siege_active and STATE.m4_hold_timer == 0

    # Restart routing reads the checkpoint flags: tower wins over station.
    STATE.mission4_station_checkpoint_reached = True
    STATE.mission4_tower_checkpoint_reached = False
    from core import game_core
    game_core.restart_current_mission()
    assert STATE.mission4_stage == m4.STAGE_KRAP_STATUS, \
        "restart did not route to the station checkpoint"
    STATE.mission4_tower_checkpoint_reached = True
    game_core.restart_current_mission()
    assert STATE.mission4_stage == m4.STAGE_COMMIT, \
        "restart did not route to the tower checkpoint"


def check_mission4_hold_clock():
    """W4 siege hold: the wave director, the diegetic arrest ladder and the
    timer-driven completion.

    Two parts:
      * Telegraph wiring, deterministic (not left to the wave RNG): a beam
        queues on STATE.m4_lasers and the director decays it; game_draw
        exercises the beam renderer with a live beam present.
      * The full hold: fireteams commit up to M4_MAX_CONCURRENT from the
        insertion doors, the arrest-beat ladder fires every mark on schedule,
        spawns break off after the relief frame, and the clock (never kills)
        raises request_mission4_ending -> STAGE_DONE. The player parked here
        may die to en-route fire; that must NOT stop the timer (m3 exfil-door
        lesson), which is exactly what this asserts.
    """
    import random as _rnd
    _rnd.seed(4469)
    from missions import m4
    from missions.m4.meta import M4_HOLD_SECONDS
    from missions.m4.components import M4Guard as _M4Guard  # lazy: M4 self-check
    from core.state import STATE

    keys = EmptyKeys()
    m4.start_mission4_tower_checkpoint()
    assert STATE.mission4_stage == m4.STAGE_COMMIT
    STATE.m4_hold_timer = 0
    m4._siege_reset()

    # 1) Telegraph + decay wiring (deterministic). Suppress spawns for this
    #    micro-run so only the decay path is exercised.
    STATE.m4_siege_spawn_timer = 10 ** 7
    m4._add_sniper_laser((64, 64), from_pos=(8, 8), life=3)
    assert len(STATE.m4_lasers) == 1, "laser telegraph did not queue"
    for _ in range(4):
        m4._run_siege_director()
    assert len(STATE.m4_lasers) == 0, "laser telegraph did not decay"
    m4._add_sniper_laser((128, 128), from_pos=(8, 8), life=20)
    cam = m4.game_update(keys)
    m4.game_draw(*cam)  # exercises _draw_m4_lasers with a live beam present

    # 2) The full hold, spawns active.
    m4._siege_reset()
    STATE.m4_hold_timer = 0
    want = {"arrest_open", "arrest_order", "arrest_confusion",
            "arrest_standdown", "arrest_retreat"}
    wave_seen = 0
    relief_seen = False
    for _ in range(int(M4_HOLD_SECONDS * 60) + 10):
        cam = m4.game_update(keys)
        if STATE.m4_siege_wave > wave_seen:
            wave_seen = STATE.m4_siege_wave
        if STATE.m4_hold_timer >= m4.M4_SIEGE_RELIEF_FRAMES:
            relief_seen = True
        if STATE.m4_hold_timer < m4.M4_SIEGE_RELIEF_FRAMES:
            alive = sum(1 for e in STATE.enemies
                        if _gw.ensure(e, _M4Guard).loyalist and e.hp > 0)
            assert alive <= m4.M4_MAX_CONCURRENT, "siege exceeded concurrency cap"
        if STATE.request_mission4_ending:
            break
    assert wave_seen >= 1, "director never committed a fireteam"
    assert relief_seen, "hold never reached the siege relief frame"
    assert want <= m4._radio_marks, \
        "arrest beat ladder incomplete: " + repr(want - set(m4._radio_marks))
    assert STATE.request_mission4_ending, "hold clock did not request the ending"
    assert STATE.mission4_stage == m4.STAGE_DONE


def check_mission4_layout():
    """Layout-rework proof: the curfew street + station interior are built on a
    solid-block grammar with legible, connected routes (the old maps were a
    hollow walkable field with 'walls' you could walk through). Asserts:
      * the street is genuinely blocky (a solid fraction, not a bare field),
      * safehouse spawn -> station door is walkable-connected (flood fill),
      * no street objective key sits on a solid char,
      * station entry -> transmitter hall is connected through the carved interior.
    """
    from missions.m4 import maps as M
    from missions.m4.meta import (
        PLAYER_START_TILE, STATION_DOOR_TILE, VASILE_CACHE_TILE,
        STATION_START_TILE, TRANSMITTER_TILE, JAMMER_TILE, LIAISON_TILE,
        M4_SOLID_CHARS)

    solid = set(M4_SOLID_CHARS)

    def _walk(g, c, r):
        return g[r][c] not in solid

    def _flood(g, start, goal):
        gw, gh = len(g[0]), len(g)
        if not (_walk(g, *start) and _walk(g, *goal)):
            return False
        seen = {start}
        stack = [start]
        while stack:
            c, r = stack.pop()
            if (c, r) == goal:
                return True
            for dc, dr in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                nc, nr = c + dc, r + dr
                if 0 <= nc < gw and 0 <= nr < gh and (nc, nr) not in seen \
                        and _walk(g, nc, nr):
                    seen.add((nc, nr))
                    stack.append((nc, nr))
        return False

    street = M.MISSION4_STREET_MAP
    sw, sh = len(street[0]), len(street)
    n_solid = sum(1 for r in range(sh) for c in range(sw)
                  if street[r][c] in solid)
    frac = n_solid / float(sw * sh)
    assert 0.45 < frac < 0.95, \
        "street solid fraction %.2f is not blocky-but-carved" % frac
    assert _flood(street, PLAYER_START_TILE, STATION_DOOR_TILE), \
        "safehouse spawn is not walkable-connected to the station door"
    for name, t in (("PLAYER_START", PLAYER_START_TILE),
                    ("VASILE_CACHE", VASILE_CACHE_TILE),
                    ("STATION_DOOR", STATION_DOOR_TILE)):
        assert street[t[1]][t[0]] not in solid, \
            "street objective %s sits on a solid char" % name

    station = M.MISSION4_STATION_MAP
    for name, t in (("STATION_START", STATION_START_TILE),
                    ("TRANSMITTER", TRANSMITTER_TILE),
                    ("JAMMER", JAMMER_TILE),
                    ("LIAISON", LIAISON_TILE)):
        assert station[t[1]][t[0]] not in solid, \
            "station objective %s sits on a solid char" % name
    assert _flood(station, STATION_START_TILE, TRANSMITTER_TILE), \
        "station entry is not connected to the transmitter hall"


def check_mission4_ending_shots_render():
    """Every W5 finale/intro shot has a renderer and paints a real frame.

    Guards the same dead-half trap the M3 fail cutscene shipped with: a shot
    list landing before its scene art makes draw_cutscene_scene fall through to
    a lit-black frame. Each scene is painted across its animation window and
    must show real tonal spread (std-dev), not a flat wash.
    """
    import statistics as _st
    import cutscenes
    from missions.m4.meta import mission4_ending_shots, mission4_intro_shots

    # The facade/game_core must expose the lists app.py asks for.
    assert getattr(gc, "mission4_ending_shots", None) is mission4_ending_shots, \
        "gc.mission4_ending_shots does not resolve to the M4 ending shots"
    assert getattr(gc, "mission4_intro_shots", None) is mission4_intro_shots, \
        "gc.mission4_intro_shots does not resolve to the M4 intro shots"

    m4_scenes = {"m4_city_curfew", "m4_arrest_screen",
                 "m4_maru_silhouette", "m4_roof_dawn"}
    seen = set()
    for shot in list(mission4_ending_shots) + list(mission4_intro_shots):
        scene = shot["scene"]
        if scene == "title_card":
            continue  # engine paints title cards as a flat fill by design
        for t in (0, 1500, 4000, 9000):
            cutscenes.draw_cutscene_scene(config.screen, shot, t)
            px = pygame.surfarray.array3d(config.screen)
            lum = [(r + g + b) // 3 for r, g, b in px.reshape(-1, 3).tolist()]
            sd = _st.pstdev(lum)
            assert sd > 3.0, "{} frame t={} is a flat wash (std-dev={:.1f})".format(
                scene, t, sd)
        if scene in m4_scenes:
            seen.add(scene)
    assert seen == m4_scenes, \
        "not all bespoke M4 scenes rendered; missing: " + repr(m4_scenes - seen)


def check_mission4_campaign_chain():
    """The campaign chain M4 depends on, as a data + routing contract.

    _SlotSelectState._activate_slot (in app.py) is not headless-runnable (it
    fires gsm transitions + menu globals), so - exactly as check_save_mission3_
    record treats M3 - we assert the two things that branch keys on:
      * the save record: a MISSION4 completion writes last_completed_mission =
        "MISSION_4" (the FULL CAMPAIGN COMPLETE trigger) with the full
        prerequisite flag set, and gc.start_mission4 boots MISSION4 (the
        last=="MISSION_3" resume target);
      * the in-progress resume ladder: the progress=="m4" branch's three
        targets (street / station / tower checkpoint) all resolve and land the
        expected stage.
    """
    from missions import m4
    from core.state import STATE

    # Save record contract (mirrors the MISSION_3 regression guard).
    rec = _save_system.mission_complete_record("MISSION4", "10:00", stats={})
    assert rec is not None, "MISSION4 must map to a record"
    assert rec["mission_id"] == "MISSION_4"
    assert "Aftermath" in rec["label"]
    for flag in ("mission1_complete", "mission2_complete",
                 "mission3_complete", "mission4_complete"):
        assert rec["flags"].get(flag), "MISSION4 record missing " + flag

    _reset_save_store()
    _save_system.select_slot(3)
    _save_system.start_new_campaign(3)
    assert _save_system.save_mission_complete_record("MISSION4", "10:00", stats={})
    assert _save_system.get_slot(3)["last_completed_mission"] == "MISSION_4", \
        "MISSION_4 not recorded (FULL CAMPAIGN COMPLETE would not fire)"

    # M3-complete save -> the resume branch calls gc.start_mission4; prove the
    # target boots MISSION4.
    gc.start_mission4()
    assert STATE.active_mission == "MISSION4", "MISSION_3 resume target did not boot M4"
    assert STATE.mission4_stage == m4.STAGE_AFTERMATH

    # In-progress ("m4") ladder: each checkpoint resume lands its stage.
    gc.start_mission4_station_checkpoint()
    assert STATE.mission4_stage == m4.STAGE_KRAP_STATUS
    gc.start_mission4_tower_checkpoint()
    assert STATE.mission4_stage == m4.STAGE_COMMIT
    _reset_save_store()


def main():
    assert config.screen is not None, "config.screen was not initialized"

    ok = True

    print("\n=== Import checks ===")
    for module_name in SPLIT_MODULES:
        ok = run_import_check(module_name) and ok

    print("\n=== UI draw checks ===")
    ui_checks = [
        ("draw_menu", check_menu_draw),
        ("draw_settings", check_settings_draw),
        ("draw_server_browser_servers", check_server_browser_servers_draw),
        ("draw_server_browser_connections", check_server_browser_connections_draw),
        ("draw_notebook_inspection", check_notebook_inspection_draw),
        ("draw_safe_keypad", check_safe_keypad_draw),
        ("draw_desk_note", check_desk_note_draw),
        ("draw_cutscene", check_cutscene_draw),
        ("draw_pause_menu", check_pause_draw),
        ("draw_death_screen", check_death_draw),
        ("draw_match_panel", check_match_panel_draw),
    ]

    for name, fn in ui_checks:
        ok = run_check(name, fn) and ok

    print("\n=== Multiplayer checks ===")
    mp_checks = [
        ("multiplayer_opens_on_server_browser",
         check_multiplayer_opens_on_server_browser),
        ("host_is_taught_how_to_host", check_host_is_taught_how_to_host),
        ("remote_input_is_applied", check_remote_input_is_applied),
        ("lobby_relay_is_not_a_player", check_lobby_relay_is_not_a_player),
        ("local_shot_kicks_camera", check_local_shot_kicks_camera),
        ("match_screen_roster", check_match_screen_roster),
        ("client_join_completes", check_client_join_completes),
        ("host_left_ends_session", check_host_left_ends_session),
        ("weapon_switching_in_match", check_weapon_switching_in_match),
        ("switch_survives_batched_inputs", check_switch_survives_batched_inputs),
        ("arena_sprite_rig_and_anim", check_arena_sprite_rig_and_anim),
        ("arena_os12_is_the_story_rifle", check_arena_os12_is_the_story_rifle),
        ("arena_hud_legibility", check_arena_hud_legibility),
        ("match_intro_transition", check_match_intro_transition),
        ("join_loopback_fallback", check_join_loopback_fallback),
        ("client_interpolation_smooth", check_client_interpolation_smooth),
        ("arena_weapons_and_pickups", check_arena_weapons_and_pickups),
        ("arena_teams_and_rounds", check_arena_teams_and_rounds),
        ("client_prediction_is_authoritative",
         check_client_prediction_is_authoritative),
        ("hit_marker_decays", check_hit_marker_decays),
        ("match_identity_and_comms", check_match_identity_and_comms),
        ("team_claims_survive_balance", check_team_claims_survive_balance),
        ("team_pick_codec", check_team_pick_codec),
        ("two_friends_pick_the_same_side",
         check_two_friends_pick_the_same_side),
        ("one_sided_lobby_cannot_start",
         check_one_sided_lobby_cannot_start),
        ("lobby_owns_the_pointer_not_the_reticle",
         check_lobby_owns_the_pointer_not_the_reticle),
        ("fallen_body_wears_the_loadout",
         check_fallen_body_wears_the_loadout),
        ("every_corpse_shows_for_everyone",
         check_every_corpse_shows_for_everyone),
        ("tab_leaderboard", check_tab_leaderboard),
    ]

    for name, fn in mp_checks:
        ok = run_check(name, fn) and ok

    print("\n=== Mission checks ===")
    mission_checks = [
        ("game_core_facade_state", check_game_core_facade_state),
        ("start_mission", check_start_mission),
        ("game_update", check_game_update),
        ("game_draw", check_game_draw),
    ]

    for name, fn in mission_checks:
        ok = run_check(name, fn) and ok

    print("\n=== Save system checks ===")
    save_checks = [
        ("save_roundtrip_flags_merged", check_save_roundtrip_flags_merged),
        ("save_mission3_record", check_save_mission3_record),
        ("save_corrupt_recovery", check_save_corrupt_recovery),
        ("save_current_slot_persist", check_save_current_slot_persist),
        ("save_progress_marker", check_save_progress_marker),
        ("save_atomic_no_tmp", check_save_atomic_no_tmp),
        ("settings_preserve_omitted_keys", check_settings_preserve_omitted_keys),
    ]

    for name, fn in save_checks:
        ok = run_check(name, fn) and ok

    print("\n=== Cosmetics and economy checks ===")
    cosmetic_checks = [
        ("appearance_default_is_legacy", check_appearance_default_is_legacy),
        ("avatar_render_parity", check_avatar_render_parity),
        ("appearance_junk_rejected", check_appearance_junk_rejected),
        ("profile_wallet", check_profile_wallet),
        ("round_credit_is_once_per_round", check_round_credit_is_once_per_round),
        ("payout_is_result_only", check_payout_is_result_only),
        ("arena_look_reaches_the_sprite", check_arena_look_reaches_the_sprite),
        ("cosmetic_loadout_survives_a_match",
         check_cosmetic_loadout_survives_a_match),
        ("outfitter_screen", check_outfitter_screen),
        ("outfitter_lives_behind_multiplayer",
         check_outfitter_lives_behind_multiplayer),
        ("two_players_wear_what_they_bought",
         check_two_players_wear_what_they_bought),
        ("campaign_player_wears_the_loadout",
         check_campaign_player_wears_the_loadout),
    ]

    for name, fn in cosmetic_checks:
        ok = run_check(name, fn) and ok

    print("\n=== Walking sim checks ===")
    walking_checks = [
        ("walking_sim_start_update_draw", check_walking_sim_start_update_draw),
    ]

    for name, fn in walking_checks:
        ok = run_check(name, fn) and ok

    print("\n=== Hidden branch checks ===")
    hidden_checks = [
        ("molotov_update_path", check_molotov_update_path),
        ("mission2_molotov_update_path", check_mission2_molotov_update_path),
        ("mission_draw_story_characters", check_mission_draw_story_characters),
        ("walking_dialogue_draw", check_walking_dialogue_draw),
    ]

    for name, fn in hidden_checks:
        ok = run_check(name, fn) and ok

    print("\n=== Mission 3 chair-break cutscene checks ===")
    chair_break_checks = [
        ("mission3_chair_break_cutscene", check_mission3_chair_break_cutscene),
        ("mission3_chair_break_shots_render", check_mission3_chair_break_shots_render),
    ]

    for name, fn in chair_break_checks:
        ok = run_check(name, fn) and ok

    for name, fn in hidden_checks:
        ok = run_check(name, fn) and ok

    print("\n=== Mission 3 broadcast wing checks ===")
    broadcast_checks = [
        ("mission3_broadcast_world_build", check_mission3_broadcast_world_build),
        ("mission3_broadcast_wave_spawn", check_mission3_broadcast_wave_spawn),
        ("mission3_broadcast_upload", check_mission3_broadcast_upload),
        ("mission3_broadcast_timeout_retry", check_mission3_broadcast_timeout_retry),
        ("mission3_broadcast_fail_shots_render", check_mission3_broadcast_fail_shots_render),
        ("mission3_broadcast_draw", check_mission3_broadcast_draw),
    ]

    for name, fn in broadcast_checks:
        ok = run_check(name, fn) and ok

    print("\n=== Mission 3 checkpoint routing checks ===")
    for name, fn in [("mission3_death_checkpoints", check_mission3_death_checkpoints)]:
        ok = run_check(name, fn) and ok

    print("\n=== Mission 4 checks ===")
    mission4_checks = [
        ("mission4_boot_and_walk", check_mission4_boot_and_walk),
        ("mission4_layout", check_mission4_layout),
        ("mission4_stage_transitions", check_mission4_stage_transitions),
        ("mission4_checkpoint_routes", check_mission4_checkpoint_routes),
        ("mission4_hold_clock", check_mission4_hold_clock),
        ("mission4_ending_shots_render", check_mission4_ending_shots_render),
        ("mission4_campaign_chain", check_mission4_campaign_chain),
    ]

    for name, fn in mission4_checks:
        ok = run_check(name, fn) and ok

    print("\n=== Multiplayer relay checks ===")
    for name, fn in [
        ("mp_relay_roundtrip", check_mp_relay_roundtrip),
        ("mp_relay_ui_integration", check_mp_relay_ui_integration),
        ("mp_host_and_portmap", check_mp_host_and_portmap),
    ]:
        ok = run_check(name, fn) and ok

    print("\n=== Font glyph coverage checks ===")
    for name, fn in [("font_glyph_coverage", check_font_glyph_coverage)]:
        ok = run_check(name, fn) and ok

    pygame.quit()

    if ok:
        print("\nSMOKE TEST: OK")
        raise SystemExit(0)

    print("\nSMOKE TEST: FAILED")
    raise SystemExit(1)


if __name__ == "__main__":
    main()
