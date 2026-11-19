"""Mission 8 metadata: identity, the two stage ladders and the beat scripts.

``STATE.m8_route`` (written by the Mission 7 radio choice) picks the ladder.
Revenge runs meet, trap, gantry, friends, kill, descent, chase, epilogue.  Duty runs
approach, mansion, liftoff, flight, crash, ridge, epilogue.
"""
MISSION8_ID = "MISSION_8"
MISSION8_KEY = "MISSION8"
MISSION8_TITLE = "The Call"
MISSION8_LOCATION = "Route 12 toll plaza"

ROUTE_DUTY = "duty"
ROUTE_REVENGE = "revenge"
ROUTES = (ROUTE_DUTY, ROUTE_REVENGE)

STAGE_MEET = "meet"
STAGE_TRAP = "trap"
STAGE_GANTRY = "gantry"
STAGE_FRIENDS = "friends"
STAGE_KILL = "kill"
STAGE_DESCENT = "descent"
STAGE_CHASE = "chase"
STAGE_EPILOGUE = "epilogue"
REVENGE_STAGES = (STAGE_MEET, STAGE_TRAP, STAGE_GANTRY, STAGE_FRIENDS,
                  STAGE_KILL, STAGE_DESCENT, STAGE_CHASE, STAGE_EPILOGUE)

STAGE_D_APPROACH = "d_approach"
STAGE_MANSION = "mansion"
STAGE_LIFTOFF = "liftoff"
STAGE_FLIGHT = "flight"
STAGE_CRASH = "crash"
STAGE_RIDGE = "ridge"
STAGE_D_EPILOGUE = "d_epilogue"
DUTY_STAGES = (STAGE_D_APPROACH, STAGE_MANSION, STAGE_LIFTOFF,
               STAGE_FLIGHT, STAGE_CRASH, STAGE_RIDGE, STAGE_D_EPILOGUE)

# The trap and the gantry are one continuous 3D scene; the gantry is its
# last phase, recorded as its own stage so a save resumes at the ladder.
FIGHT_STAGES = (STAGE_TRAP, STAGE_GANTRY)

STAGE_LABELS = {
    STAGE_MEET: "THE MEET",
    STAGE_TRAP: "THE TRAP",
    STAGE_GANTRY: "THE GANTRY",
    STAGE_FRIENDS: "OLD FRIENDS",
    STAGE_KILL: "THE KILL",
    STAGE_DESCENT: "THE DESCENT",
    STAGE_CHASE: "THE TRACTOR CHASE",
    STAGE_EPILOGUE: "EPILOGUE",
    STAGE_D_APPROACH: "APPROACH",
    STAGE_MANSION: "THE MANSION",
    STAGE_LIFTOFF: "LIFTOFF",
    STAGE_FLIGHT: "LAST FLIGHT",
    STAGE_CRASH: "THE CRASH",
    STAGE_RIDGE: "THE RIDGE",
    STAGE_D_EPILOGUE: "EPILOGUE",
}

OPERATIONS = {ROUTE_DUTY: "HEAD OF STATE", ROUTE_REVENGE: "OLD FRIENDS"}

# 3D beats: (speaker, text) lines, ENTER steps through them.  The trap, the
# gantry, the kill, the chase, the mansion, the flight and the ridge are
# playable scenes with no lines here.
# An empty speaker is a caption.  Spoken lines match the VO_xxx rows in
# audio/voice_manifest.py (caption-only until takes exist).
BEATS = {
    STAGE_MEET: (
        ("", "Dawn. Route 12. The toll gantry, the burned cars - rebuilt, quiet."),
        ("BODI", "I'll drive. You think."),
        ("", "Vasile picked the place. The catwalk where the sniper lay."),
    ),
    STAGE_FRIENDS: (
        ("VASILE", "You picked the four over the three hundred."),
        ("BIRIBEL", "You didn't pick the three hundred. You picked the desk."),
        ("VASILE", "...Maybe. Maybe both. Does it matter to them?"),
        ("VASILE", "I taught you to shoot on this kind of morning. Cold barrel, steady hands."),
        ("VASILE", "I chose the many. You chose the four."),
    ),
    STAGE_DESCENT: (
        ("BODI", "Get on."),
    ),
    STAGE_EPILOGUE: (
        ("ALEX", "Biribel - the mansion, they were waiting for us. Maru's down. I'm sorry. I'm sorry-"),
        ("PRESIDENT", "The terrorist Maru is dead. The traitor Biribel will be found."),
        ("", "Night. The estate, lit and empty. A closed state funeral in the grounds. No family."),
        ("ANCHOR", "...the state buries the man who attacked the presidential residence."),
        ("ANCHOR", "...appointed Commander of the Presidential Guard, Andrei Bogdan Velicu."),
        ("", "The Kim Kim border. The train Volkov never caught. Bodi's tractor on the tracks, smoking, lights out."),
        ("", "Ucilev at the border post, holding Biribel's photo. He watches the train go."),
        ("BIRIBEL", "Gabi, Seby, Darius. It's done. He's gone."),
        ("BIRIBEL", "Volkov - I caught your train. The coffee's terrible."),
        ("", "CALL OF ACARISTAN"),
    ),
    STAGE_D_APPROACH: (
        ("VASILE", "Guard rotations change at the fountain. Two on the doors, four on the lawn."),
        ("VASILE", "I've bought you ten minutes on the perimeter feed. Get to the study."),
    ),
    STAGE_LIFTOFF: (
        ("BIRIBEL", "He's lifting off!"),
        ("MARU", "Door's open, Biribel! Jump!"),
    ),
    STAGE_CRASH: (
        ("MARU", "Leg's gone. Take the rifle - he went down past the ridge."),
        ("BIRIBEL", "I'll come back for you."),
        ("MARU", "You'd better."),
    ),
    STAGE_D_EPILOGUE: (
        ("ANCHOR", "Interim President Vasile takes the oath this morning, on the steps of the old courthouse."),
        ("VASILE", "We owe this morning to soldiers whose names you will never know."),
        ("BIRIBEL", "Gabi, Seby, Darius. Volkov. The country's free. I wanted to tell you that."),
        ("BIRIBEL", "I didn't want to tell you who's holding it."),
        ("", "CALL OF ACARISTAN"),
    ),
}


def stages_for(route):
    """Stage ladder for a route; anything but duty plays Revenge."""
    return DUTY_STAGES if route == ROUTE_DUTY else REVENGE_STAGES


def first_stage(route):
    return stages_for(route)[0]


# --- films ---------------------------------------------------------------------
# The meet, Old Friends, the descent and the epilogue play as 3D films on the house
# cutscene player (``cutscenes/m8films.py``); ``beats`` stays as the fallback
# when a timeline has no shots.

FILM_TIMELINES = {
    STAGE_MEET: "m8.meet",
    STAGE_FRIENDS: "m8.friends",
    STAGE_DESCENT: "m8.descent",
    STAGE_EPILOGUE: "m8.epilogue",
    STAGE_D_APPROACH: "m8.d_approach",
    STAGE_LIFTOFF: "m8.d_liftoff",
    STAGE_CRASH: "m8.d_crash",
    STAGE_D_EPILOGUE: "m8.d_epilogue",
    "heli": "m8.heli",
}

M8_SCENES = {
    "m8_meet_dawn": ("m8films", "meet_dawn"),
    "m8_meet_drive": ("m8films", "meet_drive"),
    "m8_meet_gantry": ("m8films", "meet_gantry"),
    "m8_meet_walk": ("m8films", "meet_walk"),
    "m8_friends_catwalk": ("m8films", "friends_catwalk"),
    "m8_friends_four": ("m8films", "friends_four"),
    "m8_friends_desk": ("m8films", "friends_desk"),
    "m8_friends_matter": ("m8films", "friends_matter"),
    "m8_friends_taught": ("m8films", "friends_taught"),
    "m8_friends_chose": ("m8films", "friends_chose"),
    "m8_friends_raise": ("m8films", "friends_raise"),
    "m8_descent_body": ("m8films", "descent_body"),
    "m8_descent_ladder": ("m8films", "descent_ladder"),
    "m8_descent_geton": ("m8films", "descent_geton"),
    "m8_descent_pullout": ("m8films", "descent_pullout"),
    "m8_epi_radio": ("m8films", "epi_radio"),
    "m8_epi_president": ("m8films", "epi_president"),
    "m8_epi_estate": ("m8films", "epi_estate"),
    "m8_epi_casket": ("m8films", "epi_casket"),
    "m8_epi_commander": ("m8films", "epi_commander"),
    "m8_epi_crossing": ("m8films", "epi_crossing"),
    "m8_epi_ucilev": ("m8films", "epi_ucilev"),
    "m8_epi_names": ("m8films", "epi_names"),
    "m8_epi_volkov": ("m8films", "epi_volkov"),
    "m8_epi_title": ("m8films", "epi_title"),
    "m8_heli_road": ("m8films", "heli_road"),
    "m8_heli_retardovici": ("m8films", "heli_retardovici"),
    "m8_heli_flyby": ("m8films", "heli_flyby"),
    "m8_heli_lockon": ("m8films", "heli_lockon"),
    "m8d_approach_aerial": ("m8dutyfilms", "approach_aerial"),
    "m8d_approach_gate": ("m8dutyfilms", "approach_gate"),
    "m8d_liftoff_study": ("m8dutyfilms", "liftoff_study"),
    "m8d_liftoff_window": ("m8dutyfilms", "liftoff_window"),
    "m8d_liftoff_maru": ("m8dutyfilms", "liftoff_maru"),
    "m8d_crash_spin": ("m8dutyfilms", "crash_spin"),
    "m8d_crash_black": ("m8dutyfilms", "crash_black"),
    "m8d_crash_fire": ("m8dutyfilms", "crash_fire"),
    "m8d_inauguration": ("m8dutyfilms", "inauguration"),
    "m8d_vasile_speech": ("m8dutyfilms", "vasile_speech"),
    "m8d_crowd": ("m8dutyfilms", "crowd"),
    "m8d_eyes": ("m8dutyfilms", "eyes"),
    "m8d_biribel_vo": ("m8dutyfilms", "biribel_vo"),
    "m8d_title_card": ("m8dutyfilms", "title_card"),
}


def _lazy_scene(module, name):
    def draw(surface, t_ms):
        import importlib
        mod = importlib.import_module("cutscenes." + module)
        return getattr(mod, name)(surface, t_ms)
    return draw


def _register_scenes():
    from core.cutscene_registry import register_scene_renderer
    for scene_id, (module, fn_name) in M8_SCENES.items():
        register_scene_renderer(scene_id, _lazy_scene(module, fn_name), replace=True)


_register_scenes()


HELI_SHOTS = (
    {
        "scene": "m8_heli_road",
        "speaker": "BODI",
        "text": "Static on the band... Wait. Do you hear that?",
        "min_ms": 3400,
        "cues": [[150, "radio_static", 0.25]],
    },
    {
        "scene": "m8_heli_retardovici",
        "speaker": "RETARDOVICI",
        "text": "Put the bird on Route 12. Bring in the big guns - nothing crosses Kim Kim.",
        "min_ms": 4800,
        "cues": [[120, "squelch_head", 0.22]],
    },
    {
        "scene": "m8_heli_flyby",
        "speaker": "BIRIBEL",
        "text": "Bodi - heads down!",
        "min_ms": 3800,
        "auto_advance": True,
        "cues": [[2100, "wind_gust", 0.40]],
    },
    {
        "scene": "m8_heli_lockon",
        "self_graded": True,
        "full_frame": True,
        "cut_to_play": True,
        "speaker": "",
        "text": "",
        "min_ms": 2400,
        "auto_advance": True,
        "quiet_ui": True,
    },
)


def film_shots(stage):
    """Cutscene shots for a stage film (or an empty list)."""
    timeline = FILM_TIMELINES.get(stage)
    if not timeline:
        return []
    fallback = list(HELI_SHOTS) if stage == "heli" else []
    try:
        from game import timelines as _timelines
        return _timelines.shots(timeline, fallback)
    except Exception:
        return fallback
