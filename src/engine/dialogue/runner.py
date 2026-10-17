"""dialogue.runner - DialogueRunner: walk a .dlg.json graph, emit lines (RPE6 §6.14).

The runner is a pure state machine. The host (game side) provides flags/vars,
resolves text keys, and consumes events::

    runner = DialogueRunner(dlg, host)
    line = runner.begin()            # DialogueLine | DialogueEnded
    line = runner.advance()          # next line (respects conditions/effects)
    line = runner.choose(0)          # pick a choice on the current node

Conditions are data strings (``flag("met")``, ``var("heat") > 2``, ``not flag("x")``)
parsed by a tiny safe evaluator - identifiers resolve through the host only.
Effects run when a node is *entered*: ``set`` writes a host var, ``emit`` posts an
event name, ``objective`` posts an objective key. Skipping follows the dialogue's
metadata (``skippable`` default True): ``skip()`` jumps to the end, applying no
further effects (deterministic: the same nodes, just not shown).
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Protocol

from .model import Dialogue

__all__ = ["DialogueHost", "DialogueLine", "DialogueEnded", "DialogueRunner"]


class DialogueHost(Protocol):
    def flag(self, name: str) -> bool: ...
    def var(self, name: str) -> Any: ...
    def set_var(self, name: str, value: Any) -> None: ...
    def emit(self, name: str, payload: Any = None) -> None: ...
    def resolve(self, node: dict) -> str: ...
    def speaker_meta(self, speaker: str | None) -> dict: ...


@dataclass
class DialogueLine:
    node_id: str
    speaker: str | None
    text: str
    choices: list = field(default_factory=list)     # [(label, target_node_id)]
    timing: dict = field(default_factory=dict)
    meta: dict = field(default_factory=dict)        # speaker meta (colour etc.)


@dataclass
class DialogueEnded:
    dialogue_id: str
    visited: tuple = ()                              # node ids entered, in order
    skipped: bool = False


_COND = re.compile(r'^\s*(not\s+)?(flag|var)\(\s*"([^"]+)"\s*\)\s*(?:(==|!=|>=|<=|>|<)\s*(-?\d+(?:\.\d+)?))?\s*$')


def eval_condition(expr: str | None, host: DialogueHost) -> bool:
    """Evaluate one condition string through the host. Unknown shapes raise ValueError (loud, R1)."""
    if not expr:
        return True
    m = _COND.match(expr)
    if not m:
        raise ValueError(f"dialogue condition not understood: {expr!r} (want flag(\"x\") / var(\"n\") OP num)")
    neg, kind, name, op, num = m.groups()
    val = host.flag(name) if kind == "flag" else host.var(name)
    if op is None:
        out = bool(val)
    else:
        rhs = float(num)
        lhs = float(val) if val is not None else 0.0
        out = {"==": lhs == rhs, "!=": lhs != rhs, ">": lhs > rhs, "<": lhs < rhs,
               ">=": lhs >= rhs, "<=": lhs <= rhs}[op]
    return (not out) if neg else out


class DialogueRunner:
    def __init__(self, dialogue: Dialogue, host: DialogueHost) -> None:
        self.dlg = dialogue
        self.host = host
        self.current: str | None = None
        self.visited: list[str] = []
        self.ended = False
        self._pending_choice: list | None = None

    # ── flow ───────────────────────────────────────────────────────────────
    def begin(self):
        return self._enter(self.dlg.start)

    def _enter(self, node_id: str | None):
        # follow condition-false nodes through their "next" without showing them
        hops = 0
        while node_id is not None:
            hops += 1
            if hops > 10000:
                raise ValueError(f"dialogue {self.dlg.id}: condition chain too long at {node_id!r}")
            node = self.dlg.node(node_id)
            if not eval_condition(node.get("condition"), self.host):
                node_id = node.get("next")
                continue
            break
        if node_id is None:
            return self._end()
        self.current = node_id
        self.visited.append(node_id)
        node = self.dlg.node(node_id)
        for eff in node.get("effects", []) or []:
            self._effect(eff)
        choices = []
        for c in node.get("choices", []) or []:
            if eval_condition(c.get("condition"), self.host):
                label = c.get("label") or self.host.resolve({"text_key": c.get("label_key")})
                choices.append((label, c.get("next")))
        self._pending_choice = choices or None
        return DialogueLine(node_id=node_id, speaker=node.get("speaker"), text=self.host.resolve(node),
                            choices=choices, timing=dict(node.get("timing", {})),
                            meta=self.host.speaker_meta(node.get("speaker")))

    def _effect(self, eff: dict) -> None:
        if "set" in eff:
            self.host.set_var(eff["set"], eff.get("value"))
        if "emit" in eff:
            self.host.emit(eff["emit"], eff.get("payload"))
        if "objective" in eff:
            self.host.emit("objective", eff["objective"])

    def advance(self):
        """Next line: from a choice node this is an error (use ``choose``); else follow ``next``."""
        if self.ended:
            return DialogueEnded(self.dlg.id, tuple(self.visited))
        if self._pending_choice:
            raise ValueError(f"dialogue {self.dlg.id}: node {self.current!r} waits for choose()")
        node = self.dlg.node(self.current) if self.current else {}
        return self._enter(node.get("next"))

    def choose(self, index: int):
        if not self._pending_choice:
            raise ValueError(f"dialogue {self.dlg.id}: no choices pending at {self.current!r}")
        _label, target = self._pending_choice[index]
        self._pending_choice = None
        return self._enter(target)

    def skip(self):
        """Jump to the end without applying further effects (metadata ``skippable`` permitting)."""
        if not self.dlg.metadata.get("skippable", True):
            raise ValueError(f"dialogue {self.dlg.id} is not skippable")
        return self._end(skipped=True)

    def _end(self, skipped: bool = False):
        self.ended = True
        self.current = None
        self._pending_choice = None
        return DialogueEnded(self.dlg.id, tuple(self.visited), skipped)
