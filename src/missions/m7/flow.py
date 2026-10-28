"""Mission 7 - stage ladder, checkpoints and the outro handoff (skeleton).

``set_stage`` records the stage on STATE and in the save slot.
``advance_stage`` steps the ladder; past the last stage it raises
``STATE.m7_outro`` for app.py to consume through ``take_outro_request``.
"""
from core.config import audio as _audio_manager
from core.state import STATE
from engine.core import now_ms as _now_ms
from entities.player import Player

from . import m7_audio as _m7_audio
from . import choice as _choice
from . import farmyard as _farmyard
from . import raid3d as _raid
from .meta import (
    FILM_TIMELINES, MISSION7_ID, MISSION7_KEY, MISSION7_TITLE, STAGES, STAGE_ARRIVAL,
    STAGE_CHORES, STAGE_CHOICE, STAGE_FINALE, STAGE_PREP, STAGE_RAID, STAGE_RAIDIN,
    STAGE_RUNNER)

# Score cue per stage (m7_audio.MUSIC). The runner film keeps the farm theme
# running between chores and prep; the raid-in film starts the raid track so
# the fight picks it up without a cut; the radio choice is music-free so the
# hum and the two channels carry it.
STAGE_MUSIC = {
    STAGE_ARRIVAL: "film",
    STAGE_CHORES: "farm",
    STAGE_RUNNER: "farm",
    STAGE_PREP: "farm",
    STAGE_RAIDIN: "raid",
    STAGE_RAID: "raid",
    STAGE_FINALE: "film",
    STAGE_CHOICE: None,
}


def _save_progress(stage):
    try:
        from core.save_system import set_slot_progress
        set_slot_progress("m7", checkpoint=stage)
    except Exception:
        pass


def _initialize_m7(preserve_timer=False):
    old_start = getattr(STATE, "mission_start_time", 0)
    if _m7_audio.AUDIO is not None:
        _m7_audio.AUDIO.stop()
    _raid.abort()
    STATE.reset()
    STATE.active_mission = MISSION7_KEY
    STATE.active_mission_id = MISSION7_ID
    STATE.active_mission_title = MISSION7_TITLE
    STATE.active_mission_operation = "FALLOW GROUND"
    STATE.mission_start_time = (
        old_start if (preserve_timer and old_start) else _now_ms())
    STATE.mission_end_time = 0


def set_stage(token):
    STATE.mission7_stage = token
    STATE.mission_phase = "m7_" + token
    STATE.request_m7_cutscene = token if token in FILM_TIMELINES else None
    _save_progress(token)
    snd = _m7_audio.instance(_audio_manager)
    snd.warm()
    snd.stop_loops()
    if token in _farmyard.FARM_STAGES:
        _farmyard.begin(token, advance_stage)
        snd.start_loop("m7_farm_bed", 0.18)
    elif token == STAGE_RAID:
        STATE.m7_raid_cp = 0
        _raid.begin()
        snd.start_loop("m7_night_bed", 0.16)
    elif token == STAGE_CHOICE:
        _choice.begin(advance_stage)


def music_tick():
    """Per frame while M7 gameplay is on screen: steer the score to the stage cue."""
    _m7_audio.music(_audio_manager, STAGE_MUSIC.get(getattr(STATE, "mission7_stage", "")))


def film_music(key):
    """Per frame while an M7 film plays: ``key`` is the stage token, or "outro"."""
    _m7_audio.music(_audio_manager, "outro" if key == "outro" else STAGE_MUSIC.get(key))


def on_raid_done(result):
    """The raid ended (win, or a scene fault that must not lock the mission): move on."""
    if getattr(STATE, "mission7_stage", "") == STAGE_RAID:
        advance_stage()
    return True


def take_cutscene_request():
    """Stage token of the film waiting to play, once (app.py starts it)."""
    key = getattr(STATE, "request_m7_cutscene", None)
    STATE.request_m7_cutscene = None
    return key


def on_cutscene_done(key):
    """A stage film ended: step past its stage."""
    if getattr(STATE, "mission7_stage", "") == key:
        advance_stage()


def advance_stage():
    """Step to the next stage; the last stage requests the outro instead."""
    stage = getattr(STATE, "mission7_stage", "") or STAGE_ARRIVAL
    index = STAGES.index(stage)
    if index + 1 < len(STAGES):
        set_stage(STAGES[index + 1])
    else:
        STATE.m7_outro = True


def take_outro_request() -> bool:
    """True once after the mission finishes (app.py starts the outro)."""
    if getattr(STATE, "m7_outro", False):
        STATE.m7_outro = False
        return True
    return False


def handle_interact():
    if getattr(STATE, "mission7_stage", "") in _farmyard.FARM_STAGES:
        return _farmyard.interact()
    return False


def start_m7(stage=None, preserve_timer=False):
    kept = stage in (STAGE_RAID, STAGE_RAIDIN)
    preps = list(getattr(STATE, "m7_preps", None) or []) if kept else []
    _initialize_m7(preserve_timer)
    _m7_audio.instance(_audio_manager).warm()
    STATE.m7_preps = preps
    STATE.player = Player(64, 64)
    set_stage(stage or STAGE_ARRIVAL)
    return STATE.player


def start_m7_dev_raid(preps=(), cp=0):
    """Dev jump: the raid with the given preps, optionally already past wave ``cp`` (1 or 2)."""
    STATE.m7_preps = list(preps)
    player = start_m7(STAGE_RAID)
    cp = max(0, min(2, int(cp)))
    if cp:
        STATE.m7_raid_cp = cp
        _raid.begin()
    return player


def start_m7_dev_outro():
    """Dev jump: skip the radio and play the outro film (the route defaults to duty)."""
    player = start_m7(STAGE_CHOICE)
    STATE.m8_route = STATE.m8_route or "duty"
    STATE.m7_outro = True
    return player
