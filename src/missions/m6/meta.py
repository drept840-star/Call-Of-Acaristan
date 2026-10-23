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
MISSION6_PRIMARY_STYLE = "Freezing border firefights into a quiet betrayal"

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
    STAGE_CUSTOMS: (15, 1),      # north gate out of the customs post
    STAGE_NOMAN: (20, 1),        # north gate into the rail yard
    STAGE_RAIL: (25, 11),        # foot of Volkov's boxcar
    STAGE_BOXCAR: (25, 11),
    STAGE_TRAIN: (25, 11),
}

STAGE_SPAWNS = {
    STAGE_CUSTOMS: (15, 18),
    STAGE_NOMAN: (20, 16),
    STAGE_RAIL: (22, 24),
    STAGE_BOXCAR: (22, 24),
    STAGE_TRAIN: (22, 24),
}

# Optional beats inside a stage (proximity barks / set dressing).
QUEUE_ANCHOR = (5, 16)           # the frozen queue and the tanker, customs yard
QUEUE_RADIUS = 130
GATE_RADIUS = 80
BOXCAR_RADIUS = 90

VOLKOV_BOXCAR_TILE = (20, 9)     # the marked car in the rail yard
NOMAN_TOWER_TILES = ((8, 4), (31, 4), (8, 10), (31, 10))
RAIL_DETECTOR_TILES = ((41, 8), (4, 6))   # signal tower + platform lamp

# ── combat arenas ──────────────────────────────────────────────────────────
# Each top-down stage is a firefight: an opening squad dug in behind cover
# (the map's "E" markers), then scripted waves.  A wave comes when the living
# count drops to ``living`` or ``after`` seconds after the previous beat once
# the fight is loud, whichever is first.  The exit opens only when every wave
# has come and nobody is left standing.
SQUAD_KINDS = {
    STAGE_CUSTOMS: {(11, 10): "marksman", (25, 12): "raider"},
    STAGE_NOMAN: {(17, 3): "marksman", (23, 3): "marksman", (17, 7): "raider"},
    STAGE_RAIL: {(38, 6): "marksman", (16, 7): "marksman", (35, 17): "raider"},
}

# hp / speed per Guard role (sprite variant comes from the M5 Guard art).
M6_ROLE_TUNING = {
    "guard": {"hp": 70, "speed": 1.75},
    "marksman": {"hp": 55, "speed": 1.35},
    "raider": {"hp": 115, "speed": 2.45},
}

ARENA_WAVES = {
    STAGE_CUSTOMS: (
        {"living": 2, "after": 22.0, "event": None,
         "radio": ("MARU", "More of them in the post. North doors."),
         "units": (("guard", 10, 3), ("guard", 20, 3), ("raider", 27, 4))},
        {"living": 2, "after": 26.0, "event": "truck",
         "radio": ("MARU", "Truck at the gate. They brought friends."),
         "units": (("guard", 14, 1), ("guard", 16, 2), ("marksman", 22, 3),
                   ("raider", 21, 2), ("guard", 18, 2))},
    ),
    STAGE_NOMAN: (
        {"living": 2, "after": 24.0, "event": None,
         "radio": ("MARU", "North gate's opening. Second squad."),
         "units": (("guard", 19, 1), ("guard", 21, 1), ("raider", 14, 2))},
        {"living": 2, "after": 28.0, "event": "flare",
         "radio": ("MARU", "Flare! They're coming down both wire lines."),
         "units": (("guard", 2, 8), ("guard", 37, 8), ("guard", 2, 3),
                   ("raider", 37, 3))},
    ),
    STAGE_RAIL: (
        {"living": 2, "after": 22.0, "event": None,
         "radio": ("MARU", "Fence gaps, both sides. They're boxing you in."),
         "units": (("guard", 2, 15), ("raider", 2, 16), ("guard", 43, 16))},
        {"living": 2, "after": 26.0, "event": "train",
         "radio": ("VASILE", "Guard stepping off the train. Watch the platform."),
         "units": (("guard", 10, 5), ("marksman", 24, 5), ("guard", 36, 5),
                   ("raider", 20, 5))},
        {"living": 2, "after": 30.0, "event": None,
         "radio": ("MARU", "Behind you - south fence!"),
         "units": (("guard", 5, 24), ("raider", 26, 24), ("guard", 40, 24))},
    ),
}

# Fuel drums: shoot one and everything near it burns.  Never on a wave tile.
ARENA_DRUMS = {
    STAGE_CUSTOMS: ((6, 13), (23, 2), (12, 8), (16, 13), (27, 11), (8, 17)),
    STAGE_NOMAN: ((19, 8), (21, 3), (12, 12), (28, 12), (6, 3)),
    STAGE_RAIL: ((14, 12), (19, 15), (33, 14), (27, 8), (9, 5), (35, 19)),
}

# Most Guards alive at once; a wave that would overrun it waits.
ARENA_MAX_LIVING = 7

# Wave entry tiles (every tile is walkable floor in its stage map).
ALARM_SPAWN_TILES = {
    stage: tuple((c, r) for wave in waves for _kind, c, r in wave["units"])
    for stage, waves in ARENA_WAVES.items()
}
MAX_ALARM_ENEMIES = 6

# A wave never *appears* on its tile.  Every Guard walks in from a point
# ``ALARM_ENTRY_DIST`` px further out from the map centre (shortened until
# both he and the line back to his tile stand on open floor), so the first
# frame he is on screen he is already moving through kicked-up snow.
ALARM_ENTRY_DIST = 118.0
ALARM_ENTRY_S = 0.62

# Checkpoint save keys (the four playable stages before the interactive
# train; the boxcar is a cutscene inside rail and is not a save point).
CHECKPOINT_FLAGS = {
    STAGE_CUSTOMS: "m6_customs_checkpoint",
    STAGE_NOMAN: "m6_noman_checkpoint",
    STAGE_RAIL: "m6_rail_checkpoint",
    STAGE_TRAIN: "m6_train_checkpoint",
}

STAGE_OBJECTIVES = {
    STAGE_CUSTOMS: "Clear the customs post, then take the north gate.",
    STAGE_NOMAN: "Fight across the strip. Shoot out the tower lamps.",
    STAGE_RAIL: "Hold the yard, then reach Volkov's marked boxcar.",
    STAGE_BOXCAR: "Talk to Volkov.",
    STAGE_TRAIN: "Cover Volkov to the train.",
}

_STAGE_RADIO = {
    STAGE_CUSTOMS: ("MARU",
                    "Customs is full of Guard. No quiet way through - go loud."),
    STAGE_NOMAN: ("MARU",
                  "Every tower has a gunner on the lamp. Shoot the lights out."),
    STAGE_RAIL: ("VASILE",
                 "Guard traffic puts Volkov in the rail yard. Find him first."),
    STAGE_TRAIN: ("MARU",
                  "The train is leaving. Keep the Guard's heads down."),
}

# ── 3D films ─────────────────────────────────────────────────────────────
# Insertion.  ``auto_advance`` because there is no dialogue to click through;
# the final title card holds long enough to read.
mission6_intro_shots = [
    {"scene": "m6_insert_cabin", "speaker": "GUARD",
     "text": "All posts, Kim Kim crossing. High-value deserter in the rail yard. Hold the train.",
     "lighting": (5, 8, 14), "min_ms": 3600, "radio": True,
     "cues": [(100, "m6_heli_bed", 0.45), (300, "m6_radio_static", 0.45)]},
    {"scene": "m6_insert_cabin", "speaker": "MARU",
     "text": "That's your notebook man. Volkov.",
     "lighting": (5, 8, 14), "min_ms": 3000, "radio": False, "cues": []},
    {"scene": "m6_insert_cabin", "speaker": "BIRIBEL",
     "text": "Then I reach him first.",
     "lighting": (5, 8, 14), "min_ms": 3000, "radio": False, "cues": []},
    {"scene": "m6_insert_valley", "speaker": "", "text": "",
     "lighting": (6, 9, 15), "min_ms": 5000, "auto_advance": True,
     "quiet_ui": True,
     "cues": [(300, "m6_heli_bed", 0.5), (3200, "m6_wind_gust", 0.4)]},
    {"scene": "m6_insert_jump", "speaker": "", "text": "",
     "lighting": (7, 10, 16), "min_ms": 5000, "auto_advance": True,
     "quiet_ui": True,
     "cues": [(2800, "m6_jump", 0.55), (3900, "m6_land", 0.7)]},
    {"scene": "m6_insert_ground", "speaker": "", "text": "",
     "lighting": (8, 12, 18), "min_ms": 6000, "auto_advance": True,
     "quiet_ui": True,
     "cues": [(300, "m6_heli_away", 0.5), (3300, "m6_snow_step", 0.3)]},
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
    {"scene": "m6_customs_return", "speaker": "", "text": "",
     "lighting": (6, 10, 8), "min_ms": 4500, "auto_advance": True,
     "quiet_ui": True,
     "cues": [(500, "m6_snow_step", 0.35), (1500, "m6_wind_gust", 0.30),
              (2500, "m6_snow_step", 0.30), (3400, "m6_door_creak", 0.35)]},
    {"scene": "m6_customs_terminal", "speaker": "", "text": "",
     "lighting": (6, 10, 8), "min_ms": 7500, "auto_advance": True,
     "quiet_ui": True,
     "cues": [(400, "m6_terminal_beep", 0.5),
              (700, "m6_keyclick", 0.35), (900, "m6_keyclick", 0.30),
              (1100, "m6_keyclick", 0.32), (1300, "m6_keyclick", 0.28),
              (1500, "m6_keyclick", 0.30), (1700, "m6_keyclick", 0.26),
              (2600, "m6_terminal_beep", 0.35),
              (6200, "m6_terminal_beep", 0.45)]},
    {"scene": "m6_radio_vasile", "speaker": "BIRIBEL",
     "text": "Route 12 went out on your code.",
     "lighting": (10, 10, 12), "min_ms": 4400, "radio": True,
     "cues": [(150, "m6_paper", 0.4), (300, "m6_radio_static", 0.4),
              (900, "m6_switch_click", 0.35)]},
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
     "cues": [(300, "m6_radio_static", 0.45), (4200, "m6_paper", 0.35)]},
    {"scene": "m6_radio_silence", "speaker": "", "text": "",
     "lighting": (10, 10, 12), "min_ms": 2400, "auto_advance": True,
     "quiet_ui": True,
     "cues": [(100, "m6_radio_static", 0.30), (900, "m6_breath", 0.25)]},
    {"scene": "m6_radio_maru", "speaker": "MARU",
     "text": "Not tonight. Go to ground.",
     "lighting": (10, 12, 12), "min_ms": 4200, "radio": True,
     "cues": [(250, "m6_radio_static", 0.4),
              (500, "m6_switch_click", 0.25)]},
    {"scene": "m6_cut_line", "speaker": "", "text": "",
     "lighting": (10, 10, 12), "min_ms": 3000, "auto_advance": True,
     "quiet_ui": True,
     "cues": [(600, "m6_switch_click", 0.5), (900, "m6_radio_static", 0.25),
              (1700, "m6_notebook_close", 0.45),
              (2300, "m6_snow_step", 0.30)]},
    {"scene": "m6_helicopter", "speaker": "", "text": "",
     "lighting": (6, 9, 15), "min_ms": 12000, "auto_advance": True,
     "quiet_ui": True,
     "cues": [(150, "m6_heli_land", 0.6), (600, "m6_wind_gust", 0.35),
              (3900, "m6_heli_door", 0.35), (6800, "m6_heli_door", 0.6),
              (10800, "m6_heli_away", 0.5)]},
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
