
"""Package cutscenes - re-export facade. Parts: cast.py, cast3d.py, route12.py, m3cell.py, chair.py, m3ops.py, m3ko.py, m3broadcast.py, m3ending.py, m4aftermath.py, m5fx3d.py (M5 3D FX kit, imported only by m5martial3d/m5mid3d), m5martial3d.py (engine-dispatched), engine.py."""
"""Cutscene visuals and dialogue: character drawings, scene backgrounds, shot lists.

RPE6 Phase 2 (A-003): the mission-owned take modules (m3cell, m3ops, m3ko, m3broadcast,
m3ending, m4aftermath, m5martial*, m5mid3d) are no longer re-exported here; each mission
imports its own take modules from its meta module, which also registers their scene ids.
"""
from .cast import *  # noqa: F401,F403
from .cast3d import *  # noqa: F401,F403
from .route12 import *  # noqa: F401,F403
from .chair import *  # noqa: F401,F403
from .engine import *  # noqa: F401,F403
from .route12 import _ease_cutscene, _lerp_cutscene, _ca, _draw_handoff_pistol, _draw_handoff_molotov, _draw_route12_checkpoint_base, _draw_vertical_gradient, _draw_light_cone  # noqa: F401
from .chair import _pt, _cb_frame, _cb_composite_cell, _cb_tube_flicker, _draw_bloom_circle, _cb_get_camera_drift, _mote_data, _draw_dust_motes, _cb_vignette, _cb_grain_surf, _cb_get_grain, _cb_cinematic_grade, _cb_cinematic_bg, _cb_letterbox, _draw_cell_wall, _draw_cell_floor, _draw_interrogation_chair, _cb_clamp, _cb_smooth, _cb_ease_out, _cb_ease_out_cubic_m2, _cb_time_to_frames, _cb_camera_shake, _cb_surface_alpha_blit, _cb_draw_metal_leg, _cb_draw_shiv_spark, _cb_draw_chain_between, _cb_draw_forearm, _cb_draw_cuff, _cb_draw_biribel_seated_close, _cb_draw_stress_lines, _cb_draw_debris_burst, _cb_draw_flash, _cb_finish, _draw_cb_strain, _draw_cb_crack, _draw_cb_grab, _draw_cb_ready  # noqa: F401

del _mote_data, _cb_grain_surf


_LIVE_STATE = frozenset([
    "_dialogue_box_slide",
    "_mote_data",
    "_cb_grain_surf",
])

_LIVE_MODULES = (
    "cutscenes.engine",
    "cutscenes.m3ops",
    "cutscenes.chair",
    "cutscenes.m3cell",
    "cutscenes.route12",
    "cutscenes.cast",
    # Phase 4: the dialogue box owns its slide state now (engine.ui.std).
    "engine.ui.std.dialogue_box",
)


def __getattr__(name):
    """PEP 562 live view for rebound shared state (see _LIVE_STATE)."""
    if name in _LIVE_STATE:
        import sys as _sys2
        for _mod in _LIVE_MODULES:
            _m = _sys2.modules.get(_mod)
            if _m is not None and name in vars(_m):
                return vars(_m)[name]
    raise AttributeError(
        "module " + repr(__name__) + " has no attribute " + repr(name))
