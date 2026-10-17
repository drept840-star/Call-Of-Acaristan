"""CutsceneScene: a linear sequence of timed shots (§6.2, Phase 2 form).

The game supplies the ``shots`` (any mapping-like objects), a ``renderer``
callback ``renderer(ctx, shot, t_ms)`` and optionally a ``duration(shot)``
accessor (default: ``shot["duration"]`` in milliseconds). The scene owns the
cursor - which shot is on, for how long - and ends itself (``done``) after the
last shot, calling ``on_end(ctx)`` once and popping itself from its stack.

Cutscenes run on real time (``update``), not simulation time: a paused world
or a time-scaled replay must not stretch a cut. Phase 8 replaces the shot
cursor with a TimelinePlayer behind the same scene surface.
"""
from __future__ import annotations

from typing import Any, Callable, Iterable, Sequence

from .scene import Scene

__all__ = ["CutsceneScene"]


def _default_duration(shot: Any) -> float:
    try:
        return float(shot["duration"])
    except (KeyError, TypeError, ValueError):
        return float(getattr(shot, "duration", 0.0) or 0.0)


class CutsceneScene(Scene):
    skip_actions: frozenset = frozenset({"skip", "confirm"})

    def __init__(self, take: str, shots: Sequence[Any], renderer: Callable | None = None,
                 duration: Callable[[Any], float] | None = None, on_end: Callable | None = None,
                 name: str | None = None) -> None:
        super().__init__(name or f"CUTSCENE[{take}]")
        self.take = take
        self.timeline = None
        self.player = None
        self.shots = list(shots)
        self.renderer = renderer
        self.duration = duration or _default_duration
        self.on_end = on_end
        self.index = 0
        self.elapsed_ms = 0.0
        self.done = not self.shots
        self._ended = False

    @classmethod
    def from_timeline(cls, timeline, renderer: Callable | None = None,
                      on_end: Callable | None = None, name: str | None = None):
        """Build the scene from an ``engine.timeline`` Timeline (Phase 8).

        Shots come from ``timeline.shots``; the scene also keeps a
        ``TimelinePlayer`` (``self.player``) so the host can sample the
        keyframed tracks (camera/light/fx) at the scene's own clock while
        the shot cursor advances as before.
        """
        from engine.timeline import TimelinePlayer  # lazy: keep scene imports light

        def _duration_ms(shot):  # timeline shots carry duration_ms (legacy: duration)
            try:
                return float(shot.get("duration_ms", 0) or 0)
            except (AttributeError, TypeError, ValueError):
                return 0.0

        scene = cls(timeline.id, list(timeline.shots), renderer=renderer,
                    duration=_duration_ms, on_end=on_end, name=name)
        scene.timeline = timeline
        scene.player = TimelinePlayer(timeline)
        return scene

    # -- cursor ----------------------------------------------------------------
    @property
    def shot(self) -> Any:
        return self.shots[self.index] if self.index < len(self.shots) else None

    def advance(self, dt_ms: float, ctx: Any = None) -> None:
        """Move the cursor by ``dt_ms``; carries the overshoot into the next shot."""
        if self.done:
            return
        self.elapsed_ms += max(0.0, float(dt_ms))
        while not self.done:
            d = self.duration(self.shot)
            if self.elapsed_ms < d:
                break
            self.elapsed_ms -= d
            self._next(ctx)

    def skip(self, ctx: Any = None) -> None:
        """Cut to the next shot (the usual 'skip' key behaviour)."""
        if not self.done:
            self.elapsed_ms = 0.0
            self._next(ctx)

    def _next(self, ctx: Any) -> None:
        self.index += 1
        if self.index >= len(self.shots):
            self.done = True
            self.elapsed_ms = 0.0
            self._finish(ctx)

    def _finish(self, ctx: Any) -> None:
        if self._ended:
            return
        self._ended = True
        if self.on_end is not None:
            self.on_end(ctx)
        if self.stack is not None:
            self.stack.pop()

    # -- scene hooks -----------------------------------------------------------
    def handle(self, ctx: Any, action_events: Iterable[Any]) -> bool:
        for ev in action_events:
            action = getattr(ev, "action", ev)
            if action in self.skip_actions:
                self.skip(ctx)
                return True
        return False

    def update(self, ctx: Any, dt_real: float) -> None:
        self.advance(dt_real * 1000.0, ctx)

    def draw(self, ctx: Any, alpha: float) -> None:
        shot = self.shot
        if shot is not None and self.renderer is not None:
            self.renderer(ctx, shot, self.elapsed_ms)
