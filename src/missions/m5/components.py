"""Mission 5 entity components (RPE6 Phase 5, D4).

Declared data that ``missions.m5`` used to stuff onto ``Enemy`` objects as ad hoc
``m5_*`` attributes. Attach/read through ``game.world`` (``_gw.ensure(e, M5Guard)``);
defaults equal the ``getattr(..., default)`` fallbacks the old reads assumed, so an
enemy that never received the data behaves exactly as before.
"""
from __future__ import annotations

from dataclasses import dataclass

from engine.world import component

__all__ = ["M5Guard"]


@component
@dataclass(slots=True)
class M5Guard:
    guard: bool = False          # typed Guard trooper (black + red armband)
    kind: str = ""               # etype passed to _make_guard ("rifle", "shotgun", ...)
    label: str = ""              # spawn label (old faces, squad names)
    stage: object = None         # mission5_stage at spawn time
    counted: bool = False        # kill already counted toward m5_guard_kills
    squad: bool = False          # HQ squad member
    face: object = None          # OLD_FACES name for the Lower Quarter veterans (None = not one)
    passive: bool = False        # stood down (old face not provoked)
    hunt_prev: bool = False      # previous-frame hunting flag (radio call edge)
    hp0: object = None           # hp when the mercy check first saw the enemy (None = unset)
