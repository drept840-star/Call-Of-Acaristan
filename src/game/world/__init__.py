"""game.world - the game's ``engine.world`` instance: World + Scheduler + legacy roster (RPE6 Phase 5).

Owner module for the three module-level objects; other code reaches them through the
accessors (``import game.world as _gw; _gw.world()``). ``install(state)`` is idempotent
and import-free at module level (no pygame, no STATE at import time).

Step contract (called from ``core.game_core``):
    step(fn)       -> PRE (roster sync) -> SIM (``fn`` runs as the ``legacy_mission_update``
                      system at order 0, other SIM systems around it) -> POST (despawn flush);
                      returns ``fn()``'s result
    render_submit()-> RENDER_SUBMIT                            after the legacy mission draw
    pre_update()/post_update() remain for tools and tests that drive the phases by hand.
``ACA_WORLD_DEBUG=1`` turns on the read-only guard during RENDER_SUBMIT.
"""
from __future__ import annotations

import os
from typing import Any, Callable

from engine.world import POST, PRE, RENDER_SUBMIT, SIM, Scheduler, World

from .legacy import LegacyMissionSystem, LegacyRoster, make_roster_system

__all__ = ["world", "scheduler", "roster", "install", "installed", "step", "pre_update", "post_update", "render_submit",
           "reset", "entity_of", "get", "ensure"]

_WORLD: World | None = None
_SCHED: Scheduler | None = None
_ROSTER: LegacyRoster | None = None
_HOST: LegacyMissionSystem | None = None
_STATE: Any = None


def world() -> World:
    if _WORLD is None:
        raise RuntimeError("game.world not installed - call game.world.install(STATE) first")
    return _WORLD


def scheduler() -> Scheduler:
    if _SCHED is None:
        raise RuntimeError("game.world not installed - call game.world.install(STATE) first")
    return _SCHED


def roster() -> LegacyRoster:
    if _ROSTER is None:
        raise RuntimeError("game.world not installed - call game.world.install(STATE) first")
    return _ROSTER


def installed() -> bool:
    return _SCHED is not None


def install(state: Any, *, debug: bool | None = None) -> Scheduler:
    """Create the world, scheduler and roster bound to ``state`` (idempotent per state object)."""
    global _WORLD, _SCHED, _ROSTER, _HOST, _STATE
    if _SCHED is not None and _STATE is state:
        return _SCHED
    if debug is None:
        debug = os.environ.get("ACA_WORLD_DEBUG", "") == "1"
    _WORLD = World()
    _SCHED = Scheduler(_WORLD, debug=debug)
    _ROSTER = LegacyRoster(_WORLD)
    _HOST = LegacyMissionSystem()
    _STATE = state
    _SCHED.add(make_roster_system(_ROSTER, state))
    _SCHED.add(_HOST)
    return _SCHED


def reset() -> None:
    """Forget every entity (new world, same scheduler config); used by tests and mission restarts."""
    global _WORLD, _SCHED, _ROSTER
    if _SCHED is None:
        return
    systems = [s for s in _SCHED.systems() if s.label() != "legacy_roster"]
    debug = _SCHED.debug
    _WORLD = World()
    _SCHED = Scheduler(_WORLD, debug=debug)
    _ROSTER = LegacyRoster(_WORLD)
    _SCHED.add(make_roster_system(_ROSTER, _STATE))
    for s in systems:
        _SCHED.add(s)


def _autoinstall() -> None:
    """Missions attach components while a checkpoint starter runs, before the first game_update."""
    if _SCHED is None:
        from core.state import STATE  # lazy: owner of the game state; avoids an import-time dependency

        install(STATE)


def entity_of(obj: Any) -> int:
    """EntityId for a legacy object (registered on demand, before the next PRE sync)."""
    _autoinstall()
    _ROSTER.check_reset(_STATE)
    eid = _ROSTER.eid_for(obj)
    return eid if eid is not None else _ROSTER.register_now(obj, _STATE)


def get(obj: Any, kind: type, default: Any = None) -> Any:
    """Component ``kind`` of the entity bridging ``obj`` (``default`` when absent or not installed)."""
    if _ROSTER is None or _WORLD is None:
        return default
    _ROSTER.check_reset(_STATE)
    eid = _ROSTER.eid_for(obj)
    if eid is None:
        return default
    return _WORLD.get(eid, kind, default)


def ensure(obj: Any, kind: type) -> Any:
    """Component ``kind`` of ``obj``'s entity, created with its defaults when missing.

    This is the D4 replacement for ``getattr(e, "m5_x", default)`` / ``e.m5_x = v``: the
    defaults live on the component class, and the data is inspectable in the world.
    """
    _autoinstall()
    eid = entity_of(obj)
    comp = _WORLD.get(eid, kind)
    if comp is None:
        comp = _WORLD.add(eid, kind())
    return comp


def _dt() -> float:
    try:
        return float(getattr(_STATE, "dt", 1.0 / 60.0))
    except (TypeError, ValueError):
        return 1.0 / 60.0


def step(fn: Callable[[], Any]) -> Any:
    """One hosted frame: PRE -> SIM (``fn`` as ``legacy_mission_update``) -> POST; returns ``fn()``."""
    if _SCHED is None or _HOST is None:
        return fn()
    return _HOST.host_step(_SCHED, _STATE, _dt(), fn)


def pre_update() -> None:
    if _SCHED is not None:
        _SCHED.run_phase(PRE, _STATE, _dt())


def post_update() -> None:
    if _SCHED is not None:
        dt = _dt()
        _SCHED.run_phase(SIM, _STATE, dt)
        _SCHED.run_phase(POST, _STATE, dt)
        _SCHED.steps += 1


def render_submit() -> None:
    if _SCHED is not None:
        _SCHED.run_phase(RENDER_SUBMIT, _STATE, _dt())
