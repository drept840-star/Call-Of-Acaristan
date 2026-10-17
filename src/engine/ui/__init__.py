"""engine.ui - the widget kernel and the standard widgets (§6.12, Phase 4).

The kernel is deliberately small: a ``Theme`` (fonts, palette, viewport) plus
one module per standard widget under ``std``. Widgets draw onto a surface they
are given and never read game state; the caller (mission HUD, cutscene, menu)
gathers the data. That is what lets the missions delete their duplicate HUD
bodies and call the same widget instead.

Everything here is one import deep (boundary rule E4: code outside the engine
imports ``engine.ui``, never ``engine.ui.std.<widget>``):

    from engine.ui import Theme, health_bar

Legacy call sites keep working through the A-009 shim in ``src/ui/hud.py``.
"""
from __future__ import annotations

from . import std
from .std import (bottle_hud, crosshair, dialogue_box, health_bar, hostiles, minimap,
                  objective_banner, prompt, weapon_panel)
from .theme import Theme

__all__ = ["Theme", "bottle_hud", "crosshair", "dialogue_box", "health_bar",
           "hostiles", "minimap", "objective_banner", "prompt", "std",
           "weapon_panel"]
