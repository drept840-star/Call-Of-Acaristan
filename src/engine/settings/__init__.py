"""engine.settings - typed, layered user settings (RPE6 §6.18, Phase 9).

The game owns the schema (sectioned :class:`Field` records); this package
owns the mechanics: layering (defaults < file < environment < explicit),
strict coercion with range/enum checks, unknown-key preservation, and
change notification so systems can apply settings live.  It never
imports game code; persistence is the host's file dict in and out.
"""
from __future__ import annotations

from .model import BOOL, ENUM, FLOAT, INT, STR, Field, Settings, coerce, env_layer, resolve

__all__ = ["BOOL", "ENUM", "FLOAT", "INT", "STR", "Field", "Settings", "coerce", "env_layer", "resolve"]
