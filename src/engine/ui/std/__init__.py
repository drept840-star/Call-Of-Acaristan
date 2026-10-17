"""Standard widgets, extracted from what the missions already draw (§6.12).

One module per widget, each taking a ``Theme``; bodies move verbatim from their
legacy home (the missions' HUD functions and ``src/ui/hud.py``) and the legacy
name stays as a shim (A-009) until every caller has migrated.
"""
from __future__ import annotations

from . import (bottle_hud, crosshair, dialogue_box, health_bar, hostiles, minimap,
               objective_banner, prompt, weapon_panel)

__all__ = ["bottle_hud", "crosshair", "dialogue_box", "health_bar", "hostiles",
           "minimap", "objective_banner", "prompt", "weapon_panel"]
