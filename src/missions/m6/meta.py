"""Mission 6 metadata, stage constants and authored cutscene timelines.

Mission 6 ("Black Notebook") is the campaign hinge.  The playable ladder is
five stages - customs, no-man's-land, rail yard, boxcar, interactive train -
and the spectacle promised by ``docs/MISSION6_PLOT.md`` lives in three
engine3d films (insertion, boxcar, ending) plus the shoulder-cam train scene
in ``train3d.py``.  The terminal file and Vasile's call are told by the
ending film, not played as separate top-down stages.

This module owns the story data only: stage ids, anchors, shots and radio
lines.  Runtime map state lives in ``maps.py``; the films themselves live in
``cutscenes/m6films.py`` and are registered at the bottom of this file.
"""
MISSION6_ID = "MISSION_6"
MISSION6_KEY = "MISSION6"
MISSION6_TITLE = "Black Notebook"
MISSION6_LOCATION = "Kim Kim Border / Frozen Rail Yard"
MISSION6_PRIMARY_STYLE = "Freezing border stealth into a quiet betrayal"

STAGE_CUSTOMS = "customs"
STAGE_NOMAN = "noman"
STAGE_RAIL = "rail"
STAGE_BOXCAR = "boxcar"
STAGE_TRAIN = "train"
STAGES = (STAGE_CUSTOMS, STAGE_NOMAN, STAGE_RAIL, STAGE_BOXCAR, STAGE_TRAIN)

# C/W/B are the only solids in the M6 maps; every other map char is a
# walkable/special floor tile (MapBuilder stays the authority).
M6_SOLID_CHARS = frozenset("CWB")
M6_WALKABLE_TILES = frozenset(".gOKLYMESDPXVN")

MISSION_PHASES = [
    {"phase": 1, "name": "Insertion", "objective": "Reach the hills above the crossing."},
    {"phase": 2, "name": "Customs Post", "objective": "Get through the abandoned post."},
    {"phase": 3, "name": "No-Man's-Land", "objective": "Cross the floodlit strip."},
    {"phase": 4, "name": "Rail Yard", "objective": "Find Volkov before the Guard does."},
    {"phase": 5, "name": "The Boxcar", "objective": "Read the last copy of the notebook."},
    {"phase": 6, "name": "The Train", "objective": "Cover Volkov to the waiting train."},
]

# World-space tile centres.  Flow, draw and the smoke probe agree on these.
STAGE_ANCHORS = {
    STAGE_CUSTOMS: (16, 1),      # north gate out of the customs post
    STAGE_NOMAN: (20, 1),        # north gate into the rail yard
    STAGE_RAIL: (25, 11),        # foot of Volkov's boxcar
    STAGE_BOXCAR: (25, 11),
    STAGE_TRAIN: (25, 11),
}

STAGE_SPAWNS = {
    STAGE_CUSTOMS: (14, 17),
    STAGE_NOMAN: (20, 16),
    STAGE_RAIL: (22, 24),
    STAGE_BOXCAR: (22, 24),
    STAGE_TRAIN: (22, 24),
}

# Optional beats inside a stage (proximity barks / set dressing).
QUEUE_ANCHOR = (4, 15)           # the frozen family cars, customs yard
QUEUE_RADIUS = 130
GATE_RADIUS = 80
BOXCAR_RADIUS = 90

VOLKOV_BOXCAR_TILE = (20, 9)     # the marked car in the rail yard
NOMAN_TOWER_TILES = ((8, 4), (31, 4), (8, 10), (31, 10))
RAIL_DETECTOR_TILES = ((41, 8), (4, 6))   # signal tower + platform lamp

# Alarm-wave entry tiles.  Every tile is walkable floor in its stage map.
ALARM_SPAWN_TILES = {
    STAGE_NOMAN: ((19, 2), (21, 2), (19, 15), (21, 15), (20, 3), (20, 14)),
    STAGE_RAIL: ((18, 24), (26, 24), (2, 16), (43, 16), (5, 24), (42, 24)),
}
MAX_ALARM_ENEMIES = 6

# A wave never *appears* on its tile.  Every Guard walks in from a point
# ``ALARM_ENTRY_DIST`` px further out from the map centre (shortened until
# both he and the line back to his tile stand on open floor), so the first
# frame he is on screen he is already moving through kicked-up snow.
ALARM_ENTRY_DIST = 118.0
ALARM_ENTRY_S = 0.62
# Seconds after the alarm before each wave comes through the gates.  The
# first beat is deliberately late: the siren and the radio line land first,
# so the player reads the alarm before anyone is in the yard.
ALARM_WAVE_DELAYS = {
    STAGE_NOMAN: (2.4, 8.0, 13.5),
    STAGE_RAIL: (2.2, 7.6, 13.0),
}
ALARM_WAVE_SIZE = {STAGE_NOMAN: 2, STAGE_RAIL: 2}
ALARM_FIRST_WAVE = {STAGE_NOMAN: 3, STAGE_RAIL: 2}

# Checkpoint save keys (the four playable stages before the interactive
# train; the boxcar is a cutscene inside rail and is not a save point).
CHECKPOINT_FLAGS = {
    STAGE_CUSTOMS: "m6_customs_checkpoint",
    STAGE_NOMAN: "m6_noman_checkpoint",
    STAGE_RAIL: "m6_rail_checkpoint",
    STAGE_TRAIN: "m6_train_checkpoint",
}

STAGE_OBJECTIVES = {
    STAGE_CUSTOMS: "Search the abandoned crossing, then take the north gate.",
    STAGE_NOMAN: "Cross the floodlit strip. Use the dark between sweeps.",
    STAGE_RAIL: "Find Volkov - the marked boxcar on the east freight line.",
    STAGE_BOXCAR: "Talk to Volkov.",
    STAGE_TRAIN: "Cover Volkov to the train.",
}

_STAGE_RADIO = {
    STAGE_CUSTOMS: ("MARU",
                    "Border's closed. Customs is abandoned, not empty. Search it."),
    STAGE_NOMAN: ("MARU",
                  "Floodlights sweep east to west. Move when the yard goes dark."),
    STAGE_RAIL: ("VASILE",
                 "Guard traffic puts Volkov in the rail yard. Find him first."),
    STAGE_TRAIN: ("MARU",
                  "The train is leaving. Keep the Guard's heads down."),
}

# ── 3D films ─────────────────────────────────────────────────────────────
# Insertion.  ``auto_advance`` because there is no dialogue to click through;
# the final title card holds long enough to read.
mission6_intro_shots = [
    {"scene": "m6_insert_heli", "speaker": "", "text": "",
     "lighting": (5, 8, 14), "min_ms": 3200, "auto_advance": True,
     "quiet_ui": True,
     "cues": [(500, "m6_heli_bed", 0.55), (2600, "m6_rotor_away", 0.45)]},
    {"scene": "m6_insert_jump", "speaker": "", "text": "",
     "lighting": (6, 9, 15), "min_ms": 2900, "auto_advance": True,
     "quiet_ui": True,
     "cues": [(300, "m6_jump", 0.55), (2400, "m6_wind_gust", 0.4)]},
    {"scene": "m6_insert_fall", "speaker": "", "text": "",
     "lighting": (7, 10, 16), "min_ms": 2900, "auto_advance": True,
     "quiet_ui": True,
     "cues": [(200, "m6_fall", 0.5), (2200, "m6_wind_gust", 0.45)]},
    {"scene": "m6_insert_ground", "speaker": "", "text": "",
     "lighting": (8, 12, 18), "min_ms": 3100, "auto_advance": True,
     "quiet_ui": True,
     "cues": [(250, "m6_land", 0.6), (2000, "m6_heli_away", 0.45)]},
    {"scene": "title_card", "speaker": "", "text": "MISSION 6\nBLACK NOTEBOOK",
     "lighting": (4, 6, 10), "min_ms": 1900},
]

# The boxcar conversation: one mid-mission cutscene, five 3D shots.  Lines are
# verbatim from docs/MISSION6_PLOT.md ("Key Scene - The Boxcar").
M6_MID_CUTSCENES = {
    "boxcar": [
        {"scene": "m6_boxcar_wide", "speaker": "VOLKOV",
         "text": "You took this from me once. Read it this time.",
         "lighting": (13, 11, 8), "min_ms": 6200, "radio": False,
         "cues": [(600, "m6_boxcar_door", 0.4), (1200, "m6_breath", 0.25)]},
        {"scene": "m6_boxcar_notebook", "speaker": "BIRIBEL",
         "text": "...Route 12. Movement order. Authorization - That's Vasile's code.",
         "lighting": (14, 12, 9), "min_ms": 6600, "radio": False,
         "cues": [(900, "m6_paper", 0.5), (2500, "m6_page_turn", 0.4)]},
        {"scene": "m6_boxcar_volkov", "speaker": "VOLKOV",
         "text": "I tried to sell it to anyone who'd stop it. You were the one who showed up.",
         "lighting": (13, 11, 8), "min_ms": 6600, "radio": False,
         "cues": [(400, "m6_breath", 0.25)]},
        {"scene": "m6_boxcar_biribel", "speaker": "BIRIBEL",
         "text": "You knew. In the warehouse. You knew where it would go.",
         "lighting": (14, 12, 9), "min_ms": 6100, "radio": False,
         "cues": [(700, "m6_snow_step", 0.3)]},
        {"scene": "m6_boxcar_exit", "speaker": "VOLKOV",
         "text": "I knew who you'd give it to. I didn't know how to tell you without you shooting me.",
         "lighting": (12, 10, 8), "min_ms": 6900, "radio": False,
         "cues": [(900, "m6_notebook_close", 0.45)]},
        {"scene": "m6_boxcar_exit", "speaker": "VOLKOV",
         "text": "I just wanted to get out. Funny. You did too.",
         "lighting": (12, 10, 8), "min_ms": 5400, "radio": False,
         "cues": [(500, "m6_boxcar_door", 0.35), (3000, "m6_snow_step", 0.3)]},
    ],
}

# The ending chain.  Scene ids are the contract from the plot doc; do not
# rename them.  The four Vasile lines reuse one scene renderer and alternate
# camera angles from the current shot.
mission6_ending_shots = [
    {"scene": "m6_customs_terminal", "speaker": "", "text": "",
     "lighting": (6, 10, 8), "min_ms": 5200, "auto_advance": True,
     "quiet_ui": True, "cues": [(400, "m6_terminal_beep", 0.5)]},
    {"scene": "m6_radio_vasile", "speaker": "BIRIBEL",
     "text": "Route 12 went out on your code.",
     "lighting": (10, 10, 12), "min_ms": 4400, "radio": True,
     "cues": [(300, "m6_radio_static", 0.4)]},
    {"scene": "m6_radio_vasile", "speaker": "VASILE",
     "text": "...Three hundred men, Biribel. They'd have purged every one. I chose the many.",
     "lighting": (10, 10, 12), "min_ms": 6600, "radio": True,
     "cues": [(300, "m6_radio_static", 0.45)]},
    {"scene": "m6_radio_vasile", "speaker": "VASILE",
     "text": "You'd have done the same.",
     "lighting": (10, 10, 12), "min_ms": 4400, "radio": True,
     "cues": [(200, "m6_radio_static", 0.4)]},
    {"scene": "m6_radio_vasile", "speaker": "VASILE",
     "text": "Retardovici is at the mansion in two nights. I can get you inside. Let me make this right.",
     "lighting": (10, 10, 12), "min_ms": 7200, "radio": True,
     "cues": [(300, "m6_radio_static", 0.45)]},
    {"scene": "m6_radio_maru", "speaker": "MARU",
     "text": "Not tonight. Go to ground.",
     "lighting": (10, 12, 12), "min_ms": 4200, "radio": True,
     "cues": [(250, "m6_radio_static", 0.4)]},
    {"scene": "m6_helicopter", "speaker": "", "text": "",
     "lighting": (6, 9, 15), "min_ms": 5200, "auto_advance": True,
     "quiet_ui": True, "cues": [(600, "m6_heli_away", 0.55)]},
    {"scene": "title_card", "speaker": "",
     "text": "BLACK NOTEBOOK\nTHE LAST SIGNAL",
     "lighting": (4, 6, 10), "min_ms": 2200},
]

M6_FILM_SCENES = tuple(sorted({
    shot["scene"] for shot in
    (list(mission6_intro_shots)
     + [s for shots in M6_MID_CUTSCENES.values() for s in shots]
     + list(mission6_ending_shots))
    if shot["scene"] != "title_card"
}))

# Register the engine3d takes from the owner module (same idiom as M5).  The
# films module never imports missions.m6, so this stays acyclic.
try:  # pragma: no cover - registration is exercised by the smoke test
    from cutscenes import m6films as _m6films  # noqa: F401,E402
except Exception as _m6_films_err:  # keep M6 importable without a 3D stack
    _m6films = None
