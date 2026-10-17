"""game.render - the game's ``engine.render2d`` instance: queue + static layers + post-FX + camera (RPE6 Phase 6).

Owner module for the module-level host; other code reaches it through the accessors
(``import game.render as _gr; _gr.queue()``). ``install()`` is idempotent and import-free
at module level (no pygame display, no STATE at import time). The frame itself is
``frame(fcx, fcy, painter, name=...)`` - see ``host.RenderHost.frame``.
"""
from __future__ import annotations

from typing import Any, Callable

from engine.render2d import Camera2D, PostFX, RenderQueue, RenderStats, StaticLayers

from .host import RenderHost

__all__ = ["install", "installed", "host", "queue", "static_layers", "postfx", "camera", "frame", "in_frame",
           "last_stats", "reset"]

_HOST: RenderHost | None = None


def install(width: int, height: int, *, resolver: Callable[..., Any] | None = None) -> RenderHost:
    global _HOST
    if _HOST is None or (_HOST.width, _HOST.height) != (int(width), int(height)):
        _HOST = RenderHost(width, height, resolver=resolver)
    return _HOST


def installed() -> bool:
    return _HOST is not None


def host() -> RenderHost:
    if _HOST is None:
        raise RuntimeError("game.render: install(width, height) first")
    return _HOST


def queue() -> RenderQueue:
    return host().queue


def static_layers() -> StaticLayers:
    return host().static


def postfx() -> PostFX:
    return host().fx


def camera() -> Camera2D:
    return host().camera


def frame(screen: Any, fcx: float, fcy: float, painter: Callable[[Any, int, int], Any] | None = None, *,
          submitter: Callable[[RenderQueue, float, float], Any] | None = None, name: str = "legacy",
          submit_hook: Callable[[], None] | None = None) -> RenderStats:
    return host().frame(screen, fcx, fcy, painter, submitter=submitter, name=name, submit_hook=submit_hook)


def in_frame() -> bool:
    return _HOST is not None and _HOST.in_frame


def last_stats() -> RenderStats:
    return host().last


def reset() -> None:
    """Drop the host (tests)."""
    global _HOST
    _HOST = None
