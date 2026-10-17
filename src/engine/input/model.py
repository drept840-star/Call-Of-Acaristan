"""input.model - action maps and pressed-state remapping (RPE6 §6.10, Phase 9).

Gameplay code in this tree reads a raw pressed-key snapshot indexed by
legacy key constants at hundreds of sites.  Rather than rewriting every
reader, the action map works one level up: it computes a *virtual*
pressed set from the physical one.  Each action has a canonical key
(the name legacy code already tests) and a bound physical key; when the
physical key is down, the canonical name is reported down too, so every
legacy reader respects bindings unchanged.  Default bindings are the
identity.  A gamepad folds into the same set: axes/buttons map to
canonical names via the action's ``pad`` entry.

Everything here is name-based and headless: the host converts its
device snapshot to a set of key names, calls :func:`remap`, and tests
:meth:`ActionMap.down` - or converts the virtual set back to its native
snapshot form.
"""
from __future__ import annotations

from typing import Iterable, Mapping

__all__ = ["DEFAULT_ACTIONS", "ActionMap", "validate"]


# action -> (canonical legacy key name, default physical key name, pad)
DEFAULT_ACTIONS = {
    "move_up": ("w", "w", {"axis": [1, -1]}),
    "move_down": ("s", "s", {"axis": [1, 1]}),
    "move_left": ("a", "a", {"axis": [0, -1]}),
    "move_right": ("d", "d", {"axis": [0, 1]}),
    "fire": ("mouse0", "mouse0", {"button": 7}),
    "interact": ("e", "e", {"button": 0}),
    "reload": ("r", "r", {"button": 2}),
    "sprint": ("shift", "shift", {"button": 8}),
    "advance": ("space", "space", {"button": 0}),
    "skip": ("escape", "escape", {"button": 9}),
}


def validate(actions: Mapping) -> list[str]:
    out: list[str] = []
    if not isinstance(actions, dict) or not actions:
        return ["action map is empty"]
    for name, spec in actions.items():
        if not isinstance(spec, dict):
            out.append(f"action {name!r}: not an object")
            continue
        for key in ("canonical", "key"):
            if key in spec and not isinstance(spec[key], str):
                out.append(f"action {name!r}: {key} must be a key name string")
        pad = spec.get("pad")
        if pad is not None and not isinstance(pad, dict):
            out.append(f"action {name!r}: pad must be an object")
    return out


class ActionMap:
    """Bindings: action -> {canonical, key (physical), pad}."""

    def __init__(self, bindings: Mapping | None = None):
        self.actions: dict[str, dict] = {}
        for name, (canonical, key, pad) in DEFAULT_ACTIONS.items():
            self.actions[name] = {"canonical": canonical, "key": key, "pad": dict(pad)}
        for name, spec in (bindings or {}).items():
            if name in self.actions and isinstance(spec, dict):
                if isinstance(spec.get("key"), str):
                    self.actions[name]["key"] = spec["key"]
                if isinstance(spec.get("pad"), dict):
                    self.actions[name]["pad"] = dict(spec["pad"])

    def binding(self, action: str) -> str:
        return self.actions[action]["key"]

    def set_binding(self, action: str, key_name: str) -> None:
        if action not in self.actions:
            raise KeyError(f"unknown action {action!r}")
        self.actions[action]["key"] = str(key_name)

    def to_bindings(self) -> dict:
        """Only non-default bindings (what a settings file should store)."""
        return {name: {"key": spec["key"]} for name, spec in self.actions.items()
                if spec["key"] != DEFAULT_ACTIONS[name][1]}

    def remap(self, physical_down: Iterable[str]) -> set:
        """Virtual pressed set: physical + canonicals of bound actions."""
        down = set(physical_down)
        virtual = set(down)
        for spec in self.actions.values():
            if spec["key"] in down:
                virtual.add(spec["canonical"])
        return virtual

    def pad_down(self, axes, buttons, deadzone: float = 0.35) -> set:
        """Canonical names currently held on a gamepad (host supplies state)."""
        out = set()
        for spec in self.actions.values():
            pad = spec.get("pad") or {}
            btn = pad.get("button")
            if btn is not None and btn < len(buttons) and buttons[btn]:
                out.add(spec["canonical"])
                continue
            axis = pad.get("axis")
            if axis is not None and axis[0] < len(axes):
                idx, direction = axis
                if axes[idx] * direction > deadzone:
                    out.add(spec["canonical"])
        return out

    def down(self, action: str, virtual_down) -> bool:
        return self.actions[action]["canonical"] in virtual_down
