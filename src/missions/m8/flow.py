"""Mission 8 - stage ladder, checkpoints and the outro handoff.

``STATE.m8_route`` picks the ladder (``meta.stages_for``).  ``set_stage``
records the stage on STATE and in the save slot; ``advance_stage`` steps the
ladder and past the last stage raises ``STATE.m8_outro`` for app.py.
The trap and the gantry are one scene: reaching the gantry records the stage
without restarting the fight.
"""
from core.config import audio as _audio_manager
from core.state import STATE
from engine.core import now_ms as _now_ms
from entities.player import Player

from .meta import (
    FIGHT_STAGES, FILM_TIMELINES, MISSION8_ID, MISSION8_KEY, MISSION8_TITLE, OPERATIONS,
    ROUTE_REVENGE, ROUTES, STAGE_CHASE, STAGE_GANTRY, STAGE_KILL, STAGE_TRAP, film_shots,
    first_stage, stages_for)
from .revenge import beats as _beats
from .revenge import chase3d as _chase
from .revenge import kill3d as _kill
from .revenge import trap3d as _trap
from . import m8_audio as _m8_audio

# stage -> score cue when no scene owns the stage (the ENTER-stepped beats).
STAGE_MUSIC = {"meet": "meet", "friends": "friends", "epilogue": "names"}


def _save_progress(stage):
    try:
        from core.save_system import set_slot_progress
        set_slot_progress("m8", checkpoint=stage)
    except Exception:
        pass


def _saved_route():
    try:
        from core.save_system import get_slot_flags
        return (get_slot_flags() or {}).get("m8_route")
    except Exception:
        return None


def route():
    r = getattr(STATE, "m8_route", None)
    return r if r in ROUTES else ROUTE_REVENGE


def _initialize_m8(route_, preserve_timer=False):
    old_start = getattr(STATE, "mission_start_time", 0)
    _trap.abort()
    _kill.abort()
    _chase.abort()
    STATE.reset()
    STATE.m8_route = route_
    STATE.active_mission = MISSION8_KEY
    STATE.active_mission_id = MISSION8_ID
    STATE.active_mission_title = MISSION8_TITLE
    STATE.active_mission_operation = OPERATIONS.get(route_, "OLD FRIENDS")
    STATE.mission_start_time = (
        old_start if (preserve_timer and old_start) else _now_ms())
    STATE.mission_end_time = 0


def set_stage(token):
    STATE.mission8_stage = token
    STATE.mission_phase = "m8_" + token
    _save_progress(token)
    if token in FIGHT_STAGES:
        if token == STAGE_GANTRY and _trap.active():
            return                       # the fight scene is already on the gantry
        STATE.m8_trap_cp = 3 if token == STAGE_GANTRY else 0
        _trap.begin()
    elif token == STAGE_KILL:
        _kill.begin()
    elif token == STAGE_CHASE:
        _chase.begin()
    elif token in FILM_TIMELINES and film_shots(token):
        STATE.request_m8_cutscene = token      # app.py plays the film, then on_cutscene_done
    else:
        _beats.begin(token, advance_stage)


def live_scene():
    """The 3D scene that owns input now (trap/gantry fight, kill or chase), or None."""
    if _trap.active():
        return _trap
    if _kill.active():
        return _kill
    if _chase.active():
        return _chase
    return None


def music_tick():
    """Per frame while M8 gameplay is on screen: steer the score to the scene."""
    if _kill.active():
        return                              # the kill scores its own beats
    if _trap.active():
        phase = getattr(_trap.scene(), "phase", "")
        cue = "gantry" if phase in ("clear", "climb", "catwalk") else "trap"
    elif _chase.active():
        cue = "chase"
    else:
        cue = STAGE_MUSIC.get(getattr(STATE, "mission8_stage", ""))
    _m8_audio.music(_audio_manager, cue)


def scene_event(event):
    sc = live_scene()
    if sc is not None:
        sc.handle_event(event)


def scene_pause(paused):
    _trap.set_paused(paused)
    _kill.set_paused(paused)
    _chase.set_paused(paused)


def on_chase_done(result):
    """Biribel made the train (or a scene fault): on to the epilogue."""
    if getattr(STATE, "mission8_stage", "") == STAGE_CHASE:
        advance_stage()
    return True


def on_kill_done(result):
    """The shot (Biribel's, or Bodi's if he held back; or a scene fault): on to the chase."""
    if getattr(STATE, "mission8_stage", "") == STAGE_KILL:
        advance_stage()
    return True


def on_gantry_reached():
    """The road is clear: save at the gantry; the scene plays on."""
    if getattr(STATE, "mission8_stage", "") == STAGE_TRAP:
        set_stage(STAGE_GANTRY)


def on_trap_done(result):
    """The fight ended (Vasile reached, or a scene fault that must not lock the mission)."""
    if getattr(STATE, "mission8_stage", "") in FIGHT_STAGES:
        STATE.mission8_stage = STAGE_GANTRY
        advance_stage()
    return True


def advance_stage():
    """Step to the next stage; the last stage requests the outro instead."""
    stages = stages_for(route())
    stage = getattr(STATE, "mission8_stage", "") or stages[0]
    index = stages.index(stage) if stage in stages else -1
    if index + 1 < len(stages):
        set_stage(stages[index + 1])
    else:
        STATE.m8_outro = True


def take_cutscene_request():
    """Stage token of the film waiting to play, once (app.py starts it)."""
    key = getattr(STATE, "request_m8_cutscene", None)
    STATE.request_m8_cutscene = None
    return key


def on_cutscene_done(key):
    """A stage film ended: step past it."""
    if _m8_audio.AUDIO is not None:
        _m8_audio.AUDIO.film_end()
    if getattr(STATE, "mission8_stage", "") == key:
        advance_stage()


def take_outro_request() -> bool:
    """True once after the mission finishes (app.py shows mission complete)."""
    if getattr(STATE, "m8_outro", False):
        STATE.m8_outro = False
        return True
    return False


def handle_interact():
    return False


def start_m8(stage=None, route_=None, preserve_timer=False):
    """Start (or resume) Mission 8.  The route survives ``STATE.reset``:
    argument, then STATE, then the save slot, then Revenge."""
    chosen = route_ or getattr(STATE, "m8_route", None) or _saved_route()
    chosen = chosen if chosen in ROUTES else ROUTE_REVENGE
    _initialize_m8(chosen, preserve_timer)
    STATE.player = Player(64, 64)
    if stage not in stages_for(chosen):
        stage = first_stage(chosen)
    set_stage(stage)
    return STATE.player
