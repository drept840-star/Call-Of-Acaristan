"""Split from mission4.py - see __init__.py for the package facade.

Mission start / stage-flow / completion control for Mission 4.
The stage ladder mirrors missions.m3.flow (start idiom, checkpoint
wrappers, idempotent completion); the content per stage grows slice by
slice (W2 curfew city, W3 liaison meet, W4 siege hold).
"""

import math
from engine.core import LEGACY_RNG as _rng_legacy  # RPE6 R6: named 'legacy' rng stream
import time

import pygame

from core.config import (SCENE_BOT, SCENE_TOP, WIDTH)
from core.state import STATE
from core import config as _config
from entities.player import Player
import game.dialogues as _dialogues  # RPE6 P7: conversation data access
import game.timelines as _timelines  # RPE6 P8: timeline data access
from engine.timeline import TimelinePlayer as _TimelinePlayer  # RPE6 P8
from ui.hud import MiniMap
from engine.core import now_ms as _now_ms  # RPE6 B-001 timebase

audio = _config.audio

from missions.m4 import maps as _m4_maps  # live view of MISSION4_MAP/_objective
from missions.m4.meta import (
    MAP_W, MAP_H,
    MISSION4_ID, MISSION4_KEY, MISSION4_TITLE,
    M4_HOLD_SECONDS,
    STAGE_INTRO, STAGE_AFTERMATH, STAGE_KRAP_STATUS, STAGE_MARU,
    STAGE_COMMIT, STAGE_DONE,
    TRANSMITTER_TILE,
    C_SYSTEM, C_VASILE, C_MARU, C_VOLKOV, C_RETARDOVICI, C_BALACEANU,
    BIRIBEL_SPEAKER,
)
from missions.m4.world import (
    _build_m4_world, _build_station_world, _movement_locked, _near, _radio,
    _set_objective, _street_door_pos, _tile_world, _vasile_cache_pos,
    _liaison_pos, _jammer_pos, _run_siege_director, _siege_reset,
    _arm_m4_allies,

)


def _tx_pos():
    return _tile_world(*TRANSMITTER_TILE)


def _snap_camera_safe():
    """Snap the camera onto the player at a world swap / mission start."""
    from core.camera import snap_gameplay
    if STATE.player is None:
        return
    w, h = _m4_maps._live_map_dims()
    snap_gameplay(STATE.player.rect.center, w, h, aim_angle=STATE.player.angle, who="m4_snap")


# ────────────────────────────────────────────
# Curfew-street ambience + story-beat ladder (W2)
# ────────────────────────────────────────────
# The city falls apart on a clock while Biribel crosses it: timed one-shot
# radio beats (Vasile's read on the 48h collapse, the loyalists arming,
# the border intercept that Volkov is gone, the PA calling for calm) plus
# repeating distant-audio events (gunfire across the rooftops, a squelch
# of static on the open band, a distorted PA mumble). Single-owner module
# clocks, reset by start_m4 (same precedent as m3.flow._monitor_on).
_M4_AMB = {"gun": 240, "static": 460, "pa": 760}
_M4_GUN_GAP = (300, 620)      # frames between distant bursts
_M4_STATIC_GAP = (520, 940)   # frames between radio-band squelches
_M4_PA_GAP = (1080, 1680)     # frames between PA mumbles (the regime performing calm)

# (chaos-timer frame, radio mark, line, speaker color) one-shots.
_M4_STORY_BEATS = [
    (240, "beat_loyalists",
     "VASILE: This isn't a crackdown - it's a collapse. Stay off the boulevard.",
     C_VASILE),
    (600, "beat_volkov",
     "INTERCEPT: North border logged one vehicle at first light. Volkov ran.",
     C_VOLKOV),
    (960, "beat_retardovici",
     "PA: Citizens. Curfew holds. The Presidency has this under control.",
     C_RETARDOVICI),
]


def _sfx(name, volume):
    try:
        audio.play(name, volume=volume)
    except Exception:
        pass  # audio is optional in headless harnesses


def _aftermath_ambient():
    """Drive the curfew-street ambient clock (STAGE_AFTERMATH only)."""
    if STATE.player is None:
        return
    STATE.m4_chaos_timer = getattr(STATE, "m4_chaos_timer", 0) + 1
    t = STATE.m4_chaos_timer

    # Timed one-shot story beats (dedup via _radio marks, objective untouched
    # so the stage ladder stays deterministic for the smoke chain).  RPE6 P8:
    # the ladder is timeline data (m4.story_beats event track, frames).
    if _timelines.use_legacy():
        for frame, mark, line, color in _M4_STORY_BEATS:
            if t == frame:
                _radio(line, color=color, duration=440, mark=mark)
    else:
        for clip in _ladder_player("story").events_between(t - 1, t):
            _radio(clip["text"], color=tuple(clip["color"]),
                   duration=clip["duration"], mark=clip["name"])

    # Repeating distant-audio events.
    _M4_AMB["gun"] -= 1
    if _M4_AMB["gun"] <= 0:
        _sfx("gunshot_distant", 0.24)
        _M4_AMB["gun"] = _rng_legacy.randint(*_M4_GUN_GAP)
    _M4_AMB["static"] -= 1
    if _M4_AMB["static"] <= 0:
        _sfx("radio_static", 0.16)
        _M4_AMB["static"] = _rng_legacy.randint(*_M4_STATIC_GAP)
    _M4_AMB["pa"] -= 1
    if _M4_AMB["pa"] <= 0:
        _sfx("pa_mumble", 0.18)
        _M4_AMB["pa"] = _rng_legacy.randint(*_M4_PA_GAP)


# ────────────────────────────────────────────
# Liaison meet: typewriter dialogue + the tone choice (W3)
# ────────────────────────────────────────────
# M3's interrogation typewriter is mission-scoped and must NOT be imported;
# the cadence values are ported verbatim (m3.flow._TYPE_SPEED mirrors
# acaristan.py's cutscene TEXT_SPEED = 4 frames/char, with the same
# punctuation-pause hold after sentence ends).
_TYPE_SPEED = 4


def _type_interval():
    """RPE6 P9: frames per typed character (text_speed setting; 4 at 1.0x)."""
    try:
        from core.user_settings import SETTINGS
        return max(1, int(round(_TYPE_SPEED / max(0.1, SETTINGS.text_speed_mul))))
    except Exception:
        return _TYPE_SPEED
_TYPE_PAUSE_FULL = 25   # frames held after . ! ?
_TYPE_PAUSE_SOFT = 12   # frames held after , ; :

# Maru's liaison beat. "line" beats type out then wait for a confirm; the
# single "choice" beat lists two options (Up/Down or Left/Right to move the
# highlight, Enter/Space to lock). The chosen index lands on STATE.m4_tone -
# not a branch, just the tone Biribel's ending V.O. reads back in W5.
_M4_LIAISON_BEATS = [
    {"type": "line", "speaker": "MARU", "color": C_MARU,
     "text": "You got the file on air. Out here, that's not nothing."},
    {"type": "line", "speaker": "MARU", "color": C_MARU,
     "text": "His men have this block pinned. Hold the transmitter and let the arrest air."},
    {"type": "line", "speaker": "MARU", "color": C_MARU,
     "text": "One question before you bleed for this building - who are you fighting for?"},
    {"type": "choice", "speaker": "BIRIBEL", "color": BIRIBEL_SPEAKER,
     "prompt": "The state, or the people inside it?",
     "options": [
        ("The state. It outlasts every man who wears it.",
         "Then hold the line. Order is all that's between this city and the pit."),
        ("The people. The state is just the tool we point.",
         "Good answer. Tools get pointed at the people too - remember that."),
     ]},
]

# Single-owner dialogue state (this module). Mutated in place, never rebound,
# so readers via `_m4_flow._m4_dlg` (systems/draw) always see current values -
# the same one-owner pattern m3 uses for _dialogue_*.
_m4_dlg = {"beats": [], "index": 0, "char_idx": 0, "timer": 0,
           "choice": 0, "slide": 0.0, "post_hold": 0, "active": False}


def _dlg_reset():
    _m4_dlg["beats"] = []
    _m4_dlg["index"] = 0
    _m4_dlg["char_idx"] = 0
    _m4_dlg["timer"] = 0
    _m4_dlg["choice"] = 0
    _m4_dlg["slide"] = 0.0
    _m4_dlg["post_hold"] = 0
    _m4_dlg["active"] = False


def _beat_text(beat):
    if beat.get("type") == "choice":
        return beat.get("prompt", "")
    return beat.get("text", "")


def _current_beat():
    beats = _m4_dlg["beats"]
    i = _m4_dlg["index"]
    return beats[i] if 0 <= i < len(beats) else None


def _line_fully_typed():
    beat = _current_beat()
    if beat is None:
        return True
    return _m4_dlg["char_idx"] >= len(_beat_text(beat))


def _play_type_tick(ch, idx):
    try:
        if ch in ".,;:!?" or idx % 3 == 0:
            audio.play("type_tick", volume=0.10)
    except Exception:
        pass


def _start_liaison_dialogue():
    """Open the Maru meet. Idempotent: never reopens once done or in progress."""
    if getattr(STATE, "m4_dialogue_done", False) or _m4_dlg["active"]:
        return
    _dlg_reset()
    _m4_dlg["beats"] = list(_dialogues.beats(
        "m4.liaison", _M4_LIAISON_BEATS,
        {"MARU": C_MARU, "BIRIBEL": BIRIBEL_SPEAKER}, typed=True))
    _m4_dlg["active"] = True
    STATE.m4_dialogue_active = True
    _sfx("radio_static", 0.35)


def _update_dialogue():
    """Per-frame typewriter tick (ported m3.interrog cadence)."""
    _m4_dlg["timer"] += 1
    beat = _current_beat()
    if beat is None:
        return
    full = _beat_text(beat)
    # Voice-over: once, on the beat's first frame. Maru is in the room -
    # clean voice, no radio filter.
    if _m4_dlg["timer"] == 1 and beat.get("type") != "choice":
        try:
            from audio import voice
            voice.play_line(beat.get("speaker", ""), beat.get("text", ""))
        except Exception:
            pass
    if _m4_dlg["char_idx"] < len(full):
        if _m4_dlg["post_hold"] > 0:
            _m4_dlg["post_hold"] -= 1
        elif _m4_dlg["timer"] % _type_interval() == 0:
            ch = full[_m4_dlg["char_idx"]]
            _m4_dlg["char_idx"] += 1
            _play_type_tick(ch, _m4_dlg["char_idx"])
            if ch in ".!?":
                _m4_dlg["post_hold"] = _TYPE_PAUSE_FULL
            elif ch in ",;:":
                _m4_dlg["post_hold"] = _TYPE_PAUSE_SOFT
    else:
        _m4_dlg["slide"] = min(1.0, _m4_dlg["slide"] + 0.08)


def _advance_beat():
    _m4_dlg["index"] += 1
    _m4_dlg["char_idx"] = 0
    _m4_dlg["timer"] = 0
    _m4_dlg["choice"] = 0
    _m4_dlg["slide"] = 0.0
    _m4_dlg["post_hold"] = 0
    if _m4_dlg["index"] >= len(_m4_dlg["beats"]):
        _finish_liaison_dialogue()


def _resolve_choice(chosen):
    """Record the tone, splice in Biribel's spoken follow-up, advance."""
    beat = _current_beat()
    if beat is None:
        return
    opts = beat.get("options", [])
    if not (0 <= chosen < len(opts)):
        return
    follow = opts[chosen][1]
    if not isinstance(getattr(STATE, "m4_tone", None), list):
        STATE.m4_tone = []
    STATE.m4_tone.append(chosen)
    # Insert Biribel's line right after the choice beat (m3 follow-up idiom).
    _m4_dlg["beats"].insert(_m4_dlg["index"] + 1, {
        "type": "line", "speaker": "BIRIBEL", "color": BIRIBEL_SPEAKER,
        "text": follow})
    _sfx("type_tick", 0.12)
    _advance_beat()


def _finish_liaison_dialogue():
    _m4_dlg["active"] = False
    STATE.m4_dialogue_active = False
    STATE.m4_dialogue_done = True
    STATE.mission4_stage = STAGE_MARU
    STATE.mission_phase = "m4_jammer"
    _set_objective("Install the jammer on the transmitter rack, east wall.")
    _radio("MARU: Jammer's on the east rack. Break their comms before they organize.",
           color=C_MARU, duration=420, mark="maru_jammer")


def _dlg_press(key):
    """One dialogue input. Enter/Space/E confirm; Up/Left & Down/Right move
    the choice highlight. A confirm on an un-typed line snaps the typewriter
    to full (m3 idiom); the next confirm advances."""
    if not _m4_dlg["active"]:
        return
    beat = _current_beat()
    if beat is None:
        return
    confirm = key in (pygame.K_RETURN, pygame.K_SPACE, pygame.K_KP_ENTER)
    if beat.get("type") == "choice":
        if not _line_fully_typed():
            if confirm:
                _m4_dlg["char_idx"] = len(_beat_text(beat))
            return
        opts = beat.get("options", [])
        if key in (pygame.K_UP, pygame.K_LEFT):
            _m4_dlg["choice"] = (_m4_dlg["choice"] - 1) % max(1, len(opts))
            _sfx("menu_click", 0.3)
        elif key in (pygame.K_DOWN, pygame.K_RIGHT):
            _m4_dlg["choice"] = (_m4_dlg["choice"] + 1) % max(1, len(opts))
            _sfx("menu_click", 0.3)
        elif confirm or key == pygame.K_e:
            _resolve_choice(_m4_dlg["choice"])
        return
    # line beat
    if confirm or key == pygame.K_e:
        if not _line_fully_typed():
            _m4_dlg["char_idx"] = len(_beat_text(beat))
        else:
            _advance_beat()


def handle_dialogue_event(event):
    """Keyboard router for the liaison beat (called from app.py while it is up)."""
    if event.type == pygame.KEYDOWN:
        _dlg_press(event.key)


# ─────────────────────────────────────────────
# The hold: diegetic arrest-on-air beat ladder (W4)
# ─────────────────────────────────────────────
# Biribel never sees Balaceanu. He only hears the regime eat itself while the
# transmitter stays live: Retardovici's order goes out on the general's own
# airwaves (PA mumble + his color), the loyalist comms curdle into confusion
# once the jammer is soup (radio_static + C_BALACEANU), then a stand-down and
# a retreat (footstep). Driven off STATE.m4_hold_timer so the arrest reads on
# schedule no matter how the wave director is going - the clock is the boss.
_M4_ARREST_BEATS = [
    (300, "arrest_open", C_RETARDOVICI, "pa_mumble",
     "PA: All units. By order of the Presidency, garrison command is... recalibrated."),
    (1350, "arrest_order", C_RETARDOVICI, "pa_mumble",
     "PA: General Balaceanu is relieved of command and arrested. Escort him out."),
    (1800, "arrest_steer", C_VASILE, "radio_static",
     "VASILE: You don't need to see him. Trust me."),
    (2250, "arrest_confusion", C_BALACEANU, "radio_static",
     "LOYALIST COMMS (JAMMED): -say again- who gave the or- our channel's on every set-"),
    (3150, "arrest_standdown", C_SYSTEM, "radio_static",
     "SYSTEM: Guns down. That's the President on the wire. The General's in cuffs."),
    (4050, "arrest_retreat", C_BALACEANU, "footstep",
     "LOYALIST COMMS: Fall back! Nobody dies for a man already in a cell. Break off!"),
]


# RPE6 P8: ladder players, built lazily from timeline data (cached).
_ladder_players: dict = {}


def _ladder_player(kind: str):
    if kind not in _ladder_players:
        _ladder_players[kind] = _TimelinePlayer(_timelines.timeline(f"m4.{kind}_beats"))
    return _ladder_players[kind]


def _arrest_beats():
    t = getattr(STATE, "m4_hold_timer", 0)
    if _timelines.use_legacy():
        for frame, mark, color, sfx, line in _M4_ARREST_BEATS:
            if t == frame:
                _radio(line, color=color, duration=470, mark=mark)
                _sfx(sfx, 0.42)
    else:
        for clip in _ladder_player("arrest").events_between(t - 1, t):
            _radio(clip["text"], color=tuple(clip["color"]),
                   duration=clip["duration"], mark=clip["name"])
            _sfx(clip["sfx"], 0.42)


# ─────────────────────────────────────────────
# Mission start / checkpoints
# ─────────────────────────────────────────────
def start_m4(preserve_timer=False):
    """Called by game_core/acaristan to begin Mission 4 gameplay."""
    STATE.reset()
    STATE.active_mission = MISSION4_KEY
    STATE.active_mission_id = MISSION4_ID
    STATE.active_mission_title = MISSION4_TITLE
    STATE.active_mission_operation = "THE CAPITAL - 48H CURFEW"
    STATE.active_mission_outcome = "The Vostral is on air  ·  Balaceanu is cornered  ·  The capital burns"
    STATE.active_mission_quote_attr = "Retardovici, on every channel:"
    STATE.active_mission_quote = '"Citizens. Order will be maintained. Even if I have to maintain it alone."'

    # Defensive double-reset (m3 idiom): STATE.reset() already cleared the
    # flags, but checkpoint/dev entry paths must never inherit a request.
    STATE.request_mission4_ending = False
    STATE.request_death_screen = False
    STATE.player_dead = False
    STATE.mission4_stage = STAGE_AFTERMATH
    STATE.mission_phase = "m4_aftermath"
    STATE.m4_chaos_timer = 0
    STATE.m4_liaison_reached = False
    STATE.m4_cache_taken = False
    STATE.m4_maru_joined = False
    STATE.m4_dialogue_active = False
    STATE.m4_dialogue_done = False
    STATE.m4_tone = []
    STATE.m4_jammer_installed = False
    STATE.m4_siege_active = False
    STATE.m4_hold_timer = 0
    STATE.m4_broadcast_held = False
    STATE.mission4_station_checkpoint_reached = False
    STATE.mission4_tower_checkpoint_reached = False
    STATE.m4_marks = set()
    _siege_reset()  # W4 siege counters + telegraph beams (single owner: world)

    STATE.show_minimap = True
    STATE.minimap = MiniMap(_m4_maps.MISSION4_MAP, palette="m4")
    # Seed the curfew-street rain (shared sprite pass; station interior stays
    # dry, but seeding here once keeps STATE.rain_drops populated on boot).
    STATE.rain_drops = [
        (_rng_legacy.randint(0, WIDTH),
         _rng_legacy.randint(SCENE_TOP, SCENE_BOT),
         _rng_legacy.randint(10, 20))
        for _ in range(200)
    ]
    STATE.mission_start_time = (
        STATE.mission_start_time if (preserve_timer and STATE.mission_start_time)
        else _now_ms()
    )
    STATE.mission_end_time = 0
    STATE.hostiles_killed = 0
    STATE.shots_fired = 0
    STATE.shots_hit = 0

    # Biribel and Vasile regroup with what KRAP still trusts: the K-9 SMG
    # carried out of the Vostral broadcast (m3's escape loadout).
    STATE.k9_unlocked = True
    STATE.current_weapon = "k9_smg"
    STATE.player_disarmed = False

    try:
        from core.save_system import set_slot_progress
        set_slot_progress("m4")
    except Exception:
        pass

    _m4_maps._radio_marks = set()
    _m4_maps._last_keys = None
    # Reset the ambient/story clocks (module-local, single owner: this file).
    _M4_AMB["gun"] = 240
    _M4_AMB["static"] = 460
    _M4_AMB["pa"] = 760
    _dlg_reset()  # W3 liaison dialogue state (module-local, single owner)

    _build_m4_world()
    _snap_camera_safe()

    _set_objective("Regroup with Vasile - pick up the KRAP comms cache (E) on the boulevard, south of here.")
    _radio("VASILE: Two days of curfew, the city's coming apart. Meet me at the cache.",
           color=C_VASILE, duration=380, mark="start_vasile")
    return STATE.player


def start_mission4_station_checkpoint(preserve_timer=False):
    """Resume inside the radio station (liaison meet).

    W3 owns the meet content; W1 only needs the dev boot + the resume
    target for the restart ladder.
    """
    start_m4(preserve_timer=preserve_timer)

    _m4_maps.MISSION4_MAP = _m4_maps.MISSION4_STATION_MAP
    STATE.show_minimap = True
    STATE.minimap = MiniMap(_m4_maps.MISSION4_MAP, palette="m4")
    _build_station_world()
    _snap_camera_safe()

    STATE.mission4_stage = STAGE_KRAP_STATUS
    STATE.mission_phase = "m4_krap_status"
    STATE.mission4_station_checkpoint_reached = True

    _set_objective("Talk to Maru at the transmitter hall (north).")
    _radio("VASILE: Station's ours for now. Find Maru in the transmitter hall.",
           color=C_VASILE, duration=340, mark="station_checkpoint")
    return STATE.player


def start_mission4_tower_checkpoint(preserve_timer=False):
    """Resume at the transmitter hold (siege checkpoint).

    W4 replaces the placeholder objective with the wave director; the
    hold clock itself already ticks in _update_stage so the chain is
    testable end to end from Slice 0.
    """
    start_mission4_station_checkpoint(preserve_timer=preserve_timer)

    STATE.mission4_stage = STAGE_COMMIT
    STATE.mission_phase = "m4_commit"
    STATE.m4_siege_active = True
    STATE.mission4_tower_checkpoint_reached = True
    STATE.m4_hold_timer = 0
    _arm_m4_allies()

    _set_objective("Hold the transmitter until the order airs.")
    _radio("SYSTEM: The transmitter is live. Do not let it go dark.",
           color=C_SYSTEM, duration=340, mark="tower_checkpoint")
    return STATE.player


# ─────────────────────────────────────────────
# Stage ladder
# ─────────────────────────────────────────────
def _enter_station():
    """Street -> station interior handoff (the door tile owns the swap)."""
    _m4_maps.MISSION4_MAP = _m4_maps.MISSION4_STATION_MAP
    STATE.show_minimap = True
    STATE.minimap = MiniMap(_m4_maps.MISSION4_MAP, palette="m4")
    _build_station_world()
    if STATE.player is not None:
        STATE.player.hp = STATE.player.max_hp
        STATE.player.angle = -math.pi / 2
    _snap_camera_safe()

    STATE.mission4_stage = STAGE_KRAP_STATUS
    STATE.mission_phase = "m4_krap_status"
    STATE.mission4_station_checkpoint_reached = True
    STATE.m4_liaison_reached = True

    _set_objective("Cross to the transmitter hall - Maru is waiting inside.")
    _radio("VASILE: Door's clear. Maru's inside - watch the gallery.",
           color=C_VASILE, duration=380, mark="door_enter")


def _update_stage(keys):
    """Phase dispatcher (mirrors m3.flow._update_stage).

    The station ladder (W3): proximity to the liaison (Maru) opens the
    typewriter dialogue; completing it hands off to STAGE_MARU, where the
    jammer-install (handle_interact) is the gate to the STAGE_COMMIT hold
    clock (W4 owns the wave director around that clock)."""
    # Dialogue owns the frame while it's up (typewriter tick, no other logic).
    if getattr(STATE, "m4_dialogue_active", False):
        _update_dialogue()
        return

    stage = getattr(STATE, "mission4_stage", STAGE_AFTERMATH)

    if stage == STAGE_AFTERMATH:
        _aftermath_ambient()
        if not getattr(STATE, "m4_cache_taken", False):
            # The cache is a real pickup (E), not a proximity flag: the street
            # stage cannot be skipped by sprinting past the drop.
            if _near(_vasile_cache_pos(), radius=90):
                _radio("VASILE: That's the drop - the KRAP comms cache. Grab it (E).",
                       color=C_VASILE, duration=380, mark="cache_prompt")
        elif "aftermath_vasile" not in _m4_maps._radio_marks:
            _radio("VASILE: That file reached every screen. Head east - hold the station.",
                   color=C_VASILE, duration=430, mark="aftermath_vasile")
            _set_objective("Reach the radio station door - east end of the boulevard.")
            STATE.m4_liaison_reached = False
        if _near(_street_door_pos(), radius=70):
            if getattr(STATE, "m4_cache_taken", False):
                _enter_station()
            else:
                _radio("VASILE: Not without the cache, Biribel. Grab it first.",
                       color=C_VASILE, duration=300, mark="door_without_cache")
        return

    if stage == STAGE_KRAP_STATUS:
        # Walk to Maru; the dialogue locks movement. Finishing it moves on.
        if not getattr(STATE, "m4_dialogue_done", False):
            if _near(_liaison_pos(), radius=95):
                _start_liaison_dialogue()
        return

    if stage == STAGE_MARU:
        # Jammer install (handle_interact) is the gate. Prompt once on
        # proximity (dedup via _radio_marks); the interact does the rest.
        if (not getattr(STATE, "m4_jammer_installed", False)
                and "jammer_prompt" not in _m4_maps._radio_marks
                and _near(_jammer_pos(), radius=95)):
            _radio("MARU: That's the rack. Plant it (E) and their comms go dark.",
                   color=C_MARU, duration=300, mark="jammer_prompt")
        return

    if stage == STAGE_COMMIT:
        # W4 siege: the wave director + the diegetic arrest-on-air ladder both
        # ride the same hold clock. The clock is timer-driven and independent
        # of wave state (m3 exfil-door lesson) - the arrest finishes whether or
        # not a single loyalist is left standing.
        STATE.m4_hold_timer = getattr(STATE, "m4_hold_timer", 0) + 1
        _run_siege_director()
        _arrest_beats()
        if STATE.m4_hold_timer >= int(M4_HOLD_SECONDS * 60):
            _complete_m4()
        return

    # STAGE_INTRO / STAGE_DONE: no stage logic.
    return


def _take_cache():
    """Pick up Vasile's comms cache (E on the drop). Arms the door objective."""
    STATE.m4_cache_taken = True
    _sfx("pickup", 0.5)
    if STATE.player is not None:
        STATE.floating_texts.append(
            [STATE.player.rect.centerx, STATE.player.rect.centery - 42,
             "+ KRAP COMMS CACHE", (140, 200, 150), 90])
    _radio("VASILE: That file reached every screen. Head east - hold the station.",
           color=C_VASILE, duration=430, mark="aftermath_vasile")
    _set_objective("Reach the radio station door - east end of the boulevard.")
    STATE.m4_liaison_reached = False


def _install_jammer():
    """Plant the jammer -> loyalist comms go dark -> the siege (STAGE_COMMIT)."""
    STATE.m4_jammer_installed = True
    _sfx("rifle_handle", 0.5)
    _sfx("terminal_glitch", 0.5)
    _radio("MARU: Jammer's live. Their comms are soup now. Get to the "
           "transmitter and hold it - when Retardovici gives the order, it "
           "has to reach every set in the country.",
           color=C_MARU, duration=440, mark="jammer_live")
    STATE.mission4_stage = STAGE_COMMIT
    STATE.mission_phase = "m4_commit"
    STATE.m4_siege_active = True
    STATE.mission4_tower_checkpoint_reached = True
    STATE.m4_hold_timer = 0
    _arm_m4_allies()
    _set_objective("Hold the transmitter until the order airs.")
    _radio("SYSTEM: All units - the studio transmitter is live. "
           "Do not let it go dark.",
           color=C_SYSTEM, duration=340, mark="commit_start")


def _complete_m4():
    """Signal mission completion → app.py plays mission4_ending_shots."""
    if getattr(STATE, "request_mission4_ending", False):
        return  # idempotent guard
    STATE.mission4_stage = STAGE_DONE
    STATE.m4_broadcast_held = True
    STATE.mission_end_time = _now_ms()
    STATE.request_mission4_ending = True
    try:
        from core import config as _config
        _config.audio.play("terminal_glitch", volume=0.55)
    except Exception:
        pass


def handle_interact():
    """E-key dispatch: take the cache, advance the liaison dialogue, or plant
    the jammer."""
    if getattr(STATE, "m4_dialogue_active", False):
        _dlg_press(pygame.K_e)
        return
    stage = getattr(STATE, "mission4_stage", STAGE_AFTERMATH)
    if stage == STAGE_AFTERMATH and not getattr(STATE, "m4_cache_taken", False):
        if _near(_vasile_cache_pos(), radius=90):
            _take_cache()
        return
    if stage == STAGE_MARU and not getattr(STATE, "m4_jammer_installed", False):
        if _near(_jammer_pos(), radius=95):
            _install_jammer()
    return
