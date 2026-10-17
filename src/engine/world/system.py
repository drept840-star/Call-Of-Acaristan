"""engine.world.system - ``System`` base, phases and the ``Scheduler`` (RPE6 §6.4, A.1).

Phases run in a fixed order every step: ``PRE`` (input -> intents), ``SIM`` (AI,
movement, collision, combat), ``POST`` (lifetimes, despawns, event flush) and
``RENDER_SUBMIT`` (drawables only; never mutates sim state). Within a phase systems
run by ``order`` then registration order.

Debug mode (``Scheduler(debug=True)``) makes the world structurally read-only during
``RENDER_SUBMIT`` and refuses render systems that declare ``writes``. Field-level
writes through component attributes cannot be intercepted in Python - that part of
the contract is the ``writes`` declaration plus review.
"""
from __future__ import annotations

from typing import Any, Callable, Iterable

from ._component import is_component
from .entity import World, WorldError

__all__ = ["PHASES", "PRE", "SIM", "POST", "RENDER_SUBMIT", "System", "Scheduler", "FunctionSystem"]

PRE = "PRE"
SIM = "SIM"
POST = "POST"
RENDER_SUBMIT = "RENDER_SUBMIT"
PHASES: tuple[str, ...] = (PRE, SIM, POST, RENDER_SUBMIT)


class System:
    """Subclass, set the class attributes, implement ``run``.

    ``reads``/``writes`` are tuples of component classes. They are declarations (used
    by the scheduler's checks and the component dump), not an access-control mechanism.
    """

    name: str = ""
    phase: str = SIM
    order: int = 0
    reads: tuple[type, ...] = ()
    writes: tuple[type, ...] = ()
    enabled: bool = True

    def run(self, world: World, ctx: Any, dt: float) -> None:  # pragma: no cover - interface
        raise NotImplementedError

    def label(self) -> str:
        return self.name or type(self).__name__


class FunctionSystem(System):
    """Wrap a plain ``fn(world, ctx, dt)`` as a system (adapters, one-off hooks)."""

    def __init__(self, fn: Callable[[World, Any, float], None], *, name: str = "", phase: str = SIM,
                 order: int = 0, reads: Iterable[type] = (), writes: Iterable[type] = ()) -> None:
        self._fn = fn
        self.name = name or getattr(fn, "__name__", "fn")
        self.phase = phase
        self.order = order
        self.reads = tuple(reads)
        self.writes = tuple(writes)

    def run(self, world: World, ctx: Any, dt: float) -> None:
        self._fn(world, ctx, dt)


class Scheduler:
    def __init__(self, world: World, *, debug: bool = False) -> None:
        self.world = world
        self.debug = bool(debug)
        self._systems: dict[str, list[System]] = {p: [] for p in PHASES}
        self._seq = 0
        self._seq_of: dict[int, int] = {}
        self.steps: int = 0
        self.last_errors: list[tuple[str, BaseException]] = []

    # ── registration ───────────────────────────────────────────────────────
    def add(self, system: System) -> System:
        phase = system.phase
        if phase not in self._systems:
            raise WorldError(f"system {system.label()!r}: unknown phase {phase!r} (use {PHASES})")
        for k in tuple(system.reads) + tuple(system.writes):
            if not is_component(k):
                raise WorldError(f"system {system.label()!r} declares non-component {getattr(k, '__name__', k)!r}")
        if phase == RENDER_SUBMIT and system.writes:
            raise WorldError(f"render system {system.label()!r} must not declare writes")
        if any(s is system for s in self._systems[phase]):
            return system
        self._seq += 1
        self._seq_of[id(system)] = self._seq
        bucket = self._systems[phase]
        bucket.append(system)
        bucket.sort(key=lambda s: (s.order, self._seq_of[id(s)]))
        return system

    def remove(self, system_or_name: System | str) -> bool:
        for bucket in self._systems.values():
            for s in list(bucket):
                if s is system_or_name or s.label() == system_or_name:
                    bucket.remove(s)
                    self._seq_of.pop(id(s), None)
                    return True
        return False

    def systems(self, phase: str | None = None) -> list[System]:
        if phase is None:
            return [s for p in PHASES for s in self._systems[p]]
        return list(self._systems[phase])

    def find(self, name: str) -> System | None:
        for s in self.systems():
            if s.label() == name:
                return s
        return None

    # ── execution ──────────────────────────────────────────────────────────
    def run_phase(self, phase: str, ctx: Any = None, dt: float = 0.0) -> None:
        if phase not in self._systems:
            raise WorldError(f"unknown phase {phase!r}")
        world = self.world
        guard = self.debug and phase == RENDER_SUBMIT
        if guard:
            world.set_readonly(True)
        try:
            for s in self._systems[phase]:
                if s.enabled:
                    s.run(world, ctx, dt)
        finally:
            if guard:
                world.set_readonly(False)
        if phase == POST:
            world.flush()

    def step(self, ctx: Any = None, dt: float = 0.0, *, phases: Iterable[str] = PHASES) -> None:
        for phase in phases:
            self.run_phase(phase, ctx, dt)
        self.steps += 1

    def describe(self) -> list[dict[str, Any]]:
        """Ordered listing for the inspector / dump tool."""
        out = []
        for p in PHASES:
            for s in self._systems[p]:
                out.append({"phase": p, "name": s.label(), "order": s.order, "enabled": s.enabled,
                            "reads": [k.__name__ for k in s.reads], "writes": [k.__name__ for k in s.writes]})
        return out
