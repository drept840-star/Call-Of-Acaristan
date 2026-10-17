"""Cutscene scene renderers registered by scene id (RPE6 D1, boundary rule 4).

The cutscene dispatcher (``cutscenes.engine.draw_cutscene_scene``) must not
import mission-owned take modules by name. A mission registers the renderer
for the scene ids it owns, normally from its ``meta`` module (the same place
its shot lists live), and the dispatcher looks the id up here first.

Stdlib only, no pygame, no game state: safe to import from anywhere. This is
the Phase 2 take registry in its smallest form; Phase 8 turns entries into
timelines (master prompt §6.15).

    from core.cutscene_registry import register_scene_renderer
    register_scene_renderer("m5_shadow_finale", _draw_shadow_finale)   # fn(surface, t_ms)
"""
from __future__ import annotations

from typing import Callable

__all__ = ["register_scene_renderer", "register_scene_renderers", "scene_renderer", "registered_scenes",
           "set_current_shot", "current_shot"]

_RENDERERS: dict[str, Callable] = {}
_CURRENT: dict = {"shot": None}


def set_current_shot(shot) -> None:
    """The shot being drawn right now (Phase 11: renderers read its
    ``post`` block for DOF etc.). Set by the dispatcher per draw."""
    _CURRENT["shot"] = shot


def current_shot():
    return _CURRENT["shot"]


def register_scene_renderer(scene_id: str, fn: Callable, *, replace: bool = False) -> Callable:
    """Bind ``fn(surface, t_ms)`` to ``scene_id``. Re-registering the same id is an error unless ``replace``."""
    if not scene_id or not isinstance(scene_id, str):
        raise ValueError(f"scene id must be a non-empty str, got {scene_id!r}")
    if not callable(fn):
        raise TypeError(f"renderer for {scene_id!r} is not callable: {fn!r}")
    if scene_id in _RENDERERS and _RENDERERS[scene_id] is not fn and not replace:
        raise ValueError(f"scene renderer {scene_id!r} is already registered")
    _RENDERERS[scene_id] = fn
    return fn


def register_scene_renderers(table: dict, *, replace: bool = False) -> None:
    """Register every ``scene_id -> fn`` of ``table`` (a take module's own scenes)."""
    for scene_id, fn in table.items():
        register_scene_renderer(scene_id, fn, replace=replace)


def scene_renderer(scene_id: str) -> Callable | None:
    """The registered renderer for ``scene_id``, or None (the dispatcher then uses its built-ins)."""
    return _RENDERERS.get(scene_id)


def registered_scenes() -> list[str]:
    return sorted(_RENDERERS)
