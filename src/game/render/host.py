"""game.render.host - the game's render2d instance and the hosted gameplay frame (RPE6 §6.6, Phase 6).

Owner module of the queue, static layers, post-FX cache and camera mirror; reach them
through the ``game.render`` facade (``import game.render as _gr; _gr.queue()``).

Frame protocol (``core.game_core.game_draw``)::

    _gr.frame(fcx, fcy, mission_draw, name="m5.game_draw")

1. ``queue.begin(cam)`` with the legacy integer camera (``int(round(fcx))`` - the same
   rounding every mission applies itself);
2. the legacy mission painter is submitted as ONE ``CustomDraw`` on the entities layer
   (§6.6 migration step 1 - everything still works, the queue counts it);
3. ``game.world.render_submit()`` lets RENDER_SUBMIT systems add drawables;
4. ``queue.flush(screen)`` paints in layer order and records the stats the D6 gate reads.

Nothing here reads mission state; the painter is whatever the caller passes.
"""
from __future__ import annotations

from typing import Any, Callable

from engine.render2d import Camera2D, CustomDraw, Layer, PostFX, RenderQueue, RenderStats, StaticLayers

__all__ = ["RenderHost"]


class RenderHost:
    def __init__(self, width: int, height: int, *, resolver: Callable[..., Any] | None = None) -> None:
        self.width, self.height = int(width), int(height)
        self.queue = RenderQueue(resolver=resolver)
        self.static = StaticLayers()
        self.fx = PostFX()
        self.camera = Camera2D(width, height)
        self.last: RenderStats = self.queue.stats
        self.frames = 0
        self.history: list[tuple[str, int]] = []      # (painter name, custom draws) of recent frames
        self.in_frame = False

    def frame(self, screen: Any, fcx: float, fcy: float, painter: Callable[[Any, int, int], Any] | None = None, *,
              submitter: Callable[[RenderQueue, float, float], Any] | None = None, name: str = "legacy",
              layer: int = Layer.ENTITIES, submit_hook: Callable[[], None] | None = None,
              clear: Any = None) -> RenderStats:
        """One gameplay frame. Either ``painter(surface, cam_x, cam_y)`` is hosted as ONE CustomDraw
        (migration step 1) or ``submitter(queue, fcx, fcy)`` submits the mission's drawables itself
        (step 2+). A nested call while a frame is open (a legacy entry point reached from inside a
        hosted painter) only submits into the open frame."""
        cam_x, cam_y = int(round(fcx)), int(round(fcy))
        q = self.queue
        if self.in_frame:
            if submitter is not None:
                submitter(q, fcx, fcy)
            elif painter is not None:
                q.submit(CustomDraw(painter, name), layer, sort_key=0)
            return self.last
        self.camera.snap(cam_x + self.width / 2, cam_y + self.height / 2)   # mirror: the legacy camera leads (P6-M4)
        self.in_frame = True
        try:
            q.begin(cam_x, cam_y, clear=clear, viewport=screen.get_size())
            if submitter is not None:
                submitter(q, fcx, fcy)
            elif painter is not None:
                q.submit(CustomDraw(painter, name), layer, sort_key=0)
            if submit_hook is not None:
                submit_hook()
            st = q.flush(screen)
        finally:
            self.in_frame = False
        self.last = st
        self.frames += 1
        self.history.append((name, st.custom))
        if len(self.history) > 64:
            del self.history[:-64]
        return st

    def describe(self) -> dict[str, Any]:
        return {"frames": self.frames, "last": self.last.as_dict(), "static": self.static.stats(),
                "camera": self.camera.describe(), "postfx_plates": len(self.fx)}
