"""Mission 1 cutscene data (RPE6 Phase 8 + WP2: the cut as ae.timeline/1).

The escape cut was the last frame-counted sequence in the game: 1080 updates of
`escape_cutscene_timer`, with the phase, the subtitles and every one-shot cue
keyed off that one integer. It is now `m1.escape` - four shots (dashboard,
close-up, truck, rear) whose scenes are the painters registered by
`missions.m1.draw`, played by `app.CutscenePlayer` like every other cut.

The cut was authored in frames and the painters still take one, so frames stay
the authoring unit here and `_ms()` is the single conversion point. Cue and
line stamps are written in the old global frame numbers and land as ms offsets
*inside their own shot* (`_at`), which is what the player fires on - there is no
global frame counter left to read.
"""
from __future__ import annotations

import game.timelines as _timelines  # RPE6 P8: timeline data access

ESCAPE_FPS = 60
ESCAPE_FRAMES = 1080        # the old ESCAPE_CUTSCENE_DURATION, now a sanity bound
ESCAPE_VO_NOTEBOOK = "Good. I've got it. Later. You need sleep."   # VO_198 (caption-only)


def _ms(frame):
    """Timeline milliseconds for a frame stamp of the cut (60 fps)."""
    return int(round(frame * 1000.0 / ESCAPE_FPS))


def _at(frame, shot_start):
    """Offset in ms of a cut frame inside the shot that starts at `shot_start`."""
    return _ms(frame) - _ms(shot_start)


# The cut, cut at the painter's phase boundaries and at the two speaking beats.
# `scene_time_offset_ms` keeps each shot's scene on the cut's own clock, so the
# picture is continuous across the cuts.
escape_shots = [
    # 0-134  dashboard / wire close-up, starter catches.
    {"scene": "m1_escape_dashboard", "speaker": None, "text": None,
     "hide_caption": True, "quiet_ui": True, "self_graded": True,
     "auto_advance": True, "hard_cut": True,
     "min_ms": _ms(135), "scene_time_offset_ms": _ms(0), "lighting": (5, 7, 10),
     "cues": ((_at(18, 0), "door_open", 0.45),
              (_at(38, 0), "rig_low_boom", 0.25))},
    # 135-299  Biribel at the wheel.
    {"scene": "m1_escape_closeup", "speaker": None, "text": None,
     "hide_caption": True, "quiet_ui": True, "self_graded": True,
     "auto_advance": True, "hard_cut": True,
     "min_ms": _ms(300) - _ms(135), "scene_time_offset_ms": _ms(135),
     "lighting": (5, 7, 10)},
    # 300-499  side view: the truck bursts the service gate. Vasile takes the
    # notebook over the radio at frame 392 (VO_198, the M6 plant) - the painter
    # draws that caption, the timeline owns the line.
    {"scene": "m1_escape_truck", "speaker": None, "text": None,
     "hide_caption": True, "quiet_ui": True, "self_graded": True,
     "auto_advance": True, "hard_cut": True,
     "min_ms": _ms(500) - _ms(300), "scene_time_offset_ms": _ms(300),
     "lighting": (5, 7, 10),
     "cues": ((_at(310, 300), "missile_launch", 0.32),),
     "dialogue_events": ((_at(392, 300), "VASILE", ESCAPE_VO_NOTEBOOK, True),)},
    # 500-1079  rear view: road, radio handoff, signal tear-down, report card.
    {"scene": "m1_escape_rear", "speaker": None, "text": None,
     "hide_caption": True, "quiet_ui": True, "self_graded": True,
     "auto_advance": True, "hard_cut": True,
     "min_ms": _ms(ESCAPE_FRAMES) - _ms(500), "scene_time_offset_ms": _ms(500),
     "lighting": (5, 7, 10),
     "cues": ((_at(650, 500), "radio_static", 0.22),
              (_at(735, 500), "terminal_glitch", 0.24),
              (_at(820, 500), "menu_click", 0.34))},
]
escape_shots = _timelines.shots("m1.escape", escape_shots)  # WP2: timeline data
