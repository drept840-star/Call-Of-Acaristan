"""engine.input - action maps over raw device state (RPE6 §6.10, Phase 9).

Bindings (keyboard + gamepad) resolve to the canonical key names legacy
readers already test, via a virtual pressed set computed once per frame
by the host.  The kernel is name-based and headless; device polling and
snapshot conversion stay with the host.
"""
from __future__ import annotations

from .model import DEFAULT_ACTIONS, ActionMap, validate

__all__ = ["DEFAULT_ACTIONS", "ActionMap", "validate"]
