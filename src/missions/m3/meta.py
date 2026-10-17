"""Split from mission3.py - see mission3.py (shim) for the map."""
"""Mission 3: The Vostral - dialogue-driven cold open into action.

This is the third campaign mission, picking up 3 days after Mission 2's
Route 12 frame-up. Biribel wakes in an IPA black-site cell (the
"Stabilization Center") facing Prime Minister Balaceanu's long-promised
vendetta. The mission's spine is the Vostral - the buried rumor that
Balaceanu's decorated military career is fabricated. The only copy of
the service record that can prove it is held in the regime's own
Archives, so the engine of the mission is: break out of the cell, reach
the Archives, steal the file, and get it onto a live state broadcast
before Balaceanu finishes his 22:00 address pinning Route 12 on Biribel
personally.

Story posture (per the project bible): KRAP is STILL an organization -
disavowed, under siege, fighting for its survival and credibility. So
this is not Vasile-as-lone-wolf feeding floor plans out of guilt; KRAP
mobilizes as a resistance. Vasile brings real assets (an off-book
extraction element, a stolen IPA comms relay). The trust tension is
organizational, not personal.

This module keeps the existing game integration intact:
    - game_core.start_mission3()
    - game_core.game_update()/game_draw() routing (MISSION3 is checked
      BEFORE MISSION2 - see game_core.game_update)
    - acaristan.py Mission 3 intro and ending cutscenes (shot-lists
      exposed as module-level names below)
    - save as MISSION_3
    - dev command: python acaristan.py --dev-mission3

Scaffolding note: acaristan.py already routes ALL Mission 3 input
through mission3.handle_event(event) (arrow keys to pick choices,
ENTER to confirm) - this was purpose-built for the dialogue-driven
interrogation cold open that is Phase 1. Action phases (STAGE_BREAKOUT
onward) later relax that gate in acaristan.py so normal mouse-shoot
input falls through.
"""

import math
import time

import pygame

import core.config  # noqa: F401  boot side effect (A-001/B-007); removed in P4-1
from entities.art_cache import get_blood_decal, get_fullscreen_overlay, get_panel_bg
from core.state import STATE
from entities.player import Player, resolve_melee
from entities.enemy_ai import Enemy, enemy_hear_shot, _astar
from ui.hud import MiniMap, draw_objective_panel, draw_pinned_radio
from missions.m1 import _draw_molotov_icon
from fx import effects
import cutscenes
# RPE6 A-003: M3 owns these take modules; importing them registers their scene ids
# (core.cutscene_registry) before any M3 shot can be dispatched.
from cutscenes import m3cell, m3ops, m3ko, m3broadcast, m3ending, chair  # noqa: F401
from core.camera import update_camera, reset_camera_state, draw_bullets, collide_bullet_walls
from entities.weapons import _wall_blocks_line
from core import config as _config
audio = _config.audio

MISSION3_ID = "MISSION_3"
MISSION3_KEY = "MISSION3"
MISSION3_TITLE = "The Vostral"
MISSION3_LOCATION = "The Stabilization Center / IPA Black Site"
MISSION3_PRIMARY_STYLE = "Cold open interrogation into prison break thriller"

MISSION3_STORY_FLAGS = {
    "vendetta": "Balaceanu's six year vendetta against Biribel for the Y-1 Vostral leak.",
    "krap_status": "KRAP is still an organization, disavowed, under siege, fighting for survival and credibility.",
    "vostral": "The buried rumor that Balaceanu's decorated military career is fabricated. Only the regime holds the proof.",
    "maru_reveal": "Maru (MAG) is a former IPA archivist who faked their own death after refusing to forge seizure documents, the root of the trilogy's conflict.",
    "vasile_role": "Vasile re-establishes contact mid-mission under fire, bringing real KRAP assets (off book extraction, stolen IPA comms relay).",
    "broadcast_clock": "Balaceanu's 22:00 live address pinning Route 12 on Biribel personally is the ticking clock.",
}

# ─────────────────────────────────────────────
# Cutscene shot-lists
# ─────────────────────────────────────────────
# Slice 0 stubs: a minimal title-card intro/ending so --dev-mission3 boots
# without requiring new scene art. Slice C ("cinematic art") expands these
# into the full cold-open: draw_cell_interior, draw_interrogation_room,
# draw_balaceanu, draw_maru, draw_archive_vault, draw_broadcast_studio -
# then wires the new scene strings into cutscenes.draw_cutscene_scene.
#
# "Keep these names: acaristan.py uses them." (mirrors the M2 convention.)
import game.timelines as _timelines  # RPE6 P8: timeline data access
mission3_intro_shots = [
    {
        "scene": "cell_ceiling",
        "speaker": "BIRIBEL",
        "text": "Three days. Maybe four.\nHard to count with the lights.",
        "lighting": (4, 4, 6),
        "min_ms": 2600,
    },
    {
        "scene": "cell_restraints",
        "speaker": "BIRIBEL",
        "text": "Wrists raw. Chair bolted down.\nThey were ready for me before I woke up.",
        "lighting": (5, 5, 7),
        "min_ms": 3000,
    },
    {
        "scene": "interrogation_room",
        "speaker": "BALACEANU",
        "text": "You told them I was a coward, Biribel.\nA fake.\nTonight I tell the nation what you are.",
        "lighting": (5, 3, 5),
        "min_ms": 3200,
    },
    {
        "scene": "monitor_broadcast",
        "speaker": "SYSTEM",
        "text": "STATE ADDRESS, LIVE TONIGHT, 22:00\nSUBJECT: ROUTE 12 PERPETRATOR",
        "lighting": (3, 2, 3),
        "min_ms": 3200,
    },
    {
        "scene": "interrogation_room",
        "speaker": "BALACEANU",
        "text": "When the address ends, so do you.\nThat is not a threat.\nThat is a schedule.",
        "lighting": (5, 3, 5),
        "min_ms": 3200,
    },
    {
        "scene": "title_card",
        "speaker": "",
        "text": "MISSION 3\nTHE VOSTRAL",
        "lighting": (5, 5, 8),
        "min_ms": 1800,
    },
]
mission3_intro_shots = _timelines.shots("m3.intro", mission3_intro_shots)  # RPE6 P8: timeline data

mission3_ending_shots = [
    # The finale is played, not narrated: she is on her feet at the booth, the
    # address dies mid-sentence, and the record is on every screen in the
    # country before the title card lands.
    {
        "scene": "m3_end_studio",
        "speaker": "BIRIBEL",
        "text": "Twenty-two hundred. He's already talking.",
        "lighting": (14, 12, 18),
        "min_ms": 3600,
    },
    {
        "scene": "m3_end_cut",
        "speaker": "BALACEANU (PA)",
        "text": "What is this? Cut the feed. CUT THE FEED!",
        "lighting": (10, 6, 8),
        "min_ms": 3200,
    },
    {
        "scene": "m3_end_nation",
        "speaker": "NARRATOR",
        "text": "By 22:07, every screen in Acaristan was reading the Vostral.",
        "lighting": (10, 14, 20),
        "min_ms": 4200,
    },
    {
        "scene": "m3_end_booth_dark",
        "speaker": "VOLKOV",
        "text": "Six years he spent building it. You read it in one minute.",
        "lighting": (5, 5, 8),
        "min_ms": 3400,
    },
    {
        "scene": "title_card",
        "speaker": "BIRIBEL",
        "text": "He spent six years trying to kill a rumor. Now it's a record.",
        "lighting": (5, 5, 8),
        "min_ms": 4600,
    },
]
mission3_ending_shots = _timelines.shots("m3.ending", mission3_ending_shots)  # RPE6 P8: timeline data

OPENING_CINEMATIC = [
    {"speaker": s["speaker"], "text": s["text"]}
    for s in mission3_intro_shots
    if s.get("speaker")
]

# Descriptive phase table (surfaced via get_mission_phases() to menus,
# like M2's MISSION_PHASES). Not the runtime driver - STATE.mission3_stage is.
MISSION_PHASES = [
    {"phase": 1, "name": "Interrogation", "objective": "Survive the room. Learn the broadcast is tonight."},
    {"phase": 2, "name": "Breakout", "objective": "Escape the cell block."},
    {"phase": 3, "name": "KRAP Re-Contact", "objective": "Reach comms. Vasile comes back under fire."},
    {"phase": 4, "name": "The Archives", "objective": "With Volkov: clear the wing, contact Maru, steal the Vostral."},
    {"phase": 5, "name": "Kill Order", "objective": "Survive Balaceanu's personal security sweep."},
    {"phase": 6, "name": "Live Broadcast", "objective": "Fight to the control room. Upload the Vostral before the address ends."},
]

# ─────────────────────────────────────────────
# Runtime stage enum
# ─────────────────────────────────────────────
STAGE_INTERROGATION = "interrogation"
STAGE_BREAKOUT = "breakout"
STAGE_COMMS = "comms"
STAGE_ARCHIVES = "archives"
STAGE_KILL_ORDER = "kill_order"
STAGE_KO_TRANSITION = "ko_transition"
STAGE_BROADCAST = "broadcast"
STAGE_BROADCAST_TRANSITION = "broadcast_transition"
STAGE_VENT_CUTSCENE = "vent_cutscene"
STAGE_ARCHIVES_TRANSITION = "archives_transition"
STAGE_DONE = "done"

# Vent escape cutscene - triggered when the player reaches the cell-block exit.
vent_escape_shots = [
    {
        "scene": "vent_shaft",
        "speaker": None,
        "text": None,
        "lighting": (2, 2, 3),
        "hide_caption": True,
        "min_ms": 3000,
    },
    {
        "scene": "vent_exit",
        "speaker": "BIRIBEL",
        "text": "The kitchen... bypass the corridor guards. Time to move.",
        "lighting": (15, 12, 18),
        "min_ms": 2000,
    },
]
vent_escape_shots = _timelines.shots("m3.vent_escape", vent_escape_shots)  # RPE6 P8: timeline data

# Continuous first-person armory pickup: grab, unhook, chamber, low ready.
# Adjacent scene clocks match cutscenes.k9; silent takes auto-advance instead
# of freezing without a continue prompt. Existing player owns one-shot audio.
k9_pickup_shots = [
    {"scene": "k9_wall_stand", "speaker": None, "text": None,
     "hide_caption": True, "quiet_ui": True, "auto_advance": True,
     "hard_cut": True, "min_ms": 850, "lighting": (8, 10, 10)},
    {"scene": "k9_firstperson_grab", "speaker": None, "text": None,
     "hide_caption": True, "quiet_ui": True, "auto_advance": True,
     "hard_cut": True, "min_ms": 2150, "lighting": (8, 10, 10),
     "cues": ((540, "rifle_handle", 0.30), (850, "rifle_handle", 0.42),
              (1680, "rifle_handle", 0.18))},
    {"scene": "k9_ready_check", "speaker": None, "text": None,
     "hide_caption": True, "quiet_ui": True, "auto_advance": True,
     "hard_cut": True, "min_ms": 1800, "lighting": (8, 10, 10),
     "cues": ((590, "rifle_handle", 0.33), (990, "rifle_handle", 0.48))},
]
k9_pickup_shots = _timelines.shots("m3.k9_pickup", k9_pickup_shots)  # RPE6 P8: timeline data

# Transition from the cell-block service exit to the separate Comms Wing map.
service_transition_shots = [
    {"scene": "m3_service_door_transition", "speaker": None, "text": None, "hide_caption": True, "min_ms": 1500, "lighting": (5, 6, 7)},
    {"scene": "m3_volkov_radio_call", "speaker": "VOLKOV", "text": "Biribel! Take the radio. I draw them off, you get the relay alive.", "min_ms": 2400, "lighting": (5, 6, 7)},
    {"scene": "m3_radio_recovered", "speaker": None, "text": None, "hide_caption": True, "min_ms": 1600, "lighting": (5, 7, 8)},
    {"scene": "m3_comms_wing_reveal", "speaker": "VASILE", "radio": True, "text": "Biribel? If you hear me, get to the relay. I can see your signal now.", "min_ms": 2200, "lighting": (6, 9, 10)},
]
service_transition_shots = _timelines.shots("m3.service_transition", service_transition_shots)  # RPE6 P8: timeline data

# Volkov tops Biribel up when he runs dry in the Comms Wing: two spare mags
# arcing from Volkov's doorway into Biribel's hands.
volkov_mags_shots = [
    {"scene": "m3_volkov_gives_mags", "speaker": "VOLKOV", "text": "Out? Here. Two more. Make them count.", "min_ms": 2200, "lighting": (6, 7, 8)},
    {"scene": "m3_volkov_gives_mags", "speaker": None, "text": None, "hide_caption": True, "min_ms": 1500, "lighting": (6, 7, 8)},
]
volkov_mags_shots = _timelines.shots("m3.volkov_mags", volkov_mags_shots)  # RPE6 P8: timeline data

# Transition from Comms Wing into the Archives: relay goes live, the archive
# access door unlocks, and Biribel steps into the atrium.
archives_transition_shots = [
    # These shots render the real Archives map and live entity sprites. The
    # cutscene camera takes over briefly, but the visual language stays identical
    # to gameplay - no separate first-person/vector-art sequence.
    {"scene": "m3_archives_ingame_enter", "speaker": None, "text": None,
     "hide_caption": True, "min_ms": 1400, "lighting": (5, 7, 8)},
    {"scene": "m3_archives_ingame_join", "speaker": "VOLKOV",
     "text": "Your captain's code opened that IPA relay on the first try. Ask him where he got it.\nOn your six. Move.",
     "min_ms": 6000, "lighting": (7, 9, 10)},
    {"scene": "m3_archives_ingame_reveal", "speaker": "VASILE", "radio": True,
     "text": "Contacts ahead. Maru's dead drop is northwest. Clear a path.",
     "min_ms": 2200, "lighting": (8, 10, 12)},
]
archives_transition_shots = _timelines.shots("m3.archives_transition", archives_transition_shots)  # RPE6 P8: timeline data

# Archives -> Kill Order handoff: illustrated cinematic (cutscenes.m3ko),
# one continuous beat - stair tower breach, mezzanine overwatch, dock exfil.
ko_transition_shots = [
    {"scene": "m3_ko_charge", "speaker": None,
     "text": None, "hide_caption": True, "hard_cut": True,
     "min_ms": 1300, "lighting": (5, 6, 7)},
    {"scene": "m3_ko_stairwell", "speaker": "VOLKOV",
     "text": "My van's still staged at the dock, I haven't bailed on you yet. Through that smoke, friend, and don't make me regret it.",
     "min_ms": 2200, "lighting": (6, 7, 8)},
    {"scene": "m3_ko_aperture", "speaker": "BALACEANU (PA)",
     "text": "Sweep teams: the prisoner is in the lobby levels. Free fire, my address begins at 22:00, and I will not be interrupted.",
     "min_ms": 2400, "lighting": (7, 8, 9)},
    {"scene": "m3_ko_van", "speaker": "VASILE", "radio": True,
     "text": "The loading dock is your only way out, Volkov's van is staged there. Hold it, and the Vostral goes live tonight.",
     "min_ms": 2600, "lighting": (8, 9, 10)},
]
ko_transition_shots = _timelines.shots("m3.ko_transition", ko_transition_shots)  # RPE6 P8: timeline data

# Kill Order -> Broadcast handoff (Slice 5 -> Slice 6): exfil departure,
# ride to the broadcast wing, live address countdown. Bespoke illustrated
# scenes (cutscenes.m3broadcast), same family as the KO transition art.
# Branch-neutral by design (VASILE + PA only): the branch-specific exfil
# bark (VOLKOV van vs MARU roof line) already played in sweep._exfil, so
# these lines work whether Volkov drove or bailed.
broadcast_transition_shots = [
    {"scene": "m3_bcast_shutter", "speaker": None,
     "text": None, "hide_caption": True, "hard_cut": True,
     "min_ms": 1300, "lighting": (5, 6, 7)},
    {"scene": "m3_bcast_road", "speaker": "VASILE", "radio": True,
     "text": "You're out. Broadcast wing, follow the cable runs. I need you in front of a camera before that address ends.",
     "min_ms": 2200, "lighting": (6, 7, 8)},
    {"scene": "m3_bcast_mast", "speaker": "BALACEANU (PA)",
     "text": "The prisoner is contained. At twenty-two hundred I will close the matter of Route 12, on camera, before the nation.",
     "min_ms": 2400, "lighting": (7, 8, 9)},
    {"scene": "m3_bcast_onair", "speaker": "VASILE", "radio": True,
     "text": "Studio door. Two ways to do this, live on his camera, or quiet through my channel. Your call, operator.",
     "min_ms": 2200, "lighting": (8, 9, 10)},
]
broadcast_transition_shots = _timelines.shots("m3.broadcast_transition", broadcast_transition_shots)  # RPE6 P8: timeline data

# Vostral acquisition - also rendered from the live Archives map. The camera
# tightens on the pedestal, the security glass retracts, and Biribel takes the
# physical dossier before Vasile confirms it over radio.
vostral_pickup_shots = [
    {"scene": "m3_vostral_case_open", "speaker": None, "text": None,
     "hide_caption": True, "min_ms": 1300, "lighting": (6, 8, 10)},
    {"scene": "m3_vostral_take", "speaker": "BIRIBEL",
     "text": "The Vostral. The record they buried.",
     "min_ms": 1800, "lighting": (7, 9, 11)},
    {"scene": "m3_vostral_confirm", "speaker": "VASILE", "radio": True,
     "text": "Confirmed. North stairwell, move before they burn the wing.",
     "min_ms": 2100, "lighting": (8, 9, 11)},
]
vostral_pickup_shots = _timelines.shots("m3.vostral_pickup", vostral_pickup_shots)  # RPE6 P8: timeline data

# ─────────────────────────────────────
# Phase 1 - Interrogation dialogue tree
# ─────────────────────────────────────
# Speaker colors (mirrors mission2's C_* radio palette intent).
C_BIRIBEL = (220, 222, 226)      # the player - neutral white
C_BALACEANU = (170, 60, 60)      # the antagonist - regime red
C_VOLKOV = (200, 160, 90)        # returning opportunist - amber
C_SYSTEM = (120, 200, 220)       # diegetic broadcast / system captions
C_PROMPT = (240, 210, 120)       # UI choice prompts - yellow
C_MARU = (180, 140, 220)         # former IPA archivist - violet

# The cold-open script. A flat list of "beats" advanced sequentially by
# handle_event / _update_interrogation. Each beat is one of:
#
#   {"type": "line", "speaker", "text", "color"}
#       A spoken line. ENTER / SPACE advances immediately; otherwise it
#       auto-advances after a reading-time timeout.
#
#   {"type": "choice", "speaker", "prompt", "color", "options": [(label, line), ...]}
#       Blocks until the player picks (up/down or left/right to move the
#       highlight, ENTER to confirm). The chosen option's ``line`` is then
#       injected as a fresh BIRIBEL "line" beat right after this beat, so
#       the player's voice actually plays in the scene. Choices are flavor -
#       they all converge on the Volkov breach - but the player's tone is
#       remembered in STATE.mission3_tone for later slices to read.
#
#   {"type": "action", "action": "<name>"}
#       A diegetic beat with no dialogue: a system caption + sound + screen
#       shake. Used for the broadcast monitor cutting in and Volkov's breach.
#       ENTER / SPACE skips the caption early, otherwise it auto-advances.
#
# The tree is intentionally linear: Phase 1 is a held beat, not a maze. The
# choice points exist to let the player *voice* Biribel, not to branch the
# outcome. Branching is reserved for Phase 6 (the live broadcast).
INTERROGATION_SCRIPT = [
    # Cold open picks up AFTER the intro cutscene (mission3_intro_shots)
    # already delivered: Biribel's "Three days" beat, Balaceanu's "coward /
    # fake / tonight I tell the nation" taunt, the SYSTEM broadcast caption,
    # and Volkov's "You owe me one. Get up." arrival line. The beats below
    # are the EXPANDED interrogation - new material, not a replay.
    #
    # Biribel's interior monologue - processing the deadline Balaceanu
    # just gave him on the monitor.
    {"type": "line", "speaker": "BIRIBEL", "color": C_BIRIBEL,
     "text": "He wants me on camera. The Vostral, by my face, tonight. Fine. He'll get his close up."},

    # The monitor snaps on AGAIN - Balaceanu's looped tape continues with
    # new material. (The cutscene already showed the opening taunt; this is
    # the next segment of the same pre-recorded address.)
    {"type": "action", "action": "monitor_on"},
    {"type": "line", "speaker": "BALACEANU", "color": C_BALACEANU,
     "text": "Six years I have waited to show the nation what a KRAP lie looks like. Up close. On camera."},
    {"type": "line", "speaker": "BALACEANU", "color": C_BALACEANU,
     "text": "They'll see your face, Biribel. They'll hear Route 12. And then they'll see what happens to people who leak rumors about their Prime Minister."},

    # The reveal that drives the whole mission: the broadcast is TONIGHT.
    # (The cutscene's SYSTEM caption already announced "22:00 - LIVE
    # TONIGHT"; Balaceanu's line below is the personal addendum.)
    {"type": "action", "action": "broadcast_caption"},
    {"type": "line", "speaker": "BALACEANU", "color": C_BALACEANU,
     "text": "At twenty-two hundred, the President names you. Route 12. By face. I made sure the file is... thorough."},

    # First choice: how does Biribel meet the threat?
    {"type": "choice", "speaker": "BIRIBEL", "color": C_PROMPT,
     "prompt": "[The monitor stares back. Choose:]",
     "options": [
         ("Spit defiance.",
          "Then say it to my face, coward. Not through a screen."),
         ("Probe for the file.",
          "The Vostral's a rumor because you burned the only copy. So where is it?"),
         ("Stay silent. Watch.",
          "(Biribel says nothing. He memorizes the timestamp on the monitor.)"),
     ]},

    # Balaceanu reads the silence / defiance the same way - he's pre-recorded,
    # he can't actually hear Biribel. That's the point, and the joke.
    {"type": "line", "speaker": "BALACEANU", "color": C_BALACEANU,
     "text": "Oh, save it. This tape is one-way. I'm told the acoustics in here are... unkind."},
    {"type": "line", "speaker": "BALACEANU", "color": C_BALACEANU,
     "text": "When the address ends, so do you. That is not a threat. That is a schedule."},

    # The monitor cuts to static. Lights flicker.
    {"type": "action", "action": "monitor_off"},

    # Second choice: what does Biribel do with his last hour?
    {"type": "choice", "speaker": "BIRIBEL", "color": C_PROMPT,
     "prompt": "[Twenty-two hundred. The file. The broadcast. Choose:]",
     "options": [
         ("Plan the impossible.",
          "If the file exists, it's in this building. I've broken out of better."),
         ("Bargain for time.",
           "Vasile's dead air. Gabi, Seby, Darius, all dead. No one is coming."),
         ("Accept it. Almost.",
          "(He closes his eyes. Then he hears boots in the corridor, and they're wrong.)"),
     ]},

    # Pre-breach establishing beat. Someone is walking down the corridor
    # outside the cell. The player hears it (footstep SFX) and sees it (a
    # faint shadow sweeping under the cell door) BEFORE the C4 appears - so
    # Volkov's arrival reads as a build-up rather than teleportation. The
    # caption cues the player that this isn't a normal patrol round.
    {"type": "action", "action": "boots_approach"},

    # Volkov's breach. He got himself arrested on purpose to reach Biribel.
    # The cutscene already delivered his "You owe me one. Get up." arrival
    # line; the cold open plays the breach FX (flash, shake, door, boom)
    # and Volkov's new in-room line - the time-pressure beat the cutscene
    # didn't have room for.
    # The chair break + leg grab is a SEPARATE post-dialogue cinematic
    # (see chair_break_shots + cutscenes.py's cb_* renderers), not a text caption here.
    {"type": "action", "action": "breach"},
    {"type": "line", "speaker": "VOLKOV", "color": C_VOLKOV,
     "text": "Door's kicked. Camera loop: four minutes, maybe less. I get you out, you get me clear. Move."},
    {"type": "line", "speaker": "VOLKOV", "color": C_VOLKOV,
     "text": "I came in through their own back door. Same way out, if you keep up. Move, operator. Move."},
]

# Auto-advance timing (frames @ 60fps). Never blocks ENTER / SPACE - these
# only kick in if the player lets a beat sit.
#
# The auto-advance is driven by the typewriter: once the current beat's text
# is fully revealed, the system holds for a length-scaled number of frames
# and then advances. The hold scales with text length so a one-liner doesn't
# drag and a long monologue gets time to breathe:
#   40-char beat   -> 180 frames (3.0s)   [floor]
#   80-char beat   -> 240 frames (4.0s)
#   100-char beat  -> 300 frames (5.0s)
#   120-char beat  -> 360 frames (6.0s)   [ceiling]
#   140+ char beat -> 360 frames (6.0s)   [capped]
# Long lines also get all their characters typed out before the hold even
# starts -- a slow reader is never cut off mid-type.
_POST_TYPE_HOLD_MIN = 420           # 7s floor - readable, no rush
_POST_TYPE_HOLD_MAX = 720           # 12s ceiling - long monologues breathe
_POST_TYPE_HOLD_PER_CHAR = 8        # frames of hold per character of text
_BREACH_FREEZE_FRAMES = 90          # post-breach pause before the door reads as open




# Tone memory: defiant=0, probing=1, silent=2 (the option index the player
# picked). Later slices can read STATE.mission3_tone to color Biribel's
# voice in radio chatter and the ending cutscene.
_TONE_DEFIANT = 0
_TONE_PROBING = 1
_TONE_SILENT = 2

# ─────────────────────────────────────────────
# Map / authored layout
# ─────────────────────────────────────────────
# Procedural tilemap (M2-style) so the existing renderer, minimap, wall
# builder, and collision systems keep working. Smaller than M2's 70x80
# because the Stabilization Center is interior space - tight corridors,
# not open highway.
MAP_W, MAP_H = 48, 48
BCAST_MAP_W, BCAST_MAP_H = 32, 32

# Broadcast Slice 6 tuning
# Slice 6 is a 3-wave gauntlet (3 + 4 + 5 guards) then a walk to the PC and a
# 12s upload, all on this one clock. Measured floor with perfect play and
# instant kills is ~29s, so 180s leaves ~6x headroom for real combat while
# removing the dead minutes a 6-minute limit padded the climax with. Failure is
# a soft loop, not a game over: _fail_broadcast_timeout plays the fail cutscene
# and _retry_broadcast_slice rebuilds the slice with a fresh timer.
BCAST_TIME_LIMIT = 180 * 60  # 180 seconds at 60fps
BCAST_UPLOAD_TIME = 6 * 60   # 6 seconds hold-to-upload

# Broadcast fail cutscene: 22:00 reached, Balaceanu finishes his address.
# Auto-retries the slice: the third shot is the studio terminal handing the
# wing back (see _retry_broadcast_slice).
broadcast_fail_shots = [
    {"scene": "m3_bcast_fail_studio", "speaker": None,
     "text": None, "hide_caption": True, "hard_cut": True,
     "min_ms": 1500, "lighting": (3, 2, 3)},
    {"scene": "m3_bcast_fail_pa", "speaker": "BALACEANU (PA)",
     "text": "Twenty-two hundred. The address is finished. The prisoner is contained. Route 12 is closed.",
     "min_ms": 2600, "lighting": (4, 3, 4)},
    {"scene": "m3_bcast_fail_retry", "speaker": "SYSTEM",
     "text": "ADDRESS COMPLETE. THE STUDIO IS THEIRS.\nFEED RELEASED - WING RESET. GO AGAIN.",
     "min_ms": 2200, "lighting": (2, 2, 2)},
]
broadcast_fail_shots = _timelines.shots("m3.broadcast_fail", broadcast_fail_shots)  # RPE6 P8: timeline data

# Tile char legend (parsed in _build_world, drawn in game_draw):
#   "C"  solid concrete wall (full-tile Rect → STATE.walls)
#   "B"  barrier/cover (inset Rect → STATE.walls + STATE.mission3_barriers)
#   "O"  interior floor (office/control sector color)
#   "."  corridor floor
#   "g"  exterior ground (default fill)
#   "P"  player spawn
#   "X"  exfil / objective marker
#   "D"  cell door (passable visual - foreshadows locked-door beats)
#   "K"  kitchen / utility floor tile
#   "L"  laundry / uniform processing floor
#   "Y"  exercise-yard concrete floor
#   "M"  maintenance / boiler wing floor
#   "E"  exit zone tiles
#   "S"  security glass (visual only - passable, frosted-cyan tint)
PLAYER_START_TILE = (32, 9)   # inside the southernmost cell



# Cell interior tile bounds (Biribel's cell = cell index 3 in the new 48x48
# layout: cols 30..37, rows 5..12). Used to place furniture against walls.
_CELL_COL_WEST = 30
_CELL_COL_EAST = 37
_CELL_ROW_NORTH = 5
_CELL_ROW_SOUTH = 12

_MONITOR_TILE_COL, _MONITOR_TILE_ROW = 33, 5  # north wall of Biribel's cell (cell 3)

# Door tile (col 9, row 13) is where the cell's south-wall door sits.
# Computed from the map authoring: outline at (4,4) w=12 h=10 with a door
# gap at tile offset (5,9) -> (4+5, 4+9) = (9, 13).
_DOOR_TILE_COL, _DOOR_TILE_ROW = 33, 12   # south wall of Biribel's cell
