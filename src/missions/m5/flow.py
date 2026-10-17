"""Mission 5 - part module. See __init__.py for the package facade.

Mission start / stage ladder / checkpoints / completion for Mission 5.
Ported from missions.m4.flow idioms (start double-reset, checkpoint
wrappers, typewriter dialogue, idempotent completion) - not imported.

Ladder: HQ (walking sim: squadmate barks, Vasile's office dialogue) ->
QUARTER (reach the print-works door) -> PRINTWORKS (find Maru,
typewriter dialogue) -> RAID (survive M5_RAID_SECONDS, insertion squads;
then the basement stair) -> TUNNEL (escort Maru, pursuit squads) ->
Maru at the river gate -> _complete_m5. Maru dying = mission failed.
A fresh run opens at STAGE_HQ (W6); checkpoints skip it.
"""

import math
from engine.core import LEGACY_RNG as _rng_legacy  # RPE6 R6: named 'legacy' rng stream

import pygame

from core.config import (SCENE_BOT, SCENE_TOP, WIDTH)
from core.state import STATE
from game import save_adapter as _save_adapter  # RPE6 P9 (game-layer adapter; no cycle)
from core import config as _config
from ui.hud import MiniMap
from core.outfits import OUTFIT_GUARD
import game.dialogues as _dialogues  # RPE6 P7: conversation data access
from engine.core import now_ms as _now_ms  # RPE6 B-001 timebase

audio = _config.audio

from missions.m5 import maps as _m5_maps  # live MISSION5_MAP/_objective owner
from missions.m5 import decor as _m5_decor
from missions.m5 import quarter as _m5_quarter
from missions.m5.meta import (
    MISSION5_ID, MISSION5_KEY, MISSION5_TITLE,
    M5_RAID_SECONDS, M5_PURSUIT_INTERVAL, M5_MARU_MAX_HP,
    STAGE_HQ, STAGE_QUARTER, STAGE_PRINTWORKS, STAGE_RAID, STAGE_TUNNEL,
    STAGE_DONE, VASILE_OFFICE_LINES, HQ_OFFICE_RADIUS,
    C_SYSTEM, C_VASILE, C_MARU, C_GUARD, C_UCILEV, BIRIBEL_SPEAKER,
)
from missions.m5.world import (
    _build_hq_world, _update_hq_barks, _vasile_desk_pos,
    _build_quarter_world, _build_print_world, _build_tunnel_world,
    _near, _radio, _set_objective, _sfx, _tile_world,
    _printworks_door_pos, _maru_office_pos, _stair_pos, _river_gate_pos,
    _update_maru, _spawn_raid_squad, _spawn_pursuit_squad,
    _squad_alive_count,
)

M5_FAIL_HOLD_FRAMES = 150      # hold on Maru's body before the death screen
M5_RAID_SQUAD_GAP = (180, 300)  # frames between raid insertions
M5_GATE_RADIUS = 80             # Maru within this of the gate = done


def _snap_camera_safe():
    from core.camera import snap_gameplay
    if STATE.player is None:
        return
    w, h = _m5_maps._live_map_dims()
    # Snap WITH the aim lookahead, so the first follow frame after a stage
    # swap doesn't lurch 48 px toward the aim direction.
    snap_gameplay(STATE.player.rect.center, w, h, aim_angle=STATE.player.angle, who="m5_snap")


def _bind_map(grid):
    # Old-stage directions must not spill into the next playable space.
    from core.interactions import clear_radio_queue
    clear_radio_queue()
    _m5_maps.MISSION5_MAP = grid
    STATE.show_minimap = True
    STATE.minimap = MiniMap(_m5_maps.MISSION5_MAP, palette="m4")


# ────────────────────────────────────────────
# Typewriter dialogue (m4 cadence, ported)
# ────────────────────────────────────────────
_TYPE_SPEED = 4


def _type_interval():
    """RPE6 P9: frames per typed character (text_speed setting; 4 at 1.0x)."""
    try:
        from core.user_settings import SETTINGS
        return max(1, int(round(_TYPE_SPEED / max(0.1, SETTINGS.text_speed_mul))))
    except Exception:
        return _TYPE_SPEED
_TYPE_PAUSE_FULL = 25
_TYPE_PAUSE_SOFT = 12

_M5_MARU_BEATS = [
    {"speaker": "MARU", "color": C_MARU,
     "text": "Biribel. Vasile sent you. Of course he did."},
    {"speaker": "BIRIBEL", "color": BIRIBEL_SPEAKER,
     "text": "He wants you brought in. Breathing, he says."},
    {"speaker": "MARU", "color": C_MARU,
     "text": "Breathing in a Guard cell. Balaceanu was breathing too, last week."},
    {"speaker": "BIRIBEL", "color": BIRIBEL_SPEAKER,
     "text": "Then we don't go to the cell. Is there another way out?"},
    {"speaker": "MARU", "color": C_MARU,
     "text": "Basement. The old tunnel runs to the river. If we live long enough to reach it."},
    {"speaker": "SYSTEM", "color": C_GUARD,
     "text": "[ Engines outside. Boots on the loading bay. The Guard is here. ]"},
]

# Single-owner dialogue dict (mutated in place, never rebound).
# "kind" picks the completion hook: "maru" -> raid, "vasile" -> quarter.
_m5_dlg = {"beats": [], "index": 0, "char_idx": 0, "timer": 0,
           "post_hold": 0, "active": False, "kind": ""}

_SPEAKER_COLORS = {"VASILE": C_VASILE, "BIRIBEL": BIRIBEL_SPEAKER,
                   "MARU": C_MARU}


def _vasile_beats():
    """VASILE_OFFICE_LINES (meta, shared with the smoke test) as beats."""
    return [{"speaker": who, "color": _SPEAKER_COLORS.get(who, C_SYSTEM),
             "text": text} for who, text in VASILE_OFFICE_LINES]


def _dlg_reset():
    _m5_dlg.update(beats=[], index=0, char_idx=0, timer=0, post_hold=0,
                   active=False, kind="")


def _current_beat():
    b, i = _m5_dlg["beats"], _m5_dlg["index"]
    return b[i] if 0 <= i < len(b) else None


def _line_fully_typed():
    beat = _current_beat()
    return beat is None or _m5_dlg["char_idx"] >= len(beat["text"])


def _start_maru_dialogue():
    if getattr(STATE, "m5_dialogue_done", False) or _m5_dlg["active"]:
        return
    _dlg_reset()
    _m5_dlg["beats"] = list(_dialogues.beats(
        "m5.maru", _M5_MARU_BEATS,
        {"MARU": C_MARU, "BIRIBEL": BIRIBEL_SPEAKER, "SYSTEM": C_GUARD}))
    _m5_dlg["kind"] = "maru"
    _m5_dlg["active"] = True
    STATE.m5_dialogue_active = True
    STATE.m5_maru_found = True
    _sfx("radio_static", 0.3)
    _request_cut("maru")


def _start_vasile_dialogue():
    """Phase 2: Vasile's office (in-engine). Ends -> Lower Quarter."""
    if getattr(STATE, "m5_office_done", False) or _m5_dlg["active"]:
        return
    _dlg_reset()
    _m5_dlg["beats"] = _vasile_beats()
    _m5_dlg["kind"] = "vasile"
    _m5_dlg["active"] = True
    STATE.m5_dialogue_active = True
    STATE.mission_phase = "m5_office"
    _sfx("door_open", 0.3)
    _request_cut("vasile")


# Round 2: mid-mission cutscenes (meta.M5_MID_CUTSCENES), each played once per run.
_m5_seen_cuts = set()


def _request_cut(key):
    if key in _m5_seen_cuts:
        return
    _m5_seen_cuts.add(key)
    STATE.request_m5_cutscene = key


def on_m5_cutscene_done(key):
    """app.py, after a mid-mission cutscene: the conversation was shown in the
    cutscene, so close the matching in-game dialogue straight away."""
    STATE.request_m5_cutscene = None
    if key == "descent":
        _enter_tunnel()
        return
    if not _m5_dlg["active"]:
        return
    if key == "vasile" and _m5_dlg["kind"] == "vasile":
        _finish_vasile_dialogue()
    elif key == "maru" and _m5_dlg["kind"] == "maru":
        _finish_maru_dialogue()


def _update_dialogue():
    _m5_dlg["timer"] += 1
    beat = _current_beat()
    if beat is None:
        return
    if _m5_dlg["timer"] == 1 and beat["speaker"] != "SYSTEM":
        try:
            from audio import voice
            voice.play_line(beat["speaker"], beat["text"])
        except Exception:
            pass
    full = beat["text"]
    if _m5_dlg["char_idx"] < len(full):
        if _m5_dlg["post_hold"] > 0:
            _m5_dlg["post_hold"] -= 1
        elif _m5_dlg["timer"] % _type_interval() == 0:
            ch = full[_m5_dlg["char_idx"]]
            _m5_dlg["char_idx"] += 1
            if ch in ".,;:!?" or _m5_dlg["char_idx"] % 3 == 0:
                _sfx("type_tick", 0.10)
            if ch in ".!?":
                _m5_dlg["post_hold"] = _TYPE_PAUSE_FULL
            elif ch in ",;:":
                _m5_dlg["post_hold"] = _TYPE_PAUSE_SOFT


def _advance_beat():
    _m5_dlg.update(index=_m5_dlg["index"] + 1, char_idx=0, timer=0,
                   post_hold=0)
    if _m5_dlg["index"] >= len(_m5_dlg["beats"]):
        if _m5_dlg["kind"] == "vasile":
            _finish_vasile_dialogue()
        else:
            _finish_maru_dialogue()


def _dlg_press(key):
    """Enter/Space/E: snap the typewriter to full, then advance."""
    if not _m5_dlg["active"]:
        return
    beat = _current_beat()
    if beat is None:
        return
    if key in (pygame.K_RETURN, pygame.K_SPACE, pygame.K_KP_ENTER, pygame.K_e):
        if not _line_fully_typed():
            _m5_dlg["char_idx"] = len(beat["text"])
        else:
            _advance_beat()


def handle_dialogue_event(event):
    if event.type == pygame.KEYDOWN:
        _dlg_press(event.key)


def _finish_maru_dialogue():
    _m5_dlg["active"] = False
    STATE.m5_dialogue_active = False
    STATE.m5_dialogue_done = True
    _begin_raid()


def _finish_vasile_dialogue():
    _m5_dlg["active"] = False
    STATE.m5_dialogue_active = False
    STATE.m5_office_done = True
    _enter_quarter()


# ─────────────────────────────────────────────
# Stage entries
# ─────────────────────────────────────────────
def _enter_hq():
    """Phase 2: Guard HQ walking sim (fresh-run opening). Disarmed."""
    _bind_map(_m5_maps.MISSION5_HQ_MAP)
    STATE.mission5_stage = STAGE_HQ
    STATE.mission_phase = "m5_hq"
    STATE.player_disarmed = True
    _build_hq_world()
    _m5_decor.build_decor(STAGE_HQ)
    if STATE.player is not None:
        STATE.player.angle = 0.0
    _snap_camera_safe()
    _set_objective("Report to Vasile - the Commander's office, end of the corridor.")
    _radio("DESK SERGEANT: Biribel. Commander wants you. Upstairs end - "
           "and mind the new armbands.",
           color=C_SYSTEM, duration=380, mark="hq_enter")


def _enter_quarter():
    """HQ office done -> Lower Quarter streets (checkpoint). Rearmed."""
    _bind_map(_m5_maps.MISSION5_QUARTER_MAP)
    STATE.mission5_stage = STAGE_QUARTER
    STATE.mission_phase = "m5_quarter"
    STATE.player_disarmed = False
    _build_quarter_world()
    _m5_decor.build_decor(STAGE_QUARTER)
    _m5_quarter.init()
    _snap_camera_safe()
    STATE.mission5_quarter_checkpoint_reached = True
    _set_objective("Reach the MAG print works - east end of the avenue. Before the Guard does.")
    _radio("VASILE: Lower Quarter's under Guard checkpoints - our old KRAP lads in "
           "the President's black. You're one of them now. They won't stop you. Probably.",
           color=C_VASILE, duration=420, mark="start_vasile")


def _enter_printworks():
    """Quarter door -> print works interior (checkpoint)."""
    _bind_map(_m5_maps.MISSION5_PRINT_MAP)
    STATE.mission5_stage = STAGE_PRINTWORKS
    STATE.mission_phase = "m5_printworks"
    _build_print_world()
    if STATE.player is not None:
        STATE.player.hp = STATE.player.max_hp
        STATE.player.angle = -math.pi / 2
    _snap_camera_safe()
    STATE.mission5_printworks_checkpoint_reached = True
    STATE.m5_maru_hp = STATE.m5_maru["hp"] if STATE.m5_maru else M5_MARU_MAX_HP
    _set_objective("Find Maru - the back office, north-east of the press hall.")
    _radio("VASILE: You're inside. Bring them in, Biribel. Quietly.",
           color=C_VASILE, duration=360, mark="pw_enter")


def _begin_raid():
    STATE.mission5_stage = STAGE_RAID
    STATE.mission_phase = "m5_raid"
    STATE.m5_raid_active = True
    STATE.m5_raid_timer = 0
    STATE.m5_squad_timer = 60
    m = getattr(STATE, "m5_maru", None)
    if m:
        m["following"] = True
    _set_objective("Survive the raid - keep Maru alive. Hold until the stair is clear.")
    _radio("GUARD: Presidential Guard! Nobody leaves the building!",
           color=C_GUARD, duration=360, mark="raid_open")
    _sfx("door_break", 0.5)


def _open_stair():
    STATE.m5_raid_active = False
    _set_objective("Get Maru down the basement stair - south-east corridor.")
    _radio("MARU: They're regrouping - now! The stair, south-east!",
           color=C_MARU, duration=380, mark="raid_over")


def _enter_tunnel():
    """Basement stair -> tunnel (checkpoint). Maru follows from the landing."""
    _bind_map(_m5_maps.MISSION5_TUNNEL_MAP)
    STATE.mission5_stage = STAGE_TUNNEL
    STATE.mission_phase = "m5_tunnel"
    STATE.m5_raid_active = False
    STATE.m5_maru_hp = M5_MARU_MAX_HP
    _build_tunnel_world()
    if STATE.player is not None:
        STATE.player.hp = STATE.player.max_hp
        STATE.player.angle = 0.0
    _snap_camera_safe()
    STATE.mission5_tunnel_checkpoint_reached = True
    STATE.m5_squad_timer = M5_PURSUIT_INTERVAL // 2
    _set_objective("Escort Maru to the river gate - east. Don't outrun them.")
    _radio("MARU: My arm's useless. Go slow - I'm right behind you.",
           color=C_MARU, duration=380, mark="tunnel_enter")


# ─────────────────────────────────────────────
# Mission start / checkpoints
# ─────────────────────────────────────────────
def start_m5(preserve_timer=False):
    """Begin Mission 5 gameplay at the Guard HQ walk (STAGE_HQ, phase 2)."""
    STATE.reset()
    STATE.active_mission = MISSION5_KEY
    STATE.active_mission_id = MISSION5_ID
    STATE.active_mission_title = MISSION5_TITLE
    STATE.active_mission_operation = "THE CAPITAL - EMERGENCY RULE"
    STATE.active_mission_outcome = "Parliament dissolved  ·  KRAP folded into the Guard  ·  Maru is on the list"
    STATE.active_mission_quote_attr = "Retardovici, on every channel:"
    STATE.active_mission_quote = '"The Presidential Guard will finish the work the Vostral began."'

    STATE.request_mission5_ending = False
    STATE.request_death_screen = False
    STATE.player_dead = False
    STATE.mission5_stage = STAGE_HQ
    STATE.mission_phase = "m5_hq"
    STATE.m5_office_done = False
    STATE.m5_guard_kills = 0
    STATE.m5_maru_found = False
    STATE.m5_dialogue_active = False
    STATE.m5_dialogue_done = False
    STATE.m5_raid_active = False
    STATE.request_m5_cutscene = None
    STATE.m5_convoy_late = False
    STATE.m5_civ_saved = False
    _m5_seen_cuts.clear()
    _m5_decor.reset_run()
    STATE.m5_raid_timer = 0
    STATE.m5_maru_hp = M5_MARU_MAX_HP
    STATE.m5_maru_dead = False
    STATE.m5_fail_timer = 0
    STATE.mission5_quarter_checkpoint_reached = False
    STATE.mission5_printworks_checkpoint_reached = False
    STATE.mission5_tunnel_checkpoint_reached = False
    STATE.m5_marks = set()
    # Biribel is in the President's black for the whole mission: the intro's
    # m5x_change beat always plays before this, and every checkpoint start
    # (hq/quarter/printworks/tunnel) routes through here, so a skipped intro
    # or a checkpoint load can't bring the KRAP kit back. STATE.reset() puts
    # it back to "krap" for every other mission (core.outfits reads it only
    # while MISSION5 is active anyway).
    STATE.m5_outfit = OUTFIT_GUARD

    STATE.rain_drops = [
        (_rng_legacy.randint(0, WIDTH), _rng_legacy.randint(SCENE_TOP, SCENE_BOT),
         _rng_legacy.randint(10, 20))
        for _ in range(200)
    ]
    STATE.mission_start_time = (
        STATE.mission_start_time if (preserve_timer and STATE.mission_start_time)
        else _now_ms())
    STATE.mission_end_time = 0
    STATE.hostiles_killed = 0
    STATE.shots_fired = 0
    STATE.shots_hit = 0
    STATE.k9_unlocked = True
    STATE.current_weapon = "k9_smg"
    STATE.player_disarmed = False

    try:
        from core.save_system import set_slot_progress
        set_slot_progress("m5")
    except Exception:
        pass

    _m5_maps._radio_marks = set()
    _m5_maps._last_keys = None
    _dlg_reset()

    _enter_hq()
    return STATE.player


def start_mission5_hq_checkpoint(preserve_timer=False):
    """Guard HQ walk (the true opening). Same as a fresh start_m5."""
    player = start_m5(preserve_timer=preserve_timer)
    _save_adapter.capture_m5_checkpoint("hq")   # RPE6 P9: snapshot alongside the legacy save
    return player


def start_mission5_quarter_checkpoint(preserve_timer=False):
    """Lower Quarter with the HQ/office already played."""
    start_m5(preserve_timer=preserve_timer)
    STATE.m5_office_done = True
    _enter_quarter()
    _save_adapter.capture_m5_checkpoint("quarter")   # RPE6 P9
    return STATE.player


def start_mission5_printworks_checkpoint(preserve_timer=False):
    start_mission5_quarter_checkpoint(preserve_timer=preserve_timer)
    _enter_printworks()
    _save_adapter.capture_m5_checkpoint("printworks")   # RPE6 P9
    return STATE.player


def start_mission5_tunnel_checkpoint(preserve_timer=False):
    start_mission5_printworks_checkpoint(preserve_timer=preserve_timer)
    STATE.m5_maru_found = True
    STATE.m5_dialogue_done = True
    _enter_tunnel()
    _save_adapter.capture_m5_checkpoint("tunnel")   # RPE6 P9
    return STATE.player


# ─────────────────────────────────────────────
# Failure (Maru dies)
# ─────────────────────────────────────────────
def _update_maru_fail():
    """Returns True while the Maru-death fail owns the frame."""
    if not getattr(STATE, "m5_maru_dead", False):
        return False
    if getattr(STATE, "m5_fail_timer", 0) == 0:
        _set_objective("MISSION FAILED - Maru is dead.")
        _radio("VASILE: ...Biribel? Tell me that wasn't Maru.",
               color=C_VASILE, duration=400, mark="maru_dead")
        _sfx("bullet_impact_enemy", 0.5)
        STATE.mission_phase = "m5_failed"
    STATE.m5_fail_timer = getattr(STATE, "m5_fail_timer", 0) + 1
    if STATE.m5_fail_timer >= M5_FAIL_HOLD_FRAMES:
        STATE.request_death_screen = True
    return True


# ─────────────────────────────────────────────
# Stage ladder
# ─────────────────────────────────────────────
def _update_stage(keys=None):
    if getattr(STATE, "request_m5_cutscene", None):
        return
    if _update_maru_fail():
        return
    if getattr(STATE, "m5_dialogue_active", False):
        _update_dialogue()
        return

    stage = getattr(STATE, "mission5_stage", STAGE_QUARTER)

    if stage == STAGE_HQ:
        _update_hq_barks()
        if (not getattr(STATE, "m5_office_done", False)
                and _near(_vasile_desk_pos(), radius=HQ_OFFICE_RADIUS)):
            _start_vasile_dialogue()
        return

    if stage == STAGE_QUARTER:
        _m5_quarter.update()
        if getattr(STATE, "request_m5_cutscene", None):
            return  # do not overwrite the checkpoint cinematic with arrival
        if _near(_printworks_door_pos(), radius=70):
            _m5_quarter.on_exit()
            _enter_printworks()
            _request_cut("arrival")
        return

    if stage == STAGE_PRINTWORKS:
        if not getattr(STATE, "m5_dialogue_done", False):
            if _near(_maru_office_pos(), radius=95):
                _start_maru_dialogue()
        return

    if stage == STAGE_RAID:
        _update_maru()
        if STATE.m5_raid_active:
            STATE.m5_raid_timer += 1
            STATE.m5_squad_timer -= 1
            if STATE.m5_squad_timer <= 0:
                _spawn_raid_squad()
                STATE.m5_squad_timer = _rng_legacy.randint(*M5_RAID_SQUAD_GAP)
            # Timer-driven, never kill-gated (M3 exfil-door lesson).
            if STATE.m5_raid_timer >= int(M5_RAID_SECONDS * 60):
                _open_stair()
            return
        m = STATE.m5_maru
        if _near(_stair_pos(), radius=70) and m and math.hypot(
                m["x"] - _stair_pos()[0], m["y"] - _stair_pos()[1]) <= 200:
            _request_cut("descent")
        elif _near(_stair_pos(), radius=70):
            _radio("BIRIBEL: Not without Maru.", color=BIRIBEL_SPEAKER,
                   duration=240, mark="stair_wait")
        return

    if stage == STAGE_TUNNEL:
        _update_maru()
        STATE.m5_squad_timer -= 1
        if STATE.m5_squad_timer <= 0:
            _spawn_pursuit_squad()
            STATE.m5_squad_timer = M5_PURSUIT_INTERVAL
        m = STATE.m5_maru
        gx, gy = _river_gate_pos()
        if m and math.hypot(m["x"] - gx, m["y"] - gy) <= M5_GATE_RADIUS:
            _complete_m5()
        elif _near((gx, gy), radius=M5_GATE_RADIUS):
            _radio("BIRIBEL: Gate's here. Come on, Maru.",
                   color=BIRIBEL_SPEAKER, duration=240, mark="gate_wait")
        return
    return


def _complete_m5():
    """Latch success once; app.py routes to completion while the finale is cut."""
    if (getattr(STATE, "mission5_stage", None) == STAGE_DONE
            or getattr(STATE, "request_mission5_ending", False)):
        return
    STATE.mission5_stage = STAGE_DONE
    STATE.mission_phase = "m5_done"
    STATE.mission_end_time = _now_ms()
    # Preserve the existing handoff flag and mission report/save contract.
    STATE.request_mission5_ending = True


def inspect_active():
    """True while a first-person [E] look shot is on screen."""
    return _m5_decor._fpv.active()


def handle_inspect_event(event):
    """Any key (ESC included) or click closes the look shot."""
    if event.type in (pygame.KEYDOWN, pygame.MOUSEBUTTONDOWN):
        _m5_decor._fpv.skip()


def handle_interact():
    """E-key: advance dialogue; otherwise nothing (doors are proximity)."""
    if getattr(STATE, "m5_dialogue_active", False):
        _dlg_press(pygame.K_e)
        return
    if _m5_decor.inspect():
        return
    if (getattr(STATE, "mission5_stage", None) == STAGE_HQ
            and not getattr(STATE, "m5_office_done", False)
            and _near(_vasile_desk_pos(), radius=HQ_OFFICE_RADIUS)):
        _start_vasile_dialogue()
        return
    if (getattr(STATE, "mission5_stage", None) == STAGE_PRINTWORKS
            and not getattr(STATE, "m5_dialogue_done", False)
            and _near(_maru_office_pos(), radius=95)):
        _start_maru_dialogue()
