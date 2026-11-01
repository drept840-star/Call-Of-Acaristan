"""Mission 7 metadata and stage constants: Fallow Ground (skeleton).

Stages run in order: arrival, chores, runner, prep, raidin, raid, finale, choice.
This module owns identity and the stage ladder only; stage content lands
per stage later.
"""
MISSION7_ID = "MISSION_7"
MISSION7_KEY = "MISSION7"
MISSION7_TITLE = "Fallow Ground"
MISSION7_LOCATION = "Bodi's farm, Valea Seaca hills"

STAGE_ARRIVAL = "arrival"
STAGE_CHORES = "chores"
STAGE_RUNNER = "runner"
STAGE_PREP = "prep"
STAGE_RAIDIN = "raidin"
STAGE_RAID = "raid"
STAGE_FINALE = "finale"
STAGE_CHOICE = "choice"
STAGES = (STAGE_ARRIVAL, STAGE_CHORES, STAGE_RUNNER, STAGE_PREP,
          STAGE_RAIDIN, STAGE_RAID, STAGE_FINALE, STAGE_CHOICE)

STAGE_LABELS = {
    STAGE_ARRIVAL: "ARRIVAL",
    STAGE_CHORES: "CHORES",
    STAGE_RUNNER: "RUNNER",
    STAGE_PREP: "PREP",
    STAGE_RAIDIN: "RAID-IN",
    STAGE_RAID: "RAID",
    STAGE_FINALE: "FINALE",
    STAGE_CHOICE: "CHOICE",
}

# Stages that play a film on entry, and the timeline each one uses.
FILM_TIMELINES = {
    STAGE_ARRIVAL: "m7.arrival",
    STAGE_RUNNER: "m7.runner",
    STAGE_RAIDIN: "m7.raidin",
    STAGE_FINALE: "m7.finale",
}
OUTRO_TIMELINE = "m7.outro"

# Mid-stage films: these play without advancing the ladder.  The goat escape
# is requested by the chore handlers when the last chore lands, so Bodi's
# "one of them got out" is something the player has watched happen.
MID_GOAT_ESCAPE = "goat_escape"
MID_TIMELINES = {
    MID_GOAT_ESCAPE: "m7.goat.escape",
}

# Scene id -> (module in cutscenes, function name).  Loaded on first draw so
# the 3D stack stays out of game start-up.
M7_SCENES = {
    "m7_dropoff_lift": ("m7films", "dropoff_lift"),
    "m7_dropoff_field": ("m7films", "dropoff_field"),
    "m7_dropoff_fence": ("m7films", "dropoff_fence"),
    "m7_runner_ride": ("m7runner", "ride"),
    "m7_runner_meet": ("m7runner", "meet"),
    "m7_runner_folder": ("m7runner", "folder"),
    "m7_runner_plan": ("m7runner", "plan_insert"),
    "m7_runner_shotgun": ("m7runner", "shotgun_handover"),
    "m7_runner_gun": ("m7runner", "gun_insert"),
    "m7_raidin_road": ("m7films", "raidin_road"),
    "m7_raidin_yard": ("m7films", "raidin_yard"),
    "m7_burn_wide": ("m7films", "burn_wide"),
    "m7_burn_tractor": ("m7films", "burn_tractor"),
    "m7_burn_bodi": ("m7films", "burn_bodi"),
    "m7_burn_face": ("m7films", "burn_face"),
    "m7_endcard": ("m7films", "endcard"),
    "m7_goat_pen": ("m7goat", "pen"),
    "m7_goat_slip": ("m7goat", "slip"),
    "m7_goat_orchard": ("m7goat", "orchard"),
    "m7_goat_potatoes": ("m7goat", "potatoes"),
    "m7_goat_bodi": ("m7goat", "bodi"),
}


def _lazy_scene(module, name):
    def draw(surface, t_ms):
        import importlib
        mod = importlib.import_module("cutscenes." + module)
        return getattr(mod, name)(surface, t_ms)
    return draw


def _register_scenes():
    from core.cutscene_registry import register_scene_renderer
    for scene_id, (module, fn_name) in M7_SCENES.items():
        register_scene_renderer(scene_id, _lazy_scene(module, fn_name), replace=True)


_register_scenes()


def film_shots(stage):
    """Cutscene shots for a stage film or a mid-stage film (or an empty list)."""
    timeline = FILM_TIMELINES.get(stage) or MID_TIMELINES.get(stage)
    if not timeline:
        return []
    from game import timelines as _timelines
    return _timelines.shots(timeline, [])


def outro_shots():
    from game import timelines as _timelines
    return _timelines.shots(OUTRO_TIMELINE, [])
