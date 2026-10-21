"""Phase-5 colours for the Bloc landmarks and signage.

The lit colours are emissive at full strength (the fog alone dims them); the
painted ones are authored dark, so a red board reads as paint under a lamp and
not as a light of its own.
"""
from __future__ import annotations

import math

BEACON_RED = (228, 56, 42)       # aviation lamp on stacks and masts
PROP_RED = (150, 34, 30)         # painted propaganda red, never emissive
NEON_RED = (255, 72, 52)         # lit rooftop letters
LETTER_CREAM = (236, 222, 178)   # painted letters on a red board
WINDOW_WARM = (255, 203, 109)    # a lit flat
WINDOW_COLD = (176, 206, 255)    # a flat lit by its television
WINDOW_DARK = (14, 17, 23)       # unlit glass


_SIDES = ("front", "back", "left", "right", "top", "bottom")
_OUT_SIDE = {"+z": "back", "-z": "front", "+x": "right", "-x": "left"}


def only(facing, *keep):
    """A ``box(skip=...)`` that keeps just the face toward ``facing`` (and
    ``keep``): far facades and letters are only ever seen from the front, and
    the yard rings the town round the camera, so five faces in six were
    never drawn but still sorted and drawn every frame."""
    return tuple(s for s in _SIDES if s != _OUT_SIDE[facing] and s not in keep)


def dim(col, k):
    """``col`` scaled by ``k``, as ints."""
    return tuple(max(0, min(255, int(c * k))) for c in col)


def _hash(i, k=1):
    """A repeatable 0..1 from an index (no random module: stable frames)."""
    return (math.sin(i * 12.9898 + k * 78.233) * 43758.5453) % 1.0
