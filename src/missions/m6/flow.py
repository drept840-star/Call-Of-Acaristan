"""Mission 6 - stage ladder, checkpoints and the ending handoff.

Ladder: customs -> no-man's-land -> rail yard -> (3D boxcar film) -> the
interactive train -> the ending film.  The Guard terminal file and Vasile's
call are told by the ending film; they are not separate top-down stages.

The boxcar conversation is a mid-mission cutscene (``M6_MID_CUTSCENES``):
interacting with Volkov sets ``STATE.request_m6_cutscene`` and app.py
plays it, then calls ``on_m6_cutscene_done("boxcar")`` which starts the
TrainScene.  When the train ends the mission requests the ending film.
"""
from core.state import STATE
from engine.core import now_ms as _now_ms

from . import maps as _maps
from . import decor as _decor
from . import world as _world
from .meta import (
    MISSION6_ID, MISSION6_KEY, MISSION6_TITLE,
    STAGE_CUSTOMS, STAGE_NOMAN, STAGE_RAIL, STAGE_BOXCAR, STAGE_TRAIN,
    STAGE_ANCHORS, STAGE_OBJECTIVES,
    GATE_RADIUS, BOXCAR_RADIUS,
)

C_SYSTEM = (120, 190, 160)
C_BIRIBEL = (212, 186, 140)
C_VASILE = (212, 178, 120)
C_MARU = (146, 196, 206)
C_GUARD = (206, 120, 96)

_SPEAKER_COLORS = {"SYSTEM": C_SYSTEM, "BIRIBEL": C_BIRIBEL,
                   "VASILE": C_VASILE, "MARU": C_MARU, "GUARD": C_GUARD,
                   "VOLKOV": (206, 176, 138)}

_STAGE_RADIO = {
    STAGE_NOMAN: ("MARU", "Floodlights sweep east to west. Move when the yard goes dark."),
    STAGE_RAIL: ("VASILE", "Guard traffic puts Volkov in the rail yard. Find him first."),
}


def _speaker_colour(who):
    return _SPEAKER_COLORS.get(who, C_SYSTEM)


# ─────────────────────────────────────────────
# Camera / map binding
# ─────────────────────────────────────────────
def _snap_camera_safe():
    from core.camera import snap_gameplay
    if STATE.player is None:
        return
    w, h = _maps._live_map_dims()
    snap_gameplay(STATE.player.rect.center, w, h,
                  aim_angle=STATE.player.angle, who="m6_snap")


def _save_progress(stage):
    try:
        from core.save_system import set_slot_progress
        set_slot_progress("m6", checkpoint=stage)
    except Exception:
        pass


def _bind(stage, objective, radio_line=None, radio_mark=None):
    from core.interactions import clear_radio_queue
    clear_radio_queue()
    STATE.mission6_stage = stage
    STATE.mission_phase = "m6_" + stage
    _world.build_world(stage)
    _set_objective(objective)
    _snap_camera_safe()
    _save_progress(stage)
    if radio_line:
        who, line = radio_line
        _world.radio(who + ": " + line, color=_speaker_colour(who),
                     duration=400, mark=radio_mark or ("stage_" + stage))


def _set_objective(text):
    _maps._objective = text


# ─────────────────────────────────────────────
# Mission identity / reset
# ─────────────────────────────────────────────
def _initialize_m6(preserve_timer=False):
    old_start = getattr(STATE, "mission_start_time", 0)
    STATE.reset()
    STATE.active_mission = MISSION6_KEY
    STATE.active_mission_id = MISSION6_ID
    STATE.active_mission_title = MISSION6_TITLE
    STATE.active_mission_operation = "THE BORDER - BLACK NOTEBOOK"
    STATE.active_mission_outcome = (
        "Volkov trapped  \u00b7  Last notebook recovered  \u00b7  Vasile named")
    STATE.active_mission_quote_attr = "Volkov, at the boxcar:"
    STATE.active_mission_quote = (
        '"I just wanted to get out. Funny. You did too."')

    STATE.request_mission6_ending = False
    STATE.request_death_screen = False
    STATE.player_dead = False
    STATE.mission6_stage = STAGE_CUSTOMS
    STATE.mission_phase = "m6_customs"
    STATE.m6_volkov_dead = False
    STATE.m6_alarm = False
    STATE.m6_alarm_triggered = False
    STATE.m6_exposure = 0.0
    STATE.m6_wave_count = 0
    STATE.request_m6_cutscene = None
    STATE.m6_train_active = False
    STATE.m6_train_time = 0.0
    STATE.m6_train_result = None
    STATE.m6_train_overrun = False
    STATE.m6_train_guards_left = 0
    STATE.m6_train_death = False
    STATE.m6_customs_checkpoint = False
    STATE.m6_noman_checkpoint = False
    STATE.m6_rail_checkpoint = False
    STATE.m6_train_checkpoint_reached = False

    STATE.k9_unlocked = True
    STATE.current_weapon = "k9_smg"
    STATE.k9_ammo_in_mag = STATE.k9_mag_size
    STATE.k9_spare_mags = 3
    STATE.player_disarmed = False
    STATE.hostiles_killed = 0
    STATE.shots_fired = 0
    STATE.shots_hit = 0

    _maps._radio_marks = set()
    _maps._last_keys = None
    try:
        from . import train3d as _train  # lazy: the scene owns its own state
        _train.reset()
    except Exception:
        pass
    STATE.mission_start_time = (
        old_start if (preserve_timer and old_start) else _now_ms())
    STATE.mission_end_time = 0


# ─────────────────────────────────────────────
# Stage entries
# ─────────────────────────────────────────────
def _enter_customs():
    _bind(STAGE_CUSTOMS, STAGE_OBJECTIVES[STAGE_CUSTOMS],
          ("MARU", "Border's closed. Customs is abandoned, not empty. Search it."),
          "stage_customs")
    STATE.m6_customs_checkpoint = True


def _enter_noman():
    _bind(STAGE_NOMAN, STAGE_OBJECTIVES[STAGE_NOMAN],
          _STAGE_RADIO[STAGE_NOMAN], "stage_noman")
    STATE.m6_noman_checkpoint = True


def _enter_rail():
    _bind(STAGE_RAIL, STAGE_OBJECTIVES[STAGE_RAIL],
          _STAGE_RADIO[STAGE_RAIL], "stage_rail")
    STATE.m6_rail_checkpoint = True


def _enter_boxcar():
    """Freeze on the rail map and request the 3D conversation."""
    from core.interactions import clear_radio_queue
    clear_radio_queue()
    STATE.mission6_stage = STAGE_BOXCAR
    STATE.mission_phase = "m6_boxcar"
    _set_objective(STAGE_OBJECTIVES[STAGE_BOXCAR])
    STATE.request_m6_cutscene = "boxcar"
    _world.sfx("door_open", 0.35)


def _request_ending():
    """The train is the last playable beat; the ending film takes it from here."""
    STATE.request_mission6_ending = True


def _enter_train():
    """Boxcar done -> interactive shoulder-cam train sequence."""
    _bind(STAGE_TRAIN, STAGE_OBJECTIVES[STAGE_TRAIN],
          ("MARU", "The train is leaving. Keep the Guard's heads down."),
          "stage_train")
    STATE.m6_train_checkpoint_reached = True
    STATE.m6_train_result = None
    STATE.m6_train_active = True
    try:
        from . import train3d as _train
        _train.begin()
    except Exception:
        # A broken scene must never strand the mission: fall through to the ending.
        STATE.m6_train_active = False
        STATE.m6_train_result = "fallback"
        STATE.m6_volkov_dead = True
        _request_ending()


# ─────────────────────────────────────────────
# Public start / checkpoint wrappers
# ─────────────────────────────────────────────
def start_m6(preserve_timer=False):
    _initialize_m6(preserve_timer)
    _decor.reset_run()
    _enter_customs()
    return STATE.player


def _checkpoint(enter, preserve_timer=False, fresh_decor=False):
    _initialize_m6(preserve_timer)
    if fresh_decor:
        _decor.reset_run()
    enter()
    return STATE.player


def start_mission6_customs_checkpoint(preserve_timer=False):
    return _checkpoint(_enter_customs, preserve_timer)


def start_mission6_noman_checkpoint(preserve_timer=False):
    return _checkpoint(_enter_noman, preserve_timer)


def start_mission6_rail_checkpoint(preserve_timer=False):
    return _checkpoint(_enter_rail, preserve_timer)


def start_mission6_train_checkpoint(preserve_timer=False):
    return _checkpoint(_enter_train, preserve_timer)


# ─────────────────────────────────────────────
# Interaction / prompts
# ─────────────────────────────────────────────
def _anchor_pos(stage):
    c, r = STAGE_ANCHORS.get(stage, STAGE_ANCHORS[STAGE_CUSTOMS])
    return _world._tile_world(c, r)


def interaction_prompt():
    if getattr(STATE, "request_m6_cutscene", None):
        return None
    if getattr(STATE, "m6_train_active", False):
        return None
    stage = getattr(STATE, "mission6_stage", None)
    if stage == STAGE_CUSTOMS and _world.near(_anchor_pos(STAGE_CUSTOMS), GATE_RADIUS):
        return "E  NORTH GATE"
    if stage == STAGE_NOMAN and _world.near(_anchor_pos(STAGE_NOMAN), GATE_RADIUS):
        return "E  RAIL YARD"
    if stage == STAGE_RAIL and _world.near(_anchor_pos(STAGE_RAIL), BOXCAR_RADIUS):
        return "E  OPEN THE BOXCAR"
    return None


def handle_interact():
    if STATE.player is None or STATE.player_dead:
        return False
    if getattr(STATE, "m6_train_active", False):
        return False
    if getattr(STATE, "request_m6_cutscene", None):
        return False
    stage = getattr(STATE, "mission6_stage", None)
    if stage == STAGE_CUSTOMS:
        if _world.near(_anchor_pos(STAGE_CUSTOMS), GATE_RADIUS):
            _enter_noman()
            return True
    elif stage == STAGE_NOMAN:
        if _world.near(_anchor_pos(STAGE_NOMAN), GATE_RADIUS):
            _enter_rail()
            return True
    elif stage == STAGE_RAIL:
        if _world.near(_anchor_pos(STAGE_RAIL), BOXCAR_RADIUS):
            _enter_boxcar()
            return True
    return False


def on_m6_cutscene_done(key):
    """app.py: the mid-mission film finished (or was skipped)."""
    STATE.request_m6_cutscene = None
    if key != "boxcar":
        return False
    if getattr(STATE, "mission6_stage", None) != STAGE_BOXCAR:
        return False
    _enter_train()
    return True


def on_train_done(result="win"):
    """TrainScene handoff - idempotent; success hands off to the ending film.

    Failure results (``dead``/``failed``) are a retry, never an ending handoff.
    """
    if getattr(STATE, "mission6_stage", None) != STAGE_TRAIN:
        return False
    if getattr(STATE, "request_mission6_ending", False):
        return False
    if (getattr(STATE, "player_dead", False)
            or getattr(STATE, "m6_train_death", False)
            or getattr(STATE, "m6_train_result", None) in ("dead", "failed")):
        # A failed train run is a retry, not a handoff to the ending.
        return False
    STATE.m6_train_active = False
    STATE.m6_train_result = result
    if result == "win":
        STATE.active_mission_outcome = (
            "Volkov reached the step  \u00b7  Last notebook recovered"
            "  \u00b7  Vasile named")
    STATE.m6_volkov_dead = True
    v = _world.volkov()
    if v:
        v["dead"] = True
    _request_ending()
    return True


_boxcar_wait = 0.0


def _recover_boxcar(dt):
    """If a host consumed the request but never called back, move on."""
    global _boxcar_wait
    if getattr(STATE, "mission6_stage", None) != STAGE_BOXCAR:
        _boxcar_wait = 0.0
        return
    if getattr(STATE, "request_m6_cutscene", None):
        _boxcar_wait = 0.0
        return
    _boxcar_wait += max(0.0, float(dt))
    if _boxcar_wait > 2.5:
        _boxcar_wait = 0.0
        on_m6_cutscene_done("boxcar")


def update_stage(dt=None):
    if dt is None:
        dt = getattr(STATE, "dt", 1.0 / 60.0)
    _world.update_world()
    _recover_boxcar(dt)
