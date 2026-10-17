"""Mission 2 entity components (RPE6 Phase 5, D4).

``M2Role`` replaces the ad hoc ``e.is_mission2_ipa`` / ``e.is_mission2_sniper`` flags.
Defaults equal the old ``getattr(..., False)`` fallbacks.
"""
from __future__ import annotations

from dataclasses import dataclass

from engine.world import component

__all__ = ["M2Role"]


@component
@dataclass(slots=True)
class M2Role:
    ipa: bool = False                        # IPA ground trooper spawned by m2.world
    sniper: bool = False                     # the rooftop sniper (excluded from ground logic)
