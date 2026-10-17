
"""Mission 4 - part module. See __init__.py for the package facade."""
"""Mission 4: The Aftermath (working title) - the world after the broadcast.

Picks up hours after Mission 3's Vostral transmission. The regime is
reeling: Balaceanu's career is public record, Retardovici's puppet strings
are cut, and KRAP is left without clear direction. Volkov has vanished
across the border to Regatul Kim Kim. Vasile and Biribel are the only
ones left trying to figure out what comes next — KRAP doesn't fully
dissolve but "kind of dissolves," its remnants allied with MAG, while
Maru steps into physical presence for the first time.

The framing is no longer "mission assigned" but "what do we do now":
KRAP's ambiguous status, Maru's reappearance, and Biribel's own path
away from the soldier's life — without making him a fugitive.

Slice-0 title-card stubs mirror the M3 convention so a dev jump can
boot before scene art exists. Game integration (game_core.start_mission4,
save MISSION_4, app.py routing, dev_jumps) is wired in later slices.
"""

MISSION4_ID = "MISSION_4"
MISSION4_KEY = "MISSION4"
MISSION4_TITLE = "The Aftermath"
MISSION4_LOCATION = "Acaristan - post-broadcast"
MISSION4_PRIMARY_STYLE = "Post-broadcast realignment - no mission assigned"

MISSION4_STORY_FLAGS = {
    "aftermath": "The Vostral is on every screen; Balaceanu's regime is off-balance.",
    "retardovici": "Retardovici's cape is gone — the regime's survival is uncertain.",
    "krap_status": "KRAP kind of dissolves; its remnants ally with MAG, direction unclear.",
    "volkov_left": "Volkov has left Acaristan for Regatul Kim Kim, leaving a vacuum.",
    "maru_present": "Maru now has physical presence — formerly a voice, now on the ground.",
    "vasile_biribel": "Vasile and Biribel are the only close ones left, figuring what's next.",
}

# ────────────────────────────────────────────
# Map / runtime constants
# ────────────────────────────────────────────
# Kept raw numbers/tuples: meta.py stays dependency-free (same contract as
# core.mapbuilder - missions may import meta before pygame exists).
MAP_W = 40
MAP_H = 40
TILE = 64  # mirrors core.config.TILE_SIZE (local copy for the same reason)

# Tile chars (solid-first street grammar): C building block (solid), B
# barricade (solid), "." asphalt, "d" sidewalk, "R" lane paint (overlay),
# "D" door gap (walkable), "O" interior floor, "L" corridor floor,
# "V" Vasile comms cache marker, "E" guard spawn (floor), "M" marksman spawn
# (floor), "J" jammer spot, "T" transmitter spot. Solid set consumed by
# world._build_walls; the street map is a lattice carved out of a solid C field.
M4_SOLID_CHARS = ("C", "B")

# Key tiles (col, row). Street map: NW cross-streets, boulevard mid,
# radio station east.
PLAYER_START_TILE = (9, 4)     # street intersection between the blocks (V+H lane)
VASILE_CACHE_TILE = (16, 21)   # south sidewalk of the boulevard ("boulevard" zone)
STATION_DOOR_TILE = (34, 19)   # western face of the station block, off the boulevard
STATION_START_TILE = (8, 15)    # interior spawn after the door handoff
TRANSMITTER_TILE = (20, 7)      # W3/W4 objective inside the station
# Liaison meet (W3): Maru stands in the north transmitter hall; the jammer
# is installed on the transmitter rack beside him. Both are on "O" floor.
LIAISON_TILE = (7, 4)           # Maru (the KRAP-MAG liaison)
JAMMER_TILE = (20, 5)           # jammer install point on the TX rack
VASILE_STATION_TILE = (9, 4)    # Vasile covers the hall during the meet

# Named regions of the curfew street (W2). Mirrors the m2.meta ZONE_DEFS
# concept - a label + a tile-space rect - but stored as a raw (left, top,
# w, h) tuple so meta.py stays dependency-free (no pygame import here; the
# world-space rects + a point-in-zone helper are built in maps.py from
# these). Ambient event triggers and the story-beat ladder key on them.
M4_ZONE_DEFS = {
    "safehouse": {
        "label": "Old Town Streets",
        "tile_rect": (6, 1, 8, 8),
    },
    "boulevard": {
        "label": "Curfew Boulevard",
        "tile_rect": (1, 17, 30, 5),
    },
    "station_cordon": {
        "label": "Radio Station Cordon",
        "tile_rect": (26, 10, 14, 17),
    },
}

# Slice 3 hold clock: the transmitter must hold while the arrest plays out
# on air. Timer-driven and independent of wave state (M3's exfil-door
# lesson - a hold that only ends on kills can soft-lock).
M4_HOLD_SECONDS = 90

# Radio/PA speaker colors (m3.meta convention, local to m4 - no cross-
# package imports of m3 constants).
C_SYSTEM = (150, 170, 190)
C_VASILE = (110, 160, 220)
C_MARU = (110, 200, 140)
C_BALACEANU = (220, 90, 70)
C_RETARDOVICI = (230, 200, 120)
C_VOLKOV = (200, 140, 90)
BIRIBEL_SPEAKER = (225, 228, 232)  # player's own lines in the liaison beat

# Enemy stat table (values ported from m3's sweep ROLE_TUNING spirit; the
# module itself is NOT imported - m3 globals are mission-scoped).
M4_ROLE_TUNING = {
    "guard": {"hp": 90, "speed": 2.0},
    "marksman": {"hp": 70, "speed": 1.6},
}

# ─────────────────────────────────────────────
# Cutscene shot-lists (W5: real finale + intro art)
# ─────────────────────────────────────────────
# Scene names dispatch through cutscenes/engine.py::draw_cutscene_scene to the
# bespoke draws in cutscenes/m4aftermath.py. The M3 callback reuses an existing
# M3 scene (m3_end_nation) rather than duplicating art. Schema mirrors the M2/M3
# convention: scene / speaker / text / lighting / min_ms. "Keep these names:
# acaristan.py uses them."
import game.timelines as _timelines  # RPE6 P8: timeline data access
mission4_intro_shots = [
    {
        "scene": "m3_end_nation",
        "speaker": "NARRATOR",
        "text": "Forty-eight hours after the Vostral, the address is still\nreading on every screen in the capital.",
        "lighting": (10, 14, 20),
        "min_ms": 3800,
    },
    {
        "scene": "m4_city_curfew",
        "speaker": "VASILE",
        "text": "And this is what it bought us. A curfew nobody can enforce\nand a regime that shoots its own order.",
        "lighting": (12, 10, 16),
        "min_ms": 3600,
    },
    {
        "scene": "title_card",
        "speaker": "",
        "text": "MISSION 4\nTHE AFTERMATH",
        "lighting": (5, 5, 8),
        "min_ms": 2000,
    },
]
mission4_intro_shots = _timelines.shots("m4.intro", mission4_intro_shots)  # RPE6 P8: timeline data

mission4_ending_shots = [
    # Biribel never sees Balaceanu fall - he hears it on the general's own
    # airwaves. The finale is the regime eating itself, then the roof at dawn
    # and the choice to stay.
    {
        "scene": "m4_arrest_screen",
        "speaker": "VASILE",
        "text": "It's done. He's in a cell by his own guard's hands.",
        "lighting": (10, 6, 8),
        "min_ms": 14800,
        "caption_after_ms": 12400,
        "quiet_ui": True,
        "cues": ((0, "m4_tension", 0.85), (2500, "pa_mumble", 0.18),
                 (4900, "m4_breath", 0.75), (7200, "rifle_handle", 0.16),
                 (7900, "m4_cuff_close", 0.95),
                 (9600, "footstep_walk", 0.36), (10150, "footstep_walk", 0.32),
                 (10700, "footstep_walk", 0.28), (11250, "footstep_walk", 0.24),
                 (12200, "door_creak", 0.26), (12400, "m4_aftermath", 0.75),
                 (13500, "m4_crowd", 0.80)),
    },
    {
        "scene": "m4_maru_silhouette",
        "speaker": "MARU",
        "text": "And the man on the screen smiles. The country is cheering\nthe wrong name tonight.",
        "lighting": (7, 12, 12),
        "min_ms": 6400,
        "caption_after_ms": 900,
        "quiet_ui": True,
        "cues": ((0, "m4_aftermath", 0.45), (1300, "m4_breath", 0.45)),
    },
    {
        "scene": "m4_roof_dawn",
        "speaker": "BIRIBEL",
        "text": "Nobody asked us to do this. First time in my life -\nthat's how it's done right.",
        "lighting": (20, 18, 26),
        "min_ms": 7200,
        "caption_after_ms": 1600,
        "quiet_ui": True,
        "cues": ((1600, "m4_breath", 0.35),),
    },
    {
        "scene": "m4_roof_dawn",
        "speaker": "BIRIBEL",
        "text": "There's a border that doesn't care about my name.\nI'm not taking it. Not yet.",
        "lighting": (24, 20, 28),
        "min_ms": 7000,
        "scene_time_offset_ms": 7200,
        "caption_after_ms": 1100,
        "quiet_ui": True,
    },
    {
        "scene": "title_card",
        "speaker": "",
        "text": "THE AFTERMATH",
        "lighting": (5, 5, 8),
        "min_ms": 2400,
    },
]
mission4_ending_shots = _timelines.shots("m4.ending", mission4_ending_shots)  # RPE6 P8: timeline data

OPENING_CINEMATIC = [
    {"speaker": s["speaker"], "text": s["text"]}
    for s in mission4_intro_shots
    if s.get("speaker")
]

# Provisional phase table — narrative flow matching the new direction.
# Not the runtime driver - STATE.mission4_stage is (mirrors M3).
MISSION_PHASES = [
    {"phase": 1, "name": "Aftermath", "objective": "Process the broadcast's fallout; Volkov is gone."},
    {"phase": 2, "name": "KRAP Status", "objective": "Determine if KRAP allies with MAG or dissolves further."},
    {"phase": 3, "name": "Maru Reappears", "objective": "Maru's first physical appearance; new assets available."},
    {"phase": 4, "name": "New Direction", "objective": "Vasile and Biribel decide their own path — not a mission, their choice."},
]

# ─────────────────────────────────────────────
# Runtime stage enum
# ─────────────────────────────────────────────
STAGE_INTRO = "intro"
STAGE_AFTERMATH = "aftermath"
STAGE_KRAP_STATUS = "krap_status"
STAGE_MARU = "maru"
STAGE_COMMIT = "commit"
STAGE_DONE = "done"
