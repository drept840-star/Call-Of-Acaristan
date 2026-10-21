"""engine.ai.senses - what an agent knows about its target.

Memory is a plain dict (``new_memory()``) so it lives in the agent's
blackboard and copies/saves like any other state:

``aware``     0..1, fills while the target is in view, decays out of view
``contact``   True once ``aware`` reaches 1 (or the agent is shot)
``sees``      in view this tick (only meaningful with contact)
``seen_t``    when the target was last in view, ``last_pos`` where
``lead``      a place worth checking (a noise, a radio report, where contact
              was lost), with ``lead_t`` and ``lead_kind``

Sight is a cone (``fov`` degrees, ``range`` metres) plus an all-round ``near``
radius. Reaction time grows with distance: a target at the edge of range
takes ``react[1]`` seconds to notice, one close by ``react[0]``. The caller
does the line-of-sight test (only for targets ``in_view`` reports), so the
expensive part runs only when it can matter.
"""
from __future__ import annotations

import math
from typing import Callable, Sequence

__all__ = ["new_memory", "Sight", "NoiseBus", "on_hit", "give_lead", "drop_lead"]

Vec3 = Sequence[float]


def new_memory() -> dict:
    return dict(aware=0.0, contact=False, sees=False, seen_t=-1e9, last_pos=None,
                lead=None, lead_t=-1e9, lead_kind=None, heard_upto=-1e9)


def give_lead(mem: dict, t: float, pos: Vec3, kind: str) -> None:
    mem["lead"] = tuple(pos)
    mem["lead_t"] = t
    mem["lead_kind"] = kind


def drop_lead(mem: dict) -> None:
    mem["lead"] = None
    mem["lead_kind"] = None


def on_hit(mem: dict, t: float, from_pos: Vec3) -> None:
    """Being shot is instant contact: he knows where it came from."""
    mem["aware"] = 1.0
    mem["contact"] = True
    mem["seen_t"] = t
    mem["last_pos"] = tuple(from_pos)


class Sight:
    def __init__(self, fov: float = 120.0, range: float = 40.0, near: float = 3.0,
                 react: tuple[float, float] = (0.15, 1.2), forget: float = 6.0) -> None:
        self.half_cos = math.cos(math.radians(fov * 0.5))
        self.range = float(range)
        self.near = float(near)
        self.react = react
        self.forget = float(forget)

    def in_view(self, eye: Vec3, facing: Sequence[float], target: Vec3) -> bool:
        """Inside the cone or the near radius (``facing`` is a unit XZ vector)."""
        dx, dz = target[0] - eye[0], target[2] - eye[2]
        d = math.hypot(dx, dz)
        if d <= self.near:
            return True
        if d > self.range:
            return False
        return (dx * facing[0] + dz * facing[1]) / d >= self.half_cos

    def update(self, mem: dict, t: float, dt: float, visible: bool, target: Vec3,
               dist: float, boost: float = 1.0) -> bool:
        """Fold this tick's view into memory; returns ``mem["sees"]``."""
        if visible:
            if not mem["contact"]:
                f = min(1.0, max(0.0, dist / self.range))
                react = self.react[0] + (self.react[1] - self.react[0]) * f
                mem["aware"] = min(1.0, mem["aware"] + dt * boost / max(1e-3, react))
                if mem["aware"] >= 1.0:
                    mem["contact"] = True
            if mem["contact"]:
                mem["seen_t"] = t
                mem["last_pos"] = tuple(target)
        elif not mem["contact"]:
            mem["aware"] = max(0.0, mem["aware"] - dt * 0.25)
        elif t - mem["seen_t"] > self.forget:
            # lost him: the last place he was is now only a lead
            mem["contact"] = False
            mem["aware"] = 0.5
            if mem["last_pos"] is not None:
                give_lead(mem, t, mem["last_pos"], "lost")
        mem["sees"] = bool(visible and mem["contact"])
        return mem["sees"]


class NoiseBus:
    """Sounds as (t, pos, radius, kind). A wall between source and listener
    cuts the radius by ``muffle``."""

    def __init__(self, keep: float = 1.5, muffle: float = 0.5) -> None:
        self.events: list[tuple[float, tuple[float, ...], float, str]] = []
        self.keep = float(keep)
        self.muffle = float(muffle)

    def emit(self, t: float, pos: Vec3, radius: float, kind: str = "") -> None:
        self.events.append((float(t), tuple(pos), float(radius), kind))

    def prune(self, t: float) -> None:
        if self.events and t - self.events[0][0] > self.keep:
            self.events = [e for e in self.events if t - e[0] <= self.keep]

    def listen(self, mem: dict, t: float, ear: Vec3,
               blocked: Callable[[Vec3, Vec3], bool] | None = None) -> tuple | None:
        """The loudest sound since this listener last listened, or None."""
        since = mem.get("heard_upto", -1e9)
        mem["heard_upto"] = t
        best, best_l = None, 0.0
        for e in self.events:
            if e[0] <= since:
                continue
            _t, pos, radius, _kind = e
            d = math.dist((pos[0], pos[2]), (ear[0], ear[2]))
            if d >= radius:
                continue
            if blocked is not None and d >= radius * self.muffle and blocked(pos, ear):
                continue
            loud = 1.0 - d / radius
            if loud > best_l:
                best, best_l = e, loud
        return best
