"""Mission 4 entity components (RPE6 Phase 5, D4).

``M4Guard.loyalist`` replaces the ad hoc ``e.m4_loyalist`` flag; the enemy type and spawn
label (old ``m4_type`` / ``m4_label``) live in the shared ``engine.world.Label`` component
(``kind`` / ``text``). Defaults equal the old ``getattr(..., default)`` fallbacks.
"""
from __future__ import annotations

from dataclasses import dataclass

from engine.world import component

__all__ = ["M4Guard"]


@component
@dataclass(slots=True)
class M4Guard:
    loyalist: bool = False                   # siege loyalist (counts toward the concurrency cap)
