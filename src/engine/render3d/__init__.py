"""engine.render3d - declarative 3D sets (RPE6 §6.7, Phase 8).

This package is the data half of the 3D bridge: ``ae.set3d/1`` documents
describe a set (fog, light, primitive nodes, ``repeat`` stencils,
``prop_ref`` library sub-sets, decals with geometric fallbacks), and
``build`` flattens them into an ordered primitive list with every
expression evaluated.  It deliberately knows nothing about renderers -
the game-side bridge (`game.render3d_bridge`) owns the renderer pool, the
backend failure latch and presentation, and turns primitives into
``engine3d`` meshes.  Camera/light *tracks* live in ``engine.timeline``.
"""
from __future__ import annotations

from .scene3d import SCHEMA, Scene3D, Set3DError, build, from_dict, load_set3d, loads_set3d, validate
from .presets import PRESET_SCHEMA, PresetError
from .presets import load_library as load_preset_library
from .presets import resolve as resolve_lighting
from .presets import blend as blend_lighting

__all__ = ["SCHEMA", "Scene3D", "Set3DError", "build", "from_dict", "load_set3d", "loads_set3d", "validate",
           "PRESET_SCHEMA", "PresetError", "load_preset_library", "resolve_lighting", "blend_lighting"]
