"""RPE6 Phase 9: game-side input adapter (rebinding + gamepad).

Gameplay reads one pressed-key snapshot (``pygame.key.get_pressed()``)
indexed by ``K_*`` constants at hundreds of sites.  Rather than touching
any reader, this adapter wraps that single snapshot per frame in
``app._legacy_frame``: the ``engine.input`` action map computes which
canonical keys should additionally read as down (a bound physical key
presses its action's canonical key too), and the wrapper answers
``snapshot[code] or code in forced``.  Default bindings are the identity,
so with no user bindings the wrapper returns the snapshot unchanged.

A connected gamepad folds into the same forced set (left stick + buttons
per the kernel's pad map).  ``fire``'s canonical is the mouse, which the
key snapshot cannot express, so pad fire is not routed here; the pad
covers movement, interact, reload, sprint, advance and skip.

Bindings persist as plain data (``settings["bindings"]`` via
``ActionMap.to_bindings()`` -- non-defaults only).
"""
from __future__ import annotations

from typing import Any

import pygame

from engine.input import ActionMap

__all__ = ["load_bindings", "bindings_dict", "display_bindings",
           "set_binding", "reset_bindings", "apply"]

_map = ActionMap()
_joy = None
_joy_tried = False

_SPECIALS = {"shift": (pygame.K_LSHIFT, pygame.K_RSHIFT),
             "escape": (pygame.K_ESCAPE,),
             "space": (pygame.K_SPACE,),
             "mouse0": ()}


_code_cache: dict = {}


def _codes(name: str) -> tuple:
    if name in _SPECIALS:
        return _SPECIALS[name]
    if name not in _code_cache:
        try:
            _code_cache[name] = (pygame.key.key_code(name),)
        except Exception:
            _code_cache[name] = ()
    return _code_cache[name]


def _name_of(code: int) -> str:
    if code in (pygame.K_LSHIFT, pygame.K_RSHIFT):
        return "shift"
    try:
        return pygame.key.name(code)
    except Exception:
        return ""


def load_bindings(data: Any) -> None:
    global _map
    _map = ActionMap(data if isinstance(data, dict) else None)


def bindings_dict() -> dict:
    return _map.to_bindings()


def display_bindings() -> dict:
    return {name: spec["key"] for name, spec in _map.actions.items()}


def set_binding(action: str, key_name: str) -> None:
    if key_name in ("left shift", "right shift"):
        key_name = "shift"
    _map.set_binding(action, key_name)


def reset_bindings() -> None:
    global _map
    _map = ActionMap()


class _Wrapped:
    __slots__ = ("_base", "_forced")

    def __init__(self, base, forced):
        self._base = base
        self._forced = forced

    def __getitem__(self, code):
        return code in self._forced or bool(self._base[code])

    def __len__(self):
        return len(self._base)


def _pad_canonicals() -> set:
    global _joy, _joy_tried
    if _joy is None:
        if _joy_tried:
            return set()
        _joy_tried = True
        try:
            if pygame.joystick.get_count() > 0:
                _joy = pygame.joystick.Joystick(0)
                _joy.init()
        except Exception:
            return set()
        if _joy is None:
            return set()
    try:
        axes = [_joy.get_axis(i) for i in range(_joy.get_numaxes())]
        buttons = [_joy.get_button(i) for i in range(_joy.get_numbuttons())]
    except Exception:
        return set()
    return _map.pad_down(axes, buttons)


def apply(keys):
    """Wrap the raw pressed snapshot with bindings + gamepad (identity at defaults)."""
    names = set()
    for spec in _map.actions.values():
        names.add(spec["canonical"])
        names.add(spec["key"])
    down = set()
    for name in names:
        if any(keys[c] for c in _codes(name)):
            down.add(name)
    virtual = _map.remap(down)
    forced = set()
    for name in virtual:
        forced.update(_codes(name))
    for name in _pad_canonicals():
        forced.update(_codes(name))
    # Only canonicals the raw snapshot does not already report matter.
    forced = {c for c in forced if not keys[c]}
    if not forced:
        return keys
    return _Wrapped(keys, frozenset(forced))
