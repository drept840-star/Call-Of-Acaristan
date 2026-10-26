"""Mission 1 music hook: two looped stems (infiltrate / combat), crossfaded over
1.5 s when the alarm flips STATE.firefight_triggered.

The tracks are optional (CWD-relative, like the rest of assets/): without them
every call is a silent no-op. The file check runs once and is cached.

update_m1_music() runs once per M1 gameplay sim step (60 Hz) from
missions.m1.update.game_update. core.ambience calls watchdog() every frame: it
stops both stems when the mission is not M1 or when gameplay has not ticked for
a moment (cutscene, menu, pause, death screen).
"""
import os
import time

from core.config import audio
from core.state import STATE

TRACKS = ("assets/music/m1_infiltrate.ogg", "assets/music/m1_combat.ogg")
FADE_S = 1.5
STEP_DT = 1 / 60            # one call per fixed sim step
_STALE_S = 0.25

_m = {"checked": False, "sounds": None, "chans": [None, None], "levels": None, "last": 0.0}


def m1_music_targets(firefight, prev_levels, dt):
    """Pure crossfade step: move (infiltrate, combat) levels linearly toward
    (0, 1) when ``firefight`` else (1, 0), a full swing taking FADE_S seconds."""
    target = (0.0, 1.0) if firefight else (1.0, 0.0)
    step = dt / FADE_S
    return tuple(min(t, lv + step) if lv < t else max(t, lv - step)
                 for lv, t in zip(prev_levels, target))


def _load():
    _m["checked"] = True
    _m["sounds"] = None
    present = [os.path.exists(p) for p in TRACKS]
    if not any(present):
        return
    try:
        import pygame
        if not pygame.mixer.get_init():
            return
        sounds = [pygame.mixer.Sound(p) if ok else None for p, ok in zip(TRACKS, present)]
    except Exception:
        return
    if any(s is not None for s in sounds):
        _m["sounds"] = sounds


def _gain():
    return (getattr(audio, "master_volume", 1.0)
            * getattr(audio, "_current_music_vol", 0.5))


def update_m1_music(dt=STEP_DT):
    if not _m["checked"]:
        _load()
    if not _m["sounds"]:
        return
    _m["last"] = time.monotonic()
    firefight = bool(getattr(STATE, "firefight_triggered", False))
    if _m["levels"] is None:
        _m["levels"] = (0.0, 1.0) if firefight else (1.0, 0.0)
    else:
        _m["levels"] = m1_music_targets(firefight, _m["levels"], dt)
    try:
        gain = _gain()
        for i, s in enumerate(_m["sounds"]):
            if s is None:
                continue
            ch = _m["chans"][i]
            if ch is None or ch.get_sound() is not s:
                ch = s.play(loops=-1)
                _m["chans"][i] = ch
            if ch is not None:
                ch.set_volume(_m["levels"][i] * gain)
    except Exception:
        pass


def stop():
    for i, ch in enumerate(_m["chans"]):
        if ch is not None:
            try:
                ch.stop()
            except Exception:
                pass
        _m["chans"][i] = None
    _m["levels"] = None


def watchdog():
    if not _m["sounds"] or not any(ch is not None for ch in _m["chans"]):
        return
    if (getattr(STATE, "active_mission", None) != "MISSION1"
            or time.monotonic() - _m["last"] > _STALE_S):
        stop()
