"""engine.world.std - standard components (RPE6 §6.4).

Plain data. ``slots=True`` so nothing can be stuffed onto a component at runtime
(D4). Behaviour lives in systems; the few helpers here are pure reads.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

from ._component import component

__all__ = [
    "Transform", "Velocity", "Collider", "Health", "Faction", "Tags", "Label", "Sprite",
    "WalkCycle", "HitFlash", "AIBrain", "Lifetime", "LegacyRef",
]


@component
@dataclass(slots=True)
class Transform:
    x: float = 0.0
    y: float = 0.0
    angle: float = 0.0
    prev_x: float = 0.0
    prev_y: float = 0.0

    def interp(self, alpha: float) -> tuple[float, float]:
        a = 0.0 if alpha < 0.0 else 1.0 if alpha > 1.0 else alpha
        return self.prev_x + (self.x - self.prev_x) * a, self.prev_y + (self.y - self.prev_y) * a

    def remember(self) -> None:
        self.prev_x, self.prev_y = self.x, self.y


@component
@dataclass(slots=True)
class Velocity:
    vx: float = 0.0
    vy: float = 0.0

    def speed(self) -> float:
        return math.hypot(self.vx, self.vy)


@component
@dataclass(slots=True)
class Collider:
    """Axis-aligned box centred on the Transform (``w``/``h``) or a circle (``radius`` > 0)."""
    w: float = 32.0
    h: float = 32.0
    radius: float = 0.0
    solid: bool = True


@component
@dataclass(slots=True)
class Health:
    hp: float = 100.0
    max: float = 100.0

    @property
    def alive(self) -> bool:
        return self.hp > 0

    @property
    def fraction(self) -> float:
        return 0.0 if self.max <= 0 else max(0.0, min(1.0, self.hp / self.max))


@component
@dataclass(slots=True)
class Faction:
    name: str = "neutral"


@component
@dataclass(slots=True)
class Tags:
    set: set = field(default_factory=set)

    def has(self, tag: str) -> bool:
        return tag in self.set


@component
@dataclass(slots=True)
class Label:
    text: str = ""
    kind: str = ""


@component
@dataclass(slots=True)
class Sprite:
    asset: str = ""
    variant: int = 0
    scale: float = 1.0
    visible: bool = True


@component
@dataclass(slots=True)
class WalkCycle:
    """Replaces ``e._walk_prev`` / ``e._walk_ph``: phase advances while the owner moves.

    ``advance(x, y)`` reproduces the legacy displacement-driven cycle exactly: the first
    call only primes ``last_x/last_y`` (no movement), later calls add ``rate`` to the phase
    when the owner moved more than ``threshold`` since the previous call.
    """
    phase: float = 0.0
    moving: bool = False
    last_x: float = 0.0
    last_y: float = 0.0
    primed: bool = False

    def advance(self, x: float, y: float, threshold: float = 0.4, rate: float = 0.22) -> float:
        if not self.primed:
            self.last_x, self.last_y, self.primed = x, y, True
        moved = math.hypot(x - self.last_x, y - self.last_y)
        self.last_x, self.last_y = x, y
        self.moving = moved > threshold
        if self.moving:
            self.phase += rate
        return moved


@component
@dataclass(slots=True)
class HitFlash:
    t: float = 0.0
    duration: float = 0.12

    @property
    def active(self) -> bool:
        return self.t > 0.0


@component
@dataclass(slots=True)
class AIBrain:
    profile: str = ""
    state: str = "IDLE"


@component
@dataclass(slots=True)
class Lifetime:
    remaining: float = 0.0

    @property
    def expired(self) -> bool:
        return self.remaining <= 0.0


@component
@dataclass(slots=True)
class LegacyRef:
    """Bridge to a pre-ECS object (strangler step 1): the legacy ``uid`` and class name.

    Game-side adapters keep the object itself out of the component so dumps stay serialisable.
    """
    uid: int = 0
    kind: str = ""
