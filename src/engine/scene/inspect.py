"""InspectScene: a first-person look at an object that freezes gameplay (§6.2).

Generalises the game's ``inspect_fpv`` module, which already has the shape of
a scene: ``start(key)``, ``update(dt_ms) -> bool``, ``draw(surface)``,
``skip()``, ``active()``. The scene wraps any such *controller* (module or
object) as an overlay with ``passthrough_update=False`` - the scene below
keeps drawing and stops updating - and pops itself when the controller
reports it is no longer active.
"""
from __future__ import annotations

from typing import Any, Iterable

from .scene import Scene

__all__ = ["InspectScene"]


class InspectScene(Scene):
    overlay = True
    passthrough_update = False
    skip_actions: frozenset = frozenset({"skip", "confirm", "cancel"})

    def __init__(self, controller: Any, key: str, caption: str | None = None, name: str | None = None) -> None:
        super().__init__(name or f"INSPECT[{key}]")
        self.controller = controller
        self.key = key
        self.caption = caption
        self.started = False

    def on_enter(self, ctx: Any) -> None:
        if not self.started and not self._active():
            self.controller.start(self.key, self.caption)
        self.started = True

    def _active(self) -> bool:
        a = self.controller.active
        return bool(a() if callable(a) else a)

    def handle(self, ctx: Any, action_events: Iterable[Any]) -> bool:
        for ev in action_events:
            if getattr(ev, "action", ev) in self.skip_actions:
                self.controller.skip()
                return True
        return True        # an inspect overlay swallows everything else

    def update(self, ctx: Any, dt_real: float) -> None:
        self.controller.update(dt_real * 1000.0)
        if not self._active() and self.stack is not None and self.stack.top is self:
            self.stack.pop()

    def draw(self, ctx: Any, alpha: float) -> None:
        surface = getattr(ctx, "screen", None)
        if surface is not None:
            self.controller.draw(surface)
