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
    M4_SIEGE_FRAMES, M4_WAVE_GRACE, M4_JAMMER_COUNTDOWN, M4_SUPPLY_START,
    STAGE_INTRO, STAGE_ESCORT, STAGE_FORTIFY, STAGE_SIEGE, STAGE_DONE,
    STAGE_AFTERMATH, TRANSMITTER_TILE, VASILE_STATION_TILE, RESPAWN_TILE,
    C_SYSTEM, C_VASILE, C_MARU, C_VOLKOV, C_RETARDOVICI, C_BALACEANU,
    BIRIBEL_SPEAKER, M4_DOOR_FADE_OUT, M4_DOOR_FADE_HOLD, M4_DOOR_FADE_IN,
)
from missions.m4.world import (
    _build_m4_world, _build_station_world, _movement_locked, _near, _player_pos,
    _radio,
    _set_objective, _street_door_pos, _tile_world,
    _liaison_pos, _jammer_pos, _siege_reset, _ally,
    _arm_m4_allies, _tone_choice,
)
from missions.m4 import escort as _m4_escort
from missions.m4 import fortify as _m4_fortify
from missions.m4 import siege as _m4_siege


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

# Street story beats: the opening read fires once after the grace window,
# then the rest key off WHERE Biribel is. The old frame table fired all three
# lines at 4/10/16 seconds, while the player was still in the north blocks,
# and left the rest of the crossing silent. maps.zone_at() already owns the
# named districts (M4_ZONE_WORLD_RECTS) - this is its caller.
# The opening read is not geography - it must play even if the player sprints
# out of Old Town before the beat is due.
_M4_OPEN_BEAT = ("beat_loyalists",
                 "VASILE: This isn't a crackdown - it's a collapse. Stay off the boulevard.",
                 C_VASILE)
_M4_ZONE_BEATS = {
    "boulevard": ("beat_volkov",
                  "INTERCEPT: North border logged one vehicle at first light. Volkov ran.",
                  C_VOLKOV),
    "station_cordon": ("beat_retardovici",
                       "PA: Citizens. Curfew holds. The Presidency has this under control.",
                       C_RETARDOVICI),
}
_M4_ZONE_GRACE_FRAMES = 400   # let the opening Vasile line breathe
_M4_OPEN_SEEN = [False]       # list: mutated in place (single owner)
_M4_ZONE_SEEN = set()         # single owner: this module (cleared by start_m4)


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

    # Zone-triggered story beats: crossing into a named district is the
    # trigger, so the walk keeps talking to the player the whole way across
    # the map instead of dumping all three lines in the first 16 seconds
    # (objective untouched, so the stage ladder stays deterministic).
    if t >= _M4_ZONE_GRACE_FRAMES:
        if not _M4_OPEN_SEEN[0]:
            _M4_OPEN_SEEN[0] = True
            mark, line, color = _M4_OPEN_BEAT
            _radio(line, color=color, duration=440, mark=mark)
        zone = _m4_maps.zone_at(_player_pos())
        if zone in _M4_ZONE_BEATS and zone not in _M4_ZONE_SEEN:
            _M4_ZONE_SEEN.add(zone)
            mark, line, color = _M4_ZONE_BEATS[zone]
            _radio(line, color=color, duration=440, mark=mark)

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
    {"type": "line", "speaker": "BIRIBEL", "color": BIRIBEL_SPEAKER,
     "text": "Vasile's name was on the chain. There's an explanation."},
    {"type": "line", "speaker": "MARU", "color": C_MARU,
     "text": "There always is."},
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
    try:
        from audio import voice
        voice.cut()          # skipping the box skips its line too
    except Exception:
        pass
    _m4_dlg["index"] += 1
    _m4_dlg["char_idx"] = 0
    _m4_dlg["timer"] = 0
    _m4_dlg["choice"] = 0
    _m4_dlg["slide"] = 0.0
    _m4_dlg["post_hold"] = 0
    if _m4_dlg["index"] >= len(_m4_dlg["beats"]):
        _finish_liaison_dialogue()


def _resolve_choice(chosen):
    """Record the tone, splice in Maru's reply, advance."""
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
    # Insert Maru's reply right after the choice beat (m3 follow-up idiom;
    # the option labels are Biribel's answers, the follow text is Maru
    # answering them - VO_076/VO_077 are "MARU (reply)" takes).
    _m4_dlg["beats"].insert(_m4_dlg["index"] + 1, {
        "type": "line", "speaker": "MARU", "color": C_MARU,
        "text": follow})
    _sfx("type_tick", 0.12)
    _advance_beat()


def _maru_not_in_room():
    """Vasile's 'Maru is inside' lines stop being true once you stand with him."""
    return not _near(_liaison_pos(), radius=200)


_SQUAD_LINES = (
    "MARU: Two of Balaceanu's own walked out on him. Soldiers - they'll hold a door.",
    "MARU: MAG sent who it had. Four of them, no armour. Keep them alive.",
)


def _finish_liaison_dialogue():
    """The meet is done: Maru arms, the tone's squad walks in, the jammer opens."""
    _m4_dlg["active"] = False
    STATE.m4_dialogue_active = False
    STATE.m4_dialogue_done = True
    _arm_m4_allies()
    _radio(_SQUAD_LINES[_tone_choice()], color=C_MARU, duration=420, mark="maru_squad")
    _fortify_objective()


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
# The arrest on air: diegetic beat ladder over the siege
# ─────────────────────────────────────────────
# Biribel never sees Balaceanu. He only hears the regime eat itself while the
# transmitter stays live: Retardovici's order goes out on the general's own
# airwaves (PA mumble + his color), the loyalist comms curdle into confusion
# once the jammer is soup (radio_static + C_BALACEANU), then a stand-down and
# a retreat (footstep). Frames are siege-clock frames (STATE.m4_siege_t),
# spread over the five waves: the order airs early in wave 1, Vasile's steer
# and the jammed comms land in the wave 3 lull, the stand-down in wave 5 and
# the retreat sends the last of them out before the clock runs down.
_M4_ARREST_BEATS = [
    (600, "arrest_open", C_RETARDOVICI, "pa_mumble",
     "PA: All units. By order of the Presidency, garrison command is... recalibrated."),
    (11000, "arrest_order", C_RETARDOVICI, "pa_mumble",
     "PA: General Balaceanu is relieved of command and arrested. Escort him out."),
    (11500, "arrest_steer", C_VASILE, "radio_static",
     "VASILE: You don't need to see him. Trust me."),
    (19800, "arrest_confusion", C_BALACEANU, "radio_static",
     "LOYALIST COMMS (JAMMED): -say again- who gave the or- our channel's on every set-"),
    (26400, "arrest_standdown", C_SYSTEM, "radio_static",
     "SYSTEM: Guns down. That's the President on the wire. They're taking the General."),
    (28200, "arrest_retreat", C_BALACEANU, "footstep",
     "LOYALIST COMMS: Fall back! Nobody dies for a man already in a cell. Break off!"),
]


# RPE6 P8: ladder players, built lazily from timeline data (cached).
_ladder_players: dict = {}


def _ladder_player(kind: str):
    if kind not in _ladder_players:
        _ladder_players[kind] = _TimelinePlayer(_timelines.timeline(f"m4.{kind}_beats"))
    return _ladder_players[kind]


def _arrest_beats():
    """Air the beat ladder off the siege clock. The retreat beat also sends
    the loyalists out (siege.stand_down)."""
    t = getattr(STATE, "m4_siege_t", 0)
    fired = []
    if _timelines.use_legacy():
        for frame, mark, color, sfx, line in _M4_ARREST_BEATS:
            if t == frame:
                _radio(line, color=color, duration=470, mark=mark)
                _sfx(sfx, 0.42)
                fired.append(mark)
    else:
        for clip in _ladder_player("arrest").events_between(t - 1, t):
            _radio(clip["text"], color=tuple(clip["color"]),
                   duration=clip["duration"], mark=clip["name"])
            _sfx(clip["sfx"], 0.42)
            fired.append(clip["name"])
    if "arrest_retreat" in fired:
        _m4_siege.stand_down()


# ─────────────────────────────────────────────
# Holds (revive, build, repair) and the fail countdown
# ─────────────────────────────────────────────
def _update_holds(keys):
    """Runs before the player update so a hold locks movement this frame."""
    STATE.m4_work_lock = False
    _m4_escort.update_vasile_down(keys)
    if getattr(STATE, "m4_reviving", False):
        STATE.m4_hold_ui = None
        return
    _m4_fortify.update_holds(keys)


def _update_fail():
    """Vasile dead or the rack lost: a beat, then the death screen."""
    if not getattr(STATE, "m4_fail_reason", None):
        return False
    STATE.m4_fail_timer = getattr(STATE, "m4_fail_timer", 0) - 1
    if STATE.m4_fail_timer == 120:
        if STATE.m4_fail_reason == "rack":
            _radio("SYSTEM: Carrier lost. The rack is theirs.", color=C_SYSTEM,
                   duration=300, mark="fail_rack")
        _sfx("radio_static", 0.5)
    if STATE.m4_fail_timer <= 0 and not getattr(STATE, "request_death_screen", False):
        STATE.request_death_screen = True
    return True


# ─────────────────────────────────────────────
# Mission start / checkpoints
# ─────────────────────────────────────────────
def start_m4(preserve_timer=False, preserve_tone=False, keep_snaps=False):
    """Called by game_core/acaristan to begin Mission 4 gameplay.

    preserve_tone keeps STATE.m4_tone across a checkpoint restart: the liaison
    answer picks the squad, so losing it on a wipe would silently swap it.
    keep_snaps keeps the wave snapshots (the checkpoint wrappers restore from
    them); a fresh start clears them.
    """
    tone = list(getattr(STATE, "m4_tone", []) or []) if preserve_tone else []
    STATE.reset()
    STATE.active_mission = MISSION4_KEY
    STATE.active_mission_id = MISSION4_ID
    STATE.active_mission_title = MISSION4_TITLE
    STATE.active_mission_operation = "THE CAPITAL - 48H CURFEW"
    STATE.active_mission_outcome = "The Vostral is on air  ·  Balaceanu is cornered  ·  The capital burns"
    STATE.active_mission_quote_attr = "Biribel, on the studio roof at dawn:"
    STATE.active_mission_quote = '"Nobody asked us to do this. First time in my life - that\'s how it\'s done right."'

    # Defensive double-reset (m3 idiom): STATE.reset() already cleared the
    # flags, but checkpoint/dev entry paths must never inherit a request.
    STATE.request_mission4_ending = False
    STATE.request_death_screen = False
    STATE.player_dead = False
    STATE.mission4_stage = STAGE_ESCORT
    STATE.mission_phase = "m4_escort"
    STATE.m4_door_fade = 0
    STATE.m4_mag_drops = 0
    STATE.m4_bandage_drops = 0
    STATE.m4_regen_wait = 0
    STATE.m4_last_hp = 0
    STATE.m4_rack_ammo_t = 0
    STATE.k9_spare_mags = max(getattr(STATE, "k9_spare_mags", 0), 4)
    STATE.spare_mags = max(getattr(STATE, "spare_mags", 0), 3)
    STATE.m4_chaos_timer = 0
    STATE.m4_liaison_reached = False
    # Vasile carries the cache from the first frame: it is the supply pool.
    STATE.m4_cache_taken = True
    STATE.m4_cache_carried = True
    STATE.m4_supply = M4_SUPPLY_START
    STATE.m4_vasile_downs = 0
    STATE.m4_reviving = False
    STATE.m4_work_lock = False
    STATE.m4_hold_ui = None
    STATE.m4_fail_reason = None
    STATE.m4_fail_timer = 0
    STATE.m4_maru_joined = False
    STATE.m4_dialogue_active = False
    STATE.m4_dialogue_done = False
    STATE.m4_tone = tone
    STATE.m4_jammer_installed = False
    STATE.m4_siege_active = False
    STATE.m4_siege_t = -M4_JAMMER_COUNTDOWN
    STATE.m4_hold_timer = 0
    STATE.m4_broadcast_held = False
    STATE.m4_apc = None
    STATE.mission4_station_checkpoint_reached = False
    STATE.mission4_tower_checkpoint_reached = False
    STATE.m4_marks = set()
    _siege_reset()  # telegraph beams (single owner: world)
    _m4_siege.reset_runtime()
    _m4_fortify.reset()
    if not keep_snaps:
        _m4_siege.clear_snapshots()

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
    _M4_ZONE_SEEN.clear()
    _M4_OPEN_SEEN[0] = False
    _dlg_reset()  # liaison dialogue state (module-local, single owner)

    _m4_maps.MISSION4_MAP = _m4_maps.MISSION4_STREET_MAP
    _build_m4_world()
    _snap_camera_safe()

    _set_objective("Get Vasile and the cache to the radio station - east end of the boulevard.")
    if getattr(STATE, "_skip_m4_intro_radio", False):
        STATE._skip_m4_intro_radio = False
    else:
        _radio("VASILE: Two days of curfew, the city's coming apart. I've got the cache - stay close.",
               color=C_VASILE, duration=380, mark="start_vasile")
    return STATE.player


def _station_world(vasile_hp=None):
    _m4_maps.MISSION4_MAP = _m4_maps.MISSION4_STATION_MAP
    STATE.show_minimap = True
    STATE.minimap = MiniMap(_m4_maps.MISSION4_MAP, palette="m4")
    _build_station_world()
    if vasile_hp is not None:
        v = _ally("VASILE")
        if v is not None:
            v["hp"] = max(1, int(vasile_hp))
    _snap_camera_safe()
    STATE.mission4_stage = STAGE_FORTIFY
    STATE.mission_phase = "m4_fortify"
    STATE.mission4_station_checkpoint_reached = True
    STATE.m4_liaison_reached = True


def _fortify_objective():
    if getattr(STATE, "m4_dialogue_done", False):
        _set_objective("Barricade the doors and windows (hold E). Plant the jammer on the rack when ready.")
    else:
        _set_objective("Barricade the doors and windows (hold E), then talk to Maru in the entry hall.")


def start_mission4_station_checkpoint(preserve_timer=False, keep_snaps=True):
    """Resume inside the radio station at the top of the fortify stage."""
    snap = _m4_siege.SNAPS.get("station")
    start_m4(preserve_timer=preserve_timer, preserve_tone=True, keep_snaps=keep_snaps)
    _station_world(vasile_hp=snap["vasile_hp"] if snap else None)
    if snap:
        STATE.m4_supply = snap["supply"]
        STATE.m4_vasile_downs = snap["downs"]
    _fortify_objective()
    _radio("VASILE: Station's ours for now. Board it up - Maru's in the entry hall.",
           color=C_VASILE, duration=340, mark="station_checkpoint",
           valid=_maru_not_in_room)
    return STATE.player


def start_mission4_tower_checkpoint(preserve_timer=False):
    """Resume the siege at the latest wave snapshot (5 s before that wave).

    With no snapshot (dev boot) the meet is taken as done, the squad armed and
    the clock put just before wave 1."""
    snap = _m4_siege.latest()
    start_mission4_station_checkpoint(preserve_timer=preserve_timer)
    STATE.m4_dialogue_done = True
    STATE.m4_jammer_installed = True
    STATE.m4_siege_active = True
    STATE.mission4_tower_checkpoint_reached = True
    STATE.mission4_stage = STAGE_SIEGE
    STATE.mission_phase = "m4_siege"
    if snap:
        _m4_siege.restore(snap)
        _set_objective("Hold the station. Keep them off the transmitter rack.")
        _radio("SYSTEM: Wave %d inbound. Hold the rack." % snap["wave"], color=C_SYSTEM,
               duration=300, mark="tower_checkpoint")
    else:
        if not STATE.m4_tone:
            STATE.m4_tone = [0]
        _arm_m4_allies()
        STATE.m4_siege_t = -M4_WAVE_GRACE
        _set_objective("Hold the station. Keep them off the transmitter rack.")
        _radio("SYSTEM: The transmitter is live. Do not let it go dark.",
               color=C_SYSTEM, duration=340, mark="tower_checkpoint")
        v = _ally("VASILE")
        if v is not None:
            v["x"], v["y"] = _tile_world(*VASILE_STATION_TILE)
            v["path"], v["path_goal"] = [], None
    # A wave restart puts Biribel back at the rack, inside the barricades.
    if STATE.player is not None:
        STATE.player.rect.center = _tile_world(*RESPAWN_TILE)
    return STATE.player


# ─────────────────────────────────────────────
# Stage ladder
# ─────────────────────────────────────────────
def _enter_station():
    """Street -> station interior handoff (the door tile owns the swap).
    Vasile's hp and his one down carry over, and so does the supply."""
    v = _ally("VASILE")
    vasile_hp = v["hp"] if v is not None else None
    _m4_siege.SNAPS["station"] = {"supply": STATE.m4_supply, "downs": STATE.m4_vasile_downs,
                                  "vasile_hp": vasile_hp}
    _station_world(vasile_hp=vasile_hp)
    if STATE.player is not None:
        STATE.player.hp = STATE.player.max_hp
        STATE.player.angle = -math.pi / 2
    _fortify_objective()
    _radio("VASILE: We're in. %d loads of supply - spend it on the doors before they come."
           % STATE.m4_supply, color=C_VASILE, duration=420, mark="door_enter")


def _update_street():
    _aftermath_ambient()
    v = _m4_escort.vasile()
    if v is not None and v.get("downed", 0) > 0:
        _set_objective("Vasile is down - hold E over him.")
    elif "street_objective" not in _m4_maps._radio_marks:
        _m4_maps._radio_marks.add("street_objective")
        _set_objective("Get Vasile and the cache to the radio station - east end of the boulevard.")
    if _near(_street_door_pos(), radius=70):
        if _m4_escort.vasile_at_door():
            if not getattr(STATE, "m4_door_fade", 0):
                STATE.m4_door_fade = 1
                _sfx("door_open", 0.6)
        else:
            _radio("BIRIBEL: Wait for Vasile - the door stays shut without him.",
                   color=BIRIBEL_SPEAKER, duration=260, mark="door_wait")


def _update_fortify():
    if not getattr(STATE, "m4_dialogue_done", False):
        ready = _m4_fortify.built_count() >= 1 or _near(_tx_pos(), radius=260)
        if _near(_liaison_pos(), radius=95):
            if ready:
                _start_liaison_dialogue()
            else:
                _radio("MARU: Doors first, talk later. Board something up and come back.",
                       color=C_MARU, duration=300, mark="maru_doors_first",
                       valid=lambda: _m4_fortify.built_count() < 1)
        return
    if (not getattr(STATE, "m4_jammer_installed", False)
            and "jammer_prompt" not in _m4_maps._radio_marks
            and _near(_jammer_pos(), radius=95)):
        _radio("MARU: That's the rack. Plant it (E) when the doors are done - "
               "it starts the clock.", color=C_MARU, duration=320, mark="jammer_prompt")


def _update_siege():
    t = _m4_siege.update()
    _arrest_beats()
    if t >= M4_SIEGE_FRAMES:
        _m4_siege.player_line_done()
        _complete_m4()


def _update_stage(keys):
    """Phase dispatcher: escort (street), fortify (station), siege."""
    if _update_fail():
        return
    # Dialogue owns the frame while it's up (typewriter tick, no other logic).
    if getattr(STATE, "m4_dialogue_active", False):
        _update_dialogue()
        return
    fade = getattr(STATE, "m4_door_fade", 0)
    if fade:
        # Street door: fade to black, swap to the station at full black,
        # hold a beat, fade back in on the entry hall.
        STATE.m4_door_fade = fade + 1
        if fade == M4_DOOR_FADE_OUT:
            _enter_station()
        elif fade >= M4_DOOR_FADE_OUT + M4_DOOR_FADE_HOLD + M4_DOOR_FADE_IN:
            STATE.m4_door_fade = 0
        if fade <= M4_DOOR_FADE_OUT:
            return
    stage = getattr(STATE, "mission4_stage", STAGE_ESCORT)
    if stage == STAGE_ESCORT:
        _update_street()
    elif stage == STAGE_FORTIFY:
        _update_fortify()
    elif stage == STAGE_SIEGE:
        _update_siege()


def _install_jammer():
    """Plant the jammer -> loyalist comms go dark -> the 10 s countdown."""
    STATE.m4_jammer_installed = True
    _sfx("rifle_handle", 0.5)
    _sfx("terminal_glitch", 0.5)
    _radio("MARU: Jammer's live. Their comms are soup now. Hold this building - "
           "when Retardovici gives the order, it has to reach every set in the country.",
           color=C_MARU, duration=440, mark="jammer_live")
    STATE.mission4_stage = STAGE_SIEGE
    STATE.mission_phase = "m4_siege"
    STATE.m4_siege_active = True
    STATE.mission4_tower_checkpoint_reached = True
    STATE.m4_siege_t = -M4_JAMMER_COUNTDOWN
    _m4_siege.reset_runtime()
    _set_objective("Hold the station. Keep them off the transmitter rack.")


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
    """E-key dispatch: advance the liaison dialogue or plant the jammer.
    Holds (revive, build, repair) read the held key in _update_holds."""
    if getattr(STATE, "m4_dialogue_active", False):
        _dlg_press(pygame.K_e)
        return
    stage = getattr(STATE, "mission4_stage", STAGE_ESCORT)
    if (stage == STAGE_FORTIFY and getattr(STATE, "m4_dialogue_done", False)
            and not getattr(STATE, "m4_jammer_installed", False)
            and _near(_jammer_pos(), radius=95)):
        _install_jammer()
