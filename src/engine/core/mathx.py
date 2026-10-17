"""Small math helpers (lerp/ease/angles/clamp)."""
from __future__ import annotations

import math

__all__ = ["clamp", "lerp", "inv_lerp", "lerp_angle", "smoothstep", "ease_in_out_cubic", "ease_out_quad"]


def clamp(v: float, lo: float, hi: float) -> float:
    return lo if v < lo else hi if v > hi else v


def lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


def inv_lerp(a: float, b: float, v: float) -> float:
    return 0.0 if a == b else (v - a) / (b - a)


def lerp_angle(a: float, b: float, t: float) -> float:
    """Degrees, the short way round."""
    d = (b - a) % 360.0
    if d > 180.0:
        d -= 360.0
    return (a + d * t) % 360.0


def smoothstep(t: float) -> float:
    t = clamp(t, 0.0, 1.0)
    return t * t * (3 - 2 * t)


def ease_in_out_cubic(t: float) -> float:
    t = clamp(t, 0.0, 1.0)
    return 4 * t * t * t if t < 0.5 else 1 - math.pow(-2 * t + 2, 3) / 2


def ease_out_quad(t: float) -> float:
    t = clamp(t, 0.0, 1.0)
    return 1 - (1 - t) * (1 - t)
