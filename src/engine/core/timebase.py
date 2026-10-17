"""Game-time accessors for legacy code (RPE6 ADAPTER A-004, BUGS B-001).

``now_ms()`` and ``now_s()`` replace ``pygame.time.get_ticks()`` and
``time.time()`` in gameplay, UI and drawing code. They return the running
App's frame-coherent wall clock (``App.clock.wall_ms`` / ``wall_s``): the host
advances it once per presented frame, so a whole frame sees one "now" and
tests set it without monkeypatching pygame. Before an App is booted (tools,
unit tests) they fall back to the OS clocks, so behaviour is unchanged there.

``pin_wall`` / ``unpin_wall`` are the test hook that replaces the old
``pygame.time.get_ticks = lambda: ...`` monkeypatch in check tools: pass
callables (or constants) and the accessors return them until unpinned.

Engine code and scenes receive the clock explicitly (``ctx.clock``); these
module-level accessors exist only for the strangler period and go away with
A-004. Real timestamps (save files, network, profiling) must keep using
``time.time()`` / ``perf_counter()`` directly.
"""
from __future__ import annotations

import time as _time
from typing import Callable

from . import app as _app

__all__ = ["now_ms", "now_s", "pin_wall", "unpin_wall"]

_PIN_MS: Callable[[], int] | None = None
_PIN_S: Callable[[], float] | None = None


def now_ms() -> int:
    if _PIN_MS is not None:
        return int(_PIN_MS())
    a = _app._CURRENT
    if a is not None:
        return a.clock.wall_ms
    try:
        import pygame
        return pygame.time.get_ticks()
    except Exception:  # pygame absent: stdlib monotonic ms
        return int(_time.monotonic() * 1000)


def now_s() -> float:
    if _PIN_S is not None:
        return float(_PIN_S())
    a = _app._CURRENT
    if a is not None:
        return a.clock.wall_s
    return _time.time()


def pin_wall(ms=None, s=None) -> None:
    """Tools/tests only: pin ``now_ms``/``now_s`` to callables or constants.

    ``pin_wall(ms=lambda: clock[0])`` mirrors the old get_ticks monkeypatch;
    ``None`` leaves that accessor unpinned. Always pair with ``unpin_wall()``.
    """
    global _PIN_MS, _PIN_S
    _PIN_MS = None if ms is None else (ms if callable(ms) else (lambda v=ms: v))
    _PIN_S = None if s is None else (s if callable(s) else (lambda v=s: v))


def unpin_wall() -> None:
    global _PIN_MS, _PIN_S
    _PIN_MS = _PIN_S = None
