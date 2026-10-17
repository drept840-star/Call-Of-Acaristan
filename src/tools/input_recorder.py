"""Dev-only gameplay input recorder (RPE6 Phase 0, replay baselines).

Off unless ACA_RECORD_INPUT=<path.json> is set. When on, app.py's GAME.update
calls record(keys, mouse_xy, fire) once per sim step, and the run-length
stream is written at exit in the tools/ae_replay.py segment format:
  {"schema": "ae.replay.stream", "version": 1, "fps_hint": 60,
   "start_state": {...}, "input_stream": [[n_frames, "wd|shift", mx, my, fire], ...]}
Recording never changes game behaviour: it only reads the inputs it is given.
Note: the legacy loop uses variable dt (clock.tick), so a human stream replays
on the fixed-step harness as "same inputs per step", not "same wall time".
"""
from __future__ import annotations

import atexit
import json
import os

__all__ = ["enabled", "record"]

_PATH = os.environ.get("ACA_RECORD_INPUT", "")
_stream: list = []
_start: dict = {}


def enabled() -> bool:
    return bool(_PATH)


def _key_string(keys) -> str:
    import pygame
    s = "".join(c for c, k in (("w", pygame.K_w), ("a", pygame.K_a), ("s", pygame.K_s), ("d", pygame.K_d))
                if keys[k])
    return s + ("shift" if keys[pygame.K_LSHIFT] else "")


def record(keys, mouse_xy, fire) -> None:
    if not _PATH:
        return
    try:
        if not _start:
            from core.state import STATE
            pl = getattr(STATE, "player", None)
            _start.update({"player_rect": list(pl.rect) if pl is not None else None,
                           "mission": getattr(STATE, "current_mission", None)})
        row = [_key_string(keys), int(mouse_xy[0]), int(mouse_xy[1]), int(bool(fire))]
        if _stream and _stream[-1][1:] == row:
            _stream[-1][0] += 1
        else:
            _stream.append([1, *row])
    except Exception as e:  # noqa: BLE001 - dev tool must never break the game
        print(f"[input_recorder] disabled after error: {e!r}")
        globals()["_PATH"] = ""


@atexit.register
def _flush() -> None:
    if _PATH and _stream:
        with open(_PATH, "w", encoding="utf-8", newline="\n") as f:
            json.dump({"schema": "ae.replay.stream", "version": 1, "fps_hint": 60,
                       "start_state": _start, "input_stream": _stream}, f, indent=0)
        print(f"[input_recorder] wrote {sum(r[0] for r in _stream)} steps to {_PATH}")
