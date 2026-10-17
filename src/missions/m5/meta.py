"""Mission 5 - part module. See __init__.py for the package facade.

Mission 5: Martial Law. One night under emergency rule. Retardovici has
dissolved parliament and folded KRAP into the Presidential Guard under
Commander Vasile. Vasile orders Biribel to bring Maru in; Biribel gets
Maru out instead - through the Guard's raid on the MAG print works, down
the basement tunnel to the river, past an operator the state says is dead:
Ucilev Nadgob Ierdna.

Dependency-free on purpose (no pygame, no game imports) - same contract
as core.mapbuilder / missions.m4.meta.
"""

MISSION5_ID = "MISSION_5"
MISSION5_KEY = "MISSION5"
MISSION5_TITLE = "Martial Law"
MISSION5_LOCATION = "Acaristan - the capital under emergency rule"

MISSION5_STORY_FLAGS = {
    "balaceanu_dead": "Balaceanu found dead in his cell. 'Suicide.'",
    "emergency_rule": "Parliament suspended; the Presidential Guard replaces KRAP.",
    "vasile_commander": "Vasile commands the Guard - and is never surprised.",
    "maru_hunted": "Maru is on the President's list.",
    "ucilev": "Ucilev Nadgob Ierdna - listed dead two years ago - leads the raid.",
}

# ────────────────────────────────────────────
# Map / runtime constants
# ────────────────────────────────────────────
TILE = 64  # mirrors core.config.TILE_SIZE

# Tile grammar (shared with M4 so its art pipeline can be ported):
#   C solid block/wall   B barricade/wreck (solid)   H press machine (solid)
#   . asphalt   d sidewalk   O interior floor   L corridor floor
#   F foyer floor   D door gap   S basement stair   W shallow water (walkable)
# Markers stamped on floor after validation:
#   P player start   E guard spawn   M marksman spawn   N Maru
#   X exit / objective   G river gate   I raid insertion point
M5_SOLID_CHARS = ("C", "B", "H")
M5_WALKABLE_TILES = ".dOLFDSWPEMNXGI"

# Guard HQ (30x16) - the old KRAP depot, walked (phase 2, STAGE_HQ). No
# combat: the player is disarmed, squadmates bark on proximity, Vasile's
# office dialogue (VASILE_OFFICE_LINES) hands off to the Lower Quarter.
HQ_W, HQ_H = 30, 16
HQ_START_TILE = (2, 12)               # locker hall (south-west)
VASILE_TILE = (24, 2)                 # behind the desk with the flag
VASILE_DESK_FRONT_TILE = (24, 5)      # stand here -> office dialogue
HQ_OFFICE_RADIUS = 110
HQ_BARK_RADIUS = 96
# Ambient squadmates: (col, row, name, guard_armband?, bark).
HQ_NPCS = (
    (4, 10, "OLD SQUADMATE", True,
     "New armband, same boots. Don't look at me like that, Biribel."),
    (6, 14, "EMPTY LOCKER", False,
     "A name taped over with black. Third one on this row."),
    (15, 11, "DESK SERGEANT", True,
     "Half the unit signed. The other half... nobody says where they went."),
    (12, 6, "RECRUIT", True,
     "Commander's office is at the end. He's in a good mood. Scary good."),
    (26, 12, "ARMORER", False,
     "They're painting the vans black. Still got KRAP blue under my nails."),
)

# Lower Quarter (40x30) - night streets, depot (west) -> print works (east).
QUARTER_W, QUARTER_H = 40, 30
QUARTER_START_TILE = (2, 15)
PRINTWORKS_DOOR_TILE = (34, 15)       # west face of the print-works block
QUARTER_TRAM_TILES = ((24, 14), (25, 14), (26, 14))   # burning tram (solid)
# Checkpoint barricades leave a one-lane gap (stealth chokepoints).
QUARTER_CHECKPOINTS = (
    {"name": "Depot Gate", "col": 9, "gap_row": 15},
    {"name": "Tram Junction", "col": 20, "gap_row": 16},
    {"name": "Print Street", "col": 30, "gap_row": 14},
)
# Guard spawns: (col, row, kind, patrol?) - kind "guard" | "marksman".
QUARTER_GUARDS = (
    # 7 posts (was 10); KOVAC/SANDU at 31_15/31_13 stay passive -> 5 hostiles.
    (10, 14, "guard", False),
    (21, 17, "guard", True),
    (31, 15, "guard", False), (31, 13, "guard", False),
    (13, 5, "guard", True), (23, 24, "guard", True),
    (32, 5, "marksman", False),
)

# Print works (26x20) - presses, paper stacks, Maru upstairs office.
PRINT_W, PRINT_H = 26, 20
PRINT_START_TILE = (3, 17)
MARU_TILE = (20, 4)                   # back office, north-east
BASEMENT_STAIR_TILE = (22, 16)        # stair down to the tunnel
RAID_INSERTION_TILES = ((2, 17), (12, 18), (24, 10))   # front, loading bay, roof stair

# Tunnel (48x12) - basement to the river gate.
TUNNEL_W, TUNNEL_H = 48, 12
TUNNEL_START_TILE = (2, 6)
TUNNEL_MARU_START_TILE = (2, 5)
RIVER_GATE_TILE = (45, 6)
TUNNEL_PURSUIT_TILES = ((1, 5), (1, 6))

# Raid: survive waves among the presses (timer-driven, never kill-gated -
# M3 exfil-door lesson; the clock always ends the raid).
M5_RAID_SECONDS = 70
M5_RAID_MAX_CONCURRENT = 5
# Tunnel escort: Maru wounded (arm), slow.
M5_MARU_MAX_HP = 160
M5_MARU_SPEED = 2.1       # px/frame, player is 3.6
M5_MARU_LEASH = 150       # Maru waits if Biribel is further than this ahead
M5_PURSUIT_INTERVAL = 360 # frames between pursuit squads in the tunnel

M5_ROLE_TUNING = {
    "guard": {"hp": 95, "speed": 2.0},
    "marksman": {"hp": 70, "speed": 1.6},
    "raider": {"hp": 110, "speed": 2.3},
}

# Speaker colors.
C_SYSTEM = (150, 170, 190)
C_VASILE = (110, 160, 220)
C_MARU = (110, 200, 140)
C_GUARD = (210, 70, 70)
C_UCILEV = (190, 190, 200)
C_RETARDOVICI = (230, 200, 120)
BIRIBEL_SPEAKER = (225, 228, 232)

# ─────────────────────────────────────────────
# Cutscene shot-lists (scene / speaker / text / lighting / min_ms).
# Scenes m5_* are drawn by cutscenes/m5martial.py (W5); until then the
# engine's title-card style fallback renders the caption.
# ─────────────────────────────────────────────
import game.timelines as _timelines  # RPE6 P8: timeline data access
mission5_intro_shots = [
    {"scene": "m5_tv_bulletin", "speaker": "ANCHOR",
     "text": "Former Prime Minister Balaceanu was found dead in his cell this morning. Preliminary findings: suicide.",
     "lighting": (10, 12, 18), "min_ms": 4200},
    {"scene": "m5_safehouse_tv", "speaker": "BIRIBEL",
     "text": "Suicide. He didn't have the spine for it.",
     "lighting": (12, 10, 10), "min_ms": 3000},
    {"scene": "m5_retardovici_tv", "speaker": "PRESIDENT",
     "text": "Parliament is suspended. KRAP is dissolved into my Presidential Guard - every one of you now answers to me.",
     "lighting": (14, 10, 8), "min_ms": 4600},
    # Make the new allegiance explicit: Biribel is the President's man now,
    # and the black-clad Guard he will end up fighting is his own old unit.
    {"scene": "m5x_decree", "speaker": "BIRIBEL",
     "text": "Decree Number One. No more KRAP - I'm the President's man now. We all are.",
     "lighting": (14, 12, 10), "min_ms": 4000},
    {"scene": "m5x_squadmate", "speaker": "OLD SQUADMATE",
     "text": "Same squad, new colours, Biribel. Y-3 intake - we've always covered each other. Right?",
     "lighting": (14, 12, 10), "min_ms": 4200},
    # The forced change (core.outfits): from here on he wears the black in
    # every M5 view, but keeps the KRAP patch and leaves the helmet behind.
    # min_ms == cutscenes.m5mid3d._CH_END: the patch close-up + silent beat
    # always play (T2).
    {"scene": "m5x_change", "speaker": "QUARTERMASTER",
     "text": "Tunic, armband, helmet. Sign for them. The blue goes in the bin, Biribel.",
     "lighting": (14, 12, 10), "min_ms": 7700},
    {"scene": "m5x_barracks", "speaker": "BIRIBEL",
     "text": "My whole unit in the President's black. If this turns, I'll be shooting at my friends.",
     "lighting": (14, 12, 10), "min_ms": 4400},
    {"scene": "title_card", "speaker": "",
     "text": "MISSION 5\nMARTIAL LAW", "lighting": (5, 5, 8), "min_ms": 2000},
]
mission5_intro_shots = _timelines.shots("m5.intro", mission5_intro_shots)  # RPE6 P8: timeline data

# Vasile's office (phase 2) - played as an in-engine dialogue (W6); kept
# here as data so the walking sim and the smoke test share one source.
VASILE_OFFICE_LINES = [
    ("VASILE", "Commander. Me. Can you believe it? They gave me a desk with a flag on it."),
    ("VASILE", "Maru's on a list. Not my list - his. If the Guard finds them first, they're shot."),
    ("VASILE", "Bring them in quietly and I can keep them breathing. That's all I'm asking."),
    ("BIRIBEL", "And if I say no?"),
    ("VASILE", "Then somebody else goes. Somebody who doesn't care whether they breathe."),
]

# Round 2: mid-mission cutscenes (cutscenes/m5mid3d.py). Requested from flow via
# STATE.request_m5_cutscene = key; app.py plays them and resumes with
# flow.on_m5_cutscene_done(key). The text mirrors the in-game beats, which are
# finished instantly on resume (headless/smoke paths still use the in-game box).
_VASILE_TAKES = ("m5x_vasile_wide", "m5x_vasile_close", "m5x_vasile_close",
                 "m5x_vasile_biribel", "m5x_vasile_lean")
M5_MARU_LINES = [
    ("MARU", "Biribel. Vasile sent you. Of course he did.", "m5x_maru_two"),
    ("BIRIBEL", "He wants you brought in. Breathing, he says.", "m5x_maru_biribel"),
    ("MARU", "Breathing in a Guard cell. Balaceanu was breathing too, last week.", "m5x_maru_close"),
    ("BIRIBEL", "Then we don't go to the cell. Is there another way out?", "m5x_maru_biribel"),
    ("MARU", "Basement. The old tunnel runs to the river. If we live long enough to reach it.", "m5x_maru_close"),
]
M5_MID_CUTSCENES = {
    "old_faces": [
        {"scene": "m5x_faces_wide", "speaker": "KOVAC",
         "text": "Hold it. ...Biribel? I know that walk.",
         "lighting": (12, 14, 22), "min_ms": 2800},
        {"scene": "m5x_faces_kovac", "speaker": "BIRIBEL",
         "text": "Kovac. Sandu. Same checkpoint, different colours.",
         "lighting": (12, 14, 22), "min_ms": 3000},
        {"scene": "m5x_faces_sandu", "speaker": "SANDU",
         "text": "Patrol's turning back. Print works are through there. Keep your head down.",
         "lighting": (12, 14, 22), "min_ms": 3800},
        {"scene": "m5x_faces_release", "speaker": "KOVAC",
         "text": "Go. We didn't see you. Don't make us regret it.",
         "lighting": (12, 14, 22), "min_ms": 3000},
    ],
    "arrival": [
        {"scene": "m5x_pw_arrival_wide", "speaker": "",
         "text": "The MAG Print Works. Four floors of brick, and the presses still run.",
         "lighting": (12, 14, 22), "min_ms": 5200},
        {"scene": "m5x_pw_arrival_door", "speaker": "BIRIBEL",
         "text": "Loading door's open. Either they trust me, or someone wants me inside.",
         "lighting": (12, 14, 22), "min_ms": 3600},
    ],
    "descent": [
        {"scene": "m5x_basement_descent", "speaker": "", "text": "",
         "lighting": (8, 10, 12), "min_ms": 4200,
         "cues": [(450, "door_open", 0.3), (1200, "footstep", 0.25)]},
    ],
    "vasile": [{"scene": sc, "speaker": who, "text": text, "lighting": (14, 12, 12),
                "min_ms": 3400}
               for sc, (who, text) in zip(_VASILE_TAKES, VASILE_OFFICE_LINES)],
    "maru": [{"scene": sc, "speaker": who, "text": text, "lighting": (14, 12, 10),
              "min_ms": 3400} for who, text, sc in M5_MARU_LINES] + [
        {"scene": "m5x_breach_lights", "speaker": "",
         "text": "[ Engines outside. Red and blue on the windows. ]",
         "lighting": (20, 8, 8), "min_ms": 2600},
        {"scene": "m5x_breach", "speaker": "",
         "text": "[ The doors come in. A shape in the light - no face, just the rifle. ]",
         "lighting": (20, 8, 8), "min_ms": 3800},
    ],
}

# Fresh, self-contained 3D finale. No retired shot/camera/pose data reused.
from .finale_script import FINAL_SHOT, SCENE as _FINALE_SCENE
mission5_ending_shots = [FINAL_SHOT]
mission5_ending_shots = _timelines.shots("m5.ending", mission5_ending_shots)  # RPE6 P8: timeline data


def _draw_shadow_finale(surface, t_ms):
    """Renderer for the finale scene id; the dispatcher finds it via core.cutscene_registry."""
    from cutscenes.m5shadow3d import draw  # lazy: heavy 3D take, loaded on its first frame
    draw(surface, t_ms)


# RPE6 A-003: M5 owns the martial-law takes; importing the module registers their
# scene ids (3D with 2D fallback) alongside the finale registered below.
from cutscenes import m5martial3d  # noqa: F401
from core.cutscene_registry import register_scene_renderer as _register_scene_renderer
_register_scene_renderer(_FINALE_SCENE, _draw_shadow_finale)

MISSION_PHASES = [
    {"phase": 1, "name": "Bulletin", "objective": "-"},
    {"phase": 2, "name": "Guard HQ", "objective": "Report to Vasile."},
    {"phase": 3, "name": "Lower Quarter", "objective": "Reach the print works before the Guard."},
    {"phase": 4, "name": "The Print Works", "objective": "Find Maru; get them to the basement."},
    {"phase": 5, "name": "The Tunnel", "objective": "Escort Maru to the river."},
    {"phase": 6, "name": "The Shadow", "objective": "Discover who is watching."},
]

# ─────────────────────────────────────────────
# Runtime stage enum (STATE.mission5_stage)
# ─────────────────────────────────────────────
STAGE_INTRO = "intro"
STAGE_HQ = "hq"
STAGE_QUARTER = "quarter"
STAGE_PRINTWORKS = "printworks"
STAGE_RAID = "raid"
STAGE_TUNNEL = "tunnel"
STAGE_DONE = "done"
