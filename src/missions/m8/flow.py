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
    ROUTE_REVENGE, ROUTES, STAGE_CHASE, STAGE_FLIGHT, STAGE_GANTRY, STAGE_KILL, STAGE_MANSION,
    STAGE_RIDGE, STAGE_TRAP, film_shots, first_stage, stages_for)
from .duty import flight3d as _flight
from .duty import mansion3d as _mansion
from .duty import ridge3d as _ridge
from .revenge import beats as _beats
from .revenge import chase3d as _chase
from .revenge import kill3d as _kill
from .revenge import trap3d as _trap
from . import m8_audio as _m8_audio

# stage -> score cue when no scene owns the stage (the ENTER-stepped beats).
STAGE_MUSIC = {"meet": "meet", "friends": "friends", "epilogue": "names",
               "d_approach": "approach", "liftoff": "flight", "crash": "flight",
               "d_epilogue": "names"}


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
    _mansion.abort()
    _flight.abort()
    _ridge.abort()
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
        STATE.m8_trap_cp = 3 if token == STAGE_GANTRY else int(getattr(STATE, "m8_trap_cp", 0) or 0)
        _trap.begin()
    elif token == STAGE_KILL:
        _kill.begin()
    elif token == STAGE_CHASE:
        _chase.begin()
    elif token == STAGE_MANSION:
        STATE.m8_mansion_cp = int(getattr(STATE, "m8_mansion_cp", 0) or 0)
        _mansion.begin()
    elif token == STAGE_FLIGHT:
        STATE.m8_flight_cp = int(getattr(STATE, "m8_flight_cp", 0) or 0)
        _flight.begin()
    elif token == STAGE_RIDGE:
        _ridge.begin()
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
    if _mansion.active():
        return _mansion
    if _flight.active():
        return _flight
    if _ridge.active():
        return _ridge
    return None


def music_tick():
    """Per frame while M8 gameplay is on screen: steer the score to the scene."""
    if _kill.active():
        return                              # the kill scores its own beats
    if _trap.active():
        phase = getattr(_trap.scene(), "phase", "")
        cue = "gantry" if phase in ("clear", "climb", "catwalk") else "trap"
    elif _chase.active():
        cs = getattr(_chase.scene(), "cutscene", None)
        cue = cs.get("music", "chase") if cs else "chase"
    elif _mansion.active():
        cue = "mansion"
    elif _flight.active():
        cue = "flight_boss" if getattr(_flight.scene(), "cp", 0) >= 4 else "flight"
    elif _ridge.active():
        if getattr(_ridge.scene(), "phase", "") == "pres_down":
            return
        cue = "state"
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
    _mansion.set_paused(paused)
    _flight.set_paused(paused)
    _ridge.set_paused(paused)


def on_mansion_done(result):
    """Study door kicked (or scene fault): on to Liftoff."""
    if getattr(STATE, "mission8_stage", "") == STAGE_MANSION:
        STATE.m8_mansion_cp = 0
        advance_stage()
    return True


def on_flight_done(result):
    """Ucilev's rocket hit the tail: on to the crash film."""
    if getattr(STATE, "mission8_stage", "") == STAGE_FLIGHT:
        STATE.m8_flight_cp = 0
        STATE.m8_ucilev_cp = None
        advance_stage()
    return True


def on_ridge_done(result):
    """Retardovici is down: on to the epilogue."""
    if getattr(STATE, "mission8_stage", "") == STAGE_RIDGE:
        advance_stage()
    return True


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
        STATE.m8_trap_cp = 0
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
    """A stage film ended: step past it (or resume mid-chase after the gunship arrival)."""
    if _m8_audio.AUDIO is not None and key not in ("d_approach", "liftoff", "crash"):
        _m8_audio.AUDIO.film_end()
    if key == "heli" and _chase.active():
        _chase.scene().on_heli_cutscene_done()
        return
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
    same_stage = (
        getattr(STATE, "active_mission", None) == MISSION8_KEY
        and stage is not None
        and stage == getattr(STATE, "mission8_stage", None)
    )
    saved_cps = (
        {
            "m8_mansion_cp": int(getattr(STATE, "m8_mansion_cp", 0) or 0),
            "m8_flight_cp": int(getattr(STATE, "m8_flight_cp", 0) or 0),
            "m8_ucilev_cp": getattr(STATE, "m8_ucilev_cp", None),
            "m8_chase_cp": int(getattr(STATE, "m8_chase_cp", 0) or 0),
            "m8_trap_cp": int(getattr(STATE, "m8_trap_cp", 0) or 0),
        }
        if same_stage
        else None
    )
    _initialize_m8(chosen, preserve_timer)
    if saved_cps is not None:
        for k, v in saved_cps.items():
            setattr(STATE, k, v)
    STATE.player = Player(64, 64)
    if stage not in stages_for(chosen):
        stage = first_stage(chosen)
    set_stage(stage)
    return STATE.player
