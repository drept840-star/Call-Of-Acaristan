"""Mission 4 - part module. See __init__.py for the package facade."""
"""Mission 4: The Aftermath (working title) - the world after the broadcast.

Picks up two days after Mission 3's Vostral transmission. The regime is
reeling: Balaceanu's career is public record, Retardovici's strings are
cut (the read on the night - a cape without a handler; M5 shows the cape
was the puppeteer all along), and KRAP is left without clear direction.
Volkov has vanished across the border to Regatul Kim Kim. Vasile and
Biribel are the only ones left trying to figure out what comes next - KRAP
doesn't fully dissolve but "kind of dissolves," its remnants allied with
MAG, while Maru steps into physical presence for the first time.

The framing is no longer "mission assigned" but "what do we do now":
KRAP's ambiguous status, Maru's reappearance, and Biribel's own path
away from the soldier's life - without making him a fugitive.

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
    "retardovici": "Retardovici's cape is gone, so the regime's survival is uncertain.",
    "krap_status": "KRAP kind of dissolves; its remnants ally with MAG, direction unclear.",
    "volkov_left": "Volkov has left Acaristan for Regatul Kim Kim, leaving a vacuum.",
    "maru_present": "Maru now has physical presence: formerly a voice, now on the ground.",
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
# barricade (solid), H/h car hulk (solid, east-west / north-south), W weak
# wall (solid until the wave-4 breach), "." asphalt, "d" sidewalk, "R" lane
# paint (overlay), "D" door gap (walkable), "O" interior floor, "L" corridor
# floor, "F" entry-hall floor, "b" door barricade site, "w" window barricade
# site (both walkable until something is built on them), "A" APC lane, "Z"
# loyalist insertion point, "E" guard spawn, "M" marksman spawn, "J" jammer
# spot, "T" transmitter (rack area centre), "N" Maru's meet anchor. Solid
# set consumed by world._parse_grid.
M4_SOLID_CHARS = ("C", "B", "H", "h", "W")

# Key tiles (col, row). Street map: NW cross-streets, boulevard mid,
# radio station east.
PLAYER_START_TILE = (9, 4)     # street intersection between the blocks (V+H lane)
VASILE_START_TILE = (10, 4)    # Vasile starts beside Biribel, carrying the cache
VASILE_CACHE_TILE = (16, 21)   # legacy cache drop (Vasile carries it now)
STATION_DOOR_TILE = (34, 19)   # western face of the station block, off the boulevard
# Station map (36x28): the building with its forecourt and street ring.
STATION_W, STATION_H = 36, 28
STATION_BUILDING = (6, 4, 24, 18)   # (col, row, w, h): outer walls cols 6-29, rows 4-21
STATION_START_TILE = (17, 23)   # Biribel arrives on the forecourt, outside the main door
VASILE_ARRIVE_TILE = (18, 23)
TRANSMITTER_TILE = (18, 7)      # rack-area centre (the siege's hold point)
JAMMER_TILE = (18, 6)           # jammer install point in front of the TX rack
LIAISON_TILE = (17, 16)         # Maru's meet anchor in the entry hall
VASILE_STATION_TILE = (16, 8)   # Vasile's post by the rack
RESPAWN_TILE = (18, 9)          # wave restart: Biribel by the rack
RACK_TILES = (15, 5, 7)         # (col, row, width) of the rack along the hall's north wall
APC_STOP_RECT = (16, 22, 4, 3)  # tiles the rammed APC occupies (solid cover after wave 5)

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

# Escort (street): Vasile carries the KRAP comms cache, which is the supply
# pool. One revive; his next down kills him and fails the street.
M4_SUPPLY_START = 24
M4_SUPPLY_DROP_FRAC = 0.25      # first down spills a quarter of the cache
M4_VASILE_HP = 220
M4_REVIVE_WINDOW = 600          # frames to reach a downed Vasile (10 s)
M4_REVIVE_HOLD = 120            # hold E for 2 s
M4_REVIVE_RADIUS = 70

# Fortify. kind -> (label, cost, hp). Door sites take planks or plate,
# window sites take boards.
M4_BARRICADE_KINDS = {
    "planks": ("PLANKS", 3, 300),
    "plate": ("STEEL PLATE", 6, 700),
    "boards": ("BOARDS", 2, 260),
}
M4_BUILD_HOLD = 45              # frames of held E to put a barricade up
M4_REPAIR_STEP = 90             # 1.5 s per repair step
M4_REPAIR_FRAC = 0.25           # each step restores a quarter of max hp
M4_REPAIR_COST = 1
M4_BAR_FIRE_MUL = 0.5            # rifle rounds only chip a barricade
M4_SITE_RADIUS = 80             # how close Biribel stands to build or repair
M4_RUNNER_SUPPLY = 3            # MAG runners bring timber before waves 2-5
M4_JAMMER_COUNTDOWN = 600       # 10 s from install to the first wave

# Siege. Waves come from content/m4/waves.json; the arrest beats run on the
# same frame clock.
M4_SIEGE_FRAMES = 28800         # 8 minutes at 60 fps
M4_HOLD_SECONDS = M4_SIEGE_FRAMES // 60   # the hold the arrest plays out over
M4_WAVE_GRACE = 300             # a wave restart drops you 5 s before the wave
M4_RACK_RADIUS = 200            # loyalists this close to the rack hold it
M4_RACK_HOLD_FAIL = 480         # 8 s held fails the wave
M4_BREACH_CHARGE = 240          # a breacher's charge on plate burns 4 s
M4_SOLDIER_HP = 160
M4_SOLDIER_DMG_TAKEN = 0.6
M4_CIVILIAN_HP = 100
M4_FOCUS_VASILE = 0.35          # share of street shooters that pick Vasile when they see him
M4_LEASH_NEAR = 96              # Vasile stops this close to Biribel
M4_LEASH_FAR = 150              # and starts walking again past this
M4_DOOR_ESCORT_RADIUS = 220     # Vasile must be this close for the station door to open

# Station posts: (cover tile, watched opening). Every cover tile is open
# floor inside the building with a clear line to the opening it watches.
M4_POSTS = {
    "rack": ((16, 8), (12, 4)),
    "main_w": ((16, 17), (17, 21)),
    "main_e": ((19, 17), (18, 21)),
    "studio": ((26, 16), (29, 17)),
    "office": ((9, 16), (6, 16)),
    "corridor_e": ((24, 12), (28, 11)),   # faces the weak wall (solid until wave 4)
    "tx_window": ((22, 6), (23, 4)),
}
# Who joins after the Maru meet, per tone (0 = "the state", 1 = "the people").
# (name, look, weapon, post, coat tint)
M4_SQUADS = {
    0: (("SGT. DRAGAN", "soldier", "rifle", "main_w", None),
        ("PVT. ILIESCU", "soldier", "rifle", "studio", None)),
    1: (("TOMA", "civilian", "pistol", "main_w", (82, 64, 52)),
        ("ANCA", "civilian", "shotgun", "studio", (60, 70, 84)),
        ("BOGDAN", "civilian", "pistol", "office", (70, 76, 58)),
        ("ILEANA", "civilian", "pistol", "corridor_e", (88, 58, 62))),
}
M4_SQUAD_ENTRY_TILE = (18, 19)   # the squad comes in through the entry hall

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
    "breacher": {"hp": 75, "speed": 2.5},
}

# ─────────────────────────────────────────────
# Cutscene shot-lists (W5: real finale + intro art)
# ─────────────────────────────────────────────
# Scene names dispatch through cutscenes/engine.py::draw_cutscene_scene to the
# bespoke draws in cutscenes/m4aftermath.py. The intro opens on its own street
# frame (m4_street_curfew) rather than reusing the M3 ending's screen wall, so
# the campaign's second day starts where the first one left the capital.
# Schema mirrors the M2/M3 convention: scene / speaker / text / lighting /
# min_ms. "Keep these names: acaristan.py uses them."
import game.timelines as _timelines  # RPE6 P8: timeline data access
mission4_intro_shots = [
    {
        "scene": "m4_street_curfew",
        "speaker": "NARRATOR",
        "text": "Forty-eight hours after the Vostral, the address is still\nreading on every screen in the capital.",
        "lighting": (10, 14, 20),
        "min_ms": 4200,
        "caption_after_ms": 2400,
        "quiet_ui": True,
        "cues": ((0, "rain", 0.3), (300, "radio_static", 0.12),
                 (1500, "gunshot_distant", 0.22), (2600, "footstep_walk", 0.14)),
    },
    {
        "scene": "m4_city_curfew",
        "speaker": "VASILE",
        "text": "And this is what it bought us. A curfew nobody can enforce\nand a regime that shoots its own order.",
        "lighting": (12, 10, 16),
        "min_ms": 3400,
        "caption_after_ms": 1800,
        "quiet_ui": True,
        "cues": ((0, "radio_static", 0.1), (1200, "gunshot_distant", 0.18),
                 (2200, "m4_breath", 0.3)),
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

# Provisional phase table - narrative flow matching the new direction.
# Not the runtime driver - STATE.mission4_stage is (mirrors M3).
MISSION_PHASES = [
    {"phase": 1, "name": "Aftermath", "objective": "Process the broadcast's fallout; Volkov is gone."},
    {"phase": 2, "name": "KRAP Status", "objective": "Determine if KRAP allies with MAG or dissolves further."},
    {"phase": 3, "name": "Maru Reappears", "objective": "Maru's first physical appearance; new assets available."},
    {"phase": 4, "name": "New Direction", "objective": "Vasile and Biribel decide their own path. Not a mission, their choice."},
]

# ─────────────────────────────────────────────
# Runtime stage enum
# ─────────────────────────────────────────────
STAGE_INTRO = "intro"
STAGE_ESCORT = "escort"        # curfew street: walk Vasile and the cache to the station
STAGE_FORTIFY = "fortify"      # station: barricades, the Maru meet, the jammer
STAGE_SIEGE = "siege"          # 5 waves while the arrest airs
STAGE_DONE = "done"
STAGE_AFTERMATH = STAGE_ESCORT  # pre-overhaul name, still read by the 3D set
