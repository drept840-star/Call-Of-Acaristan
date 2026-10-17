"""engine.anim - animation (RPE6). Phase 2 holds the generic 2D figure kit (``draw_character`` and the
cast ``SPECS``) promoted from cutscenes.figure_kit; the pose cache (``PoseCache``/``POSES``, Phase 3); clips and rig2d follow in Phase 5."""
from __future__ import annotations

from .pose_cache import POSE_CAP, POSES, PoseCache
from .figure_kit import HEIGHT, KRAP_BLUE, KRAP_UNIFORM, REF_H, SPECS, draw_character
# Public aliases of the kit's drawing primitives: the sprite tools (tools/sprites/portraits.py)
# replay the face through them, and cutscenes.m3cell scales by REF_H.
from .figure_kit import _Pen as Pen, _face as face, _mix as mix, _dark as dark, _lite as lite, _STUBBLE as STUBBLE

__all__ = ["HEIGHT", "KRAP_BLUE", "KRAP_UNIFORM", "REF_H", "SPECS", "draw_character",
           "Pen", "face", "mix", "dark", "lite", "STUBBLE", "PoseCache", "POSES", "POSE_CAP"]
