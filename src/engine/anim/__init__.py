"""engine.anim - animation (RPE6). Phase 2 holds the generic 2D figure kit (``draw_character`` and the
cast ``SPECS``) promoted from cutscenes.figure_kit; the pose cache (``PoseCache``/``POSES``, Phase 3); clips and rig2d follow in Phase 5."""
from __future__ import annotations

from .pose_cache import POSE_CAP, POSES, PoseCache
from .figure_kit import HEIGHT, KRAP_BLUE, KRAP_UNIFORM, REF_H, SPECS, draw_character, draw_prop
from .rig3d import (
    FULL_BODY_KEYS,
    HEAD_KEYS,
    LEFT_ARM_KEYS,
    LOWER_BODY_KEYS,
    NEUTRAL_POSE,
    RIGHT_ARM_KEYS,
    TORSO_KEYS,
    UPPER_BODY_KEYS,
    WEAPON_KEYS,
    FootIKSolver,
    LayeredAnimState,
    add_pose,
    blend_poses,
    gait_cycle_m,
    locomotion_pose,
    mask_pose,
)
from .springs import AngleSpring, Spring, Spring3, TurnLagTracker
# Public aliases of the kit's drawing primitives: the sprite tools (tools/sprites/portraits.py)
# replay the face through them, and cutscenes.m3cell scales by REF_H.
from .figure_kit import _Pen as Pen, _face as face, _mix as mix, _dark as dark, _lite as lite, _STUBBLE as STUBBLE

__all__ = ["HEIGHT", "KRAP_BLUE", "KRAP_UNIFORM", "REF_H", "SPECS", "draw_character", "draw_prop",
           "Pen", "face", "mix", "dark", "lite", "STUBBLE", "PoseCache", "POSES", "POSE_CAP",
           "Spring", "AngleSpring", "Spring3", "TurnLagTracker",
           "LOWER_BODY_KEYS", "TORSO_KEYS", "HEAD_KEYS", "LEFT_ARM_KEYS", "RIGHT_ARM_KEYS",
           "WEAPON_KEYS", "UPPER_BODY_KEYS", "FULL_BODY_KEYS", "NEUTRAL_POSE",
           "blend_poses", "add_pose", "mask_pose", "locomotion_pose", "gait_cycle_m",
           "FootIKSolver", "LayeredAnimState"]