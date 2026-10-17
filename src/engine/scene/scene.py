"""Scene: one screen of the game with an explicit lifecycle (§6.2).

A scene is owned by exactly one :class:`SceneStack`. The stack calls the hooks
below; a scene never calls them itself. All hooks receive ``ctx`` — whatever
the host passes to the stack (the engine App, or a Services table) — so a
scene has no hidden global dependency.

Lifecycle (in the order the stack invokes it):

* ``on_enter``  — pushed on the stack (resources may be acquired here).
* ``on_pause``  — a *non-overlay* scene was pushed on top of this one.
* ``on_resume`` — that scene was popped again.
* ``on_exit``   — removed from the stack (release everything acquired in enter).

Per frame, for the active scenes (see the stack's dispatch rules):

* ``handle(ctx, action_events)`` — only the top scene; return True to consume.
* ``fixed_update(ctx, dt)``       — simulation step, ``dt`` in sim seconds.
* ``update(ctx, dt_real)``        — UI/animation that ignores time scale.
* ``draw(ctx, alpha)``            — ``alpha`` is the interpolation fraction.

``overlay=True`` means the scene below keeps drawing underneath this scene;
``passthrough_update=True`` additionally lets the scenes below keep updating
(e.g. a HUD or debug overlay). Both are class attributes so a scene type
declares its nature once.
"""
from __future__ import annotations

from typing import Any, Iterable

__all__ = ["Scene"]


class Scene:
    overlay: bool = False
    passthrough_update: bool = False

    def __init__(self, name: str | None = None) -> None:
        self.name: str = name or type(self).__name__
        self.stack: Any = None     # set by the SceneStack while the scene is on it

    # -- lifecycle ---------------------------------------------------------
    def on_enter(self, ctx: Any) -> None:
        pass

    def on_exit(self, ctx: Any) -> None:
        pass

    def on_pause(self, ctx: Any) -> None:
        pass

    def on_resume(self, ctx: Any) -> None:
        pass

    # -- per frame ---------------------------------------------------------
    def handle(self, ctx: Any, action_events: Iterable[Any]) -> bool:
        return False

    def fixed_update(self, ctx: Any, dt: float) -> None:
        pass

    def update(self, ctx: Any, dt_real: float) -> None:
        pass

    def draw(self, ctx: Any, alpha: float) -> None:
        pass

    def __repr__(self) -> str:
        flags = []
        if self.overlay:
            flags.append("overlay")
        if self.passthrough_update:
            flags.append("passthrough")
        return f"<{type(self).__name__} {self.name}{' ' + ' '.join(flags) if flags else ''}>"
