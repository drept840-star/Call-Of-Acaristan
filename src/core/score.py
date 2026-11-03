"""score.py - the OST under quiet gameplay.

The menu theme and Mission 7's own cues (missions.m7.m7_audio.music) were the
only streamed music; the prologue walk and M1-M6 played to foley alone. This
drives the score there, once per frame from the main loop:

  calm  - the mission's track fades in after CALM_DELAY_S of play with no
          fighting (START_DELAY_S after a mission start, cutscene or death).
  tense - a gunshot, blast or alarm, or a guard who has spotted the player,
          swaps in TENSE. It holds until COMBAT_HOLD_S after the last sign of
          a fight, then fades, and the calm countdown runs again.

Only music this module started is ever faded or replaced, so the menu theme
and M7's cues behave as before. Settings key "dynamic_music" turns it off.
"""
from audio import voice
from core.config import audio
from core.state import STATE

OST = "assets/music/ost/"
# "WALK" is the prologue state; the rest are STATE.active_mission keys.
CALM = {
    "WALK": OST + "01_call_of_acaristan.mp3",
    "MISSION1": OST + "02_black_notebook.mp3",
    "MISSION2": OST + "03_quiet_on_route_12.mp3",
    "MISSION3": OST + "04_the_vostral.mp3",
    "MISSION4": OST + "05_curfew_dawn.mp3",
    "MISSION5": OST + "05_curfew_dawn.mp3",
    "MISSION6": OST + "07_whiteout.mp3",
}
TENSE = OST + "06_not_tonight.mp3"
# play_music() levels: the menu theme sits at 0.48, M7's farm cue at 0.30.
CALM_VOL = 0.30
TENSE_VOL = 0.42
VO_DUCK = 0.55              # level scale while a voice line plays

START_DELAY_S = 6.0
CALM_DELAY_S = 20.0
COMBAT_HOLD_S = 10.0
FADE_IN_MS = {CALM_VOL: 3000, TENSE_VOL: 900}

# Sounds that mean a fight is on; AudioManager stamps the last one played.
COMBAT_SFX = frozenset({
    "gunshot", "gunshot_distant", "shotgun_blast", "sniper_crack", "bullet_snap",
    "bullet_impact", "bullet_impact_enemy", "melee_hit", "explosion",
    "molotov_explode", "breach", "alarm", "mission3_alarm_loop",
    "m6_rifle_crack", "m6_report_far", "m6_headshot", "m6_whiz",
})
# States that keep the score where it is: PAUSED holds it, the notebook
# inspect lets it play on. Everything else that is not play fades it out.
HOLD_STATES = {"PAUSED", "NOTEBOOK_INSPECT"}

audio.combat_names = COMBAT_SFX

enabled = True
_s = {"key": None, "quiet_s": 0.0, "seen_ms": None, "owned": None,
      "level": 0.0, "failed": set()}


def _key(state):
    if state == "WALK":
        return "WALK"
    if state == "GAME":
        key = getattr(STATE, "active_mission", None)
        return key if key in CALM else None
    return None


def _guard_on_alert():
    for e in getattr(STATE, "enemies", None) or ():
        if getattr(e, "alerted", False) and getattr(e, "hp", 1) > 0:
            return True
    return False


def _fight_signal():
    stamp = audio.last_combat_ms
    if stamp != _s["seen_ms"]:
        _s["seen_ms"] = stamp
        return True
    return (_guard_on_alert()
            or bool(getattr(STATE, "m6_alarm", False))
            or audio.is_playing("m3_alarm"))


def _release(fade_ms):
    """Fade out the track this module started, if it is still the one playing."""
    if _s["owned"] is not None and audio.music_name() == _s["owned"]:
        audio.fade_out_music(fade_ms)
    _s["owned"] = None


def _drive(want, vol, dt):
    if audio.music_name() != _s["owned"]:
        _s["owned"] = None                      # something else took the stream
    if want is not None and _s["owned"] == want:
        target = vol * (VO_DUCK if voice.busy() else 1.0)
        _s["level"] += (target - _s["level"]) * min(1.0, dt * 3.0)
        audio.play_music(want, volume=_s["level"])
        return
    if _s["owned"] is not None:
        _release(700 if want == TENSE else 2500)
        return
    if (want is None or want in _s["failed"]
            or audio.music_name() is not None or audio.music_busy()):
        return
    if audio.play_music(want, volume=vol, fade_ms=FADE_IN_MS[vol]):
        _s["owned"] = want
        _s["level"] = vol
    else:
        _s["failed"].add(want)                  # missing/undecodable: don't retry


def update(state, dt):
    """Call once per frame with the current game-state name and frame dt (s)."""
    if state in HOLD_STATES and _s["key"] is not None:
        if state == "PAUSED" and _s["owned"] is not None:
            audio.pause_music()
        return
    key = _key(state) if enabled else None
    if key is None:
        if _s["key"] is not None:
            _release(1500)
            _s["key"] = None
        return
    if key != _s["key"]:
        _s["key"] = key
        _s["quiet_s"] = CALM_DELAY_S - START_DELAY_S
        _s["seen_ms"] = audio.last_combat_ms
    if _fight_signal():
        _s["quiet_s"] = 0.0
    else:
        _s["quiet_s"] += dt
    if _s["quiet_s"] < COMBAT_HOLD_S:
        _drive(TENSE, TENSE_VOL, dt)
    elif _s["quiet_s"] >= CALM_DELAY_S:
        _drive(CALM[key], CALM_VOL, dt)
    else:
        _drive(None, 0.0, dt)
